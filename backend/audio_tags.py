"""Song MP3 metadata (2026-10-01): remove whatever the music provider embedded
and write our own — artist "Zeus Beats", title = the song's title.

The provider writes an ID3 frame into every file it delivers (`TXXX comment =
"made with suno; created=…; id=<provider job id>"`), visible in any music
player's file info, and the fade-out step's ffmpeg pass copied it across. Every
song MP3 the backend saves now goes through retag_song_file() once the file is
final; mp3_retag.py cleans up files saved before this existed.

Only the tag region of the file changes — the audio frames are never rewritten
(audio_digest() proves that: it hashes the file with every tag region removed).
"""
from __future__ import annotations

import hashlib
import logging
import pathlib

log = logging.getLogger("zeus.audio_tags")

ARTIST = "Zeus Beats"
FALLBACK_TITLE = "Zeus Beats song"


def song_title(db_path, variant_id: int) -> str:
    """The title users see for this song (same source as the share page)."""
    try:
        import db as _db
        variant = _db.get_song_variant_by_id(db_path, variant_id)
        if variant:
            title = _db.get_lyric_title(db_path, variant["lyric_id"])
            if title and title.strip():
                return title.strip()
    except Exception:
        log.exception("song_title: lookup failed variant_id=%s", variant_id)
    return FALLBACK_TITLE


def describe_tags(path) -> list[str]:
    """Human-readable list of every ID3v2/ID3v1/APE frame in the file."""
    from mutagen.id3 import ID3, ID3NoHeaderError
    out: list[str] = []
    try:
        tags = ID3(str(path))
        for frame in tags.values():
            if frame.FrameID == "APIC":
                out.append("APIC=<embedded picture>")
            else:
                out.append(f"{frame.HashKey}={str(frame)[:160]}")
    except ID3NoHeaderError:
        pass
    with open(path, "rb") as fh:                 # only the tail: ID3v1/APE live there
        fh.seek(0, 2)
        size = fh.tell()
        fh.seek(max(0, size - 4096))
        tail = fh.read()
    if len(tail) >= 128 and tail[-128:-125] == b"TAG":
        out.append("ID3v1=" + tail[-125:-95].decode("latin-1", "replace").strip("\x00 "))
    if b"APETAGEX" in tail:
        out.append("APEv2=<present>")
    return out


def has_provider_mark(path) -> bool:
    return any("suno" in t.lower() for t in describe_tags(path))


def wanted_tags(title: str) -> list[str]:
    return sorted([f"TIT2={title}", f"TPE1={ARTIST}"])


def is_clean(path, title: str) -> bool:
    """True when the file carries exactly our two frames and nothing else."""
    return sorted(describe_tags(path)) == wanted_tags(title)


def audio_digest(path) -> str:
    """sha256 of the audio payload only (every tag region excluded)."""
    data = pathlib.Path(path).read_bytes()
    start, end = 0, len(data)
    if data[:3] == b"ID3" and len(data) >= 10:
        size = (data[6] << 21) | (data[7] << 14) | (data[8] << 7) | data[9]
        start = 10 + size + (10 if data[5] & 0x10 else 0)
    if end - start >= 128 and data[end - 128:end - 125] == b"TAG":
        end -= 128
    ape = data.rfind(b"APETAGEX", start, end)
    if ape != -1 and end - ape <= 4096:
        end = ape
    return hashlib.sha256(data[start:end]).hexdigest()


def retag_mp3(path, title: str) -> None:
    """Strip every existing tag, then write TIT2 + TPE1. Raises on failure."""
    from mutagen import id3
    from mutagen.id3 import ID3, TIT2, TPE1
    path = str(path)
    id3.delete(path, delete_v1=True, delete_v2=True)
    try:
        from mutagen.apev2 import delete as ape_delete
        ape_delete(path)
    except Exception:
        pass  # no APE tag — the common case
    tags = ID3()
    tags.add(TIT2(encoding=3, text=title))
    tags.add(TPE1(encoding=3, text=ARTIST))
    tags.save(path, v2_version=3, padding=lambda info: 0)


def retag_song_file(path, variant_id: int, db_path=None) -> bool:
    """Best-effort hook for every place a song MP3 is saved. Never raises —
    a tagging problem must never stop a song being delivered."""
    try:
        if db_path is None:
            import db as _db
            db_path = _db.get_db_path()
        title = song_title(db_path, variant_id)
        retag_mp3(path, title)
        log.info("MP3_TAGS written variant_id=%s title=%r", variant_id, title)
        return True
    except Exception:
        log.exception("MP3_TAGS failed variant_id=%s (non-fatal — serving file with original tags)", variant_id)
        return False
