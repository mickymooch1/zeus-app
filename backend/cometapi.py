"""
cometapi.py — CometAPI client for persona-based song generation.

Used ONLY when the user has a sound_persona_id set (Your Sound feature).
Regular song generation continues to use Apiframe via songs.py.

Environment variables:
    COMETAPI_API_KEY      — CometAPI bearer token (required for persona feature)
"""
import hashlib
import hmac as _hmac
import logging
import os

import requests

log = logging.getLogger("zeus.cometapi")

COMETAPI_BASE = "https://api.cometapi.com"
COMETAPI_API_KEY = os.environ.get("COMETAPI_API_KEY", "")
COMETAPI_WEBHOOK_SECRET = os.environ.get("COMETAPI_WEBHOOK_SECRET", "")


def _make_webhook_token(variant_id: int) -> str:
    """Generate a per-variant HMAC token for webhook authentication."""
    secret = (COMETAPI_WEBHOOK_SECRET or COMETAPI_API_KEY or "zeus-default-secret").encode()
    return _hmac.new(secret, str(variant_id).encode(), hashlib.sha256).hexdigest()[:32]


def verify_webhook_token(variant_id: int, token: str) -> bool:
    """Verify a webhook token for the given variant_id."""
    expected = _make_webhook_token(variant_id)
    return _hmac.compare_digest(expected, token)

_MV_MAP = {
    "V4_5": "chirp-auk",
    "V4_5PLUS": "chirp-bluejay",
    "V5": "chirp-crow",
    "V5_5": "chirp-fenix",
}


def _headers() -> dict:
    return {
        "Authorization": f"Bearer {COMETAPI_API_KEY}",
        "Content-Type": "application/json",
    }


def create_persona(mp3_url: str, title: str) -> str:
    """
    Create a CometAPI style persona from a finished song MP3.
    Returns the persona_id UUID string.

    ⚠️  VERIFY ENDPOINT BEFORE PRODUCTION USE:
    CometAPI's persona creation endpoint is behind their authenticated docs.
    Check https://apidoc.cometapi.com → search "persona" for the exact path.
    If the endpoint below is wrong, update the URL. The response parsing handles
    both {"data": "uuid"} and {"data": {"persona_id": "uuid"}} shapes.
    """
    if not COMETAPI_API_KEY:
        raise RuntimeError("COMETAPI_API_KEY not configured")
    resp = requests.post(
        f"{COMETAPI_BASE}/suno/submit/persona",
        headers=_headers(),
        json={"audio_url": mp3_url, "title": title},
        timeout=30,
    )
    if not resp.ok:
        log.error("create_persona: HTTP %d: %s", resp.status_code, resp.text[:500])
    resp.raise_for_status()
    data = resp.json()
    payload = data.get("data") or data
    if isinstance(payload, str):
        persona_id = payload
    elif isinstance(payload, dict):
        persona_id = payload.get("persona_id") or payload.get("id")
    else:
        persona_id = None
    if not persona_id:
        raise RuntimeError(f"CometAPI persona creation: no persona_id in response: {data!r}")
    log.info("create_persona: persona_id=%s title=%r mp3=%s", persona_id, title, mp3_url)
    return str(persona_id)


def generate_with_persona(
    variant_id: int,
    lyrics: str,
    style_prompt: str,
    persona_id: str,
    webhook_url: str,
    extra_suno_params: dict | None = None,
) -> str:
    """
    Submit a Suno generation to CometAPI with the user's style persona.
    Returns the CometAPI task_id string.
    Raises RuntimeError on API error; raises requests.HTTPError on HTTP failure.
    """
    if not COMETAPI_API_KEY:
        raise RuntimeError("COMETAPI_API_KEY not configured")

    mv = "chirp-fenix"
    vocal_gender = None
    if extra_suno_params:
        if "model_version" in extra_suno_params:
            mv = _MV_MAP.get(extra_suno_params["model_version"], "chirp-fenix")
        if "vocal_gender" in extra_suno_params:
            vocal_gender = extra_suno_params["vocal_gender"]

    body: dict = {
        "mv": mv,
        "prompt": lyrics,
        "tags": style_prompt[:200],
        "persona_id": persona_id,
        "task": "artist_consistency",
        "notify_hook": webhook_url,
        "generation_type": "TEXT",
    }
    if vocal_gender:
        body["vocal_gender"] = vocal_gender

    log.info(
        "generate_with_persona: variant_id=%d persona_id=%s mv=%s webhook=%s",
        variant_id, persona_id, mv, webhook_url,
    )
    resp = requests.post(
        f"{COMETAPI_BASE}/suno/submit/music",
        headers=_headers(),
        json=body,
        timeout=30,
    )
    if not resp.ok:
        log.error("generate_with_persona: HTTP %d: %s", resp.status_code, resp.text[:500])
    resp.raise_for_status()
    data = resp.json()
    payload = data.get("data") or data
    task_id = payload if isinstance(payload, str) else payload.get("task_id") if isinstance(payload, dict) else None
    if not task_id:
        raise RuntimeError(f"CometAPI generate_with_persona: no task_id in response: {data!r}")
    log.info("generate_with_persona: variant_id=%d → task_id=%s", variant_id, task_id)
    return str(task_id)
