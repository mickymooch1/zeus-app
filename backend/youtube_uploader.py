"""
youtube_uploader.py — YouTube OAuth + upload for Zeus.
Requires GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET, and YOUTUBE_REDIRECT_URI env vars.
ffmpeg must be installed in the runtime environment (added to Dockerfile Stage 2).
"""
import base64
import hashlib
import logging
import os
import secrets
import subprocess
import tempfile
from pathlib import Path
from urllib.parse import urlencode

import requests

log = logging.getLogger("zeus.youtube")

GOOGLE_CLIENT_ID = os.environ.get("GOOGLE_CLIENT_ID", "").strip()
GOOGLE_CLIENT_SECRET = os.environ.get("GOOGLE_CLIENT_SECRET", "").strip()
YOUTUBE_REDIRECT_URI = os.environ.get("YOUTUBE_REDIRECT_URI", "http://localhost:8080/api/youtube/callback")
YOUTUBE_SCOPE = "https://www.googleapis.com/auth/youtube.upload"
YOUTUBE_SCOPES = [YOUTUBE_SCOPE]

_pkce_store: dict[str, str] = {}  # state -> verifier


def youtube_enabled() -> bool:
    return bool(GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET)


def build_auth_url(state: str) -> str:
    """Build the Google OAuth consent-screen URL with PKCE, storing the verifier for the callback."""
    verifier = secrets.token_urlsafe(96)
    challenge = base64.urlsafe_b64encode(
        hashlib.sha256(verifier.encode()).digest()
    ).rstrip(b"=").decode()
    _pkce_store[state] = verifier
    params = {
        "client_id": GOOGLE_CLIENT_ID,
        "redirect_uri": YOUTUBE_REDIRECT_URI,
        "response_type": "code",
        "scope": YOUTUBE_SCOPE,
        "access_type": "offline",
        "prompt": "consent",
        "state": state,
        "code_challenge": challenge,
        "code_challenge_method": "S256",
    }
    return "https://accounts.google.com/o/oauth2/v2/auth?" + urlencode(params)


def exchange_code(code: str, redirect_uri: str, state: str | None = None) -> str:
    """Exchange an OAuth authorisation code for a refresh token."""
    verifier = _pkce_store.pop(state, None) if state else None
    resp = requests.post(
        "https://oauth2.googleapis.com/token",
        data={
            "code": code,
            "client_id": GOOGLE_CLIENT_ID,
            "client_secret": GOOGLE_CLIENT_SECRET,
            "redirect_uri": redirect_uri,
            "grant_type": "authorization_code",
            "code_verifier": verifier,
        },
        timeout=30,
    )
    data = resp.json()
    if "error" in data:
        raise ValueError(f"Token exchange failed: {data}")
    refresh_token = data.get("refresh_token")
    if not refresh_token:
        raise ValueError(
            "Google did not return a refresh token. "
            "The user may have already authorised this app — revoke access at myaccount.google.com and try again."
        )
    return refresh_token


def upload_song_to_youtube(
    variant: dict,
    user: dict,
    privacy: str,
    title: str,
    prebuilt_mp4: Path | None = None,
) -> str:
    """
    Upload a song variant to YouTube.

    If prebuilt_mp4 points to an existing file (e.g. a D-ID avatar video), it is
    uploaded directly and FFmpeg is skipped entirely.  Otherwise the usual path
    applies: read MP3 + cover art from the Railway volume and mux via ffmpeg.

    Returns the YouTube video URL (https://youtu.be/<id>).
    """
    from google.oauth2.credentials import Credentials
    from googleapiclient.discovery import build
    from googleapiclient.http import MediaFileUpload

    refresh_token = user.get("youtube_refresh_token")
    if not refresh_token:
        raise ValueError("YouTube not connected")

    variant_id = variant["id"]
    privacy = privacy or "unlisted"

    def _upload(mp4_path: Path) -> str:
        creds = Credentials(
            token=None,
            refresh_token=refresh_token,
            token_uri="https://oauth2.googleapis.com/token",
            client_id=GOOGLE_CLIENT_ID,
            client_secret=GOOGLE_CLIENT_SECRET,
            scopes=YOUTUBE_SCOPES,
        )
        yt = build("youtube", "v3", credentials=creds)
        video_title = (title or f"Song #{variant_id}")[:100]
        body = {
            "snippet": {
                "title": video_title,
                "description": "AI-generated song created with Zeus AI · zeusaidesign.com",
                "tags": ["ai music", "zeus ai", "suno", "ai generated"],
                "categoryId": "10",
            },
            "status": {"privacyStatus": privacy},
        }
        media = MediaFileUpload(str(mp4_path), mimetype="video/mp4", resumable=True)
        insert_request = yt.videos().insert(part="snippet,status", body=body, media_body=media)
        response = None
        while response is None:
            _, response = insert_request.next_chunk()
        video_id = response["id"]
        log.info("YouTube upload complete: video_id=%s variant_id=%s user=%s",
                 video_id, variant_id, user["id"])
        return f"https://youtu.be/{video_id}"

    # Fast path — prebuilt MP4 (e.g. D-ID avatar video); no FFmpeg needed.
    if prebuilt_mp4 is not None and Path(prebuilt_mp4).exists():
        log.info("upload_song_to_youtube: using prebuilt MP4 %s", prebuilt_mp4)
        return _upload(Path(prebuilt_mp4))

    # Standard path — mux still image + MP3 into MP4 with ffmpeg.
    storage_path = os.environ["SONG_STORAGE_PATH"]  # e.g. /data/songs
    mp3_src = Path(storage_path) / f"{variant_id}.mp3"
    img_src = Path(storage_path) / f"{variant_id}.jpg"

    if not mp3_src.exists():
        raise ValueError(f"MP3 not found on volume: {mp3_src}")

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        img_path = img_src if img_src.exists() else tmp / f"{variant_id}.jpg"
        mp4_path = tmp / f"{variant_id}.mp4"

        if not img_src.exists():
            subprocess.run(
                ["ffmpeg", "-y", "-f", "lavfi", "-i", "color=c=black:s=1280x720:r=1",
                 "-frames:v", "1", str(img_path)],
                check=True, capture_output=True,
            )

        subprocess.run(
            [
                "ffmpeg", "-y",
                "-loop", "1", "-i", str(img_path),
                "-i", str(mp3_src),
                "-c:v", "libx264", "-tune", "stillimage",
                "-c:a", "aac", "-b:a", "192k",
                "-pix_fmt", "yuv420p",
                "-shortest",
                str(mp4_path),
            ],
            check=True, capture_output=True,
        )

        return _upload(mp4_path)
