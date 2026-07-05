# Zeus Beats iOS — App Store submission reference

Reference material for submitting `com.zeusbeats.app` (App Store Connect Apple ID `6774107649`)
to the App Store. Copy the relevant sections into App Store Connect.

> **⚠️ Before you submit — fill in the two placeholders below and verify them live:**
> 1. `<<DEMO_PASSWORD>>` — the real password for `review@zeusbeats.com` (Apple auto-rejects notes with a demo account that can't log in).
> 2. `<<SUPPORT_EMAIL>>` — your support/contact email.
> 3. Confirm `review@zeusbeats.com` can log in **and** generate a song **right now**, has enough generation credits, and that the backend (`zeus-app-production.up.railway.app`) stays up through the review window.

---

## 1. App Privacy questionnaire answers

Based on what the app actually does: it sends email+password to `/auth/login`, sends typed
prompts + genre + vocal mode to `/api/songs/generate`, fetches the user's generated songs from
`/api/lyrics`, and stores the JWT in the iOS Keychain. No analytics/ads/tracking/crash SDKs; no
WebView; all AI processing happens server-side on our own backend.

**"Do you or your third-party partners collect data from this app?" → Yes**
**"Is data used to track you?" → No** — declare **"Data Not Used to Track You"** (no IDFA, no ad/analytics SDKs).

Declare these **four** data types. For each: **Linked to identity = Yes · Used for tracking = No · Purpose = App Functionality (only).**

| Apple category → item | Why collected |
|---|---|
| Contact Info → **Email Address** | Sent to `/auth/login` to authenticate the account. |
| Identifiers → **User ID** | Server account ID that ties songs to the user. |
| User Content → **Audio Data** | The AI-generated songs saved to the user's library. |
| User Content → **Other User Content** | The text prompt / song description the user types. |

**Do NOT declare** (the app collects none of these): Name*, Phone Number, Physical Address,
Location (coarse/precise), Contacts, **Financial / Payment Info** (no IAP), Health & Fitness,
Browsing/Search History, Photos/Videos, Purchase History, Usage Data, Diagnostics/Crash Data,
Device ID for advertising, Sensitive Info.

\* **Decision:** if accounts store a **display name**, add Contact Info → Name (Linked = Yes,
Tracking = No, Purpose = App Functionality). Signup was simplified to email+password, so if names
aren't captured, leave Name off.

Notes: passwords aren't a declarable "nutrition label" type (only transmitted over HTTPS for
sign-in). The JWT lives in the device Keychain (local, not "collected").

---

## 2. Reviewer notes (paste into "Notes" in App Store Connect)

**Demo account (required to test the core feature)**
Email: `review@zeusbeats.com`
Password: `<<DEMO_PASSWORD>>`

**What Zeus Beats is**
Zeus Beats generates original songs from a short text description. The user types a prompt (e.g.
"a summer afrobeats song about chasing dreams"), picks a genre and a vocal mode, and our backend
produces a complete original track — lyrics, vocals, instrumental, and cover art — which the user
can play and keep in their library. It is a real product with an active backend, not a template,
wrapper, or reskin.

**How to test it (about 60 seconds)**
1. Sign in with the demo account above.
2. On the **Create** tab, tap a "Vibe" preset or type your own description, then pick a genre and tap **CREATE**.
3. Generation takes roughly 30–60 seconds — the screen shows a progress state while the backend works (it is not frozen). When it finishes, a **Play** button appears and the song plays with native audio.
4. Open the **Library** tab to see saved songs; tap any to play.
5. Open the **Profile** tab to see the account and **Sign out**.

**Genuinely native (re: prior 4.3 rejections)**
The app is built in React Native with four distinct, purpose-built native screens — Login, Create,
Library, Profile — using native controls and a native audio player. There is no WebView anywhere in
the app; no screen is a wrapped website. The generation catalog is specific and original (UK
street/grime/drill/afroswing, soul, house, afrobeats, and more, plus full/instrumental/intermittent
vocal modes), backed by our own generation pipeline. This is a single, original app — not one of
multiple similar bundles.

**Business model — no in-app purchases needed**
Zeus Beats is a multiplatform service. Accounts and any paid plans are created and managed on our
website (zeusbeats.com); the iOS app simply provides access to a signed-in user's account and
content, the same way streaming apps do. The app contains no pricing, no purchase flows, and no
in-app purchases. The only external reference is a neutral "manage your account" link.

**Contact:** `<<SUPPORT_EMAIL>>` — happy to help the reviewer or provide a fresh demo account if needed.

---

## Pre-submission checklist (App Store Connect UI)

- [ ] Fill in `<<DEMO_PASSWORD>>` and `<<SUPPORT_EMAIL>>` above.
- [ ] Verify `review@zeusbeats.com` logs in and generates a song right now; ensure it has credits.
- [ ] Confirm the backend stays live through the review window.
- [ ] Attach build **1.0.0 (13)** to the version.
- [ ] Add screenshots, description, keywords, support URL, and **privacy policy URL**.
- [ ] Complete **App Privacy** using section 1 above.
- [ ] Export Compliance: already set via `ITSAppUsesNonExemptEncryption: false` (should not prompt).
- [ ] Paste section 2 into review **Notes**, then **Submit for Review**.
