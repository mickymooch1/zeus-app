import os
import pathlib
import sys

import pytest
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))
os.environ.setdefault("APIFRAME_API_KEY", "test-key-for-tests")


def _make_resp(json_data, status_code=200):
    m = MagicMock()
    m.status_code = status_code
    m.json.return_value = json_data
    m.raise_for_status = MagicMock()
    return m


class TestSubmitImageGeneration:
    def test_returns_job_id(self):
        import image_generator
        mock_resp = _make_resp({"jobId": "abc123"})
        with patch("image_generator.APIFRAME_API_KEY", "test-key"), \
             patch("requests.post", return_value=mock_resp) as mock_post:
            job_id = image_generator.submit_image_generation(
                "a dog", "1:1", "flux", "https://example.com/webhooks/image"
            )
        assert job_id == "abc123"
        call_json = mock_post.call_args.kwargs["json"]
        assert call_json["prompt"] == "a dog"
        assert call_json["aspectRatio"] == "1:1"
        assert call_json["model"] == "flux"
        assert call_json["webhookUrl"] == "https://example.com/webhooks/image"

    def test_omits_webhook_when_empty(self):
        import image_generator
        mock_resp = _make_resp({"jobId": "abc123"})
        with patch("image_generator.APIFRAME_API_KEY", "test-key"), \
             patch("requests.post", return_value=mock_resp) as mock_post:
            image_generator.submit_image_generation("a dog", "1:1")
        call_json = mock_post.call_args.kwargs["json"]
        assert "webhookUrl" not in call_json

    def test_raises_if_no_api_key(self):
        import image_generator
        with patch("image_generator.APIFRAME_API_KEY", ""):
            with pytest.raises(ValueError, match="APIFRAME_API_KEY"):
                image_generator.submit_image_generation("a dog", "1:1")

    def test_raises_if_no_job_id_in_response(self):
        import image_generator
        mock_resp = _make_resp({"error": "bad request"})
        with patch("image_generator.APIFRAME_API_KEY", "test-key"), \
             patch("requests.post", return_value=mock_resp):
            with pytest.raises(RuntimeError, match="jobId"):
                image_generator.submit_image_generation("a dog", "1:1")


class TestGetImageJobStatus:
    def test_completed_extracts_image_url(self):
        import image_generator
        mock_resp = _make_resp({
            "status": "COMPLETED",
            "result": {"images": ["https://cdn.apiframe.ai/img.jpg"]},
        })
        with patch("image_generator.APIFRAME_API_KEY", "test-key"), \
             patch("requests.get", return_value=mock_resp):
            result = image_generator.get_image_job_status("abc123")
        assert result["status"] == "COMPLETED"
        assert result["image_url"] == "https://cdn.apiframe.ai/img.jpg"

    def test_pending_returns_none_url(self):
        import image_generator
        mock_resp = _make_resp({"status": "PENDING"})
        with patch("image_generator.APIFRAME_API_KEY", "test-key"), \
             patch("requests.get", return_value=mock_resp):
            result = image_generator.get_image_job_status("abc123")
        assert result["status"] == "PENDING"
        assert result["image_url"] is None

    def test_raises_if_no_api_key(self):
        import image_generator
        with patch("image_generator.APIFRAME_API_KEY", ""):
            with pytest.raises(ValueError, match="APIFRAME_API_KEY"):
                image_generator.get_image_job_status("abc123")
