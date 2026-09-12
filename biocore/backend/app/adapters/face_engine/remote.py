"""Remote face engine over HTTP (§15.1) — wire-ready client for a real engine.

Talks to a real engine (e.g. ZepIris behind an HTTP shim) at FACE_ENGINE_URL. The exact vendor
contract (paths/fields) is deployment-specific; the generic default assumes:
    POST {url}/embed     {image}            -> {embedding: <base64>}
    POST {url}/liveness  {image}            -> {live: bool, detail: str}
    POST {url}/compare   {a: <b64>, b: <b64>} -> {score: float, match: bool}
Adjust paths/field-mapping to the vendor when their API is available. Images/embeddings are
transient — never logged (§14.1).
"""
from __future__ import annotations

import base64

import httpx

from app.adapters.face_engine.base import FaceEngineError, LivenessResult, MatchResult
from app.core.config import settings


class RemoteFaceEngine:
    name = "remote"

    def __init__(self) -> None:
        if not settings.face_engine_url:
            raise FaceEngineError("FACE_ENGINE_URL is not set — cannot use the remote face engine.")
        self._base = settings.face_engine_url.rstrip("/")
        self._headers = ({"Authorization": settings.face_engine_token}
                         if settings.face_engine_token else {})

    def _post(self, path: str, payload: dict) -> dict:
        try:
            r = httpx.post(f"{self._base}{path}", headers=self._headers, json=payload, timeout=30.0)
        except httpx.HTTPError as e:
            raise FaceEngineError(f"Face engine {path} failed: {e}")
        if r.status_code >= 400:
            raise FaceEngineError(f"Face engine {path} HTTP {r.status_code}")
        return r.json()

    def embed(self, *, image: str) -> bytes:
        data = self._post("/embed", {"image": image})
        emb = data.get("embedding") or data.get("template")
        if emb is None:
            raise FaceEngineError("Face engine returned no embedding.")
        return base64.b64decode(emb) if isinstance(emb, str) else bytes(emb)

    def assess_liveness(self, *, image: str) -> LivenessResult:
        data = self._post("/liveness", {"image": image})
        return LivenessResult(passed=bool(data.get("live", data.get("passed", False))),
                              detail=str(data.get("detail", "")))

    def compare(self, *, stored: bytes, live: bytes) -> MatchResult:
        data = self._post("/compare", {"a": base64.b64encode(stored).decode(),
                                       "b": base64.b64encode(live).decode()})
        score = float(data.get("score", 0.0))
        threshold = settings.face_match_threshold
        matched = bool(data.get("match", score >= threshold))
        band = "high" if score >= 0.8 else "medium" if score >= threshold else "none"
        return MatchResult(matched=matched, band=band, score=score)
