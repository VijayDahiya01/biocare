# BioCore — Pending vs. the documentation package

Audit of what the docs in [`../files/`](../files) specify vs. what is built, as of
2026-06-16. Legend: ✅ done · 🟡 partial / covered differently · ❌ not built.

**Summary:** the documented **REST API is fully implemented** (106 routes; full Doc 2B
index + grievance + tokenised guardian enroll) and **58 tests pass against real
Postgres** (RLS isolation, Phase 0/1 flows, erasure cascade). **All 40 documented
screens now exist.** What remains is **real external integrations (email/SMS, PDFs,
RTSP), async/ops infra (RabbitMQ, monitoring, backups, CI/CD, K8s), live ZepIris +
models, and QA/handover artifacts** — listed below.

**Update 2026-06-16:** built the previously-missing screens (A6 user profile, A20 roles
editor, K7 guardian enroll) and the **DPDP grievance** mechanism (M7 + admin queue +
API + migration `0006`). All verified end-to-end against the live stack.

---

## A. Frontend screens (Doc 4 — "40 screens")
- ✅ **A6 User profile** `/admin/users/[id]` — view/edit (role/dept/status/member_id) + erasure. *(built 2026-06-16)*
- ✅ **A20 Roles & permissions** `/admin/roles` — presets read-only + create/delete custom roles from the permission catalog. *(built 2026-06-16)*
- ✅ **M7 Grievance** `/me/grievance` + admin `/admin/grievances` (DPO review/resolve), backed by new `POST /grievance`, `GET /grievances`, `POST /grievances/{id}/resolve`. *(built 2026-06-16)*
- ✅ **K7 Guardian enroll** `/guardian/[token]` — tokenised self-enroll (Redis-backed invite); `guardians/invite` now returns a link, new public `POST /guardians/enroll`. *(built 2026-06-16)*
- 🟡 **A4 Live feed** `/admin/live` — functionally covered by the dashboard live feed; no separate route (acceptable).

> All 40 documented screens are now present (A4 folded into the dashboard).

## B. Backend functional gaps
- ✅ **Grievance endpoint** — `POST /grievance` + `GET /grievances` + resolve (migration `0006`, RLS-isolated). *(built 2026-06-16)*
- ✅ **Email (SMTP)** — real delivery via `SMTP_URL` (STARTTLS/SSL) with a log-stub fallback when unset (so dev OTPs still appear in the log). *(built 2026-06-16)* · 🟡 SMS/WhatsApp + priority routing still pending (need provider creds).
- ✅ **PDF generation** — erasure certificate, 80G donation receipt, and muster report now produce **real PDFs** (reportlab), served by capability-token URLs `/documents/{category}/{token}`; stored on local disk in dev (MinIO in prod). *(built 2026-06-16, verified live)*
- ❌ **RTSP / IP-camera capture** — devices accept `capture_method=rtsp`, but there is no server-side RTSP frame extractor; only browser-webcam kiosk works.
- 🟡 **Per-period (class) attendance** — `/attendance/session` filters by the timetable slot's time window; it does **not** map a roster/class membership to the scan. Good enough for a demo, not a true class register.
- 🟡 **Badge printing** — `badge.print` / `events/badge-print` fire a webhook (consumer prints); no built-in print path (acceptable per the webhook design).

## C. Async & infrastructure (Doc 5)
- ✅ **RabbitMQ async bus + worker** — `eventbus.publish` (pika) hands webhook deliveries + notifications to a topic exchange; `app/worker.py` consumes with retry + dead-letter; **inline synchronous fallback** when no broker (so local dev still works). `worker` service added to compose. *(built 2026-06-16)*
- ✅ **CI/CD pipeline** — `.github/workflows/ci.yml`: backend job (Postgres service, non-superuser role so RLS holds, ruff lint, `alembic upgrade head`, `pytest --cov --cov-fail-under=70`) + frontend job (`npm ci`, `tsc`, `next build`). *(built 2026-06-16)* · 🟡 staging/prod deploy stages still to wire to your hosting.
- ✅ **Monitoring: Prometheus + Grafana** — FastAPI `/metrics` (verified live), `prometheus` + `grafana` compose services, scrape config + auto-provisioned datasource + "BioCore API" dashboard. *(built 2026-06-16)* · 🟡 alert rules + non-API exporters still to add.
- ✅ **Backups** — `infra/scripts/backup.sh` + `restore.sh` (pg_dump/pg_restore as superuser since FORCE-RLS blocks owner dumps; MinIO `mc` + Milvus hooks). **Verified round-trip** (dump → restore into scratch DB → row counts match). *(built 2026-06-16)* · 🟡 wire to cron + offsite + monthly drill.
- ✅ **Kubernetes manifests** — `infra/k8s/` namespace/config/secret, api (+HPA 2–10), worker, frontend, TLS ingress; all YAML-validated. *(built 2026-06-16)* · 🟡 data-store StatefulSets/managed services per your cluster.
- 🟡 **TLS / secrets** — nginx is configured for TLS 1.3 ✅, but real certificates and a secrets manager are deploy-time (currently self-signed script + env files).

## D. ML / face engine (Doc 7) — deployment/data-dependent
- 🟡 **Real ZepIris** — adapter unit-verified against the spec; locally a fake engine is used. A go-live **contract-verification script** now exists (`scripts/verify_zepiris.py`: insert→search→get→delete vs a real engine + a face image). Still needs the actual engine + model weights to run **[external]**.
- 🟡 **PPE** — a **reference model service** (`infra/ppe-reference/`, the `/detect` contract) is built, compose-wired (`--profile ppe`), and the enforcement path is **verified end-to-end** (`scripts/verify_ppe.py`: missing gear → deny + alert; present → grant). A **trained PPE model/dataset** is still **[external]**.

## E. Testing & QA (Doc 6 §3.1)
- 🟡 **Coverage ~78%** (pytest-cov; `--cov-fail-under=70` gate in CI); **63 tests**. Past-80% + per-table isolation tests still pending.
- ✅ **Acceptance criteria checker** — `scripts/acceptance.py` verifies all Build Plan §2 criteria against real Postgres: **22/22 PASS** (self-reg, consent gate, toggle, cross-tenant 404, RLS, erasure cascade, audit immutability, CSRF). *(built 2026-06-18)*
- ✅ **Load test** — Locust harness (`loadtest/locustfile.py`) ran against the live stack; **caught + fixed a real concurrency race** (duplicate-key 500 on `current_presence` → atomic upsert) + DB-pool tuning; clean baseline **0% errors, p95 340ms, ~80 rps on one dev worker**. True peak×2 needs multi-replica infra **[external]**. *(built 2026-06-18)*
- 🟡 **Security scans** — `bandit` (SAST, **0 medium/high**) + `pip-audit` in CI; **python-multipart patched** (6 CVEs); see `docs/SECURITY.md`. Independent **penetration test** + DPDP review still **[external]**.
- 🟡 **Integration coverage** — core + Phase 3 sweep covered; not literally every endpoint/table.

## F. Handover artifacts (Doc 6 §3.2)
- ✅ Source + README, one-command compose, reversible migrations, documented env vars, OpenAPI/Swagger at `/api/v1/docs`.
- ✅ **Admin operations guide** (`docs/OPERATIONS.md`), **Security doc** (`docs/SECURITY.md`), **Go-live runbook** (`docs/GO_LIVE.md`).
- ✅ **Acceptance walkthrough** — runnable `scripts/acceptance.py` (22/22) replaces the recorded video; ❌ external **pen-test report** still pending.

## G. Out of scope — correctly NOT built (Master Index §5)
Bank KYC/RBI, airport boarding, military clearance, prison real-time tracking. ✅ excluded by design.

---

## Suggested priority order
1. **DPDP grievance** (M7 + `POST /grievance`) — it's a compliance obligation and currently absent.
2. **Remaining admin UI** (A6 user profile, A20 roles editor) and **K7 guardian page** — close the screen inventory.
3. **Real notifications** (at least email/SMTP) so OTPs/alerts leave the server.
4. **PDF generation** for erasure certificate / 80G receipt / muster.
5. **Async workers (RabbitMQ)** for webhooks + scheduled reports + notification routing.
6. **Observability + backups + CI/CD** (Prometheus/Grafana, pg_dump/PITR, pipeline, K8s).
7. **QA**: raise coverage, integration-test every endpoint, load test, then an independent **pen test** + **DPDP/security review** before go-live.
8. **Live ZepIris** wiring with real model weights (and a PPE dataset for Phase 4).
