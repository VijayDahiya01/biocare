"""Person-centric app API — one login spanning businesses (see docs/PERSON_APP.md).

Person sessions are cross-tenant; all reads are hard-filtered to the caller's
person_id in person_service and audited.
"""
from collections import defaultdict

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.api.deps import PersonPrincipal, get_person, person_db
from app.core.config import settings
from app.core.db import bypass_rls, get_db
from app.core.envelope import ApiError, success
from app.core.otp import request_otp, verify_otp
from app.core.sessions import (
    clear_session_cookies,
    create_person_session,
    destroy_session,
    set_session_cookies,
)
from app.dpdp.audit import write_audit
from app.schemas.person import (
    JoinByCode,
    PersonFaceEnroll,
    PersonOtpRequest,
    PersonOtpVerify,
    ProfileUpdate,
)
from app.services import person_service

router = APIRouter(prefix="/person", tags=["person-app"])


@router.post("/auth/otp/request")
def otp_request(request: Request, body: PersonOtpRequest):
    return success(request, {"expires_in": request_otp(body.email)})


@router.post("/auth/otp/verify")
def otp_verify(request: Request, body: PersonOtpVerify, db: Session = Depends(get_db)):
    if not verify_otp(body.email, body.otp):
        raise ApiError(401, "OTP_INVALID", "The code is incorrect or has expired.")
    person_id = person_service.resolve_or_create_person(db, email=body.email)
    sid, csrf, ttl = create_person_session(person_id, body.email)
    write_audit(db, action="PERSON_LOGIN", actor_id=person_id, request_id=request.state.request_id)
    # audit writes under no tenant; commit via a bypass scope
    with bypass_rls(db):
        db.commit()
    resp = success(request, {"person_id": person_id})
    set_session_cookies(resp, sid, csrf, ttl)
    return resp


@router.post("/auth/dev-login")
def dev_login(request: Request, body: PersonOtpRequest, db: Session = Depends(get_db)):
    """DEV ONLY (DEV_LOGIN=true): session as any email, no OTP. 404 otherwise.

    Absent in production whatever the flag says — a misconfigured DEV_LOGIN would otherwise be
    a complete authentication bypass."""
    if settings.is_production or not settings.dev_login:
        raise ApiError(404, "NOT_FOUND", "Not available.")
    person_id = person_service.resolve_or_create_person(db, email=body.email)
    sid, csrf, ttl = create_person_session(person_id, body.email)
    write_audit(db, action="PERSON_DEV_LOGIN", actor_id=person_id, request_id=request.state.request_id)
    with bypass_rls(db):
        db.commit()
    resp = success(request, {"person_id": person_id, "dev": True})
    set_session_cookies(resp, sid, csrf, ttl)
    return resp


@router.post("/auth/logout")
def logout(request: Request, principal: PersonPrincipal = Depends(get_person)):
    destroy_session(principal.session_id)
    resp = success(request, {"logged_out": True})
    clear_session_cookies(resp)
    return resp


@router.get("/me")
def me(request: Request, principal: PersonPrincipal = Depends(get_person),
       db: Session = Depends(person_db)):
    return success(request, person_service.profile(db, principal.person_id))


@router.patch("/me")
def update_me(request: Request, body: ProfileUpdate,
              principal: PersonPrincipal = Depends(get_person),
              db: Session = Depends(person_db)):
    """The person fills in their own details. Nobody else can edit them."""
    return success(request, person_service.update_profile(
        db, person_id=principal.person_id, first_name=body.first_name,
        last_name=body.last_name, gender=body.gender,
        date_of_birth=body.date_of_birth, phone=body.phone))


@router.get("/businesses")
def businesses(request: Request, principal: PersonPrincipal = Depends(get_person),
               db: Session = Depends(person_db)):
    items = person_service.list_businesses(db, principal.person_id)
    by_sector: dict[str, list] = defaultdict(list)
    for it in items:
        by_sector[it["sector"]].append(it)
    return success(request, {"by_sector": by_sector, "total": len(items)})


@router.post("/businesses/join")
def join(request: Request, body: JoinByCode, principal: PersonPrincipal = Depends(get_person),
         db: Session = Depends(person_db)):
    result = person_service.join_by_code(db, person_id=principal.person_id,
                                         org_code=body.org_code, request_id=request.state.request_id)
    return success(request, result, status_code=201)


@router.post("/face/enroll")
def enroll_master(request: Request, body: PersonFaceEnroll,
                  principal: PersonPrincipal = Depends(get_person),
                  db: Session = Depends(person_db)):
    """Capture the master face ONCE (consent-gated, quality-checked)."""
    result = person_service.enroll_master(db, person_id=principal.person_id, image_b64=body.image,
                                          acks=body.acknowledgements.model_dump(),
                                          request_id=request.state.request_id)
    return success(request, result, status_code=201)


@router.post("/businesses/{membership_id}/consent")
def allow_business(request: Request, membership_id: str,
                   principal: PersonPrincipal = Depends(get_person),
                   db: Session = Depends(person_db)):
    """One tap: allow this business to use your verified face (re-provisions, no re-scan)."""
    result = person_service.consent_for_business(db, person_id=principal.person_id,
                                                 membership_id=membership_id,
                                                 request_id=request.state.request_id)
    return success(request, result, status_code=201)


@router.post("/businesses/{membership_id}/consent/revoke")
def revoke_business(request: Request, membership_id: str,
                    principal: PersonPrincipal = Depends(get_person),
                    db: Session = Depends(person_db)):
    result = person_service.revoke_business(db, person_id=principal.person_id,
                                            membership_id=membership_id,
                                            request_id=request.state.request_id)
    return success(request, result)


@router.post("/me/erasure")
def erase_me(request: Request, principal: PersonPrincipal = Depends(get_person),
             db: Session = Depends(person_db)):
    """Global DPDP erasure across every business + the master template."""
    result = person_service.erase_person(db, person_id=principal.person_id,
                                         request_id=request.state.request_id)
    return success(request, result)


@router.get("/businesses/{membership_id}")
def business_detail(request: Request, membership_id: str,
                    principal: PersonPrincipal = Depends(get_person),
                    db: Session = Depends(person_db)):
    """Inside one business: role, badges, verification, my check-in/out history."""
    return success(request, person_service.membership_detail(
        db, person_id=principal.person_id, membership_id=membership_id))


@router.get("/businesses/{membership_id}/events")
def business_events(request: Request, membership_id: str,
                    principal: PersonPrincipal = Depends(get_person),
                    db: Session = Depends(person_db)):
    return success(request, {"items": person_service.list_business_events(
        db, person_id=principal.person_id, membership_id=membership_id)})


@router.post("/events/{event_id}/register")
def register_event(request: Request, event_id: str,
                   principal: PersonPrincipal = Depends(get_person),
                   db: Session = Depends(person_db)):
    """Register for an event + per-event consent (reuses your verified face)."""
    return success(request, person_service.register_event(
        db, person_id=principal.person_id, event_id=event_id,
        request_id=request.state.request_id), status_code=201)


@router.post("/events/{event_id}/consent/revoke")
def revoke_event(request: Request, event_id: str,
                 principal: PersonPrincipal = Depends(get_person),
                 db: Session = Depends(person_db)):
    return success(request, person_service.revoke_event(
        db, person_id=principal.person_id, event_id=event_id,
        request_id=request.state.request_id))


@router.get("/invites")
def invites(request: Request, principal: PersonPrincipal = Depends(get_person),
            db: Session = Depends(person_db)):
    return success(request, {"items": person_service.list_invites(db, email=principal.email)})


@router.post("/invites/{invite_id}/accept")
def accept_invite(request: Request, invite_id: str,
                  principal: PersonPrincipal = Depends(get_person),
                  db: Session = Depends(person_db)):
    result = person_service.accept_invite(db, person_id=principal.person_id, email=principal.email,
                                          invite_id=invite_id, request_id=request.state.request_id)
    return success(request, result, status_code=201)
