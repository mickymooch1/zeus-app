import os
import pathlib
import sys

import pytest
from unittest.mock import MagicMock, patch, call

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))
os.environ.setdefault("FAL_API_KEY", "test-key-for-tests")


def _make_resp(json_data, status_code=200):
    m = MagicMock()
    m.status_code = status_code
    m.json.return_value = json_data
    m.raise_for_status = MagicMock()
    return m


class TestSubmitImageGeneration:
    def test_returns_local_job_id(self):
        import image_generator
        mock_resp = _make_resp({"request_id": "fal-req-abc"})
        with patch("image_generator.FAL_API_KEY", "test-key"), \
             patch("requests.post", return_value=mock_resp):
            job_id = image_generator.submit_image_generation(
                "a dog", "1:1", "flux", "https://example.com/webhooks/image"
            )
        assert isinstance(job_id, str) and len(job_id) == 32  # uuid4().hex

    def test_maps_social_ratio_to_square_1_1(self):
        import image_generator
        mock_resp = _make_resp({"request_id": "fal-req-abc"})
        with patch("image_generator.FAL_API_KEY", "test-key"), \
             patch("requests.post", return_value=mock_resp) as mock_post:
            image_generator.submit_image_generation("a dog", "1:1", webhook_url="https://example.com/webhooks/image")
        body = mock_post.call_args.kwargs["json"]
        assert body["image_size"] == "square_1_1"

    def test_maps_hero_ratio_to_landscape_16_9(self):
        import image_generator
        mock_resp = _make_resp({"request_id": "fal-req-abc"})
        with patch("image_generator.FAL_API_KEY", "test-key"), \
             patch("requests.post", return_value=mock_resp) as mock_post:
            image_generator.submit_image_generation("hero", "16:9", webhook_url="https://example.com/webhooks/image")
        body = mock_post.call_args.kwargs["json"]
        assert body["image_size"] == "landscape_16_9"

    def test_webhook_url_includes_job_id_query_param(self):
        import image_generator
        mock_resp = _make_resp({"request_id": "fal-req-abc"})
        with patch("image_generator.FAL_API_KEY", "test-key"), \
             patch("requests.post", return_value=mock_resp) as mock_post:
            job_id = image_generator.submit_image_generation("a dog", "1:1", webhook_url="https://example.com/webhooks/image")
        body = mock_post.call_args.kwargs["json"]
        assert body["_fal_webhook"] == f"https://example.com/webhooks/image?job_id={job_id}"

    def test_omits_fal_webhook_when_no_webhook_url(self):
        import image_generator
        mock_resp = _make_resp({"request_id": "fal-req-abc"})
        with patch("image_generator.FAL_API_KEY", "test-key"), \
             patch("requests.post", return_value=mock_resp) as mock_post:
            image_generator.submit_image_generation("a dog", "1:1")
        body = mock_post.call_args.kwargs["json"]
        assert "_fal_webhook" not in body

    def test_raises_if_no_api_key(self):
        import image_generator
        with patch("image_generator.FAL_API_KEY", ""):
            with pytest.raises(ValueError, match="FAL_API_KEY"):
                image_generator.submit_image_generation("a dog", "1:1")

    def test_raises_if_no_request_id_in_response(self):
        import image_generator
        mock_resp = _make_resp({"error": "bad request"})
        with patch("image_generator.FAL_API_KEY", "test-key"), \
             patch("requests.post", return_value=mock_resp):
            with pytest.raises(RuntimeError, match="request_id"):
                image_generator.submit_image_generation("a dog", "1:1")

    def test_stores_request_id_in_job_map(self):
        import image_generator
        image_generator._job_request_map.clear()
        mock_resp = _make_resp({"request_id": "fal-req-xyz"})
        with patch("image_generator.FAL_API_KEY", "test-key"), \
             patch("requests.post", return_value=mock_resp):
            job_id = image_generator.submit_image_generation("a dog", "1:1")
        assert image_generator._job_request_map[job_id] == "fal-req-xyz"


class TestGetImageJobStatus:
    def test_completed_fetches_result_and_returns_url(self):
        import image_generator
        image_generator._job_request_map["local-id"] = "fal-req-123"
        status_resp = _make_resp({"status": "COMPLETED"})
        result_resp = _make_resp({"images": [{"url": "https://fal.media/files/img.jpg"}]})
        with patch("image_generator.FAL_API_KEY", "test-key"), \
             patch("requests.get", side_effect=[status_resp, result_resp]):
            result = image_generator.get_image_job_status("local-id")
        assert result["status"] == "COMPLETED"
        assert result["image_url"] == "https://fal.media/files/img.jpg"

    def test_in_progress_returns_none_url(self):
        import image_generator
        image_generator._job_request_map["local-id"] = "fal-req-123"
        status_resp = _make_resp({"status": "IN_PROGRESS"})
        with patch("image_generator.FAL_API_KEY", "test-key"), \
             patch("requests.get", return_value=status_resp):
            result = image_generator.get_image_job_status("local-id")
        assert result["status"] == "IN_PROGRESS"
        assert result["image_url"] is None

    def test_raises_if_no_api_key(self):
        import image_generator
        with patch("image_generator.FAL_API_KEY", ""):
            with pytest.raises(ValueError, match="FAL_API_KEY"):
                image_generator.get_image_job_status("any-id")
