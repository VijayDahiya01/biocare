"""Roles & permissions (API Reference §10). 12 presets + custom roles."""
import re

from fastapi import APIRouter, Depends, Request
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import Principal, auth_db, get_db_for, get_principal, require_role
from app.core.envelope import ApiError, success
from app.dpdp.audit import write_audit
from app.models import Role, User
from app.schemas.modules import RoleCreate, RoleUpdate

router = APIRouter(tags=["roles"])
_ADMIN = ("entity_admin", "super_admin")

# Catalogue used to build the role-editor UI.
PERMISSION_CATALOG = {
    "attendance": ["attendance.view", "attendance.edit"],
    "users": ["users.view", "users.create", "users.delete"],
    "zones": ["zones.view", "zones.create"],
    "badges": ["badges.view", "badges.create", "badges.assign"],
    "devices": ["devices.view", "devices.create"],
    "reports": ["reports.view", "reports.export"],
    "alerts": ["alerts.view", "alerts.dismiss"],
    "dpdp": ["dpdp.view", "audit.view", "consent.view"],
    "settings": ["settings.view", "settings.edit"],
    "enroll": ["admin.enroll", "visitors.manage"],
}


def _scoped_db(principal: Principal = Depends(get_principal)) -> Session:
    yield from get_db_for(principal)


@router.get("/roles")
def list_roles(request: Request, principal: Principal = Depends(require_role(*_ADMIN)),
               db: Session = Depends(_scoped_db)):
    # RLS returns global presets (tenant_id NULL) + this tenant's custom roles.
    rows = db.execute(select(Role)).scalars().all()
    items = [{"role_id": str(r.id), "key": r.key, "name": r.name,
              "is_preset": r.is_preset, "permissions": r.permissions, "scope": r.scope}
             for r in rows]
    return success(request, {"items": items})


@router.post("/roles")
def create_role(request: Request, body: RoleCreate,
                principal: Principal = Depends(require_role(*_ADMIN)),
                db: Session = Depends(auth_db)):
    key = "custom_" + re.sub(r"[^a-z0-9]+", "_", body.name.lower()).strip("_")
    role = Role(tenant_id=principal.tenant_id, key=key, name=body.name,
                is_preset=False, permissions=body.permissions, scope=body.scope)
    db.add(role)
    write_audit(db, action="ROLE_CREATED", actor_id=principal.user_id,
                tenant_id=principal.tenant_id, request_id=request.state.request_id)
    db.commit()
    return success(request, {"role_id": str(role.id), "key": key}, status_code=201)


@router.patch("/roles/{role_id}")
def update_role(request: Request, role_id: str, body: RoleUpdate,
                principal: Principal = Depends(require_role(*_ADMIN)),
                db: Session = Depends(auth_db)):
    role = db.get(Role, role_id)
    if not role:
        raise ApiError(404, "ROLE_NOT_FOUND", "Role not found.")
    if role.is_preset:
        raise ApiError(403, "PRESET_IMMUTABLE", "Preset roles cannot be edited.")
    if body.permissions is not None:
        role.permissions = body.permissions
    if body.scope is not None:
        role.scope = body.scope
    db.commit()
    return success(request, {"role_id": role_id})


@router.delete("/roles/{role_id}")
def delete_role(request: Request, role_id: str,
                principal: Principal = Depends(require_role(*_ADMIN)),
                db: Session = Depends(auth_db)):
    role = db.get(Role, role_id)
    if not role:
        raise ApiError(404, "ROLE_NOT_FOUND", "Role not found.")
    if role.is_preset:
        raise ApiError(403, "PRESET_IMMUTABLE", "Preset roles cannot be deleted.")
    assigned = db.execute(
        select(func.count()).select_from(User).where(User.role == role.key)
    ).scalar_one()
    if assigned:
        raise ApiError(409, "ROLE_IN_USE", f"{assigned} users still hold this role.")
    db.delete(role)
    db.commit()
    return success(request, {"deleted": True})


@router.get("/permissions")
def list_permissions(request: Request, principal: Principal = Depends(require_role(*_ADMIN))):
    return success(request, PERMISSION_CATALOG)
