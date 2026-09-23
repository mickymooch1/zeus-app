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

import pathlib
import secrets
from datetime import datetime, timedelta, timezone

IMAGE_MAX_BYTES = 10 * 1024 * 1024
VIDEO_MAX_BYTES = 50 * 1024 * 1024

# Hardening review (2026-09-23): a per-user cap on upload-media calls, and how
# long an accepted-but-never-published upload is kept before the sweep deletes
# it. Both fixed at the brief's literal numbers rather than exposed as tunables
# nothing else needs yet.
UPLOAD_RATE_LIMIT = 20
UPLOAD_RATE_WINDOW = timedelta(hours=24)
ORPHAN_MAX_AGE = timedelta(hours=24)


def _now() -> datetime:
    return datetime.now(timezone.utc)

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


_READ_CHUNK_BYTES = 1024 * 1024  # 1MB


async def read_upload_capped(file, max_bytes: int) -> bytes:
    """Reads an UploadFile-like object (anything with an async .read(size)) in
    chunks, raising InvalidUploadError the moment the running total exceeds
    max_bytes — never buffers more than one chunk past the cap in memory.

    Replaces a bare `await file.read()`, which reads the ENTIRE body regardless
    of size before validate_image/validate_video ever get a chance to check it —
    a multi-GB request would be fully buffered (in memory or Starlette's own
    spooled temp file) before rejection. This is the server-side half of the
    hardening; see main.py's upload_clip_media for the companion Content-Length
    pre-check, which rejects an HONEST oversized request before Starlette even
    starts parsing the multipart body at all."""
    total = 0
    chunks = []
    while True:
        chunk = await file.read(_READ_CHUNK_BYTES)
        if not chunk:
            break
        total += len(chunk)
        if total > max_bytes:
            raise InvalidUploadError(f"Upload exceeds the {max_bytes // (1024 * 1024)}MB limit")
        chunks.append(chunk)
    return b"".join(chunks)


def random_filename(extension: str) -> str:
    """A stored filename that never echoes anything from the upload (name or
    extension GUESS) — only the extension this module itself determined, matching
    the existing upload_song_photo convention (uuid4-based)."""
    return f"{secrets.token_hex(16)}.{extension}"


# ── upload tracking: rate limit + orphan cleanup (hardening review, 2026-09-23) ──
# A row here is written for EVERY accepted upload-media call, not just ones that
# end up published — count_recent_uploads needs that to actually rate-limit, and
# sweep_orphaned_uploads needs it to find files nobody ever finished publishing.

def record_upload(db_path: pathlib.Path, user_id: str, filename: str, media_type: str,
                  num_bytes: int, now: datetime | None = None) -> None:
    import db
    conn = db._conn(db_path)
    try:
        conn.execute(
            "INSERT INTO clip_media_uploads (user_id, filename, media_type, bytes, created_at) "
            "VALUES (?, ?, ?, ?, ?)",
            (user_id, filename, media_type, num_bytes, (now or _now()).isoformat()),
        )
        conn.commit()
    finally:
        conn.close()


def count_recent_uploads(db_path: pathlib.Path, user_id: str, now: datetime | None = None) -> int:
    """How many uploads this user has made in the last UPLOAD_RATE_WINDOW —
    call BEFORE accepting a new one and compare against UPLOAD_RATE_LIMIT."""
    import db
    now = now or _now()
    cutoff = (now - UPLOAD_RATE_WINDOW).isoformat()
    conn = db._conn(db_path)
    try:
        return conn.execute(
            "SELECT COUNT(*) FROM clip_media_uploads WHERE user_id = ? AND created_at > ?",
            (user_id, cutoff),
        ).fetchone()[0]
    finally:
        conn.close()


def mark_upload_attached(db_path: pathlib.Path, filename: str, clip_id: int) -> None:
    """Called once POST /api/clips actually publishes a clip using this upload's
    media_url — removes it from sweep_orphaned_uploads' candidate set."""
    import db
    conn = db._conn(db_path)
    try:
        conn.execute(
            "UPDATE clip_media_uploads SET attached_clip_id = ? WHERE filename = ?",
            (clip_id, filename),
        )
        conn.commit()
    finally:
        conn.close()


def sweep_orphaned_uploads(db_path: pathlib.Path, storage_dir: pathlib.Path,
                           now: datetime | None = None) -> int:
    """Deletes uploaded files (and their tracking rows) that are older than
    ORPHAN_MAX_AGE and were never attached to a published clip. Registered as an
    hourly job in scheduler.py. Best-effort per row: a single file's delete
    failing (already gone, permissions) never aborts the rest of the sweep, and
    the row is still cleaned up either way so it can't be swept forever."""
    import db
    now = now or _now()
    cutoff = (now - ORPHAN_MAX_AGE).isoformat()
    storage_dir = pathlib.Path(storage_dir)
    conn = db._conn(db_path)
    try:
        rows = conn.execute(
            "SELECT id, filename FROM clip_media_uploads WHERE attached_clip_id IS NULL AND created_at < ?",
            (cutoff,),
        ).fetchall()
        deleted = 0
        for row_id, filename in rows:
            try:
                (storage_dir / filename).unlink(missing_ok=True)
            except OSError:
                pass  # non-fatal — the row is still cleaned up below
            conn.execute("DELETE FROM clip_media_uploads WHERE id = ?", (row_id,))
            deleted += 1
        conn.commit()
        return deleted
    finally:
        conn.close()
