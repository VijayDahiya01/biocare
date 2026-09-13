"""Auth + tenant provisioning.

These are the legitimate cross-tenant operations that explicitly opt out of RLS:
  * provision_tenant — creating a brand-new tenant (no tenant context yet).
  * authenticate     — login looks up a user by email before a tenant is known.
Both use bypass_rls() deliberately and narrowly.
"""
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.db import bypass_rls
from app.core.envelope import ApiError
from app.core.security import hash_password, verify_password
from app.models import Tenant, User


def provision_tenant(db: Session, *, name: str, org_code: str, vertical: str,
                     plan: str, admin_email: str, admin_password: str,
                     admin_name: str) -> dict:
    with bypass_rls(db):
        existing = db.execute(
            select(Tenant).where(Tenant.org_code == org_code)
        ).scalar_one_or_none()
        if existing:
            raise ApiError(409, "ORG_CODE_EXISTS", f"org_code {org_code} already in use.")

        tenant = Tenant(name=name, org_code=org_code, vertical=vertical, plan=plan)
        db.add(tenant)
        db.flush()  # get tenant.id

        admin = User(
            tenant_id=tenant.id,
            user_type="entity_admin",
            role="entity_admin",
            first_name=admin_name,
            email=admin_email,
            status="active",
            enrolled_by="self",
            password_hash=hash_password(admin_password),
        )
        db.add(admin)
        try:
            db.flush()
        except IntegrityError:
            db.rollback()
            raise ApiError(409, "EMAIL_EXISTS", "Admin email already registered.")
        db.commit()

        return {
            "tenant_id": str(tenant.id),
            "org_code": tenant.org_code,
            "admin_user_id": str(admin.id),
            "admin_email": admin.email,
        }


def create_admin(db: Session, *, tenant_id: str, email: str, password: str,
                 name: str, role: str) -> dict:
    """Create an additional admin/staff user inside the current tenant scope."""
    user = User(
        tenant_id=tenant_id,
        user_type=role,
        role=role,
        first_name=name,
        email=email,
        status="active",
        enrolled_by="self",
        password_hash=hash_password(password),
    )
    db.add(user)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise ApiError(409, "EMAIL_EXISTS", "Email already registered in this tenant.")
    return {
        "user_id": str(user.id),
        "email": email,
        "role": role,
    }


def authenticate(db: Session, *, email: str, password: str) -> dict:
    """Verify credentials and return session claims. Cross-tenant lookup by email."""
    with bypass_rls(db):
        user = db.execute(
            select(User).where(User.email == email, User.deleted_at.is_(None))
        ).scalar_one_or_none()

    # Constant-ish failure path: don't reveal whether the email exists.
    if not user or not user.password_hash or not verify_password(password, user.password_hash):
        raise ApiError(401, "INVALID_CREDENTIALS", "Email or password is incorrect.")

    if user.status != "active":
        raise ApiError(403, "ACCOUNT_INACTIVE", f"Account status is {user.status}.")

    return {
        "user_id": str(user.id),
        "tenant_id": str(user.tenant_id),
        "role": user.role,
        "email": user.email,
        "name": f"{user.first_name} {user.last_name or ''}".strip(),
    }
