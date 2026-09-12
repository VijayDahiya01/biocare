"""The standard response envelope used by EVERY endpoint (API Reference §1.3)."""
from typing import Any

from fastapi import Request
from fastapi.responses import JSONResponse


class ApiError(Exception):
    """Raise anywhere; the global handler turns it into the error envelope."""

    def __init__(self, status_code: int, code: str, message: str, details: Any = None):
        self.status_code = status_code
        self.code = code
        self.message = message
        self.details = details
        super().__init__(message)


def request_id_of(request: Request) -> str:
    return getattr(request.state, "request_id", "req_unknown")


def success(request: Request, data: Any, status_code: int = 200) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={"success": True, "data": data, "request_id": request_id_of(request)},
    )


def error_body(request_id: str, code: str, message: str, details: Any = None) -> dict:
    err: dict[str, Any] = {"code": code, "message": message}
    if details is not None:
        err["details"] = details
    return {"success": False, "error": err, "request_id": request_id}
