"""UTM attribution (2026-09-23 addition, folded into the Zeus Clips Phase 2 work).

First-touch: the frontend (utils/utmAttribution.js) captures utm_source/medium/
campaign from the URL on first landing and never overwrites an existing capture,
then carries them through signup/login/email-verification and attaches them to:
  - the user record, once, at signup (db.create_user)
  - every clip_events row logged from an endpoint that receives them
    (clips.log_event)

No decode/validation of the values happens server-side beyond "is it a string" —
these are marketing tags, free-text by nature (an unrecognised utm_source is not
an error, just an unfamiliar campaign).
"""
import importlib
import os
import pathlib
import sqlite3
import sys
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))
os.environ.setdefault("ANTHROPIC_API_KEY", "test-key")
os.environ.setdefault("APIFRAME_API_KEY", "test-key")
os.environ.setdefault("SONG_STORAGE_PATH", "/tmp/test_songs")
os.environ.setdefault("SONG_PUBLIC_BASE_URL", "https://example.com/files/songs")
os.environ.setdefault("SONG_WEBHOOK_URL", "https://zeusaidesign.com/webhooks/apiframe")
os.environ.setdefault("JWT_SECRET", "test-secret-for-utm-tests")

import db
import clips

NOW = datetime(2026, 9, 23, 12, 0, 0, tzinfo=timezone.utc)


@pytest.fixture
def app_client(tmp_path, monkeypatch):
    monkeypatch.setenv("ZEUS_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("SONG_STORAGE_PATH", str(tmp_path / "songs"))
    monkeypatch.setenv("CLIP_STORAGE_PATH", str(tmp_path / "clips"))
    import db as _db
    importlib.reload(_db)
    import main as _main
    importlib.reload(_main)
    _main.limiter.enabled = False
    with TestClient(_main.app) as client:
        yield client, _db


@pytest.fixture
def path(tmp_path):
    p = tmp_path / "test.db"
    db.init_user_tables(p)
    return p


# ── db.create_user: first-touch attribution, written once at signup ─────────

def test_create_user_stores_utm_attribution_when_given(path):
    user = db.create_user(path, "a@example.com", "hash", "Alice", NOW.isoformat(),
                          utm_source="instagram", utm_medium="social", utm_campaign="launch")
    assert user["utm_source"] == "instagram"
    assert user["utm_medium"] == "social"
    assert user["utm_campaign"] == "launch"


def test_create_user_leaves_utm_columns_null_when_not_given(path):
    """Existing call sites (the vast majority) pass none of this — must keep working."""
    user = db.create_user(path, "a@example.com", "hash", "Alice", NOW.isoformat())
    assert user["utm_source"] is None
    assert user["utm_medium"] is None
    assert user["utm_campaign"] is None


# ── clips.log_event: attached when the caller has attribution to give ───────

def add_user(path_, uid, email):
    conn = sqlite3.connect(path_)
    conn.execute(
        "INSERT INTO users (id, email, password_hash, created_at, updated_at) VALUES (?, ?, 'x', ?, ?)",
        (uid, email, NOW.isoformat(), NOW.isoformat()),
    )
    conn.commit()
    conn.close()


def test_log_event_stores_utm_fields_when_given(path):
    add_user(path, "u1", "a@example.com")
    clips.log_event(path, "clip_published", user_id="u1", clip_id=1, song_id=1,
                    utm_source="tiktok", utm_medium="social", utm_campaign="remix_push")
    conn = sqlite3.connect(path)
    row = conn.execute(
        "SELECT utm_source, utm_medium, utm_campaign FROM clip_events WHERE event_name = 'clip_published'"
    ).fetchone()
    conn.close()
    assert row == ("tiktok", "social", "remix_push")


def test_log_event_leaves_utm_columns_null_when_not_given(path):
    """Every EXISTING log_event call site (remix_completed from the webhook path,
    and any caller that predates this feature) must keep working unchanged."""
    add_user(path, "u1", "a@example.com")
    clips.log_event(path, "clip_viewed", user_id="u1", clip_id=1, song_id=1)
    conn = sqlite3.connect(path)
    row = conn.execute(
        "SELECT utm_source, utm_medium, utm_campaign FROM clip_events WHERE event_name = 'clip_viewed'"
    ).fetchone()
    conn.close()
    assert row == (None, None, None)


# ── API: /auth/register captures first-touch attribution ────────────────────

def test_register_stores_utm_attribution_on_the_user(app_client):
    client, _db = app_client
    r = client.post("/auth/register", json={
        "email": "utm-test@example.com", "password": "correcthorsebattery",
        "tc_accepted": True, "app": "beats",
        "utm_source": "instagram", "utm_medium": "social", "utm_campaign": "launch",
    })
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["user"]["utm_source"] == "instagram"
    assert body["user"]["utm_medium"] == "social"
    assert body["user"]["utm_campaign"] == "launch"


def test_register_without_utm_fields_still_works(app_client):
    """The overwhelming majority of registrations carry no attribution at all —
    must not become required."""
    client, _db = app_client
    r = client.post("/auth/register", json={
        "email": "no-utm@example.com", "password": "correcthorsebattery",
        "tc_accepted": True, "app": "beats",
    })
    assert r.status_code == 200, r.text
    assert r.json()["user"]["utm_source"] is None


# ── API: clip endpoints attach utm to the clip_events rows they log ─────────

def _publish(client, token, song_id=1, **overrides):
    body = {"song_id": song_id, "caption": "", "media_type": "cover",
            "clip_start_time": 2.0, "clip_duration": 15}
    body.update(overrides)
    return client.post("/api/clips", json=body, headers={"Authorization": f"Bearer {token}"})


@pytest.fixture
def clip_client(app_client):
    """A second fixture, layered on app_client, that also seeds a user + public
    song — split out from app_client itself so the plain register tests above
    don't pay for song/lyric setup they never use."""
    client, _db = app_client
    db_path = _db.get_db_path()
    owner = _db.create_user(db_path, "owner@example.com", "x", "Owner", "now")
    conn = sqlite3.connect(db_path)
    conn.execute("UPDATE users SET email_verified = 1 WHERE id = ?", (owner["id"],))
    conn.execute("INSERT INTO lyrics (id, user_id, brief, lyrics_text, title) VALUES "
                 "(1, ?, 'a song about summer', 'la la la', 'Summer Song')", (owner["id"],))
    conn.execute("INSERT INTO song_variants (id, lyric_id, user_id, style_prompt, genre_tag, status, "
                 "mp3_url, is_public, created_at) VALUES "
                 "(1, 1, ?, 'pop', 'pop', 'complete', '/files/songs/1.mp3', 1, ?)",
                 (owner["id"], NOW.isoformat()))
    conn.commit()
    conn.close()
    import auth
    token = auth.create_token(owner["id"], owner["email"])
    return client, _db, db_path, token


def _event_utm(db_path, event_name):
    conn = sqlite3.connect(db_path)
    row = conn.execute(
        "SELECT utm_source, utm_medium, utm_campaign FROM clip_events WHERE event_name = ? ORDER BY id DESC LIMIT 1",
        (event_name,),
    ).fetchone()
    conn.close()
    return row


def test_publishing_a_clip_with_utm_fields_attaches_them_to_the_event(clip_client):
    client, _db, db_path, token = clip_client
    r = _publish(client, token, utm_source="youtube", utm_medium="video", utm_campaign="tutorial")
    assert r.status_code == 201, r.text
    assert _event_utm(db_path, "clip_published") == ("youtube", "video", "tutorial")


def test_publishing_a_clip_without_utm_fields_leaves_the_event_columns_null(clip_client):
    client, _db, db_path, token = clip_client
    r = _publish(client, token)
    assert r.status_code == 201, r.text
    assert _event_utm(db_path, "clip_published") == (None, None, None)


def test_viewing_a_clip_with_utm_fields_attaches_them_to_the_event(clip_client):
    client, _db, db_path, token = clip_client
    clip_id = _publish(client, token).json()["id"]
    r = client.post(f"/api/clips/{clip_id}/view", json={"utm_source": "tiktok", "utm_medium": "social",
                                                          "utm_campaign": "remix_push"},
                    headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200, r.text
    assert _event_utm(db_path, "clip_viewed") == ("tiktok", "social", "remix_push")


def test_liking_a_clip_with_utm_fields_attaches_them_to_the_event(clip_client):
    client, _db, db_path, token = clip_client
    clip_id = _publish(client, token).json()["id"]
    r = client.post(f"/api/clips/{clip_id}/like", json={"utm_source": "reddit", "utm_medium": "organic",
                                                          "utm_campaign": "aug_launch"},
                    headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200, r.text
    assert _event_utm(db_path, "clip_liked") == ("reddit", "organic", "aug_launch")


def test_liking_a_clip_with_no_body_at_all_still_works(clip_client):
    """The like endpoint's body must stay fully optional — this is the exact bug
    class the pre-Phase-2 review caught on the view endpoint (a bodyless POST
    against a required Pydantic model 422s)."""
    client, _db, db_path, token = clip_client
    clip_id = _publish(client, token).json()["id"]
    r = client.post(f"/api/clips/{clip_id}/like", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200, r.text


def test_starting_a_remix_with_utm_fields_attaches_them_to_the_event(clip_client):
    from unittest.mock import patch

    client, _db, db_path, token = clip_client
    import auth
    conn = sqlite3.connect(db_path)
    remixer = _db.create_user(db_path, "remixer@example.com", "x", "Remixer", "now")
    conn.execute("UPDATE users SET email_verified = 1 WHERE id = ?", (remixer["id"],))
    conn.execute("INSERT INTO song_credits (user_id, balance) VALUES (?, 5)", (remixer["id"],))
    conn.commit()
    conn.close()
    remixer_token = auth.create_token(remixer["id"], remixer["email"])
    clip_id = _publish(client, token).json()["id"]

    def fake_generate_lyrics(**kwargs):
        conn = sqlite3.connect(db_path)
        conn.execute("INSERT INTO lyrics (id, user_id, brief, lyrics_text, title) VALUES (?, ?, '', 'x', 'x')",
                     (555, remixer["id"]))
        conn.commit(); conn.close()
        return {"lyric_id": 555, "lyrics": "x", "title": "x"}

    with patch("lyrics.generate_lyrics", side_effect=fake_generate_lyrics), \
         patch("songs._submit_to_apiframe", return_value="job-abc"):
        r = client.post(f"/api/clips/{clip_id}/remix",
                        json={"utm_source": "email", "utm_medium": "newsletter", "utm_campaign": "sept"},
                        headers={"Authorization": f"Bearer {remixer_token}"})
    assert r.status_code == 202, r.text
    assert _event_utm(db_path, "remix_started") == ("email", "newsletter", "sept")
