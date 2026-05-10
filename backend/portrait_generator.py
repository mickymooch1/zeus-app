"""portrait_generator.py — AI performer portrait generation via Apiframe."""
import logging
import os
import subprocess
import tempfile

import requests

log = logging.getLogger("zeus.portrait")

APIFRAME_API_KEY = os.environ.get("APIFRAME_API_KEY", "").strip()
APIFRAME_BASE = "https://api.apiframe.ai"
ZEUS_PUBLIC_URL = os.environ.get("ZEUS_PUBLIC_URL", "https://zeusaidesign.com")

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
    "grime":       "Professional portrait photo, grime MC, clear frontal face, dramatic urban studio lighting, intense focused expression, photorealistic",
}

_FALLBACK_PROMPT = "Professional portrait photo, musician, clear frontal face, studio lighting, photorealistic"


def _extract_image_url(payload: dict) -> str | None:
    result = payload.get("result") or {}
    images = result.get("images", [])
    return images[0] if images else None


def _convert_webp_to_jpeg(webp_url: str, job_id: str) -> str:
    """Download a WebP URL, convert to JPEG via ffmpeg, return local /files/avatars URL."""
    os.makedirs("/data/avatars", exist_ok=True)
    webp_tmp = None
    try:
        resp = requests.get(webp_url, timeout=30)
        resp.raise_for_status()
        with tempfile.NamedTemporaryFile(suffix=".webp", delete=False) as tmp:
            tmp.write(resp.content)
            webp_tmp = tmp.name
        jpeg_path = f"/data/avatars/{job_id}.jpg"
        subprocess.run(
            ["ffmpeg", "-i", webp_tmp, "-q:v", "2", "-y", jpeg_path],
            check=True,
            capture_output=True,
        )
        log.info("_convert_webp_to_jpeg: saved %s", jpeg_path)
        return f"{ZEUS_PUBLIC_URL}/files/avatars/{job_id}.jpg"
    finally:
        if webp_tmp and os.path.exists(webp_tmp):
            os.unlink(webp_tmp)


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
    status_lower = status.lower() if isinstance(status, str) else status

    log.info("get_portrait_job_status: job_id=%s status=%r", job_id, status)

    image_url = _extract_image_url(data) if status_lower == "completed" else None

    if image_url and image_url.lower().endswith(".webp"):
        log.info("get_portrait_job_status: converting WebP to JPEG for job %s", job_id)
        try:
            image_url = _convert_webp_to_jpeg(image_url, job_id)
        except Exception as exc:
            log.warning("get_portrait_job_status: WebP conversion failed: %s — using original URL", exc)

    log.info(f"Returning to frontend: image_url={image_url}")
    return {"status": status_lower, "image_url": image_url}
