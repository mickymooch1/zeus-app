# Zeus Baby Beats — Design Spec

**Date:** 2026-06-06  
**Status:** Approved  
**Scope:** Kid-safe mode for Zeus Beats — parent PIN-switch and dedicated school accounts

---

## 1. Overview

Zeus Baby Beats is a completely child-safe view of Zeus Beats accessible at `/kids`. It serves two distinct audiences:

- **Parents** who want to hand a device to a young child without exposing adult content
- **Schools and teachers** who need a safe, class-managed AI music tool

Both audiences land in the same bright, friendly Zeus Baby Beats environment. The adult cyberpunk UI is never rendered for kids users. All safety guarantees are enforced server-side — the UI is a convenience layer on top of hard backend constraints.

---

## 2. Architecture

### 2.1 Route strategy — `/kids` within web-beats (not a separate app)

Zeus Baby Beats lives at `zeusbeats.com/kids` inside the existing web-beats Vite app. It shares the same backend, auth system, and deployment. A `KidsShell` component renders an entirely separate component tree with its own CSS theme. No adult page components are imported into the kids tree.

**Why not a separate app?**  
A separate deployment (kids.zeusbeats.com) would double infrastructure and maintenance burden. A single app with a strict routing guard achieves the same safety with half the complexity.

### 2.2 Component tree isolation

```
App.jsx
├── /kids  →  KidsShell
│              ├── KidsHomePage   (song or story choice)
│              ├── KidsSongMode   (simplified song creation)
│              └── KidsStoryMode  (existing story pipeline, kids wrapper)
└── /songs, /mixer, /discover, ...  →  adult pages (blocked for school accounts)
```

No adult component is imported anywhere under `KidsShell`. The kids CSS theme is scoped to `KidsShell` and its children only.

---

## 3. Account Types

### 3.1 Database change

Add `account_type` column to the `users` table:

```sql
ALTER TABLE users ADD COLUMN account_type TEXT NOT NULL DEFAULT 'standard';
-- Values: 'standard' | 'school'
```

| Type | Description |
|---|---|
| `standard` | Existing users. Full Zeus Beats access. Can optionally enter Baby Beats via PIN. |
| `school` | New type. Baby Beats only. Route guard blocks all adult routes. |

### 3.2 Standard accounts — parent PIN switch

Parents can switch their device into baby beats mode without creating a second account.

**Setup flow:**
1. Parent opens Account Settings → "Zeus Baby Beats" section
2. Creates a 4-digit PIN (stored bcrypt-hashed in a `kids_pin_hash` column on `users`)
3. A "Switch to Zeus Baby Beats 🧸" button appears in SongsPage header

**Entering Kids Mode:**
1. Parent taps "Switch to Zeus Baby Beats 🧸"
2. PIN modal appears — parent enters their 4-digit PIN
3. On success: `sessionStorage.setItem('kidsMode', '1')` + redirect to `/kids`
4. Session flag keeps the user in kids mode for this browser tab

**Exiting Kids Mode (to hand device back):**
1. "Exit to Zeus Beats" button visible in kids header (only for standard accounts — hidden for school accounts entirely)
2. PIN modal appears again
3. On success: `sessionStorage.removeItem('kidsMode')` + redirect to `/songs`

**First-time (no PIN set):**
If a standard-account user navigates directly to `/kids` without a PIN set, they are redirected to Account Settings with a prompt to set a PIN first. This prevents accidental kid-mode entry without PIN protection.

### 3.3 School accounts — class-managed access

School accounts are registered by an adult teacher. Individual children never have their own logins — the teacher's account is the single login for an entire class.

**Registration flow:**
1. `/schools` registration page (separate from the standard signup page)
2. Fields: School name, Teacher name, Email, Year group / age range, Country
3. Password (standard hashed auth)
4. On submit: `account_type = 'school'` written to DB

**Auto-approve vs. flag for review:**

| Email domain | Action |
|---|---|
| `.sch.uk`, `.edu`, `.ac.uk`, `.school`, `.k12.*` | Auto-approved, account live immediately |
| Any other domain | Account created but flagged: `school_verified = False`. Admin receives Telegram alert. Account works immediately (no blocking), but flagged for Porick to review. |

This is light-touch: schools aren't blocked, but personal Gmail registrations under a "school" account type are surfaced for a quick manual check.

**Post-login routing:**
After login, if `account_type == 'school'`, the backend includes this in the `/me` response. `App.jsx` route guard redirects any non-`/kids` route to `/kids` immediately. There is no path through the UI that reaches adult content.

---

## 4. Safety Guarantees

Safety is enforced at three layers. The UI is convenience; the backend is the real gate.

### 4.1 Backend enforcement

All song generation endpoints check `account_type` from the authenticated user:

- `explicit` is forced to `False` for school accounts regardless of request body
- Adult genre lists (e.g. anything tagged `explicit`) are excluded from responses
- Mixer endpoint returns 403 for school accounts
- Stem separation is available (educational, safe) but adult content filter applies

### 4.2 Route guard (frontend)

`ProtectedRoute` checks `user.account_type`. If `'school'`, any route outside `/kids`, `/login`, `/schools` redirects to `/kids`. This runs client-side on every navigation.

### 4.3 Session flag for standard accounts

`sessionStorage.kidsMode = '1'` keeps kids mode active for the tab. Closing or refreshing the tab clears the flag (intentional — protects against leaving kids mode accidentally active). The PIN is required again each time.

---

## 5. Kids UI Design System

### 5.1 Theme

| Property | Value |
|---|---|
| Background | Gradient: `#FFF9E6` (cream) → `#E0F4FF` (sky blue) |
| Primary | Sunny yellow `#FBD155` |
| Accent 1 | Coral pink `#FF6B9D` |
| Accent 2 | Mint green `#4ECDC4` |
| Accent 3 | Sky blue `#45B7D1` |
| Text | Deep navy `#1A2B4A` (readable on light backgrounds) |
| Font | Nunito (Google Fonts), rounded and friendly; system fallback `ui-rounded, sans-serif` |
| Border radius | 24px (very rounded, friendly) |
| Button height | Minimum 64px; minimum 280px wide on mobile |
| Animations | Bouncy `scale(1.05)` on hover; `bounce` keyframe on mascot |

No dark backgrounds. No neon. No cyberpunk elements. Zero overlap with adult styles.

### 5.2 Mascot — Ziggy ⚡

"Ziggy" is a friendly baby lightning bolt with a smiley face and small round eyes. Appears in:
- `KidsShell` header (animated bounce)
- Loading states ("Ziggy is making your song...")
- Empty states and success confirmations

Implemented as inline SVG (no external image dependency). Simple geometric shape — round head, zigzag body, star sparkles.

### 5.3 Screens

**KidsHomePage**
- Ziggy mascot centred at top
- "Zeus Baby Beats 🧸" title in Nunito ExtraBold
- Two giant buttons stacked vertically:
  - 🎵 **Make a Song!** (yellow, primary)
  - 📖 **Hear a Story!** (coral pink)
- Small "Exit to Zeus Beats" link at bottom (standard accounts only, requires PIN)

**KidsSongMode**
- Prompt: "What kind of song do you want? 🎶"
- Theme picker — large emoji tiles (not text dropdowns):
  - 🐘 Animals · 🚀 Space · 🌈 Magic · 🐠 Ocean · 🦁 Safari · ❄️ Winter
- Age range: Tiny Tots (2-4) · Little Ones (4-6) · Big Kids (7-10)
- Optional: "Who is the song about?" free text (name/character)
- Big yellow "Make My Song! ✨" button
- No genre selectors, no accent selectors, no model version, no explicit toggle

**KidsStoryMode**
- Prompt: "What should the story be about? 📖"
- Story theme tiles: 🐉 Dragons · 🧚 Fairies · 🌙 Bedtime · 🏴‍☠️ Pirates · 🦄 Unicorns · 🌳 Forest
- Language selector (same as existing — supports foreign language stories)
- Age range selector
- "Tell My Story! 📖" button
- Same ElevenLabs pipeline as existing story mode

**ParentPINGate (modal)**
- Simple 4-digit PIN pad (large tap targets)
- Title: "Parent exit code 🔑"
- On wrong PIN: friendly shake animation, "Oops! Try again 😊"
- No indication of how many attempts (avoid frustrating kids who poke it)

---

## 6. School Registration Page (`/schools`)

Separate registration page from standard `/register`. Fields:

| Field | Validation |
|---|---|
| School name | Required, min 3 chars |
| Teacher full name | Required |
| Email | Required, valid email format |
| Year group / age range | Dropdown: Reception–Year 6 / Ages 5-11 |
| Country | Dropdown (UK default) |
| Password | Min 8 chars, standard strength rules |
| How did you hear about us? | Optional dropdown |

On submit:
1. Create user with `account_type = 'school'`
2. Domain check → set `school_verified = True/False`
3. If `school_verified = False`: Porick sends Telegram alert to admin: "🏫 New school signup from [email] — personal domain, needs review"
4. Redirect to `/kids` immediately (accounts are not blocked pending review)

No individual child data is collected. The teacher email is the only personal data stored.

---

## 7. COPPA / GDPR-K Compliance

School accounts are managed by adult teachers. Zeus Baby Beats does not collect personal data about individual children. This is a fundamental design constraint, not an afterthought.

**What is NOT stored:**
- Individual child names
- Child ages (only collected as a class-level "year group" on the teacher's account)
- Child-level usage data or song history (all songs belong to the teacher's account)
- Any data that could identify a specific child

**What IS stored:**
- Teacher email and name (adult data, standard GDPR)
- School name and year group (institutional, not personal)
- Songs and stories generated (owned by the teacher's account)

**Privacy policy additions required:**
- A "Children's Privacy" section explaining Zeus Baby Beats does not collect children's personal data
- Clarification that school accounts are teacher-managed
- Statement that Zeus Beats is not directed at children under 13 for direct registration (COPPA safe harbour)
- GDPR-K: school accounts operate under the teacher's consent as the responsible adult

**Action item:** Update `PrivacyPage.jsx` and the backend privacy policy endpoint to include a "Children's Data" section before Zeus Baby Beats goes live for schools.

---

## 8. Backend Changes Summary

| Change | File | Detail |
|---|---|---|
| `account_type` column | `db.py` | `'standard'` \| `'school'`, default `'standard'` |
| `kids_pin_hash` column | `db.py` | bcrypt hash of 4-digit PIN; nullable |
| `school_verified` column | `db.py` | Boolean, used for admin flagging |
| PIN set/verify endpoints | `main.py` | `POST /kids/pin/set`, `POST /kids/pin/verify` |
| School registration endpoint | `main.py` | `POST /auth/register/school` — domain check + Telegram alert |
| Safety enforcement middleware | `main.py` | Explicit forced false, mixer blocked for school accounts |
| `/me` response | `main.py` | Include `account_type` so frontend route guard works |

---

## 9. Frontend Changes Summary

| Component | Location | Detail |
|---|---|---|
| `KidsShell.jsx` | `web-beats/src/components/` | Layout wrapper, theme provider, Ziggy mascot header |
| `KidsHomePage.jsx` | `web-beats/src/pages/kids/` | Landing: two big buttons |
| `KidsSongMode.jsx` | `web-beats/src/pages/kids/` | Simplified song creation |
| `KidsStoryMode.jsx` | `web-beats/src/pages/kids/` | Story creation, kids-wrapped |
| `ParentPINGate.jsx` | `web-beats/src/components/` | PIN modal (enter and exit) |
| `KidsLoginPage.jsx` | `web-beats/src/pages/kids/` | School login, kids-themed |
| `SchoolRegisterPage.jsx` | `web-beats/src/pages/` | School registration form |
| `App.jsx` | `web-beats/src/` | Route guard for school accounts + `/kids` routes |
| `SongsPage.jsx` | `web-beats/src/pages/` | Add "Switch to Baby Beats" button to header |
| `AccountSettings` | `web-beats/src/pages/` | PIN setup section |
| `kids.css` | `web-beats/src/` | Separate stylesheet — light theme only |

---

## 10. Out of Scope

- Individual child user accounts (by design — COPPA)
- In-app messaging between children
- Class management dashboard for teachers (Phase 2)
- Kling video animation in kids mode (CSS Ken Burns only)
- Kids-specific billing (school accounts use standard subscription; pricing TBD)
- Mobile app Kids Mode (Phase 2 — apply same patterns to Expo app)
