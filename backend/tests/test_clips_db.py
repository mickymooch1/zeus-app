"""Zeus Clips — DB layer (clips.py + db.py migration). Phase 1 of the build brief:
clips / clip_likes / clip_remixes / clip_reports / clip_events tables and their
Python accessors. No HTTP here — see test_clips_api.py for the endpoints.

Conventions followed (see db.py's own init_user_tables): tables are created via
CREATE TABLE IF NOT EXISTS in the main executescript, new columns are appended as
try/except-wrapped ALTER TABLE statements, nothing is ever dropped or edited in place.
"""
import os
import pathlib
import sqlite3
import sys
from datetime import datetime, timedelta, timezone

import pytest

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))
os.environ.setdefault("ANTHROPIC_API_KEY", "test-key")
os.environ.setdefault("APIFRAME_API_KEY", "test-key")
os.environ.setdefault("SONG_STORAGE_PATH", "/tmp/test_songs")
os.environ.setdefault("SONG_PUBLIC_BASE_URL", "https://example.com/files/songs")
os.environ.setdefault("SONG_WEBHOOK_URL", "https://zeusaidesign.com/webhooks/apiframe")
os.environ.setdefault("JWT_SECRET", "test-secret-for-clips-db-tests")

import db
import clips

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


def add_song(path_, variant_id, user_id, is_public=1, status="complete", genre_tag="pop",
             style_prompt="modern pop, catchy synth melody", title="Test Song", brief="a song about summer love"):
    conn = sqlite3.connect(path_)
    conn.execute("INSERT INTO lyrics (id, user_id, brief, lyrics_text, title) VALUES (?, ?, ?, 'la la la', ?)",
                 (variant_id, user_id, brief, title))
    conn.execute(
        """INSERT INTO song_variants (id, lyric_id, user_id, style_prompt, genre_tag, status, mp3_url, is_public, created_at)
           VALUES (?, ?, ?, ?, ?, ?, '/files/songs/x.mp3', ?, ?)""",
        (variant_id, variant_id, user_id, style_prompt, genre_tag, status, is_public, NOW.isoformat()),
    )
    conn.commit()
    conn.close()


# ── schema ───────────────────────────────────────────────────────────────────

def test_init_creates_all_five_clip_tables_and_is_idempotent(path):
    db.init_user_tables(path)  # second run must not raise
    conn = sqlite3.connect(path)
    names = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    conn.close()
    assert {"clips", "clip_likes", "clip_remixes", "clip_reports", "clip_events"} <= names


# ── clips: create / read ─────────────────────────────────────────────────────

def test_create_clip_requires_the_source_song_to_be_public(path):
    add_user(path, "u1", "a@example.com")
    add_song(path, 1, "u1", is_public=0)
    with pytest.raises(clips.SourceNotPublicError):
        clips.create_clip(path, user_id="u1", song_id=1, caption="hi", media_type="cover",
                          media_url=None, clip_start_time=0.0, clip_duration=15)


def test_create_clip_with_cover_media_type_needs_no_media_url(path):
    add_user(path, "u1", "a@example.com")
    add_song(path, 1, "u1", is_public=1)
    clip_id = clips.create_clip(path, user_id="u1", song_id=1, caption="check this out",
                                media_type="cover", media_url=None, clip_start_time=2.5, clip_duration=15)
    row = clips.get_clip(path, clip_id)
    assert row["media_type"] == "cover" and row["media_url"] is None
    assert row["status"] == "published" and row["view_count"] == 0 and row["like_count"] == 0 and row["remix_count"] == 0
    assert row["clip_start_time"] == 2.5 and row["clip_duration"] == 15


@pytest.mark.parametrize("media_type", ["image", "video"])
def test_create_clip_with_uploaded_media_requires_a_url(path, media_type):
    add_user(path, "u1", "a@example.com")
    add_song(path, 1, "u1", is_public=1)
    with pytest.raises(ValueError):
        clips.create_clip(path, user_id="u1", song_id=1, caption="", media_type=media_type,
                          media_url=None, clip_start_time=0, clip_duration=15)


@pytest.mark.parametrize("duration", [10, 20, 45])
def test_create_clip_rejects_a_duration_that_is_not_15_or_30(path, duration):
    add_user(path, "u1", "a@example.com")
    add_song(path, 1, "u1", is_public=1)
    with pytest.raises(ValueError):
        clips.create_clip(path, user_id="u1", song_id=1, caption="", media_type="cover",
                          media_url=None, clip_start_time=0, clip_duration=duration)


def test_caption_over_150_chars_is_rejected(path):
    add_user(path, "u1", "a@example.com")
    add_song(path, 1, "u1", is_public=1)
    with pytest.raises(ValueError):
        clips.create_clip(path, user_id="u1", song_id=1, caption="x" * 151, media_type="cover",
                          media_url=None, clip_start_time=0, clip_duration=15)


def test_make_song_public_publishes_the_source_song_and_creates_the_clip_in_one_call(path):
    add_user(path, "u1", "a@example.com")
    add_song(path, 1, "u1", is_public=0)
    clip_id = clips.create_clip(path, user_id="u1", song_id=1, caption="", media_type="cover",
                                media_url=None, clip_start_time=0, clip_duration=15, make_song_public=True)
    assert clips.get_clip(path, clip_id) is not None
    conn = sqlite3.connect(path)
    is_pub = conn.execute("SELECT is_public FROM song_variants WHERE id = 1").fetchone()[0]
    conn.close()
    assert is_pub == 1


def test_without_make_song_public_a_private_song_still_raises_and_stays_private(path):
    add_user(path, "u1", "a@example.com")
    add_song(path, 1, "u1", is_public=0)
    with pytest.raises(clips.SourceNotPublicError):
        clips.create_clip(path, user_id="u1", song_id=1, caption="", media_type="cover",
                          media_url=None, clip_start_time=0, clip_duration=15)
    conn = sqlite3.connect(path)
    is_pub = conn.execute("SELECT is_public FROM song_variants WHERE id = 1").fetchone()[0]
    conn.close()
    assert is_pub == 0


def test_get_clip_returns_none_for_hidden_or_deleted_by_default(path):
    add_user(path, "u1", "a@example.com")
    add_song(path, 1, "u1", is_public=1)
    clip_id = clips.create_clip(path, "u1", 1, "", "cover", None, 0, 15)
    clips.set_clip_status(path, clip_id, "hidden")
    assert clips.get_clip(path, clip_id) is None
    assert clips.get_clip(path, clip_id, include_hidden=True)["status"] == "hidden"


def test_get_clip_joins_song_and_author_display_fields(path):
    add_user(path, "u1", "artist@example.com")
    add_song(path, 1, "u1", title="Summer Nights", genre_tag="pop")
    clip_id = clips.create_clip(path, "u1", 1, "caption here", "cover", None, 1.0, 15)
    row = clips.get_clip(path, clip_id)
    assert row["song_title"] == "Summer Nights"
    assert row["genre_tag"] == "pop"
    assert row["mp3_url"] == "/files/songs/x.mp3"


# ── likes ────────────────────────────────────────────────────────────────────

def test_like_is_idempotent_and_updates_the_counter(path):
    add_user(path, "u1", "a@example.com"); add_user(path, "u2", "b@example.com")
    add_song(path, 1, "u1")
    clip_id = clips.create_clip(path, "u1", 1, "", "cover", None, 0, 15)
    assert clips.like_clip(path, clip_id, "u2") == 1
    assert clips.like_clip(path, clip_id, "u2") == 1  # liking twice does not double-count
    assert clips.get_clip(path, clip_id)["like_count"] == 1


def test_unlike_decrements_and_is_safe_when_never_liked(path):
    add_user(path, "u1", "a@example.com"); add_user(path, "u2", "b@example.com")
    add_song(path, 1, "u1")
    clip_id = clips.create_clip(path, "u1", 1, "", "cover", None, 0, 15)
    clips.like_clip(path, clip_id, "u2")
    assert clips.unlike_clip(path, clip_id, "u2") == 0
    assert clips.unlike_clip(path, clip_id, "u2") == 0
    assert clips.get_clip(path, clip_id)["like_count"] == 0


# ── views: once per user/anon per clip per 24h ────────────────────────────────

def test_view_counts_once_per_user_per_24h(path):
    add_user(path, "u1", "a@example.com"); add_user(path, "u2", "b@example.com")
    add_song(path, 1, "u1")
    clip_id = clips.create_clip(path, "u1", 1, "", "cover", None, 0, 15)
    assert clips.record_view(path, clip_id, user_id="u2", anon_id=None, now=NOW) is True
    assert clips.record_view(path, clip_id, user_id="u2", anon_id=None, now=NOW + timedelta(hours=1)) is False
    assert clips.record_view(path, clip_id, user_id="u2", anon_id=None, now=NOW + timedelta(hours=25)) is True
    assert clips.get_clip(path, clip_id)["view_count"] == 2


def test_view_counts_once_per_anon_session_per_24h(path):
    add_user(path, "u1", "a@example.com")
    add_song(path, 1, "u1")
    clip_id = clips.create_clip(path, "u1", 1, "", "cover", None, 0, 15)
    assert clips.record_view(path, clip_id, user_id=None, anon_id="anon-abc", now=NOW) is True
    assert clips.record_view(path, clip_id, user_id=None, anon_id="anon-abc", now=NOW) is False
    assert clips.record_view(path, clip_id, user_id=None, anon_id="anon-xyz", now=NOW) is True
    assert clips.get_clip(path, clip_id)["view_count"] == 2


def test_view_with_neither_user_nor_anon_id_is_rejected(path):
    add_user(path, "u1", "a@example.com")
    add_song(path, 1, "u1")
    clip_id = clips.create_clip(path, "u1", 1, "", "cover", None, 0, 15)
    with pytest.raises(ValueError):
        clips.record_view(path, clip_id, user_id=None, anon_id=None, now=NOW)


# ── remixes: one row per remix attempt, completed on the first finished variant ──

def test_start_remix_creates_a_row_with_remix_song_id_null(path):
    add_user(path, "u1", "a@example.com"); add_user(path, "u2", "b@example.com")
    add_song(path, 1, "u1")
    clip_id = clips.create_clip(path, "u1", 1, "", "cover", None, 0, 15)
    remix_id = clips.start_remix(path, original_clip_id=clip_id, original_song_id=1, user_id="u2", lyric_id=99)
    row = clips.get_remix(path, remix_id)
    assert row["remix_song_id"] is None and row["lyric_id"] == 99
    assert clips.get_clip(path, clip_id)["remix_count"] == 0, "not incremented until completion"


def test_completing_a_remix_links_the_first_finished_variant_and_increments_remix_count(path):
    add_user(path, "u1", "a@example.com"); add_user(path, "u2", "b@example.com")
    add_song(path, 1, "u1")
    clip_id = clips.create_clip(path, "u1", 1, "", "cover", None, 0, 15)
    remix_id = clips.start_remix(path, clip_id, 1, "u2", lyric_id=99)
    # generation produces TWO variants under lyric_id=99 (existing convention) — BOTH complete
    # (201 first, e.g. take 1 finishing before take 2). The first call must link+count; the
    # second call, even though its own variant genuinely reached status='complete' too, must be
    # a no-op — this is the real race the brief calls out, not merely "an incomplete variant is
    # rejected" (that is a separate, weaker case — see test_a_not_yet_complete_variant_... below).
    conn = sqlite3.connect(path)
    conn.execute("INSERT INTO song_variants (id, lyric_id, user_id, style_prompt, status, take_number) "
                 "VALUES (201, 99, 'u2', 's', 'complete', 1)")
    conn.execute("INSERT INTO song_variants (id, lyric_id, user_id, style_prompt, status, take_number) "
                 "VALUES (202, 99, 'u2', 's', 'complete', 2)")
    conn.commit(); conn.close()
    assert clips.complete_remix_for_lyric(path, lyric_id=99, variant_id=201) is True
    assert clips.get_remix(path, remix_id)["remix_song_id"] == 201
    assert clips.get_clip(path, clip_id)["remix_count"] == 1
    # the SECOND variant, also genuinely complete, finishing later must not re-link or double-count
    assert clips.complete_remix_for_lyric(path, lyric_id=99, variant_id=202) is False
    assert clips.get_remix(path, remix_id)["remix_song_id"] == 201
    assert clips.get_clip(path, clip_id)["remix_count"] == 1


def test_completing_a_remix_logs_a_remix_completed_event_exactly_once(path):
    """Pre-Phase-2 review item 4: clip_events must gain a remix_completed row when a remix
    actually links — and, matching remix_count, exactly once per remix even though the
    same lyric_id's second variant also reaches complete."""
    add_user(path, "u1", "a@example.com"); add_user(path, "u2", "b@example.com")
    add_song(path, 1, "u1")
    clip_id = clips.create_clip(path, "u1", 1, "", "cover", None, 0, 15)
    clips.start_remix(path, clip_id, 1, "u2", lyric_id=99)
    conn = sqlite3.connect(path)
    conn.execute("INSERT INTO song_variants (id, lyric_id, user_id, style_prompt, status, take_number) "
                 "VALUES (201, 99, 'u2', 's', 'complete', 1)")
    conn.execute("INSERT INTO song_variants (id, lyric_id, user_id, style_prompt, status, take_number) "
                 "VALUES (202, 99, 'u2', 's', 'complete', 2)")
    conn.commit(); conn.close()
    clips.complete_remix_for_lyric(path, lyric_id=99, variant_id=201)
    clips.complete_remix_for_lyric(path, lyric_id=99, variant_id=202)
    conn = sqlite3.connect(path)
    rows = conn.execute(
        "SELECT user_id, clip_id, song_id FROM clip_events WHERE event_name = 'remix_completed'"
    ).fetchall()
    conn.close()
    assert len(rows) == 1, "must log once per remix, not once per completed variant"
    assert rows[0] == ("u2", clip_id, 201), "logs the remixer, the ORIGINAL clip, and the new song that resulted"


def test_a_not_yet_complete_variant_is_rejected_even_if_it_is_the_only_candidate(path):
    add_user(path, "u1", "a@example.com"); add_user(path, "u2", "b@example.com")
    add_song(path, 1, "u1")
    clip_id = clips.create_clip(path, "u1", 1, "", "cover", None, 0, 15)
    remix_id = clips.start_remix(path, clip_id, 1, "u2", lyric_id=99)
    conn = sqlite3.connect(path)
    conn.execute("INSERT INTO song_variants (id, lyric_id, user_id, style_prompt, status, take_number) "
                 "VALUES (201, 99, 'u2', 's', 'pending', 1)")
    conn.commit(); conn.close()
    assert clips.complete_remix_for_lyric(path, lyric_id=99, variant_id=201) is False
    assert clips.get_remix(path, remix_id)["remix_song_id"] is None


def test_a_failed_generation_leaves_remix_song_id_null_and_does_not_increment(path):
    add_user(path, "u1", "a@example.com"); add_user(path, "u2", "b@example.com")
    add_song(path, 1, "u1")
    clip_id = clips.create_clip(path, "u1", 1, "", "cover", None, 0, 15)
    remix_id = clips.start_remix(path, clip_id, 1, "u2", lyric_id=99)
    conn = sqlite3.connect(path)
    conn.execute("INSERT INTO song_variants (id, lyric_id, user_id, style_prompt, status, take_number) "
                 "VALUES (201, 99, 'u2', 's', 'failed', 1)")
    conn.commit(); conn.close()
    # a failed variant is never passed to complete_remix_for_lyric by the caller (webhooks.py only
    # calls it on status='complete') — this pins that nothing here treats a failed row as a completion.
    assert clips.complete_remix_for_lyric(path, lyric_id=99, variant_id=201) is False
    assert clips.get_remix(path, remix_id)["remix_song_id"] is None
    assert clips.get_clip(path, clip_id)["remix_count"] == 0


def test_remix_prefill_returns_sanitized_style_and_theme_never_raw_lyrics(path):
    add_user(path, "u1", "a@example.com"); add_user(path, "u2", "b@example.com")
    add_song(path, 1, "u1", genre_tag="reggae",
             style_prompt="reggae, punchy offbeat skank guitar, Bob Marley, 95 BPM",
             brief="a woman who plays a man for a fool and leaves him humiliated")
    clip_id = clips.create_clip(path, "u1", 1, "", "cover", None, 0, 15)
    prefill = clips.get_remix_prefill(path, clip_id)
    assert "bob marley" not in prefill["style_descriptors"].lower()
    assert "reggae" in prefill["style_descriptors"].lower()
    assert prefill["genre_tag"] == "reggae"
    assert "fool" in prefill["theme"].lower()
    assert "la la la" not in prefill["theme"].lower()  # never the raw lyrics_text


def test_remix_prefill_splits_a_single_genre_tag_into_genre_with_no_genre_b(path):
    add_user(path, "u1", "a@example.com")
    add_song(path, 1, "u1", genre_tag="pop")
    clip_id = clips.create_clip(path, "u1", 1, "", "cover", None, 0, 15)
    prefill = clips.get_remix_prefill(path, clip_id)
    assert prefill["genre"] == "pop"
    assert prefill["genre_b"] is None


def test_remix_prefill_splits_a_blended_genre_tag_into_genre_and_genre_b(path):
    """genre_tag stores a blend as '{genre}__{genre_b}' (see songs.py's own construction of
    it) — the remix prefill must hand generation the same two components back, not the
    joined string, or downstream genre validation rejects it outright (main.py bug, fixed
    alongside this test)."""
    add_user(path, "u1", "a@example.com")
    add_song(path, 1, "u1", genre_tag="pop__rock")
    clip_id = clips.create_clip(path, "u1", 1, "", "cover", None, 0, 15)
    prefill = clips.get_remix_prefill(path, clip_id)
    assert prefill["genre"] == "pop"
    assert prefill["genre_b"] == "rock"
    assert prefill["genre_tag"] == "pop__rock"  # unchanged — other callers still read this


# ── reports ──────────────────────────────────────────────────────────────────

def test_report_clip_records_reason_and_reporter(path):
    add_user(path, "u1", "a@example.com"); add_user(path, "u2", "b@example.com")
    add_song(path, 1, "u1")
    clip_id = clips.create_clip(path, "u1", 1, "", "cover", None, 0, 15)
    report_id = clips.report_clip(path, clip_id, reporter_id="u2", reason="spam")
    reports = clips.list_reported_clips(path)
    assert len(reports) == 1 and reports[0]["reason"] == "spam" and reports[0]["clip_id"] == clip_id


@pytest.mark.parametrize("reason", ["spam", "inappropriate", "copyright", "other"])
def test_report_accepts_all_four_reasons(path, reason):
    add_user(path, "u1", "a@example.com")
    add_song(path, 1, "u1")
    clip_id = clips.create_clip(path, "u1", 1, "", "cover", None, 0, 15)
    clips.report_clip(path, clip_id, reporter_id="u1", reason=reason)  # must not raise


def test_report_rejects_an_unknown_reason(path):
    add_user(path, "u1", "a@example.com")
    add_song(path, 1, "u1")
    clip_id = clips.create_clip(path, "u1", 1, "", "cover", None, 0, 15)
    with pytest.raises(ValueError):
        clips.report_clip(path, clip_id, reporter_id="u1", reason="nonsense")


# ── moderation ───────────────────────────────────────────────────────────────

def test_hide_and_restore_a_clip(path):
    add_user(path, "u1", "a@example.com")
    add_song(path, 1, "u1")
    clip_id = clips.create_clip(path, "u1", 1, "", "cover", None, 0, 15)
    clips.set_clip_status(path, clip_id, "hidden")
    assert clips.get_clip(path, clip_id) is None
    clips.set_clip_status(path, clip_id, "published")
    assert clips.get_clip(path, clip_id)["status"] == "published"


# ── hidden_reason: disambiguates admin moderation from a block auto-hide ────

def test_hiding_with_a_reason_stores_it(path):
    add_user(path, "u1", "a@example.com")
    add_song(path, 1, "u1")
    clip_id = clips.create_clip(path, "u1", 1, "", "cover", None, 0, 15)
    clips.set_clip_status(path, clip_id, "hidden", reason="admin_moderation")
    conn = sqlite3.connect(path)
    row = conn.execute("SELECT hidden_reason FROM clips WHERE id = ?", (clip_id,)).fetchone()
    conn.close()
    assert row[0] == "admin_moderation"


def test_restoring_clears_the_hidden_reason(path):
    add_user(path, "u1", "a@example.com")
    add_song(path, 1, "u1")
    clip_id = clips.create_clip(path, "u1", 1, "", "cover", None, 0, 15)
    clips.set_clip_status(path, clip_id, "hidden", reason="admin_moderation")
    clips.set_clip_status(path, clip_id, "published")
    conn = sqlite3.connect(path)
    row = conn.execute("SELECT hidden_reason FROM clips WHERE id = ?", (clip_id,)).fetchone()
    conn.close()
    assert row[0] is None


# ── hide_clips_for_blocked_user / restore_clips_hidden_for_reason ──────────

def test_hide_clips_for_blocked_user_hides_only_that_users_published_clips(path):
    add_user(path, "u1", "a@example.com"); add_user(path, "u2", "b@example.com")
    add_song(path, 1, "u1"); add_song(path, 2, "u2")
    c1 = clips.create_clip(path, "u1", 1, "", "cover", None, 0, 15)
    c2 = clips.create_clip(path, "u2", 2, "", "cover", None, 0, 15)

    hidden = clips.hide_clips_for_blocked_user(path, "u1")

    assert hidden == 1
    assert clips.get_clip(path, c1) is None            # u1's clip hidden
    assert clips.get_clip(path, c2) is not None         # u2's clip untouched


def test_hide_clips_for_blocked_user_does_not_overwrite_admin_moderated_ones(path):
    """A clip an admin already hid for its own reason must not have that
    reason silently replaced by the block sweep — composes with restore below."""
    add_user(path, "u1", "a@example.com")
    add_song(path, 1, "u1"); add_song(path, 2, "u1")
    c1 = clips.create_clip(path, "u1", 1, "", "cover", None, 0, 15)
    c2 = clips.create_clip(path, "u1", 2, "", "cover", None, 0, 15)
    clips.set_clip_status(path, c1, "hidden", reason="admin_moderation")

    hidden = clips.hide_clips_for_blocked_user(path, "u1")

    assert hidden == 1  # only c2 (c1 was already hidden, not 'published')
    conn = sqlite3.connect(path)
    reasons = dict(conn.execute("SELECT id, hidden_reason FROM clips WHERE user_id = 'u1'").fetchall())
    conn.close()
    assert reasons[c1] == "admin_moderation"
    assert reasons[c2] == "blocked_user"


def test_hide_clips_for_blocked_user_is_idempotent(path):
    add_user(path, "u1", "a@example.com")
    add_song(path, 1, "u1")
    clips.create_clip(path, "u1", 1, "", "cover", None, 0, 15)
    clips.hide_clips_for_blocked_user(path, "u1")
    assert clips.hide_clips_for_blocked_user(path, "u1") == 0  # already hidden — nothing left to do


def test_restore_clips_hidden_for_reason_restores_only_matching_reason(path):
    add_user(path, "u1", "a@example.com")
    add_song(path, 1, "u1"); add_song(path, 2, "u1")
    c1 = clips.create_clip(path, "u1", 1, "", "cover", None, 0, 15)
    c2 = clips.create_clip(path, "u1", 2, "", "cover", None, 0, 15)
    clips.set_clip_status(path, c1, "hidden", reason="admin_moderation")
    clips.set_clip_status(path, c2, "hidden", reason="blocked_user")

    restored = clips.restore_clips_hidden_for_reason(path, "u1", "blocked_user")

    assert restored == 1
    assert clips.get_clip(path, c1) is None            # admin-moderated clip stays hidden
    assert clips.get_clip(path, c2) is not None         # block-hidden clip restored


def test_unblock_after_admin_hid_a_clip_leaves_it_hidden(path):
    """The exact scenario the split reason exists for: block (auto-hide both),
    admin separately confirms one is genuinely bad (re-hides with its own
    reason), unblock must restore only the other one."""
    add_user(path, "u1", "a@example.com")
    add_song(path, 1, "u1"); add_song(path, 2, "u1")
    c1 = clips.create_clip(path, "u1", 1, "", "cover", None, 0, 15)
    c2 = clips.create_clip(path, "u1", 2, "", "cover", None, 0, 15)
    clips.hide_clips_for_blocked_user(path, "u1")  # both hidden, reason='blocked_user'
    clips.set_clip_status(path, c1, "hidden", reason="admin_moderation")  # admin overrides c1

    restored = clips.restore_clips_hidden_for_reason(path, "u1", "blocked_user")

    assert restored == 1
    assert clips.get_clip(path, c1) is None
    assert clips.get_clip(path, c2) is not None


def test_hidden_and_deleted_clips_are_excluded_from_feeds_and_trending(path):
    add_user(path, "u1", "a@example.com")
    add_song(path, 1, "u1"); add_song(path, 2, "u1"); add_song(path, 3, "u1")
    a = clips.create_clip(path, "u1", 1, "", "cover", None, 0, 15)
    b = clips.create_clip(path, "u1", 2, "", "cover", None, 0, 15)
    c = clips.create_clip(path, "u1", 3, "", "cover", None, 0, 15)
    clips.set_clip_status(path, b, "hidden")
    clips.set_clip_status(path, c, "deleted")
    feed_ids = {r["id"] for r in clips.list_feed(path, sort="new")}
    trending_ids = {r["id"] for r in clips.list_feed(path, sort="trending", now=NOW)}
    assert feed_ids == {a} and trending_ids == {a}


# ── trending score ───────────────────────────────────────────────────────────

def test_trending_score_matches_the_approved_formula(path):
    # (likes*3 + remixes*5 + views*0.1) / (hours_since_published + 2)^1.5
    add_user(path, "u1", "a@example.com")
    add_song(path, 1, "u1")
    clip_id = clips.create_clip(path, "u1", 1, "", "cover", None, 0, 15)
    conn = sqlite3.connect(path)
    conn.execute("UPDATE clips SET like_count=4, remix_count=2, view_count=50, "
                 "created_at=? WHERE id=?", ((NOW - timedelta(hours=10)).isoformat(), clip_id))
    conn.commit(); conn.close()
    expected = (4 * 3 + 2 * 5 + 50 * 0.1) / (10 + 2) ** 1.5
    got = clips.trending_score(path, clip_id, now=NOW)
    assert got == pytest.approx(expected, rel=1e-6)


def test_trending_sort_orders_by_score_not_recency(path):
    add_user(path, "u1", "a@example.com")
    add_song(path, 1, "u1"); add_song(path, 2, "u1")
    old_popular = clips.create_clip(path, "u1", 1, "", "cover", None, 0, 15)
    new_quiet = clips.create_clip(path, "u1", 2, "", "cover", None, 0, 15)
    conn = sqlite3.connect(path)
    conn.execute("UPDATE clips SET like_count=100, remix_count=20, view_count=1000, created_at=? WHERE id=?",
                 ((NOW - timedelta(hours=20)).isoformat(), old_popular))
    conn.execute("UPDATE clips SET created_at=? WHERE id=?", (NOW.isoformat(), new_quiet))
    conn.commit(); conn.close()
    ordered = clips.list_feed(path, sort="trending", now=NOW)
    assert [r["id"] for r in ordered] == [old_popular, new_quiet]


# ── analytics (Phase 4 groundwork) ───────────────────────────────────────────

def test_log_event_records_the_named_event(path):
    add_user(path, "u1", "a@example.com")
    clips.log_event(path, "clip_create_clicked", user_id="u1", anon_id=None, clip_id=None, song_id=None)
    conn = sqlite3.connect(path)
    row = conn.execute("SELECT event_name, user_id FROM clip_events").fetchone()
    conn.close()
    assert row == ("clip_create_clicked", "u1")


def test_log_event_accepts_anonymous_events(path):
    clips.log_event(path, "clip_viewed", user_id=None, anon_id="anon-1", clip_id=1, song_id=None)  # must not raise
