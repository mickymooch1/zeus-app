import os
import pathlib
import sqlite3
import sys
import uuid
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
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
    finally:
        app.dependency_overrides.pop(auth.get_current_user, None)
