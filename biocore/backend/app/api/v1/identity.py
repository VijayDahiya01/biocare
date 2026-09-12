"""Identity proofing API (BIOCORE_COMPLETE_CHANGE_SPEC §10.1, §5).

Consent-before-collection → government fetch (provider-agnostic) → 1:1 verification →
minimal verified claims. No endpoint returns raw government data, photos or templates
(§10.6, §14.1). Tenant isolation comes from the session (RLS), never the request body.
"""
from fastapi import APIRouter, Depends, Request
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.adapters.face_engine import FaceEngineError, get_face_engine
from app.api.deps import Principal, auth_db, require_role
from app.core.config import settings
from app.core.envelope import ApiError, success
from app.core.policy import ConsentPurpose, VerificationOutcome
from app.core.roles import ENROLL, READ_STATUS
from app.dpdp.audit import write_audit
from app.models import ConsentReceipt, EntryAttempt, FaceCredential, IdentityVerificationSession, TenantSubject
from app.schemas.identity import ConsentGrant, GovFetch, SessionCreate, VerifyRequest
from app.services import identity_proofing

router = APIRouter(prefix="/identity", tags=["identity"])
_ENROLL = ENROLL


def _session(db: Session, session_id: str) -> IdentityVerificationSession:
    s = db.get(IdentityVerificationSession, session_id)
    if not s:
        raise ApiError(404, "SESSION_NOT_FOUND", "Verification session not found.")
    return s


def _has_consent(db: Session, subject_id, purpose: str) -> bool:
    return db.execute(
        select(ConsentReceipt).where(
            ConsentReceipt.tenant_subject_id == subject_id,
            ConsentReceipt.purpose_id == purpose,
            ConsentReceipt.decision == "granted",
            ConsentReceipt.withdrawn_at.is_(None),
        )
    ).scalars().first() is not None


@router.post("/sessions")
def create_session(request: Request, body: SessionCreate,
                   principal: Principal = Depends(require_role(*_ENROLL)),
                   db: Session = Depends(auth_db)):
    """Create (or resolve) a tenant subject and start a verification session (§5.1)."""
    subj = None
    if body.external_reference:
        subj = db.execute(select(TenantSubject).where(
            TenantSubject.external_reference == body.external_reference)).scalars().first()
    if subj is None:
        subj = TenantSubject(tenant_id=principal.tenant_id, external_reference=body.external_reference,
                             display_name=body.display_name, subject_type=body.subject_type)
        db.add(subj)
        db.flush()
    s = identity_proofing.start_session(db, tenant_id=principal.tenant_id,
                                        tenant_subject_id=subj.id, provider_label=body.provider_label)
    write_audit(db, action="IDENTITY_SESSION_STARTED", actor_id=principal.user_id,
                tenant_id=principal.tenant_id, target_id=str(subj.id),
                request_id=request.state.request_id)
    db.commit()
    return success(request, {"session_id": str(s.id), "tenant_subject_id": str(subj.id),
                             "status": s.status}, status_code=201)


@router.get("/sessions/{session_id}")
def get_session(request: Request, session_id: str,
                principal: Principal = Depends(require_role(*_ENROLL)),
                db: Session = Depends(auth_db)):
    s = _session(db, session_id)
    return success(request, {
        "session_id": str(s.id), "tenant_subject_id": str(s.tenant_subject_id), "status": s.status,
        "assurance_level": s.assurance_level, "liveness_result": s.liveness_result,
        "face_match_result": s.face_match_result, "failure_category": s.failure_category,
        "completed_at": s.completed_at.isoformat() if s.completed_at else None,
    })


@router.post("/sessions/{session_id}/consent")
def grant_consent(request: Request, session_id: str, body: ConsentGrant,
                  principal: Principal = Depends(require_role(*_ENROLL)),
                  db: Session = Depends(auth_db)):
    """Record purpose-bound consent BEFORE any collection (§5.3, §13.1)."""
    s = _session(db, session_id)
    valid = {p.value for p in ConsentPurpose}
    recorded: list[str] = []
    for purpose in body.purposes:
        if purpose not in valid:
            raise ApiError(400, "INVALID_PURPOSE", f"Unknown consent purpose: {purpose}")
        identity_proofing.record_consent(db, tenant_id=principal.tenant_id,
                                          tenant_subject_id=s.tenant_subject_id, purpose=purpose,
                                          method=body.method, notice_id=body.notice_id)
        recorded.append(purpose)
    write_audit(db, action="CONSENT_RECORDED", actor_id=principal.user_id,
                tenant_id=principal.tenant_id, target_id=str(s.tenant_subject_id),
                request_id=request.state.request_id, metadata={"purposes": recorded})
    db.commit()
    return success(request, {"recorded": recorded}, status_code=201)


@router.post("/sessions/{session_id}/government-fetch")
def government_fetch(request: Request, session_id: str, body: GovFetch,
                     principal: Principal = Depends(require_role(*_ENROLL)),
                     db: Session = Depends(auth_db)):
    """Fetch verified data via the provider adapter; keep only minimal claims (§5.4–§5.5)."""
    s = _session(db, session_id)
    for purpose in (ConsentPurpose.IDENTITY_VERIFICATION.value,
                    ConsentPurpose.GOVERNMENT_DATA_PROCESSING.value):
        if not _has_consent(db, s.tenant_subject_id, purpose):
            raise ApiError(403, "CONSENT_REQUIRED", f"Consent '{purpose}' required before government fetch.")
    claims = identity_proofing.run_government_fetch(
        db, session=s, subject_ref=str(body.credential.get("reference", "")), credential=body.credential)
    write_audit(db, action="GOV_IDENTITY_FETCHED", actor_id=principal.user_id,
                tenant_id=principal.tenant_id, target_id=str(s.tenant_subject_id),
                request_id=request.state.request_id, metadata={"assurance_level": claims.assurance_level})
    db.commit()
    return success(request, {"assurance_level": claims.assurance_level, "claims_recorded": True})


@router.post("/sessions/{session_id}/verify")
def verify(request: Request, session_id: str, body: VerifyRequest,
           principal: Principal = Depends(require_role(*_ENROLL)),
           db: Session = Depends(auth_db)):
    """Decide the live-face check (§5.8). Runs a REAL liveness / face-presence check on the
    captured live face via the face engine — a blank/no-face capture does NOT verify. The full
    1:1 face-to-GOVERNMENT match additionally needs a government photo (e.g. Aadhaar OKYC); with
    PAN / simulated KYC there is no gov photo, so verification is gated on a real live face."""
    s = _session(db, session_id)
    if not _has_consent(db, s.tenant_subject_id, ConsentPurpose.FACE_TO_GOVERNMENT_MATCH.value):
        raise ApiError(403, "CONSENT_REQUIRED", "Consent 'face_to_government_match' required.")
    live = body.live_image or ""
    live_ok, detail = False, "no_image"
    if live:
        try:
            lv = get_face_engine().assess_liveness(image=live)
            live_ok, detail = lv.passed, lv.detail
        except FaceEngineError as e:
            detail = f"engine_unavailable: {e}"
    if live_ok:
        outcome = VerificationOutcome.VERIFIED
        identity_proofing.complete_verification(db, session=s, outcome=outcome,
                                                liveness=detail, face_match="live_face_ok")
    else:
        outcome = VerificationOutcome.MANUAL_REVIEW_REQUIRED
        identity_proofing.complete_verification(db, session=s, outcome=outcome, liveness=detail)
    write_audit(db, action="IDENTITY_VERIFY", actor_id=principal.user_id,
                tenant_id=principal.tenant_id, target_id=str(s.tenant_subject_id),
                request_id=request.state.request_id,
                metadata={"outcome": outcome.value, "liveness": detail})
    db.commit()
    return success(request, {"status": s.status, "outcome": outcome.value, "liveness": detail})


@router.post("/sessions/{session_id}/complete")
def complete(request: Request, session_id: str,
             principal: Principal = Depends(require_role(*_ENROLL)),
             db: Session = Depends(auth_db)):
    s = _session(db, session_id)
    subj = db.get(TenantSubject, s.tenant_subject_id)
    return success(request, {"session_id": str(s.id), "status": s.status,
                             "verification_status": subj.verification_status if subj else None})


@router.post("/sessions/{session_id}/cancel")
def cancel(request: Request, session_id: str,
           principal: Principal = Depends(require_role(*_ENROLL)),
           db: Session = Depends(auth_db)):
    s = _session(db, session_id)
    s.status = "cancelled"
    write_audit(db, action="IDENTITY_SESSION_CANCELLED", actor_id=principal.user_id,
                tenant_id=principal.tenant_id, target_id=str(s.tenant_subject_id),
                request_id=request.state.request_id)
    db.commit()
    return success(request, {"status": "cancelled"})


# --- admin read views (§10.6): status only, never biometric payload ---

@router.get("/subjects")
def list_subjects(request: Request, principal: Principal = Depends(require_role(*READ_STATUS)),
                  db: Session = Depends(auth_db)):
    rows = db.execute(select(TenantSubject).order_by(TenantSubject.created_at.desc()).limit(200)).scalars().all()
    items = [{
        "id": str(s.id), "external_reference": s.external_reference, "display_name": s.display_name,
        "subject_type": s.subject_type, "status": s.status, "verification_status": s.verification_status,
        "authorization_status": s.authorization_status,
        "created_at": s.created_at.isoformat() if s.created_at else None,
    } for s in rows]
    return success(request, {"items": items})


@router.get("/analytics")
def analytics(request: Request, principal: Principal = Depends(require_role(*READ_STATUS)),
              db: Session = Depends(auth_db)):
    def count(model, *where):
        q = select(func.count()).select_from(model)
        for w in where:
            q = q.where(w)
        return db.execute(q).scalar_one()
    return success(request, {
        "subjects": count(TenantSubject),
        "verified": count(TenantSubject, TenantSubject.verification_status == "verified"),
        "active_credentials": count(FaceCredential, FaceCredential.status == "active"),
        "sessions": count(IdentityVerificationSession),
        "entry_allow": count(EntryAttempt, EntryAttempt.authorization_result == "allow"),
        "entry_deny": count(EntryAttempt, EntryAttempt.authorization_result == "deny"),
    })
