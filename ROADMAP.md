# BioCore — Build Roadmap (my plan)

> My working plan for building the BioCore face-auth & attendance platform from the
> documentation package in `files/`. This is *how I will build it*, not a restatement
> of the spec. Source of truth = the 7 docs in `files/` (plain-text mirrors in `_extracted/`).
> Where docs disagree, **Doc 7 (ZepIris VERIFIED) wins** — it was checked against the real repo.

---

## 0. Product in one paragraph

A person enrolls their face once (self-service or admin-assisted). From then on they look
at a shared kiosk camera and the system recognises them in <2s and records a check-in/out.
Admins watch live and configure zones, badges, devices, and reports from a web dashboard.
One backend serves all 14 verticals — only *config* changes. Everything is multi-tenant and
isolated; DPDP Act 2026 compliance (consent, audit, erasure, India-localisation) is enforced
by the system itself.

**Three actors:** the person · the kiosk (non-human identity) · the admin/entity.
**Stack:** FastAPI · Next.js 14 (App Router) · PostgreSQL 16 · Milvus · MinIO · Redis · RabbitMQ · Nginx · Docker.
**ML core:** ZepIris v1.0.0 (Main API :8000 + ML Inference :8001), InsightFace `buffalo_l` embeddings, Milvus COSINE search.

---

## 1. The non-negotiables (hold these through every phase)

These are correctness gates, not features. If any break, the build is not done.

1. **Tenant isolation** — no query ever crosses tenant boundaries. Enforced in app code **and** Postgres Row-Level Security (RLS) as a safety net. `tenant_id` always comes from the session, never a request param.
2. **Consent first** — no face is captured before a consent record exists. Enforced at the API gateway (`/faces/enroll` returns 403 `CONSENT_REQUIRED` without it).
3. **Data minimisation** — raw image deleted immediately after the 512-d vector is generated. Only vectors + references persist.
4. **Erasure is complete** — one request hard-deletes across Milvus + MinIO + Postgres + Redis, each independently verified, then issues a certificate.
5. **Audit everything** — every face search/enroll/delete writes an immutable audit row with a `request_id`. Audit log is append-only (no edit/delete via API).
6. **Web security** — TLS 1.3 only; HttpOnly/Secure/SameSite=Strict cookies; CSRF on all mutations; Argon2/bcrypt passwords.
7. **India localisation** — all data stays in India (on-prem or India-region cloud).

**Out of scope (do NOT build):** Bank KYC/RBI identity, airport boarding, military clearance, prison real-time tracking. These verticals can still use *staff attendance* only.

---

## 2. Architectural decisions I'm locking in up front

| Decision | Choice | Why |
|---|---|---|
| ZepIris access | **Single thin adapter** in the face-auth service | ZepIris uses multipart + `tenant` form field + camelCase `requestId`; the platform exposes clean base64 JSON + snake_case envelope. Isolate all divergence in one place. Build & test this FIRST. |
| Milvus tenancy | **ONE collection `zepiris_faces`** with a `tenant` column | Per Doc 7 (verified). Earlier docs said per-tenant collections — **wrong**. Pass `tenant=<id>` on every insert/search/upsert/delete. |
| Blacklist vectors | Searched in parallel on every kiosk scan | A hit raises an immediate `blacklist.hit` alert. |
| Auth | Server-side sessions in Redis, delivered as HttpOnly cookies | NOT JWT-in-localStorage. Members: email+OTP. Admins: email+password. Kiosks: long-lived device token cookie. |
| Response shape | Uniform envelope `{success, data, request_id}` / `{success, error{code,message}}` | Every endpoint. `request_id` doubles as the audit trace key. |
| Search bad-image behaviour | `/faces/search` returns **200 with empty matches**, not 422 | Per Doc 7 — ZepIris does not error on a bad search image. Platform wraps and applies toggle logic. |
| Tenant_id source | Always from session | Forging via request param must be impossible (RLS catches it anyway). |
| Frontend | One Next.js app, three portals (`/admin/*`, `/me/*`, `/kiosk`+`/register`+`/enroll`) | shadcn/ui, TanStack Query/Table, Recharts, getUserMedia→canvas→base64 JPEG. |

---

## 3. Repository layout I'll scaffold

```
biocore/
├── docker-compose.yml          # full stack, one command up (Phase 0)
├── infra/
│   ├── nginx/                  # gateway, TLS 1.3, rate limits, routing
│   ├── k8s/                    # cloud/scale manifests (later)
│   └── env/                    # .env.example with EVERY var documented
├── backend/                    # FastAPI
│   ├── app/
│   │   ├── core/               # config, db, redis, security, RLS session ctx
│   │   ├── adapters/zepiris/   # THE adapter — build & test first
│   │   ├── services/           # face_auth, attendance, access, visitor,
│   │   │                       #   hr_payroll, notifications, reporting, tenant
│   │   ├── modules/            # wage, membership, guardian, timetable,
│   │   │                       #   donation, events, gps, emergency, erp
│   │   ├── api/v1/             # routers mirroring the API Reference
│   │   ├── models/             # SQLAlchemy, all tables from Doc 3
│   │   ├── schemas/            # pydantic request/response
│   │   └── dpdp/               # consent gate, erasure cascade, audit writer
│   ├── migrations/             # Alembic, reversible
│   └── tests/                  # unit / integration / isolation / dpdp / load
├── frontend/                   # Next.js 14 App Router
│   └── app/(admin|me|kiosk)/   # 3 portals, ~40 screens
└── docs/                       # generated OpenAPI + admin ops guide
```

---

## 4. Phased build (sequenced; each phase ends at a hard acceptance gate)

I follow the doc's phasing because the dependency order is sound, but I front-load the
ZepIris adapter and the isolation/DPDP scaffolding so they're never bolted on late.

### Phase 0 — Foundation `[gate: tenant+login+ZepIris round-trip]`
- Repo + CI/CD (lint → test → build images → staging → manual approval → prod).
- `docker-compose.yml` with **all** containers healthy: gateway, frontend, api, zepiris-main, zepiris-ml, postgres, milvus, minio, redis, rabbitmq.
- Postgres core tables: `tenants, users, roles, consent_records, audit_logs`. Enable **RLS** from day one.
- **ZepIris adapter** (`adapters/zepiris/`): decode base64 → multipart file + `tenant` field; map `requestId`/`imageQualityAssessment`/`searchResult.matches` → platform envelope. Wire health via `/readyz` (model load takes 30–60s — readiness probe must tolerate it).
- Gateway, Redis-backed session auth, CSRF token endpoint.
- **Done when:** register a tenant → create admin → login (cookie works); ZepIris embeds a test face and matches a second photo of the same person.

### Phase 1 — Core attendance MVP `[gate: self-register → kiosk check-in → live on dashboard]`
- Self-registration flow: `/register` → email OTP verify → `/consent` (4 mandatory checkboxes) → `/faces/enroll` (consent-gated; raw image deleted post-vector).
- Kiosk screen `K1`: continuous capture → `POST /faces/search` (device-token auth) → **toggle logic** (in/out from last event) → result card → auto-reset 3.5s. Handle all 7 states (idle/scanning/check-in/check-out/no-match/blacklist/quality-fail).
- Admin: `A2` dashboard overview (presence metrics + live feed, poll 10s), `A3` attendance log, `A5` users list, `A10` device registration + pairing.
- **Done when:** a person self-registers in a browser, checks in/out at a kiosk, and the admin sees it live within 10s. → Working product for Office, Gym, basic School/Factory.

### Phase 2 — Access, zones, badges, DPDP `[gate: isolation + erasure verified]`
- Zones (entry/restricted/amenity) + badges + access-control decisions; door webhooks (`access.granted/denied`, HMAC-signed).
- Admin-assisted enrollment `A7` (patient/inmate/citizen/devotee/visitor/guardian; 4 admin confirmations; optional consent-form upload) → unlocks Hospital, Government, Religious.
- **Full DPDP suite:** `/me/data/export`, **erasure cascade** (Milvus+MinIO+Postgres+Redis, each verified, certificate issued), consent revoke, audit viewer `A16`.
- Blacklist + real-time alerts; visitor temp-enrollment (QR/link, auto-expire + delete).
- **Done when:** cross-tenant access returns 404 (and RLS blocks a deliberately-unfiltered query); erasure clears all 4 stores verifiably and certifies; audit is append-only.

### Phase 3 — Verticals & modules `[gate: each module's acceptance]`
- Wage calc, break tracking, GPS check-in (+geofence), emergency headcount/muster.
- School: class timetable + per-period attendance + guardian pickup verify.
- Gym membership billing; religious donations (80G receipts); event bulk import + badge printing + footfall.
- ERP connectors (SAP/Zoho/Darwinbox/Keka) via webhooks; full reporting/export (PDF/Excel/CSV) + scheduled reports.

### Phase 4 — Advanced ML `[optional / data-dependent]`
- PPE / safety-gear detection (needs training dataset).
- Zone-to-zone movement tracking for high-security sites.

---

## 5. Critical path & risks (what I watch closely)

1. **The ZepIris adapter is the keystone** — everything face-related depends on it. Build, test, and pin its behaviour before any flow that calls it. Verified quirks: multipart not JSON, `tenant` form field, `requestId` camelCase, FLAT/COSINE index, MinIO host port 9002→9000, `ZEPIRIS_*`/`ML_SERVICE_*` env prefixes, search returns 200+empty on bad image, ML model 503 if `.pth` missing.
2. **Tenant isolation is a leak-class bug, not a feature** — RLS + app filter + an explicit isolation test suite per tenant-owned table. Deliberately try to leak in tests.
3. **DPDP carries legal liability** — consent gate, erasure verification, immutable audit must be independently reviewed. Don't ship the security/DPDP layer un-reviewed.
4. **Threshold tuning** — default match 0.5; make it per-zone (raise to 0.65–0.7 for restricted zones). Always run blur+spoof before accepting a match.
5. **Performance** — `/faces/search` must stay <2s and never be fully down (rolling deploys). `attendance_logs` will be the biggest table — composite indexes `(tenant_id,user_id,created_at)` & `(tenant_id,created_at)`, partition by month at scale.

---

## 6. Definition of done (acceptance gates I tie work to)

Mirror Doc 6 §2 exactly — each is demonstrated live:
- **Self-registration:** valid/invalid org code; OTP expires 10min; enroll blocked till 4 consents; raw image gone from MinIO; duplicate email → 409.
- **Kiosk:** match <2s; toggle alternates correctly; unregistered → "not registered" + logged; printed photo rejected by spoof; blacklist → alert; event on dashboard <10s.
- **Multi-tenancy:** A never sees/matches B; cross-tenant id → 404; RLS blocks a forgotten filter.
- **DPDP:** no enroll without consent; export machine-readable; erasure clears 4 stores + verified + certificate; every face op audited with request_id; audit uneditable via API.
- **Security:** TLS 1.3 only; cookies HttpOnly/Secure/SameSite=Strict; CSRF enforced; pen test → zero critical/high before go-live.

**Test minimums:** 80% unit on service code; every endpoint integration-tested (happy+error); isolation tests per tenant table; all §2.4 DPDP criteria; load test at peak×2; pen test before go-live.

---

## 7. Immediate next steps (when I start coding)

1. Scaffold the repo layout (§3) + `docker-compose.yml` with all 10 containers.
2. Stand up Postgres core tables + Alembic + **RLS policies**.
3. Get ZepIris (main+ml) running locally; confirm enroll+search on a test image.
4. Build & unit-test the **ZepIris adapter** against the verified Doc 7 signatures.
5. Wire gateway + Redis sessions + CSRF; prove the Phase 0 gate end-to-end.

---

### Reference index (in `files/`)
- `0_Master_Index` — package map & non-negotiables
- `1_System_and_Operations` *(= `BioCore_Documentation`, duplicate)* — actors, 12 user types, onboarding, zones/badges, 14 vertical playbooks, DPDP obligations
- `2_API_Reference` + `2B_..._Complete` — full endpoint contract (auth, face, attendance, resources, DPDP, modules)
- `3_Database_Schema` — all Postgres tables + Milvus/MinIO/Redis layouts
- `4_Screen_Specifications` — 40 screens across 3 portals
- `5_Integration_and_Infrastructure` — ZepIris wiring, Docker, deploy modes, security, DevOps
- `6_Build_Plan_and_Acceptance` — phasing & contractual acceptance criteria
- `7_ZepIris_VERIFIED` — **authoritative** real ZepIris API; overrides earlier assumptions
</content>
</invoke>
