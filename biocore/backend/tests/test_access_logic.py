"""Unit tests for pure access-control logic (zones, badges, time windows)."""
from datetime import date, datetime

from app.services.access_logic import (
    BadgeView,
    ZoneView,
    describe_hours,
    describe_windows,
    evaluate_access,
    explain_access,
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


# --- explaining the same decision to the person whose face it is -------------------------

def test_describe_windows_plain_range():
    assert describe_windows([]) == "Any time"
    assert describe_windows([{"from": "08:00", "to": "20:00"}]) == "08:00-20:00"


def test_describe_windows_collapses_a_run_of_days():
    assert describe_windows([{"from": "09:00", "to": "18:00", "days": [0, 1, 2, 3, 4]}]) \
        == "Mon-Fri 09:00-18:00"
    assert describe_windows([{"from": "09:00", "to": "18:00", "days": [0, 2, 4]}]) \
        == "Mon, Wed, Fri 09:00-18:00"
    # every day is no restriction worth naming
    assert describe_windows([{"from": "09:00", "to": "18:00",
                              "days": [0, 1, 2, 3, 4, 5, 6]}]) == "09:00-18:00"


def test_hours_are_an_intersection_not_a_union():
    # Two window sets that both have to hold cannot be concatenated — a list reads as "any of".
    text = describe_hours([{"from": "08:00", "to": "20:00"}], [{"from": "09:00", "to": "17:00"}])
    assert "09:00-17:00" in text and "08:00-20:00" in text and " or " not in text


def test_explain_open_zone_needs_no_badge():
    a = explain_access(ZoneView(zone_id="z1", type="entry_exit"), [], AFTERNOON)
    assert a.status == "open" and a.granted_now and a.via_badge is None


def test_explain_names_the_badge_that_carried_it():
    zone = ZoneView(zone_id="z1", type="restricted")
    badge = BadgeView(badge_id="b1", zones={"z1"}, expiry=date(2027, 3, 1))
    a = explain_access(zone, [badge], AFTERNOON)
    assert a.status == "allowed" and a.via_badge == "b1" and a.expires == date(2027, 3, 1)


def test_explain_separates_not_yours_from_not_right_now():
    zone = ZoneView(zone_id="z1", type="restricted")
    night = BadgeView(badge_id="b1", zones={"z1"}, time_rule="window",
                      time_windows=[{"from": "20:00", "to": "06:00"}])
    timed = explain_access(zone, [night], AFTERNOON)
    assert timed.status == "timed" and not timed.granted_now and timed.via_badge == "b1"
    assert explain_access(zone, [], AFTERNOON).status == "denied"


def test_explain_reports_an_expired_badge_as_renewable_not_as_refused():
    zone = ZoneView(zone_id="z1", type="restricted")
    old = BadgeView(badge_id="b1", zones={"z1"}, expiry=date(2026, 1, 1))
    a = explain_access(zone, [old], AFTERNOON)
    assert a.status == "expired" and a.via_badge == "b1" and a.expires == date(2026, 1, 1)


def test_explain_prefers_the_badge_that_lasted_longest():
    zone = ZoneView(zone_id="z1", type="restricted")
    badges = [BadgeView(badge_id="old", zones={"z1"}, expiry=date(2025, 1, 1)),
              BadgeView(badge_id="newer", zones={"z1"}, expiry=date(2026, 5, 1))]
    assert explain_access(zone, badges, AFTERNOON).via_badge == "newer"


def test_explain_zone_shut_for_everyone_still_denies_a_holder():
    zone = ZoneView(zone_id="z1", type="restricted",
                    time_windows=[{"from": "08:00", "to": "20:00"}])
    badge = BadgeView(badge_id="b1", zones={"z1"})
    a = explain_access(zone, [badge], NIGHT)
    assert a.status == "timed" and not a.granted_now and "08:00-20:00" in a.hours


def test_explain_never_disagrees_with_the_door():
    """The one property that matters: if the page says yes, the gate says yes."""
    zone = ZoneView(zone_id="z1", type="restricted", allowed_badges=["vip"])
    for badges in ([], [BadgeView(badge_id="staff", zones={"z1"})],
                   [BadgeView(badge_id="vip", zones={"z1"})],
                   [BadgeView(badge_id="vip", zones={"z1"}, expiry=date(2020, 1, 1))]):
        for now in (AFTERNOON, NIGHT, EARLY):
            a = explain_access(zone, badges, now)
            assert a.granted_now == evaluate_access(zone, badges, now)[0]
            assert (a.status in ("open", "allowed")) == a.granted_now
