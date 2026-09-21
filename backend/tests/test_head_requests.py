"""HEAD must work wherever GET does.

Found 2026-09-21: every GET route answered HEAD with 405 — `HEAD /`, `HEAD /health`
and even `HEAD /robots.txt` (a real static file). FastAPI's @app.get registers GET
only (Starlette adds HEAD for plain routes, FastAPI's APIRoute does not). Uptime
monitors, link-preview tools and crawlers commonly use HEAD, and read a 405 as
"broken". Fixed by adding HEAD to every GET route once all routes are registered;
uvicorn drops the body for HEAD, so the handler needs no change.
"""
import os
import pathlib
import sys

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))
os.environ.setdefault("ANTHROPIC_API_KEY", "test-key")
os.environ.setdefault("APIFRAME_API_KEY", "test-key")
os.environ.setdefault("SONG_STORAGE_PATH", "/tmp/test_songs")
os.environ.setdefault("SONG_PUBLIC_BASE_URL", "https://example.com/files/songs")
os.environ.setdefault("SONG_WEBHOOK_URL", "https://zeusaidesign.com/webhooks/apiframe")
os.environ.setdefault("JWT_SECRET", "test-secret-for-head-request-tests")

import main


@pytest.fixture
def client(tmp_path, monkeypatch):
    dist = tmp_path / "dist"
    dist.mkdir()
    (dist / "index.html").write_text("<html>SHELL {{GENRE_COUNT}}</html>", encoding="utf-8")
    (dist / "robots.txt").write_text("User-agent: *", encoding="utf-8")
    monkeypatch.setattr(main, "_beats_dist", dist)
    monkeypatch.setattr(main, "_dist", dist)
    return TestClient(main.app)


BEATS = {"host": "zeusbeats.com"}


def test_head_health_matches_get(client):
    g, h = client.get("/health"), client.head("/health")
    assert (g.status_code, h.status_code) == (200, 200)
    assert h.headers["content-type"] == g.headers["content-type"]
    assert h.headers["content-length"] == g.headers["content-length"]


@pytest.mark.parametrize("path", ["/", "/roast", "/some/client/route", "/discover/123"])
def test_head_spa_routes_return_200_like_get(client, path):
    g, h = client.get(path, headers=BEATS), client.head(path, headers=BEATS)
    assert g.status_code == 200
    assert h.status_code == 200, f"HEAD {path} -> {h.status_code}"
    assert h.headers["content-type"] == g.headers["content-type"]


def test_head_static_file_returns_200(client):
    r = client.head("/robots.txt", headers=BEATS)
    assert r.status_code == 200 and r.headers["content-type"].startswith("text/plain")


def test_head_on_a_scanner_path_is_still_404(client):
    for p in ("/.git/config", "/wp-admin", "/phpinfo"):
        assert client.head(p, headers=BEATS).status_code == 404, p


def test_head_on_a_post_only_route_answers_exactly_like_get(client):
    """HEAD is defined as GET minus the body. A POST-only API path is answered by the SPA
    catch-all's API-prefix guard (404) for GET, so HEAD must give the same — not a 405."""
    for p in ("/auth/login", "/api/songs/generate"):
        assert client.head(p).status_code == client.get(p).status_code, p


def test_every_get_route_also_allows_head():
    missing = []
    for r in main.app.routes:
        methods = getattr(r, "methods", None)
        if methods and "GET" in methods and "HEAD" not in methods:
            missing.append(getattr(r, "path", r))
    assert missing == [], f"GET routes still answering HEAD with 405: {missing}"


def test_head_is_not_added_to_routes_that_are_not_get():
    for r in main.app.routes:
        methods = getattr(r, "methods", None)
        if methods and "GET" not in methods:
            assert "HEAD" not in methods, getattr(r, "path", r)
