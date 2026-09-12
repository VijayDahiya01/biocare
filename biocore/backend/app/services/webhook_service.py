"""Outbound webhooks — HMAC-signed event delivery (API Reference §6.3).

Every payload is signed sha256=<hmac> over the canonical JSON body so the
consumer (door controller, ERP, badge printer) can verify it.

Delivery path: `dispatch()` resolves the configured hooks and, for each, tries to
hand the delivery to the RabbitMQ event bus (out-of-band, retried by the worker).
If the bus is disabled/unreachable it delivers **inline** as a synchronous
fallback — so the platform works with or without a broker. `deliver_one()` is the
single delivery routine shared by both paths.
"""
import hashlib
import hmac
import json
import logging

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core import eventbus
from app.models import WebhookConfig

log = logging.getLogger("biocore.webhooks")
_MAX_RETRIES = 3


def canonical(payload: dict) -> bytes:
    return json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()


def sign(secret: str, payload: dict) -> str:
    mac = hmac.new(secret.encode(), canonical(payload), hashlib.sha256)
    return "sha256=" + mac.hexdigest()


def verify(secret: str, payload: dict, signature: str) -> bool:
    return hmac.compare_digest(sign(secret, payload), signature)


def deliver_one(*, url: str, secret: str, event: str, payload: dict,
                max_retries: int = _MAX_RETRIES) -> bool:
    """POST one signed webhook with retries. Returns True on success.

    Used inline by dispatch() and by the RabbitMQ worker. The worker treats a
    False return as a retry/dead-letter signal."""
    body = {**payload, "event": event, "signature": sign(secret, payload)}
    for attempt in range(1, max_retries + 1):
        try:
            resp = httpx.post(url, json=body, timeout=5)
            if resp.status_code < 400:
                return True
            log.warning("webhook %s -> %s status %s (try %s)", event, url, resp.status_code, attempt)
        except httpx.HTTPError as e:
            log.warning("webhook %s -> %s error %s (try %s)", event, url, e, attempt)
    log.error("webhook %s -> %s failed after %s tries", event, url, max_retries)
    return False


def dispatch(db: Session, *, tenant_id: str, event: str, payload: dict) -> int:
    """Resolve hooks for `event` and deliver each (via the bus, else inline).
    Returns the number of hooks the event was handed off for."""
    hooks = db.execute(
        select(WebhookConfig).where(
            WebhookConfig.event == event, WebhookConfig.active.is_(True)
        )
    ).scalars().all()

    handed_off = 0
    for hook in hooks:
        task = {"kind": "webhook.deliver", "url": hook.url, "secret": hook.secret,
                "event": event, "payload": payload}
        if eventbus.publish("webhook.deliver", task):
            handed_off += 1  # worker will deliver + retry + dead-letter
        else:
            if deliver_one(url=hook.url, secret=hook.secret, event=event, payload=payload):
                handed_off += 1
    return handed_off
