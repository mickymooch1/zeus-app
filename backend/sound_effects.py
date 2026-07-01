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

# Genres routed to ElevenLabs SFX instead of Suno.
SFX_GENRES = frozenset({"naturesounds", "whalesong", "cracklingfire"})

# Clean sound-only prompts (the Suno style strings are music-oriented; ElevenLabs
# wants a plain description of the sound).
SFX_PROMPTS = {
    "naturesounds":  "steady gentle rainfall with distant rolling thunder, forest birds and soft wind through trees, calming natural ambience, no music, no instruments",
    "whalesong":     "humpback whale song calls with deep underwater ocean ambience, gentle currents, no music, no instruments",
    "cracklingfire": "a cosy crackling wood fireplace, fire gently popping and crackling, warm hearth ambience, no music, no instruments",
}

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
            "prompt_influence": 0.5,
            "loop": True,
            "model_id": "eleven_text_to_sound_v2",
        },
        timeout=120,
    )
    if resp.status_code != 200:
        # Surface plan/permission issues clearly (403 = not on plan, 401 = bad key).
        raise RuntimeError(f"ElevenLabs sound-generation HTTP {resp.status_code}: {resp.text[:300]}")
    if len(resp.content) < 5000:
        raise RuntimeError(f"ElevenLabs sound-generation returned tiny payload ({len(resp.content)} bytes)")

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
