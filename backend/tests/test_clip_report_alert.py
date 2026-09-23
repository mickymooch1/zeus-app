"""Zeus Clips Phase 3 — "Porick alerts" (build brief): reporting a clip pings
admin the moment it happens, same as every other moderation-relevant event in
this codebase (alert_signup_flag, alert_payment, ...). Pins that
POST /api/clips/{id}/report calls alerts.alert_clip_reported with the clip,
reporter and reason — trusts alerts.py's own formatting/dedup machinery,
matching how test_lyrics_failure_alert.py etc. test their calling sites
rather than re-testing alerts.py's internals.
"""
import importlib
import os
import pathlib
import sqlite3
import sys
from datetime import datetime, timezone
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))
os.environ.setdefault("ANTHROPIC_API_KEY", "test-key")
os.environ.setdefault("APIFRAME_API_KEY", "test-key")
os.environ.setdefault("SONG_STORAGE_PATH", "/tmp/test_songs")
os.environ.setdefault("SONG_PUBLIC_BASE_URL", "https://example.com/files/songs")
os.environ.setdefault("SONG_WEBHOOK_URL", "https://zeusaidesign.com/webhooks/apiframe")
os.environ.setdefault("JWT_SECRET", "test-secret-for-clip-report-alert-tests")

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

    db_path = _db.get_db_path()
    owner = _db.create_user(db_path, "owner@example.com", "x", "Owner", "now")
    reporter = _db.create_user(db_path, "reporter@example.com", "x", "Reporter", "now")
    conn = sqlite3.connect(db_path)
    conn.execute("UPDATE users SET email_verified = 1 WHERE id IN (?, ?)", (owner["id"], reporter["id"]))
    conn.execute("INSERT INTO lyrics (id, user_id, brief, lyrics_text, title) VALUES "
                 "(1, ?, 'b', 'la la', 'Test Song')", (owner["id"],))
    conn.execute("INSERT INTO song_variants (id, lyric_id, user_id, style_prompt, genre_tag, status, "
                 "mp3_url, is_public, created_at) VALUES "
                 "(1, 1, ?, 'pop', 'pop', 'complete', '/files/songs/1.mp3', 1, ?)",
                 (owner["id"], NOW.isoformat()))
    conn.commit()
    conn.close()

    import auth
    reporter_token = auth.create_token(reporter["id"], reporter["email"])
    with TestClient(_main.app) as client:
        yield client, _db, db_path, reporter_token


def _publish(client, token):
    body = {"song_id": 1, "caption": "", "media_type": "cover", "clip_start_time": 0, "clip_duration": 15}
    return client.post("/api/clips", json=body, headers={"Authorization": f"Bearer {token}"})


def test_reporting_a_clip_fires_an_admin_alert(app_client):
    client, _db, db_path, reporter_token = app_client
    # Publish as the owner (need their own token) — simplest: use reporter's
    # token isn't the owner's song, so seed via a second user quickly.
    import auth
    owner = _db.get_user_by_email(db_path, "owner@example.com")
    owner_token = auth.create_token(owner["id"], owner["email"])
    clip_id = _publish(client, owner_token).json()["id"]

    with patch("alerts.alert_clip_reported") as alert_fn:
        r = client.post(f"/api/clips/{clip_id}/report", json={"reason": "spam"},
                        headers={"Authorization": f"Bearer {reporter_token}"})
    assert r.status_code == 200, r.text
    assert alert_fn.called
    args, kwargs = alert_fn.call_args
    call = dict(zip(["clip_id", "reporter_id", "reason"], args), **kwargs)
    assert call["clip_id"] == clip_id
    assert call["reason"] == "spam"


def test_a_failed_alert_never_breaks_the_report_endpoint(app_client):
    """The alert is best-effort — a Telegram/network hiccup in alerts.py must
    never turn a successful report into a 500."""
    client, _db, db_path, reporter_token = app_client
    import auth
    owner = _db.get_user_by_email(db_path, "owner@example.com")
    owner_token = auth.create_token(owner["id"], owner["email"])
    clip_id = _publish(client, owner_token).json()["id"]

    with patch("alerts.alert_clip_reported", side_effect=RuntimeError("boom")):
        r = client.post(f"/api/clips/{clip_id}/report", json={"reason": "spam"},
                        headers={"Authorization": f"Bearer {reporter_token}"})
    assert r.status_code == 200, r.text
