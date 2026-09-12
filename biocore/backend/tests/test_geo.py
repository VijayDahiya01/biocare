"""Unit tests for geofence math."""
from app.services.geo import haversine_km, within_any


def test_haversine_zero_distance():
    assert haversine_km(28.7, 77.1, 28.7, 77.1) == 0


def test_haversine_known_distance():
    # Delhi-ish to ~1.11 km north (0.01 deg latitude ≈ 1.11 km)
    d = haversine_km(28.70, 77.10, 28.71, 77.10)
    assert 1.0 < d < 1.2


def test_within_any_no_fences_is_allowed():
    ok, name = within_any(28.7, 77.1, [])
    assert ok is True and name is None


def test_within_any_inside_and_outside():
    fences = [{"name": "HQ", "center_lat": 28.70, "center_lng": 77.10, "radius_km": 0.5}]
    assert within_any(28.701, 77.10, fences) == (True, "HQ")
    ok, name = within_any(28.80, 77.10, fences)  # ~11 km away
    assert ok is False and name is None
