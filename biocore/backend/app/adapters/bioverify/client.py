"""BioVerify credential API over HTTP (§15.1) — the real client, all nine routes.

    GET  /health
    GET  /policy/manifest
    POST /credentials/issue                     digest mint (spec 6.1)
    POST /credentials/{id}/revoke               (spec 6.2)
    GET  /credentials/{id}/status               (spec 6.3)
    GET  /revocations/sync                      (spec 6.4)
    POST /poc/enrol                             face-only onboarding       -> qr_text
    POST /poc/enrol-with-document               face + document onboarding -> qr_text
    POST /poc/verify                            gate decision (image + qr_text)

Auth is the `X-API-Key` header on every route except /health. The `/poc/*` routes take
multipart uploads; the credential routes take JSON.

The enrol RESPONSE FIELD NAMES are not pinned by the published OpenAPI (the body schema is an
open object), so the extractors below accept the plausible spellings — the same tolerance
`RemoteFaceEngine` uses for `embedding`/`template`. Pin them to the real names once an enrol
response has been observed; `EnrolResult.raw` carries whatever else came back.

Nothing here logs an image, a `qr_text` or a digest (§7.5, §14.1).
"""
from __future__ import annotations

import base64
import binascii
import json
from typing import Any

import httpx

from app.adapters.bioverify.base import (
    BioVerifyError,
    BioVerifyRefused,
    EnrolmentEvidence,
    EnrolResult,
    VerifyResult,
    band_for,
    classify_outcome,
)
from app.core.config import settings

# Response keys, most-likely first. See the module docstring.
_QR_TEXT_KEYS = ("qr_text", "qrText", "qr", "credential_text", "credential", "text")
_QR_PNG_KEYS = ("qr_png_b64", "qr_png_base64", "qr_png", "qrPng", "qr_image", "png")
_CRED_ID_KEYS = ("credential_id", "credentialId", "id", "cid")
_EXPIRES_KEYS = ("expires_at", "expiresAt", "expiry", "expires")


def _first(body: dict[str, Any], keys: tuple[str, ...]) -> Any:
    for k in keys:
        v = body.get(k)
        if v not in (None, ""):
            return v
    return None


def _media(raw: bytes) -> tuple[str, str]:
    """(filename, content-type) sniffed from the magic bytes, so the upload is labelled
    honestly rather than always claiming JPEG."""
    if raw.startswith(b"\x89PNG\r\n\x1a\n"):
        return "capture.png", "image/png"
    if raw[:4] == b"RIFF" and raw[8:12] == b"WEBP":
        return "capture.webp", "image/webp"
    return "capture.jpg", "image/jpeg"


def _image_part(image_b64: str, field_name: str) -> tuple[str, tuple[str, bytes, str]]:
    """Turn BioCore's base64 capture (optionally a `data:` URI, as the browser produces) into a
    multipart file part. The bytes are transient — never logged (§14.1)."""
    if not image_b64 or not image_b64.strip():
        raise BioVerifyError(f"{field_name}: no image supplied.")
    payload = image_b64.strip()
    if payload.startswith("data:"):
        _, _, payload = payload.partition(",")
    try:
        raw = base64.b64decode(payload, validate=False)
    except (binascii.Error, ValueError) as e:
        raise BioVerifyError(f"{field_name}: image is not valid base64.") from e
    if not raw:
        raise BioVerifyError(f"{field_name}: image decoded to zero bytes.")
    filename, content_type = _media(raw)
    return field_name, (filename, raw, content_type)


def _refusal(r: httpx.Response) -> tuple[str, bool] | None:
    """(reason, retryable) when the service declined this capture, else None.

    A refusal looks like `{"refused":"QUALITY_INSUFFICIENT","detail":"hard quality gate failed:
    RetryReason.LANDMARK_UNSTABLE","retryable":true}`. The specific RetryReason is what lets the
    screen say something useful instead of "try again".
    """
    if r.status_code != 422:
        return None
    try:
        body = r.json()
    except ValueError:
        return None
    if not isinstance(body, dict) or "refused" not in body:
        return None
    detail = str(body.get("detail") or "")
    # "hard quality gate failed: RetryReason.LANDMARK_UNSTABLE" -> "LANDMARK_UNSTABLE"
    reason = detail.rsplit("RetryReason.", 1)[-1].strip() if "RetryReason." in detail else ""
    return (reason or str(body.get("refused")), bool(body.get("retryable", True)))


def _detail(r: httpx.Response) -> str:
    """The service's error text — safe to surface (it explains WHY, e.g. 'enrolment evidence
    does not show quality_pass') and carries no biometric payload. Truncated defensively."""
    try:
        body = r.json()
    except ValueError:
        return (r.text or "").strip()[:300]
    if isinstance(body, dict) and "detail" in body:
        d = body["detail"]
        return (d if isinstance(d, str) else json.dumps(d))[:300]
    return json.dumps(body)[:300]


class BioVerifyClient:
    """HTTP client for the BioVerify credential API. One instance is reused per process."""

    name = "bioverify"

    def __init__(self, *, url: str | None = None, api_key: str | None = None,
                 timeout: float | None = None, verify_timeout: float | None = None) -> None:
        base = (settings.bioverify_url if url is None else url).strip().rstrip("/")
        if not base:
            raise BioVerifyError("BIOVERIFY_URL is not set — cannot reach the credential API.")
        key = settings.bioverify_api_key if api_key is None else api_key
        if not key:
            raise BioVerifyError("BIOVERIFY_API_KEY is not set — every route but /health needs it.")
        self._base = base
        self._headers = {"X-API-Key": key}
        self._timeout = timeout if timeout is not None else settings.bioverify_timeout_seconds
        self._verify_timeout = (verify_timeout if verify_timeout is not None
                                else settings.bioverify_verify_timeout_seconds)

    # ---- transport -----------------------------------------------------------------

    def _request(self, method: str, path: str, *, timeout: float | None = None,
                 **kwargs: Any) -> dict[str, Any]:
        try:
            r = httpx.request(method, f"{self._base}{path}", headers=self._headers,
                              timeout=timeout or self._timeout, **kwargs)
        except httpx.HTTPError as e:
            raise BioVerifyError(f"BioVerify {path} unreachable: {e}") from e
        if r.status_code >= 400:
            refusal = _refusal(r)
            if refusal is not None:
                reason, retryable = refusal
                raise BioVerifyRefused(
                    f"BioVerify {path} refused this capture: {reason}",
                    reason=reason, retryable=retryable)
            raise BioVerifyError(f"BioVerify {path} HTTP {r.status_code}: {_detail(r)}")
        try:
            body = r.json()
        except ValueError as e:
            raise BioVerifyError(f"BioVerify {path} returned a non-JSON body.") from e
        if not isinstance(body, dict):
            raise BioVerifyError(
                f"BioVerify {path} returned {type(body).__name__}, expected an object.")
        return body

    # ---- service state -------------------------------------------------------------

    def health(self) -> dict[str, Any]:
        """`models_loaded: false` here means enrol/verify WILL fail — worth surfacing in §23
        monitoring rather than discovering it at a gate."""
        return self._request("GET", "/health")

    def policy_manifest(self) -> dict[str, Any]:
        """Spec 6.5 — embedding-space registry, match threshold, PAD posture, signing key."""
        return self._request("GET", "/policy/manifest")

    # ---- onboarding ----------------------------------------------------------------

    def enrol(self, *, image: str, expires_in_s: int,
              qr_scale: int | None = None) -> EnrolResult:
        """Face-only onboarding. `expires_in_s` is REQUIRED (no default) so the credential
        lifetime always comes from BioCore retention policy — the service's own 30-day default
        would silently diverge from it."""
        scale = qr_scale if qr_scale is not None else settings.bioverify_qr_scale
        return self._enrol_result(self._request(
            "POST", "/poc/enrol",
            files=dict([_image_part(image, "image")]),
            data={"expires_in_s": str(int(expires_in_s)), "qr_scale": str(int(scale))}))

    def enrol_with_document(self, *, live: str, document: str, expires_in_s: int,
                            document_type: str = "PASSPORT",
                            qr_scale: int | None = None) -> EnrolResult:
        """Face + document onboarding (spec 7.4): match the live face to the document photo,
        then enrol the LIVE face. The document image is destroyed and never reaches the cloud.

        This does NOT establish that the document is genuine — a forged document carrying the
        attacker's own photograph passes face match perfectly (7.4.6) — and it cannot tell a
        physical document from a screen. Where gov KYC (§19.1) is available it is the stronger
        proof; this path is for subjects that route cannot cover.
        """
        scale = qr_scale if qr_scale is not None else settings.bioverify_qr_scale
        return self._enrol_result(self._request(
            "POST", "/poc/enrol-with-document",
            files=dict([_image_part(live, "live"), _image_part(document, "document")]),
            data={"document_type": document_type, "expires_in_s": str(int(expires_in_s)),
                  "qr_scale": str(int(scale))}))

    @staticmethod
    def _enrol_result(body: dict[str, Any]) -> EnrolResult:
        qr_text = _first(body, _QR_TEXT_KEYS)
        if not isinstance(qr_text, str) or not qr_text:
            raise BioVerifyError(
                "BioVerify enrol returned no credential text; expected one of "
                + ", ".join(_QR_TEXT_KEYS) + f" but got keys: {sorted(body)}.")
        cred_id = _first(body, _CRED_ID_KEYS)
        expires = _first(body, _EXPIRES_KEYS)
        doc = body.get("document_match") or body.get("document")
        return EnrolResult(
            qr_text=qr_text,
            credential_id=(str(cred_id) if cred_id is not None else None),
            qr_png_b64=_first(body, _QR_PNG_KEYS),
            expires_at=(str(expires) if expires is not None else None),
            document_match=(doc if isinstance(doc, dict) else None),
            raw=body,
        )

    # ---- the gate ------------------------------------------------------------------

    def verify(self, *, image: str, qr_text: str) -> VerifyResult:
        """The gate decision: live capture + the scanned credential. Runs on the shorter verify
        timeout — a queue is waiting. Unknown outcomes deny (§22.6)."""
        if not qr_text or not qr_text.strip():
            raise BioVerifyError("verify: no qr_text scanned.")
        body = self._request("POST", "/poc/verify",
                             files=dict([_image_part(image, "image")]),
                             data={"qr_text": qr_text}, timeout=self._verify_timeout)
        outcome = str(body.get("outcome") or "").strip().upper()
        allowed, retry = classify_outcome(outcome)
        raw_similarity = body.get("similarity")
        raw_threshold = body.get("threshold")
        similarity = float(raw_similarity) if isinstance(raw_similarity, (int, float)) else None
        threshold = float(raw_threshold) if isinstance(raw_threshold, (int, float)) else None
        return VerifyResult(
            outcome=outcome or "UNKNOWN",
            reason=str(body.get("reason") or ""),
            allowed=allowed, retry=retry,
            band=band_for(similarity, threshold),
            similarity=similarity, threshold=threshold,
            policy_version=body.get("policy_version"), raw=body,
        )

    # ---- credential plane ----------------------------------------------------------

    def issue_credential(self, *, evidence: EnrolmentEvidence, digest: str | None = None,
                         **extra: Any) -> dict[str, Any]:
        """Spec 6.1 — the digest mint path, for when an on-device SDK computes the embedding.
        Carries a digest, never a template. `/poc/enrol` already seals and issues internally;
        this is the ALTERNATIVE mint, not a second step after it."""
        body: dict[str, Any] = {"enrolment_evidence": evidence.to_dict()}
        if digest is not None:
            body["digest"] = digest
        body.update(extra)
        return self._request("POST", "/credentials/issue", json=body)

    def credential_status(self, *, credential_id: str) -> dict[str, Any]:
        """Spec 6.3."""
        return self._request("GET", f"/credentials/{credential_id}/status")

    def revoke_credential(self, *, credential_id: str) -> dict[str, Any]:
        """Spec 6.2. Revoking UPSTREAM is what makes a BioCore revoke/erase real at the gate:
        BioCore holds no template for these subjects, so a local status change alone stops
        nothing that already has the credential in hand."""
        return self._request("POST", f"/credentials/{credential_id}/revoke")

    def revocations_sync(self, *, tenant: str | None = None,
                         since: int | None = None) -> dict[str, Any]:
        """Spec 6.4 — unexpired revocations, for a gate that must decide without the network.
        The service currently returns `signature: null` with its own "unsigned; spec 6.4
        requires a signed list" warning: an unsigned list is not a trustworthy input, so check
        `signature` before letting one drive offline decisions (§16)."""
        params = {k: v for k, v in (("tenant", tenant), ("since", since)) if v is not None}
        return self._request("GET", "/revocations/sync", params=params or None)
