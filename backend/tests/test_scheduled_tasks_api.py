import os
import pathlib
import sys
from unittest.mock import patch, AsyncMock, MagicMock

import pytest

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))
os.environ.setdefault("ANTHROPIC_API_KEY", "test-key-for-tests")


def _pro_user():
    return {
        "id": "pro-user-1",
        "email": "pro@example.com",
        "subscription_status": "active",
        "subscription_plan": "pro",
        "password_hash": "x",
        "name": "Pro User",
        "is_admin": 0,
    }


def _agency_user():
    return {
        "id": "agency-user-1",
        "email": "agency@example.com",
        "subscription_status": "active",
        "subscription_plan": "agency",
        "password_hash": "x",
        "name": "Agency User",
        "is_admin": 0,
    }


def _enterprise_user():
    return {
        "id": "ent-user-1",
        "email": "ent@example.com",
        "subscription_status": "active",
        "subscription_plan": "enterprise",
        "password_hash": "x",
        "name": "Ent User",
        "is_admin": 0,
    }


def _free_user():
    return {
        "id": "free-user-1",
        "email": "free@example.com",
        "subscription_status": "free",
        "subscription_plan": None,
        "password_hash": "x",
        "name": "Free User",
        "is_admin": 0,
    }


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


class TestScheduledTasksPlanGate:
    def test_free_user_cannot_list(self):
        import auth
        from main import app
        from fastapi.testclient import TestClient
        app.dependency_overrides[auth.get_current_user] = _free_user
        try:
            with TestClient(app) as client:
                resp = client.get("/scheduled-tasks", headers={"Authorization": "Bearer fake"})
                assert resp.status_code == 403
        finally:
            app.dependency_overrides.pop(auth.get_current_user, None)

    def test_pro_user_can_list(self):
        import auth
        import db
        from main import app
        from fastapi.testclient import TestClient
        app.dependency_overrides[auth.get_current_user] = _pro_user
        try:
            with patch.object(db, "get_scheduled_tasks_for_user", return_value=[]):
                with TestClient(app) as client:
                    resp = client.get("/scheduled-tasks", headers={"Authorization": "Bearer fake"})
                    assert resp.status_code == 200
                    assert resp.json() == []
        finally:
            app.dependency_overrides.pop(auth.get_current_user, None)

    def test_admin_bypasses_plan_gate(self):
        import auth
        import db
        from main import app
        from fastapi.testclient import TestClient
        app.dependency_overrides[auth.get_current_user] = _admin_user
        try:
            with patch.object(db, "get_scheduled_tasks_for_user", return_value=[]):
                with TestClient(app) as client:
                    resp = client.get("/scheduled-tasks", headers={"Authorization": "Bearer fake"})
                    assert resp.status_code == 200
        finally:
            app.dependency_overrides.pop(auth.get_current_user, None)


class TestParseEndpoint:
    def _mock_anthropic_parse(self, natural_language, cron, label):
        """Helper: mock Anthropic client to return a cron JSON response."""
        mock_msg = MagicMock()
        mock_msg.content = [MagicMock(text=f'{{"cron_expression": "{cron}", "schedule_label": "{label}"}}')]
        mock_client = MagicMock()
        mock_client.messages.create = MagicMock(return_value=mock_msg)
        return mock_client

    def test_parse_returns_cron(self):
        import auth
        from main import app, _parse_cache
        from fastapi.testclient import TestClient
        _parse_cache.clear()
        app.dependency_overrides[auth.get_current_user] = _pro_user
        mock_client = self._mock_anthropic_parse("every monday at 9am", "0 9 * * 1", "Every Monday at 9am")
        try:
            with patch("main.get_anthropic_client", return_value=mock_client):
                with TestClient(app) as client:
                    resp = client.post(
                        "/scheduled-tasks/parse",
                        json={"natural_language": "every monday at 9am"},
                        headers={"Authorization": "Bearer fake"},
                    )
                    assert resp.status_code == 200
                    data = resp.json()
                    assert data["cron_expression"] == "0 9 * * 1"
                    assert data["schedule_label"] == "Every Monday at 9am"
        finally:
            app.dependency_overrides.pop(auth.get_current_user, None)
            _parse_cache.clear()

    def test_parse_uses_cache(self):
        import auth
        from main import app, _parse_cache
        from fastapi.testclient import TestClient
        _parse_cache.clear()
        _parse_cache["every monday at 9am"] = {"cron_expression": "0 9 * * 1", "schedule_label": "Every Monday at 9am"}
        app.dependency_overrides[auth.get_current_user] = _pro_user
        try:
            with TestClient(app) as client:
                # No mock needed — cache hit should not call Anthropic
                resp = client.post(
                    "/scheduled-tasks/parse",
                    json={"natural_language": "every monday at 9am"},
                    headers={"Authorization": "Bearer fake"},
                )
                assert resp.status_code == 200
                assert resp.json()["cron_expression"] == "0 9 * * 1"
        finally:
            app.dependency_overrides.pop(auth.get_current_user, None)
            _parse_cache.clear()

    def test_parse_returns_400_on_claude_error(self):
        import auth
        from main import app, _parse_cache
        from fastapi.testclient import TestClient
        _parse_cache.clear()
        mock_msg = MagicMock()
        mock_msg.content = [MagicMock(text='{"error": "Could not parse schedule"}')]
        mock_client = MagicMock()
        mock_client.messages.create = MagicMock(return_value=mock_msg)
        app.dependency_overrides[auth.get_current_user] = _pro_user
        try:
            with patch("main.get_anthropic_client", return_value=mock_client):
                with TestClient(app) as client:
                    resp = client.post(
                        "/scheduled-tasks/parse",
                        json={"natural_language": "potato"},
                        headers={"Authorization": "Bearer fake"},
                    )
                    assert resp.status_code == 400
        finally:
            app.dependency_overrides.pop(auth.get_current_user, None)
            _parse_cache.clear()

    def test_free_user_can_parse(self):
        """Parse endpoint has no plan gate — free users can preview."""
        import auth
        from main import app, _parse_cache
        from fastapi.testclient import TestClient
        _parse_cache.clear()
        app.dependency_overrides[auth.get_current_user] = _free_user
        mock_msg = MagicMock()
        mock_msg.content = [MagicMock(text='{"cron_expression": "0 9 * * 1", "schedule_label": "Every Monday at 9am"}')]
        mock_client = MagicMock()
        mock_client.messages.create = MagicMock(return_value=mock_msg)
        try:
            with patch("main.get_anthropic_client", return_value=mock_client):
                with TestClient(app) as client:
                    resp = client.post(
                        "/scheduled-tasks/parse",
                        json={"natural_language": "every monday"},
                        headers={"Authorization": "Bearer fake"},
                    )
                    assert resp.status_code == 200
        finally:
            app.dependency_overrides.pop(auth.get_current_user, None)
            _parse_cache.clear()
