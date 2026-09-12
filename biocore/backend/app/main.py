"""BioCore API entrypoint.

All microservice logic is mounted here behind /api/v1. Every response — success
or error — uses the standard envelope, and every error carries the request_id.
"""
import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.core.config import settings
from app.core.envelope import ApiError, error_body
from app.core.guards import assert_production_safe
from app.core.middleware import RequestIDMiddleware

logging.basicConfig(level=settings.log_level)

# Refuse to start on an unsafe production configuration, before any request lands.
assert_production_safe()

app = FastAPI(
    title="BioCore Platform API",
    version="1.0.0",
    docs_url="/api/v1/docs",
    openapi_url="/api/v1/openapi.json",
)

app.add_middleware(RequestIDMiddleware)


@app.exception_handler(ApiError)
async def api_error_handler(request: Request, exc: ApiError):
    rid = getattr(request.state, "request_id", "req_unknown")
    return JSONResponse(
        status_code=exc.status_code,
        content=error_body(rid, exc.code, exc.message, exc.details),
    )


@app.exception_handler(RequestValidationError)
async def validation_handler(request: Request, exc: RequestValidationError):
    rid = getattr(request.state, "request_id", "req_unknown")
    return JSONResponse(
        status_code=400,
        content=error_body(rid, "VALIDATION_ERROR", "Request validation failed.",
                           details=exc.errors()),
    )


@app.exception_handler(Exception)
async def unhandled_handler(request: Request, exc: Exception):
    rid = getattr(request.state, "request_id", "req_unknown")
    logging.exception("Unhandled error (request_id=%s)", rid)
    return JSONResponse(
        status_code=500,
        content=error_body(rid, "INTERNAL_ERROR", "An unexpected error occurred."),
    )


# Mount API routes (import after app + handlers are set up).
from app.api.v1 import router as api_router  # noqa: E402

app.include_router(api_router)

# Prometheus metrics at /metrics (scraped by Prometheus on the internal network).
# Guarded so the app still runs if the optional dependency isn't installed.
try:
    from prometheus_fastapi_instrumentator import Instrumentator  # noqa: E402

    Instrumentator().instrument(app).expose(app, endpoint="/metrics", include_in_schema=False)
except ImportError:
    logging.warning("prometheus-fastapi-instrumentator not installed; /metrics disabled")
