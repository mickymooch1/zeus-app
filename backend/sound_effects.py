"""sound_effects.py — pure ambient sound generation via ElevenLabs Sound Effects.

Suno adds music to everything, so the nature-sound genres (rain, whale song,
fireplace) bypass Suno/Apiframe entirely and use ElevenLabs' sound-generation
endpoint, then loop the clip up to full length.

ElevenLabs sound-generation caps at 30s per call, so we request a smoothly
loopable 30s clip and loop it to ~3 minutes with ffmpeg.
Endpoint: POST https://api.elevenlabs.io/v1/sound-generation  (xi-api-key header)
"""
import logging
import os
import subprocess
import tempfile

import requests

logger = logging.getLogger("zeus.sound_effects")

# Rich, layered sound-only prompts (the Suno style strings are music-oriented;
# ElevenLabs wants a detailed description of the FULL soundscape — one element per
# comma so it layers thunder + birds + wind etc rather than a single flat texture).
SFX_PROMPTS = {
    # Concise + open-ended: ElevenLabs fills in natural variety (esp. birds) better
    # from a short prompt than an over-prescriptive one. Keep it under ~50 words.
    "naturesounds":  "peaceful nature soundscape, gentle rainfall, birds chirping, distant rolling thunder, wind through trees",
    "cracklingfire": "wood crackling and popping in a stone fireplace, occasional log shift, fire hissing, embers glowing, warm hearth sounds, cosy indoor winter atmosphere, no music",
    "whalesong":     "humpback whale long mournful calls, deep underwater ocean ambience, distant whale song echoing, bubbles rising, deep ocean pressure, ethereal whale communication, no music",
    "thunderstorm":  "heavy driving rainfall, frequent loud thunder cracks and long rolling thunder rumbles, storm wind gusting, rain hammering on rooftops and puddles, powerful dramatic thunderstorm soundscape, no music",
    "oceanwaves":    "ocean waves rolling and crashing onto a sandy beach, gentle tide washing in and out, distant seagulls calling, soft sea breeze, coastal shoreline ambience, no music",
    "forest":        "dense forest ambience, many birds chirping and singing, wind rustling through leaves and branches, a babbling stream nearby, insects buzzing, peaceful woodland soundscape, no music",
    "nightsounds":   "peaceful night-time countryside ambience, crickets chirping steadily, occasional owl hooting, gentle warm breeze, distant rustling leaves, calm nocturnal soundscape, no music",
}

# Genres routed to ElevenLabs SFX instead of Suno.
SFX_GENRES = frozenset(SFX_PROMPTS.keys())

_ELEVEN_SFX_URL = "https://api.elevenlabs.io/v1/sound-generation"
_CLIP_SECONDS = 30       # ElevenLabs max per generation (v2)
_TARGET_SECONDS = 180    # loop up to ~3 minutes


def sfx_prompt(genre: str, brief: str = "") -> str:
    return SFX_PROMPTS.get(genre) or (brief.strip() if brief and brief.strip()
                                      else "calming ambient environmental sound, no music, no instruments")


def generate_looped_sfx(genre: str, brief: str, out_path: str) -> int:
    """Generate a full-length looped ambient track for an SFX genre and write it to
    out_path (mp3). Returns the duration in seconds. Raises on failure so the caller
    can refund the credit and mark the variant failed."""
    api_key = os.environ.get("ELEVENLABS_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("ELEVENLABS_API_KEY not set — cannot generate sound effects")
    prompt = sfx_prompt(genre, brief)
    logger.info("SFX generate: genre=%r prompt=%r", genre, prompt[:140])
    resp = requests.post(
        _ELEVEN_SFX_URL,
        headers={"xi-api-key": api_key, "Content-Type": "application/json"},
        json={
            "text": prompt,
            "duration_seconds": _CLIP_SECONDS,
            # Higher prompt_influence → follows the detailed multi-element description
            # more closely (richer layered soundscape). No "loop" — it flattens variety;
            # the ffmpeg acrossfade below handles seamless looping instead.
            "prompt_influence": 0.7,
            "model_id": "eleven_text_to_sound_v2",
        },
        timeout=120,
    )
    if resp.status_code != 200:
        # Surface plan/permission issues clearly (403 = not on plan, 401 = bad key).
        raise RuntimeError(f"ElevenLabs sound-generation HTTP {resp.status_code}: {resp.text[:300]}")
    if len(resp.content) < 5000:
        raise RuntimeError(f"ElevenLabs sound-generation returned tiny payload ({len(resp.content)} bytes)")

    # DEBUG: save the RAW 30s ElevenLabs clip (BEFORE any ffmpeg looping) next to the
    # output so we can listen and tell whether the drone is baked into ElevenLabs' audio
    # or introduced by the loop. Served at {SONG_PUBLIC_BASE_URL}/<name>_raw.mp3.
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    raw_path = (out_path[:-4] if out_path.endswith(".mp3") else out_path) + "_raw.mp3"
    try:
        with open(raw_path, "wb") as rf:
            rf.write(resp.content)
        _pub = os.environ.get("SONG_PUBLIC_BASE_URL", "").rstrip("/")
        logger.info("SFX RAW clip (pre-loop) saved: %s  →  %s/%s  (%d bytes) — listen to check for baked-in drone",
                    raw_path, _pub, os.path.basename(raw_path), len(resp.content))
    except Exception:
        logger.exception("SFX: failed to save raw debug clip")

    tmp = None
    try:
        with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as fh:
            fh.write(resp.content)
            tmp = fh.name
        os.makedirs(os.path.dirname(out_path), exist_ok=True)
        # Loop to target length with a 1s CROSSFADE at every join (acrossfade) so there
        # is no click/drone at the loop point. A hard -stream_loop leaves an audible seam
        # because the clip's end doesn't match its start; a plain afade only softens the
        # overall start/end, not the internal joins. We overlap-blend N copies instead.
        n_copies = (_TARGET_SECONDS // _CLIP_SECONDS) + 2  # enough to exceed target, then -t trims
        inputs = []
        for _ in range(n_copies):
            inputs += ["-i", tmp]
        prev = "[0]"
        filt = ""
        for i in range(1, n_copies):
            lbl = f"[a{i}]"
            filt += f"{prev}[{i}]acrossfade=d=1:c1=tri:c2=tri{lbl};"
            prev = lbl
        filt = filt.rstrip(";")
        subprocess.run(
            ["ffmpeg", "-y", *inputs, "-filter_complex", filt, "-map", prev,
             "-t", str(_TARGET_SECONDS), "-c:a", "libmp3lame", "-b:a", "192k", out_path],
            check=True, capture_output=True,
        )
    finally:
        if tmp and os.path.exists(tmp):
            os.unlink(tmp)
    logger.info("SFX generate: genre=%r looped to %ds → %s", genre, _TARGET_SECONDS, out_path)
    return _TARGET_SECONDS
