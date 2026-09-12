"""Health & readiness. The gateway probes these; orchestration uses /ready."""
from fastapi import APIRouter, Request
from sqlalchemy import text

from app.core.config import settings
from app.core.db import engine
from app.core.envelope import success
from app.core.redis_client import client as redis_client

router = APIRouter(tags=["health"])


@router.get("/health")
def health(request: Request):
    """Liveness — is the API process up."""
    return success(request, {"status": "ok"})


def _face_ready() -> tuple[str, bool]:
    """(name, ready) for whichever face service is actually configured.

    This used to probe ZepIris unconditionally, which meant /ready returned 503 forever once
    ZepIris was removed — and a load balancer reading it would never send traffic to a perfectly
    healthy deployment. Probe what is wired instead.
    """
    if (settings.credential_engine or "").strip().lower() == "bioverify":
        from app.adapters.bioverify import BioVerifyError, get_bioverify
        try:
            return "bioverify", bool(get_bioverify().health().get("models_loaded", False))
        except (BioVerifyError, Exception):  # noqa: B014 - never let a probe raise
            return "bioverify", False

    engine_name = (settings.face_engine or "").strip().lower()
    if engine_name in ("remote", "zepiris", "http"):
        import httpx
        try:
            r = httpx.get(f"{settings.face_engine_url.rstrip('/')}/health", timeout=5.0)
            return "face_engine", r.status_code == 200
        except Exception:
            return "face_engine", False
    # The dev fake is in-process, so it is ready whenever the app is.
    return "face_engine", True


@router.get("/ready")
def ready(request: Request):
    """Readiness — can we reach our dependencies."""
    checks = {"postgres": False, "redis": False}
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        checks["postgres"] = True
    except Exception:
        pass
    try:
        checks["redis"] = bool(redis_client.ping())
    except Exception:
        pass

    name, ok = _face_ready()
    checks[name] = ok

    all_ok = all(checks.values())
    return success(request, {"ready": all_ok, "checks": checks}, status_code=200 if all_ok else 503)
