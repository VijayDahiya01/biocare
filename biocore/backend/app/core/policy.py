"""Consent purposes, verification outcomes, entry reason codes and policy profiles.

BIOCORE_COMPLETE_CHANGE_SPEC §5.3 (separate consent purposes), §5.8 (verification
outcomes), §15.4 (stable gate reason codes) and §24 (named policy profiles).
"""
from __future__ import annotations

import enum


class ConsentPurpose(str, enum.Enum):
    """Separate, purpose-bound consents (§5.3). The user must not be forced to accept
    marketing (or cross-tenant reuse) to obtain entry (§5.3, §13.2)."""
    IDENTITY_VERIFICATION = "identity_verification"
    GOVERNMENT_DATA_PROCESSING = "government_data_processing"
    LIVE_FACE_CAPTURE = "live_face_capture"
    FACE_TO_GOVERNMENT_MATCH = "face_to_government_match"
    ENTRY_TEMPLATE_CREATION = "entry_template_creation"
    ENTRY_AUTHENTICATION = "entry_authentication"
    CROSS_TENANT_REUSE = "cross_tenant_reuse"   # optional, disabled by default
    MARKETING = "marketing"                     # optional, always separable


# consent that must be on record BEFORE the corresponding collection/processing (§5.3, §13.1)
CONSENT_BEFORE_CAPTURE = (
    ConsentPurpose.IDENTITY_VERIFICATION,
    ConsentPurpose.GOVERNMENT_DATA_PROCESSING,
    ConsentPurpose.LIVE_FACE_CAPTURE,
    ConsentPurpose.FACE_TO_GOVERNMENT_MATCH,
    ConsentPurpose.ENTRY_TEMPLATE_CREATION,
)


class VerificationOutcome(str, enum.Enum):
    """1:1 live-face-to-government-face comparison outcomes (§5.8). Internal thresholds/
    fraud rules must NOT be exposed to the end user (§5.8)."""
    VERIFIED = "verified"
    RETRY_REQUIRED = "retry_required"
    MANUAL_REVIEW_REQUIRED = "manual_review_required"
    GOVERNMENT_PHOTO_UNUSABLE = "government_photo_unusable"
    LIVENESS_FAILED = "liveness_failed"
    FACE_MISMATCH = "face_mismatch"
    MULTIPLE_FACES = "multiple_faces"
    QUALITY_FAILED = "quality_failed"
    SYSTEM_ERROR = "system_error"


class EntryReason(str, enum.Enum):
    """Stable gate reason codes (§15.4). A face match alone never grants entry — the
    authorization plane must also allow it (§4.5, §7.3, §29.11)."""
    ALLOWED = "ALLOWED"
    NO_FACE = "NO_FACE"
    MULTIPLE_FACES = "MULTIPLE_FACES"
    QUALITY_FAILED = "QUALITY_FAILED"
    LIVENESS_FAILED = "LIVENESS_FAILED"
    FACE_MISMATCH = "FACE_MISMATCH"
    AMBIGUOUS_MATCH = "AMBIGUOUS_MATCH"
    CREDENTIAL_EXPIRED = "CREDENTIAL_EXPIRED"
    CONSENT_WITHDRAWN = "CONSENT_WITHDRAWN"
    ACCESS_NOT_ALLOWED = "ACCESS_NOT_ALLOWED"
    DEVICE_NOT_TRUSTED = "DEVICE_NOT_TRUSTED"
    MATCH_ENGINE_UNAVAILABLE = "MATCH_ENGINE_UNAVAILABLE"


# Named tenant policy profiles (§24). Each vertical/purpose selects one; thresholds and
# model versions attach to the matching policy, not casual per-customer edits (§15.3).
POLICY_PROFILES: dict[str, dict] = {
    "basic_attendance":         {"government_verification": False, "gate_mode": "1:1", "liveness": "standard"},
    "standard_entry":           {"government_verification": False, "gate_mode": "1:1", "liveness": "standard"},
    "government_verified_entry": {"government_verification": True,  "gate_mode": "1:1", "liveness": "strong"},
    "high_security_entry":      {"government_verification": True,  "gate_mode": "1:1", "liveness": "strong", "ambiguity_margin": 0.10},
    "minor_guardian_entry":     {"government_verification": False, "gate_mode": "1:1", "guardian_consent": True},
    "temporary_event_entry":    {"government_verification": False, "gate_mode": "1:N", "auto_expire": True},
    "hotel_guest_entry":        {"government_verification": True,  "gate_mode": "1:1", "revoke_on_checkout": True},
}
