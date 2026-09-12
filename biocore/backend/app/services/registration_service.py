"""Self-registration (API Reference §3.1). The default, admin-free path.

Flow: register -> email OTP verify -> consent -> face enroll. A pending account
cannot check in until face capture completes (status active).
"""
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.db import bypass_rls
from app.core.envelope import ApiError
from app.core.otp import request_otp
from app.models import Tenant, User


def register(db: Session, *, org_code: str, first_name: str, last_name: str | None,
             email: str, department: str | None, member_id: str | None) -> dict:
    """Create a pending account under the tenant identified by org_code, then
    send an email OTP. Unauthenticated — the registrant has no session yet, so
    we resolve the tenant via bypass_rls and write the user with its tenant_id."""
    with bypass_rls(db):
        tenant = db.execute(
            select(Tenant).where(Tenant.org_code == org_code, Tenant.status == "active")
        ).scalar_one_or_none()
        if not tenant:
            raise ApiError(400, "INVALID_ORG_CODE", "Unknown or inactive organisation code.")

        dupe = db.execute(
            select(User).where(User.tenant_id == tenant.id, User.email == email)
        ).scalar_one_or_none()
        if dupe:
            raise ApiError(409, "EMAIL_EXISTS", "This email is already registered.")

        user = User(
            tenant_id=tenant.id,
            user_type="self_user",
            role="self_user",
            first_name=first_name,
            last_name=last_name,
            email=email,
            department=department,
            member_id=member_id,
            status="pending_email",
            enrolled_by="self",
        )
        db.add(user)
        try:
            db.commit()
        except IntegrityError:
            db.rollback()
            raise ApiError(409, "EMAIL_EXISTS", "This email is already registered.")
        user_id = str(user.id)

    request_otp(email)
    return {"user_id": user_id, "status": "pending_email"}


def find_member_by_email(db: Session, email: str) -> dict | None:
    """Cross-tenant lookup used at OTP verify (no session yet)."""
    with bypass_rls(db):
        user = db.execute(
            select(User).where(User.email == email, User.deleted_at.is_(None))
        ).scalar_one_or_none()
        if not user:
            return None
        return {
            "user_id": str(user.id),
            "tenant_id": str(user.tenant_id),
            "role": user.role or "self_user",
            "email": user.email,
            "status": user.status,
        }


def mark_email_verified(db: Session, user_id: str) -> None:
    """pending_email -> pending_face after OTP success."""
    with bypass_rls(db):
        user = db.get(User, user_id)
        if user and user.status == "pending_email":
            user.status = "pending_face"
            db.commit()
