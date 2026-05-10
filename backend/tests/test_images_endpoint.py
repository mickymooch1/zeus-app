import os
import pathlib
import sys

import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))

# Set required env vars before importing main (webhooks.py reads them at module level)
os.environ.setdefault("ANTHROPIC_API_KEY", "test-key-for-tests")
os.environ.setdefault("APIFRAME_API_KEY", "test-key-for-tests")
os.environ.setdefault("SONG_STORAGE_PATH", "/tmp/test_songs")
os.environ.setdefault("SONG_PUBLIC_BASE_URL", "https://example.com")
os.environ.setdefault("SONG_WEBHOOK_URL", "https://example.com/webhooks/apiframe")


def _test_user():
    return {
        "id": "user-1",
        "email": "user@example.com",
        "subscription_status": "active",
        "subscription_plan": "pro",
        "password_hash": "x",
        "name": "User",
        "is_admin": 0,
    }


class TestGenerateImageEndpoint:
    def test_returns_job_id_and_url(self):
        import auth
        import main as _main
        app = _main.app
        app.dependency_overrides[auth.get_current_user] = _test_user
        try:
            with patch("image_generator.submit_image_generation", return_value="job-xyz123"):
                with TestClient(app) as client:
                    resp = client.post(
                        "/api/images/generate",
                        json={"prompt": "a god of thunder", "use_case": "social"},
                    )
        finally:
            app.dependency_overrides.pop(auth.get_current_user, None)
        assert resp.status_code == 200
        data = resp.json()
        assert data["job_id"] == "job-xyz123"
        assert "job-xyz123" in data["url"]
        assert data["url"].endswith(".jpg")

    def test_hero_use_case_passes_16_9_ratio(self):
        import auth
        import main as _main
        app = _main.app
        app.dependency_overrides[auth.get_current_user] = _test_user
        captured = {}

        def _fake_submit(prompt, aspect_ratio, model="flux", webhook_url=""):
            captured["aspect_ratio"] = aspect_ratio
            return "job-abc"

        try:
            with patch("image_generator.submit_image_generation", side_effect=_fake_submit):
                with TestClient(app) as client:
                    client.post(
                        "/api/images/generate",
                        json={"prompt": "hero image", "use_case": "hero"},
                    )
        finally:
            app.dependency_overrides.pop(auth.get_current_user, None)
        assert captured["aspect_ratio"] == "16:9"

    def test_portrait_use_case_passes_9_16_ratio(self):
        import auth
        import main as _main
        app = _main.app
        app.dependency_overrides[auth.get_current_user] = _test_user
        captured = {}

        def _fake_submit(prompt, aspect_ratio, model="flux", webhook_url=""):
            captured["aspect_ratio"] = aspect_ratio
            return "job-def"

        try:
            with patch("image_generator.submit_image_generation", side_effect=_fake_submit):
                with TestClient(app) as client:
                    client.post(
                        "/api/images/generate",
                        json={"prompt": "portrait", "use_case": "portrait"},
                    )
        finally:
            app.dependency_overrides.pop(auth.get_current_user, None)
        assert captured["aspect_ratio"] == "9:16"

    def test_unauthenticated_returns_401(self):
        import main as _main
        app = _main.app
        with TestClient(app) as client:
            resp = client.post(
                "/api/images/generate",
                json={"prompt": "test", "use_case": "social"},
            )
        assert resp.status_code == 401


class TestImageStatusEndpoint:
    def test_returns_status_and_url(self):
        import auth
        import main as _main
        app = _main.app
        app.dependency_overrides[auth.get_current_user] = _test_user
        try:
            with patch(
                "image_generator.get_image_job_status",
                return_value={"status": "COMPLETED", "image_url": "https://cdn.apiframe.ai/img.jpg"},
            ):
                with TestClient(app) as client:
                    resp = client.get("/api/images/status/job-abc123")
        finally:
            app.dependency_overrides.pop(auth.get_current_user, None)
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "COMPLETED"
        assert data["image_url"] == "https://cdn.apiframe.ai/img.jpg"

    def test_unauthenticated_returns_401(self):
        import main as _main
        app = _main.app
        with TestClient(app) as client:
            resp = client.get("/api/images/status/job-abc123")
        assert resp.status_code == 401


class TestImageWebhookEndpoint:
    def test_fal_nested_payload_structure(self):
        import main as _main
        app = _main.app
        with patch(
            "image_generator.download_and_save_image",
            return_value="https://zeusaidesign.com/files/images/local-job-id.jpg",
        ) as mock_dl:
            with TestClient(app) as client:
                resp = client.post(
                    "/webhooks/image?job_id=local-job-id",
                    json={
                        "status": "OK",
                        "payload": {"images": [{"url": "https://fal.media/files/img.jpg", "width": 1024, "height": 1024}]},
                    },
                )
        assert resp.status_code == 200
        assert resp.json()["ok"] is True
        mock_dl.assert_called_once_with("local-job-id", "https://fal.media/files/img.jpg")

    def test_fal_flat_payload_still_works(self):
        import main as _main
        app = _main.app
        with patch(
            "image_generator.download_and_save_image",
            return_value="https://zeusaidesign.com/files/images/local-job-id.jpg",
        ) as mock_dl:
            with TestClient(app) as client:
                resp = client.post(
                    "/webhooks/image?job_id=local-job-id",
                    json={
                        "request_id": "fal-req-abc",
                        "images": [{"url": "https://fal.media/files/img.jpg"}],
                    },
                )
        assert resp.status_code == 200
        assert resp.json()["ok"] is True
        mock_dl.assert_called_once_with("local-job-id", "https://fal.media/files/img.jpg")

    def test_falls_back_to_request_id_when_no_query_param(self):
        import main as _main
        app = _main.app
        with patch(
            "image_generator.download_and_save_image",
            return_value="https://zeusaidesign.com/files/images/fal-req-abc.jpg",
        ) as mock_dl:
            with TestClient(app) as client:
                resp = client.post(
                    "/webhooks/image",
                    json={
                        "request_id": "fal-req-abc",
                        "images": [{"url": "https://fal.media/files/img.jpg"}],
                    },
                )
        assert resp.status_code == 200
        mock_dl.assert_called_once_with("fal-req-abc", "https://fal.media/files/img.jpg")

    def test_no_images_returns_ok_without_download(self):
        import main as _main
        app = _main.app
        with patch("image_generator.download_and_save_image") as mock_dl:
            with TestClient(app) as client:
                resp = client.post(
                    "/webhooks/image?job_id=local-job-id",
                    json={"request_id": "fal-req-abc", "images": []},
                )
        assert resp.status_code == 200
        mock_dl.assert_not_called()

    def test_download_failure_returns_200_not_500(self):
        import main as _main
        app = _main.app
        with patch("image_generator.download_and_save_image", side_effect=Exception("404 Client Error")):
            with TestClient(app) as client:
                resp = client.post(
                    "/webhooks/image?job_id=local-job-id",
                    json={
                        "request_id": "fal-req-abc",
                        "images": [{"url": "https://fal.media/files/nonexistent.jpg"}],
                    },
                )
        assert resp.status_code == 200
        assert resp.json()["ok"] is False

    def test_missing_job_id_returns_400(self):
        import main as _main
        app = _main.app
        with TestClient(app) as client:
            resp = client.post("/webhooks/image", json={"images": []})
        assert resp.status_code == 400
