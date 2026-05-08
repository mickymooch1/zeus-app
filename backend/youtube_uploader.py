"""
youtube_uploader.py — YouTube OAuth + upload for Zeus.
Requires GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET env vars.
ffmpeg must be installed in the runtime environment (added to Dockerfile Stage 2).
"""
import logging
import os
import subprocess
import tempfile
from pathlib import Path

import httpx

log = logging.getLogger("zeus.youtube")

GOOGLE_CLIENT_ID = os.environ.get("GOOGLE_CLIENT_ID", "")
GOOGLE_CLIENT_SECRET = os.environ.get("GOOGLE_CLIENT_SECRET", "")
YOUTUBE_SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]

_CLIENT_CONFIG = {
    "web": {
        "client_id": GOOGLE_CLIENT_ID,
        "client_secret": GOOGLE_CLIENT_SECRET,
        "auth_uri": "https://accounts.google.com/o/oauth2/auth",
        "token_uri": "https://oauth2.googleapis.com/token",
    }
}


def youtube_enabled() -> bool:
    return bool(GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET)


def build_auth_url(state: str, redirect_uri: str) -> str:
    """Return the Google OAuth consent-screen URL."""
    from google_auth_oauthlib.flow import Flow
    config = {
        "web": {
            "client_id": GOOGLE_CLIENT_ID,
            "client_secret": GOOGLE_CLIENT_SECRET,
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
        }
    }
    flow = Flow.from_client_config(config, scopes=YOUTUBE_SCOPES, redirect_uri=redirect_uri)
    auth_url, _ = flow.authorization_url(
        access_type="offline",
        include_granted_scopes="true",
        prompt="consent",
        state=state,
    )
    return auth_url


def exchange_code(code: str, redirect_uri: str) -> str:
    """Exchange OAuth authorisation code for a refresh token."""
    from google_auth_oauthlib.flow import Flow
    config = {
        "web": {
            "client_id": GOOGLE_CLIENT_ID,
            "client_secret": GOOGLE_CLIENT_SECRET,
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
        }
    }
    flow = Flow.from_client_config(config, scopes=YOUTUBE_SCOPES, redirect_uri=redirect_uri)
    flow.fetch_token(code=code)
    creds = flow.credentials
    if not creds.refresh_token:
        raise ValueError(
            "Google did not return a refresh token. "
            "The user may have already authorised this app — revoke access at myaccount.google.com and try again."
        )
    return creds.refresh_token


def upload_song_to_youtube(variant: dict, user: dict, privacy: str, title: str) -> str:
    """
    Download MP3 + cover art, mux into MP4 via ffmpeg, upload to YouTube.
    Returns the YouTube video URL (https://youtu.be/<id>).
    """
    from google.oauth2.credentials import Credentials
    from googleapiclient.discovery import build
    from googleapiclient.http import MediaFileUpload

    refresh_token = user.get("youtube_refresh_token")
    if not refresh_token:
        raise ValueError("YouTube not connected")

    variant_id = variant["id"]
    mp3_url = variant.get("mp3_url")
    if not mp3_url:
        raise ValueError("Variant has no MP3 URL yet")

    image_url = variant.get("image_url")
    privacy = privacy or "unlisted"

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        mp3_path = tmp / f"{variant_id}.mp3"
        img_path = tmp / f"{variant_id}.jpg"
        mp4_path = tmp / f"{variant_id}.mp4"

        # Download MP3
        with httpx.Client(timeout=120) as client:
            r = client.get(mp3_url)
            r.raise_for_status()
            mp3_path.write_bytes(r.content)

        # Download cover art — fall back to black frame on failure
        if image_url:
            try:
                with httpx.Client(timeout=30) as client:
                    r = client.get(image_url)
                    r.raise_for_status()
                    img_path.write_bytes(r.content)
            except Exception as exc:
                log.warning("Could not fetch cover art (%s) — using black frame", exc)
                image_url = None

        if not image_url:
            subprocess.run(
                ["ffmpeg", "-y", "-f", "lavfi", "-i", "color=c=black:s=1280x720:r=1",
                 "-frames:v", "1", str(img_path)],
                check=True, capture_output=True,
            )

        # Mux still image + audio into MP4
        subprocess.run(
            [
                "ffmpeg", "-y",
                "-loop", "1", "-i", str(img_path),
                "-i", str(mp3_path),
                "-c:v", "libx264", "-tune", "stillimage",
                "-c:a", "aac", "-b:a", "192k",
                "-pix_fmt", "yuv420p",
                "-shortest",
                str(mp4_path),
            ],
            check=True, capture_output=True,
        )

        # Authenticate with YouTube
        creds = Credentials(
            token=None,
            refresh_token=refresh_token,
            token_uri="https://oauth2.googleapis.com/token",
            client_id=GOOGLE_CLIENT_ID,
            client_secret=GOOGLE_CLIENT_SECRET,
            scopes=YOUTUBE_SCOPES,
        )
        youtube = build("youtube", "v3", credentials=creds)

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
        insert_request = youtube.videos().insert(
            part="snippet,status", body=body, media_body=media
        )

        response = None
        while response is None:
            _, response = insert_request.next_chunk()

        video_id = response["id"]
        log.info("YouTube upload complete: video_id=%s variant_id=%s user=%s",
                 video_id, variant_id, user["id"])
        return f"https://youtu.be/{video_id}"
