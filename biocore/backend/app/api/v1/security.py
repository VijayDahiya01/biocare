"""High-security analytics: zone-movement trails + PPE violations (Phase 4)."""
from datetime import date, datetime, time, timezone

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import Principal, get_db_for, get_principal, require_role
from app.core.envelope import success
from app.models import AccessEvent, AttendanceLog, Zone
from app.services.movement_logic import analyze_movement

router = APIRouter(prefix="/security", tags=["security"])
_SEC = ("entity_admin", "manager", "auditor_dpo", "super_admin")


def _scoped_db(principal: Principal = Depends(get_principal)) -> Session:
    yield from get_db_for(principal)


def _range(from_d: date, to_d: date):
    return (datetime.combine(from_d, time.min, timezone.utc),
            datetime.combine(to_d, time.max, timezone.utc))


@router.get("/movement")
def movement(request: Request, user_id: str = Query(...),
             from_: date = Query(alias="from"), to: date = Query(alias="to"),
             principal: Principal = Depends(require_role(*_SEC)),
             db: Session = Depends(_scoped_db)):
    lo, hi = _range(from_, to)
    rows = db.execute(
        select(AttendanceLog.zone_id, AttendanceLog.event_type, AttendanceLog.created_at)
        .where(AttendanceLog.user_id == user_id, AttendanceLog.created_at.between(lo, hi))
    ).all()
    events = [(str(z) if z else None, et, t) for z, et, t in rows]
    restricted = {
        str(z.id) for z in db.execute(select(Zone).where(Zone.type == "restricted")).scalars().all()
    }
    return success(request, analyze_movement(events, restricted))


@router.get("/ppe-violations")
def ppe_violations(request: Request,
                   from_: date = Query(alias="from"), to: date = Query(alias="to"),
                   principal: Principal = Depends(require_role(*_SEC)),
                   db: Session = Depends(_scoped_db)):
    lo, hi = _range(from_, to)
    rows = db.execute(
        select(AccessEvent).where(
            AccessEvent.reason == "ppe_missing", AccessEvent.created_at.between(lo, hi)
        ).order_by(AccessEvent.created_at.desc()).limit(500)
    ).scalars().all()
    items = [{"user_id": str(e.user_id) if e.user_id else None,
              "zone_id": str(e.zone_id) if e.zone_id else None,
              "at": e.created_at.isoformat()} for e in rows]
    return success(request, {"items": items})
