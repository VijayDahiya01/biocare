"""Pure access-control decision logic (no DB) so it can be unit-tested.

A zone is "gated" if it is restricted or names allowed badges. To enter a gated
zone a person must hold a badge that (a) grants that zone, (b) is not expired,
and (c) is within its time rule — and the current time must also fall inside any
time windows the zone itself defines.

`evaluate_access` is the door's answer. `explain_access` wraps it to say the same thing to
the person whose face it is, and deliberately takes its yes/no from that same call rather
than working it out again — a second copy of these rules would eventually drift, and the
failure mode is telling somebody they may walk through a door that will refuse them.
"""
from dataclasses import dataclass, field
from datetime import date, datetime, time

DAY_NAMES = ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")


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


@dataclass
class ZoneAccess:
    """What one person can expect at one zone.

    `granted_now` / `reason` are the door's own words. `status` is the same answer phrased
    for the person, with enough detail to act on: which badge carries it, when it applies,
    and when it runs out.
    """
    zone_id: str
    granted_now: bool
    reason: str                        # as evaluate_access reports it
    status: str                        # open | allowed | timed | expired | denied
    hours: str = "Any time"
    via_badge: str | None = None
    expires: date | None = None


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


def _describe_days(days: list[int] | None) -> str:
    """"Mon-Fri" for a run, "Mon, Wed, Fri" otherwise, "" for every day."""
    if days is None:
        return ""
    kept = sorted({d for d in days if 0 <= d <= 6})
    if not kept or len(kept) == 7:
        return ""
    if len(kept) > 2 and kept == list(range(kept[0], kept[-1] + 1)):
        return f"{DAY_NAMES[kept[0]]}-{DAY_NAMES[kept[-1]]}"
    return ", ".join(DAY_NAMES[d] for d in kept)


def describe_windows(windows: list[dict]) -> str:
    """Human text for a set of time windows. Empty means no restriction."""
    if not windows:
        return "Any time"
    parts = []
    for w in windows:
        days = _describe_days(w.get("days"))
        span = f"{w.get('from', '00:00')}-{w.get('to', '23:59')}"
        parts.append(f"{days} {span}".strip())
    return " or ".join(parts)


def describe_hours(zone_windows: list[dict], badge_windows: list[dict]) -> str:
    """Both sets have to hold at once, so they cannot be merged into one list — a list is
    read as "any of these"."""
    if not zone_windows and not badge_windows:
        return "Any time"
    if not badge_windows:
        return describe_windows(zone_windows)
    if not zone_windows:
        return describe_windows(badge_windows)
    return f"{describe_windows(badge_windows)}, while the area is open ({describe_windows(zone_windows)})"


def is_gated(zone: ZoneView) -> bool:
    return zone.type == "restricted" or bool(zone.allowed_badges)


def candidate_badges(zone: ZoneView, badges: list[BadgeView]) -> list[BadgeView]:
    """The badges that name this zone and that the zone admits — before any time or expiry
    test. Holding one is what separates "not yours" from "not right now"."""
    return [b for b in badges
            if zone.zone_id in b.zones
            and not (zone.allowed_badges and b.badge_id not in zone.allowed_badges)]


def evaluate_access(zone: ZoneView, badges: list[BadgeView], now: datetime) -> tuple[bool, str]:
    """Return (granted, reason)."""
    if not is_gated(zone):
        return True, "open_zone"

    # zone-level time gate (e.g. server room only 08:00-20:00)
    if not within_windows(zone.time_windows, now):
        return False, "outside_hours"

    today = now.date()
    candidates = candidate_badges(zone, badges)
    for b in candidates:
        if b.expiry is not None and today > b.expiry:
            continue
        if b.time_rule == "window" and not within_windows(b.time_windows, now):
            continue
        return True, "badge_ok"

    return (False, "badge_expired_or_outside_hours") if candidates else (False, "no_badge")


def explain_access(zone: ZoneView, badges: list[BadgeView], now: datetime) -> ZoneAccess:
    """The door's decision, plus why and when — for the person, not the operator."""
    granted, reason = evaluate_access(zone, badges, now)

    if reason == "open_zone":
        return ZoneAccess(zone.zone_id, True, reason, "open",
                          hours=describe_windows(zone.time_windows))

    def _hours(b: BadgeView) -> str:
        return describe_hours(zone.time_windows,
                              b.time_windows if b.time_rule == "window" else [])

    today = now.date()
    candidates = candidate_badges(zone, badges)
    live = [b for b in candidates if b.expiry is None or today <= b.expiry]

    if granted:
        # The badge that actually carried it: the first live one inside its own window,
        # scanned in the order evaluate_access scans them.
        b = next((c for c in live
                  if c.time_rule != "window" or within_windows(c.time_windows, now)), None)
        if b is not None:
            return ZoneAccess(zone.zone_id, True, reason, "allowed",
                              hours=_hours(b), via_badge=b.badge_id, expires=b.expiry)
        return ZoneAccess(zone.zone_id, True, reason, "allowed",
                          hours=describe_windows(zone.time_windows))

    if not candidates:
        return ZoneAccess(zone.zone_id, False, reason, "denied",
                          hours=describe_windows(zone.time_windows))

    if not live:
        # Every badge for this zone has run out. Lead with the one that lasted longest —
        # that is the one worth asking to have renewed.
        b = max(candidates, key=lambda c: c.expiry or date.min)
        return ZoneAccess(zone.zone_id, False, reason, "expired",
                          hours=_hours(b), via_badge=b.badge_id, expires=b.expiry)

    b = live[0]
    return ZoneAccess(zone.zone_id, False, reason, "timed",
                      hours=_hours(b), via_badge=b.badge_id, expires=b.expiry)
