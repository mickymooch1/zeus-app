# Zeus Song Generator — Apiframe v2 Migration

The original spec wired up Apiframe v1, but our API key (`afk_...`) is for v2. This document is a complete rewrite of `songs.py` and `webhooks.py` to use the v2 API.

**Do not run any live test after applying these changes. Apply, show me the diff, and stop. I'll review then approve the test.**

Reference docs:
- Music generation: `https://apiframe.ai/docs/music/suno`
- Common request shape: `https://apiframe.ai/docs/music`
- Webhooks: `https://apiframe.ai/docs/webhooks`

---

## v1 vs v2 — what's different

| Thing | v1 (wrong, current) | v2 (correct) |
|-------|---------------------|--------------|
| Base URL | `https://api.apiframe.pro` | `https://api.apiframe.ai` |
| Endpoint path | `/suno-imagine` | `/v2/music/generate` |
| Auth header | `Authorization: <key>` | `X-API-Key: <key>` |
| Lyrics field | `lyrics` (top-level) | `prompt` (with `sunoParams.custom_mode: true`) |
| Style field | `tags` (top-level) | `sunoParams.style` |
| Model field | `model: "V5"` (top-level) | `model: "suno"` (top-level) + `sunoParams.model_version: "V5"` |
| Webhook URL field | `webhook_url` | `webhookUrl` |
| Webhook secret | per-variant token in body | global HMAC, signing secret = `SHA256(api_key)` |
| Response key | `task_id` | `jobId` |
| Songs per call | 2 takes returned | 1 result returned |
| Webhook status | `"finished"` | `"COMPLETED"` (uppercase) |
| Webhook payload structure | `{songs: [{audio_url}, {audio_url}]}` | `{result: "<single mp3 url>"}` |
| Credits per generation | 8 | 11 |

---

## File 1 — replace `backend/songs.py` entirely

```python
"""Song variant generation via Apiframe v2 (https://api.apiframe.ai/v2/music/generate)."""
import os
import sqlite3
import logging
import requests

logger = logging.getLogger("zeus.songs")

APIFRAME_API_KEY = os.environ["APIFRAME_API_KEY"]
APIFRAME_BASE = "https://api.apiframe.ai"
WEBHOOK_URL = os.environ["SONG_WEBHOOK_URL"]


class InsufficientCreditsError(Exception):
    """Raised when a user does not have enough song credits."""


def _check_and_deduct_credit(cur, user_id) -> None:
    cur.execute("SELECT balance FROM song_credits WHERE user_id = ?", (user_id,))
    row = cur.fetchone()
    if not row or row[0] < 1:
        raise InsufficientCreditsError("No song credits available. Top up to continue.")
    cur.execute(
        "UPDATE song_credits SET balance = balance - 1 WHERE user_id = ?",
        (user_id,),
    )


def _refund_credit(cur, user_id) -> None:
    cur.execute(
        "UPDATE song_credits SET balance = balance + 1 WHERE user_id = ?",
        (user_id,),
    )


def generate_song_variant(
    user_id,
    lyric_id: int,
    style_prompt: str,
    genre_tag: str,
    db_path: str,
) -> dict:
    """
    Submit a song generation job to Apiframe v2.
    Costs 1 song credit (1 credit = 11 Apiframe credits = 1 finished track).
    Returns immediately with variant_id; the actual MP3 arrives later via webhook.
    """
    conn = sqlite3.connect(db_path)
    try:
        cur = conn.cursor()
        _check_and_deduct_credit(cur, user_id)

        cur.execute(
            "SELECT lyrics_text FROM lyrics WHERE id = ? AND user_id = ?",
            (lyric_id, user_id),
        )
        lyric_row = cur.fetchone()
        if not lyric_row:
            _refund_credit(cur, user_id)
            conn.commit()
            raise ValueError(f"Lyric {lyric_id} not found for user {user_id}")
        lyrics = lyric_row[0]

        cur.execute(
            """INSERT INTO song_variants
               (lyric_id, user_id, style_prompt, genre_tag, status, take_number)
               VALUES (?, ?, ?, ?, 'pending', 1)""",
            (lyric_id, user_id, style_prompt, genre_tag),
        )
        variant_id = cur.lastrowid
        conn.commit()
    except InsufficientCreditsError:
        conn.close()
        raise

    # Diagnostic logging — remove once the integration is stable
    logger.info(
        "APIFRAME_V2_SUBMIT first6=%r last4=%r len=%d variant_id=%d",
        APIFRAME_API_KEY[:6],
        APIFRAME_API_KEY[-4:],
        len(APIFRAME_API_KEY),
        variant_id,
    )

    try:
        response = requests.post(
            f"{APIFRAME_BASE}/v2/music/generate",
            headers={
                "X-API-Key": APIFRAME_API_KEY,           # v2 uses X-API-Key, NOT Authorization
                "Content-Type": "application/json",
            },
            json={
                "prompt": lyrics,                        # the lyrics go in `prompt` when custom_mode=true
                "model": "suno",                         # always "suno" at the top level for Suno
                "webhookUrl": f"{WEBHOOK_URL}?variant_id={variant_id}",
                "webhookEvents": ["completed", "failed"],
                "sunoParams": {
                    "custom_mode": True,                 # because we're providing real lyrics
                    "instrumental": False,
                    "model_version": "V5",
                    "style": style_prompt[:1000],        # v2 caps style at 1,000 chars
                },
            },
            timeout=30,
        )
        response.raise_for_status()
        body = response.json()
        job_id = body.get("jobId")
        if not job_id:
            raise RuntimeError(f"Apiframe response missing jobId: {body!r}")

        conn = sqlite3.connect(db_path)
        try:
            cur = conn.cursor()
            cur.execute(
                """UPDATE song_variants
                   SET provider_job_id = ?, status = 'generating'
                   WHERE id = ?""",
                (job_id, variant_id),
            )
            conn.commit()
        finally:
            conn.close()

    except Exception as exc:
        # Submission failed before Apiframe accepted the job — refund credit, mark variant failed
        conn = sqlite3.connect(db_path)
        try:
            cur = conn.cursor()
            _refund_credit(cur, user_id)
            cur.execute(
                "UPDATE song_variants SET status = 'failed' WHERE id = ?",
                (variant_id,),
            )
            conn.commit()
        finally:
            conn.close()
        raise RuntimeError(f"Music API submission failed: {exc}") from exc

    return {"variant_id": variant_id, "job_id": job_id, "status": "generating"}


def generate_multiple_variants(
    user_id,
    lyric_id: int,
    genres: list[str],
    db_path: str,
) -> dict:
    """Generate the same lyrics in multiple genres. Costs len(genres) credits."""
    from song_genres import GENRE_PRESETS

    valid_genres = [g for g in genres if g in GENRE_PRESETS]
    if not valid_genres:
        raise ValueError("No valid genres provided")
    if len(valid_genres) > 7:
        raise ValueError("Maximum 7 variants per request")

    conn = sqlite3.connect(db_path)
    try:
        cur = conn.cursor()
        cur.execute("SELECT balance FROM song_credits WHERE user_id = ?", (user_id,))
        row = cur.fetchone()
        available = row[0] if row else 0
    finally:
        conn.close()

    if available < len(valid_genres):
        raise InsufficientCreditsError(
            f"Need {len(valid_genres)} credits, have {available}"
        )

    variants = []
    for genre in valid_genres:
        result = generate_song_variant(
            user_id=user_id,
            lyric_id=lyric_id,
            style_prompt=GENRE_PRESETS[genre],
            genre_tag=genre,
            db_path=db_path,
        )
        variants.append({"genre": genre, **result})

    return {"variants": variants, "count": len(variants)}
```

---

## File 2 — replace `backend/webhooks.py` entirely

```python
"""Apiframe v2 webhook handler.

Verifies HMAC-SHA256 signature using a signing secret derived from the API key
(SHA256(api_key)), per https://apiframe.ai/docs/webhooks.
"""
import os
import hmac
import hashlib
import sqlite3
import logging
import requests
from fastapi import APIRouter, Request, HTTPException

logger = logging.getLogger("zeus.webhooks")

router = APIRouter()

APIFRAME_API_KEY = os.environ["APIFRAME_API_KEY"]
SIGNING_SECRET = hashlib.sha256(APIFRAME_API_KEY.encode()).hexdigest()
STORAGE_PATH = os.environ["SONG_STORAGE_PATH"]
PUBLIC_BASE_URL = os.environ["SONG_PUBLIC_BASE_URL"]
DB_PATH = os.environ.get("DB_PATH", "/data/zeus.db")


def _verify_signature(raw_body: bytes, signature_header: str) -> bool:
    if not signature_header:
        return False
    expected = "sha256=" + hmac.new(
        SIGNING_SECRET.encode(), raw_body, hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(signature_header, expected)


@router.post("/webhooks/apiframe")
async def apiframe_webhook(request: Request):
    raw_body = await request.body()
    signature = request.headers.get("X-Webhook-Signature", "")

    if not _verify_signature(raw_body, signature):
        logger.warning("Apiframe webhook signature verification failed")
        raise HTTPException(401, "Invalid signature")

    body = await request.json()
    variant_id = request.query_params.get("variant_id")
    if not variant_id:
        raise HTTPException(400, "Missing variant_id")
    try:
        variant_id = int(variant_id)
    except ValueError:
        raise HTTPException(400, "variant_id must be an integer")

    event = body.get("event")
    job_status = body.get("status")
    logger.info("Apiframe webhook variant_id=%d event=%s status=%s", variant_id, event, job_status)

    # Failed: mark variant failed, do NOT refund (Apiframe credits are non-refundable
    # once the job is accepted — the credit was already deducted from the user's balance,
    # so we leave that as-is and just record the failure)
    if event == "failed" or job_status == "FAILED":
        conn = sqlite3.connect(DB_PATH)
        try:
            cur = conn.cursor()
            cur.execute(
                "UPDATE song_variants SET status = 'failed' WHERE id = ?",
                (variant_id,),
            )
            conn.commit()
        finally:
            conn.close()
        return {"ok": True, "status": "failed"}

    # Progress: ignore for now (we only subscribed to completed + failed)
    if event == "progress" or job_status == "PROCESSING":
        return {"ok": True, "status": "progress_ignored"}

    if event != "completed" and job_status != "COMPLETED":
        logger.warning("Unexpected webhook event=%r status=%r body=%r", event, job_status, body)
        return {"ok": True, "status": "unexpected"}

    # Completed — download the result MP3 and record the permanent URL
    result_url = body.get("result")
    if not result_url:
        logger.error("Completed webhook missing result URL: %r", body)
        conn = sqlite3.connect(DB_PATH)
        try:
            cur = conn.cursor()
            cur.execute(
                "UPDATE song_variants SET status = 'failed' WHERE id = ?",
                (variant_id,),
            )
            conn.commit()
        finally:
            conn.close()
        return {"ok": True, "status": "no_result_url"}

    os.makedirs(STORAGE_PATH, exist_ok=True)
    local_path = os.path.join(STORAGE_PATH, f"{variant_id}.mp3")
    download = requests.get(result_url, timeout=120)
    download.raise_for_status()
    with open(local_path, "wb") as fh:
        fh.write(download.content)

    permanent_url = f"{PUBLIC_BASE_URL}/{variant_id}.mp3"

    conn = sqlite3.connect(DB_PATH)
    try:
        cur = conn.cursor()
        cur.execute(
            """UPDATE song_variants
               SET status = 'complete',
                   mp3_url = ?,
                   completed_at = CURRENT_TIMESTAMP
               WHERE id = ?""",
            (permanent_url, variant_id),
        )
        conn.commit()
    finally:
        conn.close()

    logger.info("Apiframe webhook complete: variant_id=%d url=%s", variant_id, permanent_url)
    return {"ok": True, "status": "complete", "url": permanent_url}
```

---

## File 3 — `backend/db.py` minor touch

The `webhook_secret` column we added in the v1 corrections is no longer needed (v2 uses a global signing secret). **Leave the column in place** to avoid migration churn — it'll just be NULL for new variants. No code changes required here.

The `take_number` column also stays in place. v2 always returns one track per generation, so all new rows will have `take_number=1` (which is the default we set). No change needed.

---

## File 4 — `backend/main.py` no change

The router include and static file mount from earlier sections remain correct.

---

## File 5 — admin test endpoint stays the same

`/admin/test-song-pipeline` calls `lyrics.generate_lyrics(...)` then `songs.generate_song_variant(...)`. The function signatures are unchanged, so the endpoint code itself doesn't need to change.

---

## What to do now

1. Replace `songs.py` and `webhooks.py` with the versions above.
2. Show me the diff (focus on songs.py and webhooks.py — db.py and main.py shouldn't change).
3. Commit and push. Wait for Railway to redeploy.
4. **Stop and tell me when the deploy is green.** I'll review the diff and approve the test.

When we test, I'll ask you to:

1. Re-run the test command (`POST /admin/test-song-pipeline` via PowerShell)
2. Check Railway logs for the `APIFRAME_V2_SUBMIT` line plus any webhook activity
3. After ~60 seconds, query `song_variants` for the new lyric_id and check that `status='complete'` and `mp3_url` is populated
4. Open the public URL of the MP3 in a browser to confirm playback

If the webhook signature verification fails on first try, that's our sign that either the API key in Railway differs from the one used to compute the signing secret in the running app (unlikely, both come from the same env var), or our HMAC computation needs adjustment.

## Cost note

v2 charges **11 credits per generation** (vs 8 in v1) and returns **1 track per call** (vs 2 in v1). At Michael's Basic plan rate (4,000 credits / £19) that's:

- ~£0.052 per song to Michael
- 363 songs/month within the included allowance
- Tier inclusions in the original spec (3 / 15 / 50) still work fine
- Top-up margins shift slightly but stay >85%

No need to change the user-facing pricing.
