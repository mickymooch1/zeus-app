"""Zeus Clips — upload validation. Checks the ACTUAL file content (magic bytes / real
decode), never trusts a filename extension or the browser-supplied Content-Type header,
per the build brief's explicit "renamed .exe" rejection requirement.

Images are validated by actually decoding them (PIL, already a dependency — see
_convert_photo_to_jpeg in main.py for the existing precedent) rather than a byte-prefix
guess: a real decode can't be fooled by a plausible-looking header on garbage data.
Video has no decode library available (no ffmpeg, by design — see the build brief), so
it is validated by container magic-byte signature only (the same technique file(1) and
every browser's own sniffer uses for these formats).
"""
import io
import os
import pathlib
import sqlite3
import sys
from datetime import datetime, timedelta, timezone

import pytest
from PIL import Image

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))
os.environ.setdefault("ANTHROPIC_API_KEY", "test-key")
os.environ.setdefault("APIFRAME_API_KEY", "test-key")
os.environ.setdefault("SONG_STORAGE_PATH", "/tmp/test_songs")
os.environ.setdefault("SONG_PUBLIC_BASE_URL", "https://example.com/files/songs")
os.environ.setdefault("SONG_WEBHOOK_URL", "https://zeusaidesign.com/webhooks/apiframe")
os.environ.setdefault("JWT_SECRET", "test-secret-for-clip-upload-tests")

import db
import clip_uploads

NOW = datetime(2026, 9, 23, 12, 0, 0, tzinfo=timezone.utc)


@pytest.fixture
def path(tmp_path):
    p = tmp_path / "test.db"
    db.init_user_tables(p)
    return p


def add_user(path_, uid, email):
    conn = sqlite3.connect(path_)
    conn.execute(
        "INSERT INTO users (id, email, password_hash, created_at, updated_at) VALUES (?, ?, 'x', ?, ?)",
        (uid, email, NOW.isoformat(), NOW.isoformat()),
    )
    conn.commit()
    conn.close()


def _real_image_bytes(fmt):
    img = Image.new("RGB", (4, 4), color=(200, 50, 50))
    buf = io.BytesIO()
    img.save(buf, format=fmt)
    return buf.getvalue()


# ── images: real decode, not a byte-prefix guess ─────────────────────────────

@pytest.mark.parametrize("fmt,kind", [("JPEG", "jpg"), ("PNG", "png"), ("WEBP", "webp")])
def test_a_genuine_image_of_each_accepted_kind_passes(fmt, kind):
    data = _real_image_bytes(fmt)
    assert clip_uploads.validate_image(data) == kind


def test_an_animated_gif_renamed_to_jpg_is_rejected_by_content_not_extension():
    buf = io.BytesIO()
    Image.new("RGB", (4, 4)).save(buf, format="GIF")
    with pytest.raises(clip_uploads.InvalidUploadError):
        clip_uploads.validate_image(buf.getvalue())  # GIF is a real image but not an accepted kind


def test_a_renamed_exe_claiming_to_be_a_jpg_is_rejected():
    fake = b"MZ\x90\x00\x03\x00\x00\x00\x04\x00\x00\x00\xff\xff" + b"\x00" * 200  # PE/DOS header
    with pytest.raises(clip_uploads.InvalidUploadError):
        clip_uploads.validate_image(fake)


def test_truncated_garbage_that_merely_starts_with_a_jpeg_marker_is_rejected():
    # A real magic-byte-only check would pass this (starts \xff\xd8\xff); a real decode does not.
    fake = b"\xff\xd8\xff\xe0" + os.urandom(500)
    with pytest.raises(clip_uploads.InvalidUploadError):
        clip_uploads.validate_image(fake)


def test_empty_upload_is_rejected():
    with pytest.raises(clip_uploads.InvalidUploadError):
        clip_uploads.validate_image(b"")


def test_image_over_10mb_is_rejected_even_if_genuinely_valid():
    data = _real_image_bytes("PNG")
    padded = data + b"\x00" * (10 * 1024 * 1024)  # trailing junk a real PNG decoder ignores, but size still counts
    with pytest.raises(clip_uploads.InvalidUploadError, match="10"):
        clip_uploads.validate_image(padded)


# ── video: container magic-byte signature ────────────────────────────────────

def _mp4_bytes(major=b"isom"):
    # Minimal ISOBMFF ftyp box: size(4) + 'ftyp'(4) + major_brand(4) + minor_version(4) + compat(4)
    box = (20).to_bytes(4, "big") + b"ftyp" + major + b"\x00\x00\x00\x00" + b"isom"
    return box + b"\x00" * 100


def _webm_bytes():
    return b"\x1a\x45\xdf\xa3" + b"\x00" * 100  # EBML header magic (WebM/MKV)


@pytest.mark.parametrize("data,kind", [
    (_mp4_bytes(b"isom"), "mp4"), (_mp4_bytes(b"qt  "), "mov"), (_webm_bytes(), "webm"),
])
def test_a_genuine_container_of_each_accepted_kind_passes(data, kind):
    assert clip_uploads.validate_video(data) == kind


def test_a_renamed_exe_claiming_to_be_an_mp4_is_rejected():
    fake = b"MZ\x90\x00\x03\x00\x00\x00\x04\x00\x00\x00\xff\xff" + b"\x00" * 200
    with pytest.raises(clip_uploads.InvalidUploadError):
        clip_uploads.validate_video(fake)


def test_a_jpeg_renamed_to_mp4_is_rejected():
    with pytest.raises(clip_uploads.InvalidUploadError):
        clip_uploads.validate_video(_real_image_bytes("JPEG"))


def test_video_over_50mb_is_rejected_even_if_the_container_is_genuine():
    data = _mp4_bytes() + b"\x00" * (50 * 1024 * 1024)
    with pytest.raises(clip_uploads.InvalidUploadError, match="50"):
        clip_uploads.validate_video(data)


def test_empty_video_upload_is_rejected():
    with pytest.raises(clip_uploads.InvalidUploadError):
        clip_uploads.validate_video(b"")


def test_video_too_short_to_contain_a_valid_header_is_rejected():
    with pytest.raises(clip_uploads.InvalidUploadError):
        clip_uploads.validate_video(b"\x00\x00\x00")


# ── stored filenames are randomised, never derived from the upload ──────────

def test_stored_filename_never_echoes_the_original_name_or_extension_guess():
    name1 = clip_uploads.random_filename("jpg")
    name2 = clip_uploads.random_filename("jpg")
    assert name1 != name2
    assert name1.endswith(".jpg")
    assert "/" not in name1 and ".." not in name1


# ── streaming size cap (hardening review, 2026-09-23) ────────────────────────
# A bare `await file.read()` reads the WHOLE body into memory before anything can
# check its size — a multi-GB request would be fully buffered before rejection.
# read_upload_capped reads in chunks and aborts the moment the running total would
# exceed the limit, so it never buffers more than ~one chunk past the cap.

class _BytesUploadFile:
    """Minimal async-.read() stand-in for FastAPI's UploadFile, backed by a real
    (small) bytes buffer — for exact-content round-trip checks."""
    def __init__(self, data: bytes):
        self._data = data
        self._pos = 0

    async def read(self, size=-1):
        if size is None or size < 0:
            size = len(self._data) - self._pos
        chunk = self._data[self._pos:self._pos + size]
        self._pos += len(chunk)
        return chunk


class _FillerUploadFile:
    """Emits chunk_size bytes of filler per .read() call, up to total_available —
    simulates an upload far larger than any cap WITHOUT allocating that much
    memory up front. Tracks how many bytes were actually pulled, so a test can
    assert the reader stopped early rather than draining the whole thing."""
    def __init__(self, chunk_size=65536, total_available=2 * 1024 * 1024 * 1024):
        self.chunk_size = chunk_size
        self.total_available = total_available
        self.total_read = 0

    async def read(self, size=-1):
        want = self.chunk_size if size is None or size < 0 else min(size, self.chunk_size)
        remaining = self.total_available - self.total_read
        if remaining <= 0:
            return b""
        n = min(want, remaining)
        self.total_read += n
        return b"\x00" * n


@pytest.mark.asyncio
async def test_read_upload_capped_returns_exact_bytes_when_under_the_limit():
    data = b"hello world" * 1000
    result = await clip_uploads.read_upload_capped(_BytesUploadFile(data), max_bytes=1024 * 1024)
    assert result == data


@pytest.mark.asyncio
async def test_read_upload_capped_aborts_during_the_stream_not_after_buffering_it_all():
    # A simulated ~2GB upload against a 50MB cap — if this ever buffered the whole
    # thing before checking, the test would be slow/memory-heavy; instead it must
    # raise almost immediately, having pulled only a small multiple of the cap.
    upload = _FillerUploadFile(chunk_size=1024 * 1024, total_available=2 * 1024 * 1024 * 1024)
    max_bytes = 50 * 1024 * 1024
    with pytest.raises(clip_uploads.InvalidUploadError):
        await clip_uploads.read_upload_capped(upload, max_bytes=max_bytes)
    assert upload.total_read < max_bytes * 2, (
        "must abort within a small margin of the cap, not drain the simulated 2GB stream"
    )


@pytest.mark.asyncio
async def test_read_upload_capped_accepts_exactly_the_limit():
    data = b"x" * (10 * 1024 * 1024)
    result = await clip_uploads.read_upload_capped(_BytesUploadFile(data), max_bytes=10 * 1024 * 1024)
    assert len(result) == 10 * 1024 * 1024


@pytest.mark.asyncio
async def test_read_upload_capped_rejects_one_byte_over_the_limit():
    data = b"x" * (10 * 1024 * 1024 + 1)
    with pytest.raises(clip_uploads.InvalidUploadError):
        await clip_uploads.read_upload_capped(_BytesUploadFile(data), max_bytes=10 * 1024 * 1024)


# ── per-user rate limit: max 20 uploads / 24h (hardening review, 2026-09-23) ──

def test_count_recent_uploads_finds_a_just_recorded_upload(path):
    add_user(path, "u1", "a@example.com")
    clip_uploads.record_upload(path, "u1", "abc.jpg", "image", 1024, now=NOW)
    assert clip_uploads.count_recent_uploads(path, "u1", now=NOW) == 1


def test_count_recent_uploads_only_counts_the_last_24h(path):
    add_user(path, "u1", "a@example.com")
    clip_uploads.record_upload(path, "u1", "old.jpg", "image", 1024, now=NOW - timedelta(hours=25))
    clip_uploads.record_upload(path, "u1", "fresh.jpg", "image", 1024, now=NOW - timedelta(hours=1))
    assert clip_uploads.count_recent_uploads(path, "u1", now=NOW) == 1


def test_count_recent_uploads_is_scoped_per_user(path):
    add_user(path, "u1", "a@example.com")
    add_user(path, "u2", "b@example.com")
    clip_uploads.record_upload(path, "u1", "a.jpg", "image", 1024, now=NOW)
    assert clip_uploads.count_recent_uploads(path, "u2", now=NOW) == 0


def test_twenty_recent_uploads_hit_the_limit_the_twenty_first_would_exceed(path):
    add_user(path, "u1", "a@example.com")
    for i in range(20):
        clip_uploads.record_upload(path, "u1", f"f{i}.jpg", "image", 1024, now=NOW)
    assert clip_uploads.count_recent_uploads(path, "u1", now=NOW) == 20


# ── orphan cleanup: unattached uploads older than 24h are deleted ────────────

def test_mark_upload_attached_records_the_clip_id(path):
    add_user(path, "u1", "a@example.com")
    clip_uploads.record_upload(path, "u1", "abc.jpg", "image", 1024, now=NOW)
    clip_uploads.mark_upload_attached(path, "abc.jpg", clip_id=7)
    conn = sqlite3.connect(path)
    row = conn.execute("SELECT attached_clip_id FROM clip_media_uploads WHERE filename = ?", ("abc.jpg",)).fetchone()
    conn.close()
    assert row[0] == 7


def test_sweep_deletes_an_unattached_upload_older_than_24h(path, tmp_path):
    storage = tmp_path / "clips"
    storage.mkdir()
    (storage / "orphan.jpg").write_bytes(b"data")
    add_user(path, "u1", "a@example.com")
    clip_uploads.record_upload(path, "u1", "orphan.jpg", "image", 4, now=NOW - timedelta(hours=25))

    deleted = clip_uploads.sweep_orphaned_uploads(path, storage, now=NOW)

    assert deleted == 1
    assert not (storage / "orphan.jpg").exists()
    conn = sqlite3.connect(path)
    row = conn.execute("SELECT 1 FROM clip_media_uploads WHERE filename = ?", ("orphan.jpg",)).fetchone()
    conn.close()
    assert row is None, "the tracking row must be cleaned up too, not just the file"


def test_sweep_leaves_an_attached_upload_alone_even_if_old(path, tmp_path):
    storage = tmp_path / "clips"
    storage.mkdir()
    (storage / "published.jpg").write_bytes(b"data")
    add_user(path, "u1", "a@example.com")
    clip_uploads.record_upload(path, "u1", "published.jpg", "image", 4, now=NOW - timedelta(hours=25))
    clip_uploads.mark_upload_attached(path, "published.jpg", clip_id=1)

    deleted = clip_uploads.sweep_orphaned_uploads(path, storage, now=NOW)

    assert deleted == 0
    assert (storage / "published.jpg").exists()


def test_sweep_leaves_a_recent_unattached_upload_alone(path, tmp_path):
    storage = tmp_path / "clips"
    storage.mkdir()
    (storage / "just_uploaded.jpg").write_bytes(b"data")
    add_user(path, "u1", "a@example.com")
    clip_uploads.record_upload(path, "u1", "just_uploaded.jpg", "image", 4, now=NOW - timedelta(hours=1))

    deleted = clip_uploads.sweep_orphaned_uploads(path, storage, now=NOW)

    assert deleted == 0
    assert (storage / "just_uploaded.jpg").exists()


def test_sweep_is_safe_when_the_file_is_already_missing(path, tmp_path):
    storage = tmp_path / "clips"
    storage.mkdir()
    add_user(path, "u1", "a@example.com")
    clip_uploads.record_upload(path, "u1", "already_gone.jpg", "image", 4, now=NOW - timedelta(hours=25))

    deleted = clip_uploads.sweep_orphaned_uploads(path, storage, now=NOW)  # must not raise

    assert deleted == 1
    conn = sqlite3.connect(path)
    row = conn.execute("SELECT 1 FROM clip_media_uploads WHERE filename = ?", ("already_gone.jpg",)).fetchone()
    conn.close()
    assert row is None
