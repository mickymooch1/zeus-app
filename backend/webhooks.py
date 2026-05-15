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
import textwrap
import threading
import requests
from PIL import Image, ImageDraw, ImageFont
from fastapi import APIRouter, Request, HTTPException

logger = logging.getLogger("zeus.webhooks")

router = APIRouter()

GENRE_COVER_PROMPTS: dict[str, str] = {
    "blues":        "cinematic album cover, Black blues guitarist in foreground, worn guitar, Mississippi Delta landscape behind, warm sunset, dusty road, deep soulful atmosphere, ultra detailed professional music artwork, Black musician, NOT white, correct ethnicity",
    "soul":         "cinematic album cover, Black soul singer performing in foreground, elegant stage lighting, warm golden tones, emotional powerful expression, ultra detailed professional music artwork, Black musician, NOT white, correct ethnicity",
    "rnb":          "cinematic album cover, Black RnB artist in foreground, stylish urban setting, moody blue and purple lighting, confident expression, ultra detailed professional music artwork, Black musician, NOT white, correct ethnicity",
    "country":      "cinematic album cover, rugged American cowboy with acoustic guitar in foreground, massive speakers either side, Monument Valley canyon sunset behind him, blazing orange and crimson sky, wildflowers and sagebrush, ultra detailed professional music artwork, correct ethnicity",
    "reggae":       "cinematic album cover, beautiful Black woman with long dreadlocks in foreground, massive speakers either side, tropical rainforest and palm trees behind her, Rastafarian colours red gold green, cannabis leaves, dramatic golden sunset, ultra detailed professional music artwork, Black musician, NOT white, correct ethnicity",
    "pop":          "cinematic album cover, glamorous young pop star in sparkling outfit in foreground, massive speakers either side, neon-lit arena stage behind her, enormous LED screens, holographic light beams, confetti explosion, ultra detailed professional music artwork, correct ethnicity",
    "rock":         "cinematic album cover, electric guitarist in leather jacket in foreground, massive speakers either side, rain-soaked rooftop stage behind him, lightning bolt in bruised purple sky, Marshall amp stacks, pyrotechnic fire pillars, ultra detailed professional music artwork, correct ethnicity",
    "hiphop":       "cinematic album cover, Black rapper in gold chain jewellery in foreground, massive speakers either side, New York City rooftop at midnight behind him, glittering Manhattan skyline, graffiti mural wall, ultra detailed professional music artwork, Black musician, NOT white, correct ethnicity",
    "lofi":         "cinematic album cover, young woman with headphones at desk in foreground, rain-streaked window with soft city bokeh behind her, warm amber desk lamp, cassette tapes and vinyl records, steaming mug, ultra detailed professional music artwork, correct ethnicity",
    "edm":          "cinematic album cover, EDM DJ in neon-lit booth in foreground, massive speakers either side, outdoor festival crowd behind them, towering LED screens blazing with neon fractals, laser beams, fire cannons erupting, ultra detailed professional music artwork, correct ethnicity",
    "acoustic":     "cinematic album cover, female singer-songwriter with vintage acoustic guitar in foreground, Irish meadow at golden hour behind her, rolling green hills and wildflowers, ancient oak trees, ultra detailed professional music artwork, correct ethnicity",
    "irishjig":     "cinematic album cover, Irish céilí dancer in traditional green and gold costume in foreground, stone-walled pub with blazing turf fireplace behind her, fiddles and tin whistles on walls, Guinness on oak tables, ultra detailed professional music artwork, correct ethnicity",
    "irishfolk":    "cinematic album cover, solitary Irish bard with acoustic guitar in foreground, Atlantic cliff edge at dawn behind him, ancient stone ruins, dramatic slate blue sky, waves crashing below, ultra detailed professional music artwork, correct ethnicity",
    "drumandbass":  "cinematic album cover, Black British DJ with headphones in foreground, massive speakers either side, cavernous industrial rave behind him, strobe lights in electric white and ice blue cutting through fog, ultra detailed professional music artwork, Black musician, NOT white, correct ethnicity",
    "grime":        "cinematic album cover, Black grime MC holding microphone in foreground, massive speakers either side, rain-slicked East London council estate at midnight behind him, tower blocks, cold blue streetlight, graffiti-tagged shutters, ultra detailed professional music artwork, Black musician, NOT white, correct ethnicity",
    "ukgarage":     "cinematic album cover, stylish Black British MC in designer clothes in foreground, massive speakers either side, gleaming luxury car and neon-lit London club behind him, wet tarmac reflecting electric blue and pink neon, ultra detailed professional music artwork, Black musician, NOT white, correct ethnicity",
    "jungle":       "cinematic album cover, Black jungle MC on the mic in foreground, massive speakers either side, dark 1993 London warehouse rave behind him, green and gold laser beams through smoke, Jamaican and British flags, ultra detailed professional music artwork, Black musician, NOT white, correct ethnicity",
    "bassline":     "cinematic album cover, Black British DJ at decks in foreground, massive sub-bass speaker wall either side, underground Sheffield warehouse club behind him, red and amber lighting, raw northern underground energy, ultra detailed professional music artwork, Black musician, NOT white, correct ethnicity",
    "house":        "cinematic album cover, DJ at the decks in foreground, massive speakers either side, euphoric Ibiza open-air sunrise terrace behind them, blazing coral and gold Mediterranean sky, crowd with hands raised, palm trees, ultra detailed professional music artwork, correct ethnicity",
    "bluessoul":    "cinematic album cover, Black blues soul singer in foreground, warm intimate venue, golden candlelight, raw emotional expression, ultra detailed professional music artwork, Black musician, NOT white, correct ethnicity",
    "loversrock":   "cinematic album cover, romantic Black British couple in foreground, moonlit Caribbean beach behind them, tropical flowers, warm pink and gold tiki torch light, turquoise water, palm trees swaying, ultra detailed professional music artwork, Black musicians, NOT white, correct ethnicity",
    "ukdrill":      "cinematic album cover, Black drill artist in designer puffer jacket in foreground, massive speakers either side, dark South London estate at night behind him, cold blue CCTV glow, concrete brutalist tower blocks, barbed wire fencing, ultra detailed professional music artwork, Black musician, NOT white, correct ethnicity",
    "kpop":         "cinematic album cover, Korean K-pop idol group in colour-coordinated pastel outfits in foreground, massive speakers either side, futuristic Seoul rooftop stage behind them, enormous holographic displays, cherry blossoms and confetti explosion, ultra detailed professional music artwork, Korean musicians, NOT white, correct ethnicity",
    "deepsoulblues": "cinematic album cover, elderly Black woman gospel singer in foreground, powerful dignified expression, old American church or Southern porch behind her, warm amber candlelight, deep emotional atmosphere, ultra detailed professional music artwork, Black musician, NOT white, correct ethnicity",
    "niche":          "cinematic album cover, female vocalist in sequined dress in foreground, massive speakers either side, underground Sheffield warehouse club behind her, purple and blue neon, cigarette smoke swirling, raw Yorkshire underground energy, ultra detailed professional music artwork, correct ethnicity",
    "ukstreetsoul":   "cinematic album cover, stylish Black British singer in foreground, sun-drenched Peckham backstreet at golden hour behind him, warm amber street lights, graffiti murals, long shadows across pavement, ultra detailed professional music artwork, Black musician, NOT white, correct ethnicity",
    "classical":      "cinematic album cover, orchestra conductor with baton raised in foreground, grand concert hall behind him, enormous chandelier blazing overhead, full symphony in black formal wear, gilded balconies packed with audience, ultra detailed professional music artwork, correct ethnicity",
    "indie":          "cinematic album cover, indie guitarist with vintage guitar in foreground, intimate underground music venue behind them, exposed brick walls plastered with tour posters, warm amber and red stage lights, ultra detailed professional music artwork, correct ethnicity",
    "techno":         "cinematic album cover, techno DJ at modular synth wall in foreground, massive speakers either side, dark Berlin underground warehouse behind them, minimal cold white strobes cutting through smoke, exposed concrete pillars, ultra detailed professional music artwork, correct ethnicity",
    "technhouse":     "cinematic album cover, tech house DJ at sleek decks in foreground, massive speakers either side, minimal underground club interior behind them, black and gunmetal grey architecture, cool blue and amber lighting, ultra detailed professional music artwork, correct ethnicity",
    "hyperpop":       "cinematic album cover, young hyperpop artist in oversized candy-coloured clothing in foreground, exploding glitter and shattered pixels around them, electric pink and cyan light rays, holographic butterfly wings and melting emoji faces, glitchy digital chaos, ultra detailed professional music artwork, correct ethnicity",
    "afrobeats":      "cinematic album cover, beautiful Black woman with dreadlocks in foreground, vibrant West African cityscape behind her, massive speakers on each side, tropical plants, dramatic golden sunset, ultra detailed professional music artwork, Black musician, NOT white, correct ethnicity",
    "amapiano":       "cinematic album cover, well-dressed young Black South African DJ in foreground, massive speakers either side, rooftop party in Johannesburg at golden sunset behind him, city skyline blazing amber, log step dancers in vibrant outfits, ultra detailed professional music artwork, Black musician, NOT white, correct ethnicity",
    "driftphonk":     "cinematic album cover, phonk driver in cap and face mask in foreground, modified Nissan Silvia S15 power-sliding on neon-lit Japanese mountain touge behind him, deep red tail lights, VHS grain and chromatic aberration, dark Memphis aesthetic, ultra detailed professional music artwork, correct ethnicity",
    "jerseyclub":     "cinematic album cover, Jersey Club DJ elevated on booth in foreground, massive speakers either side, packed Newark warehouse party behind them, dancers locked in sharp footwork, strobes, raw East Coast energy, ultra detailed professional music artwork, Black musician, NOT white, correct ethnicity",
    "afroswing":      "cinematic album cover, stylish Black British man with dreadlocks standing confidently in foreground, London urban street background at golden hour, large speakers either side, warm tropical colours, professional music artwork, ultra detailed, Black musician, NOT white, correct ethnicity",
    "rastadub":       "cinematic album cover, Black Rastafarian musician with long dreadlocks in foreground, massive speakers either side, vibrant tropical Jamaican landscape behind, Rastafarian colours red gold green, cannabis leaves, palm trees, dramatic golden sunset, ultra detailed professional music artwork, Black musician, NOT white, correct ethnicity",
    "deeprotbassline": "cinematic album cover, UK bassline DJ at decks in foreground, dark Northern rave warehouse behind, purple and blue neon lights, heavy bass atmosphere, ultra detailed professional music artwork, correct ethnicity",
    "jazz":            "cinematic album cover, Black jazz musician playing saxophone in foreground, smoky intimate jazz club behind, warm amber and gold lighting, vintage microphone, brick walls, ultra detailed professional music artwork, Black musician, NOT white, correct ethnicity",
}

_DEFAULT_COVER_PROMPT = "professional album cover art, cinematic, high quality"


def _add_text_overlay(image_path: str, title: str) -> None:
    """Burn a bold title into the bottom quarter of the cover image."""
    img = Image.open(image_path).convert("RGBA")
    draw = ImageDraw.Draw(img)
    w, h = img.size

    overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
    bar = ImageDraw.Draw(overlay)
    bar.rectangle([(0, h * 0.75), (w, h)], fill=(0, 0, 0, 160))
    img = Image.alpha_composite(img, overlay)
    draw = ImageDraw.Draw(img)

    try:
        font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", size=int(h * 0.07))
    except Exception:
        font = ImageFont.load_default()

    lines = textwrap.wrap(title.upper(), width=20)
    y = int(h * 0.78)
    for line in lines:
        bbox = draw.textbbox((0, 0), line, font=font)
        text_w = bbox[2] - bbox[0]
        draw.text(((w - text_w) / 2, y), line, font=font, fill=(255, 255, 255, 255))
        y += int(h * 0.09)

    img.convert("RGB").save(image_path, "JPEG", quality=95)


def _generate_flux_cover(variant_id: int, genre_tag: str | None, title: str = "") -> str | None:
    """Generate a Flux cover image and save to song storage. Returns public URL or None."""
    try:
        import image_generator as _img
        prompt = GENRE_COVER_PROMPTS.get(genre_tag or "", _DEFAULT_COVER_PROMPT)
        flux_url = _img.submit_image_generation(prompt, "1:1")
        job_id = flux_url.rsplit("/", 1)[-1].replace(".jpg", "")
        src = pathlib.Path("/data/images") / f"{job_id}.jpg"
        dst = pathlib.Path(STORAGE_PATH) / f"{variant_id}_cover.jpg"
        shutil.copy2(src, dst)
        _add_text_overlay(str(dst), title or genre_tag or "")
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
FAL_API_KEY = os.environ.get("FAL_API_KEY", "")


def _kling_pipeline(variant_id: int, cover_url: str, mp3_path: str, duration_seconds: int, genre_tag: str | None) -> None:
    """Background thread: submit cover art to Kling, loop clip with FFmpeg, save music video."""
    import time
    import subprocess
    try:
        if not FAL_API_KEY:
            logger.warning("Kling pipeline: FAL_API_KEY not set — skipping variant_id=%d", variant_id)
            return

        from songs import GENRE_MOTION_PROMPTS
        prompt = GENRE_MOTION_PROMPTS.get(
            genre_tag or "",
            "smooth cinematic camera motion, atmospheric lighting, dynamic visual movement",
        )

        fal_headers = {"Authorization": f"Key {FAL_API_KEY}", "Content-Type": "application/json"}

        # Submit to Kling via fal.ai async queue
        resp = requests.post(
            "https://queue.fal.run/fal-ai/kling-video/v2/master/image-to-video",
            headers=fal_headers,
            json={"image_url": cover_url, "prompt": prompt, "duration": "5", "aspect_ratio": "1:1"},
            timeout=30,
        )
        resp.raise_for_status()
        body = resp.json()
        request_id = body.get("request_id")
        if not request_id:
            raise RuntimeError(f"Kling: no request_id in response: {body!r}")

        logger.info("Kling submitted: variant_id=%d request_id=%s", variant_id, request_id)
        conn = sqlite3.connect(DB_PATH)
        try:
            conn.execute("UPDATE song_variants SET kling_request_id = ? WHERE id = ?", (request_id, variant_id))
            conn.commit()
        finally:
            conn.close()

        # Poll for completion (max 15 min)
        status_url = f"https://queue.fal.run/fal-ai/kling-video/v2/master/image-to-video/requests/{request_id}/status"
        result_url = f"https://queue.fal.run/fal-ai/kling-video/v2/master/image-to-video/requests/{request_id}"
        poll_headers = {"Authorization": f"Key {FAL_API_KEY}"}
        completed = False
        for _ in range(60):
            time.sleep(15)
            sr = requests.get(status_url, headers=poll_headers, timeout=15)
            sr.raise_for_status()
            status = sr.json().get("status")
            if status == "COMPLETED":
                completed = True
                break
            if status == "FAILED":
                raise RuntimeError(f"Kling job {request_id} reported FAILED")

        if not completed:
            raise RuntimeError(f"Kling job {request_id} timed out after 15 min")

        # Fetch result
        rr = requests.get(result_url, headers=poll_headers, timeout=15)
        rr.raise_for_status()
        result_data = rr.json()
        video_dl_url = (result_data.get("video") or {}).get("url")
        if not video_dl_url:
            raise RuntimeError(f"Kling result missing video URL: {result_data!r}")

        # Download 5s clip to temp
        clip_path = f"/tmp/kling_{variant_id}_clip.mp4"
        clip_resp = requests.get(video_dl_url, timeout=120)
        clip_resp.raise_for_status()
        with open(clip_path, "wb") as fh:
            fh.write(clip_resp.content)

        # FFmpeg: loop clip to full song duration, mux with MP3
        output_path = os.path.join(STORAGE_PATH, f"{variant_id}_music_video.mp4")
        duration = max(int(duration_seconds or 60), 5)
        proc = subprocess.run(
            [
                "ffmpeg", "-y",
                "-stream_loop", "-1", "-i", clip_path,
                "-i", mp3_path,
                "-t", str(duration),
                "-map", "0:v",
                "-map", "1:a",
                "-c:v", "libx264", "-preset", "fast", "-crf", "23",
                "-c:a", "aac", "-b:a", "192k",
                "-shortest",
                output_path,
            ],
            capture_output=True,
            timeout=300,
        )
        try:
            os.remove(clip_path)
        except Exception:
            pass

        if proc.returncode != 0:
            raise RuntimeError(f"FFmpeg failed (rc={proc.returncode}): {proc.stderr.decode()[:400]}")

        music_video_url = f"{PUBLIC_BASE_URL}/{variant_id}_music_video.mp4"
        conn = sqlite3.connect(DB_PATH)
        try:
            conn.execute("UPDATE song_variants SET music_video_url = ? WHERE id = ?", (music_video_url, variant_id))
            conn.commit()
        finally:
            conn.close()

        logger.info("Kling pipeline complete: variant_id=%d → %s", variant_id, music_video_url)

    except Exception as exc:
        logger.error("Kling pipeline failed for variant_id=%d: %s", variant_id, exc)


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

    # Guard: skip if already complete (duplicate webhook delivery)
    conn = sqlite3.connect(DB_PATH)
    try:
        _existing = conn.execute(
            "SELECT status, mp3_url FROM song_variants WHERE id = ?",
            (variant_id,),
        ).fetchone()
    finally:
        conn.close()
    if _existing and _existing[0] == "complete" and _existing[1]:
        logger.info("Apiframe webhook: variant_id=%d already complete — duplicate delivery skipped", variant_id)
        return {"ok": True, "status": "already_complete"}

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
    song_title = ""
    if orig:
        conn = sqlite3.connect(DB_PATH)
        try:
            row = conn.execute("SELECT title FROM lyrics WHERE id = ?", (orig[0],)).fetchone()
            song_title = row[0] if row and row[0] else ""
        finally:
            conn.close()
    flux_cover1 = _generate_flux_cover(variant_id, genre_tag, song_title)
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

    if flux_cover1 and duration1 and FAL_API_KEY:
        threading.Thread(
            target=_kling_pipeline,
            args=(variant_id, flux_cover1, local_path1, duration1, genre_tag),
            daemon=True,
        ).start()

    # ── Take 2: insert new row, download second track if present ─────────────
    take2_variant_id = None
    permanent_url2 = None

    if len(tracks) >= 2 and orig:
        track2 = tracks[1]
        temp_url2 = track2["audioUrl"]
        duration2 = round(track2.get("duration", 0))

        # Guard: skip if a take-2 row already exists for this Apiframe job
        conn = sqlite3.connect(DB_PATH)
        try:
            _t2 = conn.execute(
                "SELECT id FROM song_variants WHERE provider_job_id = ? AND take_number = 2",
                (orig[4],),
            ).fetchone()
        finally:
            conn.close()

        if _t2:
            logger.info("Apiframe webhook: take 2 already exists for job=%s — duplicate delivery skipped", orig[4])
        else:
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

            flux_cover2 = _generate_flux_cover(take2_variant_id, genre_tag, song_title)
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

            if flux_cover2 and duration2 and FAL_API_KEY:
                threading.Thread(
                    target=_kling_pipeline,
                    args=(take2_variant_id, flux_cover2, local_path2, duration2, genre_tag),
                    daemon=True,
                ).start()

    payload = {"ok": True, "status": "complete", "take1_url": permanent_url1}
    if take2_variant_id:
        payload["take2_variant_id"] = take2_variant_id
        payload["take2_url"] = permanent_url2
    return payload
