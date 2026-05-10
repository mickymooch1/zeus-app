"""image_generator.py — AI image generation via Apiframe Flux."""
import logging
import os
import pathlib
import subprocess
import tempfile

import requests

log = logging.getLogger("zeus.image")

APIFRAME_API_KEY = os.environ.get("APIFRAME_API_KEY", "").strip()
APIFRAME_BASE = "https://api.apiframe.ai"
ZEUS_PUBLIC_URL = os.environ.get("ZEUS_PUBLIC_URL", "https://zeusaidesign.com")


def submit_image_generation(
    prompt: str,
    aspect_ratio: str,
    model: str = "flux",
    webhook_url: str = "",
) -> str:
    """Submit image generation to Apiframe. Returns job_id."""
    if not APIFRAME_API_KEY:
        raise ValueError("APIFRAME_API_KEY is not configured")

    body: dict = {
        "prompt": prompt,
        "model": model,
        "aspectRatio": aspect_ratio,
    }
    if webhook_url:
        body["webhookUrl"] = webhook_url
        body["webhookEvents"] = ["completed", "failed"]

    response = requests.post(
        f"{APIFRAME_BASE}/v2/images/generate",
        headers={"X-API-Key": APIFRAME_API_KEY, "Content-Type": "application/json"},
        json=body,
        timeout=30,
    )
    response.raise_for_status()
    data = response.json()
    job_id = data.get("jobId")
    if not job_id:
        raise RuntimeError(f"Apiframe response missing jobId: {data!r}")
    log.info("submit_image_generation: job_id=%s model=%s ratio=%s", job_id, model, aspect_ratio)
    return job_id


def get_image_job_status(job_id: str) -> dict:
    """Poll Apiframe for image job status. Returns {status, image_url}."""
    if not APIFRAME_API_KEY:
        raise ValueError("APIFRAME_API_KEY is not configured")

    response = requests.get(
        f"{APIFRAME_BASE}/v2/jobs/{job_id}",
        headers={"X-API-Key": APIFRAME_API_KEY},
        timeout=15,
    )
    response.raise_for_status()
    data = response.json()
    status = data.get("status", "").upper()
    image_url = None
    if status == "COMPLETED":
        result = data.get("result") or {}
        images = result.get("images", [])
        image_url = images[0] if images else None
    return {"status": status, "image_url": image_url}


def download_and_save_image(job_id: str, image_url: str) -> str:
    """Download image_url, save to /data/images/{job_id}.jpg, return public URL."""
    images_dir = pathlib.Path("/data/images")
    images_dir.mkdir(parents=True, exist_ok=True)
    dest = images_dir / f"{job_id}.jpg"

    resp = requests.get(image_url, timeout=30)
    resp.raise_for_status()

    if image_url.lower().endswith(".webp"):
        tmp_path = None
        try:
            with tempfile.NamedTemporaryFile(suffix=".webp", delete=False) as tmp:
                tmp.write(resp.content)
                tmp_path = tmp.name
            subprocess.run(
                ["ffmpeg", "-i", tmp_path, "-q:v", "2", "-y", str(dest)],
                check=True,
                capture_output=True,
            )
        finally:
            if tmp_path and pathlib.Path(tmp_path).exists():
                pathlib.Path(tmp_path).unlink()
    else:
        dest.write_bytes(resp.content)

    log.info("download_and_save_image: saved %s", dest)
    return f"{ZEUS_PUBLIC_URL}/files/images/{job_id}.jpg"
