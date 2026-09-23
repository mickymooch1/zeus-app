"""Zeus Clips — upload validation. Design: docs/superpowers/specs/2026-09-23-zeus-clips-mvp-design.md

Never trusts a filename extension or the browser's Content-Type header (both are
attacker-controlled). Images are validated by an actual decode (PIL — already a
dependency, see main.py's _convert_photo_to_jpeg for the existing precedent); a
renamed .exe or truncated garbage that merely starts with a plausible byte prefix
fails a real decode even though a byte-signature-only check would pass it. Video has
no decode library available (no ffmpeg — a deliberate constraint, see the build
brief), so it is validated by container magic-byte signature only.

NOTE (flagged for the brief's Phase 1 review): this module does NOT verify video
DURATION server-side. The "max 30s" rule is enforced client-side only (the upload UI
reads the browser <video> element's own .duration before allowing Publish). Verifying
duration server-side would need either an ffmpeg subprocess (ruled out) or a hand-
rolled MP4/WebM box parser (real, security-relevant binary-parsing code, on top of
everything else in this module) — worth a dedicated pass if you want it enforced
server-side rather than skipped in v1.
"""
from __future__ import annotations

import secrets

IMAGE_MAX_BYTES = 10 * 1024 * 1024
VIDEO_MAX_BYTES = 50 * 1024 * 1024

_IMAGE_KINDS = {"JPEG": "jpg", "PNG": "png", "WEBP": "webp"}  # PIL format name -> stored extension


class InvalidUploadError(ValueError):
    """The uploaded file failed validation — never exposes why in detail to the
    client beyond a generic reason, so a rejection can't be used to fingerprint
    the validator."""


def validate_image(data: bytes) -> str:
    """Returns the accepted kind ('jpg'|'png'|'webp') or raises InvalidUploadError.
    Validates by actually decoding the image, not by its header bytes alone."""
    if not data:
        raise InvalidUploadError("Empty upload")
    if len(data) > IMAGE_MAX_BYTES:
        raise InvalidUploadError("Image must be under 10MB")
    from PIL import Image
    import io
    try:
        with Image.open(io.BytesIO(data)) as img:
            img.verify()  # structural check — cheap, but doesn't decode pixel data
        with Image.open(io.BytesIO(data)) as img:
            fmt = img.format
            img.load()  # force a full decode — catches truncated/corrupt data verify() can miss
    except Exception:
        raise InvalidUploadError("Not a valid image")
    kind = _IMAGE_KINDS.get(fmt or "")
    if not kind:
        raise InvalidUploadError(f"Unsupported image format {fmt!r} — use JPEG, PNG, or WebP")
    return kind


def validate_video(data: bytes) -> str:
    """Returns the accepted kind ('mp4'|'mov'|'webm') or raises InvalidUploadError.
    Container-signature check only (see module docstring re: duration)."""
    if not data:
        raise InvalidUploadError("Empty upload")
    if len(data) > VIDEO_MAX_BYTES:
        raise InvalidUploadError("Video must be under 50MB")
    if len(data) < 12:
        raise InvalidUploadError("Not a valid video file")

    if data[4:8] == b"ftyp":
        # ISOBMFF (MP4/MOV/M4V family) — the major brand at offset 8 tells them apart.
        # 'qt  ' is QuickTime's own brand; everything else in this family (isom, mp42,
        # mp41, M4V , avc1, ...) is treated as mp4 — an iPhone MOV recording and a
        # browser-recorded mp4 both land in one of these two buckets in practice.
        major_brand = data[8:12]
        return "mov" if major_brand == b"qt  " else "mp4"
    if data[:4] == b"\x1a\x45\xdf\xa3":
        return "webm"  # EBML header — WebM (and Matroska, not offered as an upload choice)
    raise InvalidUploadError("Not a valid video file — use MP4, WebM, or MOV")


def random_filename(extension: str) -> str:
    """A stored filename that never echoes anything from the upload (name or
    extension GUESS) — only the extension this module itself determined, matching
    the existing upload_song_photo convention (uuid4-based)."""
    return f"{secrets.token_hex(16)}.{extension}"
