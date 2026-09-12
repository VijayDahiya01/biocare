"""Read-only reporting aggregations (API Reference §11). Never mutates data."""
from datetime import date, datetime, time, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import AccessEvent, AttendanceLog, User


def _range(from_date: date, to_date: date):
    return (datetime.combine(from_date, time.min, timezone.utc),
            datetime.combine(to_date, time.max, timezone.utc))


def attendance(db: Session, *, from_date: date, to_date: date, group_by: str = "day") -> list[dict]:
    lo, hi = _range(from_date, to_date)
    checkins = select(AttendanceLog).where(
        AttendanceLog.event_type == "check_in",
        AttendanceLog.created_at.between(lo, hi),
    ).subquery()

    if group_by == "user":
        rows = db.execute(
            select(User.id, User.first_name, User.last_name, func.count(checkins.c.id))
            .join(checkins, checkins.c.user_id == User.id)
            .group_by(User.id, User.first_name, User.last_name)
        ).all()
        return [{"user_id": str(r[0]), "name": f"{r[1]} {r[2] or ''}".strip(), "check_ins": r[3]} for r in rows]

    if group_by == "department":
        rows = db.execute(
            select(User.department, func.count(checkins.c.id))
            .join(checkins, checkins.c.user_id == User.id)
            .group_by(User.department)
        ).all()
        return [{"department": r[0] or "—", "check_ins": r[1]} for r in rows]

    # default: by day
    rows = db.execute(
        select(func.date(AttendanceLog.created_at), func.count())
        .where(AttendanceLog.event_type == "check_in", AttendanceLog.created_at.between(lo, hi))
        .group_by(func.date(AttendanceLog.created_at))
        .order_by(func.date(AttendanceLog.created_at))
    ).all()
    return [{"date": str(r[0]), "check_ins": r[1]} for r in rows]


def late(db: Session, *, from_date: date, to_date: date, threshold: str = "09:30") -> list[dict]:
    lo, hi = _range(from_date, to_date)
    th = time.fromisoformat(threshold)
    # earliest check-in per user per day
    rows = db.execute(
        select(AttendanceLog.user_id, func.date(AttendanceLog.created_at),
               func.min(AttendanceLog.created_at))
        .where(AttendanceLog.event_type == "check_in", AttendanceLog.created_at.between(lo, hi))
        .group_by(AttendanceLog.user_id, func.date(AttendanceLog.created_at))
    ).all()
    out = []
    for uid, day, first in rows:
        if first.timetz().replace(tzinfo=None) > th:
            out.append({"user_id": str(uid), "date": str(day), "first_check_in": first.isoformat()})
    return out


def absent(db: Session, *, on_date: date) -> list[dict]:
    lo, hi = _range(on_date, on_date)
    present = select(AttendanceLog.user_id).where(
        AttendanceLog.event_type == "check_in", AttendanceLog.created_at.between(lo, hi)
    ).distinct().subquery()
    rows = db.execute(
        select(User.id, User.first_name, User.last_name)
        .where(User.status == "active", User.deleted_at.is_(None), User.id.not_in(select(present.c.user_id)))
    ).all()
    return [{"user_id": str(r[0]), "name": f"{r[1]} {r[2] or ''}".strip()} for r in rows]


def zone_access(db: Session, *, from_date: date, to_date: date) -> list[dict]:
    lo, hi = _range(from_date, to_date)
    rows = db.execute(
        select(AccessEvent).where(AccessEvent.created_at.between(lo, hi))
        .order_by(AccessEvent.created_at.desc()).limit(1000)
    ).scalars().all()
    return [{"user_id": str(e.user_id) if e.user_id else None, "zone_id": str(e.zone_id) if e.zone_id else None,
             "granted": e.granted, "reason": e.reason, "at": e.created_at.isoformat()} for e in rows]


def footfall(db: Session, *, from_date: date, to_date: date) -> list[dict]:
    lo, hi = _range(from_date, to_date)
    rows = db.execute(
        select(AttendanceLog.zone_id, func.count())
        .where(AttendanceLog.created_at.between(lo, hi))
        .group_by(AttendanceLog.zone_id)
    ).all()
    return [{"zone_id": str(r[0]) if r[0] else "unzoned", "count": r[1]} for r in rows]


def movement(db: Session, *, user_id: str, from_date: date, to_date: date) -> list[dict]:
    lo, hi = _range(from_date, to_date)
    rows = db.execute(
        select(AttendanceLog.zone_id, AttendanceLog.event_type, AttendanceLog.created_at)
        .where(AttendanceLog.user_id == user_id, AttendanceLog.created_at.between(lo, hi))
        .order_by(AttendanceLog.created_at)
    ).all()
    return [{"zone_id": str(r[0]) if r[0] else None, "event": r[1], "at": r[2].isoformat()} for r in rows]
