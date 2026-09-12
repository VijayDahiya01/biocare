"""Self-registration, consent, and face enrollment (API Reference §3).

/register is unauthenticated (the registrant has no account yet). /consent and
/faces/enroll require the member session created at OTP verify.
"""
from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.api.deps import Principal, auth_db, get_principal
from app.core.db import get_db
from app.core.envelope import success
from app.dpdp.audit import write_audit
from app.schemas.enrollment import ConsentRequest, EnrollFaceRequest, RegisterRequest
from app.services.consent_service import record_consent
from app.services.face_service import enroll_face
from app.services.registration_service import register

router = APIRouter(tags=["enrollment"])


@router.post("/register")
def register_user(request: Request, body: RegisterRequest, db: Session = Depends(get_db)):
    """Create a pending account and send an email OTP. No auth required."""
    result = register(
        db, org_code=body.org_code, first_name=body.first_name,
        last_name=body.last_name, email=body.email,
        department=body.department, member_id=body.member_id,
    )
    return success(request, result, status_code=201)


@router.post("/consent")
def post_consent(request: Request, body: ConsentRequest,
                 principal: Principal = Depends(get_principal),
                 db: Session = Depends(auth_db)):
    """Record DPDP consent for the calling member. MUST precede face capture."""
    result = record_consent(
        db, tenant_id=principal.tenant_id, user_id=principal.user_id,
        purpose=body.purpose, method=body.method,
        acknowledgements=body.acknowledgements.model_dump(),
    )
    write_audit(db, action="CONSENT_RECORDED", actor_id=principal.user_id,
                tenant_id=principal.tenant_id, target_id=principal.user_id,
                request_id=request.state.request_id,
                metadata={"consent_ref": result["consent_ref"]})
    db.commit()
    return success(request, result, status_code=201)


@router.post("/faces/enroll")
def enroll(request: Request, body: EnrollFaceRequest,
           principal: Principal = Depends(get_principal),
           db: Session = Depends(auth_db)):
    """Capture a face for the calling member (consent-gated)."""
    target_user = body.user_id or principal.user_id
    result = enroll_face(
        db, tenant_id=principal.tenant_id, user_id=target_user,
        image_b64=body.image, enrolled_by="self",
    )
    write_audit(db, action="FACE_ENROLL", actor_id=principal.user_id,
                tenant_id=principal.tenant_id, target_id=target_user,
                request_id=request.state.request_id,
                metadata={"face_id": result["face_id"]})
    db.commit()
    return success(request, result, status_code=201)
