#!/usr/bin/env python3
"""
netlify_deploy.py — Deploy a local folder to Netlify and return the live URL.

Usage:
    python netlify_deploy.py <folder_path> [site_name]

Environment:
    NETLIFY_TOKEN  — Netlify personal access token (required)
                     Create one at: https://app.netlify.com/user/applications

Prints the live https URL on success, exits non-zero on failure.
"""

import os
import sys
import time
import zipfile
import tempfile
import urllib.request
import urllib.error
import json
from pathlib import Path


# ── Netlify API helpers ────────────────────────────────────────────────────────

API = "https://api.netlify.com/api/v1"


def _request(method: str, path: str, token: str, *,
             body: bytes | None = None,
             content_type: str = "application/json") -> dict:
    url = f"{API}{path}"
    req = urllib.request.Request(url, method=method)
    req.add_header("Authorization", f"Bearer {token}")
    req.add_header("Content-Type", content_type)
    if body:
        req.data = body
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        detail = e.read().decode(errors="replace")
        raise RuntimeError(f"Netlify {method} {path} → {e.code}: {detail}") from e


def _create_site(token: str, slug: str | None) -> dict:
    payload = json.dumps({"name": slug} if slug else {}).encode()
    try:
        return _request("POST", "/sites", token, body=payload)
    except RuntimeError as e:
        if "422" in str(e) or "409" in str(e):
            # Name conflict — let Netlify auto-assign
            print("  Name taken, using auto-generated subdomain.")
            return _request("POST", "/sites", token, body=b"{}")
        raise


def _deploy_zip(token: str, site_id: str, zip_bytes: bytes) -> dict:
    return _request(
        "POST", f"/sites/{site_id}/deploys",
        token,
        body=zip_bytes,
        content_type="application/zip",
    )


def _poll_deploy(token: str, deploy_id: str, timeout: int = 180) -> dict:
    deadline = time.time() + timeout
    dots = 0
    while time.time() < deadline:
        info = _request("GET", f"/deploys/{deploy_id}", token)
        state = info.get("state", "")
        if state == "ready":
            return info
        if state == "error":
            raise RuntimeError(f"Deploy error: {info.get('error_message', 'unknown')}")
        dots += 1
        print(f"\r  Waiting for deploy to go live{'.' * (dots % 4 + 1)}   ", end="", flush=True)
        time.sleep(4)
    raise TimeoutError(f"Deploy did not reach 'ready' state within {timeout}s.")


# ── Zip helper ─────────────────────────────────────────────────────────────────

def _zip_folder(folder: Path) -> bytes:
    tmp = tempfile.NamedTemporaryFile(suffix=".zip", delete=False)
    tmp.close()
    try:
        with zipfile.ZipFile(tmp.name, "w", zipfile.ZIP_DEFLATED) as zf:
            for file in sorted(folder.rglob("*")):
                if file.is_file():
                    zf.write(file, file.relative_to(folder))
        return Path(tmp.name).read_bytes()
    finally:
        os.unlink(tmp.name)


# ── Main deploy function ────────────────────────────────────────────────────────

def deploy(folder_path: str, site_name: str | None = None) -> str:
    """
    Deploy *folder_path* to a new Netlify site and return the live HTTPS URL.
    Raises on error.
    """
    token = os.environ.get("NETLIFY_TOKEN", "").strip()
    if not token:
        raise EnvironmentError(
            "NETLIFY_TOKEN is not set.\n"
            "Create a token at https://app.netlify.com/user/applications "
            "then set it with:\n"
            "  $env:NETLIFY_TOKEN = 'your-token'   (PowerShell)\n"
            "  set NETLIFY_TOKEN=your-token         (Command Prompt)"
        )

    folder = Path(folder_path).resolve()
    if not folder.is_dir():
        raise ValueError(f"Not a directory: {folder_path}")

    # Sanitise the site name into a valid Netlify subdomain
    slug: str | None = None
    if site_name:
        import re
        slug = re.sub(r"[^a-z0-9-]", "-",
                      site_name.lower().strip().replace("'", "").replace(".", ""))
        slug = re.sub(r"-{2,}", "-", slug).strip("-")[:63] or None

    # 1. Create site
    print(f"Creating Netlify site{f' ({slug})' if slug else ''}…")
    site = _create_site(token, slug)
    site_id   = site["id"]
    site_url  = site.get("ssl_url") or site.get("url", "")
    print(f"  Site ID: {site_id}")
    print(f"  URL:     {site_url}")

    # 2. Zip project folder
    print(f"Zipping {folder}…")
    zip_bytes = _zip_folder(folder)
    print(f"  {len(zip_bytes) / 1024:.1f} KB")

    # 3. Upload zip → create deploy
    print("Uploading to Netlify…")
    deploy_info = _deploy_zip(token, site_id, zip_bytes)
    deploy_id   = deploy_info["id"]
    print(f"  Deploy ID: {deploy_id}")

    # 4. Poll until live
    final = _poll_deploy(token, deploy_id)
    print()  # newline after dots

    live_url = (
        final.get("deploy_ssl_url")
        or final.get("deploy_url")
        or site_url
    )
    return live_url


# ── CLI entry point ────────────────────────────────────────────────────────────

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    folder_arg = sys.argv[1]
    name_arg   = sys.argv[2] if len(sys.argv) > 2 else None

    try:
        url = deploy(folder_arg, name_arg)
        print(f"\n✓ Live at: {url}")
    except Exception as exc:
        print(f"\n✗ Deploy failed: {exc}", file=sys.stderr)
        sys.exit(1)
