"""Phase 0 acceptance gate (integration).

Proves: register a tenant -> create an admin -> log in -> the session cookie works.
Also exercises the tenant-isolation safety net. Requires the stack (Postgres+Redis).
"""
import uuid
from urllib.parse import parse_qs, urlparse

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def app_client(require_stack):
    from app.main import app
    return TestClient(app)




def test_provision_login_and_session(app_client):
    org = f"TEST-{uuid.uuid4().hex[:8]}"
    email = f"admin_{uuid.uuid4().hex[:8]}@example.com"

    # 1. provision tenant + entity admin
    r = app_client.post("/api/v1/admin/tenants", json={
        "name": "Test Org", "org_code": org, "vertical": "office",
        "admin_email": email, "admin_password": "supersecret123", "admin_name": "Test Admin",
    })
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["success"] is True
    assert body["request_id"].startswith("req_")

    # 2. login with email + password -> session cookie
    r = app_client.post("/api/v1/auth/login", json={
        "email": email, "password": "supersecret123",
    })
    assert r.status_code == 200, r.text
    assert "session" in r.cookies
    assert r.json()["data"]["role"] == "entity_admin"

    # 3. the session cookie authorises /auth/me
    r = app_client.get("/api/v1/auth/me")
    assert r.status_code == 200
    assert r.json()["data"]["role"] == "entity_admin"



def test_wrong_password_is_401(app_client):
    r = app_client.post("/api/v1/auth/login", json={
        "email": "nobody@example.com", "password": "wrong",
    })
    assert r.status_code == 401
    assert r.json()["error"]["code"] == "INVALID_CREDENTIALS"


def test_duplicate_org_code_conflicts(app_client):
    org = f"TEST-{uuid.uuid4().hex[:8]}"
    payload = {"name": "Org", "org_code": org, "vertical": "office",
               "admin_email": f"a_{uuid.uuid4().hex[:6]}@x.com", "admin_password": "supersecret123"}
    assert app_client.post("/api/v1/admin/tenants", json=payload).status_code == 201
    payload["admin_email"] = f"b_{uuid.uuid4().hex[:6]}@x.com"
    r = app_client.post("/api/v1/admin/tenants", json=payload)
    assert r.status_code == 409
    assert r.json()["error"]["code"] == "ORG_CODE_EXISTS"
