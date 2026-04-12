import pathlib
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


import pytest
from unittest.mock import AsyncMock, MagicMock, patch


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
            patch("zeus_agent._generate_seo_files"),
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
        assert "SEO files added" in delta_texts or "sitemap" in delta_texts.lower()
