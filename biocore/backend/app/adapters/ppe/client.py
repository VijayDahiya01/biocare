"""PPE detection adapter — a pluggable ML inference client.

The verified ZepIris engine (Doc 7) ships embed/spoof/blur/nudity only — NOT PPE.
So PPE is a separate, optional model server the platform calls directly. Like the
ZepIris model weights, the PPE model is a deployment-time artifact:

  * If PPE_SERVICE_URL is unset, detection is SKIPPED (configured=False) and the
    kiosk treats PPE as not-enforced — the platform runs fine without the model.
  * When configured, POST {image_b64} to <url>/detect and expect
    {"detections": {"helmet": true, "vest": false, ...}}.

This mirrors how spoof/blur degrade gracefully, and isolates the (future) model
behind one adapter so swapping providers touches only this file.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from functools import lru_cache

import httpx

from app.core.config import settings


@dataclass
class PpeResult:
    configured: bool
    detections: dict[str, bool] = field(default_factory=dict)


class PpeClient:
    def __init__(self, base_url: str | None = None, timeout: float | None = None):
        self.base_url = (base_url if base_url is not None else settings.ppe_service_url).rstrip("/")
        self.timeout = timeout or settings.ppe_timeout_seconds

    @property
    def enabled(self) -> bool:
        return bool(self.base_url)

    def detect(self, image_b64: str) -> PpeResult:
        if not self.enabled:
            return PpeResult(configured=False)
        try:
            with httpx.Client(base_url=self.base_url, timeout=self.timeout) as c:
                resp = c.post("/detect", json={"image_b64": image_b64})
            if resp.status_code >= 400:
                return PpeResult(configured=True, detections={})
            body = resp.json()
            return PpeResult(configured=True, detections=body.get("detections", {}))
        except (httpx.HTTPError, ValueError):
            # Fail open on transport errors: PPE is a safety overlay, not auth.
            return PpeResult(configured=True, detections={})


@lru_cache
def get_ppe() -> PpeClient:
    return PpeClient()
