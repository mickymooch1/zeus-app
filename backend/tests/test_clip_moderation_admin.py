"""Zeus Clips Phase 3 — moderation admin UI's backend: list reported clips,
hide a clip, restore a hidden clip. Admin-only, same `is_admin` gate as every
other /admin/* endpoint (see main.py's admin_list_users). Reuses clips.py's
existing list_reported_clips/set_clip_status — no new DB-layer logic, this is
just the HTTP surface the brief's Phase 3 review-queue UI calls.
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
os.environ.setdefault("JWT_SECRET", "test-secret-for-clip-moderation-admin-tests")

NOW = datetime(2026, 9, 23, 12, 0, 0, tzinfo=timezone.utc)


@pytest.fixture
def app_client(tmp_path, monkeypatch):
    monkeypatch.setenv("ZEUS_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("SONG_STORAGE_PATH", str(tmp_path / "songs"))
    monkeypatch.setenv("CLIP_STORAGE_PATH", str(tmp_path / "clips"))
    # This suite tests moderation, not the CLIPS_ENABLED gate (see
    # test_clips_feature_flag.py for that) — open creation to everyone so the
    # non-admin fixture user can publish as before the flag existed.
    monkeypatch.setenv("CLIPS_ENABLED", "true")
    import db as _db
    importlib.reload(_db)
    import clips as _clips
    importlib.reload(_clips)
    import main as _main
    importlib.reload(_main)
    _main.limiter.enabled = False

    db_path = _db.get_db_path()
    owner = _db.create_user(db_path, "owner@example.com", "x", "Owner", "now")
    reporter = _db.create_user(db_path, "reporter@example.com", "x", "Reporter", "now")
    admin = _db.create_user(db_path, "admin@example.com", "x", "Admin", "now")
    conn = sqlite3.connect(db_path)
    conn.execute("UPDATE users SET email_verified = 1 WHERE id IN (?, ?, ?)", (owner["id"], reporter["id"], admin["id"]))
    conn.execute("UPDATE users SET is_admin = 1 WHERE id = ?", (admin["id"],))
    conn.execute("INSERT INTO lyrics (id, user_id, brief, lyrics_text, title) VALUES "
                 "(1, ?, 'b', 'la la', 'Test Song')", (owner["id"],))
    conn.execute("INSERT INTO song_variants (id, lyric_id, user_id, style_prompt, genre_tag, status, "
                 "mp3_url, is_public, created_at) VALUES "
                 "(1, 1, ?, 'pop', 'pop', 'complete', '/files/songs/1.mp3', 1, ?)",
                 (owner["id"], NOW.isoformat()))
    conn.commit()
    conn.close()

    import auth
    owner_token = auth.create_token(owner["id"], owner["email"])
    reporter_token = auth.create_token(reporter["id"], reporter["email"])
    admin_token = auth.create_token(admin["id"], admin["email"], is_admin=True)
    with TestClient(_main.app) as client:
        yield client, _clips, db_path, owner_token, reporter_token, admin_token


def _publish(client, token):
    body = {"song_id": 1, "caption": "check", "media_type": "cover", "clip_start_time": 0, "clip_duration": 15}
    return client.post("/api/clips", json=body, headers={"Authorization": f"Bearer {token}"}).json()["id"]


def auth_hdr(token):
    return {"Authorization": f"Bearer {token}"}


# ── GET /admin/clips/reported ─────────────────────────────────────────────────

def test_reported_clips_requires_admin(app_client):
    client, *_ , owner_token, _reporter_token, _admin_token = app_client
    assert client.get("/admin/clips/reported", headers=auth_hdr(owner_token)).status_code == 403


def test_reported_clips_requires_auth(app_client):
    client, *_ = app_client
    assert client.get("/admin/clips/reported").status_code == 401


def test_reported_clips_lists_a_report(app_client):
    client, _clips_mod, db_path, owner_token, reporter_token, admin_token = app_client
    clip_id = _publish(client, owner_token)
    client.post(f"/api/clips/{clip_id}/report", json={"reason": "spam"}, headers=auth_hdr(reporter_token))

    r = client.get("/admin/clips/reported", headers=auth_hdr(admin_token))
    assert r.status_code == 200, r.text
    reports = r.json()["reports"]
    assert any(rep["clip_id"] == clip_id and rep["reason"] == "spam" for rep in reports)


def test_reported_clips_is_empty_when_nothing_reported(app_client):
    client, *_ , admin_token = app_client
    r = client.get("/admin/clips/reported", headers=auth_hdr(admin_token))
    assert r.status_code == 200
    assert r.json()["reports"] == []


# ── POST /admin/clips/{id}/hide ───────────────────────────────────────────────

def test_hide_requires_admin(app_client):
    client, *_ , owner_token, _reporter_token, _admin_token = app_client
    clip_id = _publish(client, owner_token)
    assert client.post(f"/admin/clips/{clip_id}/hide", headers=auth_hdr(owner_token)).status_code == 403


def test_hide_removes_it_from_the_public_feed_and_detail(app_client):
    client, *_ , owner_token, _reporter_token, admin_token = app_client
    clip_id = _publish(client, owner_token)

    r = client.post(f"/admin/clips/{clip_id}/hide", headers=auth_hdr(admin_token))
    assert r.status_code == 200, r.text
    assert client.get(f"/api/clips/{clip_id}").status_code == 404
    ids = [c["id"] for c in client.get("/api/clips?sort=new").json()["clips"]]
    assert clip_id not in ids


def test_hide_a_nonexistent_clip_404s(app_client):
    client, *_ , admin_token = app_client
    assert client.post("/admin/clips/999/hide", headers=auth_hdr(admin_token)).status_code == 404


# ── POST /admin/clips/{id}/restore ────────────────────────────────────────────

def test_restore_requires_admin(app_client):
    client, *_ , owner_token, _reporter_token, admin_token = app_client
    clip_id = _publish(client, owner_token)
    client.post(f"/admin/clips/{clip_id}/hide", headers=auth_hdr(admin_token))
    assert client.post(f"/admin/clips/{clip_id}/restore", headers=auth_hdr(owner_token)).status_code == 403


def test_restore_brings_a_hidden_clip_back(app_client):
    client, *_ , owner_token, _reporter_token, admin_token = app_client
    clip_id = _publish(client, owner_token)
    client.post(f"/admin/clips/{clip_id}/hide", headers=auth_hdr(admin_token))
    assert client.get(f"/api/clips/{clip_id}").status_code == 404

    r = client.post(f"/admin/clips/{clip_id}/restore", headers=auth_hdr(admin_token))
    assert r.status_code == 200, r.text
    assert client.get(f"/api/clips/{clip_id}").status_code == 200


def test_restore_a_nonexistent_clip_404s(app_client):
    client, *_ , admin_token = app_client
    assert client.post("/admin/clips/999/restore", headers=auth_hdr(admin_token)).status_code == 404
