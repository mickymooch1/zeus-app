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

    If create_pr=False: pushes directly to master.
    If create_pr=True:  creates branch zeus/update-{timestamp}, pushes there, opens PR.

    Returns a human-readable result string.
    """
    _validate_paths(files)

    headers = _headers()

    async with httpx.AsyncClient(headers=headers, timeout=30) as client:

        # 1. Get current HEAD commit SHA on main
        r = await client.get(f"{API}/repos/{REPO}/git/ref/heads/master")
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
                f"{API}/repos/{REPO}/git/refs/heads/master",
                json={"sha": new_commit_sha},
            )
            r.raise_for_status()
            file_list = ", ".join(f["path"] for f in files)
            return (
                f"✅ Pushed {len(files)} file(s) directly to master.\n"
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
                    "base": "master",
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
