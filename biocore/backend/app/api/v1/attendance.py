"""Attendance log + live presence (API Reference §4.1, §4.4). Admin-facing, read."""
from datetime import date, datetime, time, timezone

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import Principal, auth_db, get_db_for, get_principal, require_role
from app.core.envelope import success
from app.dpdp.audit import write_audit
from app.models import AttendanceLog, CurrentPresence, User
from app.schemas.modules import ManualEvent

router = APIRouter(prefix="/attendance", tags=["attendance"])
# security_reception included so a guard can do a manual override at the gate.
_ADMIN = ("entity_admin", "manager", "hr_payroll", "security_reception", "super_admin")


def _scoped_db(principal: Principal = Depends(get_principal)) -> Session:
    # read-only admin views: tenant-scoped DB, no CSRF (GET).
    yield from get_db_for(principal)


@router.get("")
def list_attendance(
    request: Request,
    principal: Principal = Depends(get_principal),
    db: Session = Depends(_scoped_db),
    from_: date | None = Query(None, alias="from"),
    to: date | None = Query(None, alias="to"),
    department: str | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
):
    """Event-level attendance log with filters + pagination.

    (A per-user daily check_in/check_out summary view is a Phase 1.x refinement;
    the live feed and log both consume this event stream.)"""
    stmt = select(AttendanceLog, User).join(User, User.id == AttendanceLog.user_id)
    if from_:
        stmt = stmt.where(AttendanceLog.created_at >= datetime.combine(from_, time.min, timezone.utc))
    if to:
        stmt = stmt.where(AttendanceLog.created_at <= datetime.combine(to, time.max, timezone.utc))
    if department:
        stmt = stmt.where(User.department == department)

    total = db.execute(
        select(func.count()).select_from(stmt.order_by(None).subquery())
    ).scalar_one()

    rows = db.execute(
        stmt.order_by(AttendanceLog.created_at.desc())
        .offset((page - 1) * page_size).limit(page_size)
    ).all()

    items = [
        {
            "user_id": str(log.user_id),
            "name": f"{user.first_name} {user.last_name or ''}".strip(),
            "event_type": log.event_type,
            "timestamp": log.created_at.isoformat(),
            "score": log.match_score,
            "device_id": str(log.device_id) if log.device_id else None,
            "department": user.department,
        }
        for log, user in rows
    ]
    return success(request, {"items": items, "total": total, "page": page, "page_size": page_size})


@router.post("/manual")
def manual_event(request: Request, body: ManualEvent,
                 principal: Principal = Depends(require_role(*_ADMIN)),
                 db: Session = Depends(auth_db)):
    """Admin adds/corrects an event (e.g. a missed check-out). Logged with reason."""
    ts = datetime.fromisoformat(body.timestamp)
    db.add(AttendanceLog(
        tenant_id=principal.tenant_id, user_id=body.user_id, event_type=body.event,
        device_id=None, request_id=request.state.request_id,
    ))
    # keep presence consistent with the correction
    presence_row = db.get(CurrentPresence, (principal.tenant_id, body.user_id))
    if body.event == "check_in" and presence_row is None:
        db.add(CurrentPresence(tenant_id=principal.tenant_id, user_id=body.user_id, entered_at=ts))
    elif body.event == "check_out" and presence_row is not None:
        db.delete(presence_row)
    write_audit(db, action="ATTENDANCE_MANUAL", actor_id=principal.user_id,
                tenant_id=principal.tenant_id, target_id=body.user_id,
                request_id=request.state.request_id,
                metadata={"event": body.event, "reason": body.reason, "timestamp": body.timestamp})
    db.commit()
    return success(request, {"user_id": body.user_id, "event": body.event}, status_code=201)


@router.get("/presence")
def presence(request: Request,
             principal: Principal = Depends(get_principal),
             db: Session = Depends(_scoped_db)):
    """Everyone currently inside, in real time — powers metrics + emergency headcount."""
    rows = db.execute(
        select(CurrentPresence, User).join(User, User.id == CurrentPresence.user_id)
    ).all()

    by_zone: dict[str, int] = {}
    people = []
    for pres, user in rows:
        zone = str(pres.zone_id) if pres.zone_id else "unzoned"
        by_zone[zone] = by_zone.get(zone, 0) + 1
        people.append({
            "user_id": str(pres.user_id),
            "name": f"{user.first_name} {user.last_name or ''}".strip(),
            "since": pres.entered_at.isoformat(),
        })

    return success(request, {
        "inside_count": len(people),
        "by_zone": by_zone,
        "people": people,
    })
