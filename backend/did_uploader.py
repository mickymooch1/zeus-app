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
    header_value = f"Basic {creds}"
    log.info("D-ID auth header (first 20): %r", header_value[:20])
    return {
        "Authorization": header_value,
        "Content-Type": "application/json",
    }


# Preset avatar images shown in the avatar picker modal.
GENRE_AVATARS: list[dict] = [
    {"id": "w1", "name": "Sophie", "image_url": "https://randomuser.me/api/portraits/women/1.jpg"},
    {"id": "w2", "name": "Maria",  "image_url": "https://randomuser.me/api/portraits/women/2.jpg"},
    {"id": "w3", "name": "Emily",  "image_url": "https://randomuser.me/api/portraits/women/3.jpg"},
    {"id": "w4", "name": "Aisha",  "image_url": "https://randomuser.me/api/portraits/women/4.jpg"},
    {"id": "w5", "name": "Priya",  "image_url": "https://randomuser.me/api/portraits/women/5.jpg"},
    {"id": "w6", "name": "Zoe",    "image_url": "https://randomuser.me/api/portraits/women/6.jpg"},
    {"id": "m1", "name": "James",  "image_url": "https://randomuser.me/api/portraits/men/1.jpg"},
    {"id": "m2", "name": "Marcus", "image_url": "https://randomuser.me/api/portraits/men/2.jpg"},
    {"id": "m3", "name": "Carlos", "image_url": "https://randomuser.me/api/portraits/men/3.jpg"},
    {"id": "m4", "name": "Raj",    "image_url": "https://randomuser.me/api/portraits/men/4.jpg"},
    {"id": "m5", "name": "Tyler",  "image_url": "https://randomuser.me/api/portraits/men/5.jpg"},
    {"id": "m6", "name": "Daniel", "image_url": "https://randomuser.me/api/portraits/men/6.jpg"},
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
