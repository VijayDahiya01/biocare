"""Identity Proofing Service (BIOCORE_COMPLETE_CHANGE_SPEC §4.2, §5).

Orchestrates: consent → government fetch → (live capture + 1:1 face-to-government match) →
minimal verified claims → DELETE temporary government/face material → fresh entry template.

Government photo, raw response and comparison embeddings are TEMPORARY: they live only in
local variables during the transaction and are never written to the DB, logs, Redis, queues
or files (§5.7, §5.10, §14.1). This service records only session metadata + minimal claims.
The 1:1 face-to-government comparison is provided by the real face engine via `face_compare`
(left unwired in dev — the fake engine must never be used for real verification, §29.18).
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Callable

from sqlalchemy.orm import Session

from app.adapters.gov_identity import get_gov_identity
from app.core import metrics
from app.core.policy import ConsentPurpose, VerificationOutcome
from app.models import ConsentReceipt, IdentityVerificationSession, TenantSubject, VerifiedClaim


def start_session(db: Session, *, tenant_id, tenant_subject_id,
                  provider_label: str = "") -> IdentityVerificationSession:
    s = IdentityVerificationSession(
        tenant_id=tenant_id, tenant_subject_id=tenant_subject_id,
        government_provider=provider_label or None, status="started",
    )
    db.add(s)
    db.flush()
    return s


def record_consent(db: Session, *, tenant_id, tenant_subject_id, purpose: str,
                   decision: str = "granted", method: str = "app", notice_id=None) -> ConsentReceipt:
    """Consent must be recorded BEFORE the corresponding collection/processing (§5.3, §13.1)."""
    r = ConsentReceipt(
        tenant_id=tenant_id, tenant_subject_id=tenant_subject_id, notice_id=notice_id,
        purpose_id=purpose, decision=decision, method=method,
    )
    db.add(r)
    db.flush()
    return r


def run_government_fetch(db: Session, *, session: IdentityVerificationSession,
                         subject_ref: str, credential: dict,
                         face_compare: Callable[..., tuple[bool, str]] | None = None,
                         live_vector: bytes | None = None,
                         live_image: str | None = None):
    """Call the government adapter, retain ONLY minimal claims, delete temporary material.

    Consent for `identity_verification` + `government_data_processing` must already be on
    record (caller enforces, §5.3). Returns the minimal `VerifiedClaims`.
    """
    provider = get_gov_identity()
    gov_session = provider.create_session(
        tenant_id=str(session.tenant_id), subject_ref=subject_ref, purpose="identity_verification",
    )
    try:
        with metrics.timer("gov_api.latency_ms"):
            result = provider.fetch_verified_data(session=gov_session, credential=credential)
        metrics.incr("gov_api.success")
    except Exception:
        metrics.incr("gov_api.failure")  # feeds §23 "government API success rate"
        raise

    # --- temporary material (used, NEVER stored/logged): government photo + embeddings ---
    gov_photo = result.government_photo
    claims = result.claims
    live = live_image if live_image is not None else live_vector
    if face_compare is not None and live is not None and gov_photo is not None:
        matched, detail = face_compare(gov_photo, live)
        session.face_match_result = "passed" if matched else "failed"
        session.liveness_result = detail

    session.government_provider = gov_session.provider
    session.provider_reference_hash = claims.verification_reference_hash
    session.assurance_level = claims.assurance_level

    # --- persist ONLY minimal verified claims (§5.5) ---
    for ctype, cval in [
        ("identity_verified", str(claims.identity_verified).lower()),
        ("name_verified", str(claims.name_verified).lower()),
        ("document_valid", str(claims.document_valid).lower()),
        ("age_over_18", str(claims.age_over_18).lower()),
    ]:
        db.add(VerifiedClaim(
            tenant_id=session.tenant_id, tenant_subject_id=session.tenant_subject_id,
            claim_type=ctype, claim_value=cval, source=gov_session.provider,
        ))

    provider.revoke_or_close_session(session=gov_session)
    # --- delete temporary government/face material (§5.10): drop refs; nothing was persisted ---
    gov_photo = None  # noqa: F841
    del result
    return claims


def complete_verification(db: Session, *, session: IdentityVerificationSession,
                          outcome: VerificationOutcome, liveness: str = "",
                          face_match: str = "") -> None:
    session.status = outcome.value
    if liveness:
        session.liveness_result = liveness
    if face_match:
        session.face_match_result = face_match
    session.completed_at = datetime.now(timezone.utc)
    if outcome == VerificationOutcome.VERIFIED:
        subj = db.get(TenantSubject, session.tenant_subject_id)
        if subj:
            subj.verification_status = "verified"
            subj.status = "verified"
    else:
        session.failure_category = outcome.value


# consent that must exist before capture/processing (re-exported for callers, §5.3)
REQUIRED_BEFORE_CAPTURE = (
    ConsentPurpose.IDENTITY_VERIFICATION.value,
    ConsentPurpose.GOVERNMENT_DATA_PROCESSING.value,
    ConsentPurpose.LIVE_FACE_CAPTURE.value,
    ConsentPurpose.FACE_TO_GOVERNMENT_MATCH.value,
    ConsentPurpose.ENTRY_TEMPLATE_CREATION.value,
)
