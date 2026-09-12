"""Pure access-control decision logic (no DB) so it can be unit-tested.

A zone is "gated" if it is restricted or names allowed badges. To enter a gated
zone a person must hold a badge that (a) grants that zone, (b) is not expired,
and (c) is within its time rule — and the current time must also fall inside any
time windows the zone itself defines.
"""
from dataclasses import dataclass, field
from datetime import date, datetime, time


@dataclass
class BadgeView:
    badge_id: str
    zones: set[str]
    time_rule: str = "always"          # always | window
    time_windows: list[dict] = field(default_factory=list)  # [{from,to,days?}]
    expiry: date | None = None


@dataclass
class ZoneView:
    zone_id: str
    type: str                          # entry_exit | restricted | amenity
    allowed_badges: list[str] = field(default_factory=list)  # badge ids
    time_windows: list[dict] = field(default_factory=list)


def _parse_hhmm(s: str) -> time:
    h, m = s.split(":")
    return time(int(h), int(m))


def within_windows(windows: list[dict], now: datetime) -> bool:
    """True if `now` falls in any window. Empty list = always true.
    A window is {"from":"HH:MM","to":"HH:MM","days":[0-6]?} (0=Mon)."""
    if not windows:
        return True
    cur = now.time()
    weekday = now.weekday()
    for w in windows:
        days = w.get("days")
        if days is not None and weekday not in days:
            continue
        start = _parse_hhmm(w["from"])
        end = _parse_hhmm(w["to"])
        if start <= end:
            if start <= cur <= end:
                return True
        else:  # window crosses midnight (e.g. 20:00-06:00)
            if cur >= start or cur <= end:
                return True
    return False


def is_gated(zone: ZoneView) -> bool:
    return zone.type == "restricted" or bool(zone.allowed_badges)


def evaluate_access(zone: ZoneView, badges: list[BadgeView], now: datetime) -> tuple[bool, str]:
    """Return (granted, reason)."""
    if not is_gated(zone):
        return True, "open_zone"

    # zone-level time gate (e.g. server room only 08:00-20:00)
    if not within_windows(zone.time_windows, now):
        return False, "outside_hours"

    today = now.date()
    holds_zone_badge = False
    for b in badges:
        if zone.zone_id not in b.zones:
            continue
        if zone.allowed_badges and b.badge_id not in zone.allowed_badges:
            continue
        holds_zone_badge = True
        if b.expiry is not None and today > b.expiry:
            continue
        if b.time_rule == "window" and not within_windows(b.time_windows, now):
            continue
        return True, "badge_ok"

    return (False, "badge_expired_or_outside_hours") if holds_zone_badge else (False, "no_badge")
