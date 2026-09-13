# BioCore — Pitch Deck Source

> **How to use this doc:** each `## Slide N` is one slide. The **Headline** is the
> big text on the slide; **On-slide** bullets are what you put on it (keep them
> short); **Say** is your spoken track. `‹fill in: …›` marks anything you must
> replace with your own real numbers — **do not ship placeholders or invented
> metrics in a real raise.** A tight 12-slide cut is marked ⭐; the rest is depth
> for Q&A / appendix.

---

## One-liner & taglines (pick one)

- **"One face. Every place."**
- **"Your face is your badge — everywhere, on your terms."**
- **"Face-first attendance & access, built for India's privacy era."**

**Elevator pitch (30 sec):**
> BioCore is a face-authentication platform for attendance, access, and visitor
> management. A person verifies their face **once** and uses it to check in at any
> place they belong — office, gym, school, hotel — in under two seconds, contactless.
> Businesses get real-time presence, access control, visitor handling, and emergency
> headcount. And it's built ground-up for India's **DPDP** data-protection rules:
> consent before capture, **only a math vector is stored (never the photo)**, and
> one-tap erasure. Compliance isn't a feature — it's the foundation.

---

## ⭐ Slide 1 — Title

**Headline:** BioCore — *One face. Every place.*
**On-slide:**
- Face-authentication platform for attendance, access & visitor management
- ‹fill in: presenter name, role, date, contact›
**Say:** "We're building the identity layer for the physical world — starting with
how people prove who they are when they walk through a door."
*[Visual: logo on the crimson brand mark; product screenshot of the user app login.]*

---

## ⭐ Slide 2 — Problem

**Headline:** Proving "who's here" is broken — and now it's a legal risk.
**On-slide:**
- **Cards & PINs** get shared, lost, cloned → buddy-punching, tailgating
- **Fingerprint scanners** are slow, unhygienic, hardware-bound; paper visitor books are useless in an emergency
- **Every business is a silo** — a person re-enrolls their biometrics again and again
- **Biometric data is now radioactive:** India's DPDP Act makes storing faceprints without consent, minimization & erasure a compliance time-bomb — and most attendance vendors store raw faceprints
**Say:** "Attendance and access tech is stuck between insecure (cards) and clunky
(fingerprint). Worse — the biometric systems that exist were built before DPDP, so
they're now liabilities."
*[Visual: 4 pain icons; a "compliance gap" callout.]*

---

## ⭐ Slide 3 — Solution

**Headline:** Check in with your face. Captured once. Consented everywhere.
**On-slide:**
- **<2 second, contactless** face check-in / check-out
- **One identity per person** across every place they belong — capture once, reuse with a one-tap consent
- **Privacy by design:** consent-gated, **vector-only (photo discarded)**, erasable anytime
- One platform for **attendance + access + visitors + emergency + events**
**Say:** "BioCore flips it. The person owns one verified identity; each business they
join just gets a consented reference — not a photo. Fast for users, defensible for
businesses."
*[Visual: the guard console "Welcome, Rahul Kumar" result card + the mobile hub.]*

---

## Slide 4 — Why now

**On-slide:**
- **DPDP enforcement** → every biometric system must *prove* consent, minimization & erasure (most can't)
- **Contactless** is the post-COVID default
- **Cheap cameras + on-device face models** kill the need for fingerprint hardware
- **Multi-org lives:** people belong to many places (gig work, memberships, campuses) → demand for portable identity
**Say:** "The regulation, the hardware curve, and how people work all moved at once.
A privacy-first, camera-only, person-centric model is suddenly the right answer."

---

## ⭐ Slide 5 — Product: four surfaces, one platform

**On-slide:**
- 📱 **User app** — mobile-first; one login for every place; consent & history in the user's hands
- 🛡️ **Guard console** — staffed terminal: live scan, alerts, who's-inside, enroll walk-ins, school pickup, manual override
- 🖥️ **Self-service kiosk** — unattended, always-on face check-in
- 🧭 **Admin portal** — ‹28 screens›: attendance, access, devices, HR, reports, audit, emergency, more
**Say:** "Four front doors into one tenant-isolated backend."
*[Visual: 2×2 grid of real screenshots — user app, guard, kiosk, admin dashboard.]*

---

## ⭐ Slide 6 — How it works

**Headline:** Enroll once → allow per place → check in by face.
**On-slide (flow):**
1. **Verify once** — capture face with explicit consent (4 acknowledgements)
2. **Join a place / event** — one-tap "allow my face here," no re-scan
3. **Check in** — look at the camera; matched & logged in <2s
4. **Business sees** — live presence, access decision, alerts, headcount
**Say:** "The magic is step 2 — onboarding to the next business is a single tap
because the verified identity already exists."
*[Visual: 4-step horizontal flow with the real result states (Welcome / Goodbye / Access denied).]*

---

## ⭐ Slide 7 — The moat: person-centric identity + network effect

**Headline:** Every business added makes the next onboarding one tap.
**On-slide:**
- Traditional vendors re-enroll biometrics **per business** (cost, friction, duplicate risk)
- BioCore: **enroll once, reuse with consent** → user value compounds with each place
- Two-sided pull: more **people** enrolled → easier for **businesses** to onboard staff/visitors, and vice-versa
- Switching cost = the user's consented graph of places, history & badges
**Say:** "This is why we win long-term: a portable, consented identity graph that gets
stickier and cheaper-to-onboard the more it's used."

---

## ⭐ Slide 8 — Compliance is the wedge (DPDP by design)

**Headline:** We don't bolt on privacy. It's the architecture.
**On-slide:**
- **Consent before capture** — no face is taken without a logged, per-purpose consent
- **Data minimization** — store only the **math vector**; raw image is **never persisted**
- **Per-place & per-event consent**; user can **withdraw** anywhere
- **Verified erasure cascade** — vectors + storage + DB + cache, with proof
- **Append-only audit trail**; **India data localization**; **tenant isolation** (DB row-level security)
**Say:** "For an Indian buyer, this is the difference between a tool they can deploy
and a fine waiting to happen. Compliance is our sales wedge, not a checkbox."
*[Visual: a "consent → vector-only → erase" privacy lifecycle diagram.]*

---

## Slide 9 — Who it's for (one platform, many verticals)

**On-slide:**
| Vertical | What BioCore does |
|---|---|
| Offices / IT | Attendance, access by zone/hours, PPE, emergency muster |
| Schools | **Guardian pickup verification**, timetable, attendance |
| Gyms / clubs | Membership check-in, access, dues |
| Hotels / banks | Staff attendance + **visitor** management |
| Factories / warehouses | **PPE checks**, zones, **emergency headcount** |
| Events | Registration + consented face entry |
**Say:** "Same core, configured per vertical. We can land wherever the compliance
pain and turnstile volume are highest."

---

## Slide 10 — More than attendance: the operations layer

**On-slide:**
- **Access control** — badges, zones, allowed hours, PPE gate
- **Visitor management** — invite, walk-in enroll, temporary passes
- **Safety** — blacklist alerts, **emergency muster** (live roll + PDF)
- **School pickup** — verify the authorized guardian before release
- **Events, memberships, donations, leave/HR, grievances, reports & audit**
**Say:** "Attendance gets us in the door; the operations modules are why they expand
and stay."

---

## Slide 11 — Why we win

**On-slide:**
| | Legacy biometric (fingerprint) | Generic HR/attendance SaaS | DIY / in-house | **BioCore** |
|---|---|---|---|---|
| Contactless / fast | ❌ | partial | varies | ✅ <2s face |
| Person-centric reuse | ❌ | ❌ | ❌ | ✅ |
| DPDP-by-design | ❌ | ❌ | risky | ✅ |
| Ops layer (visitor/PPE/muster/pickup) | ❌ | partial | ❌ | ✅ |
| Multi-tenant / multi-vertical | ❌ | partial | ❌ | ✅ |
**Say:** "Nobody combines person-centric reuse, the full ops layer, and DPDP-grade
privacy in one platform."

---

## Slide 12 — Built & working (status)

**Headline:** This is a working platform, not a slide.
**On-slide:**
- **4 products live in build:** user app, guard console, kiosk, ‹28-screen› admin
- **Multi-tenant** with database row-level isolation; **pluggable face engine**
- **Privacy lifecycle** implemented end-to-end (consent → vector-only → erasure)
- **Production-grade infra:** monitoring, backups, CI, **load-tested (0% errors)**, security-scanned
- ‹fill in: pilots / LOIs / design partners — list real ones or remove this line›
**Say:** "We can demo the real product live, today." *(Then do it — see demo script.)*

---

## Slide 13 — Business model

**On-slide:**
- **SaaS per active user / seat** (the person-graph drives expansion)
- **+ per terminal/device** (kiosk / guard station)
- **+ module add-ons** (visitor, PPE, school pickup, events)
- Tiered by vertical & volume; annual contracts
- ‹fill in: actual price points, ACV, gross margin once known›
**Say:** "Land with attendance seats, expand with devices and modules, grow with the
person network."

---

## Slide 14 — Market

**On-slide:**
- **Bottom-up:** ‹# target businesses in India› × ‹avg seats› × ‹price/seat/mo› = SAM
- TAM: attendance + access control + visitor management, converging
- Beachhead: ‹pick one — e.g., multi-location offices, or K-12 schools›
- ‹cite sources for any TAM/SAM/SOM figure — verify before presenting›
**Say:** "We size bottom-up from real seats and devices, not a top-down hand-wave."

---

## Slide 15 — Go-to-market

**On-slide:**
- **Land:** one high-pain vertical (‹e.g., schools — pickup safety + DPDP›)
- **Expand:** add modules + devices within the account
- **Network:** users carry their identity to the next business → warm onboarding
- **Channel:** system integrators / security-hardware resellers
- ‹fill in: first 3 target logos / segments, sales motion (PLG vs direct)›

---

## Slide 16 — Roadmap

**On-slide:**
- **Now:** core platform + 4 apps + DPDP lifecycle (done)
- **Next (‹0–6 mo›):** ‹real face-engine deployment, first pilots, on-device liveness, offline mode›
- **Later (‹6–18 mo›):** ‹SDK/API for partners, more verticals, analytics, marketplace of modules›
**Say:** "Engine and pilots next; platform and ecosystem after."

---

## Slide 17 — Team

**On-slide:** ‹fill in: founders, roles, the unfair advantage — domain, ML, India
go-to-market, prior exits›
**Say:** "Why us, why now." *(Investors fund this slide as much as the product.)*

---

## ⭐ Slide 18 — The ask / close

**On-slide:**
- **Raising ‹$X›** to ‹deploy real engine + land ‹N› pilots + ‹key hires››
- Use of funds: ‹eng / GTM / compliance / infra splits›
- **Vision:** the consented identity layer for the physical world
**Say:** "Your face, your badge — everywhere you belong, on your terms. We've built the
platform; we're raising to put it in front of the first ‹N› customers."
*[Visual: the tagline full-bleed on the brand mark.]*

---
---

# Appendix (for Q&A / data room — not main deck)

## A1 — Live demo script (~60–90s)
Your working product is your best slide. Suggested flow:
1. **User app** (`/member/login`) → "Dev sign in" → hub: one identity, the places they
   belong, verification status, badges, check-in history. → open a business → events
   & per-event consent. *("The person owns their identity and consent.")*
2. **Guard console** (`/guard`) → live face in the circle → **Welcome / Goodbye**
   (violet), **Access denied / PPE missing** (red), **Not recognised → Enroll
   visitor**, **Who's inside + Emergency muster**. *("The business's window on the gate.")*
3. **Kiosk** (`/kiosk`) → unattended self-service check-in.
4. **Admin** (`/admin`) → attendance feed, devices, audit trail, **erasure** (show the
   consent + erase controls). *("This is the DPDP story, live.")*

## A2 — Architecture & credibility (one slide if asked)
- **Frontend:** Next.js (mobile-first user app; landscape ops consoles)
- **Backend:** FastAPI; **PostgreSQL** with **row-level security** for hard tenant isolation
- **Face:** pluggable engine adapter (**ZepIris**), vector DB (**Milvus**), liveness /
  anti-spoof + **on-device face detection (MediaPipe)** to gate scanning
- **Infra:** object storage (MinIO), Redis sessions, RabbitMQ, monitoring, backups,
  Kubernetes, CI; load-tested at 0% error
- **Security:** Argon2 passwords, OTP for members, CSRF, append-only audit

## A3 — DPDP / privacy detail
- Consent recorded **before** capture, per purpose & per place; withdrawable
- **Only the embedding vector is stored**; raw images discarded by the engine — the
  platform keeps no photo
- **Verified erasure cascade**: vector store + object storage + Postgres + cache
- Append-only audit (DB-enforced), India data localization, per-tenant isolation

## A4 — Module list (admin portal)
Dashboard · Attendance · Users · Devices · Zones · Geofences · HR · Leave · Roles ·
Reports · Blacklist · Alerts · Emergency muster · Visitors · Events · Memberships ·
Badges · Donations · Grievances · Audit · Settings · School timetable · Security ·
Enroll.

## A5 — Brand / design (for deck styling)
- **User app:** crimson `#C8011A` + violet `#6D28D9` on light lavender; **Plus Jakarta Sans**
- **Terminals (guard/kiosk):** light lavender, **Space Grotesk** (display) + **IBM Plex Sans**
- Result colors: **violet = recognised**, **crimson = denied/blacklist**, **grey = no-match**
- Use real product screenshots throughout — the UI is polished; let it sell.

## A6 — Honest status notes (keep internal)
- Face matching runs today on an in-process simulator for dev/demo; **production uses a
  real ZepIris engine** (drop-in via config — no app changes). Stand it up on a GPU host
  for a real biometric pilot.
- No customer/revenue/market figures are filled in here on purpose — add only verified
  numbers before presenting.
