"""Face credential API (BIOCORE_COMPLETE_CHANGE_SPEC §10.2).

Creates/manages tenant-specific ENCRYPTED entry templates from a fresh live capture
(§5.11). No endpoint ever returns a raw or encrypted template, DEK or key (§10.2, §29.13).
"""
from datetime import datetime

from fastapi import APIRouter, Depends, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import Principal, auth_db, require_role
from app.core.envelope import ApiError, success
from app.core.policy import ConsentPurpose
from app.core.roles import ENROLL, READ_STATUS
from app.dpdp.audit import write_audit
from app.models import ConsentReceipt, FaceCredential, TenantSubject
from app.schemas.identity import CredentialCreate, ReEnroll
from app.services import credential_issuing, credential_vault, retention_service

router = APIRouter(prefix="/face-credentials", tags=["face-credentials"])
_ENROLL = ENROLL


_mint = credential_issuing.mint
_revoke_upstream = credential_issuing.revoke_upstream


def _credential(db: Session, cid: str) -> FaceCredential:
    c = db.get(FaceCredential, cid)
    if not c:
        raise ApiError(404, "CREDENTIAL_NOT_FOUND", "Face credential not found.")
    return c


def _has_consent(db: Session, subject_id, purpose: str) -> bool:
    return db.execute(
        select(ConsentReceipt).where(
            ConsentReceipt.tenant_subject_id == subject_id,
            ConsentReceipt.purpose_id == purpose,
            ConsentReceipt.decision == "granted",
            ConsentReceipt.withdrawn_at.is_(None),
        )
    ).scalars().first() is not None


@router.post("")
def create(request: Request, body: CredentialCreate,
           principal: Principal = Depends(require_role(*_ENROLL)),
           db: Session = Depends(auth_db)):
    subj = db.get(TenantSubject, body.tenant_subject_id)
    if not subj:
        raise ApiError(404, "SUBJECT_NOT_FOUND", "Tenant subject not found.")
    if subj.verification_status != "verified":
        raise ApiError(409, "NOT_VERIFIED", "Subject must be identity-verified before an entry credential.")
    if not _has_consent(db, subj.id, ConsentPurpose.ENTRY_TEMPLATE_CREATION.value):
        raise ApiError(403, "CONSENT_REQUIRED", "Consent 'entry_template_creation' required.")
    expires = (datetime.fromisoformat(body.expires_at) if body.expires_at
               else retention_service.credential_expiry(db, principal.tenant_id))
    purpose = body.purpose or ConsentPurpose.ENTRY_AUTHENTICATION.value
    cred, qr_png = _mint(db, tenant_id=principal.tenant_id, subject_id=subj.id,
                         image=body.image, purpose=purpose, expires=expires)
    write_audit(db, action="FACE_CREDENTIAL_CREATED", actor_id=principal.user_id,
                tenant_id=principal.tenant_id, target_id=str(cred.id),
                request_id=request.state.request_id)
    db.commit()
    payload = {"credential_id": str(cred.id), "status": cred.status,
               "purpose": cred.purpose_id,
               "expires_at": cred.expires_at.isoformat() if cred.expires_at else None}
    if qr_png:
        # The scannable credential, for the operator to hand to the subject. This is NOT the
        # template §10.2 forbids returning, and it is not a bearer token either: presenting it
        # without the matching live face verifies nothing.
        payload["qr_png_b64"] = qr_png
    return success(request, payload, status_code=201)


@router.get("/{cid}/status")
def status(request: Request, cid: str, principal: Principal = Depends(require_role(*READ_STATUS)),
           db: Session = Depends(auth_db)):
    c = _credential(db, cid)
    return success(request, {
        "credential_id": str(c.id), "tenant_subject_id": str(c.tenant_subject_id),
        "purpose": c.purpose_id, "status": c.status, "model_version": c.model_version,
        "template_version": c.template_version, "key_version": c.key_version,
        "created_at": c.created_at.isoformat() if c.created_at else None,
        "expires_at": c.expires_at.isoformat() if c.expires_at else None,
        "revoked_at": c.revoked_at.isoformat() if c.revoked_at else None,
        "erased_at": c.erased_at.isoformat() if c.erased_at else None,
    })


@router.post("/{cid}/re-enroll")
def re_enroll(request: Request, cid: str, body: ReEnroll,
              principal: Principal = Depends(require_role(*_ENROLL)),
              db: Session = Depends(auth_db)):
    old = _credential(db, cid)
    credential_vault.revoke_credential(db, credential=old)
    _revoke_upstream(old)
    new, qr_png = _mint(db, tenant_id=principal.tenant_id, subject_id=old.tenant_subject_id,
                        image=body.image, purpose=old.purpose_id, expires=old.expires_at)
    write_audit(db, action="FACE_CREDENTIAL_REENROLLED", actor_id=principal.user_id,
                tenant_id=principal.tenant_id, target_id=str(new.id),
                request_id=request.state.request_id, metadata={"replaced": str(old.id)})
    db.commit()
    payload = {"credential_id": str(new.id), "status": new.status, "replaced": str(old.id)}
    if qr_png:
        payload["qr_png_b64"] = qr_png
    return success(request, payload, status_code=201)


@router.post("/{cid}/revoke")
def revoke(request: Request, cid: str, principal: Principal = Depends(require_role(*_ENROLL)),
           db: Session = Depends(auth_db)):
    c = _credential(db, cid)
    credential_vault.revoke_credential(db, credential=c)
    _revoke_upstream(c)
    write_audit(db, action="FACE_CREDENTIAL_REVOKED", actor_id=principal.user_id,
                tenant_id=principal.tenant_id, target_id=str(c.id), request_id=request.state.request_id)
    db.commit()
    return success(request, {"credential_id": str(c.id), "status": "revoked"})


@router.delete("/{cid}")
def erase(request: Request, cid: str, principal: Principal = Depends(require_role(*_ENROLL)),
          db: Session = Depends(auth_db)):
    c = _credential(db, cid)
    _revoke_upstream(c)          # kill it upstream BEFORE the local id is zeroized (§13.4)
    credential_vault.erase_credential(db, credential=c)
    write_audit(db, action="FACE_CREDENTIAL_ERASED", actor_id=principal.user_id,
                tenant_id=principal.tenant_id, target_id=str(c.id), request_id=request.state.request_id)
    db.commit()
    return success(request, {"credential_id": str(c.id), "status": "erased"})
