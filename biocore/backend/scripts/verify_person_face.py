"""Verify capture-once + one-tap reuse: master capture -> join -> allow business
(re-provision, no re-scan) -> kiosk matches -> revoke removes it. In-process.

    python -m scripts.verify_person_face
"""
import uuid

from fastapi.testclient import TestClient

from app.core.redis_client import client as redis
from app.core.redis_client import otp_key
from app.main import app

IMG = "data:image/jpeg;base64,Zm9vYmFy"
RESULTS = []


def chk(name, ok, detail=""):
    RESULTS.append(ok)
    print(f"  [{'PASS' if ok else 'FAIL'}] {name}" + (f" — {detail}" if detail else ""))


def main():
    # office business + admin
    office = TestClient(app)
    org = f"OFF-{uuid.uuid4().hex[:8]}"
    aemail = f"admin_{uuid.uuid4().hex[:6]}@acme.com"
    office.post("/api/v1/admin/tenants", json={"name": "Office Co", "org_code": org,
                "vertical": "office", "admin_email": aemail, "admin_password": "supersecret123"})
    office.post("/api/v1/auth/login", json={"email": aemail, "password": "supersecret123"})
    office.headers.update({"X-CSRF-Token": office.cookies.get("csrf")})
    dev = office.post("/api/v1/devices", json={"name": "OFF-KIOSK"}).json()["data"]

    # person logs in, captures master face ONCE
    riya_email = f"riya_{uuid.uuid4().hex[:6]}@example.com"
    riya = TestClient(app)
    riya.post("/api/v1/person/auth/otp/request", json={"email": riya_email})
    riya.post("/api/v1/person/auth/otp/verify", json={"email": riya_email, "otp": redis.get(otp_key(riya_email))})
    riya.headers.update({"X-CSRF-Token": riya.cookies.get("csrf")})
    acks = {"purpose_understood": True, "sensitivity_understood": True, "rights_understood": True, "freely_given": True}
    e = riya.post("/api/v1/person/face/enroll", json={"image": IMG, "acknowledgements": acks})
    chk("master face captured once", e.status_code == 201 and e.json()["data"]["face_verified"] is True)
    chk("profile now face_verified", riya.get("/api/v1/person/me").json()["data"]["face_verified"] is True)

    # join office, then ONE-TAP allow (no re-scan)
    m = riya.post("/api/v1/person/businesses/join", json={"org_code": org}).json()["data"]["membership_id"]
    allow = riya.post(f"/api/v1/person/businesses/{m}/consent")
    chk("one-tap consent activates membership (no re-scan)", allow.status_code == 201 and allow.json()["data"]["status"] == "active")

    # kiosk at the office now recognises her (face was re-provisioned into office space)
    s = office.post("/api/v1/faces/search", headers={"X-Device-Token": dev["pairing_token"]},
                    json={"image": IMG, "action": "auto"}).json()["data"]
    chk("kiosk recognises her after reuse", s.get("match") is True and s.get("user_id") == m)

    # membership detail (role / badges / verification / my history)
    det = riya.get(f"/api/v1/person/businesses/{m}").json()["data"]
    chk("membership detail shows role + verification + my history",
        det["role"] == "self_user" and det["face_verified_here"] is True and len(det["history"]) >= 1)

    # events: admin creates one; person sees, registers (per-event consent), sees consented
    ev = office.post("/api/v1/events", json={"name": "Health Camp"}).json()["data"]
    evs = riya.get(f"/api/v1/person/businesses/{m}/events").json()["data"]["items"]
    chk("event visible, not yet registered", any(e["event_id"] == ev["event_id"] and not e["registered"] for e in evs))
    reg = riya.post(f"/api/v1/person/events/{ev['event_id']}/register")
    chk("event register + per-event consent", reg.status_code == 201 and reg.json()["data"]["registered"] is True)
    evs2 = riya.get(f"/api/v1/person/businesses/{m}/events").json()["data"]["items"]
    chk("event now registered + consented",
        any(e["event_id"] == ev["event_id"] and e["registered"] and e["consented"] for e in evs2))

    # revoke for this business -> her face is removed there
    rv = riya.post(f"/api/v1/person/businesses/{m}/consent/revoke")
    chk("revoke suspends membership", rv.status_code == 200 and rv.json()["data"]["status"] == "suspended")
    s2 = office.post("/api/v1/faces/search", headers={"X-Device-Token": dev["pairing_token"]},
                     json={"image": IMG, "action": "auto"}).json()["data"]
    chk("kiosk no longer matches after revoke", s2.get("match") is False)

    ok = all(RESULTS)
    print(f"\nVERIFY_PERSON_FACE {'OK' if ok else 'FAILED'} ({sum(RESULTS)}/{len(RESULTS)})")
    if not ok:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
