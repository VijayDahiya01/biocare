"""Person self-service verified identity API (BIOCORE_COMPLETE_CHANGE_SPEC §11.1).

Person-authenticated (person session). A person verifies themselves for a business they've
joined: consent-before-collection → government fetch → live capture + verify → encrypted
entry credential — all scoped to their own membership.
"""
from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.api.deps import PersonPrincipal, get_person, person_db
from app.core.envelope import success
from app.schemas.identity import CompleteVerify, GovOtpRequest, StartVerify
from app.services import person_identity_service

router = APIRouter(prefix="/person/verify", tags=["person-verify"])


@router.post("/{membership_id}/start")
def start(request: Request, membership_id: str, body: StartVerify,
          principal: PersonPrincipal = Depends(get_person), db: Session = Depends(person_db)):
    return success(request, person_identity_service.start_verification(
        db, person_id=principal.person_id, membership_id=membership_id,
        consents=body.consents, request_id=request.state.request_id), status_code=201)


@router.post("/{membership_id}/complete")
def complete(request: Request, membership_id: str, body: CompleteVerify,
             principal: PersonPrincipal = Depends(get_person), db: Session = Depends(person_db)):
    return success(request, person_identity_service.complete_verification(
        db, person_id=principal.person_id, membership_id=membership_id,
        reference=body.reference, image=body.image, request_id=request.state.request_id,
        document=body.document, document_type=body.document_type,
        gov_reference_id=body.gov_reference_id, gov_otp=body.gov_otp))


@router.post("/{membership_id}/gov/otp")
def government_otp(request: Request, membership_id: str, body: GovOtpRequest,
                   principal: PersonPrincipal = Depends(get_person),
                   db: Session = Depends(person_db)):
    """Ask for an Aadhaar code to be sent to the mobile registered against that number."""
    return success(request, person_identity_service.send_government_otp(
        db, person_id=principal.person_id, membership_id=membership_id,
        aadhaar_number=body.aadhaar_number))


@router.get("/{membership_id}/status")
def status(request: Request, membership_id: str,
           principal: PersonPrincipal = Depends(get_person), db: Session = Depends(person_db)):
    return success(request, person_identity_service.verify_status(
        db, person_id=principal.person_id, membership_id=membership_id))
