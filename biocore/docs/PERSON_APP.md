# Person-centric user app — design

A consumer-style app where **one human has one login** that spans every business
they belong to. Confirmed scope:
- **Person-centric identity** (one login, many businesses).
- Home shows **only businesses the person has joined**, grouped by sector (a switcher).
- **Capture face once**, then reuse for any new business/event with a **one-tap,
  per-purpose consent** (no re-scan).
- **Per-event** registration + per-event consent.
- The person only ever sees **their own** data; businesses stay isolated from each other.

This layers on top of the existing tenant-isolated platform without weakening it.

---

## 1. Identity model
A new **global** identity sits above today's per-business membership:

```
persons (global, no tenant)
  id, email/phone (verified), first_name, last_name, created_at
        ▲
        │ person_id (nullable FK)
users (per-business membership — unchanged, still tenant-scoped + RLS)
  ... one row per (person, business); holds role, status, badges, attendance
```

- Today's `users` row = a **membership** of a person in one business. We add
  `users.person_id` to clip memberships onto one identity.
- `persons` has **no tenant_id** (it's global) and is **not** under tenant RLS;
  access is gated in the app to the **authenticated person only**.

## 2. Auth: person session → "enter" a business
- The person signs in once with **email/phone + OTP** → a **person session**
  (carries `person_id`, no tenant). This powers the hub (profile + business list).
- Selecting a business mints/【scopes to】that **membership** (the existing
  tenant-scoped session/role) for everything inside that business.
- The hub's cross-business reads use a **person-scope** helper: it bypasses tenant
  RLS **but hard-filters every query to `person_id = <the caller>`** and audits it.
  This is the data subject reading **their own** data across businesses (a DPDP
  *access* right) — never another person's, and never another person's business data.

## 3. Joining a business (switcher model, no public directory)
Two entry points, both creating a `users` membership linked to the person:
1. **Invite** — a business admin adds the person's email/phone (`business_invites`).
   It appears in the person's app as *"Acme invited you as Employee — Accept"*.
   Accept → membership created (`status=pending_face` or `active` if face already
   reusable, see §4).
2. **Join code** — the person enters the business's `org_code`/QR → same result.

Leaving a business removes the membership and that business's access to the face (§4).

## 4. Face once, per-purpose consent (the important part)
**Capture once → reuse, but consent per purpose.**

- First verification stores the person's **master face template** (`person_faces`,
  global, under the person). 
- For each **new business or event**, the person taps **one "Allow"** (no camera).
  That writes a **purpose-specific consent record** and **provisions the face into
  that business's space** so its kiosks can match her. Consent is per-purpose
  because biometrics are sensitive data under DPDP — but the *capture* is one-time.
- Withdraw consent / leave business / event ends → that space's face access is
  removed. **Erasure** wipes the master template + every provisioned copy.

> **Trade-off to note (touches a non-negotiable).** Today the rule is "raw image
> deleted immediately; only the per-business vector is kept." To *re-provision a
> face into a new business without re-scanning*, the platform must retain something
> reusable at the person level. The verified ZepIris only inserts **by image**
> (not by vector), so "capture once" requires keeping **one encrypted master image/
> template per person**, India-region, **person-controlled and deletable**, used
> solely to provision the face into businesses/events the person explicitly allows.
> This is a deliberate, consented, single-copy exception for the data subject's own
> benefit — it must be approved and documented (it is, here). If not acceptable, the
> fallback is "re-scan per business" (no master retained).

## 5. Events
- A business's events appear inside that business in the app.
- **Register** (`event_registrations`) + a **per-event consent** (one tap, reuses
  the master template). The app shows, per event: *Registered ✓ · Consent ✓* and a
  withdraw control.

## 6. Privacy & isolation guardrails
- A business gets face access **only after** the person allows it for that business.
- Person-scope reads are **hard-filtered to the caller's `person_id`** + audited.
- One business can never see another business's data (tenant RLS unchanged).
- Liveness/spoof still runs at every check-in.
- Full DPDP rights at the person level: export (all businesses), erase (master + copies).

## 7. New API surface (person-facing, person session)
```
POST /person/auth/otp/request | /verify         person login (email/phone OTP)
GET  /person/me                                  profile + verification status
GET  /person/businesses                          my memberships, grouped by sector
POST /person/businesses/join                     join by org code
GET  /person/invites  ·  POST /person/invites/{id}/accept
POST /person/face/enroll                         one-time master capture (consent)
GET  /person/businesses/{membership}             role, badges, verification, check-in history (self)
POST /person/businesses/{membership}/consent     one-tap reuse consent for that business
GET  /person/businesses/{membership}/events
POST /person/events/{event_id}/register          register + per-event consent
POST /person/events/{event_id}/consent/revoke
```
Admin side adds: `POST /businesses/invites` (invite a person by email/phone).

## 8. New screens (person app, `/member/*` to avoid clashing with `/me`)
`/member/login` · `/member` (profile + business cards by sector + pending invites) ·
`/member/verify` (one-time face capture) · `/member/b/[membership]` (role/badges/
verification/check-in history + one-tap consent) · `/member/b/[membership]/events`
(register + per-event consent) · `/member/join` (enter code).

## 9. Phased build
1. **Schema** — persons, `users.person_id`, person_faces, business_invites, event_registrations (migration `0007`).
2. **Person identity + hub** — person OTP auth, `/person/me`, `/person/businesses` (person-scope aggregation + audit).
3. **Join** — invite + accept, join-by-code.
4. **Face-once + per-purpose consent reuse** — master template, provision-on-allow.
5. **Events** — register + per-event consent.
6. **Screens** — the `/member/*` UI.
7. **Tests** — person isolation (a person sees only their own memberships), join, consent-reuse, event consent; acceptance additions.

Backwards compatible: existing `/me`, `/admin`, `/kiosk` and all current APIs are unchanged; this is additive.
