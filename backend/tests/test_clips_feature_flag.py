"""Zeus Clips pre-deploy gate: CLIPS_ENABLED env var (default off). While off,
clip CREATION (publish, upload-media) is admin-only; the public feed and clip
detail pages work for anyone with a link either way — the flag only controls
whether NEW clips can be made, never visibility of ones that already exist.
Once flipped to true, creation opens to everyone. GET /api/clips/config
exposes the raw flag (not admin-aware) so the frontend can combine it with
the current user's own is_admin to decide whether to show "Create Clip".
"""
import importlib
import io
import os
import pathlib
import sqlite3
import sys
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient
from PIL import Image

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))
os.environ.setdefault("ANTHROPIC_API_KEY", "test-key")
os.environ.setdefault("APIFRAME_API_KEY", "test-key")
os.environ.setdefault("SONG_STORAGE_PATH", "/tmp/test_songs")
os.environ.setdefault("SONG_PUBLIC_BASE_URL", "https://example.com/files/songs")
os.environ.setdefault("SONG_WEBHOOK_URL", "https://zeusaidesign.com/webhooks/apiframe")
os.environ.setdefault("JWT_SECRET", "test-secret-for-clips-feature-flag-tests")

NOW = datetime(2026, 9, 23, 12, 0, 0, tzinfo=timezone.utc)


def _real_jpeg():
    buf = io.BytesIO()
    Image.new("RGB", (8, 8), (10, 20, 30)).save(buf, format="JPEG")
    return buf.getvalue()


@pytest.fixture
def app_client(tmp_path, monkeypatch):
    monkeypatch.delenv("CLIPS_ENABLED", raising=False)  # default: off, unless a test sets it
    monkeypatch.setenv("ZEUS_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("SONG_STORAGE_PATH", str(tmp_path / "songs"))
    monkeypatch.setenv("CLIP_STORAGE_PATH", str(tmp_path / "clips"))
    import db as _db
    importlib.reload(_db)
    import main as _main
    importlib.reload(_main)
    _main.limiter.enabled = False

    db_path = _db.get_db_path()
    admin = _db.create_user(db_path, "admin@example.com", "x", "Admin", "now")
    regular = _db.create_user(db_path, "regular@example.com", "x", "Regular", "now")
    conn = sqlite3.connect(db_path)
    conn.execute("UPDATE users SET email_verified = 1, subscription_status = 'active', "
                 "subscription_plan = 'music_starter' WHERE id IN (?, ?)", (admin["id"], regular["id"]))
    conn.execute("UPDATE users SET is_admin = 1 WHERE id = ?", (admin["id"],))
    conn.execute("INSERT INTO lyrics (id, user_id, brief, lyrics_text, title) VALUES "
                 "(1, ?, 'b', 'la la', 'Admin Song')", (admin["id"],))
    conn.execute("INSERT INTO song_variants (id, lyric_id, user_id, style_prompt, genre_tag, status, "
                 "mp3_url, is_public, created_at) VALUES "
                 "(1, 1, ?, 'pop', 'pop', 'complete', '/files/songs/1.mp3', 1, ?)",
                 (admin["id"], NOW.isoformat()))
    conn.execute("INSERT INTO lyrics (id, user_id, brief, lyrics_text, title) VALUES "
                 "(2, ?, 'b', 'la la', 'Regular Song')", (regular["id"],))
    conn.execute("INSERT INTO song_variants (id, lyric_id, user_id, style_prompt, genre_tag, status, "
                 "mp3_url, is_public, created_at) VALUES "
                 "(2, 2, ?, 'pop', 'pop', 'complete', '/files/songs/2.mp3', 1, ?)",
                 (regular["id"], NOW.isoformat()))
    conn.commit()
    conn.close()

    import auth
    admin_token = auth.create_token(admin["id"], admin["email"], is_admin=True)
    regular_token = auth.create_token(regular["id"], regular["email"])
    with TestClient(_main.app) as client:
        yield client, db_path, admin_token, regular_token


def auth_hdr(token):
    return {"Authorization": f"Bearer {token}"}


def _publish(client, token, song_id, **overrides):
    body = {"song_id": song_id, "caption": "", "media_type": "cover", "clip_start_time": 0, "clip_duration": 15}
    body.update(overrides)
    return client.post("/api/clips", json=body, headers=auth_hdr(token))


# ── GET /api/clips/config ─────────────────────────────────────────────────

def test_config_reports_disabled_by_default(app_client):
    client, *_ = app_client
    r = client.get("/api/clips/config")
    assert r.status_code == 200
    assert r.json()["enabled"] is False


def test_config_reports_enabled_when_the_env_var_is_set(app_client, monkeypatch):
    monkeypatch.setenv("CLIPS_ENABLED", "true")
    client, *_ = app_client
    assert client.get("/api/clips/config").json()["enabled"] is True


def test_config_requires_no_auth(app_client):
    client, *_ = app_client
    assert client.get("/api/clips/config").status_code == 200


# ── publish: admin-only while disabled, everyone once enabled ───────────────

def test_publish_is_admin_only_while_disabled(app_client):
    client, db_path, admin_token, regular_token = app_client
    r = _publish(client, regular_token, song_id=2)
    assert r.status_code == 403


def test_publish_works_for_admin_while_disabled(app_client):
    client, db_path, admin_token, regular_token = app_client
    r = _publish(client, admin_token, song_id=1)
    assert r.status_code == 201, r.text


def test_publish_works_for_everyone_once_enabled(app_client, monkeypatch):
    monkeypatch.setenv("CLIPS_ENABLED", "true")
    client, db_path, admin_token, regular_token = app_client
    r = _publish(client, regular_token, song_id=2)
    assert r.status_code == 201, r.text


# ── upload-media: same gate ──────────────────────────────────────────────

def test_upload_media_is_admin_only_while_disabled(app_client):
    client, db_path, admin_token, regular_token = app_client
    r = client.post("/api/clips/upload-media", files={"file": ("photo.jpg", _real_jpeg(), "image/jpeg")},
                    data={"media_type": "image"}, headers=auth_hdr(regular_token))
    assert r.status_code == 403


def test_upload_media_works_for_admin_while_disabled(app_client):
    client, db_path, admin_token, regular_token = app_client
    r = client.post("/api/clips/upload-media", files={"file": ("photo.jpg", _real_jpeg(), "image/jpeg")},
                    data={"media_type": "image"}, headers=auth_hdr(admin_token))
    assert r.status_code == 200, r.text


def test_upload_media_works_for_everyone_once_enabled(app_client, monkeypatch):
    monkeypatch.setenv("CLIPS_ENABLED", "true")
    client, db_path, admin_token, regular_token = app_client
    r = client.post("/api/clips/upload-media", files={"file": ("photo.jpg", _real_jpeg(), "image/jpeg")},
                    data={"media_type": "image"}, headers=auth_hdr(regular_token))
    assert r.status_code == 200, r.text


# ── the flag never touches read access ──────────────────────────────────────

def test_feed_and_detail_are_unaffected_by_the_flag(app_client):
    client, db_path, admin_token, regular_token = app_client
    clip_id = _publish(client, admin_token, song_id=1).json()["id"]
    assert client.get("/api/clips?sort=new").status_code == 200
    assert client.get(f"/api/clips/{clip_id}").status_code == 200
    # a logged-out visitor too — no auth header at all
    assert client.get(f"/api/clips/{clip_id}", headers={}).status_code == 200
