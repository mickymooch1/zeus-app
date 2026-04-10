"""
Tests for the session auth security fix:
- GET /sessions requires auth and returns only the calling user's sessions
- GET /history/{id} requires auth and returns 404 for sessions owned by other users
- HistoryStore.list_sessions_for_user filters correctly
- HistoryStore.get_transcript_if_owner enforces ownership
"""
import os
import pathlib
import sys
from datetime import datetime
from unittest.mock import MagicMock

import pytest

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))
os.environ.setdefault("ANTHROPIC_API_KEY", "test-key-for-tests")


# ── HistoryStore unit tests ───────────────────────────────────────────────────

def _make_store(tmp_path):
    """Create a HistoryStore pointed at a temp directory."""
    from zeus_agent import HistoryStore
    store = object.__new__(HistoryStore)
    store.dir = pathlib.Path(tmp_path)
    store.db_path = store.dir / "zeus.db"
    store._init_db()
    return store


def test_list_sessions_for_user_filters_by_owner(tmp_path):
    store = _make_store(tmp_path)
    t = datetime(2026, 1, 1, 12, 0)

    store.save_session("sess-alice", t, 2, "Hello", user_id="user-alice")
    store.save_session("sess-bob",   t, 3, "World", user_id="user-bob")
    store.save_session("sess-anon",  t, 1, "Anon")  # no user_id

    result = store.list_sessions_for_user("user-alice")
    ids = [r["id"] for r in result]
    assert ids == ["sess-alice"], f"Expected only alice's session, got {ids}"


def test_list_sessions_for_user_empty_when_no_sessions(tmp_path):
    store = _make_store(tmp_path)
    result = store.list_sessions_for_user("user-nobody")
    assert result == []


def test_get_transcript_if_owner_returns_transcript_for_correct_user(tmp_path):
    store = _make_store(tmp_path)
    t = datetime(2026, 1, 1, 12, 0)
    store.save_session("sess-1", t, 1, "Hi", user_id="user-a")
    store.log_turn("sess-1", 1, "user", "Hi there")
    store.log_turn("sess-1", 1, "zeus", "Hello!")

    result = store.get_transcript_if_owner("sess-1", "user-a")
    assert result is not None
    assert len(result) == 2
    assert result[0]["role"] == "user"
    assert result[1]["role"] == "zeus"


def test_get_transcript_if_owner_returns_none_for_wrong_user(tmp_path):
    store = _make_store(tmp_path)
    t = datetime(2026, 1, 1, 12, 0)
    store.save_session("sess-1", t, 1, "Hi", user_id="user-a")
    store.log_turn("sess-1", 1, "user", "Hi there")

    result = store.get_transcript_if_owner("sess-1", "user-b")
    assert result is None


def test_get_transcript_if_owner_returns_none_for_orphan_session(tmp_path):
    """Sessions with no user_id should not be accessible by any user."""
    store = _make_store(tmp_path)
    t = datetime(2026, 1, 1, 12, 0)
    store.save_session("sess-orphan", t, 1, "Old session")  # no user_id
    store.log_turn("sess-orphan", 1, "user", "Old message")

    result = store.get_transcript_if_owner("sess-orphan", "user-a")
    assert result is None


# ── Endpoint tests ────────────────────────────────────────────────────────────

def _make_user(user_id="user-1"):
    return {
        "id": user_id,
        "email": f"{user_id}@example.com",
        "subscription_status": "active",
        "subscription_plan": "pro",
        "password_hash": "x",
        "name": "Test",
        "is_admin": 0,
    }


def test_sessions_endpoint_requires_auth():
    import auth
    from main import app
    from fastapi.testclient import TestClient

    app.dependency_overrides.pop(auth.get_current_user, None)
    with TestClient(app) as client:
        resp = client.get("/sessions")
    assert resp.status_code == 401


def test_sessions_endpoint_returns_only_users_sessions():
    import auth
    from main import app
    from fastapi.testclient import TestClient
    import main as _main
    from unittest.mock import patch

    mock_store = MagicMock()
    mock_store.list_sessions_for_user.return_value = [
        {"id": "sess-1", "started": "2026-01-01T12:00:00", "turns": 2, "preview": "Hi"}
    ]

    app.dependency_overrides[auth.get_current_user] = lambda: _make_user("user-1")
    try:
        with TestClient(app) as client:
            with patch.object(_main, "history", mock_store):
                resp = client.get("/sessions", headers={"Authorization": "Bearer fake"})
    finally:
        app.dependency_overrides.pop(auth.get_current_user, None)

    assert resp.status_code == 200
    mock_store.list_sessions_for_user.assert_called_once_with("user-1")
    assert len(resp.json()) == 1


def test_history_endpoint_requires_auth():
    import auth
    from main import app
    from fastapi.testclient import TestClient

    app.dependency_overrides.pop(auth.get_current_user, None)
    with TestClient(app) as client:
        resp = client.get("/history/some-session-id")
    assert resp.status_code == 401


def test_history_endpoint_returns_404_for_wrong_user():
    import auth
    from main import app
    from fastapi.testclient import TestClient
    import main as _main
    from unittest.mock import patch

    mock_store = MagicMock()
    mock_store.get_transcript_if_owner.return_value = None  # not owner

    app.dependency_overrides[auth.get_current_user] = lambda: _make_user("user-2")
    try:
        with TestClient(app) as client:
            with patch.object(_main, "history", mock_store):
                resp = client.get(
                    "/history/sess-owned-by-user-1",
                    headers={"Authorization": "Bearer fake"},
                )
    finally:
        app.dependency_overrides.pop(auth.get_current_user, None)

    assert resp.status_code == 404


def test_history_endpoint_returns_transcript_for_owner():
    import auth
    from main import app
    from fastapi.testclient import TestClient
    import main as _main
    from unittest.mock import patch

    mock_store = MagicMock()
    mock_store.get_transcript_if_owner.return_value = [
        {"turn": 1, "role": "user", "text": "Hello"},
        {"turn": 1, "role": "zeus", "text": "Hi!"},
    ]

    app.dependency_overrides[auth.get_current_user] = lambda: _make_user("user-1")
    try:
        with TestClient(app) as client:
            with patch.object(_main, "history", mock_store):
                resp = client.get(
                    "/history/sess-owned-by-user-1",
                    headers={"Authorization": "Bearer fake"},
                )
    finally:
        app.dependency_overrides.pop(auth.get_current_user, None)

    assert resp.status_code == 200
    assert len(resp.json()) == 2
