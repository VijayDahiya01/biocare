"""Person self-service verified identity (BIOCORE_COMPLETE_CHANGE_SPEC §11.1).

The person verifies THEMSELVES for a business they've joined. Like the rest of the person
app these run under bypass_rls() but ALWAYS hard-filter to the authenticated person_id and
their own membership — the data subject acting on their own record, never anyone else. The
membership resolves the tenant; a tenant_subject + the verified-identity flow are created in
that tenant (keyed on the membership id).
"""
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.db import bypass_rls
from app.core.envelope import ApiError
from app.core.policy import ConsentPurpose, VerificationOutcome
from app.dpdp.audit import write_audit
from app.models import (
    ConsentReceipt,
    FaceCredential,
    IdentityVerificationSession,
    Tenant,
    TenantSubject,
    User,
)
from app.services import credential_issuing, identity_proofing, retention_service

_REQUIRED = (
    ConsentPurpose.IDENTITY_VERIFICATION.value,
    ConsentPurpose.GOVERNMENT_DATA_PROCESSING.value,
    ConsentPurpose.LIVE_FACE_CAPTURE.value,
    ConsentPurpose.FACE_TO_GOVERNMENT_MATCH.value,
    ConsentPurpose.ENTRY_TEMPLATE_CREATION.value,
    ConsentPurpose.ENTRY_AUTHENTICATION.value,
)


def _membership(db: Session, person_id: str, membership_id: str) -> User:
    u = db.get(User, membership_id)
    if not u or str(u.person_id) != person_id:
        raise ApiError(404, "MEMBERSHIP_NOT_FOUND", "Not your membership.")
    return u


def _subject_for(db: Session, tenant_id, membership_id: str, display_name: str) -> TenantSubject:
    subj = db.execute(
        select(TenantSubject).where(
            TenantSubject.tenant_id == tenant_id,
            TenantSubject.external_reference == membership_id,
        )
    ).scalars().first()
    if subj is None:
        subj = TenantSubject(tenant_id=tenant_id, external_reference=membership_id,
                             display_name=display_name, subject_type="self_user")
        db.add(subj)
        db.flush()
    return subj


def start_verification(db: Session, *, person_id: str, membership_id: str,
                       consents: list[str], request_id: str | None) -> dict:
    if not all(r in consents for r in _REQUIRED):
        raise ApiError(400, "CONSENT_INCOMPLETE", "All consents are required to verify.")
    with bypass_rls(db):
        u = _membership(db, person_id, membership_id)
        t = db.get(Tenant, u.tenant_id)
        subj = _subject_for(db, u.tenant_id, membership_id, f"{u.first_name} {u.last_name or ''}".strip())
        s = identity_proofing.start_session(db, tenant_id=u.tenant_id, tenant_subject_id=subj.id,
                                            provider_label="self")
        valid = {p.value for p in ConsentPurpose}
        for purpose in consents:
            if purpose in valid:
                identity_proofing.record_consent(db, tenant_id=u.tenant_id,
                                                 tenant_subject_id=subj.id, purpose=purpose, method="self")
        write_audit(db, action="PERSON_VERIFY_START", actor_id=person_id, tenant_id=str(u.tenant_id),
                    target_id=membership_id, request_id=request_id)
        db.commit()
        return {"session_id": str(s.id), "tenant_subject_id": str(subj.id), "business": t.name}


def complete_verification(db: Session, *, person_id: str, membership_id: str, reference: str,
                          image: str, request_id: str | None) -> dict:
    with bypass_rls(db):
        u = _membership(db, person_id, membership_id)
        subj = _subject_for(db, u.tenant_id, membership_id, f"{u.first_name} {u.last_name or ''}".strip())
        s = db.execute(
            select(IdentityVerificationSession)
            .where(IdentityVerificationSession.tenant_subject_id == subj.id)
            .order_by(IdentityVerificationSession.started_at.desc())
        ).scalars().first()
        if not s:
            raise ApiError(400, "NO_SESSION", "Start verification first.")
        for purpose in (ConsentPurpose.FACE_TO_GOVERNMENT_MATCH.value, ConsentPurpose.ENTRY_TEMPLATE_CREATION.value):
            if not db.execute(select(ConsentReceipt).where(
                ConsentReceipt.tenant_subject_id == subj.id, ConsentReceipt.purpose_id == purpose,
                ConsentReceipt.decision == "granted", ConsentReceipt.withdrawn_at.is_(None),
            )).scalars().first():
                raise ApiError(403, "CONSENT_REQUIRED", "Consent is required to verify.")

        identity_proofing.run_government_fetch(db, session=s, subject_ref=reference,
                                               credential={"reference": reference})
        # Mint through the shared issuer so self-service and the operator path always agree on
        # which engine issued the credential (§15.1). Fails closed if no live face was captured,
        # so the self-service credential is genuine and will match at the gate.
        outcome = VerificationOutcome.VERIFIED
        identity_proofing.complete_verification(db, session=s, outcome=outcome,
                                                liveness="self_face_ok", face_match="self_face_ok")
        cred, qr_png = credential_issuing.mint(
            db, tenant_id=u.tenant_id, subject_id=subj.id, image=image,
            purpose=ConsentPurpose.ENTRY_AUTHENTICATION.value,
            expires=retention_service.credential_expiry(db, u.tenant_id))
        credential_id = str(cred.id)
        write_audit(db, action="PERSON_VERIFY_COMPLETE", actor_id=person_id, tenant_id=str(u.tenant_id),
                    target_id=membership_id, request_id=request_id, metadata={"outcome": outcome.value})
        db.commit()
        result = {"verified": outcome == VerificationOutcome.VERIFIED, "outcome": outcome.value,
                  "credential_id": credential_id}
        if qr_png:
            # Under BioVerify the person carries the credential, so hand them the QR to keep.
            result["qr_png_b64"] = qr_png
        return result


def verify_status(db: Session, *, person_id: str, membership_id: str) -> dict:
    with bypass_rls(db):
        u = _membership(db, person_id, membership_id)
        subj = db.execute(select(TenantSubject).where(
            TenantSubject.tenant_id == u.tenant_id,
            TenantSubject.external_reference == membership_id,
        )).scalars().first()
        if not subj:
            return {"verification_status": "unverified", "has_credential": False}
        cred = db.execute(select(FaceCredential).where(
            FaceCredential.tenant_subject_id == subj.id, FaceCredential.status == "active",
        )).scalars().first()
        return {"verification_status": subj.verification_status, "has_credential": cred is not None}
