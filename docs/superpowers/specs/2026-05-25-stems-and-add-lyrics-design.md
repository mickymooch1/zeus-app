# Stem Separation + Premium Credits + Add My Lyrics — Design Spec

> **For agentic workers:** Use `superpowers:executing-plans` or `superpowers:subagent-driven-development` when implementing the plan derived from this spec.

**Goal:** Add stem separation (split any song into vocals/drums/bass/other) and "Add My Lyrics" (generate a new version with the user's words in the same style), gated behind a unified Premium Credits system renamed from the existing Animation Credits.

**Architecture:** Three sequential subsystems — (1) DB migration + rename throughout Python + UI, (2) fal.ai Demucs stem separation via background polling thread, (3) Add My Lyrics via Apiframe Suno EXTEND on the source song. Each subsystem is independently deployable; subsystem 3 depends on stems existing in DB.

**Tech Stack:** FastAPI backend, SQLite via db.py, fal.ai Demucs (`fal-ai/demucs`, same `FAL_API_KEY` used for Kling), Apiframe v2 UPLOAD + EXTEND (`api.apiframe.ai`), React/Vite frontend (web-beats only).

---

## API Research Findings

- **Apiframe** has no stem separation endpoint — generation only (Suno/Udio).
- **fal.ai `fal-ai/demucs`** — $0.0007/sec, model `htdemucs` (4-stem: vocals, drums, bass, other), output format mp3.
  - Input: `audio_url`, `model`, `stems` list, `output_format`
  - Output: `{vocals: {url}, drums: {url}, bass: {url}, other: {url}}`
  - Submit: `POST https://queue.fal.run/fal-ai/demucs` → `{request_id, status_url, response_url}`
  - Poll `status_url` until `{"status": "COMPLETED"}` then GET `response_url`.
- **Apiframe Suno UPLOAD** — `POST /v2/music/upload` with multipart audio file → `{task_id, audio_url}`.
- **Apiframe Suno EXTEND** — `POST /v2/music/extend` with `{parent_task_id, lyrics, continue_at, webhookUrl, webhookEvents}` → fires same webhook format as generate, handled by existing `/webhooks/apiframe` handler.

---

## Subsystem 1: Premium Credits Rename

### What changes

`animation_balance` → `premium_balance` and `animation_monthly_allowance` → `premium_monthly_allowance` everywhere. The Stripe product IDs (`animation_pack_5`, `animation_pack_15`) are **not renamed** — Stripe webhooks depend on these strings.

### DB migration (db.py)

Add two migrations to the existing try/except migration loop:

```python
"ALTER TABLE song_credits RENAME COLUMN animation_balance TO premium_balance",
"ALTER TABLE song_credits RENAME COLUMN animation_monthly_allowance TO premium_monthly_allowance",
```

SQLite ≥ 3.25 supports `RENAME COLUMN`. Railway's Python image ships SQLite 3.39+.

### Python renames (db.py)

| Old name | New name |
|---|---|
| `get_animation_credits()` | `get_premium_credits()` |
| `upsert_animation_credits()` | `upsert_premium_credits()` |
| `check_and_deduct_animation_credit()` | `check_and_deduct_premium_credit()` |
| `increment_animation_credits()` | `increment_premium_credits()` |
| `reset_animation_credits_balance()` | `reset_premium_credits_balance()` |

All internal SQL uses `premium_balance` / `premium_monthly_allowance`.

Return dict keys change: `{"animation_balance": ..., "animation_monthly_allowance": ...}` → `{"premium_balance": ..., "premium_monthly_allowance": ...}`.

### billing.py

- `_PLAN_ANIMATION_CREDITS` → `_PLAN_PREMIUM_CREDITS`
- All calls to `db.upsert_animation_credits` → `db.upsert_premium_credits`
- All calls to `db.increment_animation_credits` → `db.increment_premium_credits`
- All calls to `db.reset_animation_credits_balance` → `db.reset_premium_credits_balance`
- Pack labels in `ANIMATION_PACKS` dict: `"label": "5 premium credits"` etc. (UI text only)

### main.py

- Hardcoded SQL at line ~526: `SET animation_balance = 50 ...` → `SET premium_balance = 50 ...`
- `GET /api/credits` response: `"animation_credits"` → `"premium_credits"`, `"animation_monthly_allowance"` stays as is (frontend already reads it by this key — update both).
- All `db.get_animation_credits` → `db.get_premium_credits` calls
- All `db.check_and_deduct_animation_credit` → `db.check_and_deduct_premium_credit` calls

### webhooks.py

- `db._db.check_and_deduct_animation_credit(...)` → `db._db.check_and_deduct_premium_credit(...)`

### Frontend (both SongsPage.jsx files)

- State init: `animation_credits: 0, animation_monthly_allowance: 0` → `premium_credits: 0, premium_monthly_allowance: 0`
- All `credits.animation_credits` → `credits.premium_credits`
- UI text: `"animation credits"` → `"premium credits"`
- UI text: `"Buy Animation Credits"` → `"Buy Premium Credits"`
- Buy button packs: label `"5 animations"` → `"5 premium credits (animated covers + stems)"`
- Helper text: add below credit count: `"Used for animated covers & stem separation"`

---

## Subsystem 2: Stem Separation

### DB schema additions (song_variants)

```sql
ALTER TABLE song_variants ADD COLUMN stems_status TEXT;
ALTER TABLE song_variants ADD COLUMN stems_vocals_url TEXT;
ALTER TABLE song_variants ADD COLUMN stems_drums_url TEXT;
ALTER TABLE song_variants ADD COLUMN stems_bass_url TEXT;
ALTER TABLE song_variants ADD COLUMN stems_other_url TEXT;
```

Added to existing migration loop in `db.py`.

### Backend: POST /api/songs/variants/{variant_id}/stems

Located in `main.py`. Request body: none.

```
1. Auth: current_user must own the variant
2. Fetch variant; if stems_status IN ('pending', 'complete') return early
3. Check + deduct 1 premium credit (db.check_and_deduct_premium_credit)
   → 402 if insufficient: "You need at least 1 Premium Credit to get stems"
4. SET stems_status = 'pending'
5. Launch threading.Thread(_stem_pipeline, args=(variant_id, variant["mp3_url"]))
6. Return {"status": "pending", "variant_id": variant_id}
```

### Background thread: _stem_pipeline (songs.py or webhooks.py)

```python
def _stem_pipeline(variant_id: int, mp3_url: str) -> None:
    fal_headers = {"Authorization": f"Key {FAL_API_KEY}", "Content-Type": "application/json"}
    payload = {
        "audio_url": mp3_url,
        "model": "htdemucs",
        "stems": ["vocals", "drums", "bass", "other"],
        "output_format": "mp3",
    }
    resp = requests.post("https://queue.fal.run/fal-ai/demucs", headers=fal_headers, json=payload, timeout=30)
    resp.raise_for_status()
    body = resp.json()
    status_url = body["status_url"]
    response_url = body["response_url"]

    # Poll until complete (max 30 × 10s = 5 min)
    for attempt in range(30):
        time.sleep(10)
        sr = requests.get(status_url, headers={"Authorization": f"Key {FAL_API_KEY}"}, timeout=15)
        if sr.json().get("status") == "COMPLETED":
            result = requests.get(response_url, headers={"Authorization": f"Key {FAL_API_KEY}"}, timeout=15).json()
            # result shape: {"vocals": {"url": "..."}, "drums": {...}, "bass": {...}, "other": {...}}
            db.save_stems(db_path, variant_id,
                vocals_url=result["vocals"]["url"],
                drums_url=result["drums"]["url"],
                bass_url=result["bass"]["url"],
                other_url=result["other"]["url"])
            return
        if sr.json().get("status") in ("FAILED", "ERROR"):
            db.fail_stems(db_path, variant_id)
            db.increment_premium_credits(db_path, user_id, 1)  # refund
            return

    db.fail_stems(db_path, variant_id)  # timeout
```

`_stem_pipeline` lives in `webhooks.py` alongside `_kling_pipeline` (same pattern).

### New db.py helpers

```python
def save_stems(db_path, variant_id, *, vocals_url, drums_url, bass_url, other_url):
    # UPDATE song_variants SET stems_status='complete',
    #   stems_vocals_url=?, stems_drums_url=?, stems_bass_url=?, stems_other_url=?
    # WHERE id=?

def fail_stems(db_path, variant_id):
    # UPDATE song_variants SET stems_status='failed' WHERE id=?
```

### Backend: GET /api/songs/variants/{variant_id}/stems

Returns current stems state. Frontend polls this while status='pending'.

```json
{
  "stems_status": "complete",
  "stems_vocals_url": "https://fal.media/...",
  "stems_drums_url": "https://fal.media/...",
  "stems_bass_url": "https://fal.media/...",
  "stems_other_url": "https://fal.media/..."
}
```

### Frontend — web-beats SongsPage.jsx only

Each complete song card gains a **"🎵 Stems"** action button (next to Play, Download, etc.).

**States:**
- `stems_status == null` AND user has premium credits: show **"🎵 Get Stems"** button (grey, costs 1 credit)
- `stems_status == null` AND user has 0 credits: show disabled "🎵 Get Stems" with tooltip "Needs 1 Premium Credit"
- `stems_status == 'pending'`: show **"⏳ Processing..."** (poll `GET .../stems` every 5s)
- `stems_status == 'complete'`: show **"🎵 Stems ▾"** toggle button → expands stems panel

**Stems panel (expanded):**
```
┌──────────────────────────────────────────────────────┐
│ 🎤 Vocals      [▶ play]  [⬇ download]               │
│ 🥁 Drums       [▶ play]  [⬇ download]               │
│ 🎸 Bass        [▶ play]  [⬇ download]               │
│ 🎹 Melody/Other [▶ play] [⬇ download]               │
│                                                      │
│              [✍️ Add My Lyrics →]                    │
└──────────────────────────────────────────────────────┘
```

Each row uses an `<audio controls src={url}>` element and an `<a href={url} download>` link.

State additions per song card: `stemsOpen: bool`, `stemsData: {status, vocals_url, ...}`, `stemsPollTimer: ref`.

---

## Subsystem 3: Add My Lyrics

**What it does:** Takes the source song's MP3, uploads it to Apiframe's Suno UPLOAD endpoint to get a `parent_task_id`, then calls Suno EXTEND with the user's custom lyrics and `continue_at: 0`. Suno generates new music that continues from the harmonic/style context of the source song with the user's words sung over it. The result appears as a new song variant in the user's library.

**Cost:** 1 song credit (same as regular song generation). No additional premium credits needed.

**Important caveat:** Suno EXTEND with `continue_at: 0` does not overlay vocals onto the original audio — it generates **new** music starting from the style context of the uploaded track. The result will sound like the same genre and vibe with the user's lyrics. This is explained in the UI: "Generate a new track in this style with your words."

### Backend: POST /api/songs/variants/{variant_id}/add-lyrics

Located in `main.py`. Request body: `{lyrics: string}`.

```
1. Auth: current_user must own the source variant
2. Validate: lyrics non-empty, max 2000 chars
3. Fetch source variant → style_prompt, genre_tag
4. Check + deduct 1 song credit (existing _check_and_deduct_credit)
5. Create lyrics row: INSERT INTO lyrics (user_id, lyrics_text) VALUES (?, ?)
6. Create pending variant: INSERT INTO song_variants (lyric_id, user_id, style_prompt,
   genre_tag, status) VALUES (?, ?, ?, ?, 'pending') → new_variant_id
7. Commit transaction
8. Launch threading.Thread(_add_lyrics_pipeline,
     args=(new_variant_id, variant["mp3_url"], lyrics_text, style_prompt))
9. Return {"variant_id": new_variant_id, "status": "pending"}
```

### Background thread: _add_lyrics_pipeline (webhooks.py)

```python
def _add_lyrics_pipeline(variant_id, user_id, source_mp3_url, lyrics, style_prompt):
    # Step 1: Download source MP3
    audio_data = requests.get(source_mp3_url, timeout=30).content

    # Step 2: Upload to Apiframe
    upload_resp = requests.post(
        f"{APIFRAME_BASE}/v2/music/upload",
        headers={"X-API-Key": APIFRAME_API_KEY},
        files={"audio": ("source.mp3", audio_data, "audio/mpeg")},
        timeout=60,
    )
    upload_resp.raise_for_status()
    parent_task_id = upload_resp.json()["task_id"]

    # Step 3: EXTEND with user lyrics
    extend_resp = requests.post(
        f"{APIFRAME_BASE}/v2/music/extend",
        headers={"X-API-Key": APIFRAME_API_KEY, "Content-Type": "application/json"},
        json={
            "parent_task_id": parent_task_id,
            "lyrics": lyrics,
            "continue_at": 0,
            "webhookUrl": f"{WEBHOOK_URL}?variant_id={variant_id}",
            "webhookEvents": ["completed", "failed"],
        },
        timeout=30,
    )
    extend_resp.raise_for_status()
    # Webhook fires when done → existing /webhooks/apiframe handler saves mp3_url
```

The existing webhook handler at `/webhooks/apiframe` handles the EXTEND response identically to a GENERATE response (same `tracks[]` format), so no webhook handler changes are needed.

### Frontend — web-beats SongsPage.jsx

The **"✍️ Add My Lyrics →"** button in the stems panel opens a modal:

```
┌─────────────────────────────────────────────┐
│  ✍️ Add My Lyrics                    [✕]   │
│                                             │
│  Write your own lyrics below. Zeus will    │
│  generate a new track in the style of this │
│  song with your words.                     │
│                                             │
│  ┌─────────────────────────────────────┐   │
│  │                                     │   │
│  │  (lyrics textarea, 6 rows)          │   │
│  │                                     │   │
│  └─────────────────────────────────────┘   │
│                                             │
│  Costs 1 song credit                       │
│                                             │
│       [✍️ Generate with My Lyrics]         │
└─────────────────────────────────────────────┘
```

On success: modal closes, show toast "Your song is generating! Check your library soon." No immediate redirect — the new variant will appear on next library refresh.

---

## Error Handling

| Scenario | Response |
|---|---|
| fal.ai Demucs fails / timeout | `stems_status = 'failed'`, refund 1 premium credit, user sees "Stems failed — credit refunded" |
| Apiframe UPLOAD fails | Mark variant failed, refund song credit |
| Apiframe EXTEND fails | Webhook fires with `event=failed` → existing handler marks variant failed |
| 0 premium credits when requesting stems | HTTP 402 "You need at least 1 Premium Credit" |
| 0 song credits when adding lyrics | HTTP 402 "Insufficient credits" (existing error) |
| Stems not yet complete when clicking Add My Lyrics | Button disabled (frontend guard) |

---

## File Map

| File | Change type |
|---|---|
| `backend/db.py` | Migration for RENAME COLUMN + 5 new song_variants columns; rename 5 functions; add `save_stems`, `fail_stems` |
| `backend/billing.py` | Rename `_PLAN_ANIMATION_CREDITS` + all db function calls |
| `backend/webhooks.py` | Rename credit calls; add `_stem_pipeline`, `_add_lyrics_pipeline` |
| `backend/main.py` | Rename credit endpoints/responses; add `POST .../stems`, `GET .../stems`, `POST .../add-lyrics` |
| `web-beats/src/pages/SongsPage.jsx` | Rename `animation_credits` → `premium_credits` in state; stems UI on song cards; Add My Lyrics modal |
| `web/src/pages/SongsPage.jsx` | Rename `animation_credits` → `premium_credits` in state + UI text only (no stems UI on this frontend) |

---

## Out of Scope

- Mixing stems server-side to produce a full instrumental (drums+bass+other combined) — stems are provided individually
- Stem separation on web/ (Zeus AI) frontend — beats-only feature
- Stems storage on Railway disk — fal.ai CDN URLs are used directly (they expire after ~1 week; acceptable for MVP)
- Progress percentage on stem processing UI
