# BioCore — Security

Scope, automated-scan results, implemented controls, and the pre-go-live
penetration-test plan. Run before each release; gate go-live on a clean external
pen test (Build Plan §2.5: zero critical/high).

## Automated scans (run locally + in CI)
```bash
cd backend
bandit -r app -ll                      # SAST (fails on medium/high)
pip-audit -r requirements.txt          # dependency CVEs
```

### SAST — bandit (latest run)
- **0 medium/high**, 2 low: `B110 try/except/pass` in `app/api/v1/health.py` — the
  readiness probe deliberately swallows store-connection errors and reports
  `false` for that dependency. Accepted (intentional, no security impact).

### Dependencies — pip-audit (latest run)
- ✅ **python-multipart** bumped `0.0.20 → 0.0.31` — clears 6 CVEs (multipart
  parser DoS / resource-exhaustion).
- 🟡 **starlette** (8 advisories) and **pytest** (1, dev-only) remain. Their fixes
  require **starlette ≥ 1.x**, which needs a coordinated **FastAPI ≥ 0.13x** upgrade.
  Attempted in this repo: the jump (starlette 0.41 → 1.3) broke route wiring and the
  test-client API, so it is **staged as a tracked upgrade** behind the CI regression
  gate rather than shipped blind. Plan: bump FastAPI+Starlette together on a branch,
  run the full suite + load test, then merge. (pytest is a dev/test dependency, not
  in the production runtime.)

## Implemented controls (Doc 5 §3.1 / Doc 6 §2.5)
| Control | Where |
|---|---|
| TLS 1.3 only; HSTS; no plain HTTP | `infra/nginx/nginx.conf`, K8s ingress |
| HttpOnly + Secure + SameSite=Strict session cookie | `app/core/sessions.py` |
| CSRF token on all mutations | `app/api/deps.py:enforce_csrf` |
| Argon2 password hashing | `app/core/security.py` |
| Mandatory TOTP 2FA for admin roles | `app/services/auth_service.py` |
| Tenant isolation: app filter **+ Postgres FORCE RLS** | `app/core/db.py`, migrations |
| App connects as a **non-superuser** (RLS not bypassable) | deploy config / CI |
| Immutable audit log (append-only trigger) | migration `0001` |
| Rate limiting (API + tighter face-search) | `infra/nginx/nginx.conf` |
| Webhooks HMAC-SHA256 signed | `app/services/webhook_service.py` |
| Data localisation (India) | `DATA_REGION`, deploy region |
| Verified DPDP erasure cascade + certificate | `app/dpdp/erasure.py` |

## Penetration-test plan (engage an external firm before go-live)
Test at minimum:
- **AuthN/Z:** session fixation, CSRF bypass, TOTP brute-force/replay, role escalation.
- **Tenant isolation / IDOR:** attempt cross-tenant reads/writes by forging ids,
  cookies, and `tenant_id`; confirm 404 + RLS (deliberately remove an app filter in a
  staging build and confirm RLS still blocks).
- **DPDP:** enroll without consent (must 403); verify erasure truly clears all stores;
  confirm audit immutability.
- **Input/abuse:** face-image upload limits, base64/multipart fuzzing, webhook URL
  **SSRF**, rate-limit effectiveness, OTP enumeration.
- **Transport/cookies/headers:** TLS config, cookie flags, security headers.

Acceptance gate: **zero critical/high** findings; independent DPDP/security review of
the biometric + erasure paths (real legal liability under DPDP).
