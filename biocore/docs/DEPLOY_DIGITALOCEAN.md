# BioCore on DigitalOcean — deployment runbook

Takes you from nothing to a working HTTPS deployment. Follow it in order; each step assumes the
one before worked.

`GO_LIVE.md` is the older runbook and is **out of date** in two ways: it deploys ZepIris (now
replaced by the BioVerify credential API) and it targets Kubernetes. Use this file for a
DigitalOcean droplet.

> **Read this first.** The registration and gate paths are proven against the live face service
> — a real enrolment issued a real credential, and a different person's face was correctly
> refused at `-0.14` against a `0.35` threshold, in about 1.5 seconds.
>
> Three things are still open, and none of them is a deployment problem:
>
> - **Anti-spoofing is computed and then ignored.** Every verification returns a spoof score and
>   says so itself: `"pad": {"attack_probability": 0.235, "status": "RESEARCH_ONLY - not
>   enforced at verify"}`. A printed photo passes. The number exists; someone has to choose a
>   threshold and enforce it.
> - **No threshold is calibrated**, so you cannot state a false-accept rate.
> - **Nobody has confirmed that revoking a credential shuts the gate.**
>
> A pilot, internal trial or demo is reasonable. A door that matters is not, yet.

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
                 └──────────────┘  └─────────────────────┘
```

**Four containers**, not the twelve in `docker-compose.yml`. Milvus, MinIO, etcd and both
ZepIris services are gone — nothing in the current architecture reads them. Verified: a DPDP
erasure completes and self-verifies without any of them present.

Roughly **$40/month**: droplet ~$24, managed Postgres ~$15. Redis runs in a container.

---

## 1. Create the infrastructure

**Droplet** — Ubuntu 24.04, **4 GB / 2 vCPU** minimum. The Next.js build needs ~2 GB on its own;
a 2 GB droplet will fail mid-build. Choose the **Bangalore (BLR1)** region for DPDP data
localisation, and add your SSH key.

**Reserved IP** — assign one, so the address survives rebuilding the droplet.

**Managed Postgres** — version 17, same region, same VPC.

**Redis — you do not need a managed one.** `docker-compose.prod.yml` now runs
`redis:7-alpine` alongside the app with an append-only file on a persistent volume, so
`REDIS_URL=redis://redis:6379/0` and there is nothing to provision. That saves about $15/month
and is a reasonable trade here: Redis holds sessions and one-time codes, not records. If it is
lost, people sign in again — nothing is destroyed.

Use DigitalOcean Managed Redis instead only if you run more than one droplet, since a
container-local Redis cannot be shared between them.

**Firewall** — inbound `80` and `443` from anywhere, `22` from your IP only. For both databases,
set Trusted Sources to the droplet **only** — never open them to the internet.

**DNS** — point an A record at the reserved IP. You need a real hostname; certificates are not
issued for bare IPs.

---

## 1b. The face service is a dependency you own

BioCore does not do face matching itself. It calls the **BioVerify** service, and that box has
to be healthy before anyone can register a face or pass a gate. It runs on its own droplet.

Before deploying BioCore, confirm all three — every one of these has failed in practice:

```bash
# 1. reachable, and models actually loaded (not just "ok")
curl -s https://your-bioverify-host/health
#    {"status":"ok","credentials":N,"models_loaded":true}
#    models_loaded:false means enrolment fails; they load lazily on first use

# 2. the API key is accepted
curl -s -H "X-API-Key: YOUR_KEY" https://your-bioverify-host/policy/manifest
#    a 401 here means the key is not one this instance knows

# 3. the TLS certificate matches the hostname — note: NO -k
curl -s -o /dev/null -w "%{http_code}\n" https://your-bioverify-host/health
```

That third one matters more than it looks. If the service moves to a new IP, its `sslip.io`
hostname changes and the old certificate no longer matches. `curl -k` still works, so it looks
fine by hand — but BioCore verifies certificates properly and will refuse to connect, and
**every** registration and gate scan fails. Reissue with
`certbot --nginx -d <new-host>` on that box.

Being one machine with no failover, it is the single point of failure for the whole product.
Plan for it being down: today, a gate simply refuses everyone.

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

Get the code:

```bash
su - biocore
git clone https://github.com/VijayDahiya01/biocare.git
cd biocare/biocore
```

The repository is public, so that clones without credentials. If it is ever made private again,
add a **read-only deploy key** on the droplet rather than a personal access token — a token
usually reaches every repository you own, which is a far larger blast radius if the box is
compromised.

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
REDIS_URL=redis://redis:6379/0        # the container in docker-compose.prod.yml

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
curl -s https://yourdomain.com/api/v1/health          # {"status":"ok"} — is the process alive
curl -s https://yourdomain.com/api/v1/ready           # can it reach everything it needs
curl -sI https://yourdomain.com/admin/login | head -1 # 200
```

`/ready` is the one to point a load balancer at. It returns **503** until every dependency
answers, and names the one that does not:

```json
{"ready":true,"checks":{"postgres":true,"redis":true,"bioverify":true}}
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

**Monitoring.** Turn on DigitalOcean Monitoring with alerts for CPU, memory, disk above 80%.
Point its HTTP check at `/api/v1/ready`, not `/health` — the first tells you the product works,
the second only that the process is alive.

From the app, three counters worth alerting on:

| Counter | Why it matters |
|---|---|
| `bioverify.unknown_outcome` | The face service answered with a word we do not recognise. Every gate is now refusing people, and silently. |
| `bioverify.revoke_failure` | A credential is dead here but alive upstream — someone's QR still works. |
| `gate.mismatch` / `gate.liveness_failure` | A spike is either an attack or a broken camera. |

**Baselines measured against the live service**, so you know what "slow" means: a verification is
about **1.5 s**; a capture the quality gate refuses comes back in about **4.8 s**. A gate scan
much beyond two seconds means something is wrong.

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
| Faces never register | BioVerify unreachable, key rejected, or its certificate does not match its hostname. Step 1b — and test **without** `curl -k`. |
| "That photo wasn't clear enough" every time | The quality gate is refusing the capture, not a bug. More light, face filling the frame, hold still. The reason is in `details.reason`. |
| Everything refused, no obvious cause | Check `bioverify.unknown_outcome`. The service may have changed its answer vocabulary; gates then fail closed on a word we do not recognise. |
| A feature 503s with `LEGACY_ENGINE_RETIRED` | It still runs on the removed ZepIris engine: kiosk 1:N check-in, GPS field check-in, blacklist, or the person "capture once" template. All four need porting to the new engine. |
