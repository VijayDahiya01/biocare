"""Face engine adapter (BIOCORE_COMPLETE_CHANGE_SPEC §15.1).

Isolates the biometric engine (embedding, liveness/PAD, 1:1 compare) behind ONE interface so
the business logic never depends on which engine runs. Dev uses a deterministic fake; the real
engine (e.g. ZepIris behind an HTTP shim) is wired via config with NO business-logic change —
the same isolation pattern as the government adapter (§19.1) and the KMS provider (§6.5).

Plaintext images and embeddings passed through here are short-lived matcher values — never
logged or persisted (§7.5, §14.1).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


class FaceEngineError(Exception):
    pass


@dataclass
class LivenessResult:
    passed: bool
    detail: str = ""


@dataclass
class MatchResult:
    matched: bool
    band: str            # "high" | "medium" | "low" | "none" — a band, never an exact score (§7.5)
    score: float | None = None


class FaceEngine(Protocol):
    name: str
    def embed(self, *, image: str) -> bytes: ...
    def assess_liveness(self, *, image: str) -> LivenessResult: ...
    def compare(self, *, stored: bytes, live: bytes) -> MatchResult: ...
