"""DPDP consent (API Reference §3.2). MUST be recorded before any face capture.

The four acknowledgements are all mandatory; a non-biometric alternative is always
offered in the UI (consent can never be forced).
"""
import secrets
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.envelope import ApiError
from app.models import ConsentRecord

REQUIRED_ACKS = ("purpose_understood", "sensitivity_understood",
                 "rights_understood", "freely_given")


def _consent_ref() -> str:
    year = datetime.now(timezone.utc).year
    return f"CNS-{year}-{secrets.randbelow(100000):05d}"


def record_consent(db: Session, *, tenant_id: str, user_id: str, purpose: str,
                   method: str, acknowledgements: dict) -> dict:
    missing = [k for k in REQUIRED_ACKS if not acknowledgements.get(k)]
    if missing:
        raise ApiError(400, "CONSENT_INCOMPLETE",
                       "All four consent acknowledgements are required.",
                       details={"missing": missing})

    ref = _consent_ref()
    record = ConsentRecord(
        tenant_id=tenant_id,
        user_id=user_id,
        purpose=purpose,
        method=method,
        acknowledgements={k: bool(acknowledgements.get(k)) for k in REQUIRED_ACKS},
        active=True,
        consent_ref=ref,
    )
    db.add(record)
    db.commit()
    return {"consent_ref": ref}


def has_active_consent(db: Session, *, user_id: str) -> bool:
    """The gate enforced before /faces/enroll. RLS already scopes to the tenant."""
    row = db.execute(
        select(ConsentRecord.id).where(
            ConsentRecord.user_id == user_id,
            ConsentRecord.active.is_(True),
            ConsentRecord.revoked_at.is_(None),
        ).limit(1)
    ).first()
    return row is not None
