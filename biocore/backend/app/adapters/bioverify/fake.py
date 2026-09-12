"""In-process FAKE BioVerify — DEV ONLY (FAKE_BIOVERIFY=true / BIOVERIFY=fake).

Models the real service's OBSERVED behaviour closely enough that code which works here works
there: credential ids are 16-byte hex (the real service rejects anything else), an undecodable
`qr_text` comes back as RETRY/DECODE_FAILED exactly as the live service answered, and
`/credentials/issue` enforces the same evidence rules — quality_pass, pad_pass, and the
`deepfake_pass` key present even when null.

FORBIDDEN in production (the factory blocks it). It is not a biometric and must never gate
real access (§3.2, §29.18).

One thing it models OPTIMISTICALLY: revoking a credential here makes a later verify deny.
Whether the live `/poc/verify` consults revocation is UNVERIFIED. Do not let that assumption
stand alone in the entry path — BioCore's own `active_credential`/`authorization.evaluate`
check must remain the first gate, so a locally revoked subject never reaches verify at all.
"""
from __future__ import annotations

import base64
import hashlib
import time
import uuid
from typing import Any

from app.adapters.bioverify.base import (
    BioVerifyError,
    EnrolmentEvidence,
    EnrolResult,
    VerifyResult,
    band_for,
)

_PREFIX = "BVFAKE"
_THRESHOLD = 0.35          # mirrors the live /policy/manifest
_PNG_1PX = ("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmM"
            "IQAAAABJRU5ErkJggg==")


_MIN_CAPTURE_BYTES = 1024
_MAGIC = (b"\xff\xd8\xff", b"\x89PNG\r\n\x1a\n", b"RIFF")


def _digest(image: str) -> str:
    payload = (image or "").strip()
    if payload.startswith("data:"):
        _, _, payload = payload.partition(",")
    return hashlib.sha256(payload.encode()).hexdigest()


def _quality_gate(image: str) -> None:
    """Stand in for the real service's hard quality gate.

    The live service refuses a capture it cannot enrol from — `QUALITY_INSUFFICIENT`, observed
    against a real but too-small, upscaled photo. It cannot be reproduced faithfully without the
    models, but a fake that accepts literally anything would let a credential be minted from
    six bytes of rubbish and call the test green. So: it must at least decode to a real image
    of plausible size."""
    payload = (image or "").strip()
    if payload.startswith("data:"):
        _, _, payload = payload.partition(",")
    try:
        raw = base64.b64decode(payload, validate=False)
    except Exception:  # noqa: BLE001 - any decode failure is an unusable capture
        raw = b""
    if len(raw) < _MIN_CAPTURE_BYTES or not raw.startswith(_MAGIC):
        raise BioVerifyError(
            "BioVerify /poc/enrol HTTP 422: {\"refused\":\"QUALITY_INSUFFICIENT\","
            "\"detail\":\"hard quality gate failed\"}")


class FakeBioVerify:
    name = "fake-bioverify"

    def __init__(self) -> None:
        self._revoked: set[str] = set()
        self._issued: dict[str, dict[str, Any]] = {}

    # ---- service state -------------------------------------------------------------

    def health(self) -> dict[str, Any]:
        return {"status": "ok", "credentials": len(self._issued), "models_loaded": True}

    def policy_manifest(self) -> dict[str, Any]:
        return {"policy_version": 7, "match_threshold": _THRESHOLD,
                "embedding_space_registry": {"fake-v1": 1},
                "pad": {"candidate": "fake", "status": "DEV_ONLY"},
                "deepfake": {"available": False, "reason": "dev fake"},
                "calibration": "DEV FAKE — not calibrated, never production."}

    # ---- onboarding ----------------------------------------------------------------

    def enrol(self, *, image: str, expires_in_s: int, qr_scale: int | None = None) -> EnrolResult:
        _quality_gate(image)
        return self._mint(_digest(image), expires_in_s)

    def enrol_with_document(self, *, live: str, document: str, expires_in_s: int,
                            document_type: str = "PASSPORT",
                            qr_scale: int | None = None) -> EnrolResult:
        _quality_gate(live)
        _quality_gate(document)
        result = self._mint(_digest(live), expires_in_s)
        # Mirrors the real response's honesty about what a document check does NOT prove.
        result.document_match = {"document_type": document_type, "face_match_pass": True,
                                 "document_authenticity_pass": None,
                                 "document_screen_replay_pass": False}
        return result

    def _mint(self, token: str, expires_in_s: int) -> EnrolResult:
        # A FRESH id per mint, 16 bytes hex like the real service. Deriving it from the face
        # instead would make two people who share a photo collide, which no real credential
        # service does — and would trip the unique index on (tenant_id, external_credential_id).
        credential_id = uuid.uuid4().hex
        self._issued[credential_id] = {"token": token,
                                       "expires_at": int(time.time()) + int(expires_in_s)}
        self._revoked.discard(credential_id)
        return EnrolResult(qr_text=f"{_PREFIX}.{token}.{credential_id}",
                           credential_id=credential_id, qr_png_b64=_PNG_1PX,
                           expires_at=str(self._issued[credential_id]["expires_at"]),
                           raw={"fake": True})

    # ---- the gate ------------------------------------------------------------------

    def verify(self, *, image: str, qr_text: str) -> VerifyResult:
        def result(outcome: str, reason: str, similarity: float | None) -> VerifyResult:
            return VerifyResult(outcome=outcome, reason=reason,
                                allowed=(outcome == "ACCEPT"), retry=(outcome == "RETRY"),
                                band=band_for(similarity, _THRESHOLD), similarity=similarity,
                                threshold=_THRESHOLD, policy_version=7, raw={"fake": True})

        parts = (qr_text or "").split(".")
        if len(parts) != 3 or parts[0] != _PREFIX:
            return result("RETRY", "DECODE_FAILED", None)   # as the live service answered
        _, token, credential_id = parts
        if credential_id in self._revoked:
            return result("DENY", "CREDENTIAL_REVOKED", None)
        issued = self._issued.get(credential_id)
        if issued and issued["expires_at"] < time.time():
            return result("DENY", "CREDENTIAL_EXPIRED", None)
        if _digest(image) != token:
            return result("DENY", "FACE_MISMATCH", 0.0)
        return result("ACCEPT", "MATCH", 1.0)

    # ---- credential plane ----------------------------------------------------------

    def issue_credential(self, *, evidence: EnrolmentEvidence, digest: str | None = None,
                         **extra: Any) -> dict[str, Any]:
        body = evidence.to_dict()
        if not body.get("quality_pass"):
            raise BioVerifyError("BioVerify /credentials/issue HTTP 422: enrolment evidence "
                                 "does not show quality_pass")
        if not body.get("pad_pass"):
            raise BioVerifyError("BioVerify /credentials/issue HTTP 422: enrolment evidence "
                                 "does not show pad_pass")
        if "deepfake_pass" not in body:
            raise BioVerifyError("BioVerify /credentials/issue HTTP 422: enrolment evidence "
                                 "omits deepfake_pass")
        token = (digest or hashlib.sha256(repr(sorted(body.items())).encode()).hexdigest())
        credential_id = token[:32]
        self._issued[credential_id] = {"token": token, "expires_at": int(time.time()) + 2592000}
        return {"credential_id": credential_id, "status": "active"}

    def credential_status(self, *, credential_id: str) -> dict[str, Any]:
        if credential_id in self._revoked:
            return {"credential_id": credential_id, "status": "revoked"}
        if credential_id not in self._issued:
            raise BioVerifyError("BioVerify /credentials/status HTTP 404: unknown credential")
        return {"credential_id": credential_id, "status": "active"}

    def revoke_credential(self, *, credential_id: str) -> dict[str, Any]:
        self._revoked.add(credential_id)
        return {"credential_id": credential_id, "status": "revoked"}

    def revocations_sync(self, *, tenant: str | None = None,
                         since: int | None = None) -> dict[str, Any]:
        now = int(time.time())
        return {"tenant_id": tenant or "", "generated_at": now, "valid_until": now + 3600,
                "full": True, "revoked": sorted(self._revoked), "signature": None,
                "warning": "unsigned; spec 6.4 requires a signed list"}
