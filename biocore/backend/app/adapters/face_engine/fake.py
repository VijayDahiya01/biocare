"""In-process FAKE face engine — DEV ONLY (FAKE_ZEPIRIS / FACE_ENGINE=fake).

Deterministic, L2-normalized pseudo-embedding derived from the image, so BOTH the 1:1 match
and the 1:N walk-up (cosine) paths behave sensibly without the real engine: the same image
matches itself, different images don't. FORBIDDEN in production (the factory blocks it); it is
never a real biometric and must never gate real access (§3.2, §29.18).
"""
from __future__ import annotations

import hashlib

import numpy as np

from app.adapters.face_engine.base import LivenessResult, MatchResult

_DIM = 128


class FakeFaceEngine:
    name = "fake"

    def embed(self, *, image: str) -> bytes:
        seed = int.from_bytes(hashlib.sha256((image or "dev").encode()).digest()[:8], "little")
        v = np.random.default_rng(seed).standard_normal(_DIM).astype("float32")
        v /= (np.linalg.norm(v) + 1e-9)   # normalized -> cosine of same image == 1.0
        return v.tobytes()

    def assess_liveness(self, *, image: str) -> LivenessResult:
        return LivenessResult(passed=True, detail="fake_pass")

    def compare(self, *, stored: bytes, live: bytes) -> MatchResult:
        a = np.frombuffer(stored, dtype=np.float32)
        b = np.frombuffer(live, dtype=np.float32)
        if a.size == 0 or a.size != b.size:
            return MatchResult(matched=False, band="none", score=0.0)
        cos = float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b) + 1e-9))
        return MatchResult(matched=cos >= 0.9, band=("high" if cos >= 0.9 else "none"), score=cos)
