"""Trusted request context for gate requests (BIOCORE_COMPLETE_CHANGE_SPEC §12.4).

Every gate request from a hardened terminal carries a SIGNED context — device, tenant, gate,
zone, timestamp, nonce, software version, policy version — so the platform can prove it is:
  * fresh    — timestamp within the skew window (blocks stale/captured requests),
  * unique   — nonce not seen before (blocks replay),
  * bound    — names the authenticated device/tenant/zone (not the request body's claim),
  * accepted — build & policy version meet the configured minimums.

The device token is the shared secret (hashed at rest; presented raw per request as
X-Device-Token). The terminal HMAC-SHA256s the canonical context with it; the server, holding
the raw token for the request, recomputes and compares in constant time.

Enforcement is opt-in via settings.require_signed_context — when off, a request WITHOUT a
context is accepted (dev / back-compat); a request WITH a context is always verified.
"""
from __future__ import annotations

import hashlib
import hmac
import time
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.policy import EntryReason
from app.core.security import constant_time_eq
from app.models import DeviceRequestNonce

# fields, in a fixed order, that the signature covers (signature itself is excluded)
_FIELDS = ("device_id", "tenant_id", "gate_id", "zone_id", "timestamp", "nonce",
           "software_version", "policy_version")


class TrustedContextError(Exception):
    """A signed request context failed verification. `reason` is a stable EntryReason value."""
    def __init__(self, message: str, reason: str = EntryReason.DEVICE_NOT_TRUSTED.value):
        self.reason = reason
        super().__init__(message)


def canonical(ctx: dict) -> str:
    """Deterministic string the device and server both sign — order-fixed, pipe-joined."""
    return "|".join(f"{k}={ctx.get(k, '')}" for k in _FIELDS)


def sign(secret: str, ctx: dict) -> str:
    return hmac.new(secret.encode(), canonical(ctx).encode(), hashlib.sha256).hexdigest()


def _version_ok(reported: str, minimum: str) -> bool:
    if not minimum:
        return True
    def parse(v: str):
        return tuple(int(x) for x in v.split(".") if x.isdigit())
    try:
        return parse(reported) >= parse(minimum)
    except Exception:  # noqa: BLE001
        return False


def verify(db: Session, *, device_ctx, ctx: dict, secret: str, now: float | None = None) -> None:
    """Validate a signed gate context or raise TrustedContextError.

    `device_ctx` is the authenticated DeviceContext (device_id/tenant_id/zone_id come from the
    token, never the body); `ctx` is the untrusted context from the request; `secret` is the
    raw device token used as the HMAC key.
    """
    now = now if now is not None else time.time()

    # 1) freshness — timestamp within the skew window
    try:
        ts = float(ctx.get("timestamp"))
    except (TypeError, ValueError):
        raise TrustedContextError("Missing or invalid timestamp.")
    if abs(now - ts) > settings.trusted_context_skew_seconds:
        raise TrustedContextError("Stale request timestamp.")

    # 2) identity binding — the context must name the authenticated device/tenant/zone
    if str(ctx.get("device_id")) != str(device_ctx.device_id):
        raise TrustedContextError("Context device_id does not match the authenticated device.")
    if str(ctx.get("tenant_id")) != str(device_ctx.tenant_id):
        raise TrustedContextError("Context tenant_id does not match the authenticated device.")
    if device_ctx.zone_id and ctx.get("zone_id") and str(ctx["zone_id"]) != str(device_ctx.zone_id):
        raise TrustedContextError("Context zone_id does not match the device's zone.")

    # 3) build & policy version acceptable
    if not _version_ok(str(ctx.get("software_version", "")), settings.min_terminal_software_version):
        raise TrustedContextError("Terminal software version below the required minimum.")
    if settings.current_policy_version and str(ctx.get("policy_version")) != settings.current_policy_version:
        raise TrustedContextError("Context policy_version does not match the current policy.")

    # 4) signature — HMAC over the canonical context keyed by the device token
    nonce = str(ctx.get("nonce") or "")
    if not nonce:
        raise TrustedContextError("Missing request nonce.")
    if not secret:
        raise TrustedContextError("No device secret available to verify the signature.")
    expected = sign(secret, ctx)
    if not constant_time_eq(str(ctx.get("signature", "")), expected):
        raise TrustedContextError("Invalid request signature.")

    # 5) anti-replay — the nonce must be unseen; record it with a TTL (unique index backstops races)
    existing = db.execute(
        select(DeviceRequestNonce).where(
            DeviceRequestNonce.device_id == device_ctx.device_id,
            DeviceRequestNonce.nonce == nonce,
        )
    ).scalars().first()
    if existing is not None:
        raise TrustedContextError("Replayed request nonce.")
    db.add(DeviceRequestNonce(
        tenant_id=device_ctx.tenant_id, device_id=device_ctx.device_id, nonce=nonce,
        expires_at=datetime.now(timezone.utc) + timedelta(seconds=settings.nonce_ttl_seconds),
    ))
    db.flush()
