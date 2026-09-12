"""In-memory FAKE business connectors — DEV ONLY (settings.fake_connectors).

Deterministic roster + an in-memory event sink so the §19.2 sync flows are buildable and
testable without any real vendor API. FORBIDDEN in production (the factory blocks it).
"""
from __future__ import annotations

from app.adapters.connectors.base import EntryEventRecord, SubjectRecord


class FakeRosterSource:
    def __init__(self, kind: str) -> None:
        self.kind = kind

    def fetch_roster(self, *, config: dict) -> list[SubjectRecord]:
        # A real source calls the vendor API; the fake returns a deterministic demo roster.
        n = int(config.get("count", 3))
        prefix = str(config.get("prefix") or self.kind.upper())
        subject_type = str(config.get("subject_type", "member"))
        return [
            SubjectRecord(external_reference=f"{prefix}-{i:03d}",
                          display_name=f"{prefix} Person {i}", subject_type=subject_type)
            for i in range(1, n + 1)
        ]


class FakeEventSink:
    sent: list[dict] = []  # in-memory audit of what was pushed (dev only)

    def __init__(self, kind: str) -> None:
        self.kind = kind

    def push_events(self, *, config: dict, events: list[EntryEventRecord]) -> int:
        FakeEventSink.sent.extend(
            {"kind": self.kind, "ref": e.external_reference, "decision": e.decision} for e in events)
        return len(events)
