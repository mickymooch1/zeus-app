"""shared_at — when a song entered Discover.

is_public was a bare flag: nothing recorded WHEN it flipped, so "new on Discover
since your last visit" had to fall back to created_at. That is wrong for anything
created then shared later — a song made Monday and shared Friday looked a week old
and never badged.

Set by TRIGGER rather than by the endpoint, deliberately. telegram_admin exposes
`db exec "UPDATE ..."`, arbitrary SQL straight against this database, which no
application code can intercept. A trigger covers that, the share endpoint, and any
writer added later. The endpoint deliberately does not also write it — two writers
for one fact is how semantics drift, and update_song_variant binds values
(SET k = ?) so it cannot express COALESCE(shared_at, ?) anyway.
"""
import os
import pathlib
import sqlite3
import sys
import tempfile
import time

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))
os.environ.setdefault("ANTHROPIC_API_KEY", "test-key")
os.environ.setdefault("APIFRAME_API_KEY", "test-key")
os.environ.setdefault("SONG_WEBHOOK_URL", "https://example.com/webhooks/apiframe")
# test_toggle_endpoint_does_not_write_shared_at imports main, which pulls in webhooks
# and reads these at module scope. Declared here so the file passes standalone rather
# than only when the caller happens to export them.
os.environ.setdefault("SONG_STORAGE_PATH", "/tmp/test_songs")
os.environ.setdefault("SONG_PUBLIC_BASE_URL", "https://example.com/files/songs")
os.environ.setdefault("JWT_SECRET", "test-secret-for-shared-at-tests")

import db as _db

_NEW_COUNT_SQL = """SELECT COUNT(*) FROM song_variants
                    WHERE is_public = 1 AND status = 'complete' AND mp3_url IS NOT NULL
                      AND COALESCE(shared_at, created_at) > ?"""


def _fresh():
    p = pathlib.Path(tempfile.mkdtemp()) / "shared.db"
    _db.init_user_tables(p)
    return p, sqlite3.connect(str(p))


def _insert(c, vid, is_public=0, created="2020-01-01 00:00:00", shared=None):
    c.execute(
        """INSERT INTO song_variants
           (id, lyric_id, user_id, style_prompt, genre_tag, status, mp3_url, is_public, created_at, shared_at)
           VALUES (?, 1, 'u', 's', 'pop', 'complete', 'm.mp3', ?, ?, ?)""",
        (vid, is_public, created, shared),
    )
    c.commit()


def _shared_at(c, vid):
    return c.execute("SELECT shared_at FROM song_variants WHERE id = ?", (vid,)).fetchone()[0]


# ── Schema ───────────────────────────────────────────────────────────────────

def test_column_and_both_triggers_exist():
    _, c = _fresh()
    cols = [r[1] for r in c.execute("PRAGMA table_info(song_variants)")]
    assert "shared_at" in cols
    triggers = {r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='trigger'")}
    assert "trg_song_variants_shared_at" in triggers
    assert "trg_song_variants_shared_at_insert" in triggers


def test_column_is_nullable_with_no_backfill():
    """A DEFAULT would stamp every pre-existing public song with the migration time
    and announce all of them as new at once."""
    _, c = _fresh()
    _insert(c, 1)
    assert _shared_at(c, 1) is None


# ── The trigger, including paths application code cannot reach ───────────────

def test_share_stamps_shared_at_via_raw_sql():
    """Raw UPDATE, no application code — this is the `db exec` path."""
    _, c = _fresh()
    _insert(c, 1)
    c.execute("UPDATE song_variants SET is_public = 1 WHERE id = 1")
    c.commit()
    assert _shared_at(c, 1) is not None


def test_unsharing_does_not_stamp_or_clear():
    _, c = _fresh()
    _insert(c, 1)
    c.execute("UPDATE song_variants SET is_public = 1 WHERE id = 1"); c.commit()
    first = _shared_at(c, 1)
    c.execute("UPDATE song_variants SET is_public = 0 WHERE id = 1"); c.commit()
    assert _shared_at(c, 1) == first, "unshare must not touch shared_at"


def test_resharing_keeps_the_first_share_time():
    """Otherwise unshare-then-reshare would re-announce a song as new."""
    _, c = _fresh()
    _insert(c, 1)
    c.execute("UPDATE song_variants SET is_public = 1 WHERE id = 1"); c.commit()
    first = _shared_at(c, 1)
    c.execute("UPDATE song_variants SET is_public = 0 WHERE id = 1"); c.commit()
    time.sleep(1.1)                      # CURRENT_TIMESTAMP has 1-second resolution
    c.execute("UPDATE song_variants SET is_public = 1 WHERE id = 1"); c.commit()
    assert _shared_at(c, 1) == first


def test_a_private_row_is_never_stamped():
    _, c = _fresh()
    _insert(c, 1)
    c.execute("UPDATE song_variants SET is_public = 0 WHERE id = 1"); c.commit()
    assert _shared_at(c, 1) is None


def test_inserting_an_already_public_row_is_stamped():
    """AFTER UPDATE alone would miss `db exec "INSERT ... is_public=1"`, landing a
    song in Discover that could never badge."""
    _, c = _fresh()
    _insert(c, 1, is_public=1)
    assert _shared_at(c, 1) is not None


def test_ordinary_private_insert_is_untouched():
    _, c = _fresh()
    _insert(c, 1, is_public=0)
    assert _shared_at(c, 1) is None


# ── The new-count predicate ──────────────────────────────────────────────────

def test_created_long_ago_but_shared_today_counts_as_new():
    """The whole point. Under the old `created_at > ?` this returned 0."""
    _, c = _fresh()
    _insert(c, 1, created="2020-01-01 00:00:00")
    c.execute("UPDATE song_variants SET is_public = 1 WHERE id = 1"); c.commit()

    since = "2020-06-01 00:00:00"
    assert c.execute(_NEW_COUNT_SQL, (since,)).fetchone()[0] == 1
    old_logic = """SELECT COUNT(*) FROM song_variants
                   WHERE is_public = 1 AND status = 'complete' AND mp3_url IS NOT NULL
                     AND created_at > ?"""
    assert c.execute(old_logic, (since,)).fetchone()[0] == 0, "this is the bug being fixed"


def test_rows_predating_the_column_fall_back_to_created_at():
    """No backfill, so legacy rows must still behave exactly as before."""
    _, c = _fresh()
    _insert(c, 1, is_public=0, created="2026-08-20 12:00:00")
    # Simulate a legacy row: public, but shared_at never recorded.
    c.execute("UPDATE song_variants SET is_public = 1 WHERE id = 1"); c.commit()
    c.execute("UPDATE song_variants SET shared_at = NULL WHERE id = 1"); c.commit()
    assert _shared_at(c, 1) is None
    assert c.execute(_NEW_COUNT_SQL, ("2026-08-19 00:00:00",)).fetchone()[0] == 1
    assert c.execute(_NEW_COUNT_SQL, ("2026-08-21 00:00:00",)).fetchone()[0] == 0


def test_private_songs_never_counted():
    _, c = _fresh()
    _insert(c, 1, is_public=0, created="2026-08-22 00:00:00")
    assert c.execute(_NEW_COUNT_SQL, ("2020-01-01 00:00:00",)).fetchone()[0] == 0


# ── The endpoint must not become a second writer ─────────────────────────────

def test_toggle_endpoint_does_not_write_shared_at():
    """One fact, one writer. update_song_variant binds values (SET k = ?) and cannot
    express COALESCE anyway."""
    import inspect
    import main

    src = inspect.getsource(main.toggle_variant_share)
    code = "\n".join(l for l in src.splitlines() if not l.lstrip().startswith("#"))
    assert "shared_at" not in code, "the trigger owns shared_at — do not double-write it"
