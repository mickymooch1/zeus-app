"""Apiframe v2 webhook handler.

Verifies HMAC-SHA256 signature using a signing secret derived from the API key
(SHA256(api_key)), per https://apiframe.ai/docs/webhooks.
"""
import os
import hmac
import hashlib
import pathlib
import shutil
import sqlite3
import logging
import requests
from fastapi import APIRouter, Request, HTTPException

logger = logging.getLogger("zeus.webhooks")

router = APIRouter()

GENRE_COVER_PROMPTS: dict[str, str] = {
    "blues":        "cinematic blues bar at night, warm amber light, vintage microphone, smoky atmosphere, moody and soulful",
    "soul":         "Motown recording studio, warm golden light, vintage instruments, soulful and rich atmosphere",
    "rnb":          "modern R&B aesthetic, purple and gold tones, luxurious urban setting, smooth and contemporary",
    "country":      "golden sunset over Nashville, acoustic guitar silhouette, americana",
    "reggae":       "tropical beach sunset, vibrant colours, laid back Caribbean atmosphere",
    "pop":          "bright modern stage with colourful lights, clean contemporary aesthetic",
    "rock":         "dramatic dark stage with lightning bolts, electric guitars, high energy",
    "hiphop":       "urban rooftop at night, city lights, gritty authentic street aesthetic",
    "lofi":         "cosy rainy window cafe scene, warm lo-fi aesthetic, peaceful and nostalgic",
    "edm":          "massive festival stage with laser lights, crowd energy, neon colours",
    "acoustic":     "intimate wooden stage, candlelight, warm natural tones, folk aesthetic",
    "irishjig":     "traditional Irish pub interior, warm firelight, fiddles and drums",
    "irishfolk":    "misty Irish countryside at dawn, stone walls, ancient and atmospheric",
    "drumandbass":  "underground rave, strobe lights, dark industrial warehouse, high energy",
    "grime":        "London rooftops at night, urban gritty neon, raw street energy",
    "ukgarage":     "late night London underground, neon reflections, sleek urban cool",
    "jungle":       "dark 90s rave warehouse, green laser lights, raw underground energy",
    "bassline":     "underground Sheffield club, minimal lighting, heavy bass atmosphere",
    "house":        "sunrise Ibiza terrace, warm golden light, euphoric open air club",
    "bluessoul":    "intimate jazz club, warm spotlight, emotional and deeply soulful",
    "loversrock":   "romantic Caribbean sunset, warm pink and gold tones, tropical flowers, intimate and sensual atmosphere",
    "ukdrill":      "dark London night, CCTV aesthetic, gritty urban concrete, cold blue tones, raw South London energy",
    "kpop":         "vibrant pastel Seoul cityscape, neon lights, clean modern aesthetic, bright pink and blue tones, high energy K-pop visual",
    "deepsoulblues": "dimly lit Mississippi juke joint, single spotlight, weathered wooden stage, raw and emotional deep south atmosphere, warm sepia tones",
}

_DEFAULT_COVER_PROMPT = "professional album cover art, cinematic, high quality"


def _generate_flux_cover(variant_id: int, genre_tag: str | None) -> str | None:
    """Generate a Flux cover image and save to song storage. Returns public URL or None."""
    try:
        import image_generator as _img
        prompt = GENRE_COVER_PROMPTS.get(genre_tag or "", _DEFAULT_COVER_PROMPT)
        flux_url = _img.submit_image_generation(prompt, "1:1")
        job_id = flux_url.rsplit("/", 1)[-1].replace(".jpg", "")
        src = pathlib.Path("/data/images") / f"{job_id}.jpg"
        dst = pathlib.Path(STORAGE_PATH) / f"{variant_id}_cover.jpg"
        shutil.copy2(src, dst)
        cover_url = f"{PUBLIC_BASE_URL}/{variant_id}_cover.jpg"
        logger.info("Flux cover generated: variant_id=%d genre=%s → %s", variant_id, genre_tag, cover_url)
        return cover_url
    except Exception as exc:
        logger.warning("Flux cover failed for variant_id=%d: %s", variant_id, exc)
        return None


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

    # Completed — extract tracks from result dict
    result = body.get("result")
    if not result or not isinstance(result, dict):
        logger.error("Completed webhook missing/invalid result: %r", body)
        conn = sqlite3.connect(DB_PATH)
        try:
            conn.execute("UPDATE song_variants SET status = 'failed' WHERE id = ?", (variant_id,))
            conn.commit()
        finally:
            conn.close()
        return {"ok": True, "status": "no_result"}

    tracks = result.get("tracks", [])
    if not tracks:
        logger.error("Completed webhook has no tracks: %r", result)
        conn = sqlite3.connect(DB_PATH)
        try:
            conn.execute("UPDATE song_variants SET status = 'failed' WHERE id = ?", (variant_id,))
            conn.commit()
        finally:
            conn.close()
        return {"ok": True, "status": "no_tracks"}

    # Look up the original variant row now — needed for take 2 insertion
    conn = sqlite3.connect(DB_PATH)
    try:
        orig = conn.execute(
            "SELECT lyric_id, user_id, style_prompt, genre_tag, provider_job_id FROM song_variants WHERE id = ?",
            (variant_id,),
        ).fetchone()
    finally:
        conn.close()

    os.makedirs(STORAGE_PATH, exist_ok=True)

    # ── Take 1: update existing variant row ──────────────────────────────────
    track1 = tracks[0]
    temp_url1 = track1["audioUrl"]
    duration1 = round(track1.get("duration", 0))

    logger.info("Apiframe webhook: downloading take 1 from %s", temp_url1)
    dl1 = requests.get(temp_url1, timeout=120)
    dl1.raise_for_status()
    local_path1 = os.path.join(STORAGE_PATH, f"{variant_id}.mp3")
    with open(local_path1, "wb") as fh:
        fh.write(dl1.content)
    permanent_url1 = f"{PUBLIC_BASE_URL}/{variant_id}.mp3"

    permanent_image_url1 = None
    temp_image_url1 = track1.get("imageUrl")
    if temp_image_url1:
        logger.info("Apiframe webhook: downloading take 1 cover art from %s", temp_image_url1)
        try:
            img1 = requests.get(temp_image_url1, timeout=60)
            img1.raise_for_status()
            with open(os.path.join(STORAGE_PATH, f"{variant_id}.jpg"), "wb") as fh:
                fh.write(img1.content)
            permanent_image_url1 = f"{PUBLIC_BASE_URL}/{variant_id}.jpg"
        except Exception as exc:
            logger.warning("Apiframe webhook: failed to download take 1 cover art: %s", exc)

    genre_tag = orig[3] if orig else None
    flux_cover1 = _generate_flux_cover(variant_id, genre_tag)
    if flux_cover1:
        permanent_image_url1 = flux_cover1

    conn = sqlite3.connect(DB_PATH)
    try:
        conn.execute(
            """UPDATE song_variants
               SET status = 'complete', mp3_url = ?, image_url = ?, duration_seconds = ?,
                   take_number = 1, completed_at = CURRENT_TIMESTAMP
               WHERE id = ?""",
            (permanent_url1, permanent_image_url1, duration1, variant_id),
        )
        conn.commit()
    finally:
        conn.close()
    logger.info("Apiframe webhook take 1 complete: variant_id=%d url=%s", variant_id, permanent_url1)

    # ── Take 2: insert new row, download second track if present ─────────────
    take2_variant_id = None
    permanent_url2 = None

    if len(tracks) >= 2 and orig:
        track2 = tracks[1]
        temp_url2 = track2["audioUrl"]
        duration2 = round(track2.get("duration", 0))

        conn = sqlite3.connect(DB_PATH)
        try:
            cur = conn.cursor()
            cur.execute(
                """INSERT INTO song_variants
                   (lyric_id, user_id, style_prompt, genre_tag, provider_job_id,
                    take_number, status, duration_seconds, completed_at)
                   VALUES (?, ?, ?, ?, ?, 2, 'complete', ?, CURRENT_TIMESTAMP)""",
                (orig[0], orig[1], orig[2], orig[3], orig[4], duration2),
            )
            take2_variant_id = cur.lastrowid
            conn.commit()
        finally:
            conn.close()

        logger.info("Apiframe webhook: downloading take 2 from %s", temp_url2)
        dl2 = requests.get(temp_url2, timeout=120)
        dl2.raise_for_status()
        local_path2 = os.path.join(STORAGE_PATH, f"{take2_variant_id}.mp3")
        with open(local_path2, "wb") as fh:
            fh.write(dl2.content)
        permanent_url2 = f"{PUBLIC_BASE_URL}/{take2_variant_id}.mp3"

        permanent_image_url2 = None
        temp_image_url2 = track2.get("imageUrl")
        if temp_image_url2:
            logger.info("Apiframe webhook: downloading take 2 cover art from %s", temp_image_url2)
            try:
                img2 = requests.get(temp_image_url2, timeout=60)
                img2.raise_for_status()
                with open(os.path.join(STORAGE_PATH, f"{take2_variant_id}.jpg"), "wb") as fh:
                    fh.write(img2.content)
                permanent_image_url2 = f"{PUBLIC_BASE_URL}/{take2_variant_id}.jpg"
            except Exception as exc:
                logger.warning("Apiframe webhook: failed to download take 2 cover art: %s", exc)

        flux_cover2 = _generate_flux_cover(take2_variant_id, genre_tag)
        if flux_cover2:
            permanent_image_url2 = flux_cover2

        conn = sqlite3.connect(DB_PATH)
        try:
            conn.execute(
                "UPDATE song_variants SET mp3_url = ?, image_url = ? WHERE id = ?",
                (permanent_url2, permanent_image_url2, take2_variant_id),
            )
            conn.commit()
        finally:
            conn.close()
        logger.info("Apiframe webhook take 2 complete: variant_id=%d url=%s", take2_variant_id, permanent_url2)

    payload = {"ok": True, "status": "complete", "take1_url": permanent_url1}
    if take2_variant_id:
        payload["take2_variant_id"] = take2_variant_id
        payload["take2_url"] = permanent_url2
    return payload
