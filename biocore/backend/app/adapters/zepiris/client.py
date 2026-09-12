"""The ZepIris adapter — the single most important integration component.

Everything face-related goes through here. It is the ONLY place that knows the
real ZepIris wire format, so if ZepIris changes, only this file changes.

Verified facts (Doc 7, checked against github.com/zepto-labs/zepiris v1.0.0):
  * Main API on :8000. Insert/search/upsert are multipart/form-data with a real
    file upload — NOT base64 JSON. The platform's own API stays base64-friendly
    for the browser; this adapter decodes base64 -> bytes -> multipart.
  * Multi-tenant via a `tenant` FORM FIELD on every call (one shared Milvus
    collection `zepiris_faces` with a tenant column) — NOT per-tenant collections.
  * Response IDs are `requestId` (camelCase).
  * Search returns 200 with an empty matches[] on a bad image / no face — it does
    NOT raise. Insert/upsert return 422 on IQA failure / no face, 409 on dup id.
  * Health endpoints are /healthz (liveness) and /readyz (readiness).
"""
from __future__ import annotations

import base64
import binascii
from dataclasses import dataclass, field
from functools import lru_cache

import httpx

from app.core.config import settings


class ZepIrisError(Exception):
    def __init__(self, message: str, status_code: int | None = None, code: str | None = None):
        self.message = message
        self.status_code = status_code
        self.code = code
        super().__init__(message)


@dataclass
class Match:
    id: str
    score: float


@dataclass
class ImageQuality:
    passed: bool
    blur_ok: bool = True
    spoof: bool = False
    safe: bool = True
    raw: dict = field(default_factory=dict)


@dataclass
class EnrollResult:
    request_id: str
    face_id: str
    stored: bool
    quality: ImageQuality


@dataclass
class SearchResult:
    request_id: str
    quality: ImageQuality
    matches: list[Match]

    @property
    def best(self) -> Match | None:
        return self.matches[0] if self.matches else None


def _decode_base64_image(image: str) -> bytes:
    """Accept a raw base64 string or a data URL (data:image/jpeg;base64,....)."""
    if image.startswith("data:"):
        try:
            image = image.split(",", 1)[1]
        except IndexError:
            raise ZepIrisError("Malformed data URL image", status_code=400, code="BAD_IMAGE")
    try:
        return base64.b64decode(image, validate=True)
    except (binascii.Error, ValueError):
        raise ZepIrisError("Image is not valid base64", status_code=400, code="BAD_IMAGE")


def _parse_quality(iqa: dict) -> ImageQuality:
    """Map ZepIris's imageQualityAssessment block onto ImageQuality.

    Verified against zepiris v1.0.0 (POST /v1/iqa/assess, embedded verbatim by the
    Main API as `imageQualityAssessment`):

        {"passed": bool,
         "nsfw":  {"is_safe":  bool, "probability": float},
         "spoof": {"is_live":  bool, "probability": float},
         "blur":  {"is_sharp": bool, "probability": float}}

    Two traps, both previously mis-mapped here:
      * the content-safety key is `nsfw`, NOT `nudity`;
      * liveness is reported as `is_live`, which is the INVERSE of the `spoof`
        flag this dataclass exposes (there is no `is_spoof` field on the wire).

    Missing evidence fails closed. `quality.spoof` gates entry in kiosk_service and
    gps.py, so an absent/garbled block must read as "spoofed", never as "live".
    """
    if not iqa:
        return ImageQuality(passed=False, blur_ok=False, spoof=True, safe=False, raw={})

    blur = iqa.get("blur") or {}
    spoof = iqa.get("spoof") or {}
    # "nsfw" is the wire key; "nudity" tolerated for older/mocked payloads.
    nsfw = iqa.get("nsfw") or iqa.get("nudity") or {}

    if "is_live" in spoof:
        is_spoof = not bool(spoof["is_live"])
    else:
        # No liveness evidence -> treat as a spoof rather than silently allowing entry.
        is_spoof = bool(spoof.get("is_spoof", True))

    return ImageQuality(
        passed=bool(iqa.get("passed", False)),
        blur_ok=bool(blur.get("is_sharp", False)),
        spoof=is_spoof,
        safe=bool(nsfw.get("is_safe", False)),
        raw=iqa,
    )


class ZepIrisClient:
    def __init__(self, base_url: str | None = None, timeout: float | None = None):
        self.base_url = (base_url or settings.zepiris_url).rstrip("/")
        self.timeout = timeout or settings.zepiris_timeout_seconds

    def _client(self) -> httpx.Client:
        return httpx.Client(base_url=self.base_url, timeout=self.timeout)

    # --- insert (enroll a new face) ---
    def insert(self, tenant: str, face_id: str, image_b64: str) -> EnrollResult:
        return self._write("/v1/faces/insert", tenant, face_id, image_b64, op="INSERT")

    # --- upsert (re-enrollment) ---
    def upsert(self, tenant: str, face_id: str, image_b64: str) -> EnrollResult:
        return self._write("/v1/faces/upsert", tenant, face_id, image_b64, op="UPSERT")

    def _write(self, path: str, tenant: str, face_id: str, image_b64: str, op: str) -> EnrollResult:
        img = _decode_base64_image(image_b64)
        files = {"file": (f"{face_id}.jpg", img, "image/jpeg")}
        data = {"id": face_id, "tenant": tenant}
        with self._client() as c:
            resp = c.post(path, data=data, files=files)
        if resp.status_code == 409:
            raise ZepIrisError("Face id already exists", status_code=409, code="DUPLICATE")
        if resp.status_code == 422:
            raise ZepIrisError("Image quality / no face", status_code=422, code="IMAGE_QUALITY_FAILED")
        if resp.status_code >= 400:
            raise ZepIrisError(f"ZepIris {op} failed: {resp.status_code}", status_code=resp.status_code)
        body = resp.json()
        quality = _parse_quality(body.get("imageQualityAssessment", {}))
        result = body.get("userOperationResult", {})
        return EnrollResult(
            request_id=body.get("requestId", ""),
            face_id=face_id,
            stored=result.get("status") == "success",
            quality=quality,
        )

    # --- search (the check-in call) ---
    def search(
        self,
        tenant: str,
        image_b64: str,
        top_k: int = 5,
        threshold: float | None = None,
    ) -> SearchResult:
        img = _decode_base64_image(image_b64)
        files = {"file": ("query.jpg", img, "image/jpeg")}
        data = {"id": "query", "tenant": tenant}
        params: dict[str, object] = {"top_k": top_k}
        if threshold is not None:
            params["threshold"] = threshold
        with self._client() as c:
            resp = c.post("/v1/faces/search", params=params, data=data, files=files)
        # Verified: search returns 200 even on a bad image (empty matches).
        if resp.status_code >= 400:
            raise ZepIrisError(f"ZepIris search failed: {resp.status_code}", status_code=resp.status_code)
        body = resp.json()
        quality = _parse_quality(body.get("imageQualityAssessment", {}))
        raw_matches = body.get("searchResult", {}).get("matches", []) or []
        matches = [Match(id=m["id"], score=float(m["score"])) for m in raw_matches]
        return SearchResult(request_id=body.get("requestId", ""), quality=quality, matches=matches)

    # --- delete (part of the erasure cascade) ---
    def delete(self, face_id: str) -> bool:
        with self._client() as c:
            resp = c.delete("/v1/faces/delete", params={"id": face_id})
        if resp.status_code == 404:
            return False
        if resp.status_code >= 400:
            raise ZepIrisError(f"ZepIris delete failed: {resp.status_code}", status_code=resp.status_code)
        body = resp.json()
        return body.get("userOperationResult", {}).get("status") == "success"

    # --- get metadata ---
    def get(self, face_id: str) -> dict | None:
        with self._client() as c:
            resp = c.get(f"/v1/faces/get/{face_id}")
        if resp.status_code == 404:
            return None
        if resp.status_code >= 400:
            raise ZepIrisError(f"ZepIris get failed: {resp.status_code}", status_code=resp.status_code)
        return resp.json()

    # --- health / readiness ---
    def healthz(self) -> bool:
        return self._ping("/healthz")

    def readyz(self) -> bool:
        return self._ping("/readyz")

    def _ping(self, path: str) -> bool:
        try:
            with self._client() as c:
                resp = c.get(path)
            return resp.status_code == 200 and resp.json().get("status") == "ok"
        except (httpx.HTTPError, ValueError):
            return False


@lru_cache
def get_zepiris():
    """The legacy face engine.

    RETIRED when the product runs on BioVerify credentials: ZepIris, Milvus and MinIO are no
    longer deployed, so every call here would be a connection refused surfacing as an opaque
    500. Fail immediately with something a person can act on instead — callers already handle
    ZepIrisError and turn it into a clean response.

    The features still routed through here (kiosk 1:N check-in, GPS field check-in, the
    blacklist watchlist, and the person "capture once" master template) have direct
    replacements on the new engine and need porting; see docs/DEPLOY_DIGITALOCEAN.md.
    """
    if settings.fake_zepiris:
        from app.adapters.zepiris.fake import FakeZepIris
        return FakeZepIris()
    if (settings.credential_engine or "").strip().lower() == "bioverify":
        raise ZepIrisError(
            "This feature still uses the retired ZepIris face engine, which is not deployed. "
            "Use the verified-identity flow instead: /person/verify/* to register a face and "
            "/entry/match or /entry/identify at a gate.",
            status_code=503, code="LEGACY_ENGINE_RETIRED")
    return ZepIrisClient()
