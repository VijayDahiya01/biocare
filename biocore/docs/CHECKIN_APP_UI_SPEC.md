# BioCore — Check-in App (Guard Console): UI/Design Spec

A brief to design the **check-in terminal operated by a guard** (Security/Reception).
It pairs a big live **face scanner** with a guard **operations panel** to handle
exceptions, enroll walk-ins, and watch who's inside. Maps to the live API (`/api/v1`).

> Companion to the user-app spec (`PERSON_APP_UI_SPEC.md`). Most of this backend
> already exists; this is primarily a **console UI**.

---

## 1. Product in one line
"The guard's window on the gate." Every face that looks at the camera is matched and
checked in/out in <2s; the guard sees the result, and steps in for the exceptions
(unknown face, blacklist, access denied, visitor walk-ins).

## 2. Who uses it
The **Security / Reception operator ("guard")** at a gate/desk. Not the public.
A terminal is **paired to a zone/door**; a guard **signs in** on top so their
actions are accountable.

## 3. Platform & form factor (different from the user app!)
- **Landscape, large screen**: wall-mounted tablet, a desk PC with webcam, or a
  10"+ tablet. **Design tablet/desktop-first, landscape.** (The user app was phone-first; this is the opposite.)
- Always-on, **kiosk/full-screen**; readable from a step back; high-contrast.
- Touch **and** mouse; very large primary touch targets; minimal chrome.
- Two layouts to design:
  - **Unattended mode** — full-bleed camera + result only (no guard signed in).
  - **Attended mode** — camera/result + a **guard side panel** (Alerts, Who's inside, Enroll visitor, Manual).

## 4. Visual direction
Reuse the platform's **dark, high-contrast** look (cyan→blue gradient accents) but
**bigger and louder** — this is an operations display:
- **Result is the hero:** huge name + status, full-screen **color wash** by outcome
  (green = in, amber = out, red = denied/blacklist/spoof, grey = unknown).
- Color-coded, glanceable; large type; subtle motion on scan→result→reset.
- Same palette as `PERSON_APP_UI_SPEC.md` (navy `#0A0E27`, surfaces `#131B3F`,
  green `#4ADE80` / amber `#FBBF24` / red `#F87171`).

## 5. Auth model (two layers — design both)
- **Terminal pairing (device token):** the scan/break/pickup calls authenticate with
  an `X-Device-Token` header (set when the terminal is paired to a zone). No login for scanning.
- **Guard sign-in (session):** the guard logs in (Security/Reception role; email +
  password + **2FA**) to unlock the operations panel; their actions are audited.
  Design a **"Guard sign in"** affordance and a **locked/unattended** state.

## 6. Layout map
```
┌───────────────────────────── Check-in terminal (landscape) ─────────────────────────────┐
│  [zone label · device · clock]                         [guard: name ▾  |  Lock]           │
│                                                                                          │
│   ┌──────────────── LIVE CAMERA + face ring ───────────────┐   ┌──── Guard panel ────┐  │
│   │                                                         │   │  ▸ Alerts (n)        │  │
│   │        RESULT WASH: ✓ Welcome, Rahul Kumar              │   │  ▸ Who's inside (n)  │  │
│   │        Checked in · 09:02 · score 0.94                  │   │  ▸ Enroll visitor    │  │
│   │                                                         │   │  ▸ Manual check-in   │  │
│   └─────────────────────────────────────────────────────────┘   │  ▸ Pickup verify    │  │
│                                                                  └─────────────────────┘  │
└──────────────────────────────────────────────────────────────────────────────────────────┘
```
On smaller tablets the guard panel becomes a **slide-over drawer**.

---

## 7. Views

### V1 — Scanner (the always-on hero)
**Purpose:** capture frames continuously, show each result big, auto-reset (~3.5s).
**API:** `POST /faces/search` (header `X-Device-Token`) body `{ "image": "<base64 frame>", "action": "auto" }`.
**Result payload to design for:**
```json
{ "match": true, "user_id": "...", "name": "Rahul Kumar", "score": 0.94,
  "event": "check_in", "duration_minutes": null, "blacklist_hit": false,
  "access": { "gated": true, "granted": true, "reason": "badge_ok" },
  "ppe": { "checked": true, "ok": true, "missing": [] } }
```
**States (each a distinct full-screen treatment):**
| State | Trigger | Guard sees / does |
|---|---|---|
| Idle | no face | "Look at the camera" + face ring |
| Scanning | frame sent | subtle pulse |
| ✅ Check-in | match, granted | green wash, name, time |
| 🟠 Check-out | match, granted | amber wash, name, duration |
| ⛔ Access denied | `access.granted=false` | red, name + **reason** (no badge / outside hours / **PPE missing: vest**) |
| ⛔ Blacklist | `blacklist_hit=true` | red alarm, "Do not admit" |
| ⛔ Spoof | 403 `SPOOF_DETECTED` | red, "Use a real face" |
| ⟳ Retry | 422 `IMAGE_QUALITY_FAILED` | "Hold still / move closer" |
| ✗ Not registered | `match=false` | grey, "Not recognised" + **[Enroll visitor]** shortcut |
Also: **Break mode toggle** → `POST /attendance/break` body `{ "break": "start"|"end", "image }`.

### V2 — Alerts panel
**API:** `GET /alerts` → `{ items: [ { alert_id, type, priority, message, created_at } ] }`;
`POST /alerts/{alert_id}/dismiss`.
**Design:** live list, **critical (blacklist) pinned + red**; unrecognised/access-denied/
PPE as high/medium; each with **Dismiss**. Show an unread **count badge** on the panel tab.

### V3 — Who's inside (presence / headcount)
**API:** `GET /attendance/presence` → `{ inside_count, by_zone, people: [ { name, since } ] }`.
Emergency: `POST /emergency/trigger` → muster snapshot (+ PDF url); `GET /emergency/status`.
**Design:** big **inside count**, searchable people list, and a prominent **"Emergency muster"** button (confirm → snapshot + downloadable roll).

### V4 — Enroll walk-in visitor (on the spot)
**API:** `POST /admin/enroll` body `{ person_type: "visitor", first_name, last_name?, reference_id?, purpose, image, consent_method: "in_person_verbal", expiry_date?, person_present:true, purpose_explained:true, person_consented:true, admin_responsible:true }` → `{ user_id, consent_ref }`.
(Alternatively `POST /visitors/invite` to issue a QR/link the visitor opens.)
**Design:** quick form (name, phone, purpose) → **4 confirmation toggles** (gate the camera) → capture → success card with a temporary pass. Big, fast, few fields.

### V5 — Pickup verify (school)
**API:** `POST /pickup/verify` (header `X-Device-Token`) body `{ image, student_id }` → `{ authorised, guardian_name }`.
**Design:** scan guardian → **AUTHORISED (release child) / NOT AUTHORISED** big result.

### V6 — Manual check-in (override)
For when a face won't scan. **API:** `POST /attendance/manual` body `{ user_id, event: "check_in"|"check_out", timestamp, reason }`.
**Design:** search a member → pick in/out → **reason required** → confirm.
> ⚠️ Backend note for the dev: `attendance/manual` is currently restricted to admin/
> manager/HR roles — **add `security_reception`** so guards can use it (one-line change).

---

## 8. Reusable components
- **Full-screen result card** (per state, color-wash, huge name/status) — the centerpiece.
- **Live camera frame** with face-positioning ring + corner labels (zone, device, clock, today's count).
- **Guard panel tabs** (Alerts / Inside / Enroll / Manual / Pickup) with count badges; slide-over on small screens.
- **Alert row** (priority color, message, time, dismiss).
- **Confirmation toggles** (consent) + capture button (reuse the camera component).
- **Lock / unattended** overlay + **Guard sign-in** modal (email + password + 2FA).

## 9. Data dictionary
- `event`: `check_in` · `check_out` · `break_start` · `break_end`.
- `access.reason`: `badge_ok` · `no_badge` · `outside_hours` · `ppe_missing` · `open_zone`.
- `ppe.missing`: list e.g. `["vest"]`.
- `alerts.type`: `blacklist_hit` · `unrecognised` · `access_denied` · `ppe_violation` · `device_offline`; `priority`: `critical` · `high` · `medium`.
- `score`: 0–1 match confidence (show as %).

## 10. Key flows
1. **Normal entry:** face → green "Welcome, name" → auto-reset.
2. **Unknown:** face → grey "Not recognised" → guard taps **Enroll visitor** → captures → temp pass.
3. **Blacklist/denied:** red alarm → guard holds the person, dismisses/acts via Alerts.
4. **Pickup:** guard opens Pickup verify → scans guardian → AUTHORISED.
5. **Emergency:** guard taps **Muster** → live roll of everyone inside.

## 11. Must-haves
- **Glanceable from 2m**, color-coded, fast auto-reset; works offline-tolerant (show device-offline state).
- Big touch targets; the guard rarely types (mostly taps).
- Unattended mode must be safe to leave running; attended mode adds the panel.
- Design **loading / empty / error / device-unpaired / guard-locked** states.

---
### Endpoint quick-reference
| View | Method · Path | Auth |
|---|---|---|
| Scan | POST /faces/search | device token |
| Break | POST /attendance/break | device token |
| Pickup verify | POST /pickup/verify | device token |
| Alerts | GET /alerts · POST /alerts/{id}/dismiss | guard session |
| Who's inside | GET /attendance/presence · POST /emergency/trigger | guard session |
| Enroll visitor | POST /admin/enroll (or /visitors/invite) | guard session |
| Manual | POST /attendance/manual *(add security_reception role)* | guard session |
| Guard login | POST /auth/login (email+password+TOTP) | — |

*Live schemas: `/api/v1/docs`.*
