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
    "blues":        "epic blues album cover art, weathered Black bluesman seated on a worn wooden porch, battered acoustic guitar in hand, flickering oil lamp casting deep amber shadows, Mississippi Delta at dusk, storm clouds rolling in over flat cotton fields, cracked dry earth, old rusted tin-roof shack, moody cinematic lighting, rich ochre and dark navy tones, ultra-detailed digital painting, professional music artwork",
    "soul":         "epic soul album cover art, radiant Black woman in a sequined golden gown centre stage, dramatic Motown spotlight from above, lush orchestral musicians behind her in silhouette, deep red velvet curtains, polished dark wood stage, warm amber and gold light flooding the scene, vintage 1960s recording studio grandeur, ultra-detailed digital painting, cinematic dramatic lighting, professional music artwork",
    "rnb":          "epic R&B album cover art, elegant Black woman draped in deep purple satin against a floor-to-ceiling city window at night, Manhattan skyline glittering behind her, soft purple and gold neon reflections on glossy marble floors, rose petals scattered, champagne glass, moody intimate luxury penthouse atmosphere, ultra-detailed digital painting, cinematic dramatic lighting, professional music artwork",
    "country":      "epic country album cover art, lone American cowboy silhouette on horseback atop a red rock mesa, vast golden sunset over Monument Valley canyon lands, blazing orange and crimson sky with dramatic cloud streaks, acoustic guitar resting against a wooden fence post, wildflowers and sagebrush, dust rising from the trail, ultra-detailed digital painting, cinematic dramatic lighting, professional music artwork",
    "reggae":       "epic reggae album cover art, majestic Black woman with long dreadlocks and gold jewellery, massive speakers on either side, tropical rainforest and palm trees, dramatic golden orange sunset sky, Rastafarian colours red gold green, cannabis and tropical plants, urban skyline background, ultra-detailed digital painting, professional music artwork, cinematic dramatic lighting",
    "pop":          "epic pop album cover art, dazzling young woman bursting through a shower of glitter and confetti on a massive neon-lit arena stage, enormous LED screens behind her with abstract colour explosions, holographic light beams cutting through smoke, screaming crowd below, electric pink magenta and electric blue tones, ultra-modern high-energy spectacle, ultra-detailed digital painting, cinematic dramatic lighting, professional music artwork",
    "rock":         "epic rock album cover art, raw electric guitarist mid-solo on a rain-soaked rooftop stage, lightning bolt splitting a bruised purple and black sky behind him, stacks of Marshall amplifiers towering on either side, pyrotechnic fire pillars erupting, electric blue and white flashes reflecting off wet concrete, raw high-energy chaos, ultra-detailed digital painting, cinematic dramatic lighting, professional music artwork",
    "hiphop":       "epic hip-hop album cover art, Black rapper standing tall on a New York City rooftop at midnight, arms wide open facing the glittering Manhattan skyline, golden chain jewellery catching the light, graffiti mural wall behind him, low-angle dramatic perspective, city lights reflected in rain puddles on the rooftop, deep indigo sky, hazy atmospheric fog, ultra-detailed digital painting, cinematic dramatic lighting, professional music artwork",
    "lofi":         "epic lo-fi album cover art, anime-style young woman studying at a cluttered wooden desk beside a rain-streaked window, warm amber desk lamp glow, steaming mug of tea, cassette tapes and vinyl records stacked beside her, soft bokeh city lights through misty glass, autumn leaves on the windowsill, peaceful melancholic mood, warm sepia and dusty rose tones, ultra-detailed digital painting, nostalgic soft cinematic lighting, professional music artwork",
    "edm":          "epic EDM album cover art, massive outdoor festival main stage at night, towering LED screens blazing with neon fractals, laser beams in electric cyan magenta and yellow cutting across a sea of one hundred thousand raised hands, enormous speaker rigs, fire cannons erupting on either side, DJ silhouette behind a glowing console high above the crowd, ultra-detailed digital painting, cinematic dramatic lighting, professional music artwork",
    "acoustic":     "epic acoustic album cover art, lone singer-songwriter perched on a mossy stone wall in an Irish meadow at golden hour, vintage acoustic guitar in hand, wildflowers and tall grass swaying around her, soft warm amber sunlight breaking through ancient oak trees, distant rolling green hills, mist in the valleys, intimate and deeply personal atmosphere, ultra-detailed digital painting, soft cinematic golden lighting, professional music artwork",
    "irishjig":     "epic Irish jig album cover art, lively céilí dancers in traditional green and gold costumes mid-spin inside a stone-walled Irish pub, blazing turf fireplace roaring in the background, fiddles tin whistles and bodhrán drums hanging on the walls, pints of Guinness on oak tables, warm amber firelight flickering across laughing faces, ancient low timber ceiling, ultra-detailed digital painting, cinematic warm dramatic lighting, professional music artwork",
    "irishfolk":    "epic Irish folk album cover art, solitary Irish bard standing on a cliff edge overlooking the wild Atlantic Ocean at dawn, acoustic guitar slung across his back, grey mist rolling in from the sea, ancient moss-covered stone ruins beside him, dramatic moody sky in deep slate blue and pearl white, heather and gorse on the clifftops, waves crashing far below, ultra-detailed digital painting, cinematic atmospheric lighting, professional music artwork",
    "drumandbass":  "epic drum and bass album cover art, underground rave in a cavernous industrial power station, enormous bass bins stacked floor to ceiling, strobe lights cutting through thick fog in electric white and ice blue, silhouetted crowd heaving in unison, exposed brick and rusted iron girders, shattered glass catching the strobe, raw underground energy, deep shadow with explosive light bursts, ultra-detailed digital painting, cinematic dramatic lighting, professional music artwork",
    "grime":        "epic grime album cover art, Black MC standing under a flickering East London streetlight on a rain-slicked concrete estate at midnight, council tower blocks looming behind him, graffiti-tagged corrugated shutters, cold blue and sickly yellow sodium light reflecting in puddles, hooded figures in the background, raw urban tension, exhaled breath visible in cold air, ultra-detailed digital painting, cinematic dramatic lighting, professional music artwork",
    "ukgarage":     "epic UK garage album cover art, gleaming chrome and black luxury car parked outside a neon-lit London nightclub at 2am, Black British MC leaning against the bonnet in sharp designer clothes, wet tarmac reflecting electric blue and pink neon signs, bouncers at velvet rope behind him, night fog and city glow, sleek urban cool, ultra-detailed digital painting, cinematic dramatic lighting, professional music artwork",
    "jungle":       "epic jungle album cover art, dark 1993 London warehouse rave, towering speaker stacks pumping bass, green and gold laser beams slicing through dense smoke over a mass of dancing bodies, Jamaican and British flags on the walls, photocopied flyers plastered everywhere, MC on the mic silhouetted in a single spotlight, raw underground atmosphere dripping with sweat and energy, ultra-detailed digital painting, cinematic dramatic lighting, professional music artwork",
    "bassline":     "epic bassline house album cover art, underground Sheffield warehouse club at 3am, enormous sub-bass speaker wall vibrating the concrete floor, minimal red and amber lighting casting long shadows, silhouetted crowd locked in a hypnotic groove, industrial steel beams overhead, cigarette smoke and dry ice swirling, raw northern English underground atmosphere, ultra-detailed digital painting, cinematic dramatic lighting, professional music artwork",
    "house":        "epic house music album cover art, sunrise set at an open-air Ibiza super-club terrace, DJ at the decks silhouetted against a blazing coral and gold Mediterranean sunrise, crowd of euphoric dancers with hands raised, palm trees and white-washed walls, warm golden light flooding the dancefloor, shimmering ocean visible in the distance, pure joy and liberation in the air, ultra-detailed digital painting, cinematic dramatic lighting, professional music artwork",
    "bluessoul":    "epic blues soul album cover art, Black woman in a crimson evening gown seated on a wooden stool under a single warm spotlight on an empty jazz club stage, upright bass and piano in shadow behind her, deep mahogany bar and candles in the background, emotional vulnerability in her expression, rich burgundy and amber tones, whiskey glass on the stage floor, ultra-detailed digital painting, cinematic intimate dramatic lighting, professional music artwork",
    "loversrock":   "epic lovers rock album cover art, romantic Black British couple slow dancing on a moonlit Caribbean beach, tropical flowers in her hair, warm pink and gold light from tiki torches reflecting on calm turquoise water, palm trees swaying overhead, bougainvillea cascading down a white-washed wall nearby, sensual and deeply intimate atmosphere, ultra-detailed digital painting, cinematic warm romantic lighting, professional music artwork",
    "ukdrill":      "epic UK drill album cover art, Black drill artist in designer puffer jacket standing in the centre of a dark South London estate at night, cold blue CCTV camera glow overhead, concrete brutalist tower blocks receding into foggy darkness behind him, puddles reflecting cold white and blue light, barbed wire fencing, tense raw atmosphere, ultra-detailed digital painting, cinematic cold dramatic lighting, professional music artwork",
    "kpop":         "epic K-pop album cover art, stunning Korean idol group in colour-coordinated pastel outfits posed on a futuristic Seoul rooftop stage, enormous holographic displays behind them blazing in electric pink cyan and white, cherry blossoms and neon signage, confetti explosion mid-air, flawless high-fashion styling, high-energy euphoric atmosphere, ultra-detailed digital painting, cinematic dramatic lighting, professional music artwork",
    "deepsoulblues": "epic deep soul blues album cover art, elderly Black blues patriarch seated in a rocking chair on a weathered Mississippi porch at dusk, ancient resonator guitar across his lap, expression carved with decades of heartache and wisdom, fireflies beginning to glow in the humid evening air, Spanish moss hanging from a massive live oak tree, distant red sky fading to indigo, oil lamp on the porch rail, ultra-detailed digital painting, deeply cinematic sepia and amber lighting, professional music artwork",
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
