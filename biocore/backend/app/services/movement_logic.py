"""Pure zone-movement analysis (no DB) — unit-tested.

Builds a movement trail, per-zone dwell time, and flags anomalies for
high-security review:
  * restricted_before_entry — the day's first zone is restricted (entered a
    secure zone without first passing a normal entry point — a tailgating proxy).
  * rapid_transition — two different zones within `rapid_seconds` (physically
    implausible; possible tailgating / shared credential).
"""
from datetime import datetime

ZoneEvent = tuple[str | None, str, datetime]  # (zone_id, event_type, timestamp)


def analyze_movement(events: list[ZoneEvent], restricted_zones: set[str],
                     rapid_seconds: int = 20) -> dict:
    zoned = sorted([e for e in events if e[0]], key=lambda e: e[2])

    trail = [{"zone_id": z, "event": et, "at": t.isoformat()} for z, et, t in zoned]

    dwell: dict[str, float] = {}
    for (z, _et, t), (_z2, _et2, t2) in zip(zoned, zoned[1:]):
        dwell[z] = dwell.get(z, 0.0) + (t2 - t).total_seconds()

    anomalies: list[dict] = []
    if zoned and zoned[0][0] in restricted_zones:
        anomalies.append({"type": "restricted_before_entry", "zone_id": zoned[0][0],
                          "at": zoned[0][2].isoformat()})
    for (z, _et, t), (z2, _et2, t2) in zip(zoned, zoned[1:]):
        if z != z2 and (t2 - t).total_seconds() < rapid_seconds:
            anomalies.append({"type": "rapid_transition", "from": z, "to": z2,
                              "seconds": (t2 - t).total_seconds(), "at": t2.isoformat()})

    return {
        "trail": trail,
        "dwell_seconds_by_zone": {k: int(v) for k, v in dwell.items()},
        "anomalies": anomalies,
    }
