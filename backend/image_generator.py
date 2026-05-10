"""image_generator.py — AI image generation via fal.ai Flux (polling mode)."""
import logging
import os
import pathlib
import subprocess
import tempfile
import uuid
from datetime import datetime, timezone, timedelta

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
    # fal.ai returns 4xx on /status once a job completes and the queue slot is
    # cleaned up. Fall through to the result URL before declaring it expired.
    if status_resp.status_code in (404, 405, 410):
        log.info(
            "get_image_job_status: job_id=%s request_id=%s HTTP %d — trying result URL",
            job_id, request_id, status_resp.status_code,
        )
        result_resp = requests.get(
            f"{FAL_BASE}/{FAL_MODEL}/requests/{request_id}",
            headers=headers,
            timeout=15,
        )
        if result_resp.status_code in (404, 405, 410):
            log.warning(
                "get_image_job_status: job_id=%s result also %d — expired",
                job_id, result_resp.status_code,
            )
            return {"status": "EXPIRED", "image_url": None}
        result_resp.raise_for_status()
        images = result_resp.json().get("images", [])
        if not images:
            log.warning("get_image_job_status: result URL returned no images for job_id=%s", job_id)
            return {"status": "EXPIRED", "image_url": None}
        entry = images[0]
        cdn_url = entry["url"] if isinstance(entry, dict) else entry
        public_url = download_and_save_image(job_id, cdn_url)
        log.info("get_image_job_status: recovered via result URL job_id=%s → %s", job_id, public_url)
        return {"status": "COMPLETED", "image_url": public_url}

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


def process_pending_image_jobs() -> None:
    """Poll fal.ai for every job with no image_url yet; download when COMPLETED."""
    if not FAL_API_KEY:
        log.warning("process_pending_image_jobs: FAL_API_KEY not set — skipping")
        return

    import db as _db
    db_path = _db.get_db_path()
    pending = _db.get_pending_fal_image_jobs(db_path)
    log.info(f"image_poller: found {len(pending)} pending jobs")
    if not pending:
        return
    headers = {"Authorization": f"Key {FAL_API_KEY}"}

    for row in pending:
        job_id = row["job_id"]
        request_id = row["fal_request_id"]
        try:
            status_url = f"{FAL_BASE}/{FAL_MODEL}/requests/{request_id}/status"
            result_url = f"{FAL_BASE}/{FAL_MODEL}/requests/{request_id}"
            log.info(f"Trying status URL: {status_url}")
            status_resp = requests.get(status_url, headers=headers, timeout=15)
            if status_resp.status_code in (404, 405, 410):
                # fal.ai returns 4xx on /status once a job finishes and the queue
                # slot is cleaned up — but the result URL may still work.
                log.info(
                    "process_pending_image_jobs: job_id=%s /status HTTP %d — trying result URL",
                    job_id, status_resp.status_code,
                )
                log.info(f"Trying result URL: {result_url}")
                result_resp = requests.get(result_url, headers=headers, timeout=15)
                if result_resp.status_code in (404, 405, 410):
                    created_at_str = row.get("created_at", "")
                    try:
                        created_at = datetime.fromisoformat(created_at_str).replace(tzinfo=timezone.utc)
                        age = datetime.now(timezone.utc) - created_at
                    except Exception:
                        age = timedelta(minutes=10)  # unknown age → treat as old
                    if age < timedelta(minutes=5):
                        log.info(
                            "process_pending_image_jobs: job_id=%s too young (%ds), will retry",
                            job_id, int(age.total_seconds()),
                        )
                        continue
                    log.warning(
                        "process_pending_image_jobs: job_id=%s result also %d and >5 min old — marking expired",
                        job_id, result_resp.status_code,
                    )
                    _db.update_fal_image_job_url(db_path, job_id, "EXPIRED")
                    continue
                result_resp.raise_for_status()
                images = result_resp.json().get("images", [])
                if not images:
                    log.warning("process_pending_image_jobs: job_id=%s result URL returned no images — marking expired", job_id)
                    _db.update_fal_image_job_url(db_path, job_id, "EXPIRED")
                    continue
                entry = images[0]
                cdn_url = entry["url"] if isinstance(entry, dict) else entry
                public_url = download_and_save_image(job_id, cdn_url)
                _db.update_fal_image_job_url(db_path, job_id, public_url)
                log.info("process_pending_image_jobs: recovered via result URL job_id=%s → %s", job_id, public_url)
                continue

            status_resp.raise_for_status()
            status = status_resp.json().get("status", "").upper()

            if status != "COMPLETED":
                log.debug("process_pending_image_jobs: job_id=%s status=%s", job_id, status)
                continue

            log.info(f"Trying result URL: {result_url}")
            result_resp = requests.get(result_url, headers=headers, timeout=15)
            result_resp.raise_for_status()
            images = result_resp.json().get("images", [])
            if not images:
                log.warning("process_pending_image_jobs: COMPLETED but no images for job_id=%s", job_id)
                continue

            entry = images[0]
            cdn_url = entry["url"] if isinstance(entry, dict) else entry
            public_url = download_and_save_image(job_id, cdn_url)
            _db.update_fal_image_job_url(db_path, job_id, public_url)
            log.info("process_pending_image_jobs: saved job_id=%s → %s", job_id, public_url)

        except Exception:
            log.exception("process_pending_image_jobs: error processing job_id=%s", job_id)


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
