"""Tests for cover-art resolution in youtube_uploader.

Regression coverage for the intermittent "blank cover art on YouTube" bug:
the uploader used to silently mux a black frame whenever the local
{id}_cover.jpg was missing. It must instead fall back to the DB's public
image_url (fetching it), and fail loudly if no cover can be obtained.
"""
import os
import pathlib
import sys
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))

os.environ.setdefault("SONG_STORAGE_PATH", "/tmp/test_songs")
os.environ.setdefault("SONG_PUBLIC_BASE_URL", "https://example.com/files/songs")

import youtube_uploader  # noqa: E402


def _variant(**over):
    v = {"id": 4242, "image_url": "https://example.com/files/songs/4242_cover.jpg"}
    v.update(over)
    return v


def test_resolve_prefers_local_cover_file(tmp_path):
    storage = tmp_path / "songs"
    storage.mkdir()
    cover = storage / "4242_cover.jpg"
    cover.write_bytes(b"x" * 2048)

    got = youtube_uploader._resolve_cover_image(_variant(), str(storage), tmp_path)
    assert got == cover


def test_resolve_falls_back_to_plain_jpg(tmp_path):
    """Apiframe path saves the cover as {id}.jpg (no _cover suffix)."""
    storage = tmp_path / "songs"
    storage.mkdir()
    plain = storage / "4242.jpg"
    plain.write_bytes(b"x" * 2048)

    got = youtube_uploader._resolve_cover_image(_variant(), str(storage), tmp_path)
    assert got == plain


def test_resolve_downloads_image_url_when_local_missing(tmp_path):
    storage = tmp_path / "songs"
    storage.mkdir()  # no local cover files
    dl_dir = tmp_path / "dl"
    dl_dir.mkdir()

    resp = MagicMock()
    resp.content = b"y" * 4096
    resp.raise_for_status = MagicMock()

    with patch.object(youtube_uploader.requests, "get", return_value=resp) as mock_get:
        got = youtube_uploader._resolve_cover_image(_variant(), str(storage), dl_dir)

    mock_get.assert_called_once()
    assert got.exists()
    assert got.read_bytes() == b"y" * 4096


def test_resolve_raises_when_no_cover_anywhere(tmp_path):
    storage = tmp_path / "songs"
    storage.mkdir()
    with pytest.raises(ValueError):
        youtube_uploader._resolve_cover_image(_variant(image_url=""), str(storage), tmp_path)


def test_resolve_raises_when_image_url_not_public(tmp_path):
    """Guard against the old bug where image_url held a local path, not a URL."""
    storage = tmp_path / "songs"
    storage.mkdir()
    v = _variant(image_url="/data/songs/4242_cover.jpg")
    with pytest.raises(ValueError):
        youtube_uploader._resolve_cover_image(v, str(storage), tmp_path)


def test_resolve_raises_when_download_fails(tmp_path):
    storage = tmp_path / "songs"
    storage.mkdir()
    with patch.object(youtube_uploader.requests, "get", side_effect=RuntimeError("boom")), \
         patch.object(youtube_uploader.time, "sleep", return_value=None):
        with pytest.raises(ValueError):
            youtube_uploader._resolve_cover_image(_variant(), str(storage), tmp_path)


def test_resolve_never_returns_black_frame_silently(tmp_path):
    """The whole point: a missing cover must raise, not degrade to black."""
    storage = tmp_path / "songs"
    storage.mkdir()
    with patch.object(youtube_uploader.requests, "get", side_effect=RuntimeError("boom")), \
         patch.object(youtube_uploader.time, "sleep", return_value=None):
        with pytest.raises(ValueError):
            youtube_uploader._resolve_cover_image(_variant(), str(storage), tmp_path)
