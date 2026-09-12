"""Payroll calculation from attendance + wage config (API Reference §9)."""
from collections import defaultdict
from datetime import date, datetime, time, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import AttendanceLog, User, WageConfig
from app.services.payroll_logic import calc_pay, worked_break_minutes


def _current_wage(db: Session, user_id: str) -> WageConfig | None:
    return db.execute(
        select(WageConfig).where(WageConfig.user_id == user_id)
        .order_by(WageConfig.effective_from.desc()).limit(1)
    ).scalar_one_or_none()


def calculate(db: Session, *, from_date: date, to_date: date,
              user_id: str | None = None) -> list[dict]:
    stmt = select(AttendanceLog).where(
        AttendanceLog.created_at >= datetime.combine(from_date, time.min, timezone.utc),
        AttendanceLog.created_at <= datetime.combine(to_date, time.max, timezone.utc),
    )
    if user_id:
        stmt = stmt.where(AttendanceLog.user_id == user_id)
    logs = db.execute(stmt).scalars().all()

    # group events by (user, day)
    by_user_day: dict[str, dict[date, list]] = defaultdict(lambda: defaultdict(list))
    for log in logs:
        by_user_day[str(log.user_id)][log.created_at.date()].append(
            (log.event_type, log.created_at)
        )

    items = []
    for uid, days in by_user_day.items():
        wage = _current_wage(db, uid)
        if not wage:
            continue  # only hourly/daily workers with a wage config are paid here
        daily_hours = []
        for _day, events in days.items():
            worked, _brk = worked_break_minutes(events)
            daily_hours.append(worked / 60.0)
        pay = calc_pay(daily_hours, float(wage.rate_per_hour), float(wage.overtime_multiplier))
        user = db.get(User, uid)
        items.append({
            "user_id": uid,
            "name": f"{user.first_name} {user.last_name or ''}".strip() if user else uid,
            **pay,
        })
    return items
