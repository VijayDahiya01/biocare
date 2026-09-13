# BioCore — Complete Product Document (Master Reference)

*The single source of truth for what BioCore is, does, how it works, how it's built,
how it's delivered, and what's still pending. Everything in one place.*

**Status legend:** ✅ built & working · 🔶 built, needs the real engine or config to be
production-real · ⛔ not built yet (gap).

---

## Table of contents
1. What BioCore is
2. Core concept — person-centric identity
3. End-to-end flow
4. The four apps
5. Complete feature & module catalog
6. Face engine (ZepIris) — how matching, liveness & anti-deepfake work
7. Privacy & compliance (DPDP)
8. Security
9. Multi-tenancy & multi-vertical
10. Architecture & tech stack
11. Data model (key tables)
12. API surface
13. Deployment & operations
14. Where it's used (verticals & environments)
15. Go-to-market & delivery model
16. Pricing shapes
17. Testing & demo
18. Status: built vs pending (gap list)
19. Roadmap
20. Appendix — URLs, design system, glossary

---

## 1. What BioCore is
BioCore is a **multi-tenant, face-authentication platform** for **attendance, access
control, and visitor management**. A person verifies their face **once**, then uses it to
check in — in under two seconds, contactless — at any place they belong (office, school,
event, gym, hotel…). Businesses get real-time presence, access decisions, visitor handling,
emergency headcount, and a full audit trail. It is built ground-up for India's **DPDP**
data-protection rules.

**One-liner:** *One face. Every place.*

---

## 2. Core concept — person-centric identity (the moat)
- A person has **one global identity** (`persons` table) linked across every business they
  join (`users.person_id`).
- **Capture face once** → an encrypted master template is stored, then **re-provisioned per
  business/event on a one-tap consent** — no re-scan. ✅
- Network effect: enrolled at one place → onboard to the next in a single tap. Each added
  business makes the identity more valuable and each new onboarding cheaper.

---

## 3. End-to-end flow (the core loop) ✅
1. **Invite** — a business invites a person by email (shows in their app) **or** issues a
   **link/QR token** (visitor/guardian self-enroll, no login).
2. **Open link / log in** — member logs in (email OTP); visitor opens the token URL.
3. **Consent + capture face** — 4 acknowledgements (purpose, sensitivity, rights,
   freely-given) → capture face once. Quality/liveness checked (§6).
4. **Registration complete** — status `pending_face → active`.
5. **Verify/unverify visible on dashboard** — admin → Users shows status & verification.
6. **Entry by face** — at a gate/event terminal, the person looks at the camera → matched →
   check-in/out logged, access allowed/denied with a reason.
7. **Privacy controls** — withdraw face per place, or erase everything, anytime.

> Clarification: matching is **vector-to-vector**, not photo comparison — the raw photo is
> discarded; only an encrypted math embedding is kept (DPDP minimization).

---

## 4. The four apps ✅

### 4A. User app 📱 (`/member`) — mobile-first
One login for every place you belong to. Screens: login (email OTP + dev bypass), hub
(profile, verification status, places grouped by sector, invites, badges), join-by-code,
verify-face-once (consent + capture), business detail (role, badge, status, allow/withdraw
face, check-in history), events (register + per-event consent). Person self-service also at
`/me/*` (consent, data, erasure, grievance, leave).

### 4B. Guard console 🛡️ (`/guard`) — staffed terminal, landscape
Live face **inside a circle** with **MediaPipe** face detection (scans only when a real face
fills the circle). Result states: Welcome / Goodbye+duration (violet), Access denied+reason /
Blacklist "do not admit" (red), Not recognised → Enroll visitor (grey). Guard signs in
(email+password+2FA) to unlock panels: **Alerts**, **Who's inside + Emergency muster**,
**Enroll walk-in visitor**, **Pickup verify** (school), **Manual override**.

### 4C. Self-service kiosk 🖥️ (`/kiosk`) — unattended
Always-on face check-in terminal; same result system; bottom stat strip (checks today).

### 4D. Admin portal 🧭 (`/admin`) — ~28 screens
Dashboard · Attendance · Users (+ profile/edit/erase) · Devices · Zones · Geofences · HR ·
Leave · Roles · Reports · Blacklist · Alerts · Emergency · Visitors · Events · Memberships ·
Badges · Donations · Grievances · Audit · Settings · School timetable · Security · Enroll.

**A "terminal" = any device with a camera + browser** opening `/kiosk?token=…` or
`/guard?token=…`. Paired with a device token (issued once, stored hashed). No proprietary
hardware. ✅

---

## 5. Complete feature & module catalog

**Identity & onboarding** — global person identity; onboarding via admin invite, visitor
token link/QR, or self-registration by org code; capture-once + one-tap reuse; roles
(entity_admin, manager, hr_payroll, security_reception, member, guardian, self_user,
super_admin); badges; membership status. ✅

**Face verification** — consent-gated capture; quality (blur/lighting), **liveness /
anti-spoof / anti-deepfake**, face-area/centering (MediaPipe), safety check; per-zone match
threshold (0.5 attendance → 0.65–0.7 high-security). 🔶 (accuracy needs real engine)

**Attendance & workforce** — check_in / check_out / break_start / break_end; live
"who's inside" presence; departments, HR fields, leave, roles; manual corrections (audited);
reports/exports; school timetable/period attendance. ✅

**Access control** — allow/deny by **badge, zone, allowed hours, and PPE** (hi-vis/helmet);
**geofences/GPS**; device paired to a specific gate/zone; deny with reason
(no_badge / outside_hours / ppe_missing / blacklist). ✅ (PPE model pluggable 🔶)

**Events** — create events, **register attendees with per-event consent**, face entry at
the event gate, withdraw consent. ✅

**Visitor & guardian** — invite a visitor by link/QR → self-enroll → **temporary pass**;
walk-in enroll at the desk; **school pickup** — verify the authorized guardian's face before
releasing a child. ✅

**Safety & security** — **blacklist** ("do not admit" alarm), priority **alerts**
(blacklist/unrecognised/access-denied/PPE/device-offline), **emergency muster** (live
headcount roll + PDF). ✅

**Members, donations, grievances, documents** — memberships & dues; **donations** (e.g. 80G
receipts) for clubs/religious orgs; grievances; generated **PDFs** (erasure certificates,
muster reports, receipts). ✅

**Notifications & integrations** — outbound **webhooks** (retry + dead-letter via the async
worker); email/OTP (SMTP when configured). ✅ (SIS/HRMS/ticketing connectors ⛔)

**Settings** — branding, DPDP/consent config, thresholds, zones/badges/devices. ✅

---

## 6. Face engine (ZepIris) — matching, liveness & anti-deepfake
- Everything face-related goes through **one adapter** (`app/adapters/zepiris/`). Swapping
  engines changes only this file. ✅
- `get_zepiris()` returns the **real client** (HTTP → `ZEPIRIS_URL`) when
  `FAKE_ZEPIRIS=false`, else an **in-process fake** for dev. ✅
- **Real ZepIris** is a Docker stack: `zepiris-main` (:8000 API) + `zepiris-ml` (:8001
  inference) + **Milvus** (vectors, needs etcd+MinIO). ML runs on **CPU by default** (GPU
  optional). Needs 3 model weights: `spoof_model.pth` (liveness/anti-spoof),
  `blur_model.pth` (quality), `nudity_model.pth` (safety). 🔶 (images + weights required)
- **Image-quality assessment** the app enforces: `blur/is_sharp` → `IMAGE_QUALITY_FAILED`
  (422); `spoof/is_spoof` → `SPOOF_DETECTED` (403, blocks entry); face-area threshold;
  nudity. Insert 409 on dup id. ✅ (logic) / 🔶 (real detection)
- **Dev fake** returns the **most-recently-enrolled** person, always passes quality — for
  clicking through flows only; resets on backend restart.
- Switch to real: `FAKE_ZEPIRIS=false`, `ZEPIRIS_URL=…`, restart; verify with
  `scripts/verify_zepiris.py`. **No app code changes.**

---

## 7. Privacy & compliance (DPDP) — the foundation ✅
- **Consent before capture** — no face without a logged, per-purpose consent (4 acks).
- **Data minimization** — store **only the vector**; raw image is **never persisted**
  (`minio_object_key` stays null / discarded by the engine).
- **Per-place & per-purpose consent**; **withdraw** anywhere.
- **Verified erasure cascade** — vectors (Milvus) + object storage (MinIO) + Postgres +
  Redis, with proof (erasure certificate PDF).
- **Append-only audit trail** — DB-enforced; every action logged.
- **India data localization** — `DATA_REGION=india`.
- **Tenant isolation** — Postgres row-level security (FORCE RLS).

---

## 8. Security ✅
- Passwords **Argon2**; **TOTP 2FA** for admins; **OTP** for members.
- **Redis-backed sessions**, HttpOnly cookies; **CSRF** via `X-CSRF-Token`; `COOKIE_SECURE`.
- **Device tokens** stored **hashed** (raw shown once at pairing).
- App connects to DB as a **non-superuser** so **FORCE RLS** is enforced; narrow
  `bypass_rls` for person-scoped cross-tenant ops.
- Dev-only flags (`FAKE_ZEPIRIS`, `FAKE_REDIS`, `DEV_LOGIN`) default **false**; must be OFF
  in production. CI runs ruff + bandit + pytest-cov ≥70 + frontend build.

---

## 9. Multi-tenancy & multi-vertical ✅
- Every business is an isolated **tenant** (Postgres RLS keyed on `app.tenant_id`).
- One codebase serves many **verticals** via config: office, school, college, gym, hotel,
  bank, factory, warehouse, retail, hospital, construction, residential, government,
  religious, logistics, event.

---

## 10. Architecture & tech stack
- **Frontend:** Next.js 14 (TypeScript) — mobile-first user app + landscape ops consoles;
  **MediaPipe** for on-device face detection. ✅
- **Backend:** FastAPI (Python). ✅
- **Datastores:** PostgreSQL 16 (+ RLS), **Milvus** (vectors), **MinIO** (object storage),
  **Redis** (sessions/cache/OTP/presence). ✅ (Milvus/MinIO used with real engine)
- **Async:** **RabbitMQ** + a **worker** (webhooks/notifications, retry + DLQ). ✅
- **Gateway:** Nginx (TLS termination, routing). ✅
- **Monitoring:** Prometheus + Grafana (scrape `api:8080/metrics`). ✅
- **Packaging:** Dockerfiles (backend, frontend), `docker-compose.yml` (full stack, one
  command), `docker-compose.dev.yml` (postgres+redis only), **Kubernetes** manifests
  (`infra/k8s/*`). ✅
- **Face engine:** ZepIris main + ML (external images). 🔶

---

## 11. Data model (key tables)
`tenants` (org, vertical, plan, org_code) · `users` (per-tenant, role, status, department,
person_id, totp_secret) · `persons` (global identity) · `person_faces` (encrypted master
template) · `face_records` (vector reference, no raw image) · `business_invites` ·
`event_registrations` · `devices` (hashed token, zone) · `zones` / `geofences` ·
`attendance_log` (events) · `current_presence` (who's inside) · `badges` · `blacklist` ·
`alerts` · consent & audit tables (append-only) · memberships / donations / grievances /
leave / documents. ✅

---

## 12. API surface (`/api/v1`, ~30 routers) ✅
auth · enrollment · devices · kiosk · attendance · users · zones · admin_enroll · visitors ·
dpdp · blacklist · alerts · settings · hr · breaks · gps · leave · roles · reports · school ·
memberships · donations · events · integrations · notifications · security · grievances ·
documents · person · invites. Live schema at `/api/v1/docs`.

---

## 13. Deployment & operations
- **One-command full stack:** `docker compose up --build` brings up gateway, frontend, api,
  worker, ZepIris (main+ml), Milvus(+etcd), MinIO, Postgres, Redis, RabbitMQ, Prometheus,
  Grafana. All config from `.env` (`.env.example` documents every key). ✅
- **Production go-live checklist:** `docs/GO_LIVE.md` — India region; managed/HA datastores;
  non-superuser DB role; real TLS 1.3; secrets manager; deploy real ZepIris + weights; tune
  thresholds; worker + SMTP; monitoring + backups; CI green; acceptance 22/22; load test at
  peak×2; pen-test; DPDP review; onboard first tenant. ✅ (doc) / 🔶 (external steps)
- **Backups:** `infra/scripts/backup.sh` / K8s cronjob (run as superuser); restore drill
  verified. ✅
- **Day-2:** `docs/OPERATIONS.md`, `docs/SECURITY.md`.

---

## 14. Where it's used (verticals & environments)
Office gates & floors · school/college gates, classrooms, exam halls, hostels, bus boarding ·
event entry, halls, VIP zones · gym/club entry · hotel staff & service entries ·
factory/warehouse gates & hazardous zones (PPE, muster) · hospital wards · bank branches &
vaults · co-working desks · gated residential/society gates · government offices ·
construction sites · temples/religious orgs (member + donation).

---

## 15. Go-to-market & delivery model
- **Delivery modes:** cloud multi-tenant SaaS (default, India region) · private cloud ·
  on-prem (`docker compose`/K8s, for govt/strict schools) · reseller/white-label (event
  agencies, integrators).
- **Universal onboarding:** provision tenant → admin configures (branding, DPDP, zones,
  badges, devices) → import roster / send invites → people self-verify → deploy terminals
  (camera + browser + device token) → go live → support.
- **Per-vertical processes:**
  - **Events** 🎪 — create event → import registrants/ticketing → invite links → pre-event
    self-verify → portable tablet kiosks at gates → face entry + live headcount + VIP/blacklist
    alerts → **post-event erase**. Pricing: per-event + per-attendee.
  - **Schools/colleges** 🎓 — import student/staff roster (SIS) → parents invited → **student +
    guardian enroll (minor consent)** → gate + classroom terminals → attendance + **absent
    alerts** + **guardian pickup verification** + muster. Pricing: per-student/year.
  - **Workspaces/companies** 🏢 — HR imports employees (HRMS) → self-verify → terminals at
    entrances/floors (optionally wired to turnstiles) → attendance → payroll feed; visitor
    pre-invite; access by role/zone/hours; muster. Pricing: per-employee/month + per device.
  - **Gyms/hotels/factories/hospitals/banks/residential/govt** — same platform, per-site config.
- **Sales lifecycle:** discovery → live demo → 2–6 wk pilot (one gate/site) → rollout
  (provision, integrate, deploy, train) → support & expand.

---

## 16. Pricing shapes (finalize with real numbers)
Per active person/month (offices, gyms) · per student/year (schools) · per event +
per attendee (events) · per site/device add-on · module add-ons (visitor, PPE, pickup,
events) · reseller/white-label wholesale tier.

---

## 17. Testing & demo (local)
- App: `http://localhost:3001` — user app (`/member/login`, Dev sign in), guard (`/guard`),
  kiosk (`/kiosk?token=…`), admin (`/admin/login`).
- Demo tenant: **DEMO-2026**; admin **admin@acme.com / demopass123 + TOTP**; seed via
  `scripts/seed_demo.py` (prints creds + live 2FA). Full steps in `docs/TEST_RUNBOOK.md`.
- Dev face engine returns the most-recently-enrolled person; camera works on localhost/https
  only. Verify scripts: smoke, **acceptance (22/22)**, verify_person, verify_zepiris,
  verify_ppe; load test via Locust.

---

## 18. Status: built vs pending

**Built & working ✅** — all 4 apps + ~28 admin screens; multi-tenant RLS; person-centric
identity; consent → vector-only → erasure lifecycle; attendance/access/events/visitor/
pickup/blacklist/alerts/muster/HR/leave/memberships/donations/grievances/reports/audit;
webhooks + worker; MediaPipe face-gating; full docker-compose + K8s + monitoring + backups;
CI; load-tested (0% errors); production build clean (49 routes).

**Needs real engine/config 🔶** — deploy real **ZepIris** (images + `.pth` weights) for true
matching + anti-spoof/deepfake; real TLS, secrets manager, managed datastores, SMTP,
thresholds; PPE model.

**Not built yet — gaps ⛔**
- Offline / poor-network terminal mode (events, schools, factories).
- Mobile app packaging (PWA install / native wrapper).
- Roster & system **integrations**: SIS/ERP (schools), HRMS/payroll (offices),
  ticketing (events) — only outbound webhooks today.
- Access-hardware bridge (turnstile/door relays).
- Bulk enrollment tooling.
- SMS/WhatsApp notification providers wired.
- Minor-consent flow (guardian consent for under-18).
- Independent DPDP + security audit; DPA/consent templates; retention policies.
- Hardware kits & install partners; support playbook/SLAs; pricing finalized; pilot
  program; reference customers/case studies; per-vertical sales collateral.

---

## 19. Roadmap
- **Now:** platform + 4 apps + DPDP lifecycle (done).
- **Next (0–6 mo):** deploy real engine; first paid pilot in one beachhead vertical
  (schools or events); offline mode; the integrations that pilot needs.
- **Later (6–18 mo):** SDK/API for partners; more verticals; deeper analytics; module
  marketplace; access-hardware ecosystem.

---

## 20. Appendix

**Design system** — user app: crimson `#C8011A` + violet `#6D28D9` on light lavender,
**Plus Jakarta Sans**. Terminals (guard/kiosk): light lavender, **Space Grotesk** (display) +
**IBM Plex Sans**; result colors = violet (recognised) / crimson (denied/blacklist) / grey
(no-match).

**Companion docs** — `PITCH_DECK.md` (investor deck source), `TEST_RUNBOOK.md` (local test),
`GO_LIVE.md` (production checklist), `OPERATIONS.md`, `SECURITY.md`, `PERSON_APP.md`,
`CHECKIN_APP_UI_SPEC.md`, `PENDING.md`, `ROADMAP.md`.

**Glossary** — *Tenant* = a customer business (isolated). *Person* = global identity across
tenants. *Terminal/Device* = camera+browser paired by token. *Master template* = the
capture-once face vector, reused per place. *Muster* = emergency live headcount. *RLS* =
database row-level security. *DPDP* = India's Digital Personal Data Protection law.
