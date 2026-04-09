import base64
import os
import sys
import pathlib
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))
os.environ.setdefault("GITHUB_TOKEN", "test-token")

from github_push import push_to_github, _validate_paths, ALLOWED_PREFIX


class TestValidatePaths:
    def test_allows_web_src_path(self):
        # should not raise
        _validate_paths([{"path": "web/src/pages/LandingPage.jsx", "content": "x"}])

    def test_rejects_backend_path(self):
        with pytest.raises(ValueError, match="not allowed"):
            _validate_paths([{"path": "backend/main.py", "content": "x"}])

    def test_rejects_root_path(self):
        with pytest.raises(ValueError, match="not allowed"):
            _validate_paths([{"path": "README.md", "content": "x"}])

    def test_rejects_mixed_paths(self):
        with pytest.raises(ValueError, match="not allowed"):
            _validate_paths([
                {"path": "web/src/App.jsx", "content": "ok"},
                {"path": "backend/zeus_agent.py", "content": "bad"},
            ])


def _make_mock_client(pr_url="https://github.com/mickymooch1/zeus-app/pull/1"):
    """Return a mock async httpx client that returns plausible GitHub API responses."""

    async def mock_get(url, **kwargs):
        r = MagicMock()
        r.raise_for_status = MagicMock()
        if "/git/ref/" in url:
            r.json.return_value = {"object": {"sha": "abc123"}}
        elif "/git/commits/" in url:
            r.json.return_value = {"tree": {"sha": "tree456"}}
        return r

    async def mock_post(url, **kwargs):
        r = MagicMock()
        r.raise_for_status = MagicMock()
        if "/git/blobs" in url:
            r.json.return_value = {"sha": "blob789"}
        elif "/git/trees" in url:
            r.json.return_value = {"sha": "newtree000"}
        elif "/git/commits" in url:
            r.json.return_value = {"sha": "newcommit111"}
        elif "/git/refs" in url:
            r.json.return_value = {"ref": "refs/heads/zeus/update-123"}
        elif "/pulls" in url:
            r.json.return_value = {"html_url": pr_url}
        return r

    async def mock_patch(url, **kwargs):
        r = MagicMock()
        r.raise_for_status = MagicMock()
        r.json.return_value = {"ref": "refs/heads/main"}
        return r

    client = MagicMock()
    client.get = mock_get
    client.post = mock_post
    client.patch = mock_patch
    client.__aenter__ = AsyncMock(return_value=client)
    client.__aexit__ = AsyncMock(return_value=False)
    return client


class TestPushToGithub:
    @pytest.mark.asyncio
    async def test_direct_push_returns_success(self):
        mock_client = _make_mock_client()
        with patch("github_push.httpx.AsyncClient", return_value=mock_client):
            result = await push_to_github(
                files=[{"path": "web/src/App.jsx", "content": "export default function App() {}"}],
                commit_message="feat: update App",
                create_pr=False,
            )
        assert "Pushed 1 file" in result
        assert "master" in result
        assert "zeusaidesign.com" in result

    @pytest.mark.asyncio
    async def test_pr_push_returns_pr_url(self):
        mock_client = _make_mock_client(pr_url="https://github.com/mickymooch1/zeus-app/pull/42")
        with patch("github_push.httpx.AsyncClient", return_value=mock_client):
            result = await push_to_github(
                files=[{"path": "web/src/index.css", "content": "body {}"}],
                commit_message="style: update css",
                create_pr=True,
                pr_title="Update styles",
            )
        assert "Pull request created" in result
        assert "pull/42" in result

    @pytest.mark.asyncio
    async def test_rejects_disallowed_path(self):
        with pytest.raises(ValueError, match="not allowed"):
            await push_to_github(
                files=[{"path": "backend/main.py", "content": "bad"}],
                commit_message="bad commit",
            )

    @pytest.mark.asyncio
    async def test_missing_token_raises(self):
        original = os.environ.pop("GITHUB_TOKEN", None)
        try:
            with pytest.raises(ValueError, match="GITHUB_TOKEN"):
                await push_to_github(
                    files=[{"path": "web/src/App.jsx", "content": "x"}],
                    commit_message="test",
                )
        finally:
            if original:
                os.environ["GITHUB_TOKEN"] = original
            else:
                os.environ["GITHUB_TOKEN"] = "test-token"

    @pytest.mark.asyncio
    async def test_content_is_base64_encoded(self):
        """Verify the blob POST receives base64-encoded content."""
        posted_bodies = []

        async def mock_post(url, **kwargs):
            posted_bodies.append((url, kwargs.get("json", {})))
            r = MagicMock()
            r.raise_for_status = MagicMock()
            if "/git/blobs" in url:
                r.json.return_value = {"sha": "blobsha"}
            elif "/git/trees" in url:
                r.json.return_value = {"sha": "treesha"}
            elif "/git/commits" in url:
                r.json.return_value = {"sha": "commitsha"}
            elif "/git/refs" in url:
                r.json.return_value = {"ref": "refs/heads/zeus/update-1"}
            elif "/pulls" in url:
                r.json.return_value = {"html_url": "https://github.com/pr/1"}
            return r

        mock_client = _make_mock_client()
        mock_client.post = mock_post

        content = "console.log('hello');"
        with patch("github_push.httpx.AsyncClient", return_value=mock_client):
            await push_to_github(
                files=[{"path": "web/src/script.js", "content": content}],
                commit_message="test encoding",
                create_pr=False,
            )

        blob_call = next(b for url, b in posted_bodies if "/git/blobs" in url)
        decoded = base64.b64decode(blob_call["content"]).decode("utf-8")
        assert decoded == content
        assert blob_call["encoding"] == "base64"
