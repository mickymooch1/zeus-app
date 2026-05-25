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

# Keep module-level constants for upload path (rarely changes after startup).
# OAuth helpers read live env vars so Railway changes take effect immediately.
YOUTUBE_REDIRECT_URI = os.environ.get("YOUTUBE_REDIRECT_URI", "http://localhost:8080/api/youtube/callback")
YOUTUBE_SCOPE = "https://www.googleapis.com/auth/youtube.upload"
YOUTUBE_SCOPES = [YOUTUBE_SCOPE]


def youtube_enabled() -> bool:
    """Read live env vars every call — survives Railway env var updates without redeploy."""
    return bool(
        os.environ.get("GOOGLE_CLIENT_ID", "").strip() and
        os.environ.get("GOOGLE_CLIENT_SECRET", "").strip()
    )


def build_auth_url(state: str, redirect_uri: str | None = None, verifier: str | None = None) -> str:
    """Build Google OAuth consent URL.

    verifier — the PKCE code_verifier to embed as the challenge.  When the
    caller passes this in (sourced from the signed state JWT) the in-process
    _pkce_store is not needed and multi-instance / restart safety is guaranteed.
    If omitted a fresh verifier is generated (legacy path).
    """
    _redirect_uri = redirect_uri or os.environ.get("YOUTUBE_REDIRECT_URI", YOUTUBE_REDIRECT_URI)
    _client_id = os.environ.get("GOOGLE_CLIENT_ID", "").strip()
    if not verifier:
        verifier = secrets.token_urlsafe(96)
    challenge = base64.urlsafe_b64encode(
        hashlib.sha256(verifier.encode()).digest()
    ).rstrip(b"=").decode()
    params = {
        "client_id": _client_id,
        "redirect_uri": _redirect_uri,
        "response_type": "code",
        "scope": YOUTUBE_SCOPE,
        "access_type": "offline",
        "prompt": "consent",
        "state": state,
        "code_challenge": challenge,
        "code_challenge_method": "S256",
    }
    url = "https://accounts.google.com/o/oauth2/v2/auth?" + urlencode(params)
    log.info("build_auth_url: redirect_uri=%r client_id_first10=%r", _redirect_uri, _client_id[:10] if _client_id else "UNSET")
    return url


def exchange_code(code: str, redirect_uri: str, code_verifier: str | None = None) -> str:
    """Exchange an OAuth authorisation code for a refresh token.

    code_verifier — the PKCE verifier, sourced from the signed state JWT.
    """
    _client_id = os.environ.get("GOOGLE_CLIENT_ID", "").strip()
    _client_secret = os.environ.get("GOOGLE_CLIENT_SECRET", "").strip()
    body = {
        "code": code,
        "client_id": _client_id,
        "client_secret": _client_secret,
        "redirect_uri": redirect_uri,
        "grant_type": "authorization_code",
    }
    if code_verifier:
        body["code_verifier"] = code_verifier
    log.info("exchange_code: redirect_uri=%r verifier_present=%s", redirect_uri, bool(code_verifier))
    resp = requests.post("https://oauth2.googleapis.com/token", data=body, timeout=30)
    data = resp.json()
    if "error" in data:
        log.error("exchange_code: Google error: %s", data)
        raise ValueError(f"Token exchange failed: {data}")
    refresh_token = data.get("refresh_token")
    if not refresh_token:
        raise ValueError(
            "Google did not return a refresh token. "
            "The user may have already authorised this app — revoke access at myaccount.google.com and try again."
        )
    return refresh_token


_DESCRIPTIONS = {
    "beats": (
        "AI-generated song created with Zeus Beats · zeusbeats.com\n"
        "Make your own original songs at zeusbeats.com \U0001f3b5⚡"
    ),
    "web": "AI-generated song created with Zeus AI · zeusaidesign.com",
}


def upload_song_to_youtube(
    variant: dict,
    user: dict,
    privacy: str,
    title: str,
    prebuilt_mp4: Path | None = None,
    site: str = "web",
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

    _client_id = os.environ.get("GOOGLE_CLIENT_ID", "").strip()
    _client_secret = os.environ.get("GOOGLE_CLIENT_SECRET", "").strip()

    refresh_token = user.get("youtube_refresh_token")
    if not refresh_token:
        raise ValueError("YouTube not connected")

    variant_id = variant["id"]
    privacy = privacy or "unlisted"

    def _upload(mp4_path: Path) -> str:
        from google.auth.exceptions import RefreshError, TransportError
        from googleapiclient.errors import HttpError as YTHttpError

        creds = Credentials(
            token=None,
            refresh_token=refresh_token,
            token_uri="https://oauth2.googleapis.com/token",
            client_id=_client_id,
            client_secret=_client_secret,
            scopes=YOUTUBE_SCOPES,
        )
        try:
            yt = build("youtube", "v3", credentials=creds, cache_discovery=False)
        except Exception as exc:
            raise ValueError(f"YouTube API init failed: {exc}") from exc

        raw_title = title or f"Song #{variant_id}"
        if site == "beats" and "zeus beats" not in raw_title.lower():
            suffix = " — Zeus Beats"
            # Truncate the base so suffix always fits inside YouTube's 100-char cap.
            base = raw_title[: 100 - len(suffix)]
            video_title = f"{base}{suffix}"
        else:
            video_title = raw_title[:100]
        description = _DESCRIPTIONS.get(site, _DESCRIPTIONS["web"])
        tags = (
            ["ai music", "zeus beats", "zeusbeats", "ai generated"]
            if site == "beats"
            else ["ai music", "zeus ai", "suno", "ai generated"]
        )
        body = {
            "snippet": {
                "title": video_title,
                "description": description,
                "tags": tags,
                "categoryId": "10",
            },
            "status": {"privacyStatus": privacy},
        }
        media = MediaFileUpload(str(mp4_path), mimetype="video/mp4", resumable=True)
        insert_request = yt.videos().insert(part="snippet,status", body=body, media_body=media)
        try:
            response = None
            while response is None:
                _, response = insert_request.next_chunk()
        except RefreshError as exc:
            raise ValueError(f"invalid_grant: YouTube token refresh failed: {exc}") from exc
        except TransportError as exc:
            raise ValueError(f"YouTube network error during upload: {exc}") from exc
        except YTHttpError as exc:
            status = exc.resp.status if exc.resp else "?"
            raise ValueError(f"YouTube API HTTP {status}: {exc.reason}") from exc

        if not response or "id" not in response:
            raise ValueError(f"YouTube upload complete but response missing video ID: {response!r}")

        video_id = response["id"]
        log.info("YouTube upload complete: video_id=%s variant_id=%s user=%s",
                 video_id, variant_id, user["id"])
        return f"https://youtu.be/{video_id}"

    # Fast path — prebuilt MP4 (e.g. D-ID avatar video); no FFmpeg needed.
    if prebuilt_mp4 is not None and Path(prebuilt_mp4).exists():
        log.info("upload_song_to_youtube: using prebuilt MP4 %s", prebuilt_mp4)
        return _upload(Path(prebuilt_mp4))

    # Standard path — mux still image + MP3 into MP4 with ffmpeg.
    storage_path = os.environ.get("SONG_STORAGE_PATH", "/data/songs")
    mp3_src = Path(storage_path) / f"{variant_id}.mp3"
    img_src = Path(storage_path) / f"{variant_id}_cover.jpg"

    if not mp3_src.exists():
        raise ValueError(f"MP3 not found on volume: {mp3_src}")

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        img_path = img_src if img_src.exists() else tmp / f"{variant_id}_cover.jpg"
        mp4_path = tmp / f"{variant_id}.mp4"

        if not img_src.exists():
            log.info("upload_song_to_youtube: cover art not found at %s — using black fallback", img_src)
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
