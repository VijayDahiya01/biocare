"""Request dependencies: current session, CSRF enforcement, tenant-scoped DB."""
from collections.abc import Iterator
from dataclasses import dataclass

from fastapi import Depends, Request
from sqlalchemy.orm import Session

from app.core.db import SessionLocal, bypass_rls, set_tenant_guc
from app.core.envelope import ApiError
from app.core.security import constant_time_eq
from app.core.sessions import SESSION_COOKIE, read_csrf, read_session

MUTATING = {"POST", "PUT", "PATCH", "DELETE"}


@dataclass
class Principal:
    session_id: str
    user_id: str
    tenant_id: str | None
    role: str
    email: str | None = None


def get_principal(request: Request) -> Principal:
    """Resolve the caller from the session cookie. 401 if absent/invalid."""
    session_id = request.cookies.get(SESSION_COOKIE)
    if not session_id:
        raise ApiError(401, "UNAUTHENTICATED", "No valid session.")
    data = read_session(session_id)
    if not data or "user_id" not in data or "role" not in data:
        # The same cookie name carries admin/staff sessions (user_id + role) and
        # person/member sessions (kind="person", person_id only, no user_id/role) — one
        # browser can hold either at a time. A person session presented here is not an
        # error in the data, just the wrong kind of session for an admin-only endpoint.
        raise ApiError(401, "UNAUTHENTICATED", "Session expired or invalid.")
    return Principal(
        session_id=session_id,
        user_id=data["user_id"],
        tenant_id=data.get("tenant_id"),
        role=data["role"],
        email=data.get("email"),
    )


def enforce_csrf(request: Request, principal: Principal) -> None:
    """Mutating requests must carry a matching X-CSRF-Token header."""
    if request.method not in MUTATING:
        return
    header = request.headers.get("X-CSRF-Token", "")
    expected = read_csrf(principal.session_id)
    if not expected or not constant_time_eq(header, expected):
        raise ApiError(403, "CSRF_FAILED", "Missing or invalid CSRF token.")


def get_db_for(principal: Principal) -> Iterator[Session]:
    """A DB session with the RLS tenant GUC bound to the caller's tenant.

    Every tenant-owned query is therefore isolated by RLS even if app code
    forgets a filter. tenant_id comes from the session — never the request body.
    """
    db = SessionLocal()
    try:
        set_tenant_guc(db, principal.tenant_id)
        yield db
    finally:
        db.close()


def auth_db(
    request: Request,
    principal: Principal = Depends(get_principal),
) -> Iterator[Session]:
    """Combined dependency: authenticated + CSRF-checked + tenant-scoped DB."""
    enforce_csrf(request, principal)
    yield from get_db_for(principal)


@dataclass
class DeviceContext:
    device_id: str
    tenant_id: str
    zone_id: str | None
    db: Session
    token: str | None = None  # raw device token (HMAC key for signed request context, §12.4)


DEVICE_COOKIE = "device"


def device_db(request: Request) -> Iterator[DeviceContext]:
    """Authenticate a kiosk by its device token and yield a tenant-scoped DB.

    Token comes from the X-Device-Token header (preferred) or the `device`
    cookie set at pairing. Device auth uses a header/token — not a browser
    session — so it is not subject to the CSRF check."""
    from app.services.device_service import authenticate_device

    token = request.headers.get("X-Device-Token") or request.cookies.get(DEVICE_COOKIE)
    if not token:
        raise ApiError(401, "DEVICE_UNAUTHENTICATED", "No device token presented.")

    db = SessionLocal()
    try:
        with bypass_rls(db):  # device's tenant not known until we resolve the token
            ctx = authenticate_device(db, token)
        set_tenant_guc(db, ctx["tenant_id"])  # scope everything else to its tenant
        yield DeviceContext(
            device_id=ctx["device_id"], tenant_id=ctx["tenant_id"],
            zone_id=ctx["zone_id"], db=db, token=token,
        )
    finally:
        db.close()


@dataclass
class PersonPrincipal:
    session_id: str
    person_id: str
    email: str | None


def get_person(request: Request) -> PersonPrincipal:
    """Resolve the person-app caller from the session cookie (kind=person)."""
    session_id = request.cookies.get(SESSION_COOKIE)
    if not session_id:
        raise ApiError(401, "UNAUTHENTICATED", "No valid session.")
    data = read_session(session_id)
    if not data or data.get("kind") != "person" or not data.get("person_id"):
        raise ApiError(401, "UNAUTHENTICATED", "Not a person session.")
    return PersonPrincipal(session_id=session_id, person_id=data["person_id"], email=data.get("email"))


def person_db(request: Request, principal: PersonPrincipal = Depends(get_person)) -> Iterator[Session]:
    """CSRF-checked DB session for person-app calls. Person operations are
    cross-tenant by nature (your data at every business), so they do NOT bind a
    single tenant GUC — services use bypass_rls() and hard-filter by person_id."""
    # reuse the member CSRF rule (mutating methods need X-CSRF-Token)
    if request.method in MUTATING:
        header = request.headers.get("X-CSRF-Token", "")
        expected = read_csrf(principal.session_id)
        if not expected or not constant_time_eq(header, expected):
            raise ApiError(403, "CSRF_FAILED", "Missing or invalid CSRF token.")
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def require_role(*roles: str):
    def _dep(principal: Principal = Depends(get_principal)) -> Principal:
        if "*" in roles or principal.role in roles:
            return principal
        raise ApiError(403, "FORBIDDEN", "Insufficient permissions for this action.")
    return _dep
