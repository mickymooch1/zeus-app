"""Song variant generation via Apiframe v2 (https://api.apiframe.ai/v2/music/generate)."""
import os
import random
import sqlite3
import logging
import re
import time
import requests

GENRE_MODEL_OVERRIDES: dict[str, str] = {
    'ragga':    'V5_5',
    'bhangra':  'V5_5',
    'rastadub': 'V5_5',
    'deeproots': 'V5_5',
}

RANDOM_PRODUCTION = [
    "with unexpected key change",
    "with a dramatic breakdown",
    "with call and response vocals",
    "with an extended outro",
    "with a spoken word section",
    "with double time flow",
    "with a slow intro building to full energy",
    "with stripped back verses and huge chorus",
]

logger = logging.getLogger("zeus.songs")

GENRE_MOTION_PROMPTS: dict[str, str] = {
    "blues":        "blues guitarist playing soulfully, fingers moving on strings, body swaying, warm amber light",
    "soul":         "soul singer performing passionately, hands moving expressively, warm golden light",
    "reggae":       "reggae musician playing bass, relaxed rhythmic movement, tropical setting",
    "hiphop":       "hip-hop artist performing confidently, hands moving, urban setting",
    "drumandbass":  "DJ performing at rave, hands on decks, strobe lights, energetic movement",
    "grime":        "grime MC performing intensely, microphone in hand, urban backdrop",
    "house":        "DJ at club, hands raised, euphoric crowd, colourful lights",
    "jungle":       "jungle MC on stage, energetic performance, rave lights",
    "country":      "country guitarist strumming, gentle swaying, warm natural light",
    "acoustic":     "acoustic guitarist playing intimately, fingers on strings, candlelight",
    "rock":         "rock guitarist shredding, dramatic movement, stage lighting",
    "lofi":         "indie musician playing piano, relaxed peaceful movement, cosy setting",
    "edm":          "EDM performer on stage, arms raised, laser lights, massive crowd",
    "kpop":         "K-pop performer dancing gracefully, precise choreography, bright stage",
    "niche":         "DJ performing at club, hands on decks, purple neon lights, Sheffield night",
    "ukdrill":       "drill artist performing, intense expression, dark urban setting",
    "loversrock":    "lovers rock singer performing romantically, smooth movement, warm light",
    "rnb":           "R&B singer performing smoothly, flowing movement, soft purple lighting, intimate atmosphere",
    "bluessoul":     "blues soul vocalist on stage, soulful expression, hands raised, warm golden spotlight",
    "deepsoulblues": "deep soul singer seated, emotional performance, eyes closed, dim amber light",
    "bassline":      "DJ at underground Sheffield club, hands on decks, hypnotic movement, red and amber lighting",
    "irishjig":      "Irish céilí dancers spinning, traditional costumes, lively energetic movement, warm firelight",
    "irishfolk":     "Irish folk musician playing acoustic guitar, gentle swaying, misty Atlantic clifftop backdrop",
    "pop":           "pop star performing on arena stage, energetic dancing, colourful lights, confetti falling",
    "ukgarage":      "UK garage MC performing, smooth confident movement, sleek urban setting, neon-lit night",
    "ukstreetsoul":  "soul singer performing smoothly, expressive hand gestures, warm golden lighting, urban backdrop",
    "classical":     "classical musician performing, precise graceful movement, concert hall, elegant conducting gestures",
    "indie":         "indie guitarist playing, relaxed natural movement, warm stage lighting, authentic performance",
    "techno":        "DJ performing at techno club, hands on decks, dark industrial setting, intense focused energy",
    "technhouse":    "tech house DJ mixing, smooth confident movement, underground club, cool atmospheric lighting",
    "hyperpop":      "hyperpop performer, energetic chaotic movement, neon lights, glitchy effects, youthful intense energy",
    "afrobeats":     "afrobeats performer dancing joyfully, rhythmic fluid movement, warm vibrant lighting, celebratory energy",
    "amapiano":      "amapiano DJ performing smoothly, confident fluid movement, warm golden lighting, sophisticated energy",
    "driftphonk":    "phonk performer, intense aggressive movement, dark red lighting, high energy drift culture vibes",
    "jerseyclub":    "Jersey Club DJ mixing, rapid energetic movement, bright club lights, high energy dance floor vibes",
    "afroswing":     "afroswing singer performing smoothly, relaxed romantic movement, warm golden lighting, stylish urban setting",
    "rastadub":      "rasta dub musician performing spiritually, slow rhythmic movement, warm golden lighting, dreadlocks moving gently, peaceful powerful energy",
    "deeprotbassline": "UK bassline DJ mixing, hands on decks, intense focused energy, dark club lighting, heavy bass atmosphere",
    "jazz":            "jazz saxophonist playing expressively, swaying with the music, warm amber club lighting, smooth sophisticated movement, fingers moving on keys",
    "electronicfunk":  "electronic funk performer dancing groovily, robotic funky movement, warm purple neon lighting, infectious rhythm energy",
    "syntheticpop":    "synthetic pop performer dancing energetically, precise choreographed movement, bright pink and blue neon lights, glamorous high energy performance",
    "ragga":           "ragga MC performing energetically, aggressive dancehall movement, tropical warm lighting, high energy Caribbean performance",
    "dubstep":         "dubstep DJ performing, intense head nodding, dark blue purple lighting, massive bass drop energy",
    "bhangra":         "bhangra dancer performing energetically, traditional arm movements, vibrant colourful lighting, joyful celebration energy",
    "rockney":         "rockney musician performing cheerfully, pub singalong energy, warm amber pub lighting, cheeky energetic performance",
    "metal":           "metal guitarist shredding intensely, headbanging dramatic movement, dark red stage lighting, fierce powerful energy",
    "reggaeton":       "reggaeton performer dancing energetically, perreo movement, warm tropical neon lighting, confident Latin urban energy",
    "latintrap":       "Latin trap performer moving intensely, dark moody movement, blue purple neon lighting, brooding urban Latin energy",
    "rootsreggae":    "roots reggae musician performing peacefully, gentle swaying movement, warm golden sunset lighting, spiritual conscious energy",
}

APIFRAME_API_KEY = os.environ["APIFRAME_API_KEY"]
APIFRAME_BASE = "https://api.apiframe.ai"
WEBHOOK_URL = os.environ["SONG_WEBHOOK_URL"].strip().rstrip("/")
EXPECTED_PRODUCTION_WEBHOOK_URL = "https://zeusaidesign.com/webhooks/apiframe"
if WEBHOOK_URL != EXPECTED_PRODUCTION_WEBHOOK_URL:
    logger.warning("SONG_WEBHOOK_URL is %r; production should be %r", WEBHOOK_URL, EXPECTED_PRODUCTION_WEBHOOK_URL)

DIRECT_ARTIST_STYLE_MAP = {
    "drake": "melodic rap, emotional vocals, atmospheric trap drums, late night mood, polished hip-hop production",
    "travis scott": "psychedelic trap, atmospheric synths, heavy 808 drums, spacious ad-libs, dark festival energy",
    "billie eilish": "intimate whisper vocals, minimalist dark pop, sub bass, eerie atmosphere, sparse percussion",
    "taylor swift": "confessional pop songwriting, bright melodic hooks, polished pop production, emotional storytelling",
    "the weeknd": "dark synth pop, falsetto vocals, nocturnal R&B, pulsing drums, cinematic atmosphere",
    "rihanna": "island-influenced pop, confident vocals, dancehall rhythm, glossy R&B production",
    "beyonce": "powerful R&B vocals, layered harmonies, dynamic pop production, danceable groove",
    "kendrick lamar": "conscious rap, intricate flow, jazz-influenced hip-hop, dramatic storytelling",
    "post malone": "melodic trap-pop, raspy vocals, guitar textures, laid back drums",
    "ariana grande": "airy pop vocals, agile runs, glossy R&B-pop production, stacked harmonies",
}

UNSAFE_INSPIRATION_PATTERNS = (
    r"\blike\s+([A-Z][\w'.-]+(?:\s+[A-Z][\w'.-]+){0,3})",
    r"\binspired\s+by\s+([A-Z][\w'.-]+(?:\s+[A-Z][\w'.-]+){0,3})",
    r"\bin\s+the\s+style\s+of\s+([A-Z][\w'.-]+(?:\s+[A-Z][\w'.-]+){0,3})",
    r"\bsimilar\s+to\s+([A-Z][\w'.-]+(?:\s+[A-Z][\w'.-]+){0,3})",
    r"\ba\s+la\s+([A-Z][\w'.-]+(?:\s+[A-Z][\w'.-]+){0,3})",
)


def sanitize_inspired_by_descriptors(raw: str | None) -> str | None:
    """Convert user inspiration text into Suno-safe style descriptors."""
    if not raw:
        return None

    text = raw.strip()
    if not text:
        return None

    descriptor_parts: list[str] = []
    lower_text = text.lower()
    for artist, descriptors in DIRECT_ARTIST_STYLE_MAP.items():
        if artist in lower_text:
            descriptor_parts.append(descriptors)

    scrubbed = text
    for pattern in UNSAFE_INSPIRATION_PATTERNS:
        scrubbed = re.sub(pattern, "", scrubbed, flags=re.IGNORECASE)

    for artist in DIRECT_ARTIST_STYLE_MAP:
        scrubbed = re.sub(rf"\b{re.escape(artist)}\b", "", scrubbed, flags=re.IGNORECASE)

    scrubbed = re.sub(r"\b(like|inspired by|style of|similar to|a la)\b", "", scrubbed, flags=re.IGNORECASE)
    scrubbed = re.sub(r"\s+", " ", scrubbed)

    for part in re.split(r"[,;\n]+", scrubbed):
        part = part.strip(" .:-")
        if not part:
            continue
        if re.search(r"\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)+\b", part):
            continue
        descriptor_parts.append(part)

    if not descriptor_parts:
        descriptor_parts.append("contemporary pop songwriting, polished production, expressive vocals")

    seen: set[str] = set()
    safe_parts: list[str] = []
    for part in descriptor_parts:
        for item in [p.strip(" .:-") for p in part.split(",")]:
            if not item:
                continue
            key = item.lower()
            if key in seen:
                continue
            seen.add(key)
            safe_parts.append(item)

    return ", ".join(safe_parts)[:500] or None


def _dj_transition_style(style_a: str, style_b: str) -> str:
    """Build a Suno section-tag style string that switches genre per section."""
    return (
        f"[intro: {style_a}] "
        f"[verse: {style_a}] "
        f"[chorus: {style_b}] "
        f"[verse: {style_a}] "
        f"[bridge: {style_b}] "
        f"[outro: {style_b}] "
        "genre switch DJ mix, section by section genre change, not blended, alternating genres per section"
    )[:1000]


class InsufficientCreditsError(Exception):
    """Raised when a user does not have enough song credits."""


def _check_and_deduct_credit(cur, user_id, is_admin: bool = False) -> None:
    if is_admin:
        return
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
    extra_suno_params: dict | None = None,
    is_admin: bool = False,
    animate_cover: bool = True,
    suno_model: str = "V5",
) -> dict:
    """
    Submit a song generation job to Apiframe v2.
    Costs 1 song credit (1 credit = 11 Apiframe credits = 1 finished track).
    Returns immediately with variant_id; the actual MP3 arrives later via webhook.
    Admin users bypass credit check entirely.
    """
    conn = sqlite3.connect(db_path)
    try:
        cur = conn.cursor()
        _check_and_deduct_credit(cur, user_id, is_admin=is_admin)

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
               (lyric_id, user_id, style_prompt, genre_tag, status, take_number, animate_cover)
               VALUES (?, ?, ?, ?, 'pending', 1, ?)""",
            (lyric_id, user_id, style_prompt, genre_tag, 1 if animate_cover else 0),
        )
        variant_id = cur.lastrowid
        conn.commit()
    except InsufficientCreditsError:
        conn.close()
        raise

    logger.info(
        "SONG_VARIANT_CREATED variant_id=%d lyric_id=%d user_id=%s genre=%r — webhook will fire to ?variant_id=%d",
        variant_id, lyric_id, user_id, genre_tag, variant_id,
    )
    logger.info(
        "APIFRAME_V2_SUBMIT api_key_configured=%s key_len=%d variant_id=%d webhook_url=%r",
        bool(APIFRAME_API_KEY),
        len(APIFRAME_API_KEY),
        variant_id,
        WEBHOOK_URL,
    )
    logger.info(
        "APIFRAME_V2_PAYLOAD variant_id=%d genre=%r style_len=%d lyrics_len=%d extra_params=%r",
        variant_id, genre_tag, len(style_prompt), len(lyrics), extra_suno_params,
    )
    logger.info("APIFRAME_V2_STYLE variant_id=%d style=%r", variant_id, style_prompt[:600])
    logger.info("APIFRAME_V2_WEBHOOK_URL variant_id=%d url=%r", variant_id, f"{WEBHOOK_URL}?variant_id={variant_id}")

    try:
        _apiframe_payload = {
            "prompt": lyrics,
            "model": "suno",
            "webhookUrl": f"{WEBHOOK_URL}?variant_id={variant_id}",
            "webhookEvents": ["completed", "failed"],
            "sunoParams": {
                "custom_mode": True,
                "instrumental": False,
                "model_version": suno_model,
                "style": style_prompt[:1000],
                **(extra_suno_params or {}),
            },
        }
        _apiframe_headers = {
            "X-API-Key": APIFRAME_API_KEY,  # v2 uses X-API-Key, NOT Authorization
            "Content-Type": "application/json",
        }

        # Retry once on 504 or connection error
        for attempt in range(2):
            try:
                response = requests.post(
                    f"{APIFRAME_BASE}/v2/music/generate",
                    headers=_apiframe_headers,
                    json=_apiframe_payload,
                    timeout=30,
                )
                if response.status_code == 504 and attempt == 0:
                    logger.warning(
                        "Apiframe 504 timeout, retrying in 5s for variant_id=%d", variant_id
                    )
                    time.sleep(5)
                    continue
                break
            except Exception as conn_err:
                if attempt == 0:
                    logger.warning(
                        "Apiframe connection error (attempt 0), retrying in 5s for variant_id=%d: %s",
                        variant_id, conn_err,
                    )
                    time.sleep(5)
                    continue
                raise

        logger.info(
            "APIFRAME_V2_RESPONSE variant_id=%d status=%d body=%r",
            variant_id, response.status_code, response.text[:500],
        )

        if response.status_code == 504:
            raise ValueError(
                "Music generation is taking longer than usual — please try again in a moment"
            )

        response.raise_for_status()
        try:
            body = response.json()
        except Exception:
            logger.error(
                "Apiframe returned non-JSON response: %d %s",
                response.status_code, response.text[:200],
            )
            raise ValueError(f"Apiframe error: {response.status_code}")
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
        # Submission failed — refund credit (unless admin) and mark variant failed
        conn = sqlite3.connect(db_path)
        try:
            cur = conn.cursor()
            if not is_admin:
                _refund_credit(cur, user_id)
            cur.execute(
                "UPDATE song_variants SET status = 'failed' WHERE id = ?",
                (variant_id,),
            )
            conn.commit()
        finally:
            conn.close()
        if isinstance(exc, ValueError):
            raise  # propagate user-friendly message directly to the API layer
        raise RuntimeError(f"Music API submission failed: {exc}") from exc

    return {"variant_id": variant_id, "job_id": job_id, "status": "generating"}


def generate_multiple_variants(
    user_id,
    lyric_id: int,
    genres: list[str],
    db_path: str,
    extra_suno_params: dict | None = None,
    tempo_suffix: str | None = None,
    is_admin: bool = False,
    inspired_by_descriptors: str | None = None,
    animate_cover: bool = True,
    genre_b: str | None = None,
    blend_ratio: int | None = None,
) -> dict:
    """Generate the same lyrics in multiple genres. Costs len(genres) credits.
    Admin users bypass credit checks entirely."""
    from song_genres import GENRE_PRESETS

    valid_genres = [g for g in genres if g in GENRE_PRESETS]
    if not valid_genres:
        raise ValueError("No valid genres provided")
    if len(valid_genres) > 7:
        raise ValueError("Maximum 7 variants per request")

    if not is_admin:
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
        style = GENRE_PRESETS[genre]
        # Apply DJ-transition style for genre blend
        if genre_b and genre_b in GENRE_PRESETS:
            style = _dj_transition_style(style, GENRE_PRESETS[genre_b])
            logger.info("genre_blend: %s × %s DJ-transition style len=%d", genre, genre_b, len(style))
        if tempo_suffix:
            style = f"{style}, {tempo_suffix}"
        safe_inspired_by = sanitize_inspired_by_descriptors(inspired_by_descriptors)
        if safe_inspired_by:
            style = f"{style}, {safe_inspired_by}"
        style = f"{style}, {random.choice(RANDOM_PRODUCTION)}"
        # Genre tag encodes the blend so the frontend can display "Soul × Grime"
        genre_tag = f"{genre}__{genre_b}" if genre_b and genre_b in GENRE_PRESETS else genre
        suno_model = GENRE_MODEL_OVERRIDES.get(genre, GENRE_MODEL_OVERRIDES.get(genre_b or '', 'V5'))
        result = generate_song_variant(
            user_id=user_id,
            lyric_id=lyric_id,
            style_prompt=style,
            genre_tag=genre_tag,
            db_path=db_path,
            extra_suno_params=extra_suno_params,
            is_admin=is_admin,
            animate_cover=animate_cover,
            suno_model=suno_model,
        )
        variants.append({"genre": genre_tag, **result})

    return {"variants": variants, "count": len(variants)}
