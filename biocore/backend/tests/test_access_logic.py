"""Unit tests for pure access-control logic (zones, badges, time windows)."""
from datetime import date, datetime

from app.services.access_logic import (
    BadgeView,
    ZoneView,
    evaluate_access,
    within_windows,
)

# Mon 2026-06-15 14:00
AFTERNOON = datetime(2026, 6, 15, 14, 0)
NIGHT = datetime(2026, 6, 15, 23, 0)
EARLY = datetime(2026, 6, 15, 3, 0)


def test_within_windows_empty_is_always():
    assert within_windows([], AFTERNOON) is True


def test_within_windows_simple_range():
    w = [{"from": "08:00", "to": "20:00"}]
    assert within_windows(w, AFTERNOON) is True
    assert within_windows(w, NIGHT) is False


def test_within_windows_crosses_midnight():
    w = [{"from": "20:00", "to": "06:00"}]  # night shift
    assert within_windows(w, NIGHT) is True
    assert within_windows(w, EARLY) is True
    assert within_windows(w, AFTERNOON) is False


def test_within_windows_day_filter():
    w = [{"from": "00:00", "to": "23:59", "days": [5, 6]}]  # weekend only
    assert within_windows(w, AFTERNOON) is False  # Monday


def test_open_zone_always_granted():
    zone = ZoneView(zone_id="z1", type="entry_exit")
    granted, reason = evaluate_access(zone, [], AFTERNOON)
    assert granted and reason == "open_zone"


def test_restricted_zone_no_badge_denied():
    zone = ZoneView(zone_id="z1", type="restricted")
    granted, reason = evaluate_access(zone, [], AFTERNOON)
    assert not granted and reason == "no_badge"


def test_restricted_zone_with_matching_badge_granted():
    zone = ZoneView(zone_id="z1", type="restricted")
    badge = BadgeView(badge_id="b1", zones={"z1"})
    granted, reason = evaluate_access(zone, [badge], AFTERNOON)
    assert granted and reason == "badge_ok"


def test_zone_time_gate_blocks_outside_hours():
    zone = ZoneView(zone_id="z1", type="restricted", time_windows=[{"from": "08:00", "to": "20:00"}])
    badge = BadgeView(badge_id="b1", zones={"z1"})
    granted, reason = evaluate_access(zone, [badge], NIGHT)
    assert not granted and reason == "outside_hours"


def test_expired_badge_denied():
    zone = ZoneView(zone_id="z1", type="restricted")
    badge = BadgeView(badge_id="b1", zones={"z1"}, expiry=date(2026, 1, 1))
    granted, reason = evaluate_access(zone, [badge], AFTERNOON)
    assert not granted and reason == "badge_expired_or_outside_hours"


def test_allowed_badges_list_enforced():
    # zone only admits badge "vip"; holder has "staff" granting the zone
    zone = ZoneView(zone_id="z1", type="restricted", allowed_badges=["vip"])
    staff = BadgeView(badge_id="staff", zones={"z1"})
    assert evaluate_access(zone, [staff], AFTERNOON)[0] is False
    vip = BadgeView(badge_id="vip", zones={"z1"})
    assert evaluate_access(zone, [vip], AFTERNOON)[0] is True
