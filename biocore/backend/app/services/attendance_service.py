"""Records attendance events and maintains the live current_presence table."""
from datetime import datetime, timezone

from sqlalchemy import delete as sa_delete
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from app.core.envelope import ApiError
from app.models import AttendanceLog, CurrentPresence
from app.services.toggle import CHECK_IN, decide_event


def is_inside(db: Session, *, tenant_id: str, user_id: str) -> bool:
    return db.get(CurrentPresence, (tenant_id, user_id)) is not None


def record_event(db: Session, *, tenant_id: str, user_id: str, action: str,
                 device_id: str | None, zone_id: str | None,
                 match_score: float | None, request_id: str | None) -> dict:
    """Apply toggle logic, write the log row, and update presence atomically.

    Returns the recorded event and (on check-out) the duration in minutes.
    """
    inside = is_inside(db, tenant_id=tenant_id, user_id=user_id)
    event = decide_event(action, inside)
    now = datetime.now(timezone.utc)

    log = AttendanceLog(
        tenant_id=tenant_id, user_id=user_id, event_type=event,
        match_score=match_score, device_id=device_id, zone_id=zone_id,
        request_id=request_id,
    )
    db.add(log)

    duration_minutes: int | None = None
    if event == CHECK_IN:
        # Atomic upsert: concurrent scans of the SAME person (rapid double-tap /
        # retries) must not race the check-then-insert into a PK violation.
        db.execute(
            pg_insert(CurrentPresence)
            .values(tenant_id=tenant_id, user_id=user_id, entered_at=now,
                    zone_id=zone_id, device_id=device_id)
            .on_conflict_do_nothing(index_elements=["tenant_id", "user_id"])
        )
    else:  # CHECK_OUT
        presence = db.get(CurrentPresence, (tenant_id, user_id))
        if presence is not None:
            delta = now - presence.entered_at
            duration_minutes = int(delta.total_seconds() // 60)
            db.execute(
                sa_delete(CurrentPresence).where(
                    CurrentPresence.tenant_id == tenant_id,
                    CurrentPresence.user_id == user_id,
                )
            )

    db.commit()
    return {
        "event": event,
        "timestamp": now.isoformat(),
        "duration_minutes": duration_minutes,
    }


def record_break(db: Session, *, tenant_id: str, user_id: str, break_type: str,
                 device_id: str | None, match_score: float | None,
                 request_id: str | None) -> dict:
    """Record a break_start / break_end. Breaks don't change presence; they are
    subtracted from worked time during payroll (see payroll_logic)."""
    if break_type not in ("start", "end"):
        raise ApiError(400, "BAD_BREAK", "break must be 'start' or 'end'.")
    event = "break_start" if break_type == "start" else "break_end"
    now = datetime.now(timezone.utc)
    db.add(AttendanceLog(
        tenant_id=tenant_id, user_id=user_id, event_type=event,
        match_score=match_score, device_id=device_id, request_id=request_id,
    ))
    db.commit()
    return {"event": event, "timestamp": now.isoformat()}
