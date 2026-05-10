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

    def test_webhook_passed_as_query_param_not_body(self):
        import image_generator
        mock_resp = _make_resp({"request_id": "fal-req-abc"})
        with patch("image_generator.FAL_API_KEY", "test-key"), \
             patch("requests.post", return_value=mock_resp) as mock_post, \
             patch("db.save_fal_image_job"), \
             patch("db.get_db_path", return_value=pathlib.Path("/tmp/test.db")):
            image_generator.submit_image_generation("a dog", "1:1", webhook_url="https://example.com/webhooks/image")
        called_url = mock_post.call_args.args[0]
        assert "fal_webhook=https://example.com/webhooks/image" in called_url
        assert "_fal_webhook" not in mock_post.call_args.kwargs["json"]

    def test_no_webhook_in_url_when_not_provided(self):
        import image_generator
        mock_resp = _make_resp({"request_id": "fal-req-abc"})
        with patch("image_generator.FAL_API_KEY", "test-key"), \
             patch("requests.post", return_value=mock_resp) as mock_post, \
             patch("db.save_fal_image_job"), \
             patch("db.get_db_path", return_value=pathlib.Path("/tmp/test.db")):
            image_generator.submit_image_generation("a dog", "1:1")
        called_url = mock_post.call_args.args[0]
        assert "fal_webhook" not in called_url

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
        expired_resp.raise_for_status = MagicMock()
        with patch("image_generator.FAL_API_KEY", "test-key"), \
             patch("image_generator.pathlib.Path") as mock_path_cls, \
             patch("db.get_fal_request_id", return_value="fal-req-expired"), \
             patch("db.get_db_path", return_value=pathlib.Path("/tmp/test.db")), \
             patch("requests.get", return_value=expired_resp):
            mock_path_cls.return_value.__truediv__.return_value.exists.return_value = False
            result = image_generator.get_image_job_status("local-id")
        assert result["status"] == "EXPIRED"
        assert result["image_url"] is None

    def test_405_on_status_but_result_url_has_image(self):
        import image_generator
        status_405 = _make_resp({}, status_code=405)
        status_405.raise_for_status = MagicMock()
        result_resp = _make_resp({"images": [{"url": "https://fal.media/files/img.jpg"}]})
        with patch("image_generator.FAL_API_KEY", "test-key"), \
             patch("image_generator.pathlib.Path") as mock_path_cls, \
             patch("db.get_fal_request_id", return_value="fal-req-xyz"), \
             patch("db.get_db_path", return_value=pathlib.Path("/tmp/test.db")), \
             patch("requests.get", side_effect=[status_405, result_resp]), \
             patch("image_generator.download_and_save_image", return_value="https://zeusaidesign.com/files/images/local-id.jpg") as mock_dl:
            mock_path_cls.return_value.__truediv__.return_value.exists.return_value = False
            result = image_generator.get_image_job_status("local-id")
        assert result["status"] == "COMPLETED"
        assert result["image_url"] == "https://zeusaidesign.com/files/images/local-id.jpg"
        mock_dl.assert_called_once_with("local-id", "https://fal.media/files/img.jpg")

    def test_raises_if_no_api_key(self):
        import image_generator
        with patch("image_generator.FAL_API_KEY", ""):
            with pytest.raises(ValueError, match="FAL_API_KEY"):
                image_generator.get_image_job_status("any-id")


class TestFalImageJobsDb:
    def test_pending_jobs_excludes_completed(self, tmp_path):
        import db as _db
        db_path = tmp_path / "test.db"
        _db.init_user_tables(db_path)
        conn = _db._conn(db_path)
        conn.execute("INSERT INTO fal_image_jobs (job_id, fal_request_id) VALUES ('j1', 'r1')")
        conn.execute("INSERT INTO fal_image_jobs (job_id, fal_request_id, image_url) VALUES ('j2', 'r2', 'https://example.com/j2.jpg')")
        conn.commit()
        conn.close()

        pending = _db.get_pending_fal_image_jobs(db_path)
        assert len(pending) == 1
        assert pending[0]["job_id"] == "j1"

    def test_pending_jobs_empty_when_all_complete(self, tmp_path):
        import db as _db
        db_path = tmp_path / "test.db"
        _db.init_user_tables(db_path)
        conn = _db._conn(db_path)
        conn.execute("INSERT INTO fal_image_jobs (job_id, fal_request_id, image_url) VALUES ('j1', 'r1', 'https://example.com/j1.jpg')")
        conn.commit()
        conn.close()

        assert _db.get_pending_fal_image_jobs(db_path) == []

    def test_update_fal_image_job_url(self, tmp_path):
        import db as _db
        db_path = tmp_path / "test.db"
        _db.init_user_tables(db_path)
        _db.save_fal_image_job(db_path, "job-x", "req-x")
        _db.update_fal_image_job_url(db_path, "job-x", "https://example.com/job-x.jpg")

        conn = _db._conn(db_path)
        row = conn.execute("SELECT image_url FROM fal_image_jobs WHERE job_id = 'job-x'").fetchone()
        conn.close()
        assert row["image_url"] == "https://example.com/job-x.jpg"


class TestProcessPendingImageJobs:
    def test_skips_when_no_api_key(self):
        import image_generator
        with patch("image_generator.FAL_API_KEY", ""), \
             patch("db.get_pending_fal_image_jobs") as mock_pending:
            image_generator.process_pending_image_jobs()
        mock_pending.assert_not_called()

    def test_returns_early_when_no_pending_jobs(self):
        import image_generator
        with patch("image_generator.FAL_API_KEY", "test-key"), \
             patch("db.get_db_path", return_value=pathlib.Path("/tmp/test.db")), \
             patch("db.get_pending_fal_image_jobs", return_value=[]), \
             patch("requests.get") as mock_get:
            image_generator.process_pending_image_jobs()
        mock_get.assert_not_called()

    def test_marks_expired_when_both_status_and_result_return_405_and_job_is_old(self):
        import image_generator
        from datetime import datetime, timezone, timedelta
        old_ts = (datetime.now(timezone.utc) - timedelta(minutes=10)).strftime("%Y-%m-%d %H:%M:%S")
        expired_resp = _make_resp({}, status_code=405)
        expired_resp.raise_for_status = MagicMock()
        with patch("image_generator.FAL_API_KEY", "test-key"), \
             patch("db.get_db_path", return_value=pathlib.Path("/tmp/test.db")), \
             patch("db.get_pending_fal_image_jobs", return_value=[{"job_id": "j1", "fal_request_id": "r1", "created_at": old_ts}]), \
             patch("requests.get", return_value=expired_resp), \
             patch("db.update_fal_image_job_url") as mock_update:
            image_generator.process_pending_image_jobs()
        mock_update.assert_called_once_with(pathlib.Path("/tmp/test.db"), "j1", "EXPIRED")

    def test_skips_young_job_when_both_status_and_result_return_405(self):
        import image_generator
        from datetime import datetime, timezone
        young_ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
        expired_resp = _make_resp({}, status_code=405)
        expired_resp.raise_for_status = MagicMock()
        with patch("image_generator.FAL_API_KEY", "test-key"), \
             patch("db.get_db_path", return_value=pathlib.Path("/tmp/test.db")), \
             patch("db.get_pending_fal_image_jobs", return_value=[{"job_id": "j1", "fal_request_id": "r1", "created_at": young_ts}]), \
             patch("requests.get", return_value=expired_resp), \
             patch("db.update_fal_image_job_url") as mock_update:
            image_generator.process_pending_image_jobs()
        mock_update.assert_not_called()

    def test_recovers_via_result_url_when_status_returns_405(self):
        import image_generator
        from datetime import datetime, timezone
        ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
        status_405 = _make_resp({}, status_code=405)
        status_405.raise_for_status = MagicMock()
        result_resp = _make_resp({"images": [{"url": "https://fal.media/files/img.jpg"}]})
        with patch("image_generator.FAL_API_KEY", "test-key"), \
             patch("db.get_db_path", return_value=pathlib.Path("/tmp/test.db")), \
             patch("db.get_pending_fal_image_jobs", return_value=[{"job_id": "j1", "fal_request_id": "r1", "created_at": ts}]), \
             patch("requests.get", side_effect=[status_405, result_resp]), \
             patch("image_generator.download_and_save_image", return_value="https://zeusaidesign.com/files/images/j1.jpg") as mock_dl, \
             patch("db.update_fal_image_job_url") as mock_update:
            image_generator.process_pending_image_jobs()
        mock_dl.assert_called_once_with("j1", "https://fal.media/files/img.jpg")
        mock_update.assert_called_once_with(pathlib.Path("/tmp/test.db"), "j1", "https://zeusaidesign.com/files/images/j1.jpg")

    def test_skips_in_progress_jobs(self):
        import image_generator
        status_resp = _make_resp({"status": "IN_PROGRESS"})
        with patch("image_generator.FAL_API_KEY", "test-key"), \
             patch("db.get_db_path", return_value=pathlib.Path("/tmp/test.db")), \
             patch("db.get_pending_fal_image_jobs", return_value=[{"job_id": "j1", "fal_request_id": "r1"}]), \
             patch("requests.get", return_value=status_resp), \
             patch("db.update_fal_image_job_url") as mock_update:
            image_generator.process_pending_image_jobs()
        mock_update.assert_not_called()

    def test_downloads_and_saves_completed_job(self):
        import image_generator
        status_resp = _make_resp({"status": "COMPLETED"})
        result_resp = _make_resp({"images": [{"url": "https://fal.media/files/img.jpg"}]})
        with patch("image_generator.FAL_API_KEY", "test-key"), \
             patch("db.get_db_path", return_value=pathlib.Path("/tmp/test.db")), \
             patch("db.get_pending_fal_image_jobs", return_value=[{"job_id": "j1", "fal_request_id": "r1"}]), \
             patch("requests.get", side_effect=[status_resp, result_resp]), \
             patch("image_generator.download_and_save_image", return_value="https://zeusaidesign.com/files/images/j1.jpg") as mock_dl, \
             patch("db.update_fal_image_job_url") as mock_update:
            image_generator.process_pending_image_jobs()
        mock_dl.assert_called_once_with("j1", "https://fal.media/files/img.jpg")
        mock_update.assert_called_once_with(pathlib.Path("/tmp/test.db"), "j1", "https://zeusaidesign.com/files/images/j1.jpg")

    def test_exception_per_job_does_not_abort_others(self):
        import image_generator
        ok_resp = _make_resp({"status": "IN_PROGRESS"})
        with patch("image_generator.FAL_API_KEY", "test-key"), \
             patch("db.get_db_path", return_value=pathlib.Path("/tmp/test.db")), \
             patch("db.get_pending_fal_image_jobs", return_value=[
                 {"job_id": "j-bad", "fal_request_id": "r-bad"},
                 {"job_id": "j-ok", "fal_request_id": "r-ok"},
             ]), \
             patch("requests.get", side_effect=[Exception("network error"), ok_resp]), \
             patch("db.update_fal_image_job_url") as mock_update:
            image_generator.process_pending_image_jobs()
        mock_update.assert_not_called()
