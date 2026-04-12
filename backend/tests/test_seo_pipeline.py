import json
import os
import pathlib
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

import zeus_agent


class TestGenerateSeoFiles:
    def test_creates_sitemap_and_robots(self, tmp_path):
        zeus_agent._generate_seo_files(str(tmp_path), "https://test-site.netlify.app")
        assert (tmp_path / "sitemap.xml").exists()
        assert (tmp_path / "robots.txt").exists()

    def test_sitemap_contains_url_with_trailing_slash(self, tmp_path):
        zeus_agent._generate_seo_files(str(tmp_path), "https://test-site.netlify.app")
        content = (tmp_path / "sitemap.xml").read_text()
        assert "<loc>https://test-site.netlify.app/</loc>" in content

    def test_sitemap_is_valid_xml(self, tmp_path):
        zeus_agent._generate_seo_files(str(tmp_path), "https://test-site.netlify.app")
        content = (tmp_path / "sitemap.xml").read_text()
        assert content.startswith('<?xml version="1.0"')
        assert "sitemaps.org/schemas/sitemap" in content

    def test_robots_allows_all_and_references_sitemap(self, tmp_path):
        zeus_agent._generate_seo_files(str(tmp_path), "https://test-site.netlify.app")
        content = (tmp_path / "robots.txt").read_text()
        assert "User-agent: *" in content
        assert "Allow: /" in content
        assert "Sitemap: https://test-site.netlify.app/sitemap.xml" in content

    def test_trailing_slash_idempotent(self, tmp_path):
        # URL already has a trailing slash — sitemap must not double-slash
        zeus_agent._generate_seo_files(str(tmp_path), "https://test-site.netlify.app/")
        content = (tmp_path / "sitemap.xml").read_text()
        assert "netlify.app//" not in content
        assert "<loc>https://test-site.netlify.app/</loc>" in content

    def test_creates_build_dir_if_missing(self, tmp_path):
        target = str(tmp_path / "new_project")
        zeus_agent._generate_seo_files(target, "https://new-project.netlify.app")
        assert (pathlib.Path(target) / "sitemap.xml").exists()


class TestSeoFilesWiredIntoPipeline:
    @pytest.mark.asyncio
    async def test_seo_status_message_streamed(self):
        """The 'SEO files added' message must appear in the chat stream."""
        messages = []
        async def on_msg(m): messages.append(m)

        fake_history = MagicMock()

        with (
            patch("zeus_agent._run_stage_with_retry", new=AsyncMock(side_effect=[
                "SITE_NAME: wired-test\nBrief done.",
                "Research done.",
                "Build done.",
                "✅ Deployed!\n🌐 Live URL: https://wired-test.netlify.app",
            ])),
            patch("zeus_agent._generate_seo_files") as mock_generate,
            patch("zeus_agent._submit_url_to_google", create=True),
            patch("pathlib.Path.exists", return_value=True),
        ):
            await zeus_agent.run_multi_agent(
                "build a site for wired-test",
                on_msg,
                fake_history,
                user_id=None,
            )

        delta_texts = " ".join(
            m.get("delta", "") for m in messages if m.get("type") == "text"
        )
        assert "SEO files added" in delta_texts
        mock_generate.assert_called_once()


# RSA key generated once per test run (avoid per-test overhead of 2048-bit keygen)
_TEST_RSA_PEM: str | None = None


def _get_test_rsa_pem() -> str:
    global _TEST_RSA_PEM
    if _TEST_RSA_PEM is None:
        from cryptography.hazmat.primitives.asymmetric import rsa
        from cryptography.hazmat.primitives import serialization
        key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        _TEST_RSA_PEM = key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.TraditionalOpenSSL,
            encryption_algorithm=serialization.NoEncryption(),
        ).decode()
    return _TEST_RSA_PEM


class TestSubmitUrlToGoogle:
    def test_skips_silently_when_env_not_set(self):
        clean_env = {k: v for k, v in os.environ.items() if k != "GOOGLE_SERVICE_ACCOUNT_JSON"}
        with patch.dict(os.environ, clean_env, clear=True):
            zeus_agent._submit_url_to_google("https://test.netlify.app/")  # must not raise

    def test_skips_on_malformed_json(self):
        with patch.dict(os.environ, {"GOOGLE_SERVICE_ACCOUNT_JSON": "not-json"}):
            zeus_agent._submit_url_to_google("https://test.netlify.app/")  # must not raise

    def test_skips_on_missing_client_email(self):
        bad = json.dumps({"private_key": "x"})
        with patch.dict(os.environ, {"GOOGLE_SERVICE_ACCOUNT_JSON": bad}):
            zeus_agent._submit_url_to_google("https://test.netlify.app/")  # must not raise

    def test_skips_when_private_key_is_not_valid_pem(self):
        sa = json.dumps({
            "client_email": "svc@proj.iam.gserviceaccount.com",
            "private_key": "this-is-not-rsa",
            "token_uri": "https://oauth2.googleapis.com/token",
        })
        with patch.dict(os.environ, {"GOOGLE_SERVICE_ACCOUNT_JSON": sa}):
            zeus_agent._submit_url_to_google("https://test.netlify.app/")  # must not raise

    def test_skips_when_token_request_raises(self):
        sa = json.dumps({
            "client_email": "svc@proj.iam.gserviceaccount.com",
            "private_key": _get_test_rsa_pem(),
            "token_uri": "https://oauth2.googleapis.com/token",
        })
        mock_post = MagicMock(side_effect=Exception("Connection refused"))
        with patch.dict(os.environ, {"GOOGLE_SERVICE_ACCOUNT_JSON": sa}):
            with patch("requests.post", mock_post):
                zeus_agent._submit_url_to_google("https://test.netlify.app/")  # must not raise

    def test_skips_when_indexing_api_returns_403(self):
        sa = json.dumps({
            "client_email": "svc@proj.iam.gserviceaccount.com",
            "private_key": _get_test_rsa_pem(),
            "token_uri": "https://oauth2.googleapis.com/token",
        })
        token_resp = MagicMock()
        token_resp.raise_for_status.return_value = None
        token_resp.json.return_value = {"access_token": "fake-token"}

        index_resp = MagicMock()
        index_resp.raise_for_status.return_value = None
        index_resp.status_code = 403
        index_resp.text = "Permission denied — site not verified"

        with patch.dict(os.environ, {"GOOGLE_SERVICE_ACCOUNT_JSON": sa}):
            with patch("requests.post", side_effect=[token_resp, index_resp]):
                zeus_agent._submit_url_to_google("https://test.netlify.app/")  # must not raise

    def test_logs_success_on_200(self):
        sa = json.dumps({
            "client_email": "svc@proj.iam.gserviceaccount.com",
            "private_key": _get_test_rsa_pem(),
            "token_uri": "https://oauth2.googleapis.com/token",
        })
        token_resp = MagicMock()
        token_resp.raise_for_status.return_value = None
        token_resp.json.return_value = {"access_token": "fake-token"}

        index_resp = MagicMock()
        index_resp.raise_for_status.return_value = None
        index_resp.status_code = 200
        index_resp.text = '{"urlNotificationMetadata": {}}'

        with patch.dict(os.environ, {"GOOGLE_SERVICE_ACCOUNT_JSON": sa}):
            with patch("requests.post", side_effect=[token_resp, index_resp]):
                import logging
                with patch.object(logging.getLogger("zeus.agent"), "info") as mock_log:
                    zeus_agent._submit_url_to_google("https://test.netlify.app/")
                    log_calls = " ".join(str(c) for c in mock_log.call_args_list)
                    assert "200" in log_calls or "submitted" in log_calls
