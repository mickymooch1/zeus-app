"""image_generator.py — AI image generation via fal.ai Flux (polling mode)."""
import logging
import os
import pathlib
import subprocess
import tempfile
import uuid

import requests

log = logging.getLogger("zeus.image")

FAL_API_KEY = os.environ.get("FAL_API_KEY", "").strip()
FAL_BASE = "https://queue.fal.run"
FAL_MODEL = "fal-ai/flux/dev"
ZEUS_PUBLIC_URL = os.environ.get("ZEUS_PUBLIC_URL", "https://zeusaidesign.com")

_RATIO_TO_FAL_SIZE: dict[str, str] = {
    "1:1":  "square_1_1",
    "16:9": "landscape_16_9",
    "9:16": "portrait_9_16",
    "3:1":  "landscape_4_3",
}


def submit_image_generation(
    prompt: str,
    aspect_ratio: str,
    model: str = "flux",
    webhook_url: str = "",   # kept for caller compatibility, no longer used
) -> str:
    """Submit image generation to fal.ai. Returns local job_id."""
    if not FAL_API_KEY:
        raise ValueError("FAL_API_KEY is not configured")

    job_id = uuid.uuid4().hex
    image_size = _RATIO_TO_FAL_SIZE.get(aspect_ratio, "square_1_1")

    response = requests.post(
        f"{FAL_BASE}/{FAL_MODEL}",
        headers={"Authorization": f"Key {FAL_API_KEY}", "Content-Type": "application/json"},
        json={
            "prompt": prompt,
            "image_size": image_size,
            "num_images": 1,
            "enable_safety_checker": False,
        },
        timeout=30,
    )
    response.raise_for_status()
    data = response.json()
    request_id = data.get("request_id")
    if not request_id:
        raise RuntimeError(f"fal.ai response missing request_id: {data!r}")

    import db as _db
    _db.save_fal_image_job(_db.get_db_path(), job_id, request_id)
    log.info("submit_image_generation: job_id=%s request_id=%s size=%s", job_id, request_id, image_size)
    return job_id


def get_image_job_status(job_id: str) -> dict:
    """Poll fal.ai for status. Downloads and saves image when COMPLETED."""
    if not FAL_API_KEY:
        raise ValueError("FAL_API_KEY is not configured")

    # If already on disk, return immediately without hitting fal.ai
    dest = pathlib.Path("/data/images") / f"{job_id}.jpg"
    if dest.exists():
        return {"status": "COMPLETED", "image_url": f"{ZEUS_PUBLIC_URL}/files/images/{job_id}.jpg"}

    import db as _db
    request_id = _db.get_fal_request_id(_db.get_db_path(), job_id) or job_id
    headers = {"Authorization": f"Key {FAL_API_KEY}"}

    status_resp = requests.get(
        f"{FAL_BASE}/{FAL_MODEL}/requests/{request_id}/status",
        headers=headers,
        timeout=15,
    )
    status_resp.raise_for_status()
    status = status_resp.json().get("status", "").upper()
    log.info("get_image_job_status: job_id=%s request_id=%s status=%s", job_id, request_id, status)

    if status != "COMPLETED":
        return {"status": status, "image_url": None}

    result_resp = requests.get(
        f"{FAL_BASE}/{FAL_MODEL}/requests/{request_id}",
        headers=headers,
        timeout=15,
    )
    result_resp.raise_for_status()
    images = result_resp.json().get("images", [])
    if not images:
        log.warning("get_image_job_status: COMPLETED but no images for job_id=%s", job_id)
        return {"status": "COMPLETED", "image_url": None}

    entry = images[0]
    cdn_url = entry["url"] if isinstance(entry, dict) else entry
    public_url = download_and_save_image(job_id, cdn_url)
    return {"status": "COMPLETED", "image_url": public_url}


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
