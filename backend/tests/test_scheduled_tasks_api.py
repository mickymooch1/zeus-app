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


class TestCreateScheduledTask:
    def _task_row(self, **kwargs):
        base = {
            "id": "task-1",
            "user_id": "pro-user-1",
            "task_description": "Rebuild site",
            "cron_expression": "0 9 * * 1",
            "schedule_label": "Every Monday at 9am",
            "timezone": "UTC",
            "is_active": 1,
            "last_run": None,
            "next_run": "2026-04-14T09:00:00+00:00",
            "created_at": "2026-04-11T12:00:00+00:00",
        }
        base.update(kwargs)
        return base

    def test_pro_user_can_create(self):
        import auth
        import db
        import scheduler as _sched
        from main import app
        from fastapi.testclient import TestClient
        app.dependency_overrides[auth.get_current_user] = _pro_user
        task_row = self._task_row()
        try:
            with patch.object(db, "count_active_scheduled_tasks", return_value=0), \
                 patch.object(db, "create_scheduled_task", return_value=task_row), \
                 patch.object(_sched, "add_job") as mock_add:
                with TestClient(app) as client:
                    resp = client.post(
                        "/scheduled-tasks",
                        json={
                            "task_description": "Rebuild site",
                            "cron_expression": "0 9 * * 1",
                            "schedule_label": "Every Monday at 9am",
                            "timezone": "UTC",
                        },
                        headers={"Authorization": "Bearer fake"},
                    )
                    assert resp.status_code == 200
                    assert resp.json()["id"] == "task-1"
                    mock_add.assert_called_once()
        finally:
            app.dependency_overrides.pop(auth.get_current_user, None)

    def test_free_user_cannot_create(self):
        import auth
        from main import app
        from fastapi.testclient import TestClient
        app.dependency_overrides[auth.get_current_user] = _free_user
        try:
            with TestClient(app) as client:
                resp = client.post(
                    "/scheduled-tasks",
                    json={
                        "task_description": "Rebuild site",
                        "cron_expression": "0 9 * * 1",
                        "schedule_label": "Label",
                        "timezone": "UTC",
                    },
                    headers={"Authorization": "Bearer fake"},
                )
                assert resp.status_code == 403
        finally:
            app.dependency_overrides.pop(auth.get_current_user, None)

    def test_pro_user_at_limit_cannot_create(self):
        import auth
        import db
        from main import app
        from fastapi.testclient import TestClient
        app.dependency_overrides[auth.get_current_user] = _pro_user
        try:
            with patch.object(db, "count_active_scheduled_tasks", return_value=5):
                with TestClient(app) as client:
                    resp = client.post(
                        "/scheduled-tasks",
                        json={
                            "task_description": "Rebuild site",
                            "cron_expression": "0 9 * * 1",
                            "schedule_label": "Label",
                            "timezone": "UTC",
                        },
                        headers={"Authorization": "Bearer fake"},
                    )
                    assert resp.status_code == 403
                    assert "5" in resp.json()["detail"]
        finally:
            app.dependency_overrides.pop(auth.get_current_user, None)

    def test_invalid_cron_returns_400(self):
        import auth
        import db
        from main import app
        from fastapi.testclient import TestClient
        app.dependency_overrides[auth.get_current_user] = _pro_user
        try:
            with patch.object(db, "count_active_scheduled_tasks", return_value=0):
                with TestClient(app) as client:
                    resp = client.post(
                        "/scheduled-tasks",
                        json={
                            "task_description": "Rebuild site",
                            "cron_expression": "not valid",
                            "schedule_label": "Label",
                            "timezone": "UTC",
                        },
                        headers={"Authorization": "Bearer fake"},
                    )
                    assert resp.status_code == 400
        finally:
            app.dependency_overrides.pop(auth.get_current_user, None)

    def test_enterprise_user_unlimited(self):
        import auth
        import db
        import scheduler as _sched
        from main import app
        from fastapi.testclient import TestClient
        app.dependency_overrides[auth.get_current_user] = _enterprise_user
        task_row = self._task_row(user_id="ent-user-1")
        try:
            with patch.object(db, "count_active_scheduled_tasks", return_value=999), \
                 patch.object(db, "create_scheduled_task", return_value=task_row), \
                 patch.object(_sched, "add_job"):
                with TestClient(app) as client:
                    resp = client.post(
                        "/scheduled-tasks",
                        json={
                            "task_description": "Rebuild site",
                            "cron_expression": "0 9 * * 1",
                            "schedule_label": "Label",
                            "timezone": "UTC",
                        },
                        headers={"Authorization": "Bearer fake"},
                    )
                    assert resp.status_code == 200
        finally:
            app.dependency_overrides.pop(auth.get_current_user, None)


class TestDeleteScheduledTask:
    def test_delete_owned_task(self):
        import auth
        import db
        import scheduler as _sched
        from main import app
        from fastapi.testclient import TestClient
        app.dependency_overrides[auth.get_current_user] = _pro_user
        try:
            with patch.object(db, "delete_scheduled_task", return_value=True), \
                 patch.object(_sched, "remove_job") as mock_remove:
                with TestClient(app) as client:
                    resp = client.delete(
                        "/scheduled-tasks/task-1",
                        headers={"Authorization": "Bearer fake"},
                    )
                    assert resp.status_code == 200
                    assert resp.json() == {"ok": True}
                    mock_remove.assert_called_once_with("task-1")
        finally:
            app.dependency_overrides.pop(auth.get_current_user, None)

    def test_delete_not_owned_returns_404(self):
        import auth
        import db
        from main import app
        from fastapi.testclient import TestClient
        app.dependency_overrides[auth.get_current_user] = _pro_user
        try:
            with patch.object(db, "delete_scheduled_task", return_value=False):
                with TestClient(app) as client:
                    resp = client.delete(
                        "/scheduled-tasks/task-999",
                        headers={"Authorization": "Bearer fake"},
                    )
                    assert resp.status_code == 404
        finally:
            app.dependency_overrides.pop(auth.get_current_user, None)


class TestToggleScheduledTask:
    def _task_row(self, is_active):
        return {
            "id": "task-1",
            "user_id": "pro-user-1",
            "task_description": "Rebuild site",
            "cron_expression": "0 9 * * 1",
            "schedule_label": "Every Monday at 9am",
            "timezone": "UTC",
            "is_active": is_active,
            "last_run": None,
            "next_run": "2026-04-14T09:00:00+00:00",
            "created_at": "2026-04-11T12:00:00+00:00",
        }

    def test_deactivate_task(self):
        import auth
        import db
        import scheduler as _sched
        from main import app
        from fastapi.testclient import TestClient
        active_task = self._task_row(is_active=1)
        paused_task = self._task_row(is_active=0)
        app.dependency_overrides[auth.get_current_user] = _pro_user
        try:
            with patch.object(db, "get_scheduled_task", side_effect=[active_task, paused_task]), \
                 patch.object(db, "update_scheduled_task"), \
                 patch.object(_sched, "set_job_enabled") as mock_toggle:
                with TestClient(app) as client:
                    resp = client.patch(
                        "/scheduled-tasks/task-1/toggle",
                        headers={"Authorization": "Bearer fake"},
                    )
                    assert resp.status_code == 200
                    assert resp.json()["is_active"] == 0
                    mock_toggle.assert_called_once_with("task-1", False)
        finally:
            app.dependency_overrides.pop(auth.get_current_user, None)

    def test_activate_task_at_limit_returns_403(self):
        import auth
        import db
        from main import app
        from fastapi.testclient import TestClient
        paused_task = self._task_row(is_active=0)
        app.dependency_overrides[auth.get_current_user] = _pro_user
        try:
            with patch.object(db, "get_scheduled_task", return_value=paused_task), \
                 patch.object(db, "count_active_scheduled_tasks", return_value=5):
                with TestClient(app) as client:
                    resp = client.patch(
                        "/scheduled-tasks/task-1/toggle",
                        headers={"Authorization": "Bearer fake"},
                    )
                    assert resp.status_code == 403
        finally:
            app.dependency_overrides.pop(auth.get_current_user, None)
