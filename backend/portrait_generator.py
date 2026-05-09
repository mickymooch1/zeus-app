"""portrait_generator.py — AI performer portrait generation via Apiframe."""
import logging
import os

import requests

log = logging.getLogger("zeus.portrait")

APIFRAME_API_KEY = os.environ.get("APIFRAME_API_KEY", "").strip()
APIFRAME_BASE = "https://api.apiframe.ai"

GENRE_PORTRAIT_PROMPTS = {
    "blues":     "Professional portrait photo, blues musician, clear frontal face, warm amber lighting, vintage microphone, photorealistic, film grain",
    "soul":      "Professional portrait photo, soul singer, clear frontal face, warm Motown studio lighting, expressive, photorealistic",
    "rnb":       "Professional portrait photo, R&B artist, clear frontal face, modern studio lighting, confident expression, photorealistic",
    "country":   "Professional portrait photo, country musician, clear frontal face, golden hour lighting, authentic look, photorealistic",
    "reggae":    "Professional portrait photo, reggae musician, clear frontal face, warm tropical lighting, relaxed expression, photorealistic",
    "pop":       "Professional portrait photo, pop artist, clear frontal face, clean studio lighting, polished look, photorealistic",
    "rock":      "Professional portrait photo, rock musician, clear frontal face, dramatic lighting, confident expression, photorealistic",
    "hiphop":    "Professional portrait photo, hip-hop artist, clear frontal face, urban studio lighting, authentic, photorealistic",
    "lofi":      "Professional portrait photo, indie musician, clear frontal face, soft warm lighting, relaxed aesthetic, photorealistic",
    "edm":       "Professional portrait photo, EDM producer, clear frontal face, colorful dramatic lighting, energetic, photorealistic",
    "acoustic":  "Professional portrait photo, acoustic singer, clear frontal face, warm natural lighting, intimate, photorealistic",
    "irishjig":  "Professional portrait photo, Irish musician, clear frontal face, warm pub lighting, authentic, photorealistic",
    "irishfolk":   "Professional portrait photo, Irish folk singer, clear frontal face, firelight ambiance, soulful, photorealistic",
    "bluessoul":   "Professional portrait photo, blues soul musician, clear frontal face, warm amber studio lighting, emotional expression, photorealistic",
    "drumandbass": "Professional portrait photo, drum and bass DJ and producer, clear frontal face, dramatic purple and blue studio lighting, intense expression, photorealistic",
}

_FALLBACK_PROMPT = "Professional portrait photo, musician, clear frontal face, studio lighting, photorealistic"



def submit_portrait_generation(genre: str, gender: str, webhook_url: str) -> str:
    """Submit portrait generation to Apiframe. Returns job_id."""
    if not APIFRAME_API_KEY:
        raise ValueError("APIFRAME_API_KEY is not configured")

    base_prompt = GENRE_PORTRAIT_PROMPTS.get(genre, _FALLBACK_PROMPT)
    gender_prefix = "male" if gender == "m" else "female"
    prompt = f"{gender_prefix} {base_prompt}, face fills frame, suitable for video lip-sync"

    log.info("submit_portrait_generation: genre=%s gender=%s", genre, gender)

    response = requests.post(
        f"{APIFRAME_BASE}/v2/images/generate",
        headers={"X-API-Key": APIFRAME_API_KEY, "Content-Type": "application/json"},
        json={
            "prompt": prompt,
            "model": "gpt-image-2",
            "webhookUrl": webhook_url,
            "webhookEvents": ["completed", "failed"],
        },
        timeout=30,
    )
    response.raise_for_status()
    body = response.json()
    log.info("submit_portrait_generation: raw response=%r", str(body)[:200])

    job_id = body.get("jobId")
    if not job_id:
        raise RuntimeError(f"Apiframe image response missing jobId: {body!r}")

    log.info("submit_portrait_generation: job_id=%s", job_id)
    return job_id


def get_portrait_job_status(job_id: str) -> dict:
    """Poll Apiframe for portrait job status. Returns {status, image_url}."""
    if not APIFRAME_API_KEY:
        raise ValueError("APIFRAME_API_KEY is not configured")

    resp = requests.get(
        f"{APIFRAME_BASE}/v2/jobs/{job_id}",
        headers={"X-API-Key": APIFRAME_API_KEY},
        timeout=15,
    )
    resp.raise_for_status()
    data = resp.json()
    status = data.get("status", "unknown")

    log.info("get_portrait_job_status: job_id=%s status=%s", job_id, status)

    if status == "completed":
        result = data.get("result") or {}
        images = result.get("images", [])
        image_url = images[0] if images else None
    else:
        image_url = None

    log.info(f"Returning to frontend: image_url={image_url}")
    return {"status": status, "image_url": image_url}
