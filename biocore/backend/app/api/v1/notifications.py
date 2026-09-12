"""Notification channel test (API Reference §12)."""
from fastapi import APIRouter, Depends, Request

from app.api.deps import Principal, require_role
from app.core.envelope import success
from app.services.notifier import send_email

router = APIRouter(prefix="/notifications", tags=["notifications"])
_ADMIN = ("entity_admin", "manager", "super_admin")


@router.post("/test")
def test_notification(request: Request, body: dict | None = None,
                      principal: Principal = Depends(require_role(*_ADMIN))):
    """Send a test notification to verify a channel works (admin only)."""
    to = (body or {}).get("to") or (principal.email or "admin@example.com")
    send_email(to=to, subject="BioCore test notification",
               body="This is a test notification from BioCore.")
    return success(request, {"sent": True, "to": to})
