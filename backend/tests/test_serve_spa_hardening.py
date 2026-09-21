"""serve_spa must not serve files outside the SPA build, and must not greet
scanner probes with HTTP 200.

Found 2026-09-21. A Railway log line — `GET /.git/config HTTP/1.1" 200 OK` —
prompted a look at the catch-all. Two separate problems:

  1. PATH TRAVERSAL (the serious one). serve_spa did
         candidate = dist / full_path
         if candidate.exists() and candidate.is_file(): return FileResponse(...)
     with no containment check. pathlib does not collapse `..`, and an absolute
     `full_path` (from `//etc/passwd`) REPLACES `dist` outright, so a request for
     `/../app/requirements.txt` returned that file from outside the build
     directory in production. Anything the process could read — source, the
     SQLite DB, /proc/self/environ (JWT + API secrets) — was readable.

  2. SCANNER PROBES got 200. `/.git/config`, `/.env`, `/wp-admin` all fell through
     to the SPA shell and answered 200 text/html. No git data was ever exposed
     (there is no .git in the image), but a 200 reads as a hit to scanners and to
     anyone skimming logs. They should be 404.

These call serve_spa directly with the exact `full_path` Starlette would hand it,
because httpx/TestClient normalise `..` out of URLs before sending and so cannot
reproduce the raw request an attacker sends.
"""
import asyncio
import os
import pathlib
import sys

import pytest
from starlette.requests import Request
from starlette.responses import FileResponse

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))
os.environ.setdefault("ANTHROPIC_API_KEY", "test-key")
os.environ.setdefault("APIFRAME_API_KEY", "test-key")
os.environ.setdefault("SONG_STORAGE_PATH", "/tmp/test_songs")
os.environ.setdefault("SONG_PUBLIC_BASE_URL", "https://example.com/files/songs")
os.environ.setdefault("SONG_WEBHOOK_URL", "https://zeusaidesign.com/webhooks/apiframe")
os.environ.setdefault("JWT_SECRET", "test-secret-for-serve-spa-hardening-tests")

SECRET = "TOP-SECRET-OUTSIDE-THE-BUILD"
SHELL = "SPA_SHELL_MARKER"


@pytest.fixture
def site(tmp_path, monkeypatch):
    """A fake build tree: <tmp>/dist holds the SPA; <tmp>/secret.txt is OUTSIDE it."""
    import main as _main
    dist = tmp_path / "dist"
    dist.mkdir()
    (dist / "index.html").write_text(f"<html>{SHELL} {{{{GENRE_COUNT}}}}</html>", encoding="utf-8")
    (dist / "robots.txt").write_text("User-agent: *", encoding="utf-8")
    secret = tmp_path / "secret.txt"
    secret.write_text(SECRET, encoding="utf-8")
    monkeypatch.setattr(_main, "_beats_dist", dist)
    monkeypatch.setattr(_main, "_dist", dist)
    return {"dist": dist, "secret": secret}


def _call(full_path, host="zeusbeats.com"):
    import main as _main
    scope = {
        "type": "http", "method": "GET", "scheme": "https", "path": "/" + full_path,
        "raw_path": ("/" + full_path).encode(), "query_string": b"",
        "headers": [(b"host", host.encode()), (b"user-agent", b"pytest")],
        "server": ("testserver", 443), "client": ("203.0.113.9", 1234),
    }
    return asyncio.run(_main.serve_spa(full_path, Request(scope)))


def _text(resp):
    """Whatever the response would put on the wire, as text."""
    if isinstance(resp, FileResponse):
        return pathlib.Path(resp.path).read_text(encoding="utf-8", errors="replace")
    return bytes(resp.body).decode("utf-8", errors="replace")


# ── unchanged behaviour ─────────────────────────────────────────────────────

@pytest.mark.parametrize("path", ["", "some/client/route", "discover/abc", "songs/anything"])
def test_client_side_routes_still_get_the_spa_shell(site, path):
    resp = _call(path)
    assert resp.status_code == 200
    assert SHELL in _text(resp)


def test_real_static_file_is_still_served(site):
    resp = _call("robots.txt")
    assert resp.status_code == 200
    assert isinstance(resp, FileResponse)
    assert "User-agent" in _text(resp)


# ── path traversal ──────────────────────────────────────────────────────────

def _abs_of(p: pathlib.Path) -> str:
    # What `//abs/path` hands serve_spa: an absolute-looking full_path.
    return p.as_posix()


@pytest.mark.parametrize("attempt", [
    "../secret.txt",
    "a/../../secret.txt",
    "assets/../../secret.txt",
    "./../secret.txt",
    "....//secret.txt",
])
def test_dotdot_traversal_never_leaves_the_build_dir(site, attempt):
    resp = _call(attempt)
    assert SECRET not in _text(resp), f"leaked a file outside the build via {attempt!r}"
    assert resp.status_code in (200, 404)  # 200 only ever means the SPA shell


def test_absolute_path_never_leaves_the_build_dir(site):
    # `//<abs path>` makes Starlette pass full_path="/<abs path>"; pathlib then
    # treats it as absolute and discards `dist` entirely.
    for attempt in (_abs_of(site["secret"]), "/" + _abs_of(site["secret"])):
        resp = _call(attempt)
        assert SECRET not in _text(resp), f"leaked via absolute path {attempt!r}"


def test_nul_byte_in_path_does_not_500(site):
    resp = _call("robots.txt\x00.png")
    assert resp.status_code in (200, 404)


# ── scanner probes ──────────────────────────────────────────────────────────

@pytest.mark.parametrize("probe", [
    ".git/config", ".git/HEAD", ".git/index", "a/.git/config",
    ".env", ".env.local", "config/.env", ".DS_Store", ".svn/entries", ".aws/credentials",
    "wp-admin", "wp-admin/setup-config.php", "wp-login.php", "wp-content/plugins/x",
    "wp-includes/x.js", "wp-json/wp/v2/users", "xmlrpc.php", "wordpress/wp-admin",
    "phpmyadmin/index.php", "pma/", "cgi-bin/luci", "server-status", "actuator/env",
    "shell.php", "SHELL.PHP", "a/b/c.asp", "x.aspx", "x.jsp", "backup.sql", "db.bak",
])
def test_scanner_probes_get_404_not_the_spa_shell(site, probe):
    for host in ("zeusbeats.com", "zeusaidesign.com"):
        resp = _call(probe, host=host)
        assert resp.status_code == 404, f"{probe!r} on {host} returned {resp.status_code}"
        assert SHELL not in _text(resp)


@pytest.mark.parametrize("path", [
    ".well-known/assetlinks.json", "roast", "discover/123", "songs/share/abc-123_x",
    "robots.txt", "sitemap.xml", "favicon.ico", "assets-beats/index-abc123.js",
    "manifest.webmanifest", "genres/hip-hop", "about",
])
def test_legitimate_paths_are_not_mistaken_for_scanners(path):
    import main as _main
    assert _main._is_scanner_path(path) is False
