# BioCore on DigitalOcean — deployment runbook

Takes you from nothing to a working HTTPS deployment. Follow it in order; each step assumes the
one before worked.

`GO_LIVE.md` is the older runbook and is **out of date** in two ways: it deploys ZepIris (now
replaced by the BioVerify credential API) and it targets Kubernetes. Use this file for a
DigitalOcean droplet.

> **Read this first.** Before real people use this, see the readiness assessment. In short:
> there is no anti-spoof model in the path, so **a printed photo of a face passes**; no threshold
> is calibrated; and nobody has yet confirmed that revoking a credential shuts the gate. Those
> are not deployment problems and none of this runbook fixes them. Deploying for a pilot,
> internal trial or demo is reasonable. Putting it on a door that matters is not, yet.

---

## What you are building

```
                    ┌───────────────────────────────┐
  browser ──443──▶  │ Droplet (Ubuntu 24.04, 4 GB)  │
                    │  nginx ─┬─▶ frontend :3000    │
                    │         └─▶ api :8080         │
                    └────┬──────────────┬───────────┘
                         │ VPC          │ HTTPS
                 ┌───────▼──────┐  ┌────▼────────────────┐
                 │ Managed      │  │ BioVerify service   │
                 │ Postgres 17  │  │ (separate droplet)  │
                 │ Managed Redis│  └─────────────────────┘
                 └──────────────┘
```

**Four containers**, not the twelve in `docker-compose.yml`. Milvus, MinIO, etcd and both
ZepIris services are gone — nothing in the current architecture reads them. Verified: a DPDP
erasure completes and self-verifies without any of them present.

Roughly **$40–60/month**: droplet ~$24, managed Postgres ~$15, managed Redis ~$15.

---

## 1. Create the infrastructure

**Droplet** — Ubuntu 24.04, **4 GB / 2 vCPU** minimum. The Next.js build needs ~2 GB on its own;
a 2 GB droplet will fail mid-build. Choose the **Bangalore (BLR1)** region for DPDP data
localisation, and add your SSH key.

**Reserved IP** — assign one, so the address survives rebuilding the droplet.

**Managed Postgres** — version 17, same region, same VPC.

**Managed Redis (Valkey)** — same region, same VPC.

**Firewall** — inbound `80` and `443` from anywhere, `22` from your IP only. For both databases,
set Trusted Sources to the droplet **only** — never open them to the internet.

**DNS** — point an A record at the reserved IP. You need a real hostname; certificates are not
issued for bare IPs.

---

## 2. The database role — do not skip this

DigitalOcean gives you `doadmin`. **Do not run the app as `doadmin`.**

Tenant isolation is enforced by PostgreSQL row-level security. RLS is **bypassed** by superusers
and by roles with `BYPASSRLS`. If the app connects as such a role, every tenant can read every
other tenant's data and nothing in the application will complain.

Connect as `doadmin` once and create a plain role that owns the schema:

```sql
CREATE ROLE biocore LOGIN PASSWORD 'use-a-long-random-one';
CREATE DATABASE biocore OWNER biocore;
\c biocore
GRANT ALL ON SCHEMA public TO biocore;
```

Then **prove** it, connected as `biocore`:

```sql
SELECT current_user, rolsuper, rolbypassrls
FROM pg_roles WHERE rolname = current_user;
```

Both flags must be **false**. If either is true, stop and fix the role — otherwise the isolation
this product is sold on does not exist.

---

## 3. Prepare the droplet

```bash
ssh root@your.reserved.ip

apt-get update && apt-get upgrade -y
apt-get install -y docker.io docker-compose-v2 git certbot
systemctl enable --now docker

adduser --disabled-password --gecos "" biocore
usermod -aG docker biocore
```

Get the code (the repo is private, so use a read-only deploy key or a personal access token):

```bash
su - biocore
git clone https://github.com/VijayDahiya01/biocare.git
cd biocare/biocore
```

---

## 4. Write the configuration

```bash
cp backend/.env.example .env        # compose reads ./.env
openssl rand -base64 48             # run twice, once per secret
```

Edit `.env`. Every line below matters:

```ini
ENVIRONMENT=production
DATA_REGION=india

DATABASE_URL=postgresql+psycopg://biocore:PASSWORD@private-db-host:25060/biocore?sslmode=require
REDIS_URL=rediss://default:PASSWORD@private-redis-host:25061/0

SESSION_SECRET=<first openssl output>
CSRF_SECRET=<second openssl output>
COOKIE_SECURE=true

# Every test shortcut OFF. The app refuses to start otherwise.
DEV_LOGIN=false
DEMO_DISABLE_TOTP=false
FAKE_REDIS=false
FAKE_ZEPIRIS=false
FAKE_BIOVERIFY=false
FAKE_CONNECTORS=false
FAKE_GOV_IDENTITY=false          # see step 8 before turning this off

# Face credentials via the BioVerify service
CREDENTIAL_ENGINE=bioverify
BIOVERIFY_URL=https://your-bioverify-host
BIOVERIFY_API_KEY=<from whoever runs it>

# Template encryption. A real KMS is better; at minimum set a strong root key.
KMS_PROVIDER=software
KMS_ROOT_KEY=<openssl rand -base64 48>

# Outbound email — without this nobody can receive a sign-in code.
SMTP_URL=smtps://apikey:KEY@smtp.sendgrid.net:465
SMTP_FROM=BioCore <no-reply@yourdomain.com>

# Government KYC (billed per call when live)
GOV_IDENTITY_PROVIDER=sandbox
SANDBOX_API_KEY=
SANDBOX_API_SECRET=
```

```bash
chmod 600 .env
```

**DigitalOcean blocks outbound port 25** on droplets, so a plain SMTP relay will silently fail.
Use a provider on port 465/587 — SendGrid, Mailgun, Postmark, Amazon SES.

---

## 5. Certificates

```bash
exit                                 # back to root
certbot certonly --standalone -d yourdomain.com --agree-tos -m you@yourdomain.com
```

Edit `infra/nginx/nginx.conf` so the certificate paths point at
`/etc/letsencrypt/live/yourdomain.com/fullchain.pem` and `privkey.pem`, and set `server_name` to
your hostname.

Renewal, with a reload so nginx picks up the new certificate:

```bash
echo '0 3 * * * certbot renew --quiet --deploy-hook "docker kill -s HUP biocore-gateway-1"' | crontab -
```

---

## 6. Migrate, then start

```bash
su - biocore && cd biocare/biocore

docker compose -f docker-compose.prod.yml build
docker compose -f docker-compose.prod.yml run --rm api alembic upgrade head
docker compose -f docker-compose.prod.yml up -d
docker compose -f docker-compose.prod.yml ps
```

**If the api container exits immediately, read its logs — that is the safety guard doing its
job**, and it names every problem:

```bash
docker compose -f docker-compose.prod.yml logs api | tail -30
```

```
Refusing to start: this configuration is not safe for production.
  1. DEV_LOGIN=true — lets ANYONE sign in as ANY email...
  2. SMTP_URL is unset — one-time codes are only written to the log...
```

Fix what it lists and start again. It checks: dev login, every fake engine, the 2FA bypass,
insecure cookies, default secrets, a software KMS with no root key, missing email, and an engine
selected without its address.

---

## 7. Verify before anyone uses it

```bash
curl -s https://yourdomain.com/api/v1/health          # {"status":"ok"}
curl -sI https://yourdomain.com/admin/login | head -1 # 200
```

**Prove tenant isolation on the real database.** This is the one test worth running against
production, because a wrong database role defeats it silently:

```bash
docker compose -f docker-compose.prod.yml run --rm api python -m pytest tests/test_isolation_rls.py -q
```

**Walk the whole journey** — creates a throwaway organisation and person, so run it before you
create the real one, and delete them afterwards:

```bash
docker compose -f docker-compose.prod.yml run --rm api python scripts/real_journey.py \
  https://yourdomain.com/api/v1
```

Expect `19 passed, 0 failed`. It will stop at the face capture unless the image passes
BioVerify's quality gate — that step is better done from a browser with a real webcam.

Then create your first real organisation at `https://yourdomain.com/onboard` and **write down the
2FA secret it shows you**. It is displayed once. `backend/scripts/totp.py` can recover a code from
the database, but only if you can reach the database.

---

## 8. Two decisions that are not technical

**Government KYC.** With `FAKE_GOV_IDENTITY=true` no PAN or Aadhaar check happens, and the words
"identity verified" in your product mean only that a face was captured. Turning it off makes real,
**billed** calls to NSDL/UIDAI. Either is a legitimate choice — just don't describe it as working
before it is.

**Anti-spoof.** There is none. Hold a phone with someone's photo to the camera and you are them.
If a customer asks what stops that, the honest answer today is "nothing yet".

---

## 9. Keep it alive

**Backups.** Managed Postgres does daily backups automatically — confirm the retention window and
**do a restore drill once** before you rely on it. An untested backup is a hope.

**Logs.** Already capped at 10 MB × 5 files per container in the compose file, so they cannot fill
the disk.

**Monitoring.** Turn on DigitalOcean Monitoring with alerts for CPU, memory, disk above 80%. Also
watch, from the app: `bioverify.revoke_failure` (a credential dead locally but alive upstream) and
gate mismatch/liveness rates.

**Updating:**

```bash
cd biocare && git pull
docker compose -f biocore/docker-compose.prod.yml build
docker compose -f biocore/docker-compose.prod.yml run --rm api alembic upgrade head
docker compose -f biocore/docker-compose.prod.yml up -d
```

**Rolling back** needs care: application containers roll back cleanly, but a migration may not.
Check whether the release added one, and take a database snapshot before any deployment that did.

---

## If it will not start

| What you see | Cause |
|---|---|
| api exits, logs say "Refusing to start" | The safety guard. It lists every problem — fix and restart. |
| 502 from nginx | api is not healthy yet; `docker compose logs api`. |
| Cannot sign in, no error | `COOKIE_SECURE=true` without working HTTPS. Fix TLS first. |
| No sign-in codes arrive | `SMTP_URL` wrong, or port 25 blocked. Use 465/587. |
| Tenants can see each other | The app is connecting as a superuser or `BYPASSRLS` role. Step 2. |
| Faces never register | BioVerify unreachable or its API key rejected. `curl https://your-bioverify-host/health`. |
