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

import scanner_paths


def test_dot_segments_and_known_probes_are_scanner_paths():
    for p in (".git/config", "/.env", "a/.svn/entries", "wp-admin/x", "/wp-login.php",
              "x.PHP", "backup.sql", "/../app/requirements.txt", "cgi-bin/luci"):
        assert scanner_paths.is_scanner_path(p) is True, p


def test_real_routes_and_well_known_are_not_scanner_paths():
    for p in ("", "/", "roast", "discover/123", "robots.txt", ".well-known/assetlinks.json",
              "assets-beats/index-abc123.js"):
        assert scanner_paths.is_scanner_path(p) is False, p


def test_main_alias_is_the_same_function():
    import main
    assert main._is_scanner_path is scanner_paths.is_scanner_path
