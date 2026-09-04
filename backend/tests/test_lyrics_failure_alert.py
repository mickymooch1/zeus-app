"""The alert that did not exist for the 2026-09-02 `temperature` SDK-drift
incident: every song failed identically for hours, with nothing paging anyone,
until a customer reported it. This pins that /api/songs/generate now calls
alert_lyrics_generation_failed() the moment generate_lyrics() raises — for
every song type, with the error and type included — and that a DB-layer failure
in the unrelated custom_lyrics path does NOT fire it (that's a different bug
class, not what this alert is for).
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
os.environ.setdefault("JWT_SECRET", "test-secret-for-lyrics-alert-tests")


def _user():
    return {
        "id": "alert-user", "email": "alerttest@example.com",
        "subscription_status": "active", "subscription_plan": "free",
        "password_hash": "x", "name": "Alert Test", "is_admin": 0,
        "email_verified": 1,
    }


def _post(body, lyrics_error=None, custom_lyrics_error=None):
    """POST /api/songs/generate, capturing the alert_lyrics_generation_failed call."""
    import auth
    import main as _main

    _main.app.dependency_overrides[auth.get_current_user] = lambda: _user()
    _main.limiter.enabled = False
    try:
        with patch("db.get_song_credits", return_value={"balance": 10, "monthly_allowance": 0}), \
             patch("db.upsert_song_credits"), \
             patch("alerts.alert_lyrics_generation_failed") as alert_fn:
            if lyrics_error:
                with patch("lyrics.generate_lyrics", side_effect=lyrics_error):
                    with TestClient(_main.app) as client:
                        resp = client.post("/api/songs/generate", json=body,
                                           headers={"Authorization": "Bearer fake"})
            elif custom_lyrics_error:
                with patch("lyrics.store_custom_lyrics", side_effect=custom_lyrics_error):
                    with TestClient(_main.app) as client:
                        resp = client.post("/api/songs/generate", json=body,
                                           headers={"Authorization": "Bearer fake"})
            else:
                with TestClient(_main.app) as client:
                    resp = client.post("/api/songs/generate", json=body,
                                       headers={"Authorization": "Bearer fake"})
            return resp, alert_fn
    finally:
        _main.app.dependency_overrides.pop(auth.get_current_user, None)


def test_normal_song_failure_fires_the_alert():
    err = TypeError("Messages.create() got an unexpected keyword argument 'temperature'")
    resp, alert_fn = _post({"brief": "a song about summer", "genres": ["pop"]}, lyrics_error=err)
    assert resp.status_code == 500
    alert_fn.assert_called_once()
    email, song_type, error_text = alert_fn.call_args[0]
    assert email == "alerttest@example.com"
    assert song_type == "normal"
    assert "temperature" in error_text


def test_kids_story_failure_fires_the_alert_with_kids_story_type():
    """song_type classification keys on kids_story alone, not kids_mode — using
    kids_mode='song' here deliberately (not 'story') since story mode is
    currently disabled by the kill switch in test_story_mode_kill_switch.py and
    this test is about the lyrics-failure alert, not story mode itself."""
    err = RuntimeError("kids lyrics generation exploded")
    resp, alert_fn = _post(
        {"brief": "a dragon adventure", "genres": ["pop"], "kids_story": True, "kids_mode": "song"},
        lyrics_error=err,
    )
    assert resp.status_code == 500
    alert_fn.assert_called_once()
    _, song_type, error_text = alert_fn.call_args[0]
    assert song_type == "kids-story"
    assert "exploded" in error_text


def test_roast_failure_fires_the_alert_with_roast_type():
    err = ValueError("roast json parse failed")
    resp, alert_fn = _post(
        {"brief": "x", "genres": ["pop"], "is_roast": True, "roast_name": "Dave"},
        lyrics_error=err,
    )
    assert resp.status_code == 500
    alert_fn.assert_called_once()
    _, song_type, _ = alert_fn.call_args[0]
    assert song_type == "roast"


def test_custom_lyrics_failure_does_not_fire_this_alert():
    """store_custom_lyrics never calls Claude — a failure there is a DB/logic bug,
    not the class of failure this alert exists for."""
    err = Exception("db write failed")
    resp, alert_fn = _post(
        {"brief": "x", "genres": ["pop"], "custom_lyrics": "[Verse 1]\nmy own words"},
        custom_lyrics_error=err,
    )
    assert resp.status_code == 500
    alert_fn.assert_not_called()


def test_a_successful_generation_never_fires_the_alert():
    import auth
    import main as _main

    _main.app.dependency_overrides[auth.get_current_user] = lambda: _user()
    _main.limiter.enabled = False
    try:
        with patch("db.get_song_credits", return_value={"balance": 10, "monthly_allowance": 0}), \
             patch("db.upsert_song_credits"), \
             patch("alerts.alert_lyrics_generation_failed") as alert_fn, \
             patch("lyrics.generate_lyrics",
                   return_value={"lyric_id": 1, "lyrics": "[Verse 1]\nfake", "title": "Fake"}):
            with TestClient(_main.app) as client:
                client.post("/api/songs/generate", json={"brief": "x", "genres": ["pop"]},
                           headers={"Authorization": "Bearer fake"})
        alert_fn.assert_not_called()
    finally:
        _main.app.dependency_overrides.pop(auth.get_current_user, None)


def test_a_broken_alert_call_does_not_turn_the_500_into_a_crash():
    """The alert send itself must never take down the actual error response —
    same guarantee every alert_* in alerts.py already gives."""
    import auth
    import main as _main

    _main.app.dependency_overrides[auth.get_current_user] = lambda: _user()
    _main.limiter.enabled = False
    try:
        with patch("db.get_song_credits", return_value={"balance": 10, "monthly_allowance": 0}), \
             patch("db.upsert_song_credits"), \
             patch("alerts.alert_lyrics_generation_failed", side_effect=RuntimeError("telegram down")), \
             patch("lyrics.generate_lyrics", side_effect=TypeError("boom")):
            with TestClient(_main.app) as client:
                resp = client.post("/api/songs/generate", json={"brief": "x", "genres": ["pop"]},
                                   headers={"Authorization": "Bearer fake"})
        assert resp.status_code == 500, "the real error must still surface, not a 500 from the alert crashing"
        assert "boom" in resp.json()["detail"]
    finally:
        _main.app.dependency_overrides.pop(auth.get_current_user, None)
