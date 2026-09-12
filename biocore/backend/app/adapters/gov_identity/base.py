"""Government identity provider adapter.

BIOCORE_COMPLETE_CHANGE_SPEC §19.1 — isolates provider-specific formats (Aadhaar eKYC,
DigiLocker, PAN, passport, or a KYC vendor) from the platform. The Identity Proofing
Service calls ONLY this interface. The raw response and government photo are **temporary**
(§5.5, §5.10): the adapter returns an allowlisted set of minimal claims plus a short-lived
photo, and the service deletes the photo/raw material once verification completes.

Non-negotiable: no full government response, government photo, or plain government ID is
persisted or logged (§5.5, §14.1, §29.3).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol


class GovernmentIdentityError(Exception):
    def __init__(self, message: str, category: str = "system_error"):
        self.category = category
        super().__init__(message)


@dataclass
class GovSession:
    provider: str
    session_ref: str


@dataclass
class VerifiedClaims:
    """The ONLY things retained (§5.5 "retained minimal verified claims") — never the raw
    payload, photo or plain ID number."""
    identity_verified: bool
    name_verified: bool
    document_valid: bool
    age_over_18: bool
    assurance_level: str
    verification_reference_hash: str
    extra: dict = field(default_factory=dict)


@dataclass
class GovResult:
    claims: VerifiedClaims
    # temporary government photo bytes — used only during the transaction, then deleted.
    government_photo: bytes | None


class GovernmentIdentityProvider(Protocol):
    """§19.1 adapter contract. `fetch_verified_data` orchestrates validate → extract-claims →
    extract-photo so provider-specific formats never leak past this boundary."""
    def create_session(self, *, tenant_id: str, subject_ref: str, purpose: str) -> GovSession: ...
    def fetch_verified_data(self, *, session: GovSession, credential: dict) -> GovResult: ...
    def validate_response(self, *, raw: dict) -> bool: ...
    def extract_allowed_claims(self, *, raw: dict, context: dict) -> VerifiedClaims: ...
    def extract_temporary_photo(self, *, raw: dict) -> bytes | None: ...
    def revoke_or_close_session(self, *, session: GovSession) -> None: ...
