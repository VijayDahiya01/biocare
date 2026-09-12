"""Request-ID middleware. Every request gets a trace id used in the envelope
and as the audit-log correlation key."""
import secrets

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request


def new_request_id() -> str:
    return "req_" + secrets.token_hex(6)


class RequestIDMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        rid = request.headers.get("X-Request-ID") or new_request_id()
        request.state.request_id = rid
        response = await call_next(request)
        response.headers["X-Request-ID"] = rid
        return response
