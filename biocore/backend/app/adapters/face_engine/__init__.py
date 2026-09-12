"""Face engine factory (BIOCORE_COMPLETE_CHANGE_SPEC §15.1)."""
from functools import lru_cache

from app.adapters.face_engine.base import (
    FaceEngine,
    FaceEngineError,
    LivenessResult,
    MatchResult,
)
from app.core.config import settings


@lru_cache
def get_face_engine() -> FaceEngine:
    engine = (settings.face_engine or "").strip().lower()
    # An explicit real engine wins — so the new verified-identity flow can use a real engine
    # even while FAKE_ZEPIRIS stays on for the legacy face path.
    if engine in ("remote", "zepiris", "http"):
        from app.adapters.face_engine.remote import RemoteFaceEngine
        return RemoteFaceEngine()
    # Dev fake: explicit FACE_ENGINE=fake, or the legacy FAKE_ZEPIRIS / FAKE_GOV_IDENTITY flags.
    if engine == "fake" or settings.fake_zepiris or settings.fake_gov_identity:
        if settings.is_production:
            raise FaceEngineError(
                "Fake face engine is forbidden in production. Wire a real engine "
                "(FACE_ENGINE=remote + FACE_ENGINE_URL) and set FAKE_ZEPIRIS=false.")
        from app.adapters.face_engine.fake import FakeFaceEngine
        return FakeFaceEngine()
    raise FaceEngineError(
        f"No face engine wired for '{settings.face_engine}'. Set FAKE_ZEPIRIS=true for dev, or "
        "FACE_ENGINE=remote + FACE_ENGINE_URL for a real engine.")


__all__ = ["get_face_engine", "FaceEngine", "FaceEngineError", "LivenessResult", "MatchResult"]
