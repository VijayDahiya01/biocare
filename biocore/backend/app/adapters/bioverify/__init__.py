"""BioVerify adapter factory (BIOCORE_COMPLETE_CHANGE_SPEC §15.1).

Config-switchable exactly like `app.adapters.face_engine`: an explicitly configured real
service wins, the dev fake is used otherwise, and the fake is forbidden in production so both
mint and match fail CLOSED rather than quietly accepting a stand-in (§22.6).
"""
from functools import lru_cache

from app.adapters.bioverify.base import (
    BioVerifyEngine,
    BioVerifyError,
    EnrolmentEvidence,
    EnrolResult,
    VerifyResult,
)
from app.core.config import settings


@lru_cache
def get_bioverify() -> BioVerifyEngine:
    if settings.bioverify_url.strip() and not settings.fake_bioverify:
        from app.adapters.bioverify.client import BioVerifyClient
        return BioVerifyClient()
    if settings.fake_bioverify or settings.fake_zepiris or settings.fake_gov_identity:
        if settings.is_production:
            raise BioVerifyError(
                "Fake BioVerify is forbidden in production. Set BIOVERIFY_URL + "
                "BIOVERIFY_API_KEY and FAKE_BIOVERIFY=false.")
        from app.adapters.bioverify.fake import FakeBioVerify
        return FakeBioVerify()
    raise BioVerifyError(
        "No BioVerify service wired. Set BIOVERIFY_URL + BIOVERIFY_API_KEY for the real "
        "service, or FAKE_BIOVERIFY=true for dev.")


__all__ = ["get_bioverify", "BioVerifyEngine", "BioVerifyError", "EnrolResult",
           "EnrolmentEvidence", "VerifyResult"]
