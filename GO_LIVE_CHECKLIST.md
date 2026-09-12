# BioCore — Operational Acceptance & Go-Live Checklist

Maps every production dependency to the **exact switch, file, and verification** required before
a deployment goes live. Grounds `BIOCORE_COMPLETE_CHANGE_SPEC` §22.6 (operational acceptance)
and §22.5 (security testing) in the code as built.

**Status of the build:** every codeable spec section is implemented, tested, and running in dev
(~118 backend tests green). What remains before production is (a) flipping the dev flags,
(b) swapping four external dependencies that have dev stand-ins today, and (c) passing the
operational drills below. Each dev stand-in is **guard-blocked in production** so a half-configured
deployment fails closed rather than running fake.

---

## 1. Production switch summary (env flags)

| Flag | Dev value | **Production** | Enforced by |
|---|---|---|---|
| `ENVIRONMENT` | `development` | `production` | `settings.is_production` (drives every guard below) |
| `FAKE_ZEPIRIS` | `true` | **`false`** | real face engine required (see §2.1) |
| `FAKE_GOV_IDENTITY` | `true` | **`false`** | `get_gov_identity()` forbids fake in prod |
| `GOV_IDENTITY_PROVIDER` | `sandbox` | `sandbox` or prod vendor | factory (see §2.3) |
| `KMS_PROVIDER` | `software` | **`aws` \| `gcp` \| `vault`** | `get_kms()` forbids `software` in prod |
| `KMS_ROOT_KEY` | dev string | *(unset — real KMS holds keys)* | §2.2 |
| `FAKE_REDIS` | `true` | **`false`** | real Redis sessions |
| `DEV_LOGIN` | `true` | **`false`** | dev login bypass off |
| `FAKE_CONNECTORS` | `true` | **`false`** | `get_roster_source/get_event_sink` forbid fake |
| `COOKIE_SECURE` | `false` | **`true`** | HttpOnly+Secure cookies |
| `REQUIRE_SIGNED_CONTEXT` | `false` | **`true`** (hardened gates) | §12.4 signed context |
| `REQUIRE_HARDENED_TERMINAL` | `false` | **`true`** (hardened gates) | §12.3 posture gate |
| `OFFLINE_MODE` | `off` | per site: `off`\|`manual`\|`roster` | §16 |

> After flipping these, the app **fails to mint credentials or verify identity** until the real
> engine, KMS and gov provider are wired — by design.

---

## 2. External dependencies to swap in

### 2.1 Real face engine (ZepIris) — §15.1, §22.6 "real face engine enabled"
- **Now:** embedding/liveness/1:N match run behind a single pluggable adapter
  (`app/adapters/face_engine/`); dev uses `FakeFaceEngine` (sha512, always-live, exact match).
  `entry_service` and `face_credentials` call `get_face_engine()` — no scattered stand-ins.
- **Wire (config-only path):** point `RemoteFaceEngine` at the engine — `FACE_ENGINE=remote` +
  `FACE_ENGINE_URL` (+ `FACE_ENGINE_TOKEN`), and set `FACE_MATCH_THRESHOLD`. Only the HTTP
  field-mapping in `remote.py` may need adjusting to the vendor's exact contract; the business
  logic (embed → liveness → compare) is unchanged.
- **Bump:** `FACE_MODEL_VERSION` / `FACE_TEMPLATE_VERSION` (bound into the encryption AAD, so old
  templates re-enroll on a model change).
- **Verify:** with `FAKE_ZEPIRIS=false` + `FACE_ENGINE` unset, mint AND match both return
  `FACE_ENGINE_UNAVAILABLE` (fail closed); once wired, run §22.2 biometric + §22.3 spoof accuracy
  (FAR/FRR/APCER/BPCER) against the engine (the `test_real_pad_accuracy_against_engine` placeholder).

### 2.2 Real KMS / HSM — §6.5, §22.6 "production keys active"
- **Now:** `SoftwareKms` derives per-tenant KEKs from `KMS_ROOT_KEY` (dev only).
- **Wire:** implement `KmsProvider` (`app/core/crypto/envelope.py`) against AWS KMS / GCP KMS /
  Vault / HSM; add the branch in `get_kms()`; set `KMS_PROVIDER` accordingly. Nothing else changes.
- **Verify:** `KMS_PROVIDER=software` + `ENVIRONMENT=production` raises `KmsError` (test
  `test_software_kms_and_fake_gov_forbidden_in_production`); confirm KMS latency in `/monitoring/metrics`.

### 2.3 Real government provider (prod access) — §19.1
- **Now:** provider-agnostic adapter; **Sandbox (api.sandbox.co.in) wired and live-auth-proven**
  (PAN verify confirmed with a real call; Aadhaar OKYC built, needs one real OTP run to lock schema).
- **Wire:** for production KYC either keep Sandbox with production entitlements, or add another
  `GovernmentIdentityProvider` (DigiLocker/UIDAI-AUA/etc.) and select via `GOV_IDENTITY_PROVIDER`.
- **Verify:** `FAKE_GOV_IDENTITY=false`; `python -m scripts.gov_sandbox_check` authenticates;
  gov-API success rate visible in `/monitoring/metrics`. **Redact logs** (see §3, item 4).

### 2.4 TEE / confidential compute — §17.4
- **Optional**, for high-security customers: run the matching service in a TEE, no swap/core dumps.
- **Wire:** deploy the matcher in a confidential-compute enclave; keep KMS release policy bound to
  attestation. No app-code change to the interfaces.

### 2.5 Real business connectors — §19.2 (as needed per customer)
- **Now:** in-memory fakes behind `RosterSource`/`EventSink`.
- **Wire:** implement the vendor connector, register it in `app/adapters/connectors/__init__.py`,
  set `FAKE_CONNECTORS=false`. `/connectors/catalog` lists the 8 supported kinds.

---

## 3. §22.6 operational-acceptance gate

A deployment is **not ready** until all pass:

- [ ] **Real face engine enabled** — §2.1 wired; `FAKE_ZEPIRIS=false`.
- [ ] **Fake engine disabled** — grep confirms no fake path reachable; mint fails without the engine.
- [ ] **Production keys active** — §2.2; `KMS_PROVIDER` real; `SoftwareKms` blocked.
- [ ] **Government API logs redacted** — confirm no raw gov response / plain ID / photo in logs
      (the adapter returns only minimal claims; run `test_no_biometric_in_logs_or_at_rest`).
- [ ] **Retention rules configured** — set policies via `POST /retention/policies` per data category
      (`GET /retention/policies` to confirm); auto-expiry sweep scheduled.
- [ ] **Fallback entry works** — §16: `OFFLINE_MODE` set; QR/manual (`/entry/manual-review`,
      `/entry/manual-override`) or encrypted roster (`/offline/roster`) exercised at the gate.
- [ ] **Devices paired and trusted** — `POST /devices/pair`; certificates issued;
      `POST /devices/{id}/posture` attested; `REQUIRE_HARDENED_TERMINAL=true`,
      `REQUIRE_SIGNED_CONTEXT=true`.
- [ ] **Monitoring active** — `/monitoring/metrics` + `/monitoring/alerts` scraped/exported to
      Prometheus/OTel; alert routing to on-call configured.
- [ ] **Erasure drill passes** — `POST /privacy/erasure-request` → credential zeroized, subject
      erased, certificate issued (`test_erasure_leaves_nothing_recoverable`).
- [ ] **Backup restore drill passes** — restore a backup to a clean env; confirm templates are
      ciphertext-only at rest and decrypt only via the real KMS.
- [ ] **Incident contacts assigned** — runbook + on-call + DPO/privacy contact documented.

---

## 4. §22.5 security gates (out-of-band, before go-live)

In-process slices pass in the suite (`tests/test_security_program.py`); the full versions are
external engagements:

- [ ] Third-party **API penetration test** (authz, tenant scoping, input handling).
- [ ] **Device-compromise** drill (stolen token/cert → revoke; posture spoof → denied).
- [ ] **Tenant-isolation** audit (RLS; automated check green).
- [ ] **KMS-policy** test (only proofing/matching/erasure/rotation identities can decrypt).
- [ ] **Template-copy** test (AAD binding; automated check green).
- [ ] **Replay / session-hijack** (signed-context nonce + CSRF; automated checks green).
- [ ] **Log & backup leakage** review (no biometric anywhere; automated check green).
- [ ] **Erasure verification** (certificate is a verifiable proof).

---

## 5. Sign-off

| Area | Owner | Date | ✔ |
|---|---|---|---|
| Face engine + spoof accuracy | | | |
| KMS / key management | | | |
| Government provider + log redaction | | | |
| Retention & erasure (DPO) | | | |
| Device trust & gates | | | |
| Monitoring & incident response | | | |
| Security testing (pen test) | | | |

> **Fail-closed guarantee:** with `ENVIRONMENT=production`, `SoftwareKms`, the fake gov provider,
> fake connectors, and (for mint) the fake engine are all rejected — a misconfigured production
> deployment stops rather than silently running on stand-ins.
