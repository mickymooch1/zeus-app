# Stem Separation + Cover This Song Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add stem separation (fal.ai Demucs) and "Cover This Song" (Apiframe Suno EXTEND) to Zeus Beats, gated behind Premium Credits (renamed from Animation Credits).

**Architecture:** Three sequential groups — (A) DB + Python rename throughout codebase, (B) stem separation backend + frontend, (C) Cover This Song backend + frontend. Each group commits independently. The rename must land before groups B and C since they read premium_balance.

**Tech Stack:** FastAPI/SQLite backend, fal.ai Demucs API (polling, same pattern as Kling), Apiframe v2 UPLOAD + EXTEND (existing webhook handler reused), React/Vite (web-beats only for stems UI).

---

## File Map

| File | Change |
|---|---|
| `backend/db.py` | Migrations: RENAME 2 columns + ADD 5 stems columns; rename 5 functions; add `save_stems`, `fail_stems` |
| `backend/billing.py` | Rename `_PLAN_ANIMATION_CREDITS` + 4 db call sites |
| `backend/webhooks.py` | Rename 1 db call; add `_stem_pipeline`, `_cover_pipeline`, `WEBHOOK_URL` env var |
| `backend/main.py` | Rename 2 db calls + inline SQL + API response keys; add 3 new endpoints |
| `web/src/pages/SongsPage.jsx` | Rename state key + 6 UI text occurrences |
| `web-beats/src/pages/SongsPage.jsx` | Rename state key + UI text; add stems state + SongCard props + stems panel + Cover modal |

---

## Task 1: DB Migrations + Renamed Functions + Stems Helpers

**Files:**
- Modify: `backend/db.py:233-281` (migration list)
- Modify: `backend/db.py:1184-1263` (five animation credit functions)

### Steps

- [ ] **Step 1: Add migrations to db.py**

Open `backend/db.py`. Inside the migration list (after the last existing entry before the closing `]:`), add these entries:

```python
            # Premium Credits: rename animation columns (SQLite 3.25+ RENAME COLUMN)
            "ALTER TABLE song_credits RENAME COLUMN animation_balance TO premium_balance",
            "ALTER TABLE song_credits RENAME COLUMN animation_monthly_allowance TO premium_monthly_allowance",
            # Stems columns on song_variants
            "ALTER TABLE song_variants ADD COLUMN stems_status TEXT",
            "ALTER TABLE song_variants ADD COLUMN stems_vocals_url TEXT",
            "ALTER TABLE song_variants ADD COLUMN stems_drums_url TEXT",
            "ALTER TABLE song_variants ADD COLUMN stems_bass_url TEXT",
            "ALTER TABLE song_variants ADD COLUMN stems_other_url TEXT",
```

The existing `try/except: pass` wrapper means already-applied migrations are silently ignored on re-deploy.

- [ ] **Step 2: Rename the five animation credit functions in db.py**

Replace all five functions (lines ~1184–1263). The new versions use `premium_balance` / `premium_monthly_allowance`:

```python
def get_premium_credits(db_path: pathlib.Path, user_id: str) -> dict | None:
    """Return premium_balance and premium_monthly_allowance from song_credits."""
    conn = _conn(db_path)
    try:
        row = conn.execute(
            "SELECT premium_balance, premium_monthly_allowance FROM song_credits WHERE user_id = ?",
            (user_id,),
        ).fetchone()
        return {"premium_balance": row["premium_balance"], "premium_monthly_allowance": row["premium_monthly_allowance"]} if row else None
    finally:
        conn.close()


def upsert_premium_credits(
    db_path: pathlib.Path,
    user_id: str,
    balance: int,
    monthly_allowance: int,
) -> None:
    """Set premium credit columns on song_credits row, creating it if absent."""
    conn = _conn(db_path)
    try:
        conn.execute(
            """INSERT INTO song_credits (user_id, balance, monthly_allowance, premium_balance, premium_monthly_allowance, last_reset)
               VALUES (?, 0, 0, ?, ?, CURRENT_TIMESTAMP)
               ON CONFLICT(user_id) DO UPDATE SET
                   premium_balance = ?,
                   premium_monthly_allowance = ?""",
            (user_id, balance, monthly_allowance, balance, monthly_allowance),
        )
        conn.commit()
    finally:
        conn.close()


def check_and_deduct_premium_credit(db_path: pathlib.Path, user_id: str) -> bool:
    """Atomically deduct 1 premium credit. Returns True on success, False if balance is 0."""
    conn = _conn(db_path)
    try:
        row = conn.execute(
            "SELECT premium_balance FROM song_credits WHERE user_id = ?", (user_id,)
        ).fetchone()
        if not row or row["premium_balance"] < 1:
            return False
        conn.execute(
            "UPDATE song_credits SET premium_balance = premium_balance - 1 WHERE user_id = ?",
            (user_id,),
        )
        conn.commit()
        return True
    finally:
        conn.close()


def increment_premium_credits(db_path: pathlib.Path, user_id: str, amount: int) -> None:
    """Add premium credits to song_credits row (for top-up pack purchases and refunds)."""
    conn = _conn(db_path)
    try:
        conn.execute(
            """INSERT INTO song_credits (user_id, balance, monthly_allowance, premium_balance, premium_monthly_allowance)
               VALUES (?, 0, 0, ?, 0)
               ON CONFLICT(user_id) DO UPDATE SET premium_balance = premium_balance + ?""",
            (user_id, amount, amount),
        )
        conn.commit()
    finally:
        conn.close()


def reset_premium_credits_balance(db_path: pathlib.Path, user_id: str) -> None:
    """Reset premium_balance back to premium_monthly_allowance — called on Stripe monthly renewal."""
    conn = _conn(db_path)
    try:
        conn.execute(
            """UPDATE song_credits
               SET premium_balance = premium_monthly_allowance
               WHERE user_id = ?""",
            (user_id,),
        )
        conn.commit()
    finally:
        conn.close()
```

- [ ] **Step 3: Add save_stems and fail_stems helpers to db.py** (append after `reset_premium_credits_balance`)

```python
def save_stems(
    db_path: pathlib.Path,
    variant_id: int,
    *,
    vocals_url: str,
    drums_url: str,
    bass_url: str,
    other_url: str,
) -> None:
    """Save completed Demucs stem URLs and mark stems_status='complete'."""
    conn = _conn(db_path)
    try:
        conn.execute(
            """UPDATE song_variants
               SET stems_status='complete', stems_vocals_url=?, stems_drums_url=?,
                   stems_bass_url=?, stems_other_url=?
               WHERE id=?""",
            (vocals_url, drums_url, bass_url, other_url, variant_id),
        )
        conn.commit()
    finally:
        conn.close()


def fail_stems(db_path: pathlib.Path, variant_id: int) -> None:
    """Mark stems_status='failed' on a variant."""
    conn = _conn(db_path)
    try:
        conn.execute(
            "UPDATE song_variants SET stems_status='failed' WHERE id=?", (variant_id,)
        )
        conn.commit()
    finally:
        conn.close()


def get_stems(db_path: pathlib.Path, variant_id: int) -> dict | None:
    """Return stems status and URLs for a variant."""
    conn = _conn(db_path)
    try:
        row = conn.execute(
            """SELECT stems_status, stems_vocals_url, stems_drums_url,
                      stems_bass_url, stems_other_url
               FROM song_variants WHERE id=?""",
            (variant_id,),
        ).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()
```

- [ ] **Step 4: Verify syntax**

```bash
cd backend && python -c "import ast; ast.parse(open('db.py').read()); print('db.py OK')"
```

Expected: `db.py OK`

- [ ] **Step 5: Commit**

```bash
git add backend/db.py
git commit -m "feat: premium credits DB rename + stems columns

- RENAME animation_balance→premium_balance, animation_monthly_allowance→premium_monthly_allowance
- ADD 5 stems columns: stems_status, stems_vocals_url, stems_drums_url, stems_bass_url, stems_other_url
- Rename 5 animation credit functions → premium credit functions
- Add save_stems, fail_stems, get_stems helpers"
```

---

## Task 2: Rename Animation Credits in billing.py

**Files:**
- Modify: `backend/billing.py:105-112` (`_PLAN_ANIMATION_CREDITS`)
- Modify: `backend/billing.py:453-461` (increment call in checkout handler)
- Modify: `backend/billing.py:529-531` (upsert call in subscription grant)
- Modify: `backend/billing.py:559-561` (upsert call in invoice paid handler)

### Steps

- [ ] **Step 1: Rename the constant and all four call sites in billing.py**

```python
# Line ~105: rename constant
_PLAN_PREMIUM_CREDITS = {
    "pro":           10,
    "agency":        20,
    "enterprise":    50,
    "music_starter": 3,
    "music_pro":     10,
    "music_agency":  20,
}
```

```python
# Line ~453: in _handle_checkout_completed — animation pack purchase
        elif anim_pack and anim_pack in ANIMATION_PACKS:
            if user:
                credits = ANIMATION_PACKS[anim_pack]["credits"]
                db.increment_premium_credits(db_path, user["id"], credits)
                db.update_user(db_path, user["id"], has_paid=1)
                log.info("Premium top-up: added %d credits (%s) to user %s", credits, anim_pack, user["id"])
            else:
                log.warning("Premium top-up: could not find user (email=%s customer=%s user_id=%s)",
                            customer_email, customer_id, user_id)
```

```python
# Line ~529: in _handle_subscription_activated
    anim_allowance = _PLAN_PREMIUM_CREDITS.get(plan, 0)
    db.upsert_premium_credits(db_path, user["id"], balance=anim_allowance, monthly_allowance=anim_allowance)
    log.info("Granted %d premium credits (%s plan) to user %s", anim_allowance, plan, user["id"])
```

```python
# Line ~559: in _handle_invoice_paid
    anim_allowance = _PLAN_PREMIUM_CREDITS.get(plan, 0)
    db.upsert_premium_credits(db_path, user["id"], balance=anim_allowance, monthly_allowance=anim_allowance)
    log.info("Monthly premium credits reset for user %s: %d credits (%s plan)", user["id"], anim_allowance, plan)
```

- [ ] **Step 2: Verify syntax**

```bash
python -c "import ast; ast.parse(open('billing.py').read()); print('billing.py OK')"
```

Expected: `billing.py OK`

- [ ] **Step 3: Commit**

```bash
git add backend/billing.py
git commit -m "feat: rename animation credits → premium credits in billing.py"
```

---

## Task 3: Rename in webhooks.py + Add _stem_pipeline

**Files:**
- Modify: `backend/webhooks.py:242` (Kling credit deduction call)
- Modify: `backend/webhooks.py` (add WEBHOOK_URL env var + two new pipeline functions)

### Steps

- [ ] **Step 1: Update the Kling credit deduction call in webhooks.py**

Find (around line 242):
```python
            _has_anim_credit = _db.check_and_deduct_animation_credit(pathlib.Path(DB_PATH), _user_id)
            if not _has_anim_credit:
                logger.info(
                    "Kling skipped for variant_id=%d: no animation credits remaining for user %s",
```

Replace with:
```python
            _has_anim_credit = _db.check_and_deduct_premium_credit(pathlib.Path(DB_PATH), _user_id)
            if not _has_anim_credit:
                logger.info(
                    "Kling skipped for variant_id=%d: no premium credits remaining for user %s",
```

- [ ] **Step 2: Add WEBHOOK_URL env var near the top of webhooks.py** (after the existing env var block around line 188-191)

```python
WEBHOOK_URL = os.environ.get("WEBHOOK_URL", "")
```

- [ ] **Step 3: Add _stem_pipeline to webhooks.py** (append after the `_kling_pipeline` function)

```python
def _stem_pipeline(variant_id: int, user_id: str, mp3_url: str) -> None:
    """Background thread: submit song to fal.ai Demucs, poll for result, save stem URLs."""
    import time as _time
    logger.info("Stem pipeline START: variant_id=%d user=%s mp3_url=%s", variant_id, user_id, mp3_url)
    db_path = pathlib.Path(DB_PATH)
    try:
        if not FAL_API_KEY:
            logger.warning("Stem pipeline: FAL_API_KEY not set — skipping variant_id=%d", variant_id)
            _db.fail_stems(db_path, variant_id)
            _db.increment_premium_credits(db_path, user_id, 1)
            return

        fal_headers = {"Authorization": f"Key {FAL_API_KEY}", "Content-Type": "application/json"}
        payload = {
            "audio_url": mp3_url,
            "model": "htdemucs",
            "stems": ["vocals", "drums", "bass", "other"],
            "output_format": "mp3",
        }
        resp = requests.post(
            "https://queue.fal.run/fal-ai/demucs",
            headers=fal_headers,
            json=payload,
            timeout=30,
        )
        logger.info("Demucs submit: variant_id=%d status=%d body=%r", variant_id, resp.status_code, resp.text[:400])
        if resp.status_code == 403:
            raise RuntimeError(f"Demucs: 403 Forbidden — fal.ai balance likely exhausted. Body: {resp.text[:200]}")
        resp.raise_for_status()
        body = resp.json()
        status_url = body.get("status_url")
        response_url = body.get("response_url")
        if not status_url or not response_url:
            raise RuntimeError(f"Demucs: missing status_url/response_url: {body!r}")

        logger.info("Demucs submitted: variant_id=%d polling %s", variant_id, status_url)
        poll_headers = {"Authorization": f"Key {FAL_API_KEY}"}
        for attempt in range(1, 37):  # max 36 × 10s = 6 min
            _time.sleep(10)
            sr = requests.get(status_url, headers=poll_headers, timeout=15)
            poll_status = sr.json().get("status", "")
            logger.info("Demucs poll: variant_id=%d attempt=%d status=%s", variant_id, attempt, poll_status)
            if poll_status == "COMPLETED":
                result = requests.get(response_url, headers=poll_headers, timeout=15).json()
                vocals_url = result.get("vocals", {}).get("url", "")
                drums_url  = result.get("drums", {}).get("url", "")
                bass_url   = result.get("bass", {}).get("url", "")
                other_url  = result.get("other", {}).get("url", "")
                logger.info(
                    "Demucs COMPLETE: variant_id=%d vocals=%s drums=%s bass=%s other=%s",
                    variant_id, vocals_url[:60], drums_url[:60], bass_url[:60], other_url[:60],
                )
                _db.save_stems(db_path, variant_id,
                               vocals_url=vocals_url, drums_url=drums_url,
                               bass_url=bass_url, other_url=other_url)
                return
            if poll_status in ("FAILED", "ERROR"):
                raise RuntimeError(f"Demucs job failed: {sr.json()!r}")

        raise RuntimeError(f"Demucs timeout after 6 min for variant_id={variant_id}")

    except Exception as exc:
        logger.exception("Stem pipeline FAILED: variant_id=%d error=%s", variant_id, exc)
        _db.fail_stems(db_path, variant_id)
        _db.increment_premium_credits(db_path, user_id, 1)  # refund


def _cover_pipeline(variant_id: int, source_mp3_url: str, lyrics_text: str) -> None:
    """Background thread: upload source song to Apiframe, EXTEND with user lyrics."""
    import time as _time
    logger.info("Cover pipeline START: variant_id=%d source=%s lyrics_len=%d", variant_id, source_mp3_url, len(lyrics_text))
    db_path = pathlib.Path(DB_PATH)
    apiframe_headers_json = {"X-API-Key": APIFRAME_API_KEY, "Content-Type": "application/json"}
    webhook_url = f"{WEBHOOK_URL}?variant_id={variant_id}"
    try:
        # Step 1: Download source mp3
        audio_resp = requests.get(source_mp3_url, timeout=30)
        audio_resp.raise_for_status()
        audio_data = audio_resp.content
        logger.info("Cover pipeline: downloaded %d bytes for variant_id=%d", len(audio_data), variant_id)

        # Step 2: Upload to Apiframe
        upload_resp = requests.post(
            f"{APIFRAME_BASE}/v2/music/upload",
            headers={"X-API-Key": APIFRAME_API_KEY},
            files={"audio": ("source.mp3", audio_data, "audio/mpeg")},
            timeout=60,
        )
        logger.info("Cover upload: variant_id=%d status=%d body=%r", variant_id, upload_resp.status_code, upload_resp.text[:300])
        upload_resp.raise_for_status()
        parent_task_id = upload_resp.json().get("task_id")
        if not parent_task_id:
            raise RuntimeError(f"Cover upload: no task_id in response: {upload_resp.json()!r}")

        # Step 3: Extend with user lyrics
        extend_payload = {
            "parent_task_id": parent_task_id,
            "lyrics": lyrics_text,
            "continue_at": 0,
            "webhookUrl": webhook_url,
            "webhookEvents": ["completed", "failed"],
        }
        extend_resp = requests.post(
            f"{APIFRAME_BASE}/v2/music/extend",
            headers=apiframe_headers_json,
            json=extend_payload,
            timeout=30,
        )
        logger.info("Cover extend: variant_id=%d status=%d body=%r", variant_id, extend_resp.status_code, extend_resp.text[:300])
        extend_resp.raise_for_status()
        logger.info("Cover pipeline: EXTEND submitted for variant_id=%d — awaiting webhook", variant_id)

    except Exception as exc:
        logger.exception("Cover pipeline FAILED: variant_id=%d error=%s", variant_id, exc)
        conn = sqlite3.connect(DB_PATH)
        try:
            conn.execute("UPDATE song_variants SET status='failed' WHERE id=?", (variant_id,))
            conn.commit()
        finally:
            conn.close()
```

Note: `APIFRAME_BASE` is already defined in `songs.py` as `"https://api.apiframe.ai"`. Add it near `WEBHOOK_URL` in webhooks.py:

```python
APIFRAME_BASE = "https://api.apiframe.ai"
```

- [ ] **Step 4: Verify syntax**

```bash
python -c "import ast; ast.parse(open('webhooks.py').read()); print('webhooks.py OK')"
```

Expected: `webhooks.py OK`

- [ ] **Step 5: Commit**

```bash
git add backend/webhooks.py
git commit -m "feat: add _stem_pipeline + _cover_pipeline to webhooks.py; rename animation→premium credit call"
```

---

## Task 4: Rename + New Endpoints in main.py

**Files:**
- Modify: `backend/main.py:519-537` (startup block + credits endpoint)
- Modify: `backend/main.py:1981-1994` (GET /api/credits response)
- Add: three new endpoints after existing variant endpoints

### Steps

- [ ] **Step 1: Update the startup block SQL and credits endpoint in main.py**

Find the startup block (~line 519):
```python
                   SET animation_balance = 50, animation_monthly_allowance = 50
```
Replace with:
```python
                   SET premium_balance = 50, premium_monthly_allowance = 50
```

Find (~line 531):
```python
                   FROM users u LEFT JOIN song_credits sc ON sc.user_id = u.id
                   WHERE lower(u.email) = 'dominic.rowle@yahoo.com'"""
            ).fetchone()
            if _acrow:
                log.info(
                    "owner animation credits — email=%r balance=%r allowance=%r",
```
Replace the log message:
```python
                log.info(
                    "owner premium credits — email=%r balance=%r allowance=%r",
```

- [ ] **Step 2: Update GET /api/credits response (~line 1981)**

```python
    anim_row = db.get_premium_credits(db_path, current_user["id"])
    anim_allowance = billing._PLAN_PREMIUM_CREDITS.get(plan, 0)
    return {
        "balance": row["balance"],
        "monthly_allowance": allowance,
        "is_admin": bool(current_user.get("is_admin", 0)),
        "plan": plan,
        "has_paid": bool(current_user.get("has_paid", 0)),
        "youtube_connected": bool(current_user.get("youtube_refresh_token")),
        "video_credits": video_row["balance"] if video_row else 0,
        "video_monthly_allowance": video_allowance,
        "artist_name": current_user.get("artist_name") or "",
        "premium_credits": anim_row["premium_balance"] if anim_row else 0,
        "premium_monthly_allowance": anim_allowance,
    }
```

- [ ] **Step 3: Add the three new Pydantic models and endpoints**

Add immediately before the `@app.post("/api/playlists/ai-generate")` endpoint (or at the end of the variant section):

```python
class _CoverSongRequest(BaseModel):
    lyrics: str = Field(min_length=1, max_length=3000)


@app.post("/api/songs/variants/{variant_id}/stems", status_code=202)
async def request_stems(variant_id: int, current_user=Depends(auth.get_current_user)):
    """Submit a stem separation job for a variant the user owns. Costs 1 premium credit."""
    db_path = db.get_db_path()
    variant = db.get_song_variant_by_id(db_path, variant_id)
    if not variant or variant["user_id"] != current_user["id"]:
        raise HTTPException(status_code=404, detail="Variant not found")
    if not variant.get("mp3_url"):
        raise HTTPException(status_code=400, detail="Song not ready yet")
    status = variant.get("stems_status")
    if status in ("pending", "complete"):
        row = db.get_stems(db_path, variant_id)
        return {"status": status, "variant_id": variant_id, **(row or {})}
    user_id = current_user["id"]
    if not db.check_and_deduct_premium_credit(db_path, user_id):
        raise HTTPException(status_code=402, detail="You need at least 1 Premium Credit to separate stems. Buy credits from your dashboard.")
    conn = sqlite3.connect(str(db_path))
    try:
        conn.execute("UPDATE song_variants SET stems_status='pending' WHERE id=?", (variant_id,))
        conn.commit()
    finally:
        conn.close()
    import threading as _threading
    import webhooks as _wh
    _threading.Thread(
        target=_wh._stem_pipeline,
        args=(variant_id, user_id, variant["mp3_url"]),
        daemon=True,
    ).start()
    log.info("Stems requested: variant_id=%d user=%s", variant_id, user_id)
    return {"status": "pending", "variant_id": variant_id}


@app.get("/api/songs/variants/{variant_id}/stems")
async def get_stems(variant_id: int, current_user=Depends(auth.get_current_user)):
    """Poll stems status for a variant."""
    db_path = db.get_db_path()
    variant = db.get_song_variant_by_id(db_path, variant_id)
    if not variant or variant["user_id"] != current_user["id"]:
        raise HTTPException(status_code=404, detail="Variant not found")
    row = db.get_stems(db_path, variant_id)
    if not row:
        raise HTTPException(status_code=404, detail="No stems data")
    return row


@app.post("/api/songs/variants/{variant_id}/cover", status_code=202)
async def cover_song(
    variant_id: int,
    body: _CoverSongRequest,
    current_user=Depends(auth.get_current_user),
):
    """Create a new song variant using the source song's style with the user's custom lyrics."""
    db_path = db.get_db_path()
    source = db.get_song_variant_by_id(db_path, variant_id)
    if not source or source["user_id"] != current_user["id"]:
        raise HTTPException(status_code=404, detail="Variant not found")
    if not source.get("mp3_url"):
        raise HTTPException(status_code=400, detail="Source song not ready")
    user_id = current_user["id"]
    lyrics_text = body.lyrics.strip()
    conn = sqlite3.connect(str(db_path))
    try:
        cur = conn.cursor()
        # Check and deduct song credit
        from songs import _check_and_deduct_credit, InsufficientCreditsError
        try:
            _check_and_deduct_credit(cur, user_id)
        except InsufficientCreditsError:
            conn.close()
            raise HTTPException(status_code=402, detail="Insufficient song credits")
        cur.execute(
            "INSERT INTO lyrics (user_id, lyrics_text) VALUES (?, ?)",
            (user_id, lyrics_text),
        )
        lyric_id = cur.lastrowid
        cur.execute(
            """INSERT INTO song_variants (lyric_id, user_id, style_prompt, genre_tag, status)
               VALUES (?, ?, ?, ?, 'pending')""",
            (lyric_id, user_id, source.get("style_prompt", ""), source.get("genre_tag", "")),
        )
        new_variant_id = cur.lastrowid
        conn.commit()
    finally:
        conn.close()
    import threading as _threading
    import webhooks as _wh
    _threading.Thread(
        target=_wh._cover_pipeline,
        args=(new_variant_id, source["mp3_url"], lyrics_text),
        daemon=True,
    ).start()
    log.info("Cover song submitted: source_variant=%d new_variant=%d user=%s", variant_id, new_variant_id, user_id)
    return {"variant_id": new_variant_id, "status": "pending"}
```

- [ ] **Step 4: Verify syntax**

```bash
python -c "import ast; ast.parse(open('main.py').read()); print('main.py OK')"
```

Expected: `main.py OK`

- [ ] **Step 5: Commit**

```bash
git add backend/main.py
git commit -m "feat: stems + cover endpoints in main.py; rename animation→premium credits in API response"
```

---

## Task 5: Frontend — web/ credit rename only

**Files:**
- Modify: `web/src/pages/SongsPage.jsx` (state initialiser + 5 UI occurrences)

### Steps

- [ ] **Step 1: Rename state key and all UI references in web/SongsPage.jsx**

Find the `useState` credits initialiser (around line 823):
```js
animation_credits: 0, animation_monthly_allowance: 0
```
Replace with:
```js
premium_credits: 0, premium_monthly_allowance: 0
```

Replace ALL occurrences of `credits.animation_credits` → `credits.premium_credits` (use replace-all — there are 4 occurrences).

Replace UI text occurrences:
- `"animation credits remaining"` → `"premium credits remaining"`
- `"Buy Animation Credits"` → `"Buy Premium Credits"`
- `"Buy more"` button tooltip (inside animation_credits === 0 check) — no text change needed, already generic.

Also update the helper text where it says "🎬 Buy Animation Credits":
```jsx
<h3>🌟 Buy Premium Credits</h3>
```
and update the subtext if any to mention both uses:
- If there's a description text, add: `"Used for animated covers & stem separation"`

- [ ] **Step 2: Verify no remaining animation_credits references**

```bash
grep -n "animation_credits\|animation_monthly" web/src/pages/SongsPage.jsx
```

Expected: no output (zero matches).

- [ ] **Step 3: Commit**

```bash
git add web/src/pages/SongsPage.jsx
git commit -m "feat: rename animation_credits → premium_credits in web/ SongsPage"
```

---

## Task 6: Frontend — web-beats/ credit rename + stems UI + Cover modal

**Files:**
- Modify: `web-beats/src/pages/SongsPage.jsx` — many sections

### Steps

- [ ] **Step 1: Rename state key and UI text in web-beats/SongsPage.jsx**

Find the `useState` credits initialiser (~line 875):
```js
animation_credits: 0, animation_monthly_allowance: 0
```
Replace with:
```js
premium_credits: 0, premium_monthly_allowance: 0
```

Replace ALL `credits.animation_credits` → `credits.premium_credits` (4 occurrences, use replace-all).

Update UI text:
- `"animation credits remaining"` → `"premium credits remaining"`
- `"🎬 Buy Animation Credits"` → `"🌟 Buy Premium Credits"`
- Where credits count is shown, add a subscript line after: `"Covers animated art & stems"`
- Pack label strings (`"5 animations"`, `"15 animations"`) → `"5 premium credits"`, `"15 premium credits"`

Verify:
```bash
grep -n "animation_credits\|animation_monthly" web-beats/src/pages/SongsPage.jsx
```
Expected: zero matches.

- [ ] **Step 2: Add stems state to the page-level component**

In the main `export default function SongsPage()` (or equivalent) component, add these state declarations alongside the existing `ytStatus`, `didStatus` maps:

```js
const [stemsData, setStemsData]     = useState({}); // {[variant_id]: {stems_status, stems_vocals_url, ...}}
const [stemsPoll, setStemsPoll]     = useState({}); // {[variant_id]: intervalId}
const [coverModal, setCoverModal]   = useState(null); // null | {variantId, sourceTitle}
const [coverLyrics, setCoverLyrics] = useState('');
const [coverLoading, setCoverLoading] = useState(false);
const [coverError, setCoverError]   = useState('');
const [coverToast, setCoverToast]   = useState(false);
```

- [ ] **Step 3: Add stems handler functions to the page component**

Add these handlers (near `handleYouTubeClick`, `handleAvatarClick`, etc.):

```js
const handleGetStems = async (variantId) => {
  try {
    const r = await fetch(`${BACKEND_URL}/api/songs/variants/${variantId}/stems`, {
      method: 'POST',
      headers: { Authorization: `Bearer ${token}` },
    });
    const data = await r.json();
    if (!r.ok) { alert(data.detail || 'Could not start stem separation'); return; }
    setStemsData(prev => ({ ...prev, [variantId]: data }));
    if (data.stems_status === 'pending') {
      const intervalId = setInterval(async () => {
        const pr = await fetch(`${BACKEND_URL}/api/songs/variants/${variantId}/stems`, {
          headers: { Authorization: `Bearer ${token}` },
        });
        if (!pr.ok) return;
        const pd = await pr.json();
        setStemsData(prev => ({ ...prev, [variantId]: pd }));
        if (pd.stems_status !== 'pending') {
          setStemsPoll(prev => { clearInterval(prev[variantId]); const n = {...prev}; delete n[variantId]; return n; });
        }
      }, 5000);
      setStemsPoll(prev => ({ ...prev, [variantId]: intervalId }));
    }
  } catch {
    alert('Network error starting stem separation');
  }
};

const handleCoverSubmit = async () => {
  if (!coverModal || !coverLyrics.trim()) return;
  setCoverLoading(true);
  setCoverError('');
  try {
    const r = await fetch(`${BACKEND_URL}/api/songs/variants/${coverModal.variantId}/cover`, {
      method: 'POST',
      headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
      body: JSON.stringify({ lyrics: coverLyrics.trim() }),
    });
    const data = await r.json();
    if (!r.ok) { setCoverError(data.detail || 'Something went wrong'); return; }
    setCoverModal(null);
    setCoverLyrics('');
    setCoverToast(true);
    setTimeout(() => setCoverToast(false), 4000);
  } catch {
    setCoverError('Network error. Try again.');
  } finally {
    setCoverLoading(false);
  }
};
```

- [ ] **Step 4: Pass stems props to SongCard and add stems props to SongCard definition**

In the SongCard definition (around line 280), add to the destructured props:
```js
premiumCredits, stemsData: stemsProp, onGetStems, onOpenCover,
```

In every `<SongCard ... />` instantiation (lines ~2445 and ~2533), add:
```jsx
premiumCredits={credits.premium_credits}
stemsData={stemsData[v.variant_id]}
onGetStems={handleGetStems}
onOpenCover={(variantId, title) => { setCoverModal({ variantId, sourceTitle: title }); setCoverLyrics(''); setCoverError(''); }}
```

- [ ] **Step 5: Add stems panel inside SongCard**

Inside SongCard, add state:
```js
const [stemsOpen, setStemsOpen] = useState(false);
```

After Row 4 (Remake + Regen buttons), add a Row 5 for stems (before the playlist / delete row):

```jsx
{/* Row 5: Stems */}
{variant.mp3_url && (() => {
  const st = stemsProp?.stems_status;
  if (st === 'complete') {
    return (
      <div style={{ marginTop: 8 }}>
        <button
          onClick={() => setStemsOpen(o => !o)}
          style={{ ...actionBtnStyle, width: '100%', color: '#a78bfa', borderColor: 'rgba(167,139,250,0.5)' }}
        >
          🎵 Stems {stemsOpen ? '▲' : '▼'}
        </button>
        {stemsOpen && (
          <div style={{ marginTop: 8, background: 'rgba(167,139,250,0.05)', borderRadius: 8, border: '1px solid rgba(167,139,250,0.15)', overflow: 'hidden' }}>
            {[
              { label: '🎤 Vocals',       url: stemsProp.stems_vocals_url },
              { label: '🥁 Drums',        url: stemsProp.stems_drums_url },
              { label: '🎸 Bass',         url: stemsProp.stems_bass_url },
              { label: '🎹 Melody/Other', url: stemsProp.stems_other_url },
            ].map(({ label, url }) => (
              <div key={label} style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '8px 12px', borderBottom: '1px solid rgba(255,255,255,0.04)' }}>
                <span style={{ fontSize: 12, color: '#c4b5fd', width: 100, flexShrink: 0 }}>{label}</span>
                {url ? (
                  <>
                    <audio controls src={url} style={{ flex: 1, height: 28, minWidth: 0 }} />
                    <a href={url} download style={{ color: '#a78bfa', fontSize: 18, textDecoration: 'none', flexShrink: 0 }} title="Download">⬇</a>
                  </>
                ) : (
                  <span style={{ color: '#555', fontSize: 12 }}>unavailable</span>
                )}
              </div>
            ))}
            <div style={{ padding: '10px 12px' }}>
              <button
                onClick={() => onOpenCover(variant.variant_id, title)}
                style={{ width: '100%', padding: '9px 0', borderRadius: 7, border: '1px solid rgba(0,240,255,0.4)', background: 'rgba(0,240,255,0.06)', color: '#00f0ff', fontSize: 12, fontWeight: 700, cursor: 'pointer' }}
              >
                🎤 Cover This Song
              </button>
            </div>
          </div>
        )}
      </div>
    );
  }
  if (st === 'pending') {
    return (
      <div style={{ marginTop: 8, padding: '8px 12px', borderRadius: 7, background: 'rgba(167,139,250,0.06)', border: '1px solid rgba(167,139,250,0.2)', color: '#a78bfa', fontSize: 12, textAlign: 'center' }}>
        ⏳ Separating stems… (check back in a minute)
      </div>
    );
  }
  if (st === 'failed') {
    return (
      <div style={{ marginTop: 8, padding: '8px 12px', borderRadius: 7, background: 'rgba(248,113,113,0.06)', border: '1px solid rgba(248,113,113,0.2)', color: '#f87171', fontSize: 12, textAlign: 'center' }}>
        Stems failed — 1 premium credit refunded
      </div>
    );
  }
  // No stems yet
  return (
    <div style={{ marginTop: 8 }}>
      <button
        onClick={() => premiumCredits > 0 ? onGetStems(variant.variant_id) : null}
        disabled={premiumCredits === 0}
        title={premiumCredits === 0 ? 'Needs 1 Premium Credit' : 'Separate into vocals, drums, bass, melody (costs 1 premium credit)'}
        style={{
          ...actionBtnStyle, width: '100%',
          color: premiumCredits > 0 ? '#a78bfa' : '#555',
          borderColor: premiumCredits > 0 ? 'rgba(167,139,250,0.4)' : 'rgba(255,255,255,0.08)',
          opacity: premiumCredits === 0 ? 0.5 : 1,
          cursor: premiumCredits === 0 ? 'not-allowed' : 'pointer',
        }}
      >
        🎵 Get Stems {premiumCredits === 0 ? '(0 credits)' : `(1 credit)`}
      </button>
    </div>
  );
})()}
```

- [ ] **Step 6: Add the Cover This Song modal and success toast to the page JSX**

At the bottom of the page's return, before the closing outer `</>` or `</div>`, add:

```jsx
{/* Cover This Song modal */}
{coverModal && (
  <div
    onClick={() => setCoverModal(null)}
    style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.8)', zIndex: 1000, display: 'flex', alignItems: 'center', justifyContent: 'center', padding: 20 }}
  >
    <div
      onClick={e => e.stopPropagation()}
      style={{ background: '#12121e', border: '1px solid rgba(0,240,255,0.25)', borderRadius: 16, padding: '28px 24px', maxWidth: 480, width: '100%' }}
    >
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 14 }}>
        <h2 style={{ margin: 0, fontSize: 18, fontWeight: 800, background: 'linear-gradient(90deg,#00f0ff,#a855f7)', WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent' }}>
          🎤 Cover This Song
        </h2>
        <button onClick={() => setCoverModal(null)} style={{ background: 'none', border: '1px solid rgba(255,255,255,0.12)', borderRadius: 6, color: '#94a3b8', fontSize: 13, cursor: 'pointer', padding: '4px 9px' }}>✕</button>
      </div>

      <div style={{ background: 'rgba(0,240,255,0.05)', border: '1px solid rgba(0,240,255,0.15)', borderRadius: 8, padding: '10px 14px', marginBottom: 16, fontSize: 13, color: '#94a3b8', lineHeight: 1.5 }}>
        Zeus will create a <strong style={{ color: '#e2e8f0' }}>new song</strong> in the same style as this one but with your lyrics. It won't be an exact overlay on the original beat — think of it like a <strong style={{ color: '#e2e8f0' }}>cover version</strong> inspired by this track.
      </div>

      <textarea
        value={coverLyrics}
        onChange={e => setCoverLyrics(e.target.value)}
        placeholder={"[Verse 1]\nWrite your lyrics here...\n\n[Chorus]\nYour chorus here..."}
        rows={8}
        maxLength={3000}
        style={{ width: '100%', background: 'rgba(255,255,255,0.04)', border: '1px solid rgba(255,255,255,0.12)', borderRadius: 8, color: '#e2e8f0', fontSize: 13, padding: '10px 12px', outline: 'none', resize: 'vertical', fontFamily: 'inherit', boxSizing: 'border-box', marginBottom: 8 }}
      />
      <div style={{ fontSize: 11, color: '#475569', textAlign: 'right', marginBottom: 12 }}>{coverLyrics.length}/3000 · costs 1 song credit</div>

      {coverError && <p style={{ color: '#f87171', fontSize: 13, margin: '0 0 10px' }}>{coverError}</p>}

      <button
        onClick={handleCoverSubmit}
        disabled={coverLoading || !coverLyrics.trim()}
        style={{ width: '100%', padding: '11px 0', background: 'linear-gradient(135deg,#7c3aed,#a855f7)', border: 'none', borderRadius: 8, color: '#fff', fontWeight: 700, fontSize: 14, cursor: coverLoading || !coverLyrics.trim() ? 'not-allowed' : 'pointer', opacity: coverLoading || !coverLyrics.trim() ? 0.55 : 1, transition: 'opacity 0.2s' }}
      >
        {coverLoading ? '🎵 Submitting…' : '🎤 Generate Cover'}
      </button>
    </div>
  </div>
)}

{/* Cover success toast */}
{coverToast && (
  <div style={{ position: 'fixed', bottom: 24, left: '50%', transform: 'translateX(-50%)', background: 'rgba(0,240,255,0.12)', border: '1px solid rgba(0,240,255,0.4)', borderRadius: 10, padding: '12px 24px', color: '#00f0ff', fontWeight: 600, fontSize: 14, zIndex: 2000, whiteSpace: 'nowrap' }}>
    🎤 Your cover is generating! Check your library soon.
  </div>
)}
```

- [ ] **Step 7: Verify syntax compiles**

```bash
cd /c/Users/Student/zeus-app/web-beats && npm run build 2>&1 | tail -20
```

Expected: build succeeds with no errors (warnings OK).

- [ ] **Step 8: Commit and push**

```bash
cd /c/Users/Student/zeus-app
git add web-beats/src/pages/SongsPage.jsx web/src/pages/SongsPage.jsx
git commit -m "feat: stems UI + Cover This Song modal in web-beats; premium credits rename in both frontends

- Rename animation_credits → premium_credits in both SongsPage.jsx files
- Add Get Stems button on song cards (web-beats only)
- Stems panel with 4 audio players + download links per stem
- Cover This Song modal with explanation text, lyrics textarea, generates new variant
- Success toast on cover submission"
git push origin master
```

---

## Self-Review

**Spec coverage:**
- ✅ Premium Credits DB rename (Task 1)
- ✅ billing.py + webhooks.py rename (Tasks 2, 3)
- ✅ main.py rename + 3 new endpoints (Task 4)
- ✅ web/ rename (Task 5)
- ✅ web-beats/ rename + stems UI + Cover modal (Task 6)
- ✅ 1 premium credit deducted + refunded on failure
- ✅ Polling every 5s while pending
- ✅ Cover This Song modal with explanation text (spec requirement)
- ✅ `_cover_pipeline` uses UPLOAD + EXTEND
- ✅ Existing webhook handler processes EXTEND response (no webhook changes needed)

**Placeholder scan:** No TBDs found. All SQL, function calls, component props, and API payloads are fully specified.

**Type consistency:**
- `check_and_deduct_premium_credit` — defined Task 1, called Task 3 + Task 4 ✅
- `save_stems(db_path, variant_id, *, vocals_url, drums_url, bass_url, other_url)` — defined Task 1, called Task 3 ✅
- `get_stems(db_path, variant_id)` — defined Task 1, called Task 4 ✅
- `_stem_pipeline(variant_id, user_id, mp3_url)` — defined Task 3, called Task 4 ✅
- `_cover_pipeline(variant_id, source_mp3_url, lyrics_text)` — defined Task 3, called Task 4 ✅
- `stemsProp` in SongCard (from `stemsData={stemsData[v.variant_id]}`) — all fields match DB column names ✅
