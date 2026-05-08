import logging
import os

import requests
from fastapi import APIRouter, Header, HTTPException, Request

import db

router = APIRouter()
log = logging.getLogger("zeus.webhooks")

STORAGE_PATH = os.environ.get("SONG_STORAGE_PATH", "/data/songs")
PUBLIC_BASE_URL = os.environ.get("SONG_PUBLIC_BASE_URL", "https://zeusaidesign.com/files/songs")


@router.post("/webhooks/apiframe")
async def apiframe_webhook(
    request: Request,
    x_webhook_secret: str | None = Header(None),
):
    variant_id_str = request.query_params.get("variant_id")
    if not variant_id_str:
        raise HTTPException(400, "Missing variant_id")
    try:
        variant_id = int(variant_id_str)
    except ValueError:
        raise HTTPException(400, "Invalid variant_id")

    db_path = db.get_db_path()

    # Auth: look up stored secret before touching the body
    variant = db.get_song_variant_by_id(db_path, variant_id)
    if not variant:
        raise HTTPException(404, "Variant not found")

    stored_secret = variant.get("webhook_secret")
    if not stored_secret or x_webhook_secret != stored_secret:
        log.warning("apiframe_webhook: secret mismatch for variant %s", variant_id)
        raise HTTPException(401, "Invalid webhook secret")

    body = await request.json()
    status = body.get("status")
    log.info("apiframe_webhook: variant=%s status=%s", variant_id, status)

    # Not finished — mark failed. No credit refund: Apiframe already charged once
    # they accepted the job and returned a task_id.
    if status != "finished":
        conn = db._conn(db_path)
        try:
            conn.execute(
                "UPDATE song_variants SET status = 'failed' WHERE id = ?",
                (variant_id,),
            )
            conn.commit()
        finally:
            conn.close()
        log.warning("apiframe_webhook: variant %s failed (status=%s), no refund", variant_id, status)
        return {"ok": True, "status": "failed"}

    songs = body.get("songs", [])
    if not songs:
        raise HTTPException(400, "Webhook payload missing songs array")

    os.makedirs(STORAGE_PATH, exist_ok=True)

    # ── Take 1: update the existing variant row ───────────────────────────────
    song1 = songs[0]
    temp_url1 = song1["audio_url"]
    local_path1 = os.path.join(STORAGE_PATH, f"{variant_id}.mp3")

    log.info("apiframe_webhook: downloading take 1 from %s", temp_url1)
    dl1 = requests.get(temp_url1, timeout=120)
    dl1.raise_for_status()
    with open(local_path1, "wb") as fh:
        fh.write(dl1.content)
    permanent_url1 = f"{PUBLIC_BASE_URL}/{variant_id}.mp3"
    log.info("apiframe_webhook: take 1 saved to %s", local_path1)

    conn = db._conn(db_path)
    try:
        conn.execute(
            """UPDATE song_variants
               SET status = 'complete',
                   mp3_url = ?,
                   take_number = 1,
                   completed_at = CURRENT_TIMESTAMP
               WHERE id = ?""",
            (permanent_url1, variant_id),
        )
        conn.commit()
    finally:
        conn.close()

    # ── Take 2: insert a new variant row, then download ───────────────────────
    take2_variant_id = None
    permanent_url2 = None

    if len(songs) >= 2:
        song2 = songs[1]
        temp_url2 = song2["audio_url"]

        conn = db._conn(db_path)
        try:
            cur = conn.cursor()
            cur.execute(
                """INSERT INTO song_variants
                   (lyric_id, user_id, style_prompt, genre_tag,
                    provider_job_id, take_number, status, completed_at)
                   VALUES (?, ?, ?, ?, ?, 2, 'complete', CURRENT_TIMESTAMP)""",
                (
                    variant["lyric_id"],
                    variant["user_id"],
                    variant["style_prompt"],
                    variant["genre_tag"],
                    variant["provider_job_id"],
                ),
            )
            take2_variant_id = cur.lastrowid
            conn.commit()
        finally:
            conn.close()

        log.info("apiframe_webhook: downloading take 2 from %s", temp_url2)
        local_path2 = os.path.join(STORAGE_PATH, f"{take2_variant_id}.mp3")
        dl2 = requests.get(temp_url2, timeout=120)
        dl2.raise_for_status()
        with open(local_path2, "wb") as fh:
            fh.write(dl2.content)
        permanent_url2 = f"{PUBLIC_BASE_URL}/{take2_variant_id}.mp3"
        log.info("apiframe_webhook: take 2 saved to %s", local_path2)

        conn = db._conn(db_path)
        try:
            conn.execute(
                "UPDATE song_variants SET mp3_url = ? WHERE id = ?",
                (permanent_url2, take2_variant_id),
            )
            conn.commit()
        finally:
            conn.close()

    result: dict = {"ok": True, "status": "complete", "take1_url": permanent_url1}
    if take2_variant_id:
        result["take2_variant_id"] = take2_variant_id
        result["take2_url"] = permanent_url2
    return result
