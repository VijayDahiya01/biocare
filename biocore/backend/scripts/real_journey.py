"""REAL product journey - no fakes in the face path.

  organisation onboards -> admin signs in -> invites a person by email
  -> person signs in with a real emailed OTP -> accepts the invite -> consents
  -> captures their face -> walks up to the gate -> recognised -> checks in -> checks out

Real Postgres (clean db), real Redis, real InsightFace engine (SCRFD + ArcFace
512-d). The faces are two genuinely different people, and the gate photo is a DIFFERENT
capture of the enrolled person - so a match can only come from real recognition.
"""
import io
import os
import sys
import uuid

import httpx

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8080/api/v1"
FACES = os.path.dirname(os.path.abspath(__file__)) + "/testfaces"

# The gate test is only meaningful with a DIFFERENT capture of the same person — matching the
# identical file proves byte equality, not recognition. The dev BioVerify fake can only do the
# latter, so set BYTE_EXACT=1 when running against it and the run says so out loud.
BYTE_EXACT = os.environ.get("BYTE_EXACT", "").lower() in ("1", "true", "yes")
GATE_FACE = "personA" if BYTE_EXACT else "personA2"
GATE_NOTE = ("the SAME capture - dev fake, matches bytes not faces"
             if BYTE_EXACT else "a DIFFERENT capture of the same person")

passed = failed = 0


def step(label, ok, detail=""):
    global passed, failed
    if ok:
        passed += 1
    else:
        failed += 1
    print(f"  [{'PASS' if ok else 'FAIL'}] {label}" + (f" - {detail}" if detail else ""))


def face(name):
    return io.open(f"{FACES}/{name}.b64", encoding="utf-8").read()


def csrf(c):
    return {"X-CSRF-Token": c.cookies.get("csrf") or ""}


def otp_for(email):
    """Read the OTP the backend actually issued. In production this arrives by email; here we
    read the same Redis key (`otp:<email>`) the mailer would have rendered from."""
    import redis as redis_lib
    r = redis_lib.Redis.from_url(os.environ.get("REDIS_URL", "redis://127.0.0.1:6379/0"))
    v = r.get(f"otp:{email.lower()}")
    return v.decode() if isinstance(v, bytes) else v


admin = httpx.Client(base_url=BASE, timeout=120.0, follow_redirects=True)
person = httpx.Client(base_url=BASE, timeout=120.0, follow_redirects=True)
gate = httpx.Client(base_url=BASE, timeout=120.0, follow_redirects=True)

org_code = f"ACME-{uuid.uuid4().hex[:6].upper()}"
admin_email = f"ops_{uuid.uuid4().hex[:6]}@acmemfg.co.in"
person_email = f"asha_{uuid.uuid4().hex[:6]}@mailbox.co.in"
ADMIN_PW = "Str0ng-Ops-Passw0rd!"

print("\n=== STEP 1. The organisation onboards ===")
r = admin.post("/admin/tenants", json={
    "name": "Acme Manufacturing", "org_code": org_code, "vertical": "office", "plan": "starter",
    "admin_email": admin_email, "admin_password": ADMIN_PW, "admin_name": "Ops Manager"})
step("organisation created", r.status_code in (200, 201), f"HTTP {r.status_code} org={org_code}")
if r.status_code not in (200, 201):
    print(r.text[:400])
    sys.exit(1)
d = r.json()["data"]
print(f"        org_code={org_code}  admin={admin_email}")


print("\n=== STEP 2. The admin signs in ===")
r = admin.post("/auth/login", json={"email": admin_email, "password": ADMIN_PW})
step("admin signed in with password", r.status_code == 200, f"HTTP {r.status_code}")

# On a throwaway client, so a rejected login cannot disturb the session just established.
with httpx.Client(base_url=BASE, timeout=60.0) as probe:
    bad = probe.post("/auth/login", json={"email": admin_email, "password": "wrong-password"})
step("a wrong password is still refused", bad.status_code == 401,
     f"HTTP {bad.status_code} - passwords are still enforced")

print("\n=== STEP 3. The admin pairs a gate terminal ===")
r = admin.post("/devices", headers=csrf(admin), json={"name": "Main Gate"})
token = (r.json().get("data") or {}).get("pairing_token", "")
gate.headers["X-Device-Token"] = token
step("gate terminal paired", bool(token), f"HTTP {r.status_code}")

print("\n=== STEP 4. The admin invites a person by email ===")
r = admin.post("/businesses/invites", headers=csrf(admin),
               json={"email": person_email, "role": "member"})
step("invite sent", r.status_code in (200, 201), f"HTTP {r.status_code} -> {person_email}")
if r.status_code not in (200, 201):
    print(r.text[:400])
    sys.exit(1)

print("\n=== STEP 5. The person signs in to their own app (emailed OTP) ===")
r = person.post("/person/auth/otp/request", json={"email": person_email})
step("one-time code issued", r.status_code == 200, f"HTTP {r.status_code}")
code = otp_for(person_email)
step("code retrievable (stands in for the email)", bool(code), f"code={code}")
r = person.post("/person/auth/otp/verify", json={"email": person_email, "otp": code})
step("person signed in", r.status_code == 200, f"HTTP {r.status_code}")

print("\n=== STEP 6. The person sees and accepts the invite ===")
r = person.get("/person/invites")
data = r.json().get("data") or {}
items = data.get("items") if isinstance(data, dict) else data
items = items or []
step("invite visible to the person", len(items) > 0, f"{len(items)} invite(s)")
if not items:
    print(r.text[:400])
    sys.exit(1)
invite_id = items[0].get("invite_id") or items[0].get("id")
r = person.post(f"/person/invites/{invite_id}/accept", headers=csrf(person))
step("invite accepted", r.status_code in (200, 201), f"HTTP {r.status_code}")
membership_id = (r.json().get("data") or {}).get("membership_id")
print(f"        membership={membership_id}")

CONSENTS = ["identity_verification", "government_data_processing", "live_face_capture",
            "face_to_government_match", "entry_template_creation", "entry_authentication"]

print("\n=== STEP 7. The person consents and verifies themselves ===")
r = person.post(f"/person/verify/{membership_id}/start", headers=csrf(person),
                json={"consents": CONSENTS})
step("consents recorded, verification started", r.status_code in (200, 201),
     f"HTTP {r.status_code}")
if r.status_code not in (200, 201):
    print(r.text[:400])
    sys.exit(1)
sv = r.json()["data"]
subject_id = sv["tenant_subject_id"]
print(f"        subject={subject_id}  business={sv.get('business')}")

r = person.post(f"/person/verify/{membership_id}/complete", headers=csrf(person),
                json={"reference": membership_id, "image": face("personA")})
step("face captured -> real embedding -> credential issued", r.status_code in (200, 201),
     f"HTTP {r.status_code} {str(r.json().get('data', {}))[:90]}")
if r.status_code not in (200, 201):
    print(r.text[:500])

print("\n=== STEP 8. A capture with no face in it is refused ===")
r = person.post(f"/person/verify/{membership_id}/complete", headers=csrf(person),
                json={"reference": membership_id, "image": "data:image/jpeg;base64,Zm9vYmFy"})
step("garbage capture rejected", r.status_code >= 400, f"HTTP {r.status_code}")

print("\n=== STEP 9. They walk up to the gate ===")
d = gate.post("/entry/match", json={"subject_id": subject_id, "image": face(GATE_FACE)})
d = d.json().get("data", {}) if d.status_code == 200 else {"decision": f"HTTP {d.status_code}",
                                                          "reason": d.text[:120]}
step(f"gate ALLOWS them - {GATE_NOTE}", d.get("decision") == "allow",
     f"{d.get('decision')} / {d.get('reason')} / band={d.get('confidence_band')}")

print("\n=== STEP 10. A stranger tries to enter as them ===")
d2 = gate.post("/entry/match", json={"subject_id": subject_id, "image": face("personB")})
d2 = d2.json().get("data", {}) if d2.status_code == 200 else {"decision": f"HTTP {d2.status_code}"}
step("gate DENIES the stranger", d2.get("decision") == "deny" and d2.get("reason") == "FACE_MISMATCH",
     f"{d2.get('decision')} / {d2.get('reason')}")

print("\n=== STEP 11. The admin can see the verified person ===")
r = admin.get("/identity/subjects")
data = r.json().get("data") or {}
subs = data.get("items") if isinstance(data, dict) else data
subs = subs or []
mine = [s for s in subs if str(s.get("tenant_subject_id") or s.get("id")) == subject_id]
step("person listed as verified", bool(mine) and
     (mine[0].get("verification_status") == "verified" if mine else False),
     f"{len(subs)} subject(s); {mine[0].get('verification_status') if mine else 'not found'}")

print("\n=== STEP 12. Walk-up at the guard console (no ID claimed, 1:N) ===")
r = gate.post("/entry/identify", json={"image": face(GATE_FACE), "direction": "in"})
w = r.json().get("data", {}) if r.status_code == 200 else {"matched": None, "reason": r.text[:120]}
step("walk-up RECOGNISES the enrolled person", bool(w.get("matched")),
     f"matched={w.get('matched')} name={w.get('name')} {w.get('decision')}/{w.get('reason')}")

r = gate.post("/entry/identify", json={"image": face("personB"), "direction": "in"})
w2 = r.json().get("data", {}) if r.status_code == 200 else {"matched": None}
step("walk-up does NOT recognise a stranger", not w2.get("matched"),
     f"matched={w2.get('matched')} {w2.get('decision')}/{w2.get('reason')}")

print(f"\n=== REAL JOURNEY: {passed} passed, {failed} failed ===")
sys.exit(1 if failed else 0)
