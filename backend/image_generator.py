"""image_generator.py — AI image generation via fal.ai Flux (synchronous mode)."""
import logging
import os
import pathlib
import subprocess
import tempfile
import uuid

import requests

log = logging.getLogger("zeus.image")

FAL_API_KEY = os.environ.get("FAL_API_KEY", "").strip()
FAL_SYNC_BASE = "https://fal.run"
FAL_MODEL = "fal-ai/flux/dev"
ZEUS_PUBLIC_URL = os.environ.get("ZEUS_PUBLIC_URL", "https://zeusaidesign.com")

_RATIO_TO_FAL_SIZE: dict[str, str] = {
    "1:1":  "square_hd",
    "16:9": "landscape_16_9",
    "9:16": "portrait_9_16",
    "3:1":  "landscape_4_3",
}


def submit_image_generation(
    prompt: str,
    aspect_ratio: str,
    model: str = "flux",
    webhook_url: str = "",  # kept for caller compatibility, no longer used
) -> str:
    """Generate an image synchronously via fal.ai. Downloads and returns public URL."""
    if not FAL_API_KEY:
        raise ValueError("FAL_API_KEY is not configured")

    job_id = uuid.uuid4().hex
    image_size = _RATIO_TO_FAL_SIZE.get(aspect_ratio, "square_1_1")

    log.info("submit_image_generation: job_id=%s size=%s", job_id, image_size)
    response = requests.post(
        f"{FAL_SYNC_BASE}/{FAL_MODEL}",
        headers={"Authorization": f"Key {FAL_API_KEY}"},
        json={
            "prompt": prompt,
            "image_size": image_size,
            "num_images": 1,
        },
        timeout=120,
    )
    if not response.ok:
        log.error("fal.ai sync error %d: %s", response.status_code, response.text[:500])
    response.raise_for_status()
    data = response.json()
    images = data.get("images", [])
    if not images:
        raise RuntimeError(f"fal.ai response missing images: {data!r}")

    entry = images[0]
    cdn_url = entry["url"] if isinstance(entry, dict) else entry
    public_url = download_and_save_image(job_id, cdn_url)
    log.info("submit_image_generation: completed job_id=%s → %s", job_id, public_url)
    return public_url


def get_image_job_status(job_id: str) -> dict:
    """Return status for a generated image. Images are now generated synchronously."""
    dest = pathlib.Path("/data/images") / f"{job_id}.jpg"
    if dest.exists():
        return {"status": "COMPLETED", "image_url": f"{ZEUS_PUBLIC_URL}/files/images/{job_id}.jpg"}
    return {"status": "NOT_FOUND", "image_url": None}


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
