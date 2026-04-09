# PushToGitHub Tool Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a `PushToGitHub` tool to Zeus that atomically commits multiple files to `mickymooch1/zeus-app` (restricted to `web/src/`) via the GitHub Git Data API, with configurable direct-push or PR creation.

**Architecture:** A standalone `backend/github_push.py` module owns all GitHub API logic and is called from `run_turn_stream` in `zeus_agent.py` as an inline async handler (same pattern as `MultiAgentBuild`). The tool schema is registered in `TOOLS` and Zeus is instructed when to use it via the system prompt.

**Tech Stack:** Python `httpx` (async, already imported), GitHub Git Data REST API v3, `GITHUB_TOKEN` env var (Railway).

---

### Task 1: Create `backend/github_push.py`

**Files:**
- Create: `backend/github_push.py`

- [ ] **Step 1: Write the file**

```python
"""
github_push.py — Push files to GitHub via the Git Data API.

Supports atomic multi-file commits to mickymooch1/zeus-app.
All paths must be under web/src/.
"""
import base64
import os
import time

import httpx

REPO = "mickymooch1/zeus-app"
ALLOWED_PREFIX = "web/src/"
API = "https://api.github.com"


def _headers() -> dict:
    token = os.environ.get("GITHUB_TOKEN", "").strip()
    if not token:
        raise ValueError("GITHUB_TOKEN environment variable is not set")
    return {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }


def _validate_paths(files: list[dict]) -> None:
    """Raise ValueError if any path is outside web/src/."""
    for f in files:
        path = f.get("path", "")
        if not path.startswith(ALLOWED_PREFIX):
            raise ValueError(
                f"Path '{path}' is not allowed. "
                f"PushToGitHub may only write files under {ALLOWED_PREFIX}"
            )


async def push_to_github(
    files: list[dict],
    commit_message: str,
    create_pr: bool = False,
    pr_title: str = "",
    pr_body: str = "",
) -> str:
    """
    Atomically commit `files` to the repo.

    Each entry in `files`: {"path": "web/src/...", "content": "<utf-8 text>"}

    If create_pr=False: pushes directly to main.
    If create_pr=True:  creates branch zeus/update-{timestamp}, pushes there, opens PR.

    Returns a human-readable result string.
    """
    _validate_paths(files)

    headers = _headers()

    async with httpx.AsyncClient(headers=headers, timeout=30) as client:

        # 1. Get current HEAD commit SHA on main
        r = await client.get(f"{API}/repos/{REPO}/git/ref/heads/main")
        r.raise_for_status()
        head_sha = r.json()["object"]["sha"]

        # 2. Get the tree SHA from that commit
        r = await client.get(f"{API}/repos/{REPO}/git/commits/{head_sha}")
        r.raise_for_status()
        base_tree_sha = r.json()["tree"]["sha"]

        # 3. Create a blob for each file
        tree_entries = []
        for f in files:
            content_b64 = base64.b64encode(f["content"].encode("utf-8")).decode("ascii")
            r = await client.post(
                f"{API}/repos/{REPO}/git/blobs",
                json={"content": content_b64, "encoding": "base64"},
            )
            r.raise_for_status()
            blob_sha = r.json()["sha"]
            tree_entries.append({
                "path": f["path"],
                "mode": "100644",
                "type": "blob",
                "sha": blob_sha,
            })

        # 4. Create a new tree on top of the base tree
        r = await client.post(
            f"{API}/repos/{REPO}/git/trees",
            json={"base_tree": base_tree_sha, "tree": tree_entries},
        )
        r.raise_for_status()
        new_tree_sha = r.json()["sha"]

        # 5. Create a commit
        r = await client.post(
            f"{API}/repos/{REPO}/git/commits",
            json={
                "message": commit_message,
                "tree": new_tree_sha,
                "parents": [head_sha],
            },
        )
        r.raise_for_status()
        new_commit_sha = r.json()["sha"]

        if not create_pr:
            # 6a. Advance main to the new commit
            r = await client.patch(
                f"{API}/repos/{REPO}/git/refs/heads/main",
                json={"sha": new_commit_sha},
            )
            r.raise_for_status()
            file_list = ", ".join(f["path"] for f in files)
            return (
                f"✅ Pushed {len(files)} file(s) directly to main.\n"
                f"Files: {file_list}\n"
                f"Commit: {new_commit_sha[:7]} — {commit_message}\n"
                f"Railway will redeploy zeusaidesign.com automatically."
            )
        else:
            # 6b. Create a new branch and open a PR
            branch = f"zeus/update-{int(time.time())}"
            r = await client.post(
                f"{API}/repos/{REPO}/git/refs",
                json={"ref": f"refs/heads/{branch}", "sha": new_commit_sha},
            )
            r.raise_for_status()

            r = await client.post(
                f"{API}/repos/{REPO}/pulls",
                json={
                    "title": pr_title or commit_message,
                    "body": pr_body or f"Automated update by Zeus AI.\n\n{commit_message}",
                    "head": branch,
                    "base": "main",
                },
            )
            r.raise_for_status()
            pr_url = r.json()["html_url"]
            file_list = ", ".join(f["path"] for f in files)
            return (
                f"✅ Pull request created.\n"
                f"Files: {file_list}\n"
                f"PR: {pr_url}\n"
                f"Merge it to deploy to zeusaidesign.com."
            )
```

- [ ] **Step 2: Verify the file saved**

```bash
cd backend && python -c "import github_push; print('import OK')"
```
Expected: `import OK`

---

### Task 2: Write tests for `github_push.py`

**Files:**
- Create: `backend/tests/test_github_push.py`

- [ ] **Step 1: Write the test file**

```python
import base64
import os
import sys
import pathlib
from unittest.mock import AsyncMock, MagicMock, patch, call

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
    responses = {
        "get_ref":    {"object": {"sha": "abc123"}},
        "get_commit": {"tree": {"sha": "tree456"}},
        "blob":       {"sha": "blob789"},
        "tree":       {"sha": "newtree000"},
        "commit":     {"sha": "newcommit111"},
        "patch_ref":  {"ref": "refs/heads/main"},
        "post_ref":   {"ref": "refs/heads/zeus/update-123"},
        "pull":       {"html_url": pr_url},
    }

    async def mock_get(url, **kwargs):
        r = MagicMock()
        r.raise_for_status = MagicMock()
        if "/git/ref/" in url:
            r.json.return_value = responses["get_ref"]
        elif "/git/commits/" in url:
            r.json.return_value = responses["get_commit"]
        return r

    async def mock_post(url, **kwargs):
        r = MagicMock()
        r.raise_for_status = MagicMock()
        if "/git/blobs" in url:
            r.json.return_value = responses["blob"]
        elif "/git/trees" in url:
            r.json.return_value = responses["tree"]
        elif "/git/commits" in url:
            r.json.return_value = responses["commit"]
        elif "/git/refs" in url:
            r.json.return_value = responses["post_ref"]
        elif "/pulls" in url:
            r.json.return_value = responses["pull"]
        return r

    async def mock_patch(url, **kwargs):
        r = MagicMock()
        r.raise_for_status = MagicMock()
        r.json.return_value = responses["patch_ref"]
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
        assert "main" in result
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
```

- [ ] **Step 2: Run tests to verify they pass**

```bash
cd backend && python -m pytest tests/test_github_push.py -v
```

Expected: all 9 tests PASS.

---

### Task 3: Add `PushToGitHub` to `TOOLS` in `zeus_agent.py`

**Files:**
- Modify: `backend/zeus_agent.py` — TOOLS list (after `CreateBackgroundTask` entry)

- [ ] **Step 1: Add tool schema after the `CreateBackgroundTask` entry in TOOLS**

Find the end of the `CreateBackgroundTask` tool entry (look for `"Enterprise plan only."` near the closing `},`) and insert after it:

```python
    {
        "name": "PushToGitHub",
        "description": (
            "Push one or more files to the mickymooch1/zeus-app GitHub repository "
            "and commit them atomically. Restricted to paths under web/src/ only. "
            "Use this to update the zeusaidesign.com website — landing page, pricing, "
            "styles, copy, or any frontend file. "
            "Set create_pr=false for minor changes (copy fix, price update, colour change). "
            "Set create_pr=true for significant changes (redesigns, multi-section rewrites). "
            "Railway will automatically redeploy zeusaidesign.com when merged to main. "
            "Admin only."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "files": {
                    "type": "array",
                    "description": "List of files to write. Each must have 'path' (under web/src/) and 'content' (full file text).",
                    "items": {
                        "type": "object",
                        "properties": {
                            "path": {"type": "string"},
                            "content": {"type": "string"},
                        },
                        "required": ["path", "content"],
                    },
                },
                "commit_message": {
                    "type": "string",
                    "description": "Git commit message, e.g. 'feat: update pricing section'",
                },
                "create_pr": {
                    "type": "boolean",
                    "description": "true = open a pull request for review; false = push directly to main",
                    "default": False,
                },
                "pr_title": {
                    "type": "string",
                    "description": "PR title — required if create_pr is true",
                },
                "pr_body": {
                    "type": "string",
                    "description": "PR description — optional summary of changes",
                },
            },
            "required": ["files", "commit_message"],
        },
    },
```

- [ ] **Step 2: Verify TOOLS list is valid Python (no syntax errors)**

```bash
cd backend && python -c "from zeus_agent import TOOLS; names=[t['name'] for t in TOOLS]; print(names)"
```

Expected output includes `'PushToGitHub'` in the list.

---

### Task 4: Add inline handler in `run_turn_stream`

**Files:**
- Modify: `backend/zeus_agent.py` — tool dispatch block in `run_turn_stream`

- [ ] **Step 1: Add import at top of zeus_agent.py**

Find the imports section and add after the existing local imports:

```python
from github_push import push_to_github as _push_to_github
```

- [ ] **Step 2: Add handler in the tool dispatch block**

Find this block in `run_turn_stream`:

```python
                elif tb["name"] == "CreateBackgroundTask":
                    result = await _handle_create_background_task(
                        request=tb["input"].get("request", ""),
                        description=tb["input"].get("description", "Background build"),
                        history=history,
                        user_id=user_id,
                    )
                else:
                    result = _run_tool(tb["name"], tb["input"], history)
```

Replace with:

```python
                elif tb["name"] == "CreateBackgroundTask":
                    result = await _handle_create_background_task(
                        request=tb["input"].get("request", ""),
                        description=tb["input"].get("description", "Background build"),
                        history=history,
                        user_id=user_id,
                    )
                elif tb["name"] == "PushToGitHub":
                    # Admin-only gate
                    _is_admin_push = False
                    if user_id:
                        try:
                            import db as _db
                            _u = _db.get_user_by_id(_db.get_db_path(), user_id)
                            _is_admin_push = bool(_u and _u.get("is_admin", 0))
                        except Exception:
                            pass
                    if not _is_admin_push:
                        result = "❌ PushToGitHub is restricted to admin users only."
                    else:
                        try:
                            result = await _push_to_github(
                                files=tb["input"].get("files", []),
                                commit_message=tb["input"].get("commit_message", "Update from Zeus"),
                                create_pr=tb["input"].get("create_pr", False),
                                pr_title=tb["input"].get("pr_title", ""),
                                pr_body=tb["input"].get("pr_body", ""),
                            )
                        except Exception as _exc:
                            result = f"❌ PushToGitHub failed: {_exc}"
                else:
                    result = _run_tool(tb["name"], tb["input"], history)
```

- [ ] **Step 3: Verify no import/syntax errors**

```bash
cd backend && python -c "import zeus_agent; print('zeus_agent OK')"
```

Expected: `zeus_agent OK`

---

### Task 5: Update Zeus system prompt

**Files:**
- Modify: `backend/zeus_agent.py` — `ZEUS_SYSTEM_PROMPT`

- [ ] **Step 1: Add PushToGitHub description to the Memory & Learning section**

Find this line in `ZEUS_SYSTEM_PROMPT`:

```
**CreateBackgroundTask(request, description)** — when a user asks for a MultiAgentBuild
```

Insert before it:

```
**PushToGitHub(files, commit_message, create_pr, pr_title, pr_body)** — update the live
zeusaidesign.com website by pushing files directly to the GitHub repo. Restricted to
web/src/ files only. Use create_pr=false for minor updates (copy, prices, colours) and
create_pr=true for significant redesigns. Admin only — only use this tool when is_admin
is confirmed in the system context.

```

- [ ] **Step 2: Verify system prompt contains the new text**

```bash
cd backend && python -c "from zeus_agent import ZEUS_SYSTEM_PROMPT; print('PushToGitHub' in ZEUS_SYSTEM_PROMPT)"
```

Expected: `True`

---

### Task 6: Run full test suite and commit

**Files:** none new

- [ ] **Step 1: Run all backend tests**

```bash
cd backend && python -m pytest tests/test_github_push.py tests/test_db_tasks.py tests/test_tasks_endpoint.py -v
```

Expected: all tests PASS.

- [ ] **Step 2: Commit**

```bash
git add backend/github_push.py backend/tests/test_github_push.py backend/zeus_agent.py docs/superpowers/plans/2026-04-09-push-to-github.md
git commit -m "feat: add PushToGitHub tool for atomic web/src commits via Git Data API"
```
