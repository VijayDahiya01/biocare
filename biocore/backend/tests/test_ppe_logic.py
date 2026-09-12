"""Unit tests for PPE decision logic + adapter no-op behaviour."""
from app.adapters.ppe import PpeClient
from app.services.ppe_logic import DEFAULT_REQUIRED, evaluate_ppe


def test_all_present_is_ok():
    ok, missing = evaluate_ppe({"helmet": True, "vest": True})
    assert ok is True and missing == []


def test_missing_item_listed():
    ok, missing = evaluate_ppe({"helmet": True, "vest": False})
    assert ok is False and missing == ["vest"]


def test_custom_required_set():
    ok, missing = evaluate_ppe({"helmet": True, "gloves": False}, required=["helmet", "gloves"])
    assert ok is False and missing == ["gloves"]


def test_default_required_is_helmet_and_vest():
    assert DEFAULT_REQUIRED == ["helmet", "vest"]
    ok, missing = evaluate_ppe({})
    assert ok is False and set(missing) == {"helmet", "vest"}


def test_adapter_disabled_when_no_url():
    client = PpeClient(base_url="", timeout=5)
    assert client.enabled is False
    res = client.detect("data:image/jpeg;base64,xxx")
    assert res.configured is False and res.detections == {}
