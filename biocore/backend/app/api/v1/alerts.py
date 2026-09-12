"""Alerts + alert routing settings (API Reference §12)."""
from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.api.deps import Principal, auth_db, get_db_for, get_principal, require_role
from app.core.envelope import success
from app.dpdp.audit import write_audit
from app.models import Tenant
from app.schemas.access import AlertSettings
from app.services import alert_service

router = APIRouter(prefix="/alerts", tags=["alerts"])
_ADMIN = ("entity_admin", "manager", "security_reception", "super_admin")


def _scoped_db(principal: Principal = Depends(get_principal)) -> Session:
    yield from get_db_for(principal)


@router.get("")
def list_alerts(request: Request, principal: Principal = Depends(require_role(*_ADMIN)),
                db: Session = Depends(_scoped_db),
                priority: str | None = None, type: str | None = None):
    return success(request, {"items": alert_service.list_alerts(db, priority=priority, type=type)})


@router.post("/{alert_id}/dismiss")
def dismiss(request: Request, alert_id: str,
            principal: Principal = Depends(require_role(*_ADMIN)),
            db: Session = Depends(auth_db)):
    alert_service.dismiss_alert(db, alert_id=alert_id, actor_id=principal.user_id)
    write_audit(db, action="ALERT_DISMISSED", actor_id=principal.user_id,
                tenant_id=principal.tenant_id, target_id=alert_id,
                request_id=request.state.request_id)
    db.commit()
    return success(request, {"alert_id": alert_id, "status": "dismissed"})


@router.get("/settings")
def get_settings(request: Request, principal: Principal = Depends(require_role(*_ADMIN)),
                 db: Session = Depends(_scoped_db)):
    tenant = db.get(Tenant, principal.tenant_id)
    return success(request, (tenant.settings or {}).get("alerts", {}))


@router.patch("/settings")
def patch_settings(request: Request, body: AlertSettings,
                   principal: Principal = Depends(require_role(*_ADMIN)),
                   db: Session = Depends(auth_db)):
    tenant = db.get(Tenant, principal.tenant_id)
    settings = dict(tenant.settings or {})
    settings["alerts"] = {**settings.get("alerts", {}),
                          **{k: v for k, v in body.model_dump().items() if v is not None}}
    tenant.settings = settings
    db.commit()
    return success(request, settings["alerts"])
