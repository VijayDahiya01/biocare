"""Phase 2 acceptance (integration): tenant isolation (cross-tenant 404) and the
verified DPDP erasure cascade. ZepIris is mocked; Postgres + Redis required."""
import base64
import re
import uuid
from urllib.parse import parse_qs, urlparse

import httpx
import pytest
import respx
from fastapi.testclient import TestClient

from app.core.config import settings

Z = settings.zepiris_url.rstrip("/")
PIXEL = "data:image/jpeg;base64," + base64.b64encode(b"\xff\xd8\xff\xd9img").decode()


@pytest.fixture
def client(require_stack):
    from app.main import app
    return TestClient(app)


def _csrf(c: TestClient) -> dict:
    return {"X-CSRF-Token": c.cookies.get("csrf")}


def _admin(client) -> tuple[TestClient, str]:
    org = f"P2-{uuid.uuid4().hex[:8]}"
    email = f"admin_{uuid.uuid4().hex[:6]}@x.com"
    r = client.post("/api/v1/admin/tenants", json={
        "name": "P2", "org_code": org, "vertical": "office",
        "admin_email": email, "admin_password": "supersecret123",
    })
    c = TestClient(client.app)
    c.post("/api/v1/auth/login", json={"email": email, "password": "supersecret123"})
    return c, org


def test_cross_tenant_resource_is_404(client):
    a, _ = _admin(client)
    b, _ = _admin(client)
    # A registers a device
    dev = a.post("/api/v1/devices", headers=_csrf(a), json={"name": "A-KIOSK"}).json()["data"]
    # B (different tenant) cannot see or act on A's device -> 404, not another tenant's data
    r = b.post(f"/api/v1/devices/{dev['device_id']}/disable", headers=_csrf(b))
    assert r.status_code == 404
    assert r.json()["error"]["code"] == "DEVICE_NOT_FOUND"


@respx.mock
def test_erasure_cascade_verified(client):
    a, org = _admin(client)

    # enroll a member with a face
    member_email = f"m_{uuid.uuid4().hex[:6]}@x.com"
    uid = client.post("/api/v1/register", json={
        "org_code": org, "first_name": "Asha", "email": member_email,
    }).json()["data"]["user_id"]

    from app.core.redis_client import client as redis
    from app.core.redis_client import otp_key
    member = TestClient(client.app)
    member.post("/api/v1/auth/otp/verify", json={"email": member_email, "otp": redis.get(otp_key(member_email))})
    member.post("/api/v1/consent", headers=_csrf(member), json={
        "purpose": "attendance", "method": "self",
        "acknowledgements": {"purpose_understood": True, "sensitivity_understood": True,
                             "rights_understood": True, "freely_given": True},
    })
    respx.post(f"{Z}/v1/faces/insert").mock(return_value=httpx.Response(200, json={
        "requestId": "r", "imageQualityAssessment": {"passed": True, "spoof": {"is_spoof": False}},
        "userOperationResult": {"status": "success"},
    }))
    member.post("/api/v1/faces/enroll", headers=_csrf(member), json={"image": PIXEL})

    # erasure: engine delete succeeds, and get-after-delete returns 404 (verified gone)
    respx.delete(f"{Z}/v1/faces/delete").mock(return_value=httpx.Response(200, json={
        "requestId": "d", "userOperationResult": {"operation": "DELETE", "status": "success"}}))
    respx.get(re.compile(rf"{re.escape(Z)}/v1/faces/get/.*")).mock(return_value=httpx.Response(404))

    # OTP re-auth, then erase
    member.post("/api/v1/auth/otp/request", json={"email": member_email})
    code = redis.get(otp_key(member_email))
    r = member.post("/api/v1/me/data/erasure", headers=_csrf(member), json={"otp": code})
    assert r.status_code == 200, r.text
    data = r.json()["data"]
    assert set(data["stores_cleared"]) >= {"milvus", "minio", "postgres", "redis"}
    assert all(data["verified"].values())
    assert data["erasure_ref"].startswith("ERA-")

    # erasure is itself audited (and the user is soft-deleted, so hidden from /users)
    audit = a.get("/api/v1/audit?action=ERASURE_COMPLETE").json()["data"]["items"]
    assert any(e["target_id"] == uid for e in audit)
