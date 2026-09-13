# BioCore — Go-Live Runbook

The checklist to take BioCore from "feature-complete + verified locally" to a
production launch. Items marked **[external]** need your infrastructure, real
data/models, or a third party; everything else is in this repo.

## 1. Infrastructure & data localisation [external]
- [ ] Provision in an **India region** (or on-prem) — DPDP localisation. Set `DATA_REGION=india`.
- [ ] Managed/HA **Postgres, Redis, RabbitMQ, MinIO, Milvus** (or StatefulSets). Point the
      Secret/ConfigMap at them (`infra/k8s/00-namespace-config.yaml`).
- [ ] App DB role is a **non-superuser** (so FORCE RLS is enforced) that **owns** the tables.
- [ ] Real **TLS 1.3** certificate at the gateway/ingress (replace the self-signed dev cert).
- [ ] Secrets in a **secrets manager** (not `.env`/git): `SESSION_SECRET`, `CSRF_SECRET`,
      DB/Redis/RabbitMQ/MinIO creds, `SMTP_URL`. Set `COOKIE_SECURE=true`.

## 2. Face engine (ZepIris) [external]
- [ ] Deploy real **ZepIris** (main :8000 + ML :8001) + **model weights**
      (`spoof/blur/nudity .pth`); set `ZEPIRIS_URL`, `FAKE_ZEPIRIS=false`.
- [ ] **Verify the contract** against the real engine with a real face image:
      ```bash
      FAKE_ZEPIRIS=false ZEPIRIS_URL=http://zepiris-main:8000 \
        python -m scripts.verify_zepiris /path/to/face.jpg
      ```
      Expect insert → search-matches → get → delete → gone, all PASS.
- [ ] Tune per-zone `match_threshold` (0.5 attendance; 0.65–0.7 high-security).

## 3. PPE (Phase 4, optional) [external]
- [ ] Train/deploy the real **PPE model** behind the `POST /detect` contract
      (`infra/ppe-reference/app.py` is the reference shape); set `PPE_SERVICE_URL`.
      Path already verified end-to-end via `scripts/verify_ppe.py`.

## 4. Async, monitoring, backups
- [ ] Set `RABBITMQ_URL` and run the **worker** (compose `worker` / K8s `20-worker.yaml`)
      so webhooks/notifications deliver out-of-band with retry + DLQ.
- [ ] Configure **SMTP** (and SMS/WhatsApp providers when added) so OTPs/alerts send.
- [ ] **Prometheus + Grafana** up (`infra/monitoring/`); scrape `api:8080/metrics`;
      add alert rules (error rate, p95 latency, face-search availability).
- [ ] **Backups**: deploy `infra/k8s/50-backup-cronjob.yaml` (or cron `infra/scripts/backup.sh`)
      as a **superuser**; add offsite sync; **run a monthly restore drill** (`restore.sh`,
      verified working). 

## 5. Quality gates (Build Plan §3) [partly external]
- [ ] CI green (`.github/workflows/ci.yml`: ruff + bandit + pytest-cov ≥70 + frontend build).
- [ ] **Acceptance**: `python -m scripts.acceptance` → 22/22 PASS (run against staging).
- [ ] **Load test** at **peak × 2**: `locust -f loadtest/locustfile.py ...` with multiple
      api replicas; confirm p95 + 0 errors at target concurrency.
- [ ] **[external] Penetration test** — zero critical/high (scope in `docs/SECURITY.md`).
- [ ] **[external] Independent DPDP/security review** of the biometric + erasure paths.
- [ ] Close the staged **starlette/FastAPI dependency upgrade** (see `docs/SECURITY.md`).

## 6. Onboard the first tenant
- [ ] `POST /api/v1/admin/tenants` (super-admin) → hand the entity admin their org code.
- [ ] Admin sets branding/DPDP/threshold, creates zones/badges/devices, opens self-registration.
- [ ] Smoke the live kiosk: register a member → enroll → check in/out → see it on the dashboard.

## 7. Day-2
- Operations: [`docs/OPERATIONS.md`](OPERATIONS.md). Security: [`docs/SECURITY.md`](SECURITY.md).
- Pending/roadmap status: [`../PENDING.md`](../PENDING.md), [`../ROADMAP.md`](../ROADMAP.md).
