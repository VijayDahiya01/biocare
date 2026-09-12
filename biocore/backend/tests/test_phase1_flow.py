"""Phase 1 acceptance (integration): self-register -> consent -> enroll -> kiosk
check-in/out -> live presence. ZepIris is mocked over HTTP (respx); Postgres +
Redis must be reachable (otherwise the whole module skips).
"""
import uuid
from urllib.parse import parse_qs, urlparse

import httpx
import pyotp
import pytest
import respx
from fastapi.testclient import TestClient

from app.core.config import settings

Z = settings.zepiris_url.rstrip("/")
PIXEL = "data:image/jpeg;base64," + __import__("base64").b64encode(b"\xff\xd8\xff\xd9img").decode()


@pytest.fixture
def client(require_stack):
    from app.main import app
    return TestClient(app)


def _csrf(c: TestClient) -> dict:
    return {"X-CSRF-Token": c.cookies.get("csrf")}


def _totp(uri: str) -> str:
    return pyotp.TOTP(parse_qs(urlparse(uri).query)["secret"][0]).now()


def _provision(client) -> tuple[str, str, str]:
    org = f"P1-{uuid.uuid4().hex[:8]}"
    email = f"admin_{uuid.uuid4().hex[:6]}@x.com"
    r = client.post("/api/v1/admin/tenants", json={
        "name": "P1 Org", "org_code": org, "vertical": "office",
        "admin_email": email, "admin_password": "supersecret123",
    })
    assert r.status_code == 201, r.text
    return org, email, r.json()["data"]["totp_provisioning_uri"]


@respx.mock
def test_full_attendance_mvp(client):
    org, admin_email, admin_uri = _provision(client)

    # --- member self-registration ---
    member_email = f"rahul_{uuid.uuid4().hex[:6]}@x.com"
    r = client.post("/api/v1/register", json={
        "org_code": org, "first_name": "Rahul", "last_name": "Kumar", "email": member_email,
    })
    assert r.status_code == 201, r.text
    user_id = r.json()["data"]["user_id"]
    assert r.json()["data"]["status"] == "pending_email"

    # pull the OTP straight from Redis (the email channel is a dev stub)
    from app.core.redis_client import client as redis
    from app.core.redis_client import otp_key
    code = redis.get(otp_key(member_email))
    assert code, "registration should have issued an OTP"

    # --- verify OTP -> member session ---
    member = TestClient(client.app)
    r = member.post("/api/v1/auth/otp/verify", json={"email": member_email, "otp": code})
    assert r.status_code == 200, r.text
    assert r.json()["data"]["status"] == "pending_face"

    # --- consent (all four acks) ---
    r = member.post("/api/v1/consent", headers=_csrf(member), json={
        "purpose": "attendance", "method": "self",
        "acknowledgements": {"purpose_understood": True, "sensitivity_understood": True,
                             "rights_understood": True, "freely_given": True},
    })
    assert r.status_code == 201, r.text

    # --- enroll face (ZepIris insert mocked) ---
    respx.post(f"{Z}/v1/faces/insert").mock(return_value=httpx.Response(200, json={
        "requestId": "r1",
        "imageQualityAssessment": {"passed": True, "blur": {"is_sharp": True},
                                   "spoof": {"is_spoof": False}, "nudity": {"is_safe": True}},
        "userOperationResult": {"operation": "INSERT", "status": "success"},
    }))
    r = member.post("/api/v1/faces/enroll", headers=_csrf(member), json={"image": PIXEL})
    assert r.status_code == 201, r.text
    assert r.json()["data"]["vector_stored"] is True

    # --- consent gate: a user with no consent cannot enroll ---
    # (covered by unit-level gate; here we proceed to kiosk)

    # --- admin registers a kiosk device ---
    admin = TestClient(client.app)
    admin.post("/api/v1/auth/login", json={
        "email": admin_email, "password": "supersecret123", "totp_code": _totp(admin_uri),
    })
    r = admin.post("/api/v1/devices", headers=_csrf(admin), json={"name": "KIOSK-GATE-01"})
    assert r.status_code == 201, r.text
    device_token = r.json()["data"]["pairing_token"]

    # --- kiosk check-in (ZepIris search mocked to match our user) ---
    def mock_search(score=0.95):
        respx.post(f"{Z}/v1/faces/search").mock(return_value=httpx.Response(200, json={
            "requestId": "s1", "imageQualityAssessment": {"passed": True, "spoof": {"is_spoof": False}},
            "searchResult": {"matches": [{"id": user_id, "score": score}]},
        }))

    mock_search()
    r = client.post("/api/v1/faces/search", headers={"X-Device-Token": device_token},
                    json={"image": PIXEL, "action": "auto"})
    assert r.status_code == 200, r.text
    data = r.json()["data"]
    assert data["match"] is True and data["event"] == "check_in"

    # second scan toggles to check_out
    r = client.post("/api/v1/faces/search", headers={"X-Device-Token": device_token},
                    json={"image": PIXEL, "action": "auto"})
    assert r.json()["data"]["event"] == "check_out"

    # --- presence reflects nobody inside after check-out ---
    r = admin.get("/api/v1/attendance/presence")
    assert r.status_code == 200
    assert r.json()["data"]["inside_count"] == 0

    # --- attendance log shows both events ---
    r = admin.get("/api/v1/attendance")
    assert r.status_code == 200
    events = {row["event_type"] for row in r.json()["data"]["items"]}
    assert {"check_in", "check_out"} <= events


@respx.mock
def test_spoof_is_rejected_at_kiosk(client):
    org, admin_email, admin_uri = _provision(client)
    admin = TestClient(client.app)
    admin.post("/api/v1/auth/login", json={
        "email": admin_email, "password": "supersecret123", "totp_code": _totp(admin_uri),
    })
    r = admin.post("/api/v1/devices", headers=_csrf(admin), json={"name": "K2"})
    device_token = r.json()["data"]["pairing_token"]

    respx.post(f"{Z}/v1/faces/search").mock(return_value=httpx.Response(200, json={
        "requestId": "s", "imageQualityAssessment": {"passed": False, "spoof": {"is_spoof": True}},
        "searchResult": {"matches": []},
    }))
    r = client.post("/api/v1/faces/search", headers={"X-Device-Token": device_token},
                    json={"image": PIXEL, "action": "auto"})
    assert r.status_code == 403
    assert r.json()["error"]["code"] == "SPOOF_DETECTED"
