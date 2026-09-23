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
import sys

import pytest
from PIL import Image

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))
os.environ.setdefault("ANTHROPIC_API_KEY", "test-key")
os.environ.setdefault("APIFRAME_API_KEY", "test-key")
os.environ.setdefault("SONG_STORAGE_PATH", "/tmp/test_songs")
os.environ.setdefault("SONG_PUBLIC_BASE_URL", "https://example.com/files/songs")
os.environ.setdefault("SONG_WEBHOOK_URL", "https://zeusaidesign.com/webhooks/apiframe")
os.environ.setdefault("JWT_SECRET", "test-secret-for-clip-upload-tests")

import clip_uploads


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
