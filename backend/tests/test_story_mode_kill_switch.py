"""Kids Story Mode is disabled because the ElevenLabs narration key is unpaid
(401s). This pins that a story-mode request is rejected BEFORE any lyrics
generation or ElevenLabs call — not just hidden in the UI — and that every
other generation path (kids song mode, normal songs) is untouched.

Defaults to disabled unless STORY_MODE_ENABLED="true" — shipping this code is
itself the disable; no separate env-var change is required to take effect.
"""
import os
import pathlib
import sys
from unittest.mock import patch

from fastapi.testclient import TestClient

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))
os.environ.setdefault("ANTHROPIC_API_KEY", "test-key")
os.environ.setdefault("APIFRAME_API_KEY", "test-key")
os.environ.setdefault("SONG_STORAGE_PATH", "/tmp/test_songs")
os.environ.setdefault("SONG_PUBLIC_BASE_URL", "https://example.com/files/songs")
os.environ.setdefault("SONG_WEBHOOK_URL", "https://zeusaidesign.com/webhooks/apiframe")
os.environ.setdefault("JWT_SECRET", "test-secret-for-story-kill-switch")


def _user():
    return {
        "id": "story-user", "email": "story@test.com", "subscription_status": "active",
        "subscription_plan": "free", "password_hash": "x", "name": "Story Test", "is_admin": 0,
        "email_verified": 1,
    }


def _post(body, env_overrides=None):
    """Drives the real endpoint end to end for paths that get past the kill
    switch — generate_multiple_variants (Apiframe submission) is mocked too so
    these tests never touch the network regardless of how far the request gets."""
    import auth
    import main as _main

    _main.app.dependency_overrides[auth.get_current_user] = lambda: _user()
    _main.limiter.enabled = False
    env_overrides = env_overrides or {}
    try:
        with patch.dict(os.environ, env_overrides), \
             patch("db.get_song_credits", return_value={"balance": 10, "monthly_allowance": 0}), \
             patch("db.upsert_song_credits"), \
             patch("lyrics.generate_lyrics",
                   return_value={"lyric_id": 1, "lyrics": "[Verse 1]\nfake", "title": "Fake"}) as lyrics_fn, \
             patch("songs.generate_multiple_variants",
                   return_value={"variants": [{"variant_id": 1, "genre": "pop"}]}), \
             patch("httpx.AsyncClient.post") as el_post:
            with TestClient(_main.app) as client:
                resp = client.post("/api/songs/generate", json=body,
                                   headers={"Authorization": "Bearer fake"})
            return resp, lyrics_fn, el_post
    finally:
        _main.app.dependency_overrides.pop(auth.get_current_user, None)


STORY_BODY = {
    "brief": "a dragon adventure", "genres": ["pop"],
    "kids_story": True, "kids_mode": "story",
}


def test_story_mode_rejected_by_default():
    """No STORY_MODE_ENABLED set at all — must be disabled by default."""
    resp, lyrics_fn, el_post = _post(STORY_BODY, env_overrides={"STORY_MODE_ENABLED": ""})
    assert resp.status_code == 503
    assert "coming soon" in resp.json()["detail"].lower()


def test_story_mode_never_calls_generate_lyrics_when_disabled():
    """The real bug class this exists to prevent: burning a Claude call (and a
    credit) on a request that's going to fail anyway."""
    resp, lyrics_fn, el_post = _post(STORY_BODY, env_overrides={"STORY_MODE_ENABLED": "false"})
    assert resp.status_code == 503
    lyrics_fn.assert_not_called()


def test_story_mode_never_calls_elevenlabs_when_disabled():
    """The actual safety property: the ElevenLabs narration HTTP call is
    structurally unreachable, not just hidden behind a frontend button."""
    resp, lyrics_fn, el_post = _post(STORY_BODY, env_overrides={"STORY_MODE_ENABLED": "false"})
    assert resp.status_code == 503
    el_post.assert_not_called()


def test_explicit_true_re_enables_story_mode():
    """Flipping the flag back on must restore the path — this is the whole
    point of it being a flag and not a deleted code path. The ElevenLabs call
    itself still fails in this test (no real API key), which surfaces as a 500
    further down the pipeline — the point here is only that the kill switch
    itself (503, before lyrics) no longer fires."""
    resp, lyrics_fn, el_post = _post(
        STORY_BODY,
        env_overrides={"STORY_MODE_ENABLED": "true", "ELEVENLABS_API_KEY": "fake-key-for-test"},
    )
    assert resp.status_code != 503
    lyrics_fn.assert_called_once()
    el_post.assert_called()


def test_kids_song_mode_is_unaffected():
    """Kids Song Mode (kids_mode='song') never touches ElevenLabs — must not be
    caught by the story-mode kill switch."""
    body = {"brief": "a fun song", "genres": ["pop"], "kids_story": True, "kids_mode": "song"}
    resp, lyrics_fn, el_post = _post(body, env_overrides={"STORY_MODE_ENABLED": "false"})
    assert resp.status_code != 503
    lyrics_fn.assert_called_once()
    el_post.assert_not_called()


def test_normal_song_generation_is_unaffected():
    body = {"brief": "a song about summer", "genres": ["pop"]}
    resp, lyrics_fn, el_post = _post(body, env_overrides={"STORY_MODE_ENABLED": "false"})
    assert resp.status_code != 503
    lyrics_fn.assert_called_once()


def test_feature_flags_endpoint_reflects_disabled_state():
    import main as _main
    with patch.dict(os.environ, {"STORY_MODE_ENABLED": ""}):
        with TestClient(_main.app) as client:
            resp = client.get("/api/feature-flags")
    assert resp.status_code == 200
    assert resp.json() == {"story_mode_enabled": False}


def test_feature_flags_endpoint_reflects_enabled_state():
    import main as _main
    with patch.dict(os.environ, {"STORY_MODE_ENABLED": "true"}):
        with TestClient(_main.app) as client:
            resp = client.get("/api/feature-flags")
    assert resp.status_code == 200
    assert resp.json() == {"story_mode_enabled": True}


def test_feature_flags_endpoint_requires_no_auth():
    """The frontend needs this before a user is logged in (e.g. on the kids
    home screen), so it must not require a bearer token."""
    import main as _main
    with TestClient(_main.app) as client:
        resp = client.get("/api/feature-flags")
    assert resp.status_code == 200
