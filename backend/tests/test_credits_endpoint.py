import os
import pathlib
import sys

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from fastapi.testclient import TestClient

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))

# Ensure ANTHROPIC_API_KEY is set so the FastAPI lifespan doesn't raise
os.environ.setdefault("ANTHROPIC_API_KEY", "test-key-for-tests")


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


class TestCreditsEndpoint:
    def test_non_admin_gets_403(self):
        import auth
        import main as _main
        app = _main.app
        app.dependency_overrides[auth.get_current_user] = _regular_user
        try:
            with TestClient(app) as client:
                resp = client.get(
                    "/admin/credits",
                    headers={"Authorization": "Bearer fake"},
                )
                assert resp.status_code == 403
        finally:
            app.dependency_overrides.pop(auth.get_current_user, None)

    def test_admin_gets_balance_on_success(self):
        import auth
        import main as _main
        import httpx

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"balance": {"available": [{"amount": 1234, "currency": "USD"}]}}

        app = _main.app
        app.dependency_overrides[auth.get_current_user] = _admin_user
        try:
            with patch("main.httpx.AsyncClient") as mock_client_cls:
                mock_client = AsyncMock()
                mock_client.__aenter__ = AsyncMock(return_value=mock_client)
                mock_client.__aexit__ = AsyncMock(return_value=False)
                mock_client.get = AsyncMock(return_value=mock_response)
                mock_client_cls.return_value = mock_client
                with TestClient(app) as client:
                    resp = client.get(
                        "/admin/credits",
                        headers={"Authorization": "Bearer fake"},
                    )
                    assert resp.status_code == 200
                    data = resp.json()
                    assert data["balance"] is not None
        finally:
            app.dependency_overrides.pop(auth.get_current_user, None)

    def test_admin_gets_unavailable_on_anthropic_error(self):
        import auth
        import main as _main

        app = _main.app
        app.dependency_overrides[auth.get_current_user] = _admin_user
        try:
            with patch("main.httpx.AsyncClient") as mock_client_cls:
                mock_client = AsyncMock()
                mock_client.__aenter__ = AsyncMock(return_value=mock_client)
                mock_client.__aexit__ = AsyncMock(return_value=False)
                mock_client.get = AsyncMock(side_effect=Exception("connection failed"))
                mock_client_cls.return_value = mock_client
                with TestClient(app) as client:
                    resp = client.get(
                        "/admin/credits",
                        headers={"Authorization": "Bearer fake"},
                    )
                    assert resp.status_code == 200
                    data = resp.json()
                    assert data["balance"] is None
                    assert "unavailable" in data["message"].lower()
        finally:
            app.dependency_overrides.pop(auth.get_current_user, None)

    def test_admin_gets_unavailable_on_403_from_anthropic(self):
        import auth
        import main as _main

        mock_response = MagicMock()
        mock_response.status_code = 403

        app = _main.app
        app.dependency_overrides[auth.get_current_user] = _admin_user
        try:
            with patch("main.httpx.AsyncClient") as mock_client_cls:
                mock_client = AsyncMock()
                mock_client.__aenter__ = AsyncMock(return_value=mock_client)
                mock_client.__aexit__ = AsyncMock(return_value=False)
                mock_client.get = AsyncMock(return_value=mock_response)
                mock_client_cls.return_value = mock_client
                with TestClient(app) as client:
                    resp = client.get(
                        "/admin/credits",
                        headers={"Authorization": "Bearer fake"},
                    )
                    assert resp.status_code == 200
                    data = resp.json()
                    assert data["balance"] is None
        finally:
            app.dependency_overrides.pop(auth.get_current_user, None)
