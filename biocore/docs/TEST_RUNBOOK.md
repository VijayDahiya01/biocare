# BioCore — Complete Test Runbook (local)

Everything to click through the whole product on this PC. **Dev/local only** — these
are demo credentials and a dev device token; do not use in production.

## 0. Live essentials

| Thing | Value |
|---|---|
| App base (this PC) | http://localhost:3001 |
| Backend API | http://localhost:8080/api/v1 (health: `/health`) |
| Org code (to join) | **DEMO-2026** (tenant "Demo Co") |
| Admin login | **admin@acme.com** / **demopass123** |
| Guardian (pickup test) | parent@acme.com |
| **Device token** (kiosk/guard) | `dev_Zl9lWXQGyk-ObzvbkUDwiVRUTW8xYm8jDofCCtJDi38` |
| Kiosk URL (pre-paired) | http://localhost:3001/kiosk?token=dev_Zl9lWXQGyk-ObzvbkUDwiVRUTW8xYm8jDofCCtJDi38 |
| Guard URL (pre-paired) | http://localhost:3001/guard?token=dev_Zl9lWXQGyk-ObzvbkUDwiVRUTW8xYm8jDofCCtJDi38 |


> **Camera note:** browsers only allow the webcam on `localhost` or `https`. Test all
> camera screens on **this PC via localhost** (not the phone-over-LAN URL).

---

## How the dev face engine behaves (read first)
`FAKE_ZEPIRIS=true` — no real ML. A scan returns the **most recently enrolled** person
for that tenant, with a 0.99 score; quality always passes, never a spoof. So:
- To see **"Welcome, <name>"**, enroll that person **last**, then scan.
- The in-memory face store **resets if the backend restarts** — re-enroll after a restart.
- This is purely a dev stand-in; real recognition needs the ZepIris engine (see `ZepIris` notes).

---

## Test 1 — User app (person) 📱  `/member`
1. Open **http://localhost:3001/member/login** → click **Dev sign in (skip OTP)**.
2. **Hub:** see your profile, "0 places", empty state. ✅ layout, crimson theme.
3. **Join:** tap **+ Join** → enter **DEMO-2026** → **Join**. Back on hub: "Demo Co",
   sector **OFFICE**, chips **Pending face** + **Tap to allow**. ✅
4. **Verify face (once):** profile → **Verify my face once** → tick all 4 consent rows →
   **Capture my face** (allow camera). → returns to hub, status flips. ✅
5. **Business detail:** open **Demo Co** → status, **Allow/Withdraw face**, badges,
   **check-in history**, **Events** tile. ✅
6. **Events:** open **Events** → register / withdraw (per-event consent). ✅
7. (Privacy) Withdraw face on the business, and confirm it updates. ✅

## Test 2 — Kiosk (self-service) 🖥️  `/kiosk`
1. First enroll a face so there's someone to match — easiest: do **Test 1 step 4**, or
   **Test 3 step 4** (guard enroll a visitor) **right before** this.
2. Open the **Kiosk URL** above → light terminal, top bar + clock, camera in the hint,
   **3-stat strip**.
3. Look at the camera → **Welcome, <name>** (violet) → auto-resets after ~3.5s. ✅
4. Cover the camera / no enrollment → **Not recognised** (grey) state. ✅

## Test 3 — Guard console 🛡️  `/guard`
1. Open the **Guard URL** above (pre-paired). Unattended view: **live face inside the
   circle**, dashed ring → **turns violet when MediaPipe detects your face**. ✅
2. **Scan:** a face fills the circle → scans → **Welcome / Goodbye** (violet), or
   **Access denied** (red) / **Not recognised** (grey + Enroll visitor). ✅
3. **Guard sign in** (top-right): **admin@acme.com / demopass123** → panel appears. ✅
4. **Enroll** tab: name + tick 4 confirmations → **Capture & enroll** a walk-in visitor.
   Now switch to the scan view and look → **Welcome, <that visitor>** (most-recent match). ✅
5. **Alerts** tab: live list + dismiss. **Inside** tab: headcount + **Emergency muster**. ✅
6. **Pickup** tab (school): enter a student id + scan guardian → AUTHORISED / NOT. *(advanced)*

## Test 4 — Admin portal 🧭  `/admin`
1. Open **http://localhost:3001/admin/login** → **admin@acme.com / demopass123**.
2. **Dashboard** → live metrics. **Attendance** → the events from your kiosk/guard scans. ✅
3. **Devices** → see "Demo Terminal (test)"; create another (copy its token → `/kiosk?token=…`). ✅
4. **Users** → the demo users; open one → edit / **erase (DPDP cascade)**. ✅
5. **Audit** → append-only trail of everything you just did (logins, enroll, device, erasure). ✅
6. Browse the rest: Zones, Geofences, HR, Leave, Roles, Reports, Blacklist, Alerts,
   Emergency, Visitors, Events, Memberships, Badges, Donations, Grievances, Settings,
   School timetable, Security. ✅

---

## Quick happy-path (fastest end-to-end, ~2 min)
1. `/guard?token=…` → **Guard sign in** (admin) → **Enroll** tab → enroll yourself
   as a visitor (capture your face).
2. Switch to the scan view → look at the camera → **Welcome, <you>**.
3. `/admin` → **Attendance** → see the check-in event. → **Audit** → see the trail.

## Reset / re-seed (if needed)
- Re-print admin creds: `cd biocore/backend && .venv/Scripts/python scripts/seed_demo.py`
- Backend restart clears the in-memory face store → re-enroll before scanning.
- Need a new device token: Admin → Devices → create (or ask Claude to mint one).

## Known caveats
- Camera only on localhost/https (not phone-over-LAN).
- Real recognition (true match/liveness) needs the ZepIris engine on a GPU host; the dev
  fake just returns the most-recent enrollment. See `docs/PITCH_DECK.md` A6 / ZepIris notes.
