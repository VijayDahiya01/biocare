"""Acceptance-criteria checker — verifies each Build Plan §2 criterion against a
real Postgres and prints a PASS/FAIL report. A runnable substitute for the
"recorded walkthrough" handover artifact.

    python -m scripts.acceptance          # uses .env (FAKE_ZEPIRIS/REDIS on for local)

Runs in-process (TestClient) so it can read the in-process OTP and make DB-level
assertions (RLS, raw-image retention, audit immutability).
"""
import uuid

from fastapi.testclient import TestClient
from sqlalchemy import select, text

from app.core.db import SessionLocal, bypass_rls, set_tenant_guc
from app.core.redis_client import client as redis
from app.core.redis_client import otp_key
from app.main import app
from app.models import FaceRecord

RESULTS: list[tuple[str, bool, str]] = []


def check(crit: str, ok: bool, detail: str = "") -> None:
    RESULTS.append((crit, ok, detail))
    print(f"  [{'PASS' if ok else 'FAIL'}] {crit}" + (f" — {detail}" if detail else ""))


def info(crit: str, detail: str) -> None:
    print(f"  [INFO] {crit} — {detail}")


def _admin(tc: TestClient):
    org = f"AC-{uuid.uuid4().hex[:8]}"
    email = f"admin_{uuid.uuid4().hex[:6]}@acme.com"
    from urllib.parse import parse_qs, urlparse

    import pyotp
    r = tc.post("/api/v1/admin/tenants", json={"name": "Acc", "org_code": org, "vertical": "office",
                                               "admin_email": email, "admin_password": "supersecret123"})
    uri = r.json()["data"]["totp_provisioning_uri"]
    secret = parse_qs(urlparse(uri).query)["secret"][0]
    tc.post("/api/v1/auth/login", json={"email": email, "password": "supersecret123",
                                        "totp_code": pyotp.TOTP(secret).now()})
    tc.headers.update({"X-CSRF-Token": tc.cookies.get("csrf")})
    return org, email, secret


def main() -> None:
    a = TestClient(app)
    orgA, adminA_email, adminA_secret = _admin(a)

    print("\n2.1 Self-registration")
    r = a.post("/api/v1/register", json={"org_code": "NOPE-9999", "first_name": "X", "email": f"x{uuid.uuid4().hex[:5]}@x.com"})
    check("invalid org code rejected", r.status_code == 400 and r.json()["error"]["code"] == "INVALID_ORG_CODE", f"{r.status_code}")

    m_email = f"mem_{uuid.uuid4().hex[:6]}@acme.com"
    r = a.post("/api/v1/register", json={"org_code": orgA, "first_name": "Mem", "email": m_email})
    check("valid registration creates pending account", r.status_code == 201 and r.json()["data"]["status"] == "pending_email")
    r2 = a.post("/api/v1/register", json={"org_code": orgA, "first_name": "Mem", "email": m_email})
    check("duplicate email -> 409", r2.status_code == 409 and r2.json()["error"]["code"] == "EMAIL_EXISTS")

    # OTP required before a session exists
    m = TestClient(app)
    code = redis.get(otp_key(m_email))
    check("email OTP issued on registration", bool(code))
    r = m.post("/api/v1/consent", json={"purpose": "attendance", "method": "self",
               "acknowledgements": {"purpose_understood": True, "sensitivity_understood": True,
                                    "rights_understood": True, "freely_given": True}})
    check("action blocked before OTP verify (401)", r.status_code == 401)

    m.post("/api/v1/auth/otp/verify", json={"email": m_email, "otp": code})
    m.headers.update({"X-CSRF-Token": m.cookies.get("csrf")})
    # consent gate: enroll before consent -> 403
    r = m.post("/api/v1/faces/enroll", json={"image": "data:image/jpeg;base64,Zm9v"})
    check("face enroll blocked without consent (403)", r.status_code == 403 and r.json()["error"]["code"] == "CONSENT_REQUIRED")

    m.post("/api/v1/consent", json={"purpose": "attendance", "method": "self",
           "acknowledgements": {"purpose_understood": True, "sensitivity_understood": True,
                                "rights_understood": True, "freely_given": True}})
    enr = m.post("/api/v1/faces/enroll", json={"image": "data:image/jpeg;base64,Zm9v"}).json()["data"]
    uid = enr["face_id"]
    # raw image not retained
    db = SessionLocal()
    with bypass_rls(db):
        fr = db.execute(select(FaceRecord).where(FaceRecord.user_id == uid)).scalar_one()
    check("raw image not retained (minio_object_key NULL)", fr.minio_object_key is None)
    db.close()

    print("\n2.2 Kiosk check-in (toggle)")
    dev = a.post("/api/v1/devices", json={"name": "AC-KIOSK"}).json()["data"]
    tok = {"X-Device-Token": dev["pairing_token"]}
    s1 = a.post("/api/v1/faces/search", headers=tok, json={"image": "data:image/jpeg;base64,Zm9v", "action": "auto"}).json()["data"]
    s2 = a.post("/api/v1/faces/search", headers=tok, json={"image": "data:image/jpeg;base64,Zm9v", "action": "auto"}).json()["data"]
    check("recognised face records an event", s1.get("match") is True and s1.get("event") == "check_in")
    check("toggle alternates check-in/out", s2.get("event") == "check_out")
    log = a.get("/api/v1/attendance").json()["data"]
    check("event appears in attendance log", log["total"] >= 2)
    info("spoof rejected / blacklist alert", "verified by suite (test_phase1_flow::test_spoof_is_rejected_at_kiosk; kiosk_service blacklist path)")

    print("\n2.3 Multi-tenancy isolation")
    b = TestClient(app)
    orgB, _, _ = _admin(b)
    r = b.post(f"/api/v1/devices/{dev['device_id']}/disable")
    check("cross-tenant resource -> 404 (not other tenant's data)", r.status_code == 404)
    db = SessionLocal()
    try:
        # RLS blocks an UNFILTERED read to the caller's tenant only
        tenant_a_id = a.get("/api/v1/auth/me").json()["data"]["tenant_id"]
        set_tenant_guc(db, tenant_a_id)
        seen = {str(x[0]) for x in db.execute(text("SELECT DISTINCT tenant_id FROM users")).fetchall()}
        check("RLS hides other tenants on unfiltered query", seen == {tenant_a_id}, f"tenants visible: {len(seen)}")
        set_tenant_guc(db, None)
        none_rows = db.execute(text("SELECT count(*) FROM users")).scalar_one()
        check("no tenant context -> 0 rows", none_rows == 0)
    finally:
        db.close()

    print("\n2.4 DPDP")
    exp = m.get("/api/v1/me/data/export").json()["data"]
    check("data export returns the subject's data", "profile" in exp and "consents" in exp and "attendance" in exp)
    victim = a.post("/api/v1/admin/enroll", json={
        "person_type": "patient", "first_name": "Erase", "last_name": "Me", "purpose": "t",
        "image": "data:image/jpeg;base64,Zm9v", "consent_method": "in_person_verbal",
        "person_present": True, "purpose_explained": True, "person_consented": True, "admin_responsible": True,
    }).json()["data"]
    er = a.request("DELETE", f"/api/v1/users/{victim['user_id']}").json()["data"]
    check("erasure clears all four stores", set(er["stores_cleared"]) >= {"milvus", "minio", "postgres", "redis"})
    check("erasure independently verified", all(er["verified"].values()))
    check("erasure certificate issued", er["erasure_ref"].startswith("ERA-") and er["certificate_url"].startswith("/api/v1/documents/certificates/"))
    aud = a.get("/api/v1/audit?action=FACE_SEARCH").json()["data"]["items"]
    check("face ops audited with request_id", bool(aud) and all(e.get("request_id") for e in aud[:5]))
    db = SessionLocal()
    try:
        with bypass_rls(db):
            try:
                db.execute(text("UPDATE audit_logs SET action='TAMPER' WHERE action='FACE_SEARCH'"))
                db.commit()
                immutable = False
            except Exception:
                db.rollback()
                immutable = True
        check("audit log is append-only (UPDATE rejected)", immutable)
    finally:
        db.close()

    print("\n2.5 Security")
    # fresh client to inspect login cookies
    s = TestClient(app)
    import pyotp
    rl = s.post("/api/v1/auth/login", json={"email": adminA_email, "password": "supersecret123",
                                            "totp_code": pyotp.TOTP(adminA_secret).now()})
    setc = " ".join(rl.headers.get_list("set-cookie")).lower()
    check("session cookie HttpOnly + SameSite", "httponly" in setc and "samesite=strict" in setc)
    info("session cookie Secure", "enabled in prod via COOKIE_SECURE=true (off for local http)")
    r = a.post("/api/v1/devices", headers={"X-CSRF-Token": "wrong"}, json={"name": "x"})
    check("mutation with bad CSRF rejected (403)", r.status_code == 403 and r.json()["error"]["code"] == "CSRF_FAILED")
    r = s.post("/api/v1/auth/login", json={"email": adminA_email, "password": "supersecret123"})
    check("admin login requires TOTP", r.status_code == 401 and r.json()["error"]["code"] == "TOTP_REQUIRED")
    info("TLS 1.3 / HTTP refused", "enforced by the nginx gateway / K8s ingress (not exercisable on local http)")

    # summary
    passed = sum(1 for _, ok, _ in RESULTS if ok)
    total = len(RESULTS)
    print(f"\n=== ACCEPTANCE: {passed}/{total} criteria PASS ===")
    if passed != total:
        print("FAILURES:")
        for c, ok, d in RESULTS:
            if not ok:
                print(f"  - {c} ({d})")
        raise SystemExit(1)


if __name__ == "__main__":
    main()
