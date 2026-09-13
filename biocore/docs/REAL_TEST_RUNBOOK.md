# BioCore — REAL Test Runbook

Testing the actual product: real Postgres, real Redis, real face recognition
(InsightFace SCRFD + ArcFace 512-d). **No fakes in the face path.**

This replaces `TEST_RUNBOOK.md` for real testing — that one documents the demo tenant and the
`FAKE_ZEPIRIS` stand-in, which are deliberately not used here.

---

## 0. What is real, and what is not

| Part | Status |
|---|---|
| Database | **Real.** Clean cluster, `biocore_real`, zero demo data |
| Redis (sessions, OTP) | **Real.** Redis 7.4.11 on `:6379` |
| Admin password / session / CSRF | **Real** |
| Admin 2FA | **OFF.** `DEMO_DISABLE_TOTP=true` — password alone signs you in. Set it to `false` to re-enable; secrets are still stored per admin, and `scripts/totp.py <email> --watch` prints a live code |
| Face detect / embed / match | **Real.** InsightFace `buffalo_l` on CPU, local |
| Passwords, CSRF, RLS, audit | **Real** |
| Government KYC | **STUBBED** — `FAKE_GOV_IDENTITY=true`. Real calls are billed (see §6) |
| Anti-spoof (PAD) | **NOT PRESENT** — a printed photo will pass (see §6) |
| BioVerify credential API | **OFF** — `CREDENTIAL_ENGINE=template`; its droplet can't load models |

---

## 1. Start everything (4 services, in this order)

```bash
# 1. Database
C:/Users/DELL/tools/pg17/bin/pg_ctl.exe -D C:/Users/DELL/AppData/Local/biocore_pgdata \
    -o "-p 5544" -l C:/Users/DELL/tools/pg5544.log start

# 2. Redis  (skip if something already answers on 6379)
C:/Users/DELL/tools/redis/redis-server.exe --port 6379 --save "" --appendonly no

# 3. Face engine  (first run downloads ~300MB, then it is instant)
C:/Users/DELL/bcface/Scripts/python.exe biocore/face-engine/server.py

# 4. Backend  (loads .env.real, NOT .env)
cd biocore/backend
set -a; . ./.env.real; set +a
.venv/Scripts/python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8080

# 5. Frontend
cd biocore/frontend
PATH="/c/Users/DELL/tools/node24:$PATH" node node_modules/next/dist/bin/next dev -p 3001
```

Check all five are alive:

```bash
curl -s http://127.0.0.1:8080/api/v1/health     # {"status":"ok"}
curl -s http://127.0.0.1:8099/health            # {"model":"buffalo_l"}
curl -s -o /dev/null -w "%{http_code}\n" http://127.0.0.1:3001/member/login   # 200
C:/Users/DELL/tools/redis/redis-cli.exe -p 6379 ping                       # PONG
```

**Node must be v24.** The system `node` is v14 and Next.js refuses to start on it. In Git Bash
the PATH entry must be POSIX-form (`/c/Users/...`), not `C:/Users/...`.

---

## 2. The one-command check

```bash
cd biocore/backend
set -a; . ./.env.real; set +a
.venv/Scripts/python.exe scripts/real_journey.py http://127.0.0.1:8080/api/v1
```

Expected: **`REAL JOURNEY: 19 passed, 0 failed`**. It runs the whole thing — organisation
onboarding, invite, person sign-in with a real OTP, self-onboarding with a real face,
gate entry, stranger rejection, and walk-up recognition.

To prove the face engine itself is doing real recognition (not comparing bytes):

```bash
C:/Users/DELL/bcface/Scripts/python.exe scripts/prep_faces.py
```

Expected: `A vs A2 (same person, different capture): score≈0.98 match=True` and
`A vs B (different people): score≈-0.07 match=False`.

---

## 3. Testing each step by hand (API)

Every step below is what the one-command check does, broken out so you can run them one at a
time and see the response.

### Step 1 — The organisation onboards

```bash
curl -s -X POST http://127.0.0.1:8080/api/v1/admin/tenants \
  -H "Content-Type: application/json" \
  -d '{"name":"Acme Manufacturing","org_code":"ACME-001","vertical":"office",
       "plan":"starter","admin_email":"ops@acmemfg.co.in",
       "admin_password":"Str0ng-Ops-Passw0rd!","admin_name":"Ops Manager"}'
```

**Expect `201`.** A `totp_provisioning_uri` comes back and the secret is stored, but
you do not need it while `DEMO_DISABLE_TOTP=true`.

> Email domains must be ordinary. `.test`, `.invalid` and `.localhost` are rejected by the
> email validator as reserved.

### Step 2 — The admin signs in

```bash
curl -s -c cookies.txt -X POST http://127.0.0.1:8080/api/v1/auth/login   -H "Content-Type: application/json"   -d '{"email":"ops@acmemfg.co.in","password":"Str0ng-Ops-Passw0rd!"}'

# a wrong password must still be refused
curl -s -X POST http://127.0.0.1:8080/api/v1/auth/login -H "Content-Type: application/json"   -d '{"email":"ops@acmemfg.co.in","password":"wrong-password"}'
```

**Expect `200` then `401`.** Password alone signs you in (`DEMO_DISABLE_TOTP=true`); passwords,
sessions and CSRF are untouched. To put two-factor back, set `DEMO_DISABLE_TOTP=false` and
restart — every admin already has a secret, and `scripts/totp.py <email> --watch` prints a
live code.

Every later admin call needs the session cookie **and** the CSRF header:
`-b cookies.txt -H "X-CSRF-Token: <the csrf cookie value>"`.

### Step 3 — Pair a gate terminal

```bash
curl -s -b cookies.txt -H "X-CSRF-Token: <csrf>" -X POST \
  http://127.0.0.1:8080/api/v1/devices \
  -H "Content-Type: application/json" -d '{"name":"Main Gate"}'
```

**Expect `201`** with a `pairing_token`. Keep it — the gate authenticates with it, never with
an admin session.

### Step 4 — Invite a person

```bash
curl -s -b cookies.txt -H "X-CSRF-Token: <csrf>" -X POST \
  http://127.0.0.1:8080/api/v1/businesses/invites \
  -H "Content-Type: application/json" -d '{"email":"asha@mailbox.co.in","role":"member"}'
```

**Expect `201`.**

### Step 5 — The person signs in (one-time code)

```bash
curl -s -X POST http://127.0.0.1:8080/api/v1/person/auth/otp/request \
  -H "Content-Type: application/json" -d '{"email":"asha@mailbox.co.in"}'

# no mail server here, so read the code the backend actually issued:
C:/Users/DELL/tools/redis/redis-cli.exe -p 6379 get "otp:asha@mailbox.co.in"

curl -s -c person.txt -X POST http://127.0.0.1:8080/api/v1/person/auth/otp/verify \
  -H "Content-Type: application/json" -d '{"email":"asha@mailbox.co.in","otp":"<code>"}'
```

**Expect `200`.** The code is a real 6-digit OTP with a real TTL — it expires.

### Step 6 — Accept the invite

```bash
curl -s -b person.txt http://127.0.0.1:8080/api/v1/person/invites
curl -s -b person.txt -H "X-CSRF-Token: <csrf>" -X POST \
  http://127.0.0.1:8080/api/v1/person/invites/<invite_id>/accept
```

**Expect** the invite listed, then `201` with a `membership_id`.

### Step 7 — Consent and capture the face

```bash
curl -s -b person.txt -H "X-CSRF-Token: <csrf>" -X POST \
  http://127.0.0.1:8080/api/v1/person/verify/<membership_id>/start \
  -H "Content-Type: application/json" \
  -d '{"consents":["identity_verification","government_data_processing","live_face_capture",
       "face_to_government_match","entry_template_creation","entry_authentication"]}'
```

**Expect `201`** with a `tenant_subject_id` — save it, the gate needs it.

```bash
curl -s -b person.txt -H "X-CSRF-Token: <csrf>" -X POST \
  http://127.0.0.1:8080/api/v1/person/verify/<membership_id>/complete \
  -H "Content-Type: application/json" \
  -d '{"reference":"<membership_id>","image":"data:image/jpeg;base64,<their photo>"}'
```

**Expect `200`** with `{"verified":true,...,"credential_id":"..."}`.

**Negative test that matters:** send `"image":"data:image/jpeg;base64,Zm9vYmFy"` (garbage).
**Expect `503`**, not a credential. The engine must fail closed — a credential minted from a
capture with no face in it would be valid for its whole lifetime.

### Step 8 — Gate entry, with an ID claimed

```bash
curl -s -X POST http://127.0.0.1:8080/api/v1/entry/match \
  -H "X-Device-Token: <pairing_token>" -H "Content-Type: application/json" \
  -d '{"subject_id":"<tenant_subject_id>","image":"data:image/jpeg;base64,<a NEW photo>"}'
```

**Expect** `{"decision":"allow","reason":"ALLOWED","confidence_band":"high"}`.

Use a **different photo of the same person** than the one enrolled. If a re-used identical
photo is the only thing that matches, you are testing byte equality, not face recognition.

Then send a **different person's** photo with the same `subject_id`.
**Expect** `{"decision":"deny","reason":"FACE_MISMATCH"}`.

### Step 9 — Walk-up entry, no ID claimed (1:N)

```bash
curl -s -X POST http://127.0.0.1:8080/api/v1/entry/identify \
  -H "X-Device-Token: <pairing_token>" -H "Content-Type: application/json" \
  -d '{"image":"data:image/jpeg;base64,<their photo>","direction":"in"}'
```

**Expect** `{"matched":true,"name":"...","decision":"allow"}`, and `matched:false` for a
stranger. This is the guard console's flow.

### Step 10 — Revoke and erase

```bash
curl -s -b cookies.txt -H "X-CSRF-Token: <csrf>" -X POST \
  http://127.0.0.1:8080/api/v1/face-credentials/<credential_id>/revoke
# then repeat step 8 -> expect deny / CREDENTIAL_EXPIRED

curl -s -b cookies.txt -H "X-CSRF-Token: <csrf>" -X DELETE \
  http://127.0.0.1:8080/api/v1/face-credentials/<credential_id>
# status becomes "erased" and the stored template is zeroized
```

---

## 4. Testing in the browser (with a real webcam)

Camera only works on `localhost` or `https` — use this PC, not a phone over the LAN.

| Screen | URL | Status |
|---|---|---|
| Admin | http://localhost:3001/admin/login | **Works.** Needs the 2FA code |
| Person app | http://localhost:3001/member/login | **Works** |
| Guard console | http://localhost:3001/guard?token=&lt;pairing_token&gt; | **Works** — walk-up, calls `/entry/identify` |
| Kiosk | http://localhost:3001/kiosk?token=&lt;pairing_token&gt; | **Default mode BROKEN** (see below) |

Browser run-through:

1. `/admin/login` → sign in with 2FA → **Devices** → create a gate → copy its token.
2. **Users / Invites** → invite yourself by email.
3. `/member/login` → request a code → read it from Redis (§3 step 5) → sign in.
4. Accept the invite → consent → **capture your face with the webcam**.
5. Open `/guard?token=…` → look at the camera → you are recognised by name.
6. Have someone else look at it → not recognised.

**The kiosk's default check-in mode calls the legacy `/faces/search`, which needs the ZepIris
service.** ZepIris is being removed and is not running, so that mode returns a 500. Use
`/guard` for gate testing. The same applies to `/person/face/enroll` (the old person-app
capture) — the modern `/person/verify/*` path used above replaces it.

---

## 5. Resetting to a clean slate

```bash
C:/Users/DELL/tools/pg17/bin/psql.exe -h 127.0.0.1 -p 5544 -U postgres -d postgres \
  -c "DROP DATABASE biocore_real" -c "CREATE DATABASE biocore_real OWNER biocore"
cd biocore/backend && set -a; . ./.env.real; set +a && .venv/Scripts/python.exe -m alembic upgrade head
```

`biocore` (the old demo database) is untouched and still there if you want it.

---

## 6. Two things that are NOT real yet — decide before any customer sees this

**Government KYC is stubbed.** `FAKE_GOV_IDENTITY=true`. The Sandbox adapter is wired and its
live handshake has been proven, but PAN/Aadhaar calls are **billed against real NSDL/UIDAI**.
Flip `FAKE_GOV_IDENTITY=false` only deliberately. Until then "verified against a government
record" is not actually happening.

**There is no anti-spoof.** `/liveness` checks a real face is present, big enough and sharp —
that is a *quality* gate. **A printed photo or a phone screen held to the camera will pass.**
Real presentation-attack detection needs a separate model (MiniFASNet or equivalent) that is
not wired. Do not describe the product as spoof-proof, and do not put it on a door where that
matters, until it is.
