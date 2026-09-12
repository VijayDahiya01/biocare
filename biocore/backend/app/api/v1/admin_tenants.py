"""Super-admin tenant provisioning + entity-admin user creation (API Reference §13.1)."""
from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.api.deps import Principal, auth_db, require_role
from app.core.db import get_db, set_tenant_guc
from app.core.envelope import success
from app.dpdp.audit import write_audit
from app.schemas.auth import CreateAdminRequest, ProvisionTenantRequest
from app.services.auth_service import create_admin, provision_tenant

router = APIRouter(prefix="/admin", tags=["admin"])


@router.post("/tenants")
def create_tenant(request: Request, body: ProvisionTenantRequest,
                  db: Session = Depends(get_db)):
    """Provision a new tenant + its first entity admin.

    Phase 0 note: open bootstrap endpoint so the stack can be initialised. In
    production this is gated to the platform super_admin (TODO: enable the
    require_role guard once a platform admin exists)."""
    result = provision_tenant(
        db,
        name=body.name, org_code=body.org_code, vertical=body.vertical,
        plan=body.plan, admin_email=body.admin_email,
        admin_password=body.admin_password, admin_name=body.admin_name,
    )
    set_tenant_guc(db, result["tenant_id"])
    write_audit(db, action="TENANT_PROVISIONED", tenant_id=result["tenant_id"],
                target_id=result["tenant_id"], request_id=request.state.request_id,
                metadata={"org_code": result["org_code"]})
    db.commit()
    return success(request, result, status_code=201)


@router.post("/users")
def add_admin(request: Request, body: CreateAdminRequest,
              principal: Principal = Depends(require_role("entity_admin", "super_admin")),
              db: Session = Depends(auth_db)):
    """Entity admin invites another admin/staff member within their tenant."""
    result = create_admin(
        db, tenant_id=principal.tenant_id, email=body.email,
        password=body.password, name=body.name, role=body.role,
    )
    write_audit(db, action="ADMIN_CREATED", actor_id=principal.user_id,
                tenant_id=principal.tenant_id, target_id=result["user_id"],
                request_id=request.state.request_id)
    db.commit()
    return success(request, result, status_code=201)
