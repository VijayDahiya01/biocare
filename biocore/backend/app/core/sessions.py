"""Server-side sessions in Redis, delivered as HttpOnly cookies.

NOT JWT-in-localStorage. The cookie holds only an opaque session id; all session
state lives in Redis and is destroyed server-side on logout (real revocation).
"""
import json

from fastapi import Response

from app.core.config import settings
from app.core.redis_client import client, csrf_key, session_key
from app.core.security import new_token

SESSION_COOKIE = "session"
CSRF_COOKIE = "csrf"
ADMIN_ROLES = {"super_admin", "entity_admin", "manager", "contractor_sub_admin",
               "hr_payroll", "auditor_dpo", "security_reception"}


def _ttl_for(role: str) -> int:
    return (
        settings.session_ttl_admin_seconds
        if role in ADMIN_ROLES
        else settings.session_ttl_member_seconds
    )


def create_session(user_id: str, tenant_id: str | None, role: str,
                   email: str | None = None) -> tuple[str, str, int]:
    """Returns (session_id, csrf_token, ttl_seconds)."""
    session_id = new_token("sess_")
    csrf_token = new_token("csrf_")
    ttl = _ttl_for(role)
    payload = json.dumps({"user_id": user_id, "tenant_id": tenant_id, "role": role, "email": email})
    pipe = client.pipeline()
    pipe.set(session_key(session_id), payload, ex=ttl)
    pipe.set(csrf_key(session_id), csrf_token, ex=ttl)
    pipe.execute()
    return session_id, csrf_token, ttl


def create_person_session(person_id: str, email: str | None) -> tuple[str, str, int]:
    """Session for the person-centric app — carries person_id, no tenant.
    Returns (session_id, csrf_token, ttl_seconds)."""
    session_id = new_token("sess_")
    csrf_token = new_token("csrf_")
    ttl = settings.session_ttl_member_seconds
    payload = json.dumps({"kind": "person", "person_id": person_id, "email": email})
    pipe = client.pipeline()
    pipe.set(session_key(session_id), payload, ex=ttl)
    pipe.set(csrf_key(session_id), csrf_token, ex=ttl)
    pipe.execute()
    return session_id, csrf_token, ttl


def read_session(session_id: str) -> dict | None:
    raw = client.get(session_key(session_id))
    return json.loads(raw) if raw else None


def read_csrf(session_id: str) -> str | None:
    return client.get(csrf_key(session_id))


def destroy_session(session_id: str) -> None:
    client.delete(session_key(session_id), csrf_key(session_id))


def flush_user_sessions(user_id: str) -> int:
    """Erasure support: drop every session belonging to a user."""
    removed = 0
    for key in client.scan_iter(match="session:*"):
        raw = client.get(key)
        if raw and json.loads(raw).get("user_id") == user_id:
            sid = key.split(":", 1)[1]
            destroy_session(sid)
            removed += 1
    return removed


def set_session_cookies(response: Response, session_id: str, csrf_token: str, ttl: int) -> None:
    common = dict(
        secure=settings.cookie_secure,
        samesite="strict",
        max_age=ttl,
        path="/",
    )
    if settings.cookie_domain:
        common["domain"] = settings.cookie_domain
    # session: HttpOnly (JS can never read it).
    response.set_cookie(SESSION_COOKIE, session_id, httponly=True, **common)
    # csrf: readable by JS so the SPA can echo it in the X-CSRF-Token header.
    response.set_cookie(CSRF_COOKIE, csrf_token, httponly=False, **common)


def clear_session_cookies(response: Response) -> None:
    response.delete_cookie(SESSION_COOKIE, path="/")
    response.delete_cookie(CSRF_COOKIE, path="/")
