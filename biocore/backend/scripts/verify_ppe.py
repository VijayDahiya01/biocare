"""Verify PPE enforcement end-to-end against the reference PPE service.

Prereq: reference PPE server running on :8002  (python infra/ppe-reference/app.py)
Run:    python -m scripts.verify_ppe

In-process app (TestClient) with PPE_SERVICE_URL pointed at the reference server.
A zone with require_ppe denies entry + alerts when gear is missing, and grants
when present — proving the kiosk -> PPE adapter -> model -> decision path.
"""
import os
import uuid

os.environ["PPE_SERVICE_URL"] = "http://127.0.0.1:8002"  # before importing app

import httpx  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

PPE = "http://127.0.0.1:8002"
IMG = "data:image/jpeg;base64,Zm9vYmFy"


def _admin(tc):
    from urllib.parse import parse_qs, urlparse

    import pyotp
    org = f"PPE-{uuid.uuid4().hex[:8]}"
    email = f"admin_{uuid.uuid4().hex[:6]}@acme.com"
    uri = tc.post("/api/v1/admin/tenants", json={"name": "PPE", "org_code": org, "vertical": "factory",
                  "admin_email": email, "admin_password": "supersecret123"}).json()["data"]["totp_provisioning_uri"]
    secret = parse_qs(urlparse(uri).query)["secret"][0]
    tc.post("/api/v1/auth/login", json={"email": email, "password": "supersecret123",
                                        "totp_code": pyotp.TOTP(secret).now()})
    tc.headers.update({"X-CSRF-Token": tc.cookies.get("csrf")})


def main():
    # confirm reference PPE server is reachable
    assert httpx.get(f"{PPE}/healthz", timeout=5).json()["status"] == "ok", "PPE server not up on :8002"

    from app.adapters.ppe import get_ppe
    from app.main import app
    assert get_ppe().enabled, "PPE adapter not enabled (PPE_SERVICE_URL unset)"

    c = TestClient(app)
    _admin(c)

    # zone that requires PPE but is otherwise open (isolate the PPE decision)
    zone = c.post("/api/v1/zones", json={"name": "Hazard Floor", "type": "entry_exit",
                  "access_rule": {"require_ppe": True, "ppe_items": ["helmet", "vest"]}}).json()["data"]
    dev = c.post("/api/v1/devices", json={"name": "PPE-KIOSK", "zone_id": zone["zone_id"]}).json()["data"]
    tok = {"X-Device-Token": dev["pairing_token"]}
    c.post("/api/v1/admin/enroll", json={
        "person_type": "patient", "first_name": "Worker", "last_name": "Ppe", "purpose": "t",
        "image": IMG, "consent_method": "in_person_verbal", "person_present": True,
        "purpose_explained": True, "person_consented": True, "admin_responsible": True})

    # --- 1. gear MISSING -> deny + alert ---
    httpx.post(f"{PPE}/_simulate", json={"helmet": True, "vest": False}, timeout=5)
    d = c.post("/api/v1/faces/search", headers=tok, json={"image": IMG, "action": "auto"}).json()["data"]
    miss_ok = d.get("ppe", {}).get("ok") is False and d["ppe"]["missing"] == ["vest"] \
        and d["access"]["granted"] is False and d["access"]["reason"] == "ppe_missing"
    alerts = c.get("/api/v1/alerts?type=ppe_violation").json()["data"]["items"]
    print(f"[{'PASS' if miss_ok else 'FAIL'}] missing PPE -> denied (ppe={d.get('ppe')}, access={d.get('access')})")
    print(f"[{'PASS' if alerts else 'FAIL'}] ppe_violation alert raised ({len(alerts)} alert(s))")

    # --- 2. gear PRESENT -> granted ---
    httpx.post(f"{PPE}/_simulate", json={"helmet": True, "vest": True}, timeout=5)
    d2 = c.post("/api/v1/faces/search", headers=tok, json={"image": IMG, "action": "auto"}).json()["data"]
    ok = d2.get("ppe", {}).get("ok") is True and d2["access"]["granted"] is True
    print(f"[{'PASS' if ok else 'FAIL'}] full PPE -> granted (ppe={d2.get('ppe')}, access={d2.get('access')})")

    if miss_ok and alerts and ok:
        print("\nVERIFY_PPE OK  (missing -> deny+alert, present -> grant)")
    else:
        raise SystemExit("VERIFY_PPE FAILED")


if __name__ == "__main__":
    main()
