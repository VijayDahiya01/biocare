"""Pure geofence math (no DB) — unit-tested. Haversine great-circle distance."""
import math

EARTH_RADIUS_KM = 6371.0088


def haversine_km(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlam = math.radians(lng2 - lng1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlam / 2) ** 2
    return 2 * EARTH_RADIUS_KM * math.asin(math.sqrt(a))


def within_any(lat: float, lng: float, fences: list[dict]) -> tuple[bool, str | None]:
    """fences: [{name, center_lat, center_lng, radius_km}]. No fences = allowed."""
    if not fences:
        return True, None
    for f in fences:
        if haversine_km(lat, lng, f["center_lat"], f["center_lng"]) <= f["radius_km"]:
            return True, f["name"]
    return False, None
