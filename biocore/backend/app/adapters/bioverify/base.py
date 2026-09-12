"""BioVerify credential adapter — contract (BIOCORE_COMPLETE_CHANGE_SPEC §15.1).

BioVerify owns the WHOLE credential lifecycle. It enrols a face, seals and issues a scannable
credential, and decides the 1:1 verification at the gate. BioCore stores the `credential_id`
(so revoke/status have something to address) and the `qr_text` (so the credential can be
re-shown), and holds no template for these subjects.

This is a DIFFERENT shape from `app.adapters.face_engine` (embed/assess_liveness/compare):
there is no embedding to hold and no comparison to run locally, so the two cannot share one
Protocol. `BioVerifyError` subclasses `FaceEngineError` so existing call sites that already map
that to a clean 503 keep working unchanged.

Images and `qr_text` passing through here are short-lived credential material — never logged,
never placed in an audit payload (§7.5, §14.1). `VerifyResult.similarity` is a matcher-boundary
value: persist the `band`, never the score (§7.5).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol

from app.adapters.face_engine.base import FaceEngineError


class BioVerifyError(FaceEngineError):
    """Any BioVerify failure — unreachable, refused, or an unusable response.

    Subclasses FaceEngineError deliberately: `face_credentials._embed` and
    `entry_service._engine` already turn that into 503 FACE_ENGINE_UNAVAILABLE, so both mint
    and match keep failing CLOSED without touching those call sites (§15.1, §22.6).
    """


class BioVerifyRefused(BioVerifyError):
    """The service worked and declined this particular capture (its own quality gate).

    Kept distinct from "the service is unreachable" because the two need opposite things from
    the person in front of the camera: a refusal means try again with better light or framing,
    while an outage means nothing they do will help. Reporting both the same way sends people
    into a retry loop over a problem that is not theirs.
    """

    def __init__(self, message: str, *, reason: str = "", retryable: bool = True) -> None:
        super().__init__(message)
        self.reason = reason
        self.retryable = retryable


# Verify outcomes. OBSERVED against the live service: `RETRY` (an undecodable credential) and
# `BLOCK` (a refused verification). The accept token is not yet confirmed, so the plausible
# spellings are all accepted; anything unrecognised is a DENY, never an allow (§22.6).
_ALLOW_OUTCOMES = frozenset({"ACCEPT", "ACCEPTED", "ALLOW", "ALLOWED", "MATCH", "MATCHED",
                             "PASS", "PASSED", "OK", "SUCCESS", "VERIFIED"})
_RETRY_OUTCOMES = frozenset({"RETRY", "RETRYABLE", "TRY_AGAIN"})
_DENY_OUTCOMES = frozenset({"BLOCK", "BLOCKED", "DENY", "DENIED", "REJECT", "REJECTED", "FAIL"})


def classify_outcome(outcome: str) -> tuple[bool, bool]:
    """Map a service outcome to (allowed, retry). Unknown → (False, False): fail closed."""
    token = (outcome or "").strip().upper()
    return token in _ALLOW_OUTCOMES, token in _RETRY_OUTCOMES


def is_known_outcome(outcome: str) -> bool:
    """Whether the service said something we recognise.

    An unrecognised outcome still denies, but it means the service has changed its vocabulary
    and every gate is now failing closed on a word we do not understand — worth alerting on
    rather than silently refusing people.
    """
    token = (outcome or "").strip().upper()
    return token in _ALLOW_OUTCOMES or token in _RETRY_OUTCOMES or token in _DENY_OUTCOMES


def band_for(similarity: float | None, threshold: float | None) -> str:
    """Bucket a similarity into the §7.5 band. Mirrors RemoteFaceEngine.compare so the two
    engines report bands on the same scale."""
    if similarity is None:
        return "none"
    cut = threshold if threshold is not None else 0.0
    if similarity >= 0.8:
        return "high"
    return "medium" if similarity >= cut else "none"


@dataclass
class EnrolmentEvidence:
    """Evidence for the digest mint path (`/credentials/issue`, spec 6.1).

    `deepfake_pass` is emitted even when it is None. The service requires the key to be present
    whether or not the check ran, "so that 'not checked' is recorded and not merely absent" —
    an absent key and a failed check must never look alike.
    """
    quality_pass: bool
    pad_pass: bool
    deepfake_pass: bool | None = None
    liveness_pass: bool | None = None
    extra: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        body: dict[str, Any] = {
            "quality_pass": bool(self.quality_pass),
            "pad_pass": bool(self.pad_pass),
            "deepfake_pass": self.deepfake_pass,     # always present, may be null
        }
        if self.liveness_pass is not None:
            body["liveness_pass"] = bool(self.liveness_pass)
        body.update(self.extra)
        return body


@dataclass
class EnrolResult:
    """What BioCore persists after an enrol. `qr_text` IS the credential — treat it as
    sensitive at rest and never log it."""
    qr_text: str
    credential_id: str | None = None
    qr_png_b64: str | None = None
    expires_at: str | None = None
    document_match: dict[str, Any] | None = None
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass
class VerifyResult:
    outcome: str                      # the service's own token, upper-cased
    reason: str
    allowed: bool
    retry: bool                       # distinct from deny: ask the subject to present again
    band: str                         # persist THIS (§7.5)
    similarity: float | None = None   # matcher-boundary only — never persisted or logged
    threshold: float | None = None
    policy_version: Any = None
    raw: dict[str, Any] = field(default_factory=dict)


class BioVerifyEngine(Protocol):
    """All nine routes of the BioVerify API."""
    name: str

    def health(self) -> dict[str, Any]: ...
    def policy_manifest(self) -> dict[str, Any]: ...

    # Whole-flow routes — the onboarding and gate paths BioCore uses.
    def enrol(self, *, image: str, expires_in_s: int, qr_scale: int | None = None) -> EnrolResult: ...
    def enrol_with_document(self, *, live: str, document: str, expires_in_s: int,
                            document_type: str = "PASSPORT",
                            qr_scale: int | None = None) -> EnrolResult: ...
    def verify(self, *, image: str, qr_text: str) -> VerifyResult: ...

    # Digest routes — the credential plane (used directly once an on-device SDK exists).
    def issue_credential(self, *, evidence: EnrolmentEvidence, digest: str | None = None,
                         **extra: Any) -> dict[str, Any]: ...
    def credential_status(self, *, credential_id: str) -> dict[str, Any]: ...
    def revoke_credential(self, *, credential_id: str) -> dict[str, Any]: ...
    def revocations_sync(self, *, tenant: str | None = None,
                         since: int | None = None) -> dict[str, Any]: ...


__all__ = ["BioVerifyEngine", "BioVerifyError", "EnrolResult", "EnrolmentEvidence",
           "VerifyResult", "band_for", "classify_outcome"]
