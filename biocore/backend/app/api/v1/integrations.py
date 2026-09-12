"""ERP / HR connectors (API Reference §14.8)."""
from datetime import date, datetime, time, timezone

from fastapi import APIRouter, Depends, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import Principal, auth_db, get_db_for, get_principal, require_role
from app.core.envelope import success
from app.dpdp.audit import write_audit
from app.models import AttendanceLog, Integration
from app.schemas.modules import ErpSync
from app.services import webhook_service

router = APIRouter(tags=["integrations"])
_ADMIN = ("entity_admin", "super_admin")


def _scoped_db(principal: Principal = Depends(get_principal)) -> Session:
    yield from get_db_for(principal)


@router.get("/integrations")
def list_integrations(request: Request, principal: Principal = Depends(require_role(*_ADMIN)),
                      db: Session = Depends(_scoped_db)):
    rows = db.execute(select(Integration)).scalars().all()
    items = [{"id": str(i.id), "kind": i.kind, "status": i.status} for i in rows]
    return success(request, {"items": items})


@router.post("/integrations/erp/sync")
def erp_sync(request: Request, body: ErpSync,
             principal: Principal = Depends(require_role(*_ADMIN)),
             db: Session = Depends(auth_db)):
    """Push attendance to a connected ERP. Delivery rides the signed webhook
    channel (event attendance.recorded); here we trigger a batch push."""
    today = date.today()
    from_d = date.fromisoformat(body.from_date) if body.from_date else today
    to_d = date.fromisoformat(body.to_date) if body.to_date else today
    lo = datetime.combine(from_d, time.min, timezone.utc)
    hi = datetime.combine(to_d, time.max, timezone.utc)
    logs = db.execute(
        select(AttendanceLog).where(AttendanceLog.created_at.between(lo, hi))
    ).scalars().all()
    payload = {"kind": body.kind, "records": [
        {"user_id": str(rec.user_id), "event": rec.event_type, "at": rec.created_at.isoformat()}
        for rec in logs
    ]}
    sent = webhook_service.dispatch(db, tenant_id=principal.tenant_id,
                                    event="attendance.recorded", payload=payload)
    write_audit(db, action="ERP_SYNC", actor_id=principal.user_id,
                tenant_id=principal.tenant_id, request_id=request.state.request_id,
                metadata={"kind": body.kind, "records": len(logs)})
    db.commit()
    return success(request, {"kind": body.kind, "records": len(logs), "dispatched": sent})
