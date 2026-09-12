"""Load test for the kiosk face-search path (Doc 6 §3.1: peak x2 concurrent scans).

  locust -f loadtest/locustfile.py --host http://127.0.0.1:8080 --headless -u 100 -r 20 -t 30s

A one-time setup (on test_start) provisions a tenant + admin + device and enrolls
a worker, then every simulated kiosk POSTs /faces/search with the device token.
Run against a server with FAKE_ZEPIRIS=true to load the app layer (not the ML).
"""
import base64
from urllib.parse import parse_qs, urlparse

import httpx
import pyotp
from locust import HttpUser, between, events, task

IMG = "data:image/jpeg;base64," + base64.b64encode(b"\xff\xd8\xff\xd9img").decode()
DEVICE_TOKEN = {"value": None}


@events.test_start.add_listener
def _setup(environment, **_):
    base = environment.host.rstrip("/") + "/api/v1"
    c = httpx.Client(base_url=base, timeout=15)
    import uuid
    org = f"LT-{uuid.uuid4().hex[:8]}"
    email = f"lt_{uuid.uuid4().hex[:6]}@acme.com"
    r = c.post("/admin/tenants", json={"name": "Load", "org_code": org, "vertical": "office",
                                       "admin_email": email, "admin_password": "supersecret123"})
    secret = parse_qs(urlparse(r.json()["data"]["totp_provisioning_uri"]).query)["secret"][0]
    c.post("/auth/login", json={"email": email, "password": "supersecret123",
                                "totp_code": pyotp.TOTP(secret).now()})
    csrf = {"X-CSRF-Token": c.cookies.get("csrf")}
    dev = c.post("/devices", headers=csrf, json={"name": "LT-KIOSK"}).json()["data"]
    c.post("/admin/enroll", headers=csrf, json={
        "person_type": "patient", "first_name": "Load", "last_name": "Worker", "purpose": "lt",
        "image": IMG, "consent_method": "in_person_verbal", "person_present": True,
        "purpose_explained": True, "person_consented": True, "admin_responsible": True})
    DEVICE_TOKEN["value"] = dev["pairing_token"]
    c.close()
    print(f"[loadtest] setup done; device token acquired for org {org}")


class Kiosk(HttpUser):
    wait_time = between(0.1, 0.5)

    @task
    def face_search(self):
        token = DEVICE_TOKEN["value"]
        if not token:
            return
        self.client.post("/api/v1/faces/search", name="/faces/search",
                         headers={"X-Device-Token": token},
                         json={"image": IMG, "action": "auto"})
