"""
did_uploader.py — D-ID Talks API integration for Zeus avatar lip-sync videos.
Requires DID_API_KEY env var.
"""
import base64
import logging
import os

import requests

log = logging.getLogger("zeus.did")

DID_API_KEY = os.environ.get("DID_API_KEY", "").strip()
DID_BASE = "https://api.d-id.com"


def did_enabled() -> bool:
    return bool(DID_API_KEY)


def _auth() -> dict:
    creds = base64.b64encode(f"{DID_API_KEY}:".encode()).decode()
    return {
        "Authorization": f"Basic {creds}",
        "Content-Type": "application/json",
    }


# Preset avatar images shown in the avatar picker modal.
# All URLs are D-ID's own reliably-hosted DefaultPresenters CDN.
GENRE_AVATARS: list[dict] = [
    {
        "id": "noelle",
        "label": "Noelle",
        "gender": "F",
        "url": "https://create-images-results.d-id.com/DefaultPresenters/Noelle_f/image.png",
    },
    {
        "id": "anna",
        "label": "Anna",
        "gender": "F",
        "url": "https://create-images-results.d-id.com/DefaultPresenters/Anna_f/image.png",
    },
    {
        "id": "amy",
        "label": "Amy",
        "gender": "F",
        "url": "https://create-images-results.d-id.com/DefaultPresenters/Amy_f/image.png",
    },
    {
        "id": "jack",
        "label": "Jack",
        "gender": "M",
        "url": "https://create-images-results.d-id.com/DefaultPresenters/Jack_m/image.png",
    },
    {
        "id": "ethan",
        "label": "Ethan",
        "gender": "M",
        "url": "https://create-images-results.d-id.com/DefaultPresenters/Ethan_m/image.png",
    },
    {
        "id": "will",
        "label": "Will",
        "gender": "M",
        "url": "https://create-images-results.d-id.com/DefaultPresenters/Will_m/image.png",
    },
]


def submit_avatar_video(
    *,
    audio_url: str,
    source_url: str,
    webhook_url: str | None = None,
) -> str:
    """
    Submit a lip-sync talk job to D-ID.

    audio_url   — publicly accessible MP3 (e.g. Suno CDN URL stored in mp3_url)
    source_url  — face image URL (preset or user-uploaded /files/avatars/<file>)
    webhook_url — optional Zeus webhook that D-ID will POST to on completion

    Returns the D-ID talk id (job_id).
    """
    if not did_enabled():
        raise ValueError("DID_API_KEY is not configured")

    body: dict = {
        "source_url": source_url,
        "script": {
            "type": "audio",
            "audio_url": audio_url,
        },
        "config": {
            "stitch": True,
        },
    }
    if webhook_url:
        body["webhook"] = webhook_url

    resp = requests.post(
        f"{DID_BASE}/talks",
        json=body,
        headers=_auth(),
        timeout=30,
    )
    if not resp.ok:
        raise ValueError(
            f"D-ID submission failed: {resp.status_code} {resp.text[:300]}"
        )

    job_id = resp.json()["id"]
    log.info("did submit_avatar_video: job_id=%s source=%s", job_id, source_url[:60])
    return job_id


def get_job_status(job_id: str) -> dict:
    """
    Poll a D-ID talk job.

    Returns a dict with keys:
      status     — "created" | "started" | "done" | "error"
      result_url — public MP4 URL when status == "done", else None
      error      — error detail when status == "error", else None
    """
    if not did_enabled():
        raise ValueError("DID_API_KEY is not configured")

    resp = requests.get(
        f"{DID_BASE}/talks/{job_id}",
        headers=_auth(),
        timeout=15,
    )
    if not resp.ok:
        raise ValueError(
            f"D-ID status check failed: {resp.status_code} {resp.text[:200]}"
        )

    data = resp.json()
    return {
        "status": data.get("status", "unknown"),
        "result_url": data.get("result_url"),
        "error": data.get("error"),
    }
