"""Account deletion cleanup tool (built 2026-09-23 for the Zeus Clips remix QA
test cleanup, made reusable via Porick — see telegram_admin.py's
delete_user/reset_clip_remixes commands for the Telegram-facing half).

db.discover_user_reference_tables / preview_user_deletion / delete_user_account
live in db.py because they span nearly every table in the schema, not just
clips ones. Dynamic discovery (PRAGMA table_info against sqlite_master) is the
whole point: a hand-picked table list goes stale the moment a new table with a
user_id column is added, silently leaving orphans. _EXTRA_USER_REFERENCE_COLUMNS
covers the one table found (2026-09-23 schema review) that references a user
under a non-standard column name (clip_reports.reporter_id).
"""
import os
import pathlib
import sqlite3
import sys

import pytest

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))
os.environ.setdefault("ANTHROPIC_API_KEY", "test-key")
os.environ.setdefault("APIFRAME_API_KEY", "test-key")
os.environ.setdefault("SONG_STORAGE_PATH", "/tmp/test_songs")
os.environ.setdefault("SONG_PUBLIC_BASE_URL", "https://example.com/files/songs")
os.environ.setdefault("SONG_WEBHOOK_URL", "https://zeusaidesign.com/webhooks/apiframe")
os.environ.setdefault("JWT_SECRET", "test-secret-for-delete-user-tests")

import db


@pytest.fixture
def path(tmp_path):
    p = tmp_path / "test.db"
    db.init_user_tables(p)
    return p


def _add_user(path_, uid, email, is_admin=0):
    conn = sqlite3.connect(path_)
    conn.execute(
        "INSERT INTO users (id, email, password_hash, is_admin, created_at, updated_at) "
        "VALUES (?, ?, 'x', ?, 'now', 'now')",
        (uid, email, is_admin),
    )
    conn.commit()
    conn.close()


# ── discovery ────────────────────────────────────────────────────────────────

def test_discover_user_reference_tables_finds_the_standard_user_id_columns(path):
    tables = db.discover_user_reference_tables(path)
    assert tables["lyrics"] == "user_id"
    assert tables["song_variants"] == "user_id"
    assert tables["clip_events"] == "user_id"
    assert tables["song_credits"] == "user_id"


def test_discover_user_reference_tables_includes_the_non_standard_reporter_id_column(path):
    """clip_reports references a user via reporter_id, not user_id — the plain
    PRAGMA sweep would silently miss it without _EXTRA_USER_REFERENCE_COLUMNS."""
    tables = db.discover_user_reference_tables(path)
    assert tables["clip_reports"] == "reporter_id"


def test_discover_user_reference_tables_never_includes_users_itself(path):
    # users.id is the primary key being referenced, not a self-reference to delete by.
    tables = db.discover_user_reference_tables(path)
    assert "users" not in tables


# ── preview (dry run) ────────────────────────────────────────────────────────

def test_preview_returns_none_user_for_an_unknown_email(path):
    preview = db.preview_user_deletion(path, "nobody@example.com")
    assert preview["user"] is None


def test_preview_lists_rows_across_multiple_tables_without_deleting_anything(path):
    _add_user(path, "u1", "target@example.com")
    conn = sqlite3.connect(path)
    conn.execute("INSERT INTO lyrics (id, user_id, brief, lyrics_text, title) VALUES (1, 'u1', '', 'la', 't')")
    conn.execute("INSERT INTO song_credits (user_id, balance, monthly_allowance) VALUES ('u1', 2, 3)")
    conn.commit(); conn.close()

    preview = db.preview_user_deletion(path, "target@example.com")
    assert preview["user"]["email"] == "target@example.com"
    assert len(preview["rows"]["lyrics"]) == 1
    assert len(preview["rows"]["song_credits"]) == 1

    # Nothing was actually deleted.
    conn = sqlite3.connect(path)
    assert conn.execute("SELECT COUNT(*) FROM lyrics").fetchone()[0] == 1
    assert conn.execute("SELECT COUNT(*) FROM users").fetchone()[0] == 1
    conn.close()


def test_preview_refuses_for_an_admin_account(path):
    _add_user(path, "u1", "admin@example.com", is_admin=1)
    with pytest.raises(db.AdminAccountProtectedError):
        db.preview_user_deletion(path, "admin@example.com")


def test_preview_finds_orphaned_song_variant_photos_and_playlist_songs(path):
    _add_user(path, "u1", "target@example.com")
    conn = sqlite3.connect(path)
    conn.execute("INSERT INTO lyrics (id, user_id, brief, lyrics_text, title) VALUES (1, 'u1', '', 'la', 't')")
    conn.execute("INSERT INTO song_variants (id, lyric_id, user_id, style_prompt, status) VALUES (1, 1, 'u1', 'p', 'complete')")
    conn.execute("INSERT INTO song_variant_photos (variant_id, filename) VALUES (1, 'photo.jpg')")
    conn.execute("INSERT INTO playlists (id, user_id, name) VALUES (1, 'u1', 'My Playlist')")
    conn.execute("INSERT INTO playlist_songs (playlist_id, variant_id, position) VALUES (1, 1, 0)")
    conn.commit(); conn.close()

    preview = db.preview_user_deletion(path, "target@example.com")
    assert len(preview["orphans"]["song_variant_photos"]) == 1
    assert len(preview["orphans"]["playlist_songs"]) == 1


# ── actual deletion ──────────────────────────────────────────────────────────

def test_delete_raises_for_an_unknown_email(path):
    with pytest.raises(ValueError):
        db.delete_user_account(path, "nobody@example.com")


def test_delete_refuses_and_makes_no_changes_for_an_admin_account(path):
    _add_user(path, "u1", "admin@example.com", is_admin=1)
    conn = sqlite3.connect(path)
    conn.execute("INSERT INTO lyrics (id, user_id, brief, lyrics_text, title) VALUES (1, 'u1', '', 'la', 't')")
    conn.commit(); conn.close()

    with pytest.raises(db.AdminAccountProtectedError):
        db.delete_user_account(path, "admin@example.com")

    conn = sqlite3.connect(path)
    assert conn.execute("SELECT COUNT(*) FROM users WHERE id='u1'").fetchone()[0] == 1
    assert conn.execute("SELECT COUNT(*) FROM lyrics WHERE user_id='u1'").fetchone()[0] == 1
    conn.close()


def test_delete_removes_every_row_across_all_referencing_tables_in_one_go(path):
    _add_user(path, "u1", "target@example.com")
    conn = sqlite3.connect(path)
    conn.execute("INSERT INTO lyrics (id, user_id, brief, lyrics_text, title) VALUES (1, 'u1', '', 'la', 't')")
    conn.execute("INSERT INTO song_variants (id, lyric_id, user_id, style_prompt, status) VALUES (1, 1, 'u1', 'p', 'complete')")
    conn.execute("INSERT INTO song_credits (user_id, balance, monthly_allowance) VALUES ('u1', 2, 3)")
    conn.execute("INSERT INTO email_verification_tokens (user_id, token, expires_at, used) VALUES ('u1', 'tok', 'later', 1)")
    conn.commit(); conn.close()

    result = db.delete_user_account(path, "target@example.com")
    assert result["email"] == "target@example.com"
    assert result["deleted"]["lyrics"] == 1
    assert result["deleted"]["song_variants"] == 1
    assert result["deleted"]["song_credits"] == 1
    assert result["deleted"]["email_verification_tokens"] == 1
    assert result["deleted"]["users"] == 1

    conn = sqlite3.connect(path)
    for t in ("lyrics", "song_variants", "song_credits", "email_verification_tokens", "users"):
        assert conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0] == 0, f"{t} not fully cleaned up"
    conn.close()


def test_delete_removes_clip_reports_via_the_non_standard_reporter_id_column(path):
    _add_user(path, "u1", "reporter@example.com")
    _add_user(path, "u2", "owner@example.com")
    conn = sqlite3.connect(path)
    conn.execute("INSERT INTO lyrics (id, user_id, brief, lyrics_text, title) VALUES (1, 'u2', '', 'la', 't')")
    conn.execute("INSERT INTO song_variants (id, lyric_id, user_id, style_prompt, status, is_public) VALUES (1, 1, 'u2', 'p', 'complete', 1)")
    conn.execute("INSERT INTO clips (id, user_id, song_id, media_type, clip_start_time, clip_duration, created_at) "
                 "VALUES (1, 'u2', 1, 'cover', 0, 15, 'now')")
    conn.execute("INSERT INTO clip_reports (clip_id, reporter_id, reason, created_at) VALUES (1, 'u1', 'spam', 'now')")
    conn.commit(); conn.close()

    result = db.delete_user_account(path, "reporter@example.com")
    assert result["deleted"]["clip_reports"] == 1
    conn = sqlite3.connect(path)
    assert conn.execute("SELECT COUNT(*) FROM clip_reports").fetchone()[0] == 0
    # the reported-against owner's own clip must be untouched
    assert conn.execute("SELECT COUNT(*) FROM clips WHERE id=1").fetchone()[0] == 1
    conn.close()


def test_delete_cascades_orphaned_song_variant_photos_and_playlist_songs(path):
    _add_user(path, "u1", "target@example.com")
    conn = sqlite3.connect(path)
    conn.execute("INSERT INTO lyrics (id, user_id, brief, lyrics_text, title) VALUES (1, 'u1', '', 'la', 't')")
    conn.execute("INSERT INTO song_variants (id, lyric_id, user_id, style_prompt, status) VALUES (1, 1, 'u1', 'p', 'complete')")
    conn.execute("INSERT INTO song_variant_photos (variant_id, filename) VALUES (1, 'photo.jpg')")
    conn.execute("INSERT INTO playlists (id, user_id, name) VALUES (1, 'u1', 'My Playlist')")
    conn.execute("INSERT INTO playlist_songs (playlist_id, variant_id, position) VALUES (1, 1, 0)")
    conn.commit(); conn.close()

    result = db.delete_user_account(path, "target@example.com")
    assert result["deleted"]["song_variant_photos"] == 1
    assert result["deleted"]["playlist_songs"] == 1
    conn = sqlite3.connect(path)
    assert conn.execute("SELECT COUNT(*) FROM song_variant_photos").fetchone()[0] == 0
    assert conn.execute("SELECT COUNT(*) FROM playlist_songs").fetchone()[0] == 0
    conn.close()


def test_delete_never_touches_another_users_rows(path):
    _add_user(path, "u1", "target@example.com")
    _add_user(path, "u2", "other@example.com")
    conn = sqlite3.connect(path)
    conn.execute("INSERT INTO lyrics (id, user_id, brief, lyrics_text, title) VALUES (1, 'u1', '', 'la', 't1')")
    conn.execute("INSERT INTO lyrics (id, user_id, brief, lyrics_text, title) VALUES (2, 'u2', '', 'la', 't2')")
    conn.execute("INSERT INTO song_credits (user_id, balance, monthly_allowance) VALUES ('u1', 2, 3)")
    conn.execute("INSERT INTO song_credits (user_id, balance, monthly_allowance) VALUES ('u2', 9, 9)")
    conn.commit(); conn.close()

    db.delete_user_account(path, "target@example.com")

    conn = sqlite3.connect(path)
    assert conn.execute("SELECT COUNT(*) FROM users WHERE id='u2'").fetchone()[0] == 1
    assert conn.execute("SELECT COUNT(*) FROM lyrics WHERE user_id='u2'").fetchone()[0] == 1
    assert conn.execute("SELECT balance FROM song_credits WHERE user_id='u2'").fetchone()[0] == 9
    conn.close()


def test_delete_with_no_related_rows_at_all_still_removes_the_bare_user(path):
    _add_user(path, "u1", "lonely@example.com")
    result = db.delete_user_account(path, "lonely@example.com")
    assert result["deleted"]["users"] == 1
    assert result["deleted"].get("lyrics", 0) == 0
