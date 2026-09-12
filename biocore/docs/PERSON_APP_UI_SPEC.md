# BioCore — User App: UI/Design Spec (for the designer)

A complete brief to design the **person-centric user app**. One human logs in once
and manages their identity, the businesses they belong to, face verification, and
events — across **mobile, tablet, and desktop** (responsive, same app).

Everything here maps to a **live API** (base path `/api/v1`). Each screen lists the
exact endpoint(s), the data fields, and the states to design.

---

## 1. Product in one line
"One login for every place you belong to." The user verifies their face **once**,
then joining any business or event is a **single tap** (no re-scan); they can see
their role, check-in history, and consents per place, and withdraw anytime.

## 2. Platforms & responsiveness
- **Mobile-first**, but must look intentional on **tablet & desktop** (not a phone
  column floating in the middle).
- Recommended behavior: content in a centered container that grows — ~600–760px on
  tablet, ~1000–1040px on desktop. Lists of businesses/events become a **grid**:
  **1 col (phone) → 2 (tablet) → 3 (desktop)**.
- Large tap targets (min 44px), thumb-reachable primary actions on mobile.

## 3. Visual direction (reference: bolna.ai)
Dark, modern, gradient-accented, minimal/enterprise. Starting tokens (designer may refine):
| Token | Value |
|---|---|
| Background | deep navy `#0A0E27` with soft radial cyan/blue glows |
| Surface (cards) | `#131B3F`, 1px border `rgba(255,255,255,.09)`, radius 16–18px, soft shadow |
| Text / muted | `#E9ECFF` / `#98A2CC` |
| Accent gradient | `linear-gradient(135deg, #22D3EE, #3B82F6)` (cyan→blue) — brand, primary buttons, key numbers |
| Status colors | green `#4ADE80`, amber `#FBBF24`, red `#F87171` (as translucent pills) |
| Typography | system sans; headings 700–800, body 400–500; H1 22–30px (fluid) |
| Buttons | radius 14px; primary = gradient fill; secondary = translucent surface; pill buttons for inline actions |
| Spacing | 16px base padding; 12–16px gaps |

Iconography: sectors currently use emoji (🏢 office, 🎓 school, 🏨 hotel, 🏋️ gym,
🏥 hospital, 🏭 factory, 🛍️ retail, 🏦 bank, 🏗️ construction, 🏘️ residential,
🏛️ government, 🛕 religious, 🚚 logistics, 🎪 event). **Designer should replace with a
clean icon set.**

## 4. Global patterns (apply to every screen)
- **Auth:** session is a secure cookie set at login; the app just calls the
  endpoints. No tokens to manage in the UI.
- **Response shape:** success `{ "success": true, "data": {…} }`; error
  `{ "success": false, "error": { "code", "message" } }`. Design **error toasts/inline
  messages** from `error.message`; some codes drive specific UX (see screens).
- **Three states per data view:** Loading (skeletons), Empty (friendly illustration +
  CTA), Error (message + retry). Please design all three.
- **401 anywhere → bounce to Login.**

## 5. Navigation map
```
/app/login ─▶ /app (Hub)
                 ├─▶ /app/verify           (one-time face capture)
                 ├─▶ /app/join             (enter org code)
                 └─▶ /app/b/{membership}   (a business)
                        └─▶ /app/b/{membership}/events
```
Suggested chrome: a top app bar (brand + Sign out) on all signed-in screens.
Optional (designer's call): a bottom tab bar on mobile (Home · Verify · Privacy).

---

## 6. Screens

### S1 — Login  `/app/login`
**Purpose:** sign in as a person (email + one-time code). Full-screen hero, no app bar.
**Fields/UI:** email input; after "Send code" → OTP input + "Sign in". A secondary
"Dev sign in" exists for testing (hide in production design).
**API:**
- `POST /person/auth/otp/request` body `{ "email": "you@email.com" }` → `{ "expires_in": 600 }`
- `POST /person/auth/otp/verify` body `{ "email", "otp": "123456" }` → `{ "person_id" }` (sets session)
**States:** default · code-sent (email locked, OTP shown) · error (`OTP_INVALID`) · busy.

### S2 — Hub (home)  `/app`
**Purpose:** the person's dashboard.
**API (load all three):**
- `GET /person/me` → `{ name, email, phone, face_verified: bool, business_count: int }`
- `GET /person/businesses` → `{ by_sector: { "office": [Membership…], "gym": […] }, total }`
- `GET /person/invites` → `{ items: [ { invite_id, business, sector, role } ] }`
**Design:**
- **Profile card** (gradient): avatar (initials), name, email, a **Face verified / Not set up** pill. If not verified → prominent **"Verify my face"** button → S3.
- **Metrics row:** Places, Invites, Verified (small stat tiles).
- **Invitations** (if any): card/tile per invite with **Accept** → `POST /person/invites/{invite_id}/accept`.
- **My places**, grouped by **sector** headers; each membership is a **tile**: sector
  icon, business name, role, and pills (status + face-here). Tap → S5. A **"+ Join"** action → S4.
- **Empty state:** "You haven't joined any place yet" + Join CTA.

### S3 — Verify face (one-time)  `/app/verify`
**Purpose:** capture the master face once (consent-gated). Reused everywhere after.
**UI:** 4 **consent toggles** (purpose, sensitivity, rights, freely-given) — camera
disabled until all 4 ticked; then a **camera view** + "Capture my face".
**API:** `POST /person/face/enroll` body `{ "image": "<base64 jpeg/dataURL>", "acknowledgements": { "purpose_understood": true, "sensitivity_understood": true, "rights_understood": true, "freely_given": true } }` → `{ "face_verified": true }`
**States:** consent incomplete (camera locked) · camera live · capturing · success
(→ Hub) · error `IMAGE_QUALITY_FAILED` ("too blurry / no face — retry"). Design a
clear camera framing guide (face ring).

### S4 — Join a business  `/app/join`
**Purpose:** join by organisation code.
**API:** `POST /person/businesses/join` body `{ "org_code": "ACME-2026" }` → `{ membership_id, business, sector, status: "pending_face" }`
**States:** default · busy · error (`INVALID_ORG_CODE`, `ALREADY_MEMBER`). On success → Hub.

### S5 — Business detail  `/app/b/{membership_id}`
**Purpose:** everything about the person **inside one business**.
**API:** `GET /person/businesses/{membership_id}` →
```json
{ "business": "Acme Corp", "sector": "office", "role": "self_user",
  "status": "active", "face_verified_here": true,
  "badges": ["Main Gate", "3rd Floor"],
  "history": [ { "event": "check_in", "at": "2026-06-18T09:02:00+00:00" },
               { "event": "check_out", "at": "…" } ] }
```
**Design:**
- Header: business name + sector·role.
- **Status card** with status pill + face-allowed pill, and the key action:
  - if **not** allowed here → **"Allow my face here"** → `POST /person/businesses/{membership_id}/consent` (one tap, no re-scan). If it returns `NO_MASTER_FACE`, route to S3 first.
  - if allowed → **"Withdraw face use"** → `POST /person/businesses/{membership_id}/consent/revoke`.
- **Badges** as pills.
- A **tile linking to Events** → S6.
- **My check-in history** as a list (event pill + datetime). Empty state: "No check-ins yet."

### S6 — Events  `/app/b/{membership_id}/events`
**Purpose:** the business's events + per-event registration/consent.
**API:**
- `GET /person/businesses/{membership_id}/events` → `{ items: [ { event_id, name, registered: bool, consented: bool } ] }`
- `POST /person/events/{event_id}/register` → `{ registered: true, consent_ref }` (may return `NO_MASTER_FACE` → route to S3)
- `POST /person/events/{event_id}/consent/revoke` → `{ registered: false }`
**Design:** event tiles; show **Register** (not registered) or **Withdraw** + pills
"registered ✓ / consent ✓". Empty state: "No events right now."

### S7 — Privacy / account (recommended addition)
Not yet a screen, but the API exists — please design it:
- **Logout:** `POST /person/auth/logout`.
- **Erase everything (DPDP):** `POST /person/me/erasure` → `{ erased: true, memberships_erased }`.
  Design a serious confirmation flow (explain it wipes face + all memberships).

---

## 7. Reusable components to design
- **App bar** (brand + sign out; sticky, glassy).
- **Profile card** (gradient, avatar w/ initials, verified pill).
- **Stat tile** (number + label).
- **Business/Invite/Event tile** (icon + title + subtitle + pills + chevron/action) — the workhorse; design the grid + hover/press states.
- **Status pill** (active/pending/suspended; face ✓ / tap-to-allow; registered/consent).
- **Primary / secondary / danger buttons**, **pill (inline) button**.
- **Consent toggle row** (checkbox + label).
- **Camera capture** (live view + face guide + capture button + retry on quality fail).
- **Inline error / success banners**, **toasts**, **skeleton loaders**, **empty states**.

## 8. Data dictionary
- **Membership.status:** `pending_email` · `pending_face` · `active` · `suspended` · `erased`. Design a pill style for each.
- **face_verified** (person-level) and **face_verified_here** (per business): booleans → pills.
- **sector:** one of the 15 verticals (icons above).
- **history[].event:** `check_in` · `check_out` (also `break_start`/`break_end`).
- **role:** e.g. `self_user`, `manager` — display as a readable label.

## 9. Key flows (happy paths)
1. **Onboard:** Login → (Hub shows "verify") → Verify face once → Join code / Accept invite → open business → **Allow my face** (1 tap) → done.
2. **Daily:** open Hub → tap a business → see today's check-in/out history.
3. **Event:** business → Events → Register (1 tap, per-event consent) → shows registered ✓.
4. **Privacy:** business → Withdraw face use (per place); or Account → Erase everything.

## 10. Tone & must-haves
- Reassuring about **privacy**: make "verify once," "you control each place," and
  "withdraw/erase anytime" visible and friendly — it's the product's promise.
- Fast, few taps, big buttons; works one-handed on mobile and spacious on desktop.
- Design **loading / empty / error** for every data screen.

---

### Endpoint quick-reference
| Screen | Method · Path | Returns |
|---|---|---|
| Login | POST /person/auth/otp/request · …/verify | session |
| Hub | GET /person/me · /person/businesses · /person/invites | profile, memberships by sector, invites |
| Join | POST /person/businesses/join | membership |
| Invite accept | POST /person/invites/{id}/accept | membership |
| Verify | POST /person/face/enroll | face_verified |
| Business | GET /person/businesses/{id} | role, badges, status, history |
| Allow/Withdraw | POST /person/businesses/{id}/consent · …/consent/revoke | status |
| Events | GET /person/businesses/{id}/events | events + registered/consented |
| Register/Withdraw event | POST /person/events/{id}/register · …/consent/revoke | registered |
| Account | POST /person/auth/logout · /person/me/erasure | — |

*Live OpenAPI/Swagger for exact schemas: `/api/v1/docs`.*
