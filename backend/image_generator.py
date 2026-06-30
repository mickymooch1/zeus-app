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


def _public_image_url(job_id: str, ext: str = "jpg") -> str:
    """Absolute, public-facing URL for a saved image/video — clickable and
    shareable everywhere, and loadable inline in an <img>/<video> tag (which
    can't send auth headers).

    Uses the PUBLIC ``/files/images`` static mount, NOT the authenticated
    ``/api/files/images`` endpoint — exactly how Zeus Beats serves song covers
    (public ``/files/songs/...``). Generated logos/images/cover art aren't
    private, so they're served like any other public asset."""
    return f"{ZEUS_PUBLIC_URL.rstrip('/')}/files/images/{job_id}.{ext}"

# Log API key presence at import time so Railway logs confirm configuration
if FAL_API_KEY:
    log.info("image_generator: FAL_API_KEY is set (len=%d)", len(FAL_API_KEY))
else:
    log.warning("image_generator: FAL_API_KEY is NOT set — image generation will fail")

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
        raise ValueError(
            "FAL_API_KEY is not set in Railway environment variables. "
            "Add it at: Railway → zeus-app service → Variables → FAL_API_KEY"
        )

    job_id = uuid.uuid4().hex
    image_size = _RATIO_TO_FAL_SIZE.get(aspect_ratio, "square_hd")

    url = f"{FAL_SYNC_BASE}/{FAL_MODEL}"
    log.info(
        "submit_image_generation: job_id=%s url=%s size=%s model=%s prompt_preview=%.80r",
        job_id, url, image_size, model, prompt,
    )

    try:
        response = requests.post(
            url,
            headers={"Authorization": f"Key {FAL_API_KEY}"},
            json={
                "prompt": prompt,
                "image_size": image_size,
                "num_images": 1,
            },
            timeout=120,
        )
    except requests.exceptions.Timeout:
        log.error("fal.ai request timed out after 120s (job_id=%s)", job_id)
        raise RuntimeError("fal.ai timed out after 120 seconds — the service may be overloaded")
    except requests.exceptions.ConnectionError as exc:
        log.error("fal.ai connection error (job_id=%s): %s", job_id, exc)
        raise RuntimeError(f"Could not connect to fal.ai ({FAL_SYNC_BASE}): {exc}")

    if not response.ok:
        body = response.text[:2000]
        log.error(
            "fal.ai error: HTTP %d from %s — body: %s",
            response.status_code, url, body,
        )
        # Give a clear actionable message for known fal.ai error states
        if response.status_code == 403 and "Exhausted balance" in body:
            raise RuntimeError(
                "Image generation unavailable: fal.ai account balance is exhausted. "
                "Top up at fal.ai/dashboard/billing to restore image generation."
            )
        if response.status_code == 401:
            raise RuntimeError(
                "Image generation unavailable: fal.ai API key is invalid or missing. "
                "Check FAL_API_KEY in Railway environment variables."
            )
        raise RuntimeError(
            f"fal.ai returned HTTP {response.status_code}: {body}"
        )

    try:
        data = response.json()
    except Exception as exc:
        log.error("fal.ai: could not parse JSON response (job_id=%s): %s | raw: %.500s",
                  job_id, exc, response.text)
        raise RuntimeError(f"fal.ai response was not valid JSON: {exc}")

    images = data.get("images", [])
    if not images:
        log.error("fal.ai response missing 'images' key (job_id=%s): %r", job_id, data)
        raise RuntimeError(f"fal.ai response missing images field. Full response: {data!r}")

    entry = images[0]
    cdn_url = entry["url"] if isinstance(entry, dict) else entry
    log.info("submit_image_generation: downloading from cdn_url=%.120s", cdn_url)
    public_url = download_and_save_image(job_id, cdn_url)
    log.info("submit_image_generation: completed job_id=%s → %s", job_id, public_url)
    return public_url


def get_image_job_status(job_id: str) -> dict:
    """Return status for a generated image. Images are now generated synchronously."""
    dest = pathlib.Path("/data/images") / f"{job_id}.jpg"
    if dest.exists():
        return {"status": "COMPLETED", "image_url": _public_image_url(job_id)}
    return {"status": "NOT_FOUND", "image_url": None}


def download_and_save_image(job_id: str, image_url: str) -> str:
    """Download image_url, save to /data/images/{job_id}.jpg, return public URL."""
    images_dir = pathlib.Path("/data/images")
    images_dir.mkdir(parents=True, exist_ok=True)
    dest = images_dir / f"{job_id}.jpg"

    try:
        resp = requests.get(image_url, timeout=30)
        resp.raise_for_status()
    except Exception as exc:
        log.error("download_and_save_image: failed to download %s — %s", image_url, exc)
        raise

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

    local_path = str(dest)
    public_url = _public_image_url(job_id)
    log.info("download_and_save_image: saved %s (%d bytes)", dest, len(resp.content))
    log.info(f"Logo generated: local_path={local_path} public_url={public_url}")
    return public_url


_KLING_SUBMIT_URL = "https://queue.fal.run/fal-ai/kling-video/v2/master/image-to-video"
_KLING_POLL_INTERVAL = 5
_KLING_TIMEOUT = 300


def generate_video_art(image_url: str, prompt: str, duration: int = 5) -> str:
    """Generate an animated video from an image using fal.ai Kling. Returns public video URL."""
    if not FAL_API_KEY:
        raise ValueError(
            "FAL_API_KEY is not set — video generation requires fal.ai credentials."
        )

    job_id = uuid.uuid4().hex
    headers = {"Authorization": f"Key {FAL_API_KEY}", "Content-Type": "application/json"}
    payload = {"image_url": image_url, "prompt": prompt, "duration": duration}

    log.info("generate_video_art: submitting job_id=%s prompt_preview=%.80r", job_id, prompt)
    try:
        submit_resp = requests.post(_KLING_SUBMIT_URL, headers=headers, json=payload, timeout=30)
    except requests.exceptions.ConnectionError as exc:
        raise RuntimeError(f"Could not connect to fal.ai Kling: {exc}")

    if not submit_resp.ok:
        body = submit_resp.text[:1000]
        log.error("Kling submit error: HTTP %d — %s", submit_resp.status_code, body)
        if submit_resp.status_code == 403 and "Exhausted balance" in body:
            raise RuntimeError(
                "Video generation unavailable: fal.ai account balance is exhausted. "
                "Top up at fal.ai/dashboard/billing."
            )
        raise RuntimeError(f"Kling submit returned HTTP {submit_resp.status_code}: {body}")

    request_id = submit_resp.json().get("request_id")
    if not request_id:
        raise RuntimeError(f"Kling submit response missing request_id: {submit_resp.text[:500]}")

    log.info("generate_video_art: submitted request_id=%s, polling…", request_id)
    status_url = f"{_KLING_SUBMIT_URL}/requests/{request_id}/status"
    result_url = f"{_KLING_SUBMIT_URL}/requests/{request_id}"
    elapsed = 0

    while elapsed < _KLING_TIMEOUT:
        import time
        time.sleep(_KLING_POLL_INTERVAL)
        elapsed += _KLING_POLL_INTERVAL

        try:
            status_resp = requests.get(status_url, headers=headers, timeout=15)
        except requests.exceptions.ConnectionError:
            continue

        if not status_resp.ok:
            log.warning("Kling status poll HTTP %d (request_id=%s)", status_resp.status_code, request_id)
            continue

        status_data = status_resp.json()
        state = status_data.get("status", "")
        log.info("generate_video_art: poll elapsed=%ds state=%s", elapsed, state)

        if state == "COMPLETED":
            result_resp = requests.get(result_url, headers=headers, timeout=15)
            result_resp.raise_for_status()
            result_data = result_resp.json()
            video_url = (result_data.get("video") or {}).get("url") or result_data.get("video_url", "")
            if not video_url:
                raise RuntimeError(f"Kling result missing video URL: {result_data!r}")

            # Download and save to /data/images as .mp4
            videos_dir = pathlib.Path("/data/images")
            videos_dir.mkdir(parents=True, exist_ok=True)
            dest = videos_dir / f"{job_id}.mp4"
            vid_resp = requests.get(video_url, timeout=60)
            vid_resp.raise_for_status()
            dest.write_bytes(vid_resp.content)
            local_path = str(dest)
            public_url = _public_image_url(job_id, "mp4")
            log.info("generate_video_art: saved %s (%d bytes)", dest, len(vid_resp.content))
            log.info(f"Video art generated: local_path={local_path} public_url={public_url}")
            return public_url

        if state in ("FAILED", "ERROR"):
            raise RuntimeError(f"Kling video generation failed: {status_data}")

    raise RuntimeError(f"Kling video generation timed out after {_KLING_TIMEOUT}s (request_id={request_id})")
