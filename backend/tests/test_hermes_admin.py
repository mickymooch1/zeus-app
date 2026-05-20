import os
import pathlib
import sqlite3
import sys
import uuid
import logging
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock
from unittest.mock import patch

from fastapi.testclient import TestClient

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))

os.environ.setdefault("ANTHROPIC_API_KEY", "test-key-for-tests")
os.environ.setdefault("APIFRAME_API_KEY", "test-apiframe-key")
os.environ.setdefault("SONG_WEBHOOK_URL", "https://zeusaidesign.com/webhooks/apiframe")
os.environ.setdefault("SONG_STORAGE_PATH", "C:/Users/Student/zeus-app/backend/.pytest-hermes-storage")
os.environ.setdefault("SONG_PUBLIC_BASE_URL", "https://example.com/songs")


def _admin_user():
    return {
        "id": "admin-1",
        "email": "admin@example.com",
        "subscription_status": "active",
        "subscription_plan": "enterprise",
        "password_hash": "x",
        "name": "Admin",
        "is_admin": 1,
    }


def _regular_user():
    return {
        "id": "user-1",
        "email": "user@example.com",
        "subscription_status": "active",
        "subscription_plan": "pro",
        "password_hash": "x",
        "name": "User",
        "is_admin": 0,
    }


def _tmp_db_dir():
    path = pathlib.Path("C:/Users/Student/zeus-app/backend/.pytest-hermes") / f"hermes-test-{uuid.uuid4().hex}"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _seed_db(tmp_path):
    import db

    db_path = tmp_path / "zeus.db"
    db.init_user_tables(db_path)
    conn = sqlite3.connect(db_path)
    try:
        conn.execute(
            """INSERT INTO users
               (id, email, password_hash, name, subscription_status, subscription_plan,
                is_admin, created_at, updated_at, has_paid)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            ("u-1", "listener@example.com", "hash", "Listener", "active", "music_pro", 0, "2026-05-20", "2026-05-20", 1),
        )
        conn.execute(
            "INSERT INTO lyrics (id, user_id, brief, lyrics_text, title) VALUES (?, ?, ?, ?, ?)",
            (1, "u-1", "brief", "lyrics", "Test Track"),
        )
        conn.execute(
            """INSERT INTO song_variants
               (id, lyric_id, user_id, style_prompt, genre_tag, status, mp3_url,
                image_url, music_video_url, kling_request_id, webhook_secret, take_number)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                101,
                1,
                "u-1",
                "melodic rap",
                "hiphop",
                "complete",
                "https://cdn.example/song.mp3",
                "https://cdn.example/cover.jpg",
                "https://cdn.example/video.mp4",
                "req_123",
                "secret-value",
                1,
            ),
        )
        conn.execute(
            """INSERT INTO song_variants
               (id, lyric_id, user_id, style_prompt, genre_tag, status, take_number)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (102, 1, "u-1", "ambient pop", "pop", "failed", 2),
        )
        conn.execute(
            """INSERT INTO song_credits
               (user_id, balance, monthly_allowance, animation_balance, animation_monthly_allowance)
               VALUES (?, ?, ?, ?, ?)""",
            ("u-1", 7, 10, 2, 4),
        )
        conn.commit()
    finally:
        conn.close()
    return db_path


class _FakeMessages:
    async def create(self, **kwargs):
        assert "Safe internal context JSON" in kwargs["messages"][0]["content"]
        return SimpleNamespace(content=[SimpleNamespace(text="Hermes sees one recent failed song and masked user data.")])


class _FakeClaude:
    messages = _FakeMessages()


def test_non_admin_gets_403():
    import auth
    import main as _main

    app = _main.app
    app.dependency_overrides[auth.get_current_user] = _regular_user
    try:
        with TestClient(app) as client:
            resp = client.post(
                "/api/admin/hermes/chat",
                json={"message": "Check recent failures"},
                headers={"Authorization": "Bearer fake"},
            )
            assert resp.status_code == 403
    finally:
        app.dependency_overrides.pop(auth.get_current_user, None)


def test_admin_can_chat_with_safe_context():
    import auth
    import main as _main

    db_path = _seed_db(_tmp_db_dir())
    app = _main.app
    app.dependency_overrides[auth.get_current_user] = _admin_user
    try:
        with patch("main.db.get_db_path", return_value=db_path):
            with patch("main.get_anthropic_client", return_value=_FakeClaude()):
                with TestClient(app) as client:
                    resp = client.post(
                        "/api/admin/hermes/chat",
                        json={"message": "Why did animated covers fail?"},
                        headers={"Authorization": "Bearer fake"},
                    )
        assert resp.status_code == 200
        assert "reply" in resp.json()
        assert "Hermes sees" in resp.json()["reply"]
    finally:
        app.dependency_overrides.pop(auth.get_current_user, None)


def test_safe_context_masks_email_and_secret_fields():
    import main as _main

    db_path = _seed_db(_tmp_db_dir())
    context = _main._hermes_build_context(db_path)
    context_text = str(context)
    assert "listener@example.com" not in context_text
    assert "l*******@example.com" in context_text
    assert "secret-value" not in context_text


def test_reply_sanitizer_masks_secret_like_values():
    import main as _main

    reply = _main._hermes_sanitize_reply(
        "Email listener@example.com api_key=sk-ant-thisShouldNotLeak123456789 token: abc123"
    )
    assert "listener@example.com" not in reply
    assert "l*******@example.com" in reply
    assert "thisShouldNotLeak" not in reply
    assert "token: [masked]" in reply


def test_watcher_detects_song_media_and_pipeline_issues():
    import main as _main

    db_path = _seed_db(_tmp_db_dir())
    now = datetime.now(timezone.utc)
    old = (now - timedelta(minutes=90)).isoformat()
    recent = (now - timedelta(minutes=15)).isoformat()

    conn = sqlite3.connect(db_path)
    try:
        conn.execute(
            """INSERT INTO song_variants
               (id, lyric_id, user_id, style_prompt, genre_tag, status, provider_job_id,
                mp3_url, image_url, music_video_url, kling_request_id, created_at, completed_at,
                animate_cover)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (201, 1, "u-1", "trap", "hiphop", "generating", "job-old", None, None, None, None, old, None, 1),
        )
        conn.execute(
            """INSERT INTO song_variants
               (id, lyric_id, user_id, style_prompt, genre_tag, status, provider_job_id,
                mp3_url, image_url, music_video_url, kling_request_id, created_at, completed_at,
                animate_cover)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (202, 1, "u-1", "pop", "pop", "complete", "job-cover", "https://cdn.example/audio.mp3", None, None, None, recent, recent, 1),
        )
        conn.execute(
            """INSERT INTO song_variants
               (id, lyric_id, user_id, style_prompt, genre_tag, status, provider_job_id,
                mp3_url, image_url, music_video_url, kling_request_id, created_at, completed_at,
                animate_cover)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (203, 1, "u-1", "r&b", "rnb", "complete", "job-kling", "https://cdn.example/audio2.mp3", "https://cdn.example/cover.jpg", None, "req_missing", old, old, 1),
        )
        conn.commit()
    finally:
        conn.close()

    issues = _main._hermes_run_health_check(db_path, notify=False, now=now)
    issue_codes = {issue["code"] for issue in issues}

    assert "recent_song_generation_failures" in issue_codes
    assert "missing_apiframe_webhook" in issue_codes
    assert "missing_cover_art" in issue_codes
    assert "paid_missing_music_video" in issue_codes
    assert "kling_pipeline_stalled" in issue_codes
    assert "listener@example.com" not in str(issues)


def test_manual_health_check_requires_admin():
    import auth
    import main as _main

    app = _main.app
    app.dependency_overrides[auth.get_current_user] = _regular_user
    try:
        with TestClient(app) as client:
            resp = client.post(
                "/api/admin/hermes/check",
                headers={"Authorization": "Bearer fake"},
            )
            assert resp.status_code == 403
    finally:
        app.dependency_overrides.pop(auth.get_current_user, None)


def test_manual_health_check_returns_issues_for_admin():
    import auth
    import main as _main

    db_path = _seed_db(_tmp_db_dir())
    app = _main.app
    app.dependency_overrides[auth.get_current_user] = _admin_user
    try:
        with patch("main.db.get_db_path", return_value=db_path):
            with patch("main._hermes_notify_admin", return_value=False):
                with TestClient(app) as client:
                    resp = client.post(
                        "/api/admin/hermes/check",
                        headers={"Authorization": "Bearer fake"},
                    )
        assert resp.status_code == 200
        data = resp.json()
        assert data["ok"] is True
        assert isinstance(data["issues"], list)
        assert data["issue_count"] == len(data["issues"])
        assert data["telegram_alert_sent"] is False
    finally:
        app.dependency_overrides.pop(auth.get_current_user, None)


def test_telegram_alert_format_is_safe_and_actionable():
    import main as _main

    issues = [
        {
            "code": "kling_pipeline_stalled",
            "severity": "medium",
            "title": "Kling pipeline appears stalled",
            "summary": "Paid-user songs have cover art but no animated cover.",
            "count": 2,
            "variants": [{"variant_id": 321}, {"variant_id": 322}],
            "recommended_action": "Check Kling polling logs and fal.ai balance.",
        }
    ]
    message = _main._hermes_format_alert(issues)
    assert "Zeus Hermes Alert" in message
    assert "Issue:" in message
    assert "Details:" in message
    assert "Suggested action:" in message
    assert "321" in message
    assert "TELEGRAM_BOT_TOKEN" not in message


def test_telegram_alert_sends_only_when_configured(monkeypatch):
    import main as _main

    issues = [
        {
            "code": "recent_song_generation_failures",
            "severity": "high",
            "title": "Recent song generation failures",
            "summary": "One song failed.",
            "count": 1,
            "variants": [{"variant_id": 102}],
            "recommended_action": "Check Apiframe logs.",
        }
    ]

    monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
    monkeypatch.delenv("ADMIN_TELEGRAM_CHAT_ID", raising=False)
    monkeypatch.delenv("TELEGRAM_BOT_TOKEN2", raising=False)
    monkeypatch.delenv("ADMIN_TELEGRAM_CHAT_ID2", raising=False)
    assert _main._hermes_notify_admin(issues) is False

    calls = []

    class _Resp:
        status_code = 200
        text = "ok"

    def _fake_post(url, json, timeout):
        calls.append((url, json, timeout))
        return _Resp()

    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "secret-token")
    monkeypatch.setenv("ADMIN_TELEGRAM_CHAT_ID", "12345")
    monkeypatch.setattr(_main.httpx, "post", _fake_post)

    assert _main._hermes_notify_admin(issues) is True
    assert len(calls) == 1
    assert "secret-token" in calls[0][0]
    assert calls[0][1]["chat_id"] == "12345"
    assert "Zeus Hermes Alert" in calls[0][1]["text"]
    assert "secret-token" not in calls[0][1]["text"]


def test_hermes_telegram_config_prefers_new_env_names(monkeypatch):
    import main as _main

    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "old-token")
    monkeypatch.setenv("ADMIN_TELEGRAM_CHAT_ID", "111")
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN2", "new-token")
    monkeypatch.setenv("ADMIN_TELEGRAM_CHAT_ID2", "222")

    token, chat_id = _main._hermes_telegram_config()

    assert token == "new-token"
    assert chat_id == "222"


def test_hermes_telegram_webhook_replies_to_authorized_admin(monkeypatch, caplog):
    import main as _main

    caplog.set_level(logging.INFO, logger="zeus")
    db_path = _seed_db(_tmp_db_dir())
    replies = []

    async def _fake_reply(token, chat_id, text, parse_mode=None):
        replies.append({"token": token, "chat_id": chat_id, "text": text})

    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "old-telegram-secret")
    monkeypatch.setenv("ADMIN_TELEGRAM_CHAT_ID", "99999")
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN2", "telegram-secret")
    monkeypatch.setenv("ADMIN_TELEGRAM_CHAT_ID2", "12345")

    with patch("main.db.get_db_path", return_value=db_path):
        with patch("main.get_anthropic_client", return_value=_FakeClaude()):
            with patch("main._telegram_reply", new=AsyncMock(side_effect=_fake_reply)):
                with TestClient(_main.app) as client:
                    resp = client.post(
                        "/webhooks/telegram/hermes",
                        json={
                            "message": {
                                "chat": {"id": 12345, "type": "private"},
                                "text": "Check recent song failures",
                            }
                        },
                    )

    assert resp.status_code == 200
    assert resp.json()["ok"] is True
    assert resp.json()["handled"] is True
    assert len(replies) == 1
    assert replies[0]["chat_id"] == 12345
    assert replies[0]["token"] == "telegram-secret"
    assert "Hermes sees" in replies[0]["text"]
    assert "telegram-secret" not in replies[0]["text"]
    assert "received authorized admin message" in caplog.text
    assert "Check recent song failures" not in caplog.text


def test_hermes_telegram_webhook_blocks_unknown_chat(monkeypatch):
    import main as _main

    monkeypatch.setenv("TELEGRAM_BOT_TOKEN2", "telegram-secret")
    monkeypatch.setenv("ADMIN_TELEGRAM_CHAT_ID2", "12345")

    with patch("main.get_anthropic_client") as mock_client:
        with patch("main._telegram_reply", new=AsyncMock()) as mock_reply:
            with TestClient(_main.app) as client:
                mock_client.reset_mock()
                resp = client.post(
                    "/webhooks/telegram/hermes",
                    json={
                        "message": {
                            "chat": {"id": 99999, "type": "private"},
                            "text": "Check recent song failures",
                        }
                    },
                )

    assert resp.status_code == 200
    assert resp.json()["ok"] is True
    assert resp.json()["handled"] is False
    mock_client.assert_not_called()
    mock_reply.assert_not_called()
