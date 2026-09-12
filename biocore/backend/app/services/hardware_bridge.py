"""Local hardware bridge commands (BIOCORE_COMPLETE_CHANGE_SPEC §19.3).

Turns a gate DECISION (allow/deny) + signed context into an actuation command for a local
bridge that drives a door relay / turnstile / boom barrier / elevator / alarm / LED / buzzer.

The command carries ONLY allow/deny + signed context — NEVER a face template, embedding or
subject biometric (§19.3). It is signed (HMAC-SHA256 keyed on the device token) so the bridge
executes commands only from its own server, and carries a nonce + timestamp against replay.
"""
from __future__ import annotations

import hashlib
import hmac
import os
import time

from app.core.config import settings

ACTUATORS = ("door_relay", "turnstile", "boom_barrier", "elevator", "alarm", "led", "buzzer")
_SIGNED_FIELDS = ("action", "actuator", "device_id", "gate_id", "duration_ms", "nonce", "timestamp")


def _canonical(cmd: dict) -> str:
    return "|".join(f"{k}={cmd.get(k, '')}" for k in _SIGNED_FIELDS)


def sign(secret: str, cmd: dict) -> str:
    return hmac.new(secret.encode(), _canonical(cmd).encode(), hashlib.sha256).hexdigest()


def build_command(*, device_ctx, decision: str, gate_id: str | None = None,
                  actuator: str = "door_relay", reason: str = "") -> dict:
    """Build a signed actuation command for the bridge. No biometric data is included."""
    allow = decision == "allow"
    cmd = {
        "action": "open" if allow else "deny",
        "actuator": actuator if actuator in ACTUATORS else "door_relay",
        "device_id": str(device_ctx.device_id),
        "gate_id": gate_id or (str(device_ctx.zone_id) if device_ctx.zone_id else None),
        "duration_ms": settings.hardware_open_ms if allow else 0,
        "nonce": os.urandom(8).hex(),
        "timestamp": time.time(),
        "reason": reason,  # a stable reason code for the operator, never biometric
    }
    cmd["signature"] = sign(device_ctx.token or "", cmd)
    return cmd


def verify_command(secret: str, cmd: dict) -> bool:
    """Bridge-side check: the command must carry a valid signature from the server."""
    expected = sign(secret, cmd)
    return hmac.compare_digest(str(cmd.get("signature", "")), expected)
