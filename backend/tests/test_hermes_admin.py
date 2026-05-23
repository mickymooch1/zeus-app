import os
import pathlib
import sys

from fastapi.testclient import TestClient

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))

os.environ.setdefault("ANTHROPIC_API_KEY", "test-key-for-tests")
os.environ.setdefault("APIFRAME_API_KEY", "test-apiframe-key")
os.environ.setdefault("SONG_WEBHOOK_URL", "https://zeusaidesign.com/webhooks/apiframe")
os.environ.setdefault("SONG_STORAGE_PATH", "C:/Users/Student/zeus-app/backend/.pytest-hermes-storage")
os.environ.setdefault("SONG_PUBLIC_BASE_URL", "https://example.com/songs")


def test_hermes_chat_endpoint_is_offline():
    import main as _main

    with TestClient(_main.app) as client:
        resp = client.post(
            "/api/admin/hermes/chat",
            json={"message": "Check recent song failures"},
            headers={"Authorization": "Bearer fake"},
        )

    assert resp.status_code in {404, 405}


def test_hermes_health_check_endpoint_is_offline():
    import main as _main

    with TestClient(_main.app) as client:
        resp = client.post(
            "/api/admin/hermes/check",
            headers={"Authorization": "Bearer fake"},
        )

    assert resp.status_code in {404, 405}


def test_hermes_watcher_helpers_are_not_registered():
    import main as _main

    assert not hasattr(_main, "_hermes_start_watcher_background")
    assert not hasattr(_main, "_hermes_run_health_check")
    assert not hasattr(_main, "_hermes_notify_admin")


def test_existing_telegram_admin_bot_remains_available():
    import main as _main

    assert hasattr(_main, "telegram_webhook")
    assert hasattr(_main, "post_to_telegram")
