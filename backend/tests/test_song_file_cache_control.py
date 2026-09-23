"""Pre-Phase-2 review item 5: /files/songs/*.mp3 currently serves with NO Cache-Control
header at all (confirmed live on zeusaidesign.com — Range/206 already works, caching
does not).

Deliberately NOT `immutable` / 1-year, unlike /files/clips: song mp3s are named
`{variant_id}.mp3` — NOT content-hashed like /assets or randomised like /files/clips —
so a filename CAN be rewritten in place (webhooks.py's AUTO_EXTEND path does exactly
that, swapping a short take for a longer one under the same filename; currently
disabled via _AUTO_EXTEND_ENABLED = False, but dormant, not impossible). `max-age=86400`
with no `immutable` means a rewrite self-heals within a day instead of staying stale
for up to a year. /files/clips keeps the long/immutable treatment since its upload
filenames are random and genuinely never rewritten."""
import importlib
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
os.environ.setdefault("JWT_SECRET", "test-secret-for-song-cache-control-tests")


@pytest.fixture
def app_client(tmp_path, monkeypatch):
    monkeypatch.setenv("ZEUS_DATA_DIR", str(tmp_path))
    song_storage = tmp_path / "songs"
    song_storage.mkdir()
    monkeypatch.setenv("SONG_STORAGE_PATH", str(song_storage))
    import main as _main
    importlib.reload(_main)
    with TestClient(_main.app) as client:
        yield client, song_storage


def test_song_mp3_is_served_with_a_day_long_non_immutable_cache_control_header(app_client):
    client, song_storage = app_client
    (song_storage / "42.mp3").write_bytes(b"fake mp3 bytes for range testing 0123456789")
    r = client.get("/files/songs/42.mp3")
    assert r.status_code == 200
    cc = r.headers.get("cache-control", "")
    assert cc == "public, max-age=86400", (
        "must NOT be immutable/1-year — an in-place AUTO_EXTEND rewrite must self-heal within a day"
    )


def test_song_mp3_still_supports_range_requests_with_cache_control(app_client):
    client, song_storage = app_client
    (song_storage / "42.mp3").write_bytes(b"fake mp3 bytes for range testing 0123456789")
    r = client.get("/files/songs/42.mp3", headers={"Range": "bytes=0-3"})
    assert r.status_code == 206
    assert r.headers.get("content-range", "").startswith("bytes 0-3/")
    assert r.headers.get("cache-control", "") == "public, max-age=86400"
