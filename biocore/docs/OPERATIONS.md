# BioCore — Admin Operations Guide

Day-2 operations for running BioCore. Covers start/stop, configuration, database
migrations, backup/restore, adding a tenant, monitoring, scaling, and triage.
(Handover artifact per Build Plan §3.2.)

---

## 1. Start / stop

### Full stack (Docker Compose — single host / on-prem)
```bash
cp .env.example .env            # fill in secrets first
./infra/scripts/gen-certs.sh    # TLS cert (use a real cert in prod)
docker compose up -d --build    # all services
docker compose --profile ppe up -d   # also start the optional PPE model server
docker compose ps               # health
docker compose logs -f api      # tail a service
docker compose down             # stop (add -v to wipe volumes — destroys data)
```
Async delivery: set `RABBITMQ_URL` in `.env` so webhooks/notifications run via the
`worker` service; unset ⇒ the API delivers them inline (no worker needed).

### Kubernetes (cloud / scale)
See [`infra/k8s/README.md`](../infra/k8s/README.md). App tier autoscales (HPA 2–10);
data stores are managed services or separate StatefulSets.

### Local dev (no ML, no Docker images)
See the README "Test it locally" section — portable/containerised Postgres + the
fake face engine; run `uvicorn` + `next dev` on the host.

---

## 2. Configuration
All config is environment variables — never hardcoded. Source of truth:
[`.env.example`](../.env.example). Key ones:

| Var | Purpose |
|---|---|
| `DATABASE_URL` | Postgres (RLS-enforced; app connects as a **non-superuser**) |
| `REDIS_URL` / `FAKE_REDIS` | sessions/OTP/cache; `FAKE_REDIS=true` for dev only |
| `ZEPIRIS_URL` / `FAKE_ZEPIRIS` | face engine; `FAKE_ZEPIRIS=true` for dev only |
| `RABBITMQ_URL` | async bus; unset ⇒ inline delivery |
| `SMTP_URL`, `SMTP_FROM` | email; unset ⇒ emails logged (dev) |
| `MATCH_THRESHOLD` | default face-match threshold (per-zone overridable) |
| `SESSION_SECRET`, `CSRF_SECRET` | rotate via your secrets manager |
| `COOKIE_SECURE` | must be `true` in production (HTTPS) |
| `DATA_REGION` | keep `india` (DPDP localisation) |

---

## 3. Database migrations
```bash
cd backend
alembic upgrade head          # apply (runs automatically in the api container entrypoint)
alembic downgrade -1          # roll back one (migrations are reversible)
alembic current               # show applied revision
alembic history               # list
```
Migrations run automatically on api container start. In CI they run against a
disposable Postgres before tests.

---

## 4. Backup & restore (Doc 5 §3.3)
**Backups must run as a Postgres superuser / `BYPASSRLS` role** — `FORCE ROW LEVEL
SECURITY` filters even the table owner, so an app-role dump fails.

```bash
# daily (cron): Postgres + (optionally) MinIO objects + Milvus vectors
BACKUP_DIR=/backups RETENTION_DAYS=30 \
  BACKUP_DATABASE_URL='postgresql://postgres:***@postgres:5432/biocore' \
  MINIO_ALIAS=biominio \
  ./infra/scripts/backup.sh

# restore into a fresh/staging DB, then point the app at it and hit /api/v1/ready
BACKUP_DATABASE_URL='postgresql://postgres:***@host:5432/biocore_restore' \
  ./infra/scripts/restore.sh /backups/pg-YYYYmmdd-HHMMSS.dump
```
**Run a restore drill monthly** — a backup you haven't restored is not a backup.
(Verified round-trip: dump → restore into a scratch DB → row counts match.)

---

## 5. Add a tenant (onboard a client)
1. **Provision** (super-admin / bootstrap): `POST /api/v1/admin/tenants`
   ```json
   { "name": "Acme School", "org_code": "ACME-2026", "vertical": "school",
     "admin_email": "principal@acme.com", "admin_password": "•••" }
   ```
   Returns the entity admin's TOTP provisioning URI — give it to them to add to an
   authenticator app. (Locally, `python -m scripts.seed_demo` creates a demo tenant
   and prints a current 2FA code.)
2. The entity admin signs in at `/admin/login`, sets branding/DPDP/threshold under
   **Settings**, creates **Zones/Badges/Devices**, then opens self-registration via
   the org code (members register at `/register`).
3. Choose the vertical at provisioning time to preload the right modules.

---

## 6. Monitoring
- **Health:** `GET /api/v1/health` (liveness), `GET /api/v1/ready` (postgres/redis/zepiris).
- **Metrics:** Prometheus scrapes `api:8080/metrics` (request rate, latency histogram,
  status codes). Grafana dashboard "BioCore API" is auto-provisioned
  (`infra/monitoring/`), at `http://<host>:3002` (admin / `GRAFANA_PASSWORD`).
- **Audit:** every significant action is in `audit_logs` (immutable) and visible to
  admins/DPO at `/admin/audit`.
- **Alerts:** blacklist hits / unrecognised faces / access-denied / PPE violations
  appear at `/admin/alerts`.

---

## 7. Scaling & availability
- API is stateless → scale horizontally (compose `--scale api=N` or K8s HPA 2–10).
- Sessions/rate-limits are in Redis, so any replica can serve any request.
- The **face-search path must never be fully down** — keep ≥2 api replicas and use
  rolling deploys. ZepIris ML can run on GPU nodes separately.
- `attendance_logs` is the largest table; it's composite-indexed and can be
  partitioned by month at high volume.

---

## 8. Troubleshooting
| Symptom | Likely cause / fix |
|---|---|
| `/api/v1/ready` shows `zepiris:false` | ZepIris ML still loading models (30–60s) or `ZEPIRIS_URL` wrong |
| Login 500 + `row-level security policy ... audit_logs` | a handler ran without a tenant bound — ensure auth dep sets the GUC (fixed in core/db.py) |
| `pg_dump ... row-level security` error | backup ran as the app role — use a **superuser**/`BYPASSRLS` role |
| OTP/email never arrives | `SMTP_URL` unset ⇒ codes are in the **api logs**; set SMTP for real delivery |
| Webhooks not delivered | check the `worker` (if `RABBITMQ_URL` set) and the `biocore.dead` DLQ |
| Cross-tenant data visible | app must connect as a **non-superuser** (superusers bypass RLS) |
| Kiosk "not registered" for everyone | wrong `device` token/zone, or ZepIris collection empty/threshold too high |

---

## 9. Security & compliance checklist (before go-live)
- TLS 1.3 only; `COOKIE_SECURE=true`; admin TOTP enforced.
- App DB role is **non-superuser** (RLS enforced); secrets in a manager, not git.
- Independent **penetration test** (zero critical/high) and **DPDP/security review**.
- **Load test** at peak × 2 concurrent kiosk scans.
- Data + backups pinned to an **India region** (on-prem or India cloud).
