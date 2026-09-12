"""Unit tests for zone-movement analysis."""
from datetime import datetime

from app.services.movement_logic import analyze_movement


def _e(zone, et, h, m=0, s=0):
    return (zone, et, datetime(2026, 6, 15, h, m, s))


def test_trail_and_dwell():
    events = [_e("gate", "check_in", 9), _e("floor", "check_in", 10), _e("gate", "check_out", 12)]
    out = analyze_movement(events, restricted_zones=set())
    assert [t["zone_id"] for t in out["trail"]] == ["gate", "floor", "gate"]
    # gate->floor was 1h (3600s); floor->gate was 2h (7200s)
    assert out["dwell_seconds_by_zone"]["gate"] == 3600
    assert out["dwell_seconds_by_zone"]["floor"] == 7200


def test_restricted_before_entry_flagged():
    events = [_e("vault", "check_in", 9)]
    out = analyze_movement(events, restricted_zones={"vault"})
    assert any(a["type"] == "restricted_before_entry" for a in out["anomalies"])


def test_no_anomaly_when_entry_first():
    events = [_e("gate", "check_in", 9), _e("vault", "check_in", 10)]
    out = analyze_movement(events, restricted_zones={"vault"})
    assert not any(a["type"] == "restricted_before_entry" for a in out["anomalies"])


def test_rapid_transition_flagged():
    events = [_e("gate", "check_in", 9, 0, 0), _e("vault", "check_in", 9, 0, 5)]
    out = analyze_movement(events, restricted_zones={"vault"}, rapid_seconds=20)
    rapid = [a for a in out["anomalies"] if a["type"] == "rapid_transition"]
    assert rapid and rapid[0]["from"] == "gate" and rapid[0]["to"] == "vault"


def test_events_without_zone_ignored():
    events = [(None, "check_in", datetime(2026, 6, 15, 9))]
    out = analyze_movement(events, restricted_zones=set())
    assert out["trail"] == []
