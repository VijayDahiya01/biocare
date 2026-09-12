"""Government identity provider factory (BIOCORE_COMPLETE_CHANGE_SPEC §19.1)."""
from functools import lru_cache

from app.adapters.gov_identity.base import (
    GovernmentIdentityError,
    GovernmentIdentityProvider,
    GovResult,
    GovSession,
    VerifiedClaims,
)
from app.core.config import settings


@lru_cache
def get_gov_identity() -> GovernmentIdentityProvider:
    if settings.fake_gov_identity:
        # The fake provider is DEV ONLY — forbidden in production / real pilots (§29.18).
        if settings.is_production:
            raise GovernmentIdentityError(
                "Fake government provider is forbidden in production. Wire a real provider "
                "and set FAKE_GOV_IDENTITY=false.",
                category="system_error",
            )
        from app.adapters.gov_identity.fake import FakeGovernmentProvider
        return FakeGovernmentProvider()
    provider = (settings.gov_identity_provider or "").strip().lower()
    if provider == "sandbox":
        # Sandbox (api.sandbox.co.in) — real vendor KYC API (PAN verify + Aadhaar OKYC).
        from app.adapters.gov_identity.sandbox import SandboxGovernmentProvider
        return SandboxGovernmentProvider()
    # Other real providers (aadhaar | digilocker | vendor …) implement
    # GovernmentIdentityProvider and wire in here once their production access is chosen.
    raise GovernmentIdentityError(
        f"No real government identity provider wired for '{settings.gov_identity_provider}'. "
        "Set FAKE_GOV_IDENTITY=true for dev, GOV_IDENTITY_PROVIDER=sandbox for the Sandbox "
        "KYC API, or implement a provider.",
        category="system_error",
    )


__all__ = [
    "get_gov_identity",
    "GovernmentIdentityProvider",
    "GovernmentIdentityError",
    "GovSession",
    "GovResult",
    "VerifiedClaims",
]
