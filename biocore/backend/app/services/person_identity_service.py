"""Person self-service verified identity (BIOCORE_COMPLETE_CHANGE_SPEC §11.1).

The person verifies THEMSELVES for a business they've joined. Like the rest of the person
app these run under bypass_rls() but ALWAYS hard-filter to the authenticated person_id and
their own membership — the data subject acting on their own record, never anyone else. The
membership resolves the tenant; a tenant_subject + the verified-identity flow are created in
that tenant (keyed on the membership id).
"""
import base64

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.adapters.face_engine import FaceEngineError, get_face_engine
from app.adapters.gov_identity import GovernmentIdentityError, get_gov_identity
from app.core.db import bypass_rls
from app.core.envelope import ApiError
from app.core.policy import ConsentPurpose, VerificationOutcome
from app.dpdp.audit import write_audit
from app.models import (
    ConsentReceipt,
    FaceCredential,
    IdentityVerificationSession,
    Person,
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

        # A credential must belong to a named person. Until they have given their details,
        # `first_name` is a placeholder taken from their email address — issuing against that
        # would put "asha_8f8906" on a guard's screen and leave nothing to check a government
        # record against.
        person = db.get(Person, person_id)
        if person is None or person.profile_completed_at is None:
            raise ApiError(409, "PROFILE_INCOMPLETE",
                           "Please fill in your details before verifying.")

        # Re-sync the name: they may have joined this business before completing their profile.
        full_name = f"{person.first_name} {person.last_name or ''}".strip()
        if u.first_name != person.first_name or u.last_name != person.last_name:
            u.first_name, u.last_name = person.first_name, person.last_name
        subj = _subject_for(db, u.tenant_id, membership_id, full_name)
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
        return {"session_id": str(s.id), "tenant_subject_id": str(subj.id), "business": t.name,
                # What this organisation asks for. The app uses it to decide whether to
                # collect an identity document after the selfie.
                "verification_level": t.verification_level or "face_only"}


def send_government_otp(db: Session, *, person_id: str, membership_id: str,
                        aadhaar_number: str) -> dict:
    """Step 1 of an Aadhaar check: ask for a code to be sent to the registered mobile.

    The number is used for this one request and never stored — only the provider's reference
    comes back, which means nothing on its own and dies with the attempt.
    """
    with bypass_rls(db):
        _membership(db, person_id, membership_id)      # must be their own membership
    provider = get_gov_identity()
    send = getattr(provider, "aadhaar_okyc_send_otp", None)
    if send is None:
        raise ApiError(501, "GOVERNMENT_OTP_UNSUPPORTED",
                       "This government provider does not support Aadhaar OTP.")
    try:
        reference_id = send(aadhaar_number=aadhaar_number, reason="identity verification")
    except GovernmentIdentityError as e:
        raise ApiError(400, "AADHAAR_OTP_FAILED", str(e))
    return {"reference_id": reference_id}


def _compare_to_government_photo(gov_photo: bytes, live_image: str) -> tuple[bool, str]:
    """Match the live capture against the photo the government record returned.

    Aadhaar OKYC returns a real face; the dev fake returns a marker, which cannot be matched
    and must not be reported as a pass. Either way the photo is discarded immediately after —
    it is never stored (§5.10).
    """
    if not gov_photo or gov_photo == b"FAKE_GOV_PHOTO":
        return False, "no usable government photo (simulated record)"
    try:
        engine = get_face_engine()
        stored = engine.embed(image=base64.b64encode(gov_photo).decode())
        live = engine.embed(image=live_image)
        result = engine.compare(stored=stored, live=live)
        return result.matched, f"government photo {'matched' if result.matched else 'did not match'}"
    except FaceEngineError as e:
        # Cannot check. Report the failure rather than let an unchecked face read as verified.
        return False, f"could not compare against the government photo: {e}"


def complete_verification(db: Session, *, person_id: str, membership_id: str, reference: str,
                          image: str, request_id: str | None, document: str | None = None,
                          document_type: str = "PASSPORT",
                          gov_reference_id: str | None = None,
                          gov_otp: str | None = None) -> dict:
    with bypass_rls(db):
        u = _membership(db, person_id, membership_id)
        person = db.get(Person, person_id)
        full_name = (f"{person.first_name} {person.last_name or ''}".strip() if person
                     else f"{u.first_name} {u.last_name or ''}".strip())
        subj = _subject_for(db, u.tenant_id, membership_id, full_name)
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

        # What this organisation asks for decides whether a document is required here.
        level = (db.get(Tenant, u.tenant_id).verification_level or "face_only")
        if level == "face_and_document" and not document:
            raise ApiError(400, "DOCUMENT_REQUIRED",
                           "This organisation asks for an identity document as well as a selfie.")
        if document and level == "face_only":
            document = None          # not asked for: do not send it, do not process it

        # The government check compares against what we already hold: the name the person
        # gave us at sign-up, and — for Aadhaar, which returns a photo — their live face.
        gov_claims = identity_proofing.run_government_fetch(
            db, session=s, subject_ref=reference,
            credential=({"type": "aadhaar", "reference": reference,
                         "expected_name": full_name,
                         "reference_id": gov_reference_id, "otp": gov_otp}
                        if gov_reference_id and gov_otp else
                        {"reference": reference, "expected_name": full_name}),
            face_compare=_compare_to_government_photo, live_image=image)

        if level == "face_and_government" and not (gov_reference_id and gov_otp):
            raise ApiError(400, "GOVERNMENT_OTP_REQUIRED",
                           "Enter your Aadhaar number and the code sent to your phone.")

        if level == "face_and_government":
            # Only meaningful at this level: the other levels never contacted a government
            # record, so there is nothing to have matched.
            if not gov_claims.name_verified:
                reason = (gov_claims.extra or {}).get("name_match_reason", "")
                raise ApiError(409, "NAME_MISMATCH",
                               "The name on your government record does not match the name on "
                               "your account. Please check your details and try again.",
                               details={"reason": reason})
            if s.face_match_result == "failed":
                detail = s.liveness_result or ""
                if "simulated" in detail or "could not compare" in detail:
                    # Nothing was actually checked. Blaming the person for a deployment that
                    # is not wired to a real government record would be a lie, and they would
                    # retry forever.
                    raise ApiError(503, "GOVERNMENT_CHECK_UNAVAILABLE",
                                   "Government verification is not available right now. This "
                                   "is not a problem with your photo — please try later or "
                                   "contact the organisation.", details={"reason": detail})
                raise ApiError(409, "GOVERNMENT_FACE_MISMATCH",
                               "Your face does not match the photo on your government record.")
        # Mint through the shared issuer so self-service and the operator path always agree on
        # which engine issued the credential (§15.1). Fails closed if no live face was captured,
        # so the self-service credential is genuine and will match at the gate.
        outcome = VerificationOutcome.VERIFIED
        identity_proofing.complete_verification(db, session=s, outcome=outcome,
                                                liveness="self_face_ok", face_match="self_face_ok")
        cred, qr_png = credential_issuing.mint(
            db, tenant_id=u.tenant_id, subject_id=subj.id, image=image,
            purpose=ConsentPurpose.ENTRY_AUTHENTICATION.value,
            expires=retention_service.credential_expiry(db, u.tenant_id),
            document=document, document_type=document_type)
        credential_id = str(cred.id)
        write_audit(db, action="PERSON_VERIFY_COMPLETE", actor_id=person_id, tenant_id=str(u.tenant_id),
                    target_id=membership_id, request_id=request_id, metadata={"outcome": outcome.value})
        db.commit()
        result = {"verified": outcome == VerificationOutcome.VERIFIED, "outcome": outcome.value,
                  "credential_id": credential_id, "verification_level": level}
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
