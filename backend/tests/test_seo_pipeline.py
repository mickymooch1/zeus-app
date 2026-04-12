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
