import os
import pathlib
import sys
from unittest.mock import patch

import pytest

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))

# Ensure ANTHROPIC_API_KEY is set so the FastAPI lifespan doesn't raise
os.environ.setdefault("ANTHROPIC_API_KEY", "test-key-for-tests")


def _make_enterprise_user():
    return {
        "id": "ent-user-1",
        "email": "test@example.com",
        "subscription_status": "active",
        "subscription_plan": "enterprise",
        "password_hash": "x",
        "name": "Test User",
    }


def _make_free_user():
    return {
        "id": "free-user-1",
        "email": "free@example.com",
        "subscription_status": "free",
        "subscription_plan": None,
        "password_hash": "x",
        "name": "Free User",
    }


class TestTasksEndpoint:
    def test_requires_auth(self):
        import auth
        from main import app
        from fastapi.testclient import TestClient

        # Remove any overrides so real auth runs
        app.dependency_overrides.pop(auth.get_current_user, None)
        with TestClient(app) as client:
            resp = client.get("/tasks")
        assert resp.status_code == 401

    def test_enterprise_user_gets_empty_list(self):
        import auth
        import db
        from main import app
        from fastapi.testclient import TestClient

        app.dependency_overrides[auth.get_current_user] = lambda: _make_enterprise_user()
        try:
            with patch.object(db, "get_tasks_for_user", return_value=[]):
                with TestClient(app) as client:
                    resp = client.get(
                        "/tasks",
                        headers={"Authorization": "Bearer fake-token"},
                    )
        finally:
            app.dependency_overrides.pop(auth.get_current_user, None)

        assert resp.status_code == 200
        assert resp.json() == []

    def test_non_enterprise_gets_403(self):
        import auth
        from main import app
        from fastapi.testclient import TestClient

        app.dependency_overrides[auth.get_current_user] = lambda: _make_free_user()
        try:
            with TestClient(app) as client:
                resp = client.get(
                    "/tasks",
                    headers={"Authorization": "Bearer fake-token"},
                )
        finally:
            app.dependency_overrides.pop(auth.get_current_user, None)

        assert resp.status_code == 403

    def test_returns_tasks_for_user(self):
        import auth
        import db
        from main import app
        from fastapi.testclient import TestClient

        mock_tasks = [
            {
                "id": "task-1",
                "user_id": "ent-user-1",
                "description": "Build site for Acme",
                "status": "done",
                "result": "Live at https://acme.netlify.app",
                "live_url": "https://acme.netlify.app",
                "created_at": "2026-04-09T10:00:00",
                "completed_at": "2026-04-09T10:30:00",
            }
        ]
        app.dependency_overrides[auth.get_current_user] = lambda: _make_enterprise_user()
        try:
            with patch.object(db, "get_tasks_for_user", return_value=mock_tasks):
                with TestClient(app) as client:
                    resp = client.get(
                        "/tasks",
                        headers={"Authorization": "Bearer fake-token"},
                    )
        finally:
            app.dependency_overrides.pop(auth.get_current_user, None)

        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["live_url"] == "https://acme.netlify.app"
