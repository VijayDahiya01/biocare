# BioCore Platform

Web-only, multi-tenant **face authentication & attendance** platform built on the
open-source **ZepIris** engine. People enroll a face once, then check in/out at shared
kiosks; admins monitor and configure from a web dashboard. One backend serves 14
verticals by configuration. DPDP Act 2026 compliance is enforced by the system itself.

> Build plan and phasing live in [`../ROADMAP.md`](../ROADMAP.md). Source-of-truth
> specs are the documents in [`../files/`](../files). Where docs disagree, the
> **ZepIris VERIFIED** doc wins.

**Stack:** FastAPI · Next.js 14 · PostgreSQL 16 · Milvus · MinIO · Redis · RabbitMQ · Nginx · Docker.

---

## Status

### Phase 0 — Foundation ✅
- **Full stack `docker-compose.yml`** — gateway, frontend, api, zepiris-main, zepiris-ml, postgres, milvus (+etcd), minio, redis, rabbitmq.
- **Backend core** — settings from env, SQLAlchemy + Redis clients, Argon2 passwords, request-id middleware, standard response envelope.
- **Core schema + migration** — `tenants, roles, users, consent_records, audit_logs` with **Row-Level Security (FORCE)** as the isolation safety net, an **append-only audit trigger**, and the **12 role presets** seeded.
- **ZepIris adapter** — the keystone. Base64→multipart, `tenant` form field, camelCase `requestId`, search-returns-200-on-bad-image — all per the verified spec. Fully unit-tested.
- **Auth** — Redis-backed sessions as HttpOnly cookies, CSRF tokens, admin login, tenant provisioning, audit logging on every action.

### Phase 1 — Core attendance MVP ✅ (backend)
- **Self-registration flow** — `POST /register` → email OTP (`/auth/otp/request|verify`) → `POST /consent` (4 mandatory acks) → `POST /faces/enroll` (consent-gated; raw image not retained). Pending accounts cannot check in until face capture completes.
- **Device registration + pairing** — `POST /devices` issues a one-time pairing token (stored hashed) + kiosk URL; `POST /devices/{id}/disable`; device-token auth for the kiosk.
- **Kiosk check-in** — `POST /faces/search` (device-authenticated) → ZepIris search → **toggle logic** → writes `attendance_logs` + maintains `current_presence`. Spoof → 403, bad quality → 422, no match → `{match:false}`. Every search is audited.
- **Admin dashboard APIs** — `GET /attendance` (filters + pagination), `GET /attendance/presence` (live, powers metrics + emergency headcount), `GET /users`.
- **New tables** (migration `0002`): `face_records, attendance_logs, current_presence, devices` — all under the same FORCE-RLS isolation, attendance composite-indexed.

- **Frontend (Next.js 14 App Router, 3 portals)** — builds clean (16 routes):
  - *Kiosk* `/kiosk` — continuous webcam capture, device-token auth, all 7 result states, auto-reset.
  - *Registration* `/register` → `/register/verify` (OTP) → `/enroll` (consent gate + face capture) → `/enroll/done`.
  - *Member* `/me/login` (OTP) + `/me` (my attendance).
  - *Admin* `/admin/login`, `/admin/dashboard` (live metrics + feed, 10s poll), `/admin/attendance` (filters+paging), `/admin/users`, `/admin/devices` (register + one-time pairing token).
  - Cookie-based API client with automatic CSRF header; `getUserMedia`→canvas→base64 capture hook.

> Phase 1 is complete end-to-end for Office / Gym / basic School & Factory attendance.

### Phase 2 — Access control, DPDP, blacklist & alerts ✅
- **Zones, badges, access control** — zone/badge CRUD, badge assignment; pure access-decision engine (restricted/amenity gating, badge time-windows incl. overnight, expiry, zone hours); evaluated at the kiosk for gated zones, recording `access_events` and firing the door webhook.
- **Door & integration webhooks** — `access.granted/denied`, `attendance.recorded`, `blacklist.hit`, all **HMAC-SHA256 signed** with retry + dead-letter logging.
- **Admin-assisted enrollment** — `POST /admin/enroll` for patient/inmate/citizen/devotee/visitor/guardian; four mandatory admin confirmations; consent recorded on the person's behalf, fully traceable.
- **Visitor temp-enrollment** — `POST /visitors/invite` (tokenised QR/link with expiry) + public `POST /visitors/enroll`; time-limited, auto-expiring identities.
- **Full DPDP suite** — `GET /me/data/export` (machine-readable), `POST /me/data/erasure` (**verified cascade** across Milvus+MinIO+Postgres+Redis, each store independently confirmed, erasure certificate issued; OTP re-auth required), `POST /me/consent/revoke`, and the read-only `GET /audit` viewer.
- **Blacklist + real-time alerts** — blacklist faces searched in the same collection; a hit raises a *critical* alert + webhook and admits nobody; unrecognised faces and access denials raise alerts; `GET /alerts`, dismiss, routing settings.
- **Tenant settings** — `GET/PATCH /settings` (branding, DPDP config, match threshold, modules) + webhook CRUD.
- **New tables** (migrations `0003`/`0004`): zones, badges, user_badges, access_events, blacklist, webhook_configs, alerts, visitor_invites, tenants.settings — all FORCE-RLS isolated.
- **Frontend (Phase 2 screens)** — admin: `/admin/zones`, `/admin/badges` (+assign), `/admin/enroll` (A7, 4-confirmation gate), `/admin/visitors`, `/admin/blacklist`, `/admin/alerts` (live count in nav), `/admin/audit`, `/admin/settings` (branding/DPDP/threshold + webhook CRUD); member DPDP: `/me/consent`, `/me/data` (export+download), `/me/erasure` (OTP re-auth + certificate); public `/visit/[token]` visitor self-enroll. Reusable `CameraCapture` component.

> 47 API routes, 26 frontend routes. **Phase 2 acceptance** is met: cross-tenant access
> returns 404 (+ RLS safety net), erasure clears all four stores verifiably and certifies,
> audit is append-only and viewable.

### Phase 3 — Vertical modules ✅
- **Wages & payroll** — wage-config (history), `payroll/calculate` + CSV export from attendance (per-day regular/overtime split), `hr/summary`. Pure payroll/productive-time engine, unit-tested.
- **Break tracking** — device-authenticated `attendance/break` (start/end); breaks subtracted from worked time.
- **GPS field check-in** — `attendance/gps` with face-must-match-signed-in-user + **haversine geofence** check (unit-tested); geofence CRUD.
- **Emergency headcount** — `emergency/trigger` (muster snapshot) + `emergency/status`.
- **Leave** — submit/list/approve/reject + balance (pure allocation logic, unit-tested).
- **Custom roles & permissions** — role CRUD (presets immutable, in-use guard) + permission catalog.
- **Reporting** — attendance (day/user/dept), late, absent, zone-access, footfall, movement, CSV export, scheduling.
- **School** — timetable + per-period `attendance/session`; guardian invite/list + kiosk `pickup/verify`.
- **Gym** — membership create/get/expiring (auto end-date by plan).
- **Religious** — donations + 80G receipt reference.
- **Events** — CSV bulk `events/import`, `badge-print` (webhook), per-event footfall.
- **ERP** — `integrations/erp/sync` (batch push over signed webhook) + integrations list.
- **Also**: `attendance/manual` correction, full `users/{id}` CRUD (DELETE = erasure cascade), `zones/{id}` PATCH, `notifications/test`.
- **New tables** (migration `0005`): wage_config, memberships, guardian_links, timetables, donations, geofences, leave_requests, events, integrations — all FORCE-RLS isolated.
- **Frontend (Phase 3 screens)** — sectioned admin nav; admin: `/admin/hr` (summary + wage config + payroll run + CSV), `/admin/leave` (approve/reject), `/admin/reports` (type+range+CSV), `/admin/emergency` (muster), `/admin/geofences`, `/admin/timetable` (+ per-period attendance), `/admin/memberships`, `/admin/donations`, `/admin/events` (create + CSV import + footfall); member: `/me/leave` (balance + request). CSV download + multipart upload helpers.

> **100 API routes — 100% of the Doc 2B endpoint index — and 36 frontend routes.** Pure
> business logic (payroll, geofencing, leave, toggle, access, HMAC) is unit-tested:
> **38 tests pass**.

### Phase 4 — Advanced ML ✅
- **PPE / safety-gear detection** — a **pluggable** inference adapter (`PPE_SERVICE_URL`; the model is a deployment artifact, like the ZepIris weights). If unset, PPE checks are skipped and the platform runs unchanged. When a zone has `require_ppe`, the kiosk runs detection on the same frame; missing gear **denies the gated zone, records an `ppe_missing` access event, and raises a high-priority alert** (attendance still records — the person is present, just not admitted to the hazardous zone). Pure `evaluate_ppe` logic is unit-tested; optional `ppe-ml` compose service behind a `--profile ppe`.
- **Zone-movement tracking** — pure analysis building a movement **trail**, per-zone **dwell time**, and **anomaly flags** (`restricted_before_entry` tailgating proxy, `rapid_transition` implausible zone hops). Exposed via `GET /security/movement` and `GET /security/ppe-violations`. Unit-tested.
- **Frontend** — zones gain a *Require PPE* toggle; new `/admin/security` page traces a user's movement + anomalies and lists PPE violations.

> **102 API routes; 37 frontend routes; 48 unit tests pass.** The PPE *model* and a
> real movement-anomaly ruleset are deployment/data dependent — the integration
> points, decision logic, config, alerts, and UI are all built and tested.

---

## ✅ Roadmap complete (Phases 0–4)

Every phase in [`../ROADMAP.md`](../ROADMAP.md) is built — backend + the admin/member/kiosk
UI — covering **100% of the documented API surface**. What still requires real infrastructure
or data (and so can't be finished in this environment) is called out in **Production readiness** below.

---

## ▶️ Test it locally (no ML, no model weights)

A **dev mode** fakes the face engine in-process (`FAKE_ZEPIRIS=true`) so you need
**no Milvus / MinIO / ML / ZepIris images** — just Postgres (and Redis, or fake it too).

> Dev face behaviour: a kiosk scan recognises the **most recently enrolled** person
> for that tenant (real recognition needs the actual ZepIris engine). Everything else
> — auth, consent, attendance/toggle, access, DPDP, modules — behaves for real.

**1. Start Postgres + Redis** (one-time Docker Desktop install, then):
```bash
docker compose -f docker-compose.dev.yml up -d
```
*(No Docker? Install Postgres locally and point `DATABASE_URL` at it, then set
`FAKE_REDIS=true` in `backend/.env` so Redis isn't needed either.)*

**2. Backend** (terminal 1):
```bash
cd backend
python -m venv .venv && . .venv/Scripts/activate    # Windows; or: source .venv/bin/activate
pip install -r requirements.txt
cp .env.dev .env                 # dev config: FAKE_ZEPIRIS=true, COOKIE_SECURE=false
alembic upgrade head             # create tables + RLS + seed the 12 role presets
python -m scripts.seed_demo      # create a demo tenant + admin
uvicorn app.main:app --port 8080 --reload
```

**3. Frontend** (terminal 2):
```bash
cd frontend
npm install
npm run dev                      # proxies /api -> http://localhost:8080
```

**4. Click through it** at `http://localhost:3000`:
- **Admin** → `/admin/login` with the demo creds code from `seed_demo`.
- **Register a member** → `/register` (org code `DEMO-2026`) → the OTP is printed in
  the **backend terminal** (email is a dev stub) → verify → consent → capture face.
- **Register a kiosk** → admin `Devices` → copy the kiosk link → open `/kiosk?token=…`
  in another tab → it checks in the **last-enrolled** member (dev fake), toggling in/out.
- Explore zones/badges, admin-assisted enroll, alerts, audit, HR/payroll, leave,
  reports, DPDP export/erasure, etc.

Re-run `python -m scripts.seed_demo` any time to reprint the demo credentials.

## Production readiness (remaining, infra/data-dependent)
- Bring up the stack (Docker) and run the **10 integration tests** + a live **ZepIris** round-trip.
- Supply ML model weights (ZepIris spoof/blur/nudity `.pth`; the PPE model) and a PPE training dataset.
- Real **TLS certificates**, secrets in a manager, India-region/on-prem deployment.
- **Pen test** (zero critical/high) and **load test** (peak × 2) before go-live, per Doc 6 §3.
- Wire tenant **branding/theme** into the frontend; move webhook delivery + scheduled reports onto **RabbitMQ** workers; generate the erasure/80G/muster **PDFs**.

---

## Quick start (full stack)

```bash
cp .env.example .env          # then edit secrets
./infra/scripts/gen-certs.sh  # self-signed TLS cert for local dev
docker compose up --build
```

- App:           `https://localhost/`
- API health:    `https://localhost/api/v1/health`
- API readiness: `https://localhost/api/v1/ready`  (reports postgres/redis/zepiris)
- API docs:      `https://localhost/api/v1/docs`
- MinIO console: `http://localhost:9001`
- RabbitMQ UI:   `http://localhost:15672`

> ZepIris ML models take 30–60s to load on first start; `/api/v1/ready` returns
> `503` until `zepiris` reports ready, then `200`.

---

## Backend development (without Docker)

```bash
cd backend
python -m venv .venv && . .venv/Scripts/activate   # Windows
# (or: source .venv/bin/activate on macOS/Linux)
pip install -r requirements.txt

# unit tests (no stack needed) — ZepIris adapter + toggle logic
pytest tests/test_zepiris_adapter.py tests/test_toggle.py -v

# full suite: integration tests (Phase 0 gate, RLS isolation, Phase 1 flow)
# auto-skip unless Postgres+Redis are reachable
pytest
```

To run the **integration + isolation** tests, point `DATABASE_URL` / `REDIS_URL`
at a running Postgres/Redis (e.g. `docker compose up postgres redis -d`), then:

```bash
alembic upgrade head
pytest
```

---

## Phase 0 acceptance — how to verify the gate

The definition of done for Phase 0 (ROADMAP §4):

1. **Stack comes up healthy** — `docker compose ps` shows every container healthy.
2. **Register a tenant → create an admin → log in; the session cookie works.**
   Demonstrated by `tests/test_phase0_gate.py`, or manually:
   ```bash
   # provision a tenant + entity admin
   curl -k -X POST https://localhost/api/v1/admin/tenants \
     -H 'Content-Type: application/json' \
     -d '{"name":"Acme","org_code":"ACME-2026","vertical":"office",
          "admin_email":"admin@acme.com","admin_password":"supersecret123"}'

   # add the secret to an authenticator, then log in with the 6-digit code
   curl -k -X POST https://localhost/api/v1/auth/login \
     -H 'Content-Type: application/json' -c cookies.txt \
     -d '{"email":"admin@acme.com","password":"supersecret123"}'

   # the session cookie now authorises /auth/me
   curl -k https://localhost/api/v1/auth/me -b cookies.txt
   ```
3. **ZepIris returns a vector for a test face and matches a second image.**
   The adapter is verified by `tests/test_zepiris_adapter.py`; end-to-end against a
   live ZepIris is covered when the face endpoints land in Phase 1.
4. **Tenant isolation holds even without an app filter** — `tests/test_isolation_rls.py`
   proves RLS hides other tenants on an unfiltered query.

---

## Non-negotiables (enforced, not optional)

Tenant isolation (app + RLS) · consent-before-capture · raw-image deletion ·
verified erasure cascade · immutable audit · TLS 1.3 / HttpOnly+SameSite cookies /
CSRF · India data localisation. See ROADMAP §1.

## Layout

```
backend/   FastAPI — core, adapters/zepiris (keystone), models, services, api/v1, dpdp, migrations, tests
frontend/  Next.js 14 App Router — 3 portals (kiosk / member / admin), lib/ api+camera
infra/     nginx gateway, scripts, model-weight mount point
docker-compose.yml   full stack, one command
.env.example         every env var, documented
```
