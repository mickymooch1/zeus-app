import os
import pathlib
import secrets
import requests

APIFRAME_API_KEY = os.environ.get("APIFRAME_API_KEY", "")
APIFRAME_BASE = "https://api.apiframe.pro"
WEBHOOK_URL = os.environ.get("SONG_WEBHOOK_URL", "")

import db


class InsufficientCreditsError(Exception):
    pass


def _check_and_deduct_credit(cur, user_id: str) -> None:
    cur.execute("SELECT balance FROM song_credits WHERE user_id = ?", (user_id,))
    row = cur.fetchone()
    if not row or row[0] < 1:
        raise InsufficientCreditsError("No song credits available. Top up to continue.")
    cur.execute(
        "UPDATE song_credits SET balance = balance - 1 WHERE user_id = ?",
        (user_id,),
    )


def _refund_credit(cur, user_id: str) -> None:
    cur.execute(
        "UPDATE song_credits SET balance = balance + 1 WHERE user_id = ?",
        (user_id,),
    )


def generate_song_variant(
    user_id: str,
    lyric_id: int,
    style_prompt: str,
    genre_tag: str,
    db_path: pathlib.Path,
) -> dict:
    """Submit a song generation job. Costs 1 credit. Returns variant_id."""
    if not APIFRAME_API_KEY:
        raise RuntimeError("APIFRAME_API_KEY is not set")

    conn = db._conn(db_path)
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
               (lyric_id, user_id, style_prompt, genre_tag, status)
               VALUES (?, ?, ?, ?, 'pending')""",
            (lyric_id, user_id, style_prompt, genre_tag),
        )
        variant_id = cur.lastrowid
        conn.commit()
    except InsufficientCreditsError:
        conn.close()
        raise

    try:
        # Generate a per-variant secret and persist it before calling the API,
        # so the webhook handler can authenticate inbound callbacks.
        webhook_secret = secrets.token_urlsafe(32)
        cur = conn.cursor()
        cur.execute(
            "UPDATE song_variants SET webhook_secret = ? WHERE id = ?",
            (webhook_secret, variant_id),
        )
        conn.commit()

        response = requests.post(
            f"{APIFRAME_BASE}/suno-imagine",
            headers={
                "Content-Type": "application/json",
                "Authorization": APIFRAME_API_KEY,  # raw key, NOT "Bearer <key>"
            },
            json={
                "lyrics": lyrics,
                "tags": style_prompt,         # Apiframe uses "tags", not "style"
                "model": "V5",               # single field, not "suno" + model_version
                "make_instrumental": False,
                "webhook_url": f"{WEBHOOK_URL}?variant_id={variant_id}",
                "webhook_secret": webhook_secret,
            },
            timeout=30,
        )
        response.raise_for_status()
        # Once Apiframe returns a task_id, the credit is spent — no refund possible
        # even if generation fails downstream. Refund only happens above when the
        # submission itself errors (connection failure, 4xx/5xx before task_id).
        task_id = response.json()["task_id"]

        cur = conn.cursor()
        cur.execute(
            """UPDATE song_variants
               SET provider_job_id = ?, status = 'generating'
               WHERE id = ?""",
            (task_id, variant_id),
        )
        conn.commit()
    except Exception as exc:
        cur = conn.cursor()
        _refund_credit(cur, user_id)
        cur.execute(
            "UPDATE song_variants SET status = 'failed' WHERE id = ?",
            (variant_id,),
        )
        conn.commit()
        conn.close()
        raise RuntimeError(f"Music API submission failed: {exc}") from exc

    conn.close()
    return {"variant_id": variant_id, "status": "generating"}


def generate_multiple_variants(
    user_id: str,
    lyric_id: int,
    genres: list[str],
    db_path: pathlib.Path,
) -> dict:
    """Generate the same lyrics in multiple genres. Costs len(genres) credits."""
    from song_genres import GENRE_PRESETS

    valid_genres = [g for g in genres if g in GENRE_PRESETS]
    if not valid_genres:
        raise ValueError("No valid genres provided")
    if len(valid_genres) > 7:
        raise ValueError("Maximum 7 variants per request")

    # Pre-check credits before submitting any jobs
    conn = db._conn(db_path)
    cur = conn.cursor()
    cur.execute("SELECT balance FROM song_credits WHERE user_id = ?", (user_id,))
    row = cur.fetchone()
    available = row[0] if row else 0
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
