"""Tenant settings + outbound webhooks (API Reference §13, §6.3)."""
from fastapi import APIRouter, Depends, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import Principal, auth_db, get_db_for, get_principal, require_role
from app.core.envelope import ApiError, success
from app.dpdp.audit import write_audit
from app.models import Tenant, WebhookConfig
from app.schemas.access import WebhookCreate

# How much proof an organisation wants before it issues an entry credential.
_VERIFICATION_LEVELS = ("face_only", "face_and_document", "face_and_government")

router = APIRouter(prefix="/settings", tags=["settings"])
_ADMIN = ("entity_admin", "super_admin")


def _scoped_db(principal: Principal = Depends(get_principal)) -> Session:
    yield from get_db_for(principal)


@router.get("")
def get_settings(request: Request, principal: Principal = Depends(require_role(*_ADMIN)),
                 db: Session = Depends(_scoped_db)):
    tenant = db.get(Tenant, principal.tenant_id)
    return success(request, {
        "branding": tenant.branding, "dpdp": tenant.dpdp_config,
        "settings": tenant.settings, "vertical": tenant.vertical, "plan": tenant.plan,
        "verification_level": tenant.verification_level or "face_only",
    })


@router.patch("")
def patch_settings(request: Request, body: dict,
                   principal: Principal = Depends(require_role(*_ADMIN)),
                   db: Session = Depends(auth_db)):
    tenant = db.get(Tenant, principal.tenant_id)
    if "branding" in body:
        tenant.branding = {**(tenant.branding or {}), **body["branding"]}
    if "dpdp" in body:
        tenant.dpdp_config = {**(tenant.dpdp_config or {}), **body["dpdp"]}
    if "verification_level" in body:
        level = str(body["verification_level"])
        if level not in _VERIFICATION_LEVELS:
            raise ApiError(400, "VERIFICATION_LEVEL_INVALID",
                           f"Choose one of: {', '.join(_VERIFICATION_LEVELS)}.")
        tenant.verification_level = level
    # everything else (match_threshold, modules_enabled, ...) goes into settings.
    extras = {k: v for k, v in body.items()
              if k not in ("branding", "dpdp", "verification_level")}
    if extras:
        tenant.settings = {**(tenant.settings or {}), **extras}
    write_audit(db, action="SETTINGS_UPDATED", actor_id=principal.user_id,
                tenant_id=principal.tenant_id, request_id=request.state.request_id)
    db.commit()
    return success(request, {"updated": True})


@router.get("/webhooks")
def list_webhooks(request: Request, principal: Principal = Depends(require_role(*_ADMIN)),
                  db: Session = Depends(_scoped_db)):
    rows = db.execute(select(WebhookConfig)).scalars().all()
    items = [{"id": str(w.id), "event": w.event, "url": w.url, "active": w.active} for w in rows]
    return success(request, {"items": items})


@router.post("/webhooks")
def add_webhook(request: Request, body: WebhookCreate,
                principal: Principal = Depends(require_role(*_ADMIN)),
                db: Session = Depends(auth_db)):
    hook = WebhookConfig(tenant_id=principal.tenant_id, event=body.event,
                         url=body.url, secret=body.secret)
    db.add(hook)
    write_audit(db, action="WEBHOOK_ADDED", actor_id=principal.user_id,
                tenant_id=principal.tenant_id, request_id=request.state.request_id)
    db.commit()
    return success(request, {"id": str(hook.id)}, status_code=201)


@router.delete("/webhooks/{webhook_id}")
def delete_webhook(request: Request, webhook_id: str,
                   principal: Principal = Depends(require_role(*_ADMIN)),
                   db: Session = Depends(auth_db)):
    hook = db.get(WebhookConfig, webhook_id)
    if hook:
        db.delete(hook)
        db.commit()
    return success(request, {"deleted": True})
