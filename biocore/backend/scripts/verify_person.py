"""Verify the person-centric hub: login -> join -> invite/accept -> businesses by
sector -> cross-person isolation. In-process (real Postgres, fake Redis for OTP).

    python -m scripts.verify_person
"""
import uuid

from fastapi.testclient import TestClient

from app.core.redis_client import client as redis
from app.core.redis_client import otp_key
from app.main import app

RESULTS = []


def chk(name, ok, detail=""):
    RESULTS.append(ok)
    print(f"  [{'PASS' if ok else 'FAIL'}] {name}" + (f" — {detail}" if detail else ""))


def make_business(vertical: str):
    tc = TestClient(app)
    org = f"{vertical[:3].upper()}-{uuid.uuid4().hex[:8]}"
    email = f"admin_{uuid.uuid4().hex[:6]}@acme.com"
    tc.post("/api/v1/admin/tenants", json={"name": f"{vertical.title()} Co", "org_code": org,
            "vertical": vertical, "admin_email": email, "admin_password": "supersecret123"})
    tc.post("/api/v1/auth/login", json={"email": email, "password": "supersecret123"})
    tc.headers.update({"X-CSRF-Token": tc.cookies.get("csrf")})
    return tc, org


def person_login(email: str) -> TestClient:
    pc = TestClient(app)
    pc.post("/api/v1/person/auth/otp/request", json={"email": email})
    pc.post("/api/v1/person/auth/otp/verify", json={"email": email, "otp": redis.get(otp_key(email))})
    pc.headers.update({"X-CSRF-Token": pc.cookies.get("csrf")})
    return pc


def main():
    office, office_code = make_business("office")
    gym, _ = make_business("gym")

    riya_email = f"riya_{uuid.uuid4().hex[:6]}@example.com"
    riya = person_login(riya_email)
    chk("person hub starts empty", riya.get("/api/v1/person/businesses").json()["data"]["total"] == 0)

    # join the office by code
    j = riya.post("/api/v1/person/businesses/join", json={"org_code": office_code})
    chk("join by code creates a membership", j.status_code == 201 and j.json()["data"]["sector"] == "office")

    # gym admin invites riya -> she sees + accepts
    gym.post("/api/v1/businesses/invites", json={"email": riya_email, "role": "self_user"})
    inv = riya.get("/api/v1/person/invites").json()["data"]["items"]
    chk("invite appears in person's app", len(inv) == 1 and inv[0]["sector"] == "gym")
    acc = riya.post(f"/api/v1/person/invites/{inv[0]['invite_id']}/accept")
    chk("accept invite creates membership", acc.status_code == 201)

    # hub now shows both, grouped by sector
    biz = riya.get("/api/v1/person/businesses").json()["data"]
    chk("hub lists both businesses by sector", biz["total"] == 2 and "office" in biz["by_sector"] and "gym" in biz["by_sector"])
    prof = riya.get("/api/v1/person/me").json()["data"]
    chk("profile shows business_count=2, face not yet verified", prof["business_count"] == 2 and prof["face_verified"] is False)

    # isolation: a different person sees NONE of riya's businesses
    bob = person_login(f"bob_{uuid.uuid4().hex[:6]}@example.com")
    chk("another person sees only their own (none)", bob.get("/api/v1/person/businesses").json()["data"]["total"] == 0)

    ok = all(RESULTS)
    print(f"\nVERIFY_PERSON {'OK' if ok else 'FAILED'} ({sum(RESULTS)}/{len(RESULTS)})")
    if not ok:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
