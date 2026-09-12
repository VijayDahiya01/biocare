"""Health & readiness. The gateway probes these; orchestration uses /ready."""
from fastapi import APIRouter, Request
from sqlalchemy import text

from app.adapters.zepiris import get_zepiris
from app.core.db import engine
from app.core.envelope import success
from app.core.redis_client import client as redis_client

router = APIRouter(tags=["health"])


@router.get("/health")
def health(request: Request):
    """Liveness — is the API process up."""
    return success(request, {"status": "ok"})


@router.get("/ready")
def ready(request: Request):
    """Readiness — can we reach our dependencies."""
    checks = {"postgres": False, "redis": False, "zepiris": False}
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        checks["postgres"] = True
    except Exception:
        pass
    try:
        checks["redis"] = redis_client.ping()
    except Exception:
        pass
    # ZepIris models take 30-60s to load; readyz reflects that.
    checks["zepiris"] = get_zepiris().readyz()

    all_ok = all(checks.values())
    return success(request, {"ready": all_ok, "checks": checks}, status_code=200 if all_ok else 503)
