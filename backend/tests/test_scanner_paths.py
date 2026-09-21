"""The scanner-path rules live in scanner_paths.py so the bot-guard middleware
(which cannot import main without a cycle) and serve_spa share ONE definition.
main keeps `_is_scanner_path` as an alias — test_serve_spa_hardening.py and any
external caller keep working."""
import os
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))
os.environ.setdefault("ANTHROPIC_API_KEY", "test-key")
os.environ.setdefault("APIFRAME_API_KEY", "test-key")
os.environ.setdefault("SONG_STORAGE_PATH", "/tmp/test_songs")
os.environ.setdefault("SONG_PUBLIC_BASE_URL", "https://example.com/files/songs")
os.environ.setdefault("SONG_WEBHOOK_URL", "https://zeusaidesign.com/webhooks/apiframe")
os.environ.setdefault("JWT_SECRET", "test-secret-for-scanner-paths-tests")

import pytest

import scanner_paths


def test_dot_segments_and_known_probes_are_scanner_paths():
    for p in (".git/config", "/.env", "a/.svn/entries", "wp-admin/x", "/wp-login.php",
              "x.PHP", "backup.sql", "/../app/requirements.txt", "cgi-bin/luci"):
        assert scanner_paths.is_scanner_path(p) is True, p


def test_real_routes_and_well_known_are_not_scanner_paths():
    for p in ("", "/", "roast", "discover/123", "robots.txt", ".well-known/assetlinks.json",
              "assets-beats/index-abc123.js"):
        assert scanner_paths.is_scanner_path(p) is False, p


# The exact probes 35.244.66.87 made on 2026-09-21 that slipped through with a 200 (SPA shell):
# a scanner reads 200 as "found". Rules were: last segment must end .php/.asp/..., or be a
# known name — so no-extension names, `.php~`/`.php.save`, and index.php/<pathinfo> all leaked.
GAP_PATHS = [
    "/phpinfo", "/info", "/_profiler/phpinfo", "/_environment",
    "/webroot/index.php/_environment",
    "/phpinfo.php", "/phpinfo.php~", "/phpinfo.php.save", "/phpinfo.php.bak", "/phpinfo.php.old",
    "/info.php.bak", "/_phpinfo.php", "/php-info.php", "/phpversion.php", "/server-info.php",
    "/old_phpinfo.php", "/admin/phpinfo.php", "/mail/phpinfo.php",
]


@pytest.mark.parametrize("p", GAP_PATHS)
def test_the_scanner_gap_paths_are_now_blocked(p):
    assert scanner_paths.is_scanner_path(p) is True, p


@pytest.mark.parametrize("p", [
    "a/index.php/b", "index.php", "x.php5", "x.PHP7", "x.phtml", "config.php.orig", "notes.txt~",
    "dump.save", "app.aspx-old", "x.jsp_bak",
])
def test_script_extensions_are_caught_in_any_segment_and_with_backup_suffixes(p):
    assert scanner_paths.is_scanner_path(p) is True, p


@pytest.mark.parametrize("p", [
    # generic words are blocked only as a WHOLE path, never as part of a real route
    "about/info", "songs/info", "info-page", "information", "informational/faq",
    # names that merely resemble a scanner token
    "phpstorm-tips", "phpinfo-guide", "environment", "profiler", "harmony", "belonging",
    "index-D-rvzpop.js", "assets-beats/SearchPage-BH2fqh7P.js", "app.js.map",
    "sitemap.xml", "manifest.webmanifest", "sw.js", "robots.txt", "favicon.ico",
    "discover/123", "songs/share/abc-123_x", "roast", "genres/hip-hop", ".well-known/assetlinks.json",
])
def test_the_tighter_rules_do_not_block_legitimate_routes(p):
    assert scanner_paths.is_scanner_path(p) is False, p


def test_no_real_frontend_route_is_blocked_by_the_rules():
    """Every client route in both frontends must survive the blocklist."""
    import re
    root = pathlib.Path(__file__).resolve().parents[2]
    hits, seen = [], 0
    for app in ("web-beats/src", "web/src"):
        for f in (root / app).rglob("*"):
            if f.suffix not in (".js", ".jsx", ".ts", ".tsx") or "node_modules" in f.parts:
                continue
            src = f.read_text(encoding="utf-8", errors="ignore")
            for m in re.finditer(r'<Route[^>]*\spath=["\'{`]+([^"\'`}]+)["\'`}]', src):
                seen += 1
                path = m.group(1)
                if scanner_paths.is_scanner_path(path.replace(":", "")):
                    hits.append((str(f.relative_to(root)), path))
    assert seen > 20, "route scan found suspiciously few routes"
    assert hits == [], f"legitimate routes would be 404'd: {hits}"


def test_main_alias_is_the_same_function():
    import main
    assert main._is_scanner_path is scanner_paths.is_scanner_path
