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
             patch("requests.post", return_value=mock_resp), \
             patch("db.save_fal_image_job"), \
             patch("db.get_db_path", return_value=pathlib.Path("/tmp/test.db")):
            job_id = image_generator.submit_image_generation("a dog", "1:1")
        assert isinstance(job_id, str) and len(job_id) == 32

    def test_maps_social_ratio_to_square_1_1(self):
        import image_generator
        mock_resp = _make_resp({"request_id": "fal-req-abc"})
        with patch("image_generator.FAL_API_KEY", "test-key"), \
             patch("requests.post", return_value=mock_resp) as mock_post, \
             patch("db.save_fal_image_job"), \
             patch("db.get_db_path", return_value=pathlib.Path("/tmp/test.db")):
            image_generator.submit_image_generation("a dog", "1:1")
        assert mock_post.call_args.kwargs["json"]["image_size"] == "square_1_1"

    def test_maps_hero_ratio_to_landscape_16_9(self):
        import image_generator
        mock_resp = _make_resp({"request_id": "fal-req-abc"})
        with patch("image_generator.FAL_API_KEY", "test-key"), \
             patch("requests.post", return_value=mock_resp) as mock_post, \
             patch("db.save_fal_image_job"), \
             patch("db.get_db_path", return_value=pathlib.Path("/tmp/test.db")):
            image_generator.submit_image_generation("hero", "16:9")
        assert mock_post.call_args.kwargs["json"]["image_size"] == "landscape_16_9"

    def test_no_fal_webhook_in_body(self):
        import image_generator
        mock_resp = _make_resp({"request_id": "fal-req-abc"})
        with patch("image_generator.FAL_API_KEY", "test-key"), \
             patch("requests.post", return_value=mock_resp) as mock_post, \
             patch("db.save_fal_image_job"), \
             patch("db.get_db_path", return_value=pathlib.Path("/tmp/test.db")):
            image_generator.submit_image_generation("a dog", "1:1", webhook_url="https://example.com/webhooks/image")
        assert "_fal_webhook" not in mock_post.call_args.kwargs["json"]

    def test_saves_mapping_to_db(self):
        import image_generator
        mock_resp = _make_resp({"request_id": "fal-req-xyz"})
        with patch("image_generator.FAL_API_KEY", "test-key"), \
             patch("requests.post", return_value=mock_resp), \
             patch("db.save_fal_image_job") as mock_save, \
             patch("db.get_db_path", return_value=pathlib.Path("/tmp/test.db")):
            job_id = image_generator.submit_image_generation("a dog", "1:1")
        mock_save.assert_called_once_with(pathlib.Path("/tmp/test.db"), job_id, "fal-req-xyz")

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


class TestGetImageJobStatus:
    def test_returns_completed_from_disk_without_api_call(self, tmp_path):
        import image_generator
        dest = tmp_path / "local-id.jpg"
        dest.write_bytes(b"fake")
        with patch("image_generator.FAL_API_KEY", "test-key"), \
             patch("image_generator.ZEUS_PUBLIC_URL", "https://zeusaidesign.com"), \
             patch("image_generator.pathlib.Path") as mock_path:
            mock_path.return_value.__truediv__.return_value.exists.return_value = True
            result = image_generator.get_image_job_status("local-id")
        assert result["status"] == "COMPLETED"
        assert "local-id" in result["image_url"]

    def test_completed_downloads_and_returns_public_url(self):
        import image_generator
        status_resp = _make_resp({"status": "COMPLETED"})
        result_resp = _make_resp({"images": [{"url": "https://fal.media/files/img.jpg"}]})
        with patch("image_generator.FAL_API_KEY", "test-key"), \
             patch("image_generator.pathlib.Path") as mock_path_cls, \
             patch("db.get_fal_request_id", return_value="fal-req-123"), \
             patch("db.get_db_path", return_value=pathlib.Path("/tmp/test.db")), \
             patch("requests.get", side_effect=[status_resp, result_resp]), \
             patch("image_generator.download_and_save_image", return_value="https://zeusaidesign.com/files/images/local-id.jpg") as mock_dl:
            mock_path_cls.return_value.__truediv__.return_value.exists.return_value = False
            result = image_generator.get_image_job_status("local-id")
        assert result["status"] == "COMPLETED"
        assert result["image_url"] == "https://zeusaidesign.com/files/images/local-id.jpg"
        mock_dl.assert_called_once_with("local-id", "https://fal.media/files/img.jpg")

    def test_in_progress_returns_none_url(self):
        import image_generator
        status_resp = _make_resp({"status": "IN_PROGRESS"})
        with patch("image_generator.FAL_API_KEY", "test-key"), \
             patch("image_generator.pathlib.Path") as mock_path_cls, \
             patch("db.get_fal_request_id", return_value="fal-req-123"), \
             patch("db.get_db_path", return_value=pathlib.Path("/tmp/test.db")), \
             patch("requests.get", return_value=status_resp):
            mock_path_cls.return_value.__truediv__.return_value.exists.return_value = False
            result = image_generator.get_image_job_status("local-id")
        assert result["status"] == "IN_PROGRESS"
        assert result["image_url"] is None

    def test_expired_job_returns_expired_status(self):
        import image_generator
        expired_resp = _make_resp({}, status_code=405)
        expired_resp.raise_for_status = MagicMock()  # don't raise — we check status_code directly
        with patch("image_generator.FAL_API_KEY", "test-key"), \
             patch("image_generator.pathlib.Path") as mock_path_cls, \
             patch("db.get_fal_request_id", return_value="fal-req-expired"), \
             patch("db.get_db_path", return_value=pathlib.Path("/tmp/test.db")), \
             patch("requests.get", return_value=expired_resp):
            mock_path_cls.return_value.__truediv__.return_value.exists.return_value = False
            result = image_generator.get_image_job_status("local-id")
        assert result["status"] == "EXPIRED"
        assert result["image_url"] is None

    def test_raises_if_no_api_key(self):
        import image_generator
        with patch("image_generator.FAL_API_KEY", ""):
            with pytest.raises(ValueError, match="FAL_API_KEY"):
                image_generator.get_image_job_status("any-id")
