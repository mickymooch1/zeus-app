"""Block user hardening (2026-09-23 follow-up): abuse_blocklist previously only
gated registration — a blocked email's EXISTING account could still publish,
upload, like, report and remix freely. Every clip-mutating endpoint now
re-checks the caller's email against abuse_blocklist on every request (see
main.py's _reject_if_blocked), not just at signup. Read-only endpoints (view,
get, feed) and unlike are deliberately NOT gated — see the brief's exact
five-verb list: publish, upload, like, report, remix.
"""
import importlib
import io
import os
import pathlib
import sqlite3
import sys
from datetime import datetime, timezone
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from PIL import Image

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))
os.environ.setdefault("ANTHROPIC_API_KEY", "test-key")
os.environ.setdefault("APIFRAME_API_KEY", "test-key")
os.environ.setdefault("SONG_STORAGE_PATH", "/tmp/test_songs")
os.environ.setdefault("SONG_PUBLIC_BASE_URL", "https://example.com/files/songs")
os.environ.setdefault("SONG_WEBHOOK_URL", "https://zeusaidesign.com/webhooks/apiframe")
os.environ.setdefault("JWT_SECRET", "test-secret-for-blocked-user-tests")

NOW = datetime(2026, 9, 23, 12, 0, 0, tzinfo=timezone.utc)


def _real_jpeg():
    buf = io.BytesIO()
    Image.new("RGB", (8, 8), (10, 20, 30)).save(buf, format="JPEG")
    return buf.getvalue()


@pytest.fixture
def app_client(tmp_path, monkeypatch):
    monkeypatch.setenv("ZEUS_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("SONG_STORAGE_PATH", str(tmp_path / "songs"))
    monkeypatch.setenv("CLIP_STORAGE_PATH", str(tmp_path / "clips"))
    import db as _db
    importlib.reload(_db)
    import clips as _clips
    importlib.reload(_clips)
    import main as _main
    importlib.reload(_main)
    _main.limiter.enabled = False

    db_path = _db.get_db_path()
    blocked = _db.create_user(db_path, "blocked@example.com", "x", "Blocked", "now")
    ok_user = _db.create_user(db_path, "ok@example.com", "x", "OK", "now")
    conn = sqlite3.connect(db_path)
    conn.execute("UPDATE users SET email_verified = 1, subscription_status = 'active', "
                 "subscription_plan = 'music_starter' WHERE id IN (?, ?)", (blocked["id"], ok_user["id"]))
    conn.execute("INSERT INTO song_credits (user_id, balance) VALUES (?, 5)", (blocked["id"],))
    conn.execute("INSERT INTO song_credits (user_id, balance) VALUES (?, 5)", (ok_user["id"],))
    conn.execute("INSERT INTO lyrics (id, user_id, brief, lyrics_text, title) VALUES "
                 "(1, ?, 'b', 'la la', 'Test Song')", (blocked["id"],))
    conn.execute("INSERT INTO song_variants (id, lyric_id, user_id, style_prompt, genre_tag, status, "
                 "mp3_url, is_public, created_at) VALUES "
                 "(1, 1, ?, 'pop', 'pop', 'complete', '/files/songs/1.mp3', 1, ?)",
                 (blocked["id"], NOW.isoformat()))
    # A second song owned by ok_user, for tests where the BLOCKED user needs
    # to act on a clip they don't themselves own (like/report/remix/view).
    conn.execute("INSERT INTO lyrics (id, user_id, brief, lyrics_text, title) VALUES "
                 "(2, ?, 'b', 'la la', 'OK Song')", (ok_user["id"],))
    conn.execute("INSERT INTO song_variants (id, lyric_id, user_id, style_prompt, genre_tag, status, "
                 "mp3_url, is_public, created_at) VALUES "
                 "(2, 2, ?, 'pop', 'pop', 'complete', '/files/songs/2.mp3', 1, ?)",
                 (ok_user["id"], NOW.isoformat()))
    conn.commit()
    conn.close()

    import auth
    blocked_token = auth.create_token(blocked["id"], blocked["email"])
    ok_token = auth.create_token(ok_user["id"], ok_user["email"])
    with TestClient(_main.app) as client:
        yield client, _db, _clips, db_path, blocked, ok_user, blocked_token, ok_token


def auth_hdr(token):
    return {"Authorization": f"Bearer {token}"}


def block(db_module, db_path, email):
    import signup_guard
    db_module.add_to_blocklist(db_path, "email", signup_guard.normalize_email(email), "test block")


def _publish(client, token, **overrides):
    body = {"song_id": 1, "caption": "", "media_type": "cover", "clip_start_time": 0, "clip_duration": 15}
    body.update(overrides)
    return client.post("/api/clips", json=body, headers=auth_hdr(token))


# ── publish ────────────────────────────────────────────────────────────────

def test_blocked_user_cannot_publish_a_clip(app_client):
    client, _db, _clips, db_path, blocked, *_ , blocked_token, _ok_token = app_client
    block(_db, db_path, blocked["email"])
    r = _publish(client, blocked_token)
    assert r.status_code == 403
    assert "restricted" in r.json()["detail"].lower()


def test_unblocked_user_can_still_publish(app_client):
    client, *_ , blocked_token, _ok_token = app_client
    r = _publish(client, blocked_token)
    assert r.status_code == 201, r.text


# ── upload-media ──────────────────────────────────────────────────────────

def test_blocked_user_cannot_upload_media(app_client):
    client, _db, _clips, db_path, blocked, *_ , blocked_token, _ok_token = app_client
    block(_db, db_path, blocked["email"])
    r = client.post("/api/clips/upload-media", files={"file": ("photo.jpg", _real_jpeg(), "image/jpeg")},
                    data={"media_type": "image"}, headers=auth_hdr(blocked_token))
    assert r.status_code == 403
    assert "restricted" in r.json()["detail"].lower()


# ── like ──────────────────────────────────────────────────────────────────

def test_blocked_user_cannot_like_a_clip(app_client):
    client, _db, _clips, db_path, blocked, ok_user, blocked_token, ok_token = app_client
    clip_id = _publish(client, ok_token, song_id=2).json()["id"]
    block(_db, db_path, blocked["email"])
    r = client.post(f"/api/clips/{clip_id}/like", headers=auth_hdr(blocked_token))
    assert r.status_code == 403
    assert "restricted" in r.json()["detail"].lower()


def test_blocked_user_can_still_unlike(app_client):
    """Deliberately NOT gated — see module docstring. A block must not strand
    a like a user made before being blocked."""
    client, _db, _clips, db_path, blocked, ok_user, blocked_token, ok_token = app_client
    clip_id = _publish(client, ok_token, song_id=2).json()["id"]
    client.post(f"/api/clips/{clip_id}/like", headers=auth_hdr(blocked_token))
    block(_db, db_path, blocked["email"])
    r = client.delete(f"/api/clips/{clip_id}/like", headers=auth_hdr(blocked_token))
    assert r.status_code == 200


# ── report ────────────────────────────────────────────────────────────────

def test_blocked_user_cannot_report_a_clip(app_client):
    client, _db, _clips, db_path, blocked, ok_user, blocked_token, ok_token = app_client
    clip_id = _publish(client, ok_token, song_id=2).json()["id"]
    block(_db, db_path, blocked["email"])
    r = client.post(f"/api/clips/{clip_id}/report", json={"reason": "spam"}, headers=auth_hdr(blocked_token))
    assert r.status_code == 403
    assert "restricted" in r.json()["detail"].lower()


# ── remix ─────────────────────────────────────────────────────────────────

def test_blocked_user_cannot_start_a_remix(app_client):
    client, _db, _clips, db_path, blocked, ok_user, blocked_token, ok_token = app_client
    clip_id = _publish(client, ok_token, song_id=2).json()["id"]
    block(_db, db_path, blocked["email"])
    with patch("lyrics.generate_lyrics") as gen_lyrics, patch("songs._submit_to_apiframe") as submit:
        r = client.post(f"/api/clips/{clip_id}/remix", headers=auth_hdr(blocked_token))
    assert r.status_code == 403
    assert "restricted" in r.json()["detail"].lower()
    assert not gen_lyrics.called and not submit.called, "must be rejected before any generation work starts"


# ── views/feed/detail stay open (read-only, not in the brief's gated list) ──

def test_blocked_user_can_still_view_the_feed_and_a_clip(app_client):
    client, _db, _clips, db_path, blocked, ok_user, blocked_token, ok_token = app_client
    clip_id = _publish(client, ok_token, song_id=2).json()["id"]
    block(_db, db_path, blocked["email"])
    assert client.get("/api/clips?sort=new", headers=auth_hdr(blocked_token)).status_code == 200
    assert client.get(f"/api/clips/{clip_id}", headers=auth_hdr(blocked_token)).status_code == 200
