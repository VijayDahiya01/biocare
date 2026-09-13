"""Person self-service verified identity API (BIOCORE_COMPLETE_CHANGE_SPEC §11.1).

Person-authenticated (person session). A person verifies themselves for a business they've
joined: consent-before-collection → government fetch → live capture + verify → encrypted
entry credential — all scoped to their own membership.
"""
from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.api.deps import PersonPrincipal, get_person, person_db
from app.core.envelope import success
from app.schemas.identity import CompleteVerify, StartVerify
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
        document=body.document, document_type=body.document_type))


@router.get("/{membership_id}/status")
def status(request: Request, membership_id: str,
           principal: PersonPrincipal = Depends(get_person), db: Session = Depends(person_db)):
    return success(request, person_identity_service.verify_status(
        db, person_id=principal.person_id, membership_id=membership_id))
