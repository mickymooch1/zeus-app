# "Your Sound" — Sonic Persona Feature Design Spec

**Date:** 2026-05-26  
**Status:** Approved for implementation  
**Provider strategy:** Option A — CometAPI as parallel provider (persona + persona-based generation only); Apiframe unchanged for regular generation, images, and cover-song.

---

## Goal

Users can "lock" one of their finished songs as their sonic DNA. All future generations automatically use CometAPI's `persona_id` to maintain their unique style across every genre they try. This is gated behind a paid plan to drive upgrades.

---

## Architecture

### New files
- **`backend/cometapi.py`** — CometAPI client: persona creation + persona-based song generation. Isolated from `songs.py` and `webhooks.py` so CometAPI can be swapped or extended without touching proven Apiframe paths.

### Modified files
- **`backend/db.py`** — three new `ALTER TABLE users` migrations (idempotent try/except pattern)
- **`backend/main.py`** — two new endpoints (`POST /api/user/sound`, `DELETE /api/user/sound`); modified `POST /api/songs/generate` to branch on persona; extended `/api/auth/me` response to include persona fields
- **`backend/webhooks.py`** — new `POST /webhooks/cometapi` handler for async generation callbacks from CometAPI
- **`web-beats/src/pages/SongsPage.jsx`** — "Lock My Sound" button on completed song cards; "Your Sound Active" pill with inline X reset near Generate button
- **`web-beats/src/pages/BillingPage.jsx`** — "Your Sound" settings section

---

## Database

Three columns added to the `users` table via the existing idempotent migration loop:

```sql
ALTER TABLE users ADD COLUMN sound_persona_id TEXT
ALTER TABLE users ADD COLUMN sound_persona_variant_id INTEGER
ALTER TABLE users ADD COLUMN sound_persona_title TEXT
```

- `sound_persona_id` — CometAPI persona UUID (null = no persona set)
- `sound_persona_variant_id` — FK to `song_variants.id`, the reference song
- `sound_persona_title` — display title of the reference song (denormalised for cheap reads)

New `db.py` helpers:
- `set_sound_persona(db_path, user_id, *, persona_id, variant_id, title) -> None`
- `clear_sound_persona(db_path, user_id) -> None`

Both helpers live alongside existing user-update functions and use the pattern-level `_conn()` helper.

---

## CometAPI module — `backend/cometapi.py`

### Environment variables
```
COMETAPI_API_KEY=<key>
COMETAPI_WEBHOOK_URL=https://zeusaidesign.com/webhooks/cometapi
```

### Pre-build verification (step 0)
The public CometAPI docs confirm `persona_id` as a generation parameter with `task: artist_consistency` but do not publicly document a persona-creation endpoint. Before implementing `create_persona()`, verify against CometAPI's authenticated docs which scenario applies:

- **Scenario A (expected):** A dedicated endpoint (e.g. `POST /suno/submit/persona`) takes `audio_url` and returns `persona_id`. Use this.
- **Scenario B (fallback):** No creation step exists — `persona_id` is caller-supplied; style reference is passed as `audio_url` in generation. In this case, generate a UUID locally and store the mp3_url alongside it; pass both at generation time.

`create_persona()` is wrapped in its own function so either scenario can be implemented without changing callers.

### Public interface
```python
COMETAPI_BASE = "https://api.cometapi.com"

def create_persona(mp3_url: str, title: str) -> str:
    """Create a style persona from a finished song MP3. Returns persona_id."""

def generate_with_persona(
    variant_id: int,
    lyrics: str,
    style_prompt: str,
    persona_id: str,
    webhook_url: str,
    extra_suno_params: dict | None = None,
) -> str:
    """Submit song generation to CometAPI using persona. Returns CometAPI task_id."""
    # POST https://api.cometapi.com/suno/submit/music
    # Body: { mv: "chirp-fenix", prompt: lyrics, tags: style_prompt,
    #         persona_id: persona_id, task: "artist_consistency",
    #         notify_hook: webhook_url, ...extra_suno_params }
```

Auth header: `Authorization: Bearer {COMETAPI_API_KEY}`

---

## API endpoints

### POST /api/user/sound
Lock a song as the user's sonic persona.

**Request body:**
```json
{ "variant_id": 42 }
```

**Flow:**
1. Fetch `song_variants` row — must belong to `current_user`, must have `mp3_url` (400 if not)
2. Check user plan — if `subscription_plan` is null / free: return 402 with `{"detail": "upgrade_required"}`
3. Call `cometapi.create_persona(mp3_url, song_title)` — 502 on failure
4. Call `db.set_sound_persona(db_path, user_id, persona_id=..., variant_id=42, title=song_title)`
5. Return 200:
```json
{
  "sound_persona_id": "uuid-...",
  "sound_persona_title": "Midnight Drift",
  "sound_persona_variant_id": 42
}
```

**Error responses:**
- 400 — variant not complete (no mp3_url)
- 402 — free user (detail: "upgrade_required")
- 404 — variant not found / not owned by user
- 502 — CometAPI persona creation failed

### DELETE /api/user/sound
Clear the persona.

**Response 200:**
```json
{ "ok": true }
```

### GET /api/auth/me (extended)
Existing endpoint; extend the user dict returned to include:
```json
{
  "sound_persona_id": "uuid-...",
  "sound_persona_title": "Midnight Drift",
  "sound_persona_variant_id": 42
}
```
All three default to `null` when not set.

### POST /api/songs/generate (modified)
No change to request shape. Internal branching added after `extra_suno_params` is built:

```python
user_row = db.get_user_by_id(db_path, user_id)
persona_id = user_row.get("sound_persona_id")
if persona_id:
    # CometAPI path
    task_id = cometapi.generate_with_persona(
        variant_id, lyrics, style_prompt, persona_id,
        f"{COMETAPI_WEBHOOK_URL}?variant_id={variant_id}",
        extra_suno_params,
    )
    db.update_variant_provider_job_id(db_path, variant_id, task_id)
else:
    # Existing Apiframe path — unchanged
    ...
```

---

## Webhook — POST /webhooks/cometapi

CometAPI fires to `notify_hook` URL when generation completes. Response shape differs from Apiframe.

**CometAPI response shape (from docs research):**
```json
{
  "task_id": "...",
  "status": "SUCCESS",
  "data": [
    { "audio_url": "https://...", "title": "...", "duration": 180 }
  ]
}
```

**Handler flow:**
1. Parse `variant_id` from query param
2. Verify `status == "SUCCESS"` (log and 200-return on failure — CometAPI expects 2xx regardless)
3. Take `data[0].audio_url` as the mp3 source URL
4. Download + save MP3 using the same logic as the existing Apiframe webhook (`_save_audio()`)
5. Update `song_variants` row: `mp3_url`, `status='complete'`
6. If `animate_cover == 1`: trigger animation pipeline (same as Apiframe path)

CometAPI failed status (`"FAILED"`) → set `status='failed'` in DB, log error.

---

## Free/paid gate

"Lock My Sound" is gated behind any paid plan (`subscription_plan IS NOT NULL AND subscription_plan != 'free'`).

**Backend:** `POST /api/user/sound` returns HTTP 402 with `{"detail": "upgrade_required"}` for free users.

Gate logic (consistent between backend and frontend):
```python
MUSIC_PLAN_KEYS = {"music_starter", "music_pro", "music_agency"}
is_music_paid = (
    bool(user.get("is_admin"))
    or (
        user.get("subscription_status") == "active"
        and user.get("subscription_plan") in MUSIC_PLAN_KEYS
    )
)
```

**Frontend:** "Lock My Sound 🔒" button always visible on completed song cards. On click:
- If user is free → show inline toast: *"Upgrade to Music Starter to unlock Your Sound 🔒"* with a link to `/billing`
- If user is paid → POST /api/user/sound → success toast "Your Sound locked to [title]"

Gate check uses `subscription_plan` and `subscription_status` already returned in `/api/auth/me`.

---

## Frontend — web-beats

### SongsPage.jsx changes

**Song card — "Lock My Sound" button:**
- Shown on every card where `mp3_url` is set (generation complete)
- If this variant is already the locked sound: render "✓ Your Sound" (disabled, cyan text)
- Otherwise: render "🔒 Lock My Sound" button
- On click for free user: show toast "Upgrade to Music Starter to unlock Your Sound"
- On click for paid user: POST /api/user/sound → update local `soundPersona` state → show toast "Your Sound locked!"

**"Your Sound Active" pill (near Generate button):**
- Shown only when `soundPersona.sound_persona_id` is set
- Renders: `🔒 Your Sound Active — [title]` + an **×** button
- × button: calls DELETE /api/user/sound → clears local `soundPersona` state → pill disappears
- Tapping the title text: navigates to /billing (where full settings live)

**State:** `const [soundPersona, setSoundPersona] = useState(null)` — populated from `/api/auth/me` on load.

### BillingPage.jsx — "Your Sound" section

Positioned prominently (above billing/plan details).

**When persona is set:**
```
🎧 Your Sound
🔒 Locked to: "Midnight Drift"
All future songs will use this sonic DNA.
[Change Sound]   [Reset]
```
- "Change Sound" → navigates to `/songs` (no modal; the "Lock My Sound" button on any card is the action)
- "Reset" → DELETE /api/user/sound → clears state

**When not set:**
```
🎧 Your Sound  (paid users only)
Not set — go to any song you love and click
"Lock My Sound" to save your sonic DNA.
```
Free users see the section but with the upgrade prompt instead.

---

## Environment variables

Add to Railway:
```
COMETAPI_API_KEY=<key from cometapi.com>
COMETAPI_WEBHOOK_URL=https://zeusaidesign.com/webhooks/cometapi
```

---

## What this does NOT change

- Apiframe song generation path — untouched
- Cover This Song (Apiframe upload/extend) — untouched
- Portrait generation (Apiframe images) — untouched
- Stem separation (fal.ai Demucs) — untouched
- All existing billing/credits logic — untouched
- web/ (Zeus AI frontend) — untouched

---

## Success criteria

1. Free user clicks "Lock My Sound" → sees upgrade prompt, no API call made
2. Paid user clicks "Lock My Sound" → persona created via CometAPI, all future songs route through CometAPI with that persona_id
3. "Your Sound Active" pill shows on Songs page with × to reset inline
4. Billing page shows locked song title + Change/Reset
5. Resetting persona → next generation goes back to Apiframe automatically
6. CometAPI webhook fires → song saves and animates exactly as Apiframe songs do
7. If CometAPI API key is missing, persona endpoints return 503 (not a 500 crash)
