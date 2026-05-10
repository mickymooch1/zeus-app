import os
import pathlib
import sys

import pytest
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))
os.environ.setdefault("FAL_API_KEY", "test-key-for-tests")


def _make_resp(json_data, status_code=200):
    m = MagicMock()
    m.status_code = status_code
    m.json.return_value = json_data
    m.raise_for_status = MagicMock()
    return m


class TestSubmitImageGeneration:
    def test_returns_public_url(self):
        import image_generator
        fal_resp = _make_resp({"images": [{"url": "https://fal.media/files/img.jpg"}]})
        with patch("image_generator.FAL_API_KEY", "test-key"), \
             patch("requests.post", return_value=fal_resp), \
             patch("image_generator.download_and_save_image", return_value="https://zeusaidesign.com/files/images/abc.jpg"):
            result = image_generator.submit_image_generation("a dog", "1:1")
        assert result == "https://zeusaidesign.com/files/images/abc.jpg"

    def test_posts_to_sync_endpoint(self):
        import image_generator
        fal_resp = _make_resp({"images": [{"url": "https://fal.media/files/img.jpg"}]})
        with patch("image_generator.FAL_API_KEY", "test-key"), \
             patch("requests.post", return_value=fal_resp) as mock_post, \
             patch("image_generator.download_and_save_image", return_value="https://zeusaidesign.com/files/images/abc.jpg"):
            image_generator.submit_image_generation("a dog", "1:1")
        called_url = mock_post.call_args.args[0]
        assert called_url.startswith("https://fal.run/")
        assert "queue.fal.run" not in called_url

    def test_maps_social_ratio_to_square_1_1(self):
        import image_generator
        fal_resp = _make_resp({"images": [{"url": "https://fal.media/files/img.jpg"}]})
        with patch("image_generator.FAL_API_KEY", "test-key"), \
             patch("requests.post", return_value=fal_resp) as mock_post, \
             patch("image_generator.download_and_save_image", return_value="https://zeusaidesign.com/files/images/abc.jpg"):
            image_generator.submit_image_generation("a dog", "1:1")
        assert mock_post.call_args.kwargs["json"]["image_size"] == "square_1_1"

    def test_maps_hero_ratio_to_landscape_16_9(self):
        import image_generator
        fal_resp = _make_resp({"images": [{"url": "https://fal.media/files/img.jpg"}]})
        with patch("image_generator.FAL_API_KEY", "test-key"), \
             patch("requests.post", return_value=fal_resp) as mock_post, \
             patch("image_generator.download_and_save_image", return_value="https://zeusaidesign.com/files/images/abc.jpg"):
            image_generator.submit_image_generation("hero", "16:9")
        assert mock_post.call_args.kwargs["json"]["image_size"] == "landscape_16_9"

    def test_raises_if_no_api_key(self):
        import image_generator
        with patch("image_generator.FAL_API_KEY", ""):
            with pytest.raises(ValueError, match="FAL_API_KEY"):
                image_generator.submit_image_generation("a dog", "1:1")

    def test_raises_if_no_images_in_response(self):
        import image_generator
        fal_resp = _make_resp({"images": []})
        with patch("image_generator.FAL_API_KEY", "test-key"), \
             patch("requests.post", return_value=fal_resp):
            with pytest.raises(RuntimeError, match="images"):
                image_generator.submit_image_generation("a dog", "1:1")

    def test_downloads_image_immediately(self):
        import image_generator
        fal_resp = _make_resp({"images": [{"url": "https://fal.media/files/img.jpg"}]})
        with patch("image_generator.FAL_API_KEY", "test-key"), \
             patch("requests.post", return_value=fal_resp), \
             patch("image_generator.download_and_save_image", return_value="https://zeusaidesign.com/files/images/abc.jpg") as mock_dl:
            image_generator.submit_image_generation("a dog", "1:1")
        mock_dl.assert_called_once_with(mock_dl.call_args.args[0], "https://fal.media/files/img.jpg")


class TestGetImageJobStatus:
    def test_returns_completed_when_file_on_disk(self, tmp_path):
        import image_generator
        dest = tmp_path / "local-id.jpg"
        dest.write_bytes(b"fake")
        with patch("image_generator.pathlib.Path") as mock_path:
            mock_path.return_value.__truediv__.return_value.exists.return_value = True
            result = image_generator.get_image_job_status("local-id")
        assert result["status"] == "COMPLETED"
        assert "local-id" in result["image_url"]

    def test_returns_not_found_when_file_missing(self):
        import image_generator
        with patch("image_generator.pathlib.Path") as mock_path:
            mock_path.return_value.__truediv__.return_value.exists.return_value = False
            result = image_generator.get_image_job_status("missing-id")
        assert result["status"] == "NOT_FOUND"
        assert result["image_url"] is None
