"""Visitor temporary enrollment (API Reference §5.5, System doc §6.4).

Reception invites a visitor (QR/link with an expiry); the visitor captures their
face against that token. The enrollment is time-limited and the data auto-expires
(an expiry sweep / erasure removes it after the window).
"""
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.db import bypass_rls
from app.core.envelope import ApiError
from app.core.security import hash_token, new_token
from app.models import ConsentRecord, User, VisitorInvite
from app.services.face_service import enroll_face


def invite(db: Session, *, tenant_id: str, host_user_id: str | None,
           visitor_name: str | None, valid_hours: int) -> dict:
    raw = new_token("vis_")
    expires_at = datetime.now(timezone.utc) + timedelta(hours=valid_hours)
    inv = VisitorInvite(
        tenant_id=tenant_id, token=hash_token(raw), visitor_name=visitor_name,
        host_user_id=host_user_id, expires_at=expires_at,
    )
    db.add(inv)
    db.commit()
    return {
        "invite_id": str(inv.id),
        "token": raw,                       # shown once; embed in QR / link
        "enroll_url": f"/visit/{raw}",
        "expires_at": expires_at.isoformat(),
    }


def enroll(db: Session, *, token: str, name: str, phone: str | None, image: str) -> dict:
    """Unauthenticated — the visitor presents the invite token. Resolve the
    tenant via the token (bypass), then create + enroll within it."""
    token_hash = hash_token(token)
    with bypass_rls(db):
        inv = db.execute(
            select(VisitorInvite).where(VisitorInvite.token == token_hash)
        ).scalar_one_or_none()
        if not inv:
            raise ApiError(404, "INVITE_INVALID", "Unknown visitor invite.")
        if inv.used:
            raise ApiError(409, "INVITE_USED", "This invite has already been used.")
        if inv.expires_at <= datetime.now(timezone.utc):
            raise ApiError(403, "INVITE_EXPIRED", "This invite has expired.")

        tenant_id = str(inv.tenant_id)
        visitor = User(
            tenant_id=tenant_id, user_type="visitor", role="visitor",
            first_name=name, status="active", enrolled_by="visitor_self",
            expiry_date=inv.expires_at.date(), extra={"phone": phone} if phone else {},
        )
        db.add(visitor)
        db.flush()
        user_id = str(visitor.id)

        db.add(ConsentRecord(
            tenant_id=tenant_id, user_id=user_id, purpose="visitor_access",
            method="self",
            acknowledgements={"purpose_understood": True, "sensitivity_understood": True,
                              "rights_understood": True, "freely_given": True},
            active=True, consent_ref=f"CNS-VIS-{user_id[:8]}",
        ))
        inv.used = True
        inv.user_id = visitor.id
        db.commit()

    # enroll_face runs under the tenant scope set after bypass closes.
    from app.core.db import set_tenant_guc
    set_tenant_guc(db, tenant_id)
    enroll_face(db, tenant_id=tenant_id, user_id=user_id, image_b64=image,
                enrolled_by="visitor_self")
    return {"user_id": user_id, "expires_at": inv.expires_at.isoformat()}
