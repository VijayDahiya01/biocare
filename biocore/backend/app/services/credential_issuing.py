"""Where an entry credential is minted (BIOCORE_COMPLETE_CHANGE_SPEC §15.1).

ONE place, so every path agrees on which engine issued the credential. Both the operator path
(`/face-credentials`) and the person's self-service path (`/person/verify/*`) come through here.

Before this existed each minted its own way, and only the operator path consulted
`CREDENTIAL_ENGINE` — so flipping that setting changed one path and not the other, and a tenant
could end up holding two kinds of credential without anyone choosing that.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.adapters.bioverify import get_bioverify
from app.adapters.bioverify.base import BioVerifyRefused
from app.adapters.face_engine import FaceEngineError, get_face_engine
from app.core import metrics
from app.core.config import settings
from app.core.envelope import ApiError
from app.core.policy import ConsentPurpose
from app.models import FaceCredential
from app.services import credential_vault


def using_bioverify() -> bool:
    return (settings.credential_engine or "").strip().lower() == "bioverify"


def expiry_or_default(expires: datetime | None) -> datetime:
    """Never hand back an open-ended credential.

    `retention_service.credential_expiry` returns None when the tenant has no retention policy
    yet — which every brand-new tenant is. Falling through on that would mint credentials that
    never expire, quietly contradicting the one thing a purpose-bound credential promises. A
    tenant policy still wins; this is only the floor.
    """
    if expires is not None:
        return expires
    return datetime.now(timezone.utc) + timedelta(days=settings.default_credential_retention_days)


def _ttl_seconds(expires: datetime) -> int:
    """Lifetime in seconds for BioVerify, taken from BioCore policy rather than the service's
    own 30-day default, so the two clocks cannot drift apart."""
    if expires.tzinfo is None:
        expires = expires.replace(tzinfo=timezone.utc)
    ttl = int((expires - datetime.now(timezone.utc)).total_seconds())
    if ttl <= 0:
        raise ApiError(409, "CREDENTIAL_EXPIRY_INVALID",
                       "Retention policy puts this credential's expiry in the past.")
    return ttl


def _active_for(db: Session, *, subject_id, purpose: str) -> list[FaceCredential]:
    return list(db.execute(
        select(FaceCredential).where(
            FaceCredential.tenant_subject_id == subject_id,
            FaceCredential.status == "active",
            FaceCredential.purpose_id == purpose,
        )
    ).scalars().all())


def _retire(db: Session, superseded: list[FaceCredential]) -> None:
    """Revoke the credentials a new one replaces, locally and upstream.

    A person should hold ONE active entry credential. Re-verifying used to stack them, and the
    gate then had several to choose from — a stale one, or one issued by an engine that is no
    longer wired. Revoking upstream too means a superseded QR someone still holds stops working.

    Called only AFTER the replacement exists: retiring first would mean a re-enrolment that the
    quality gate refuses leaves the person with no working credential at all.
    """
    for old in superseded:
        revoke_upstream(old)
        credential_vault.revoke_credential(db, credential=old)
    if superseded:
        db.flush()


def mint(db: Session, *, tenant_id, subject_id, image: str,
         purpose: str = ConsentPurpose.ENTRY_AUTHENTICATION.value,
         expires: datetime | None = None) -> tuple[FaceCredential, str | None]:
    """Create the entry credential; returns (credential, qr_png_b64 or None).

    Under BioVerify the service enrols the face and returns a sealed, scannable credential whose
    TEXT is stored through the same vault an embedding would be — same envelope, same AAD
    binding to tenant/subject/purpose, same key events, same erase-zeroize. Only
    `credential_source` tells them apart, and the matcher branches on it.
    """
    expires_at = expiry_or_default(expires)
    superseded = _active_for(db, subject_id=subject_id, purpose=purpose)

    if not using_bioverify():
        try:
            vector = get_face_engine().embed(image=image)
        except FaceEngineError as e:
            raise ApiError(503, "FACE_ENGINE_UNAVAILABLE", str(e))
        cred = credential_vault.create_credential(
            db, tenant_id=tenant_id, tenant_subject_id=subject_id, vector=vector,
            purpose=purpose, expires_at=expires_at)
        _retire(db, superseded)
        return cred, None

    try:
        result = get_bioverify().enrol(image=image, expires_in_s=_ttl_seconds(expires_at))
    except BioVerifyRefused as e:
        # The service worked and declined THIS capture. That is the person's to fix, so it is a
        # 422 carrying the reason — not a 503, which would tell them the system is broken and
        # send them into a pointless retry loop. Their existing credential is untouched.
        raise ApiError(422, "CAPTURE_REFUSED",
                       "That capture could not be used.", details={"reason": e.reason})
    except FaceEngineError as e:
        # Genuinely unavailable: nothing the person does will help.
        raise ApiError(503, "FACE_ENGINE_UNAVAILABLE", str(e))
    cred = credential_vault.create_credential(
        db, tenant_id=tenant_id, tenant_subject_id=subject_id,
        vector=result.qr_text.encode("utf-8"), purpose=purpose, expires_at=expires_at,
        source="bioverify", external_credential_id=result.credential_id)
    _retire(db, superseded)
    return cred, result.qr_png_b64


def revoke_upstream(credential: FaceCredential) -> None:
    """Revoke at BioVerify as well. BioCore holds no template for these subjects, so a local
    status change alone does not invalidate a credential already in someone's hands.

    A failure is recorded, not raised: the local revoke stands and the gate checks status before
    it ever calls verify, so BioCore is already shut. Watch `bioverify.revoke_failure` — a
    credential live upstream but dead locally is exactly what an erasure certificate should not
    be claiming (§13.4).
    """
    if credential.credential_source != "bioverify" or not credential.external_credential_id:
        return
    try:
        get_bioverify().revoke_credential(credential_id=credential.external_credential_id)
    except FaceEngineError:
        metrics.incr("bioverify.revoke_failure")
