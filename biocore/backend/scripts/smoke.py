"""End-to-end smoke against the LIVE server (real Postgres). Proves the core loop:
admin login -> register a kiosk -> admin-assisted enroll -> kiosk check-in/out ->
attendance + presence. Run after the server is up:  python -m scripts.smoke
"""
import sys

import httpx

BASE = "http://127.0.0.1:8080/api/v1"
IMG = "data:image/jpeg;base64,Zm9vYmFy"  # fake engine ignores contents



def main() -> None:
    c = httpx.Client(base_url=BASE, timeout=10)

    # 1. admin login (email + password)
    r = c.post("/auth/login", json={"email": "admin@acme.com", "password": "demopass123"})
    r.raise_for_status()
    print("1. login            ->", r.json()["data"]["role"])
    csrf = {"X-CSRF-Token": c.cookies.get("csrf")}

    # 2. session works
    print("2. /auth/me         ->", c.get("/auth/me").json()["data"]["email"])

    # 3. register a kiosk device
    dev = c.post("/devices", headers=csrf, json={"name": "SMOKE-KIOSK"}).json()["data"]
    token = dev["pairing_token"]
    print("3. device           ->", dev["device_id"][:8], "token", token[:12] + "…")

    # 4. admin-assisted enrollment (consent recorded on behalf; fake face stored)
    enr = c.post("/admin/enroll", headers=csrf, json={
        "person_type": "patient", "first_name": "Test", "last_name": "Worker",
        "purpose": "smoke test", "image": IMG, "consent_method": "in_person_verbal",
        "person_present": True, "purpose_explained": True,
        "person_consented": True, "admin_responsible": True,
    }).json()["data"]
    print("4. admin/enroll     ->", enr["user_id"][:8], "consent", enr["consent_ref"])

    # 5. kiosk check-in (device-token auth; fake engine matches the last enrolled)
    s1 = c.post("/faces/search", headers={"X-Device-Token": token},
                json={"image": IMG, "action": "auto"}).json()["data"]
    print("5. faces/search #1  ->", "match" if s1["match"] else "no-match",
          s1.get("name"), "event:", s1.get("event"))

    # 6. second scan toggles to check-out
    s2 = c.post("/faces/search", headers={"X-Device-Token": token},
                json={"image": IMG, "action": "auto"}).json()["data"]
    print("6. faces/search #2  -> event:", s2.get("event"),
          "duration_min:", s2.get("duration_minutes"))

    # 7. attendance + presence reflect it
    att = c.get("/attendance").json()["data"]
    pres = c.get("/attendance/presence").json()["data"]
    print("7. attendance rows  ->", att["total"], "| inside now:", pres["inside_count"])

    # 8. audit trail recorded everything (append-only)
    aud = c.get("/audit").json()["data"]["items"]
    print("8. audit actions    ->", ", ".join(a["action"] for a in aud[:6]))

    print("\nSMOKE OK  (admin auth, CSRF writes, enroll, device kiosk, toggle, attendance, audit)")


if __name__ == "__main__":
    try:
        main()
    except httpx.HTTPStatusError as e:
        print("SMOKE FAILED:", e.response.status_code, e.response.text)
        sys.exit(1)
