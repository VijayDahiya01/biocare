"""Authentication endpoints (API Reference §2)."""
from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy.orm import Session

from app.api.deps import Principal, auth_db, get_principal
from app.core.db import get_db, set_tenant_guc
from app.core.envelope import ApiError, success
from app.core.otp import request_otp, verify_otp
from app.core.sessions import (
    clear_session_cookies,
    create_session,
    destroy_session,
    read_csrf,
    set_session_cookies,
)
from app.dpdp.audit import write_audit
from app.schemas.auth import LoginRequest
from app.schemas.enrollment import OtpRequest, OtpVerify
from app.services.auth_service import authenticate
from app.services.registration_service import find_member_by_email, mark_email_verified

router = APIRouter(prefix="/auth", tags=["auth"])


@router.get("/csrf")
def get_csrf(request: Request, principal: Principal = Depends(get_principal)):
    """Return the CSRF token for the current session (echo in X-CSRF-Token)."""
    token = read_csrf(principal.session_id)
    return success(request, {"csrf_token": token})


@router.post("/login")
def login(request: Request, response: Response, body: LoginRequest,
          db: Session = Depends(get_db)):
    """Email + password. Issues a session cookie."""
    claims = authenticate(db, email=body.email, password=body.password)
    session_id, csrf_token, ttl = create_session(
        claims["user_id"], claims["tenant_id"], claims["role"], claims.get("email")
    )
    # bind tenant so the audit insert satisfies RLS WITH CHECK
    set_tenant_guc(db, claims["tenant_id"])
    write_audit(
        db, action="LOGIN_SUCCESS", actor_id=claims["user_id"],
        tenant_id=claims["tenant_id"], request_id=request.state.request_id,
        ip_address=request.client.host if request.client else None,
    )
    db.commit()

    # Cookies MUST be set on the response we actually return (the envelope
    # JSONResponse), not the injected Response — that one is discarded.
    resp = success(request, {
        "user_id": claims["user_id"],
        "role": claims["role"],
        "tenant_id": claims["tenant_id"],
        "name": claims["name"],
    })
    set_session_cookies(resp, session_id, csrf_token, ttl)
    return resp


@router.post("/logout")
def logout(request: Request,
           principal: Principal = Depends(get_principal),
           db: Session = Depends(auth_db)):
    destroy_session(principal.session_id)
    write_audit(db, action="LOGOUT", actor_id=principal.user_id,
                tenant_id=principal.tenant_id, request_id=request.state.request_id)
    db.commit()
    resp = success(request, {"logged_out": True})
    clear_session_cookies(resp)
    return resp


@router.post("/otp/request")
def otp_request(request: Request, body: OtpRequest):
    """Member login / registration step 1 — email an OTP (always 200, no enumeration)."""
    expires_in = request_otp(body.email)
    return success(request, {"expires_in": expires_in})


@router.post("/otp/verify")
def otp_verify(request: Request, body: OtpVerify, db: Session = Depends(get_db)):
    """Member login / registration step 2 — verify OTP, issue a member session.

    Also advances a freshly-registered account from pending_email -> pending_face."""
    if not verify_otp(body.email, body.otp):
        raise ApiError(401, "OTP_INVALID", "The code is incorrect or has expired.")

    member = find_member_by_email(db, body.email)
    if not member:
        raise ApiError(404, "USER_NOT_FOUND", "No account for this email.")

    if member["status"] == "pending_email":
        mark_email_verified(db, member["user_id"])
        member["status"] = "pending_face"

    session_id, csrf_token, ttl = create_session(
        member["user_id"], member["tenant_id"], member["role"], member.get("email") or body.email
    )
    set_tenant_guc(db, member["tenant_id"])
    write_audit(db, action="MEMBER_LOGIN", actor_id=member["user_id"],
                tenant_id=member["tenant_id"], request_id=request.state.request_id)
    db.commit()
    resp = success(request, {"user_id": member["user_id"], "status": member["status"]})
    set_session_cookies(resp, session_id, csrf_token, ttl)
    return resp


@router.get("/me")
def me(request: Request, principal: Principal = Depends(get_principal)):
    return success(request, {
        "user_id": principal.user_id,
        "tenant_id": principal.tenant_id,
        "role": principal.role,
        "email": principal.email,
    })
