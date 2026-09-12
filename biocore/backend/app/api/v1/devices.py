"""Device (kiosk) management (API Reference §5.4)."""
from fastapi import APIRouter, Depends, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import Principal, auth_db, require_role
from app.core.envelope import success
from app.dpdp.audit import write_audit
from app.models import Device
from app.schemas.device import CreateDeviceRequest
from app.services.device_service import disable_device, register_device

router = APIRouter(prefix="/devices", tags=["devices"])

_ADMIN = ("entity_admin", "manager", "super_admin")


@router.get("")
def list_devices(request: Request,
                 principal: Principal = Depends(require_role(*_ADMIN)),
                 db: Session = Depends(auth_db)):
    rows = db.execute(select(Device)).scalars().all()
    items = [
        {"device_id": str(d.id), "name": d.name, "zone_id": str(d.zone_id) if d.zone_id else None,
         "capture_method": d.capture_method, "status": d.status,
         "last_seen": d.last_seen.isoformat() if d.last_seen else None}
        for d in rows
    ]
    return success(request, {"items": items, "total": len(items)})


@router.post("")
def create_device(request: Request, body: CreateDeviceRequest,
                  principal: Principal = Depends(require_role(*_ADMIN)),
                  db: Session = Depends(auth_db)):
    result = register_device(
        db, tenant_id=principal.tenant_id, name=body.name,
        zone_id=body.zone_id, capture_method=body.capture_method,
    )
    write_audit(db, action="DEVICE_REGISTERED", actor_id=principal.user_id,
                tenant_id=principal.tenant_id, target_id=result["device_id"],
                request_id=request.state.request_id)
    db.commit()
    return success(request, result, status_code=201)


@router.post("/{device_id}/disable")
def disable(request: Request, device_id: str,
            principal: Principal = Depends(require_role(*_ADMIN)),
            db: Session = Depends(auth_db)):
    disable_device(db, device_id=device_id)
    write_audit(db, action="DEVICE_DISABLED", actor_id=principal.user_id,
                tenant_id=principal.tenant_id, target_id=device_id,
                request_id=request.state.request_id)
    db.commit()
    return success(request, {"device_id": device_id, "status": "disabled"})
