"""Unit tests for webhook HMAC signing (API Reference §6.3 — consumers verify)."""
from app.services.webhook_service import sign, verify


def test_sign_is_deterministic_and_prefixed():
    payload = {"event": "access.granted", "user_id": "u1", "zone_id": "z1"}
    s1 = sign("secret", payload)
    s2 = sign("secret", payload)
    assert s1 == s2
    assert s1.startswith("sha256=")


def test_verify_accepts_valid_and_rejects_tampered():
    payload = {"user_id": "u1", "zone_id": "z1"}
    sig = sign("topsecret", payload)
    assert verify("topsecret", payload, sig) is True
    # wrong secret
    assert verify("other", payload, sig) is False
    # tampered payload
    assert verify("topsecret", {"user_id": "u2", "zone_id": "z1"}, sig) is False


def test_key_order_does_not_change_signature():
    a = sign("s", {"a": 1, "b": 2})
    b = sign("s", {"b": 2, "a": 1})
    assert a == b  # canonical (sorted) JSON
