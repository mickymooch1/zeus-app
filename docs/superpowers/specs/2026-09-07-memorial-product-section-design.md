# Memorial Product Section — dedicated page, simplified flow, one-off pricing

**Date:** 2026-09-07
**Context:** Zeus Beats already has partial memorial support — an `occasion` field
(`song_variants.occasion` includes `"memorial"`), a share-token system, photo upload
(up to 5), a `PhotoCarousel` slideshow, and OG-tag handling on `/songs/share/:token`.
This spec turns that into its own product: a calm landing page at `/memorials`, a
simplified creation flow (no genre grid, no sound control, no Telegram/YouTube/
Avatar/Stems/Remake), a dedicated public page at `/memorial/:token`, and one-off
(non-subscription) Stripe pricing.

## Goals

1. A standalone, non-app-themed entry point (`/memorials`) that doesn't expose the
   normal SongsPage complexity.
2. Reuse the existing song-generation engine (`POST /api/songs/generate`,
   `generationPoller.js`, `GET /api/lyrics/{id}/variants`) — no duplicate generation
   pipeline.
3. Public memorial URLs stay unguessable tokens only — stricter than the existing
   `/songs/share/` route, which also accepts numeric IDs.
4. One-off Stripe pricing, fully isolated from subscription credit pools, with the
   same idempotency guarantees the billing safety net (2026-07-10) added for top-ups
   — no double-grants, no double-charges, verifiable end-to-end.
5. iOS App Store compliance: no pricing/checkout UI reachable from the iOS WebView.

## 1. Routes

- **`/memorials`** — new `MemorialsLandingPage.jsx`. Public, unauthenticated, no app
  chrome. Headline/subtext/CTA per spec. "Create a Memorial" → login gate → credit
  gate (§3) → `/memorials/create`.
- **`/memorials/create`** — new `MemorialWizardPage.jsx`, behind the existing
  `ProtectedRoute`. One component, internal step state: Name → Memories → Song →
  Photos → Review → QR. No per-step sub-routes — nothing else in this app deep-links
  wizard steps, and the steps are strictly linear.
- **`/memorial/:token`** — new `MemorialPage.jsx`. **Token-only**: the frontend
  validates the URL param against the share-token shape before making any network
  call and renders 404 locally on mismatch (e.g. a numeric ID). This is stricter than
  `/songs/share/:variantId`, which resolves both. Belt-and-suspenders: the backend's
  existing `GET /api/songs/variants/{identifier}/public` already withholds photos for
  numeric identifiers regardless of caller, so even a crafted request can't leak
  photos this way — the frontend guard just avoids a pointless coverless page.

All three routes gated `!isIOSWebView` per existing App Store compliance policy;
inside the iOS wrapper, `/memorials` shows "Visit zeusbeats.com to create a
Memorial." instead of the CTA.

## 2. Data model

- `song_variants.tribute_message` (nullable TEXT) — the Memories step, freeform,
  ~1000 char cap enforced client + server side.
- `users.memorial_credits_available` (INTEGER DEFAULT 0) — new balance, separate
  from existing song/premium/video credit types, migrated the same lightweight way
  as other user columns.
- `credit_ledger.credit_type` gains a new value: `'memorial'` (the ledger and
  `record_credit_grant` already support arbitrary credit types — see §3).
- Photo cap: the existing 5-photo limit in the upload endpoint becomes conditional —
  `10` when `song_variants.occasion == 'memorial'`, `5` otherwise. Global default is
  unchanged.

## 3. Payment & entitlement — reusing the credit ledger

Rather than a bare counter increment, this reuses the credit-ledger idempotency
mechanism the billing safety net spec (2026-07-10) built specifically to prevent the
double-grant/silent-failure class of bug:

- New one-off Stripe product in `billing.py`: `MEMORIAL_PACKAGE` (flat price, e.g.
  £49 to start — tune post-launch), `mode: "payment"`, built the same way as
  `create_song_pack_checkout_session` — `payment_method_types: ["card"]`,
  `payment_intent_data.metadata` mirrored (needed for the Apple Pay async-payment
  path), metadata tagged `{"type": "memorial_package"}` for webhook dispatch,
  requires an authenticated `customer` (no guest checkout — account required per
  earlier decision).
- `_handle_checkout_completed` and `_handle_payment_intent_succeeded` each get a new
  branch (mirroring the existing song/animation top-up branches) that on
  `metadata.type == "memorial_package"`:
  1. Calls `db.record_credit_grant(db_path, user_id, email, credit_type="memorial", amount=1, source="checkout_topup"|"payment_intent_topup", stripe_payment_id=pi_id)`.
  2. Only if that returns `True` (newly recorded — the `UNIQUE(stripe_payment_id, credit_type)` constraint is the idempotency gate), calls a new `db.increment_memorial_credits(db_path, user_id, 1)`.
  3. If it returns `False`, logs the skip — exactly the existing dedupe pattern, so
     checkout-completed + payment-intent-succeeded firing for the same
     `payment_intent` can't double-grant, and Stripe's webhook retries can't either.
- `alert_credit_not_granted` covers this branch too, same as the existing top-up
  sites, so a failed grant pages the same way a missed song-pack credit would.

**Generation gating** — extending `POST /api/songs/generate` (not the separate
occasion endpoint) to accept `occasion`, `occasion_name`, and `tribute_message`
directly at creation time, since the wizard collects Name/Memories *before* Song.
When `occasion == "memorial"`:
- Requires `memorial_credits_available > 0` (402 otherwise), decrements it via a new
  `db.decrement_memorial_credits` — and skips the normal subscription/song-credit
  deduction entirely. The one-off purchase pays for the song outright; a subscriber
  does not additionally burn a subscription credit, and a non-subscriber isn't
  blocked by not having subscription credits.
- Stores `occasion`, `occasion_name`, `tribute_message` on the variant at creation,
  removing the need for a follow-up call to the existing occasion endpoint (which
  remains available for later edits from the owner view, §5).

## 4. Wizard flow (frontend)

`MemorialWizardPage.jsx`, steps as internal state:

1. **Name** — whose memorial this is.
2. **Memories** — the freeform tribute text.
3. **Song** — reuses the existing lyric-generation + `POST /api/songs/generate`
   (with `occasion="memorial"`) + `generationPoller.js` against
   `GET /api/lyrics/{id}/variants`, exactly as SongsPage does today, but with no
   genre grid, no Sound Control panel, no kids-mode toggles — a single "Create Song"
   action using sensible fixed defaults.
4. **Photos** — reuses the existing photo upload endpoint/HEIC conversion, capped at
   10 (§2).
5. **Review** — shows the assembled memorial page preview, plaque artwork button
   (disabled, "coming soon" — see §6), and the share link.
6. **QR** — reuses the existing client-side `qrcode.react` generation and
   `mark-qr-generated` call, pointed at `/memorial/{token}` instead of
   `/songs/share/{token}`.

## 5. Public memorial page & owner view

`MemorialPage.jsx` fetches via `GET /api/songs/variants/{token}/public` (existing
endpoint, token path already returns photos). Two render modes:

- **Public** (default): tribute message, `PhotoCarousel` slideshow (reused from
  `SongSharePage.jsx`), song player. Read-only, no edit affordances. Must never be
  indexed — same `noindex` handling as the existing share page.
- **Owner** (logged in and owns the variant — checked via an authenticated
  owner-only fetch keyed on the variant id returned by the public payload): adds
  edit controls (name/tribute via the existing occasion endpoint, photo add/remove),
  QR download, share link — plus a single collapsed **"More song tools ▾"** section.

New small reusable `CollapsibleSection.jsx` (today every panel in `SongsPage.jsx`
hand-rolls its own open/close `useState` — this is the first shared instance).
"More song tools" wraps Telegram/YouTube/Avatar/Stems/Remake, calling the same
backend endpoints directly from `MemorialPage.jsx` rather than importing anything
from `SongsPage.jsx` — that file doesn't currently export reusable handlers, and
coupling a new page to its internals isn't worth it for five button calls.
Non-memorial songs in `SongsPage.jsx` are untouched by any of this.

## 6. Plaque artwork — open item

Deferred per decision. The Review step renders a disabled "Download plaque
artwork — coming soon" button so flow and pricing copy aren't broken. Format
(client-rendered PNG vs. server-rendered PDF) is a follow-up decision once there's a
concrete example of what the artwork should contain.

## Testing (TDD)

Given this touches the billing/webhook path, tested with the same rigor as the
2026-07-10 billing safety net, end-to-end before going live:

- `record_credit_grant` / `increment_memorial_credits`: replayed checkout webhook
  for the same `payment_intent` grants exactly one memorial credit, not two.
- `payment_intent.succeeded` firing after `checkout.session.completed` for the same
  `pi_` does not double-grant (mirrors the existing Apple Pay overlap test).
- `POST /api/songs/generate` with `occasion="memorial"`: decrements
  `memorial_credits_available`, leaves subscription/song credit balance untouched;
  fails 402 with zero memorial credits without touching either balance.
- Photo upload: 10 allowed for `occasion="memorial"`, 11th rejected; non-memorial
  variants still capped at 5.
- `/memorial/:token`: numeric-shaped param never reaches the network call (frontend
  test); public endpoint still withholds photos for a numeric identifier regardless
  (existing behavior, regression-guarded).
- Owner vs. public render mode on `MemorialPage.jsx` for the same token.
- **Manual/staging pass before launch**: one real Stripe test-mode purchase, full
  path — checkout → webhook → credit lands → wizard generates a song consuming the
  memorial credit (not subscription credits) → confirm no double-charge on a
  webhook redelivery (Stripe CLI `stripe trigger` replay) — this is the same failure
  class (unpinned/miswired webhook path) that caused the 2.5-week silent billing gap
  in July; this new branch gets the same manual verification before going live, not
  just unit coverage.

## Out of scope

- Plaque artwork rendering (stubbed, §6).
- Tiered/variable memorial pricing (flat price only, for now).
- Guest checkout (account required, per decision).
- Any change to non-memorial `SongsPage.jsx` behavior or the existing
  `/songs/share/:variantId` route.
