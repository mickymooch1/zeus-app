"""
netlify_manager.py — Fetch files from an existing Netlify site and redeploy with changes.

Functions:
    fetch_site_files(site_id, token) -> dict[str, str]
    redeploy_site(site_id, files, token) -> str
    resolve_site_name(site_name, token) -> dict  (returns {id, ssl_url, name})
"""

import io
import json
import time
import zipfile
import urllib.request
import urllib.error
import logging

log = logging.getLogger("zeus.netlify_manager")

API = "https://api.netlify.com/api/v1"

_TEXT_EXTENSIONS = {
    ".html", ".htm", ".css", ".js", ".json", ".txt", ".xml",
    ".svg", ".md", ".toml", ".yaml", ".yml",
}


def _request(method: str, path: str, token: str, *,
             body: bytes | None = None,
             content_type: str = "application/json") -> dict | list | bytes:
    url = f"{API}{path}"
    req = urllib.request.Request(url, method=method)
    req.add_header("Authorization", f"Bearer {token}")
    req.add_header("Content-Type", content_type)
    if body:
        req.data = body
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            raw = resp.read()
            ct = resp.headers.get("Content-Type", "")
            if "application/json" in ct:
                return json.loads(raw.decode())
            return raw
    except urllib.error.HTTPError as e:
        detail = e.read().decode(errors="replace")
        raise RuntimeError(f"Netlify {method} {path} → {e.code}: {detail}") from e


def resolve_site_name(site_name: str, token: str) -> dict:
    """Look up a Netlify site by its subdomain name and return {id, ssl_url, name}.

    site_name: the slug, e.g. 'smith-plumbing-abc123' (without .netlify.app)
    Also accepts a full URL like 'https://smith-plumbing.netlify.app'.
    Raises RuntimeError if the site is not found or token is invalid.
    """
    name = site_name.strip()
    if name.startswith("http"):
        # e.g. https://smith-plumbing.netlify.app → smith-plumbing
        name = name.split("//")[-1].split(".")[0]

    data = _request("GET", f"/sites/{name}", token)
    if isinstance(data, dict) and data.get("id"):
        return {
            "id": data["id"],
            "ssl_url": data.get("ssl_url") or data.get("url", ""),
            "name": data.get("name", name),
        }
    raise RuntimeError(f"Site '{site_name}' not found on this Netlify account.")


def fetch_site_files(site_id: str, token: str) -> dict[str, str]:
    """Download all text files from the latest deploy of a Netlify site.

    Returns a dict mapping file path (e.g. '/index.html') to its text content.
    Binary files (images, fonts) are skipped.
    """
    file_list = _request("GET", f"/sites/{site_id}/files", token)
    if not isinstance(file_list, list):
        raise RuntimeError(f"Unexpected response from Netlify files API: {file_list}")

    files: dict[str, str] = {}
    for entry in file_list:
        path = entry.get("id") or entry.get("path", "")
        if not path:
            continue
        ext = "." + path.rsplit(".", 1)[-1].lower() if "." in path else ""
        if ext not in _TEXT_EXTENSIONS:
            log.debug("fetch_site_files: skipping binary %s", path)
            continue
        try:
            content = _request("GET", f"/sites/{site_id}/files{path}", token)
            if isinstance(content, bytes):
                files[path] = content.decode("utf-8", errors="replace")
            elif isinstance(content, str):
                files[path] = content
            else:
                files[path] = str(content)
        except RuntimeError as exc:
            log.warning("fetch_site_files: could not fetch %s: %s", path, exc)

    log.info("fetch_site_files: fetched %d files from site %s", len(files), site_id)
    return files


def redeploy_site(site_id: str, files: dict[str, str], token: str) -> str:
    """Zip files dict and deploy to an existing Netlify site. Returns the live URL.

    files: dict mapping path (e.g. 'index.html' or '/index.html') to text content.
    """
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for path, content in files.items():
            arc_name = path.lstrip("/")
            zf.writestr(
                arc_name,
                content.encode("utf-8") if isinstance(content, str) else content,
            )
    zip_bytes = buf.getvalue()
    log.info("redeploy_site: zipped %d files (%d bytes) for site %s",
             len(files), len(zip_bytes), site_id)

    deploy_info = _request(
        "POST", f"/sites/{site_id}/deploys",
        token,
        body=zip_bytes,
        content_type="application/zip",
    )
    deploy_id = deploy_info["id"]
    log.info("redeploy_site: deploy %s created, polling…", deploy_id)

    live_url = _poll_deploy(token, deploy_id)
    log.info("redeploy_site: site %s live at %s", site_id, live_url)
    return live_url


def _poll_deploy(token: str, deploy_id: str, timeout: int = 180) -> str:
    deadline = time.time() + timeout
    while time.time() < deadline:
        info = _request("GET", f"/deploys/{deploy_id}", token)
        state = info.get("state", "")
        if state == "ready":
            return (
                info.get("deploy_ssl_url")
                or info.get("deploy_url")
                or info.get("url", "")
            )
        if state == "error":
            raise RuntimeError(
                f"Deploy {deploy_id} failed: {info.get('error_message', 'unknown error')}"
            )
        time.sleep(4)
    raise TimeoutError(f"Deploy {deploy_id} did not reach 'ready' within {timeout}s.")
