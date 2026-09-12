"""Face engine adapter (§15.1): fake behaviour + config-switchable factory + fail-closed guard.

Pure unit tests — no stack required.
"""
import pytest

from app.adapters.face_engine import FaceEngineError, get_face_engine
from app.adapters.face_engine.fake import FakeFaceEngine
from app.core.config import settings


def test_fake_engine_behaviour():
    e = FakeFaceEngine()
    v1 = e.embed(image="face-A")
    assert v1 == e.embed(image="face-A") and e.embed(image="other") != v1   # deterministic
    assert e.assess_liveness(image="x").passed
    assert e.compare(stored=v1, live=v1).matched                            # exact match
    miss = e.compare(stored=v1, live=e.embed(image="other"))
    assert not miss.matched and miss.band == "none"


def test_factory_returns_fake_in_dev():
    get_face_engine.cache_clear()
    assert get_face_engine().name == "fake"     # test env: FAKE_GOV_IDENTITY=true


def test_fake_forbidden_in_production(monkeypatch):
    monkeypatch.setattr(settings, "environment", "production")
    get_face_engine.cache_clear()
    try:
        with pytest.raises(FaceEngineError):
            get_face_engine()
    finally:
        get_face_engine.cache_clear()           # restore dev engine for later tests


def test_remote_engine_requires_url(monkeypatch):
    monkeypatch.setattr(settings, "fake_zepiris", False)
    monkeypatch.setattr(settings, "fake_gov_identity", False)
    monkeypatch.setattr(settings, "face_engine", "remote")
    monkeypatch.setattr(settings, "face_engine_url", "")
    get_face_engine.cache_clear()
    try:
        with pytest.raises(FaceEngineError):
            get_face_engine()                    # remote selected but no URL -> fails closed
    finally:
        get_face_engine.cache_clear()
