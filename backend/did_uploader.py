"""
did_uploader.py — D-ID Talks API integration for Zeus avatar lip-sync videos.
Requires DID_API_KEY env var.
"""
import base64
import logging
import os
import pathlib

import requests

log = logging.getLogger("zeus.did")

DID_API_KEY = os.environ.get("DID_API_KEY", "").strip()
DID_BASE = "https://api.d-id.com"


def did_enabled() -> bool:
    return bool(DID_API_KEY)


def _auth_header_value() -> str:
    creds = base64.b64encode(f"{DID_API_KEY}:".encode()).decode()
    return f"Basic {creds}"


def _auth() -> dict:
    header_value = _auth_header_value()
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


def upload_audio_to_did(mp3_path: pathlib.Path) -> str:
    """
    Upload an MP3 file to D-ID's /audios endpoint.
    Returns the D-ID-hosted audio URL to pass to the talks job.
    """
    if not did_enabled():
        raise ValueError("DID_API_KEY is not configured")

    if not mp3_path.exists():
        raise ValueError(f"MP3 file not found on disk: {mp3_path}")

    header_value = _auth_header_value()
    log.info("upload_audio_to_did: uploading %s (%d bytes)", mp3_path.name, mp3_path.stat().st_size)

    filename = mp3_path.name[:50]  # D-ID enforces 50-char filename limit
    with mp3_path.open("rb") as fh:
        resp = requests.post(
            f"{DID_BASE}/audios",
            headers={"Authorization": header_value},
            files={"audio": (filename, fh, "audio/mpeg")},
            timeout=60,
        )

    if not resp.ok:
        raise ValueError(f"D-ID audio upload failed: {resp.status_code} {resp.text[:300]}")

    data = resp.json()
    audio_url = data.get("url")
    if not audio_url:
        raise ValueError(f"D-ID audio upload returned no URL: {data!r}")

    log.info("upload_audio_to_did: %s → %s", mp3_path.name, audio_url[:100])
    return audio_url


def submit_avatar_video(
    *,
    mp3_path: pathlib.Path,
    source_url: str,
    webhook_url: str | None = None,
) -> str:
    """
    Pre-upload the MP3 to D-ID then submit a lip-sync talk job.

    mp3_path    — local path to the song MP3 (e.g. /data/songs/<variant_id>.mp3)
    source_url  — face image URL (preset or user-uploaded /files/avatars/<file>)
    webhook_url — optional Zeus webhook that D-ID will POST to on completion

    Returns the D-ID talk id (job_id).
    """
    if not did_enabled():
        raise ValueError("DID_API_KEY is not configured")

    # Pre-upload audio so D-ID fetches from its own S3, bypassing Railway URL reachability issues.
    did_audio_url = upload_audio_to_did(mp3_path)
    log.info("submit_avatar_video: using D-ID audio URL %s", did_audio_url[:100])

    body: dict = {
        "source_url": source_url,
        "script": {
            "type": "audio",
            "audio_url": did_audio_url,
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
    log.info("submit_avatar_video: job_id=%s source=%s", job_id, source_url[:60])
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
