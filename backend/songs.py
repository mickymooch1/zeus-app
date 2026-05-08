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
