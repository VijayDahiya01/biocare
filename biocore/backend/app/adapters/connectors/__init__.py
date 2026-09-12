"""Business connector factory (BIOCORE_COMPLETE_CHANGE_SPEC §19.2)."""
from app.adapters.connectors.base import (
    CONNECTOR_CATALOG,
    ConnectorError,
    EntryEventRecord,
    EventSink,
    RosterSource,
    SubjectRecord,
)
from app.core.config import settings


def _supported(kind: str, capability: str) -> None:
    meta = CONNECTOR_CATALOG.get(kind)
    if not meta:
        raise ConnectorError(f"Unknown connector kind: {kind}")
    if capability not in meta["capabilities"]:
        raise ConnectorError(f"Connector '{kind}' does not support '{capability}'.")


def get_roster_source(kind: str) -> RosterSource:
    _supported(kind, "roster")
    if settings.fake_connectors:
        from app.adapters.connectors.fake import FakeRosterSource
        return FakeRosterSource(kind)
    raise ConnectorError(
        f"No real roster connector wired for '{kind}'. Set FAKE_CONNECTORS=true for dev, or "
        "implement a RosterSource.")


def get_event_sink(kind: str) -> EventSink:
    _supported(kind, "events")
    if settings.fake_connectors:
        from app.adapters.connectors.fake import FakeEventSink
        return FakeEventSink(kind)
    raise ConnectorError(
        f"No real event connector wired for '{kind}'. Set FAKE_CONNECTORS=true for dev, or "
        "implement an EventSink.")


__all__ = [
    "CONNECTOR_CATALOG", "ConnectorError", "EntryEventRecord", "EventSink", "RosterSource",
    "SubjectRecord", "get_roster_source", "get_event_sink",
]
