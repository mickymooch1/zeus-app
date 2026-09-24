"""Zeus Clips MVP — DB-layer logic. Design: docs/superpowers/specs/2026-09-23-zeus-clips-mvp-design.md

A clip is a song reference + a start time + a duration + a visual (the source song's
own cover, or an uploaded image/video). No server-side rendering: the clip page plays
the song's mp3 in the browser over the visual — see the upload/HTTP-serving code in
main.py for the media side of that.

Every function takes `db_path` first, matching db.py's own convention. Timestamps are
stored as ISO-8601 UTC strings (`datetime.isoformat()`), matching the `lyrics`/`users`
convention already used elsewhere in this codebase (security_store.py's tables use a
plain 'YYYY-MM-DD HH:MM:SS' format instead — NOT reused here, to match clips' nearest
neighbours: song_variants/lyrics, which this feature is far closer to than the security
monitor).
"""
from __future__ import annotations

import pathlib
import sqlite3
from datetime import datetime, timedelta, timezone

import db
import songs as _songs

VALID_MEDIA_TYPES = {"cover", "image", "video"}
VALID_DURATIONS = {15, 30}
VALID_STATUSES = {"published", "hidden", "deleted"}
VALID_REPORT_REASONS = {"spam", "inappropriate", "copyright", "other"}
CAPTION_MAX_LEN = 150
VIEW_DEDUP_WINDOW = timedelta(hours=24)

# Trending formula (approved 2026-09-23): recency-decayed engagement score.
TRENDING_LIKE_WEIGHT = 3
TRENDING_REMIX_WEIGHT = 5
TRENDING_VIEW_WEIGHT = 0.1
TRENDING_AGE_OFFSET_HOURS = 2
TRENDING_AGE_EXPONENT = 1.5


class SourceNotPublicError(Exception):
    """Raised when a clip is created from a song that is not (and was not just made) public."""


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _conn(db_path: pathlib.Path) -> sqlite3.Connection:
    conn = db._conn(db_path)
    conn.row_factory = sqlite3.Row
    return conn


# ── clips ────────────────────────────────────────────────────────────────────

def create_clip(db_path: pathlib.Path, user_id: str, song_id: int, caption: str, media_type: str,
                media_url: str | None, clip_start_time: float, clip_duration: int,
                make_song_public: bool = False, now: datetime | None = None) -> int:
    """Publish a clip. Raises SourceNotPublicError if the source song isn't public and
    `make_song_public` wasn't asked for; raises ValueError for any other invalid input.
    When `make_song_public=True` and the song was private, it is made public and the
    clip is created in the SAME call — no retry needed."""
    if media_type not in VALID_MEDIA_TYPES:
        raise ValueError(f"media_type must be one of {VALID_MEDIA_TYPES}, got {media_type!r}")
    if media_type in ("image", "video") and not media_url:
        raise ValueError(f"media_type={media_type!r} requires a media_url")
    if clip_duration not in VALID_DURATIONS:
        raise ValueError(f"clip_duration must be one of {VALID_DURATIONS}, got {clip_duration!r}")
    if len(caption or "") > CAPTION_MAX_LEN:
        raise ValueError(f"caption must be at most {CAPTION_MAX_LEN} chars")

    now = now or _now()
    conn = _conn(db_path)
    try:
        row = conn.execute("SELECT is_public FROM song_variants WHERE id = ?", (song_id,)).fetchone()
        is_public = bool(row and row["is_public"])
        if not is_public:
            if not make_song_public:
                raise SourceNotPublicError(f"song {song_id} is not public")
            conn.execute("UPDATE song_variants SET is_public = 1 WHERE id = ?", (song_id,))

        cur = conn.execute(
            """INSERT INTO clips (user_id, song_id, caption, media_type, media_url,
                                  clip_start_time, clip_duration, status, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, 'published', ?)""",
            (user_id, song_id, caption or "", media_type, media_url, clip_start_time, clip_duration,
             now.isoformat()),
        )
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()


def get_clip(db_path: pathlib.Path, clip_id: int, include_hidden: bool = False) -> dict | None:
    conn = _conn(db_path)
    try:
        sql = """SELECT c.*, l.title AS song_title, sv.genre_tag, sv.mp3_url, sv.image_url AS song_cover_url,
                        u.artist_name, u.name AS user_name,
                        so.artist_name AS song_artist_name, so.name AS song_user_name
                 FROM clips c
                 JOIN song_variants sv ON sv.id = c.song_id
                 JOIN lyrics l ON l.id = sv.lyric_id
                 JOIN users u ON u.id = c.user_id
                 JOIN users so ON so.id = sv.user_id
                 WHERE c.id = ?"""
        if not include_hidden:
            sql += " AND c.status = 'published'"
        row = conn.execute(sql, (clip_id,)).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def set_clip_status(db_path: pathlib.Path, clip_id: int, status: str, reason: str | None = None) -> None:
    """reason is only meaningful (and only stored) when status='hidden' — e.g.
    'admin_moderation' (moderation UI) vs 'blocked_user' (account block
    auto-hide) — see hide_clips_for_blocked_user. Any other status transition
    clears it, since a published or owner-deleted clip has no hidden reason."""
    if status not in VALID_STATUSES:
        raise ValueError(f"status must be one of {VALID_STATUSES}, got {status!r}")
    conn = db._conn(db_path)
    try:
        conn.execute(
            "UPDATE clips SET status = ?, hidden_reason = ? WHERE id = ?",
            (status, reason if status == "hidden" else None, clip_id),
        )
        conn.commit()
    finally:
        conn.close()


def hide_clips_for_blocked_user(db_path: pathlib.Path, user_id: str) -> int:
    """Auto-hides every currently-published clip owned by this user — called
    when their account is blocked (see telegram_admin.py's _cmd_block_email).
    Only touches 'published' clips (never an already-hidden or owner-deleted
    one, and never overwrites an existing hidden_reason), so it composes
    correctly with a clip an admin separately moderated. Idempotent to re-run.
    Returns the count hidden."""
    conn = db._conn(db_path)
    try:
        cur = conn.execute(
            "UPDATE clips SET status = 'hidden', hidden_reason = 'blocked_user' "
            "WHERE user_id = ? AND status = 'published'",
            (user_id,),
        )
        conn.commit()
        return cur.rowcount
    finally:
        conn.close()


def restore_clips_hidden_for_reason(db_path: pathlib.Path, user_id: str, reason: str) -> int:
    """Reverses hide_clips_for_blocked_user — restores only clips hidden for
    the GIVEN reason, leaving one an admin separately hid (a different
    hidden_reason) untouched even if this same account is now unblocked.
    Returns the count restored."""
    conn = db._conn(db_path)
    try:
        cur = conn.execute(
            "UPDATE clips SET status = 'published', hidden_reason = NULL "
            "WHERE user_id = ? AND status = 'hidden' AND hidden_reason = ?",
            (user_id, reason),
        )
        conn.commit()
        return cur.rowcount
    finally:
        conn.close()


# ── likes ────────────────────────────────────────────────────────────────────

def like_clip(db_path: pathlib.Path, clip_id: int, user_id: str, now: datetime | None = None) -> int:
    """Idempotent: liking twice never double-counts. Returns the new like_count."""
    conn = db._conn(db_path)
    try:
        conn.execute(
            "INSERT OR IGNORE INTO clip_likes (clip_id, user_id, created_at) VALUES (?, ?, ?)",
            (clip_id, user_id, (now or _now()).isoformat()),
        )
        count = conn.execute("SELECT COUNT(*) FROM clip_likes WHERE clip_id = ?", (clip_id,)).fetchone()[0]
        conn.execute("UPDATE clips SET like_count = ? WHERE id = ?", (count, clip_id))
        conn.commit()
        return count
    finally:
        conn.close()


def unlike_clip(db_path: pathlib.Path, clip_id: int, user_id: str) -> int:
    conn = db._conn(db_path)
    try:
        conn.execute("DELETE FROM clip_likes WHERE clip_id = ? AND user_id = ?", (clip_id, user_id))
        count = conn.execute("SELECT COUNT(*) FROM clip_likes WHERE clip_id = ?", (clip_id,)).fetchone()[0]
        conn.execute("UPDATE clips SET like_count = ? WHERE id = ?", (count, clip_id))
        conn.commit()
        return count
    finally:
        conn.close()


# ── views ────────────────────────────────────────────────────────────────────

def record_view(db_path: pathlib.Path, clip_id: int, user_id: str | None, anon_id: str | None,
                now: datetime | None = None) -> bool:
    """Counts a view once per user (or anon session) per clip per 24h. Returns True if this
    call actually counted (i.e. the clip's view_count was incremented)."""
    if not user_id and not anon_id:
        raise ValueError("record_view requires user_id or anon_id")
    now = now or _now()
    cutoff = (now - VIEW_DEDUP_WINDOW).isoformat()
    conn = db._conn(db_path)
    try:
        if user_id:
            recent = conn.execute(
                "SELECT 1 FROM clip_views WHERE clip_id = ? AND user_id = ? AND created_at > ? LIMIT 1",
                (clip_id, user_id, cutoff),
            ).fetchone()
        else:
            recent = conn.execute(
                "SELECT 1 FROM clip_views WHERE clip_id = ? AND anon_id = ? AND created_at > ? LIMIT 1",
                (clip_id, anon_id, cutoff),
            ).fetchone()
        if recent:
            return False
        conn.execute(
            "INSERT INTO clip_views (clip_id, user_id, anon_id, created_at) VALUES (?, ?, ?, ?)",
            (clip_id, user_id, anon_id, now.isoformat()),
        )
        conn.execute("UPDATE clips SET view_count = view_count + 1 WHERE id = ?", (clip_id,))
        conn.commit()
        return True
    finally:
        conn.close()


# ── remixes ──────────────────────────────────────────────────────────────────

def start_remix(db_path: pathlib.Path, original_clip_id: int, original_song_id: int, user_id: str,
                lyric_id: int, now: datetime | None = None) -> int:
    """One row per remix attempt. remix_song_id stays NULL until complete_remix_for_lyric()
    links the first variant to finish under this lyric_id. remix_count on the original clip
    is NOT incremented here — only on completion (see complete_remix_for_lyric)."""
    conn = db._conn(db_path)
    try:
        cur = conn.execute(
            """INSERT INTO clip_remixes (original_clip_id, original_song_id, lyric_id, user_id, created_at)
               VALUES (?, ?, ?, ?, ?)""",
            (original_clip_id, original_song_id, lyric_id, user_id, (now or _now()).isoformat()),
        )
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()


def get_remix(db_path: pathlib.Path, remix_id: int) -> dict | None:
    conn = _conn(db_path)
    try:
        row = conn.execute("SELECT * FROM clip_remixes WHERE id = ?", (remix_id,)).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def complete_remix_for_lyric(db_path: pathlib.Path, lyric_id: int, variant_id: int) -> bool:
    """Call when a variant reaches status='complete' (from the webhook completion path).
    Links `variant_id` to the FIRST clip_remixes row under this lyric_id still missing a
    remix_song_id, and increments that remix's original clip's remix_count. A second variant
    completing under the same lyric_id (the standard 2-variant generation) is a no-op here —
    it finds no still-open row, since the first call already filled it in. Defensively
    re-checks variant_id's own status is 'complete' rather than trusting the caller, so a
    webhook bug that calls this on a failed/pending variant can't wrongly link or count it.
    Logs a single 'remix_completed' clip_events row in the same transaction (never once per
    variant, matching remix_count). Returns True only if this call was the one that did the
    linking."""
    conn = db._conn(db_path)
    try:
        variant = conn.execute("SELECT status FROM song_variants WHERE id = ?", (variant_id,)).fetchone()
        if not variant or variant["status"] != "complete":
            return False
        row = conn.execute(
            "SELECT id, original_clip_id, user_id FROM clip_remixes WHERE lyric_id = ? AND remix_song_id IS NULL",
            (lyric_id,),
        ).fetchone()
        if not row:
            return False
        conn.execute("UPDATE clip_remixes SET remix_song_id = ? WHERE id = ?", (variant_id, row["id"]))
        conn.execute("UPDATE clips SET remix_count = remix_count + 1 WHERE id = ?", (row["original_clip_id"],))
        conn.execute(
            "INSERT INTO clip_events (event_name, user_id, anon_id, clip_id, song_id, created_at) "
            "VALUES ('remix_completed', ?, NULL, ?, ?, ?)",
            (row["user_id"], row["original_clip_id"], variant_id, _now().isoformat()),
        )
        conn.commit()
        return True
    finally:
        conn.close()


def recount_clip_remix_count(db_path: pathlib.Path, clip_id: int) -> dict:
    """Porick's 'reset_clip_remixes CLIP_ID' — RECOUNTS remix_count from the
    actual clip_remixes rows rather than just zeroing it, so it's correct
    regardless of how many real remixes the clip has ever had. Uses the same
    condition complete_remix_for_lyric itself checks before incrementing
    (remix_song_id IS NOT NULL, i.e. genuinely completed) — a merely-started/
    still-pending remix is never counted, matching normal behaviour exactly.
    Returns {"clip_id", "old_count", "new_count"}. Raises ValueError if no
    such clip."""
    conn = db._conn(db_path)
    try:
        row = conn.execute("SELECT remix_count FROM clips WHERE id = ?", (clip_id,)).fetchone()
        if row is None:
            raise ValueError(f"no clip {clip_id}")
        old_count = row["remix_count"]
        real_count = conn.execute(
            "SELECT COUNT(*) FROM clip_remixes WHERE original_clip_id = ? AND remix_song_id IS NOT NULL",
            (clip_id,),
        ).fetchone()[0]
        conn.execute("UPDATE clips SET remix_count = ? WHERE id = ?", (real_count, clip_id))
        conn.commit()
        return {"clip_id": clip_id, "old_count": old_count, "new_count": real_count}
    finally:
        conn.close()


def _normalize_handle(name: str | None) -> str:
    return (name or "").strip().lower().replace(" ", "")


def get_user_public_profile(db_path: pathlib.Path, handle: str) -> dict | None:
    """The Zeus Clips profile page (/clips/u/:handle) — a read-only aggregate,
    not a real per-account username system (out of scope for this visual-only
    restyle). Reuses the SAME @handle every clip already derives client-side:
    artist_name, or the account name as fallback, lowercased with whitespace
    stripped (see _clip_out's artist_name fallback). Handles are therefore
    NOT guaranteed unique — a collision deterministically picks the user with
    the most recently created matching clip, never a merged/mixed set.

    Only matches a user with at least one currently-published clip: a profile
    for someone who's never used Clips isn't useful, and this keeps a clips
    URL from being usable to probe arbitrary account existence.

    Returns {"handle", "display_name", "clip_count", "total_likes",
    "avatar_url", "clips": [...]}, or None if no published clip's author
    matches this handle."""
    conn = _conn(db_path)
    try:
        rows = conn.execute(
            """SELECT c.id AS clip_id, c.media_type, c.media_url, c.view_count, c.like_count, c.created_at,
                      sv.image_url AS song_cover_url, u.id AS user_id, u.artist_name, u.name AS user_name
               FROM clips c
               JOIN song_variants sv ON sv.id = c.song_id
               JOIN users u ON u.id = c.user_id
               WHERE c.status = 'published'
               ORDER BY c.created_at DESC"""
        ).fetchall()
    finally:
        conn.close()

    target = _normalize_handle(handle)
    matches = [r for r in rows if _normalize_handle(r["artist_name"] or r["user_name"] or "zeusbeats") == target]
    if not matches:
        return None

    # rows are already ordered by created_at DESC, so the first match's
    # user_id is the "most recently active" one on a handle collision.
    winning_user_id = matches[0]["user_id"]
    display_name = matches[0]["artist_name"] or matches[0]["user_name"] or "Zeus Beats"
    user_clips = [r for r in matches if r["user_id"] == winning_user_id]

    avatar_url = None
    for r in user_clips:
        if r["media_type"] == "cover" and r["song_cover_url"]:
            avatar_url = r["song_cover_url"]
            break
        if r["media_type"] == "image" and r["media_url"]:
            avatar_url = r["media_url"]
            break

    return {
        "handle": target,
        "display_name": display_name,
        "clip_count": len(user_clips),
        "total_likes": sum(r["like_count"] for r in user_clips),
        "avatar_url": avatar_url,
        "clips": [
            {
                "id": r["clip_id"], "media_type": r["media_type"], "media_url": r["media_url"],
                "song_cover_url": r["song_cover_url"], "view_count": r["view_count"],
            }
            for r in user_clips
        ],
    }


def get_remix_prefill(db_path: pathlib.Path, clip_id: int) -> dict:
    """Remix prefill for a clip — the prefill of the clip's source song (see
    get_song_remix_prefill). {} for an unknown clip."""
    conn = _conn(db_path)
    try:
        row = conn.execute("SELECT song_id FROM clips WHERE id = ?", (clip_id,)).fetchone()
    finally:
        conn.close()
    return get_song_remix_prefill(db_path, row["song_id"]) if row else {}


def get_song_remix_prefill(db_path: pathlib.Path, song_id: int) -> dict:
    """What the prefilled create-flow needs to remix this song: SANITIZED style descriptors
    and a short theme — never the source song's lyrics_text (see the build brief's explicit
    "never pass the original lyrics"). Reuses the exact sanitizers the Search/"Inspired By"
    path already uses (songs.py), so the same artist-name/song-title stripping and length
    caps apply here — one sanitization policy, not a second copy of it. Shared by the clip
    remix (via get_remix_prefill) and the Discover song remix."""
    conn = _conn(db_path)
    try:
        row = conn.execute(
            """SELECT sv.genre_tag, sv.style_prompt, l.brief, l.title AS song_title
               FROM song_variants sv JOIN lyrics l ON l.id = sv.lyric_id
               WHERE sv.id = ?""",
            (song_id,),
        ).fetchone()
    finally:
        conn.close()
    if not row:
        return {}
    # genre_tag stores a blend as "{genre}__{genre_b}" (see songs.py's own construction of
    # it, right where it names the genre_tag column) — split it back into the two
    # components generation actually takes as separate parameters. partition() rather than
    # split() so a tag with no "__" cleanly yields genre_b="" (below, None) instead of a
    # one-item list; genre_tag is never anything but "genre" or "genre__genre_b".
    genre, _sep, genre_b = (row["genre_tag"] or "").partition("__")
    return {
        "genre_tag": row["genre_tag"],
        "genre": genre or None,
        "genre_b": genre_b or None,
        "style_descriptors": _songs.sanitize_inspired_by_descriptors(row["style_prompt"]) or "",
        "theme": _songs.sanitize_inspired_by_theme(row["brief"]) or "",
        "source_song_title": row["song_title"],
    }


# ── reports ──────────────────────────────────────────────────────────────────

def report_clip(db_path: pathlib.Path, clip_id: int, reporter_id: str, reason: str,
                now: datetime | None = None) -> int:
    if reason not in VALID_REPORT_REASONS:
        raise ValueError(f"reason must be one of {VALID_REPORT_REASONS}, got {reason!r}")
    conn = db._conn(db_path)
    try:
        cur = conn.execute(
            "INSERT INTO clip_reports (clip_id, reporter_id, reason, created_at) VALUES (?, ?, ?, ?)",
            (clip_id, reporter_id, reason, (now or _now()).isoformat()),
        )
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()


def list_reported_clips(db_path: pathlib.Path) -> list[dict]:
    conn = _conn(db_path)
    try:
        rows = conn.execute(
            """SELECT r.id AS report_id, r.clip_id, r.reporter_id, r.reason, r.created_at,
                      c.status AS clip_status, c.caption
               FROM clip_reports r JOIN clips c ON c.id = r.clip_id
               ORDER BY r.created_at DESC"""
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


# ── feeds ────────────────────────────────────────────────────────────────────

def trending_score(db_path: pathlib.Path, clip_id: int, now: datetime | None = None) -> float:
    conn = _conn(db_path)
    try:
        row = conn.execute(
            "SELECT like_count, remix_count, view_count, created_at FROM clips WHERE id = ?", (clip_id,)
        ).fetchone()
    finally:
        conn.close()
    if not row:
        raise ValueError(f"no clip {clip_id}")
    return _score(row, now or _now())


def _score(row, now: datetime) -> float:
    created = datetime.fromisoformat(row["created_at"])
    if created.tzinfo is None:
        created = created.replace(tzinfo=timezone.utc)
    hours = max(0.0, (now - created).total_seconds() / 3600)
    numerator = (row["like_count"] * TRENDING_LIKE_WEIGHT + row["remix_count"] * TRENDING_REMIX_WEIGHT
                 + row["view_count"] * TRENDING_VIEW_WEIGHT)
    return numerator / (hours + TRENDING_AGE_OFFSET_HOURS) ** TRENDING_AGE_EXPONENT


def list_feed(db_path: pathlib.Path, sort: str = "new", page: int = 0, page_size: int = 20,
             now: datetime | None = None) -> list[dict]:
    """Published clips only (hidden/deleted excluded everywhere — approved decision).
    sort='new': newest first. sort='trending': by trending_score(), newest first on ties."""
    if sort not in ("new", "trending"):
        raise ValueError("sort must be 'new' or 'trending'")
    now = now or _now()
    conn = _conn(db_path)
    try:
        rows = conn.execute(
            """SELECT c.*, l.title AS song_title, sv.genre_tag, sv.mp3_url, sv.image_url AS song_cover_url,
                      u.artist_name, u.name AS user_name,
                      so.artist_name AS song_artist_name, so.name AS song_user_name
               FROM clips c
               JOIN song_variants sv ON sv.id = c.song_id
               JOIN lyrics l ON l.id = sv.lyric_id
               JOIN users u ON u.id = c.user_id
               JOIN users so ON so.id = sv.user_id
               WHERE c.status = 'published'
               ORDER BY c.created_at DESC"""
        ).fetchall()
    finally:
        conn.close()
    items = [dict(r) for r in rows]
    if sort == "trending":
        items.sort(key=lambda r: (-_score(r, now), -datetime.fromisoformat(r["created_at"]).timestamp()))
    start = page * page_size
    return items[start:start + page_size]


# ── analytics ────────────────────────────────────────────────────────────────

def log_event(db_path: pathlib.Path, event_name: str, user_id: str | None = None, anon_id: str | None = None,
             clip_id: int | None = None, song_id: int | None = None, now: datetime | None = None,
             utm_source: str | None = None, utm_medium: str | None = None,
             utm_campaign: str | None = None, is_own_song: bool | None = None) -> None:
    """utm_* (2026-09-23): the caller's first-touch attribution, if it has any to
    give — see utils/utmAttribution.js on the frontend. Optional/keyword-only so
    every existing call site (including remix_completed above, which has no
    request context to draw attribution from at all) keeps working unchanged."""
    conn = db._conn(db_path)
    try:
        conn.execute(
            "INSERT INTO clip_events (event_name, user_id, anon_id, clip_id, song_id, created_at, "
            "utm_source, utm_medium, utm_campaign, is_own_song) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (event_name, user_id, anon_id, clip_id, song_id, (now or _now()).isoformat(),
             utm_source, utm_medium, utm_campaign, None if is_own_song is None else int(bool(is_own_song))),
        )
        conn.commit()
    finally:
        conn.close()
