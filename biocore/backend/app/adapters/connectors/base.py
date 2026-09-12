"""Business integration connectors (BIOCORE_COMPLETE_CHANGE_SPEC §19.2).

Provider-agnostic contracts so external systems plug in WITHOUT touching business logic — the
same isolation pattern as the government adapter (§19.1). Two directions:

  * RosterSource — INBOUND: pull the authorized roster from the source of truth (ticketing,
    SIS, ERP, HRMS, PMS, visitor mgmt) into tenant subjects (additively; verification/consent
    still happen per person before any credential).
  * EventSink    — OUTBOUND: push entry/attendance events to an external system (controllers,
    HRMS, notifications). Only minimal event metadata leaves — never a biometric payload.

A `kind` selects the connector; its per-tenant config lives on the Integration row. Dev uses
in-memory fakes; real per-vendor connectors implement these Protocols and register in the
factory once their access is provisioned.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol


class ConnectorError(Exception):
    pass


@dataclass
class SubjectRecord:
    """An inbound roster record — who should be authorized (not yet verified)."""
    external_reference: str
    display_name: str | None = None
    subject_type: str = "member"
    valid_from: str | None = None
    valid_until: str | None = None
    metadata: dict = field(default_factory=dict)


@dataclass
class EntryEventRecord:
    """An outbound entry/attendance event — minimal metadata only, never biometric (§7.5)."""
    external_reference: str | None
    decision: str
    reason: str
    at: str
    gate_id: str | None = None


class RosterSource(Protocol):
    kind: str
    def fetch_roster(self, *, config: dict) -> list[SubjectRecord]: ...


class EventSink(Protocol):
    kind: str
    def push_events(self, *, config: dict, events: list[EntryEventRecord]) -> int: ...


# §19.2 catalog — kind -> {label, capabilities}. capability "roster" = inbound, "events" = outbound.
CONNECTOR_CATALOG: dict[str, dict] = {
    "event_ticketing":    {"label": "Event ticketing & registration", "capabilities": ["roster", "events"]},
    "school_sis":         {"label": "School SIS",                      "capabilities": ["roster"]},
    "college_erp":        {"label": "College ERP",                     "capabilities": ["roster"]},
    "hrms_payroll":       {"label": "HRMS & payroll",                  "capabilities": ["roster", "events"]},
    "hotel_pms":          {"label": "Hotel PMS",                       "capabilities": ["roster", "events"]},
    "visitor_management": {"label": "Visitor management",              "capabilities": ["roster", "events"]},
    "access_controller":  {"label": "Door/turnstile controller",      "capabilities": ["events"]},
    "notifications":      {"label": "SMS / email / WhatsApp",          "capabilities": ["events"]},
}
