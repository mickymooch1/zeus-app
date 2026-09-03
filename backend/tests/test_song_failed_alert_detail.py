"""alert_song_failed used to fire with just an email and a variant_id — no error
text, no song type — even though both were already sitting in scope at its one
call site (webhooks.py's Apiframe FAILED handler). This threads them through, and
dedupes per song_type via the same category-keyed helper as the other alerts (the
error text/email vary every call, so the base exact-text dedup never matched).
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
os.environ.setdefault("JWT_SECRET", "test-secret-for-song-failed-tests")

import alerts  # noqa: E402


def _reset_dedup():
    alerts._ALERT_CATEGORY_STATE.clear()
    alerts._sent_alerts.clear()


# ── alerts.alert_song_failed ────────────────────────────────────────────────

def test_alert_song_failed_includes_error_and_type_and_dedupes_by_type(monkeypatch):
    _reset_dedup()
    sent = []
    monkeypatch.setattr(alerts, "_send_telegram", lambda msg: sent.append(msg) or True)

    alerts.alert_song_failed("a@x.co", 1, error_msg="Suno rendering timeout", song_type="normal")
    alerts.alert_song_failed("b@x.co", 2, error_msg="different error text", song_type="normal")  # suppressed
    alerts.alert_song_failed("c@x.co", 3, error_msg="story render failed", song_type="kids-story")  # own alert

    assert len(sent) == 2, "same song_type back-to-back must dedupe; a different type must not"
    assert "Suno rendering timeout" in sent[0]
    assert "type=normal" in sent[0]
    assert "type=kids-story" in sent[1]


def test_alert_song_failed_defaults_are_backward_compatible(monkeypatch):
    """error_msg/song_type are optional — old-style two-arg calls must still work."""
    _reset_dedup()
    sent = []
    monkeypatch.setattr(alerts, "_send_telegram", lambda msg: sent.append(msg) or True)
    alerts.alert_song_failed("a@x.co", 1)
    assert len(sent) == 1
    assert "no error detail from provider" in sent[0]
    assert "type=normal" in sent[0]


# ── webhooks.py: FAILED handler threads error_msg + kids_story through ────────

def _user():
    return {"id": "wh-user", "email": "webhook@test.co", "subscription_status": "active",
            "subscription_plan": "free", "password_hash": "x", "name": "W", "is_admin": 0,
            "email_verified": 1}


def _setup_db(tmp_path, kids_story: bool):
    import db as _db
    p = tmp_path / "wh.db"
    _db.init_user_tables(p)
    u = _db.create_user(p, email="webhook@test.co", password_hash="x", name="W", tc_accepted_at="n")
    conn = _db._conn(p)
    try:
        conn.execute(
            "INSERT INTO lyrics (id,user_id,title,brief,lyrics_text,kids_story,created_at) "
            "VALUES (1,?,'T','b','la',?,datetime('now'))",
            (u["id"], 1 if kids_story else 0),
        )
        conn.execute(
            "INSERT INTO song_variants (id,lyric_id,user_id,style_prompt,genre_tag,status,take_number) "
            "VALUES (1,1,?,'s','pop','generating',1)",
            (u["id"],),
        )
        conn.commit()
    finally:
        conn.close()
    return p, u


def _post_failed_webhook(db_path, error="Suno render error: out of credits"):
    import webhooks as _webhooks_mod
    import main as _main

    with patch.object(_webhooks_mod, "DB_PATH", str(db_path)), \
         patch("alerts.alert_song_failed") as alert_fn, \
         patch("zeus_ops_agent.on_song_failed"):
        with TestClient(_main.app) as client:
            resp = client.post(
                "/webhooks/apiframe?variant_id=1",
                json={"event": "failed", "error": error},
            )
        return resp, alert_fn


def test_normal_song_failure_passes_error_and_normal_type(tmp_path):
    db_path, _ = _setup_db(tmp_path, kids_story=False)
    resp, alert_fn = _post_failed_webhook(db_path)
    assert resp.status_code == 200
    alert_fn.assert_called_once()
    args, kwargs = alert_fn.call_args
    assert args[0] == "webhook@test.co"
    assert args[1] == 1
    assert kwargs["error_msg"] == "Suno render error: out of credits"
    assert kwargs["song_type"] == "normal"


def test_kids_story_song_failure_passes_kids_story_type(tmp_path):
    db_path, _ = _setup_db(tmp_path, kids_story=True)
    resp, alert_fn = _post_failed_webhook(db_path, error="TTS pipeline error")
    assert resp.status_code == 200
    alert_fn.assert_called_once()
    _, kwargs = alert_fn.call_args
    assert kwargs["song_type"] == "kids-story"
    assert kwargs["error_msg"] == "TTS pipeline error"
