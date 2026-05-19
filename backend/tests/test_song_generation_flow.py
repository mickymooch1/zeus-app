import os
import pathlib
import sys
from unittest.mock import patch

import pytest

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))

os.environ.setdefault("ANTHROPIC_API_KEY", "test-key-for-tests")
os.environ.setdefault("APIFRAME_API_KEY", "test-key-for-tests")
os.environ.setdefault("SONG_STORAGE_PATH", "/tmp/test_songs")
os.environ.setdefault("SONG_PUBLIC_BASE_URL", "https://example.com/files/songs")
os.environ.setdefault("SONG_WEBHOOK_URL", "https://zeusaidesign.com/webhooks/apiframe")


def _user():
    return {
        "id": "user-1",
        "email": "user@example.com",
        "subscription_status": "active",
        "subscription_plan": "music_pro",
        "password_hash": "x",
        "name": "User",
        "is_admin": 0,
        "email_verified": 1,
    }


def test_inspired_by_text_is_sanitized_before_suno_style_prompt():
    import songs

    sanitizer = getattr(songs, "sanitize_inspired_by_descriptors", None)
    assert sanitizer is not None

    safe = sanitizer("like Drake, with Travis Scott ad-libs and Billie Eilish whisper vocals")

    lowered = safe.lower()
    assert "drake" not in lowered
    assert "travis" not in lowered
    assert "billie" not in lowered
    assert "like " not in lowered
    assert "melodic rap" in lowered
    assert "atmospheric trap drums" in lowered


@pytest.mark.asyncio
async def test_lyric_variants_response_includes_music_video_url():
    import main as _main

    with patch.object(_main.db, "get_db_path", return_value=pathlib.Path("unused.db")), \
         patch.object(_main.db, "get_lyric", return_value={"id": 123, "user_id": "user-1"}), \
         patch.object(_main.db, "get_song_variants_for_lyric", return_value=[
             {
                 "id": 456,
                 "genre_tag": "hiphop",
                 "take_number": 1,
                 "status": "complete",
                 "mp3_url": "https://example.com/456.mp3",
                 "image_url": "https://example.com/456.jpg",
                 "duration_seconds": 120,
                 "did_job_id": None,
                 "video_url": None,
                 "youtube_url": None,
                 "music_video_url": "https://example.com/456_music_video.mp4",
                 "is_favourite": 0,
             }
         ]):
        resp = await _main.get_lyric_variants(123, current_user=_user())

    variant = resp["variants"][0]
    assert variant["music_video_url"] == "https://example.com/456_music_video.mp4"
