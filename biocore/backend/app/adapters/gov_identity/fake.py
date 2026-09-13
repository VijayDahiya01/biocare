"""In-process FAKE government identity provider — local DEV ONLY (FAKE_GOV_IDENTITY=true).

Returns deterministic verified claims plus a placeholder photo so the identity-proofing
flow can be built and clicked through without a real KYC API. FORBIDDEN in production and
in any real pilot / customer demo claiming real verification (§3.2, §29.18).
"""
from __future__ import annotations

import hashlib
import uuid

from app.adapters.gov_identity.base import (
    GovernmentIdentityError,
    GovResult,
    GovSession,
    VerifiedClaims,
)
from app.core.name_match import compare_names


class FakeGovernmentProvider:
    provider = "fake_gov"

    def create_session(self, *, tenant_id: str, subject_ref: str, purpose: str) -> GovSession:
        return GovSession(provider=self.provider, session_ref=str(uuid.uuid4()))

    def fetch_verified_data(self, *, session: GovSession, credential: dict) -> GovResult:
        # §19.1 orchestration: validate → extract claims → extract temporary photo
        raw = {"reference": str(credential.get("reference") or credential.get("id") or "dev"),
               "session_ref": session.session_ref, "ok": True}
        if not self.validate_response(raw=raw):
            raise GovernmentIdentityError("Fake provider returned an invalid response.", "provider_error")
        claims = self.extract_allowed_claims(raw=raw, context=credential)
        return GovResult(claims=claims, government_photo=self.extract_temporary_photo(raw=raw))

    def validate_response(self, *, raw: dict) -> bool:
        return bool(raw.get("ok"))

    def extract_allowed_claims(self, *, raw: dict, context: dict) -> VerifiedClaims:
        ref_hash = hashlib.sha256(f"{raw.get('session_ref')}:{raw.get('reference')}".encode()).hexdigest()
        # Mirror the real provider: compare the name we hold against the one the record
        # returns. A fake that always says "name verified" would make a broken comparison
        # look correct in every test.
        expected = str(context.get("expected_name") or "").strip()
        official = str(context.get("fake_government_name") or expected)
        if expected:
            verdict = compare_names(expected, official)
            name_ok, name_reason = verdict.matched, verdict.reason
        else:
            name_ok, name_reason = False, "no name on file to compare against"
        return VerifiedClaims(
            identity_verified=True, name_verified=name_ok, document_valid=True,
            age_over_18=True, assurance_level="fake_dev", verification_reference_hash=ref_hash,
            extra={"name_match_reason": name_reason},
        )

    def extract_temporary_photo(self, *, raw: dict) -> bytes | None:
        # A real provider returns the actual government face here; the fake returns a marker.
        return b"FAKE_GOV_PHOTO"

    def revoke_or_close_session(self, *, session: GovSession) -> None:
        return None
