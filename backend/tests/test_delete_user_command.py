"""Porick 'delete_user EMAIL [confirm]' and 'reset_clip_remixes CLIP_ID' — built
2026-09-23 to clean up the Zeus Clips remix QA test's data without ever needing
direct production DB access. Exact-match, bypasses the AI parser (same
"precision/dangerous command" convention as block/unblock/db exec — see
telegram_admin.py's parse_and_run docstring): a misread "delete_user" must
never be left to a language model.

'delete_user EMAIL' alone is a dry run — reports what WOULD be deleted, from
db.py's dynamic user-reference discovery (test_delete_user_account.py), and
changes nothing. Only 'delete_user EMAIL confirm' actually deletes, refuses
outright for an is_admin account, and — unlike block/unblock's success-only
logging — logs every run (including refusals), since an audit trail of
blocked/failed attempts matters for a command this destructive.
"""
import importlib
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
os.environ.setdefault("JWT_SECRET", "test-secret-for-delete-user-command-tests")


@pytest.fixture
def T(tmp_path, monkeypatch):
    monkeypatch.setenv("ZEUS_DATA_DIR", str(tmp_path))
    import db as _db
    importlib.reload(_db)
    import clips as _clips
    importlib.reload(_clips)
    import telegram_admin as _T
    importlib.reload(_T)
    return _T


def no_ai(monkeypatch, T):
    def boom(*a, **k):
        raise AssertionError("delete_user/reset_clip_remixes must not be routed through the AI parser")
    monkeypatch.setattr(T, "_ai_parse", boom)


# ── routing — exact match, bypasses the AI ──────────────────────────────────

@pytest.mark.parametrize("text,expected_email", [
    ("delete_user joe@example.com", "joe@example.com"),
    ("Porick delete_user joe@example.com", "joe@example.com"),
    ("DELETE_USER JOE@EXAMPLE.COM", "JOE@EXAMPLE.COM"),
])
def test_delete_user_dry_run_routing(T, monkeypatch, text, expected_email):
    no_ai(monkeypatch, T)
    calls = []
    monkeypatch.setattr(T, "_cmd_preview_delete_user", lambda *a: calls.append(a) or "OK")
    assert T.parse_and_run(text, chat_id="c1") == "OK"
    assert calls == [(expected_email,)]


@pytest.mark.parametrize("text,expected_email", [
    ("delete_user joe@example.com confirm", "joe@example.com"),
    ("Porick delete_user joe@example.com confirm", "joe@example.com"),
])
def test_delete_user_confirm_routing(T, monkeypatch, text, expected_email):
    no_ai(monkeypatch, T)
    calls = []
    monkeypatch.setattr(T, "_cmd_confirm_delete_user", lambda *a: calls.append(a) or "✅ OK")
    assert T.parse_and_run(text, chat_id="c1") == "✅ OK"
    assert calls == [(expected_email,)]


def test_delete_user_without_confirm_never_calls_the_destructive_handler(T, monkeypatch):
    calls = []
    monkeypatch.setattr(T, "_cmd_preview_delete_user", lambda *a: "dry run reply")
    monkeypatch.setattr(T, "_cmd_confirm_delete_user", lambda *a: calls.append(a) or "SHOULD NOT BE CALLED")
    result = T.parse_and_run("delete_user joe@example.com", chat_id="c1")
    assert calls == []
    assert result == "dry run reply"


def test_reset_clip_remixes_routing(T, monkeypatch):
    no_ai(monkeypatch, T)
    calls = []
    monkeypatch.setattr(T, "_cmd_recount_clip_remixes", lambda *a: calls.append(a) or "✅ done")
    result = T.parse_and_run("reset_clip_remixes 1", chat_id="c1")
    assert calls == [("1",)]
    assert result == "✅ done"


def test_help_documents_both_commands(T):
    assert "delete_user" in T.HELP_TEXT.lower()
    assert "reset_clip_remixes" in T.HELP_TEXT.lower()


# ── _cmd_preview_delete_user ─────────────────────────────────────────────────

def test_preview_reports_no_user_found(T):
    reply = T._cmd_preview_delete_user("nobody@example.com")
    assert "no user" in reply.lower() or "❓" in reply


def test_preview_refuses_an_admin_account_with_a_clear_message(T):
    import db as _db
    db_path = _db.get_db_path()
    _db.create_user(db_path, "admin@example.com", "x", "Admin", "now")
    conn = sqlite3.connect(db_path)
    conn.execute("UPDATE users SET is_admin = 1 WHERE email = 'admin@example.com'")
    conn.commit(); conn.close()

    reply = T._cmd_preview_delete_user("admin@example.com")
    assert reply.startswith("❌")
    assert "admin" in reply.lower()


def test_preview_lists_rows_and_changes_nothing(T):
    import db as _db
    db_path = _db.get_db_path()
    user = _db.create_user(db_path, "target@example.com", "x", "Target", "now")
    conn = sqlite3.connect(db_path)
    conn.execute("INSERT INTO song_credits (user_id, balance, monthly_allowance) VALUES (?, 2, 3)", (user["id"],))
    conn.commit(); conn.close()

    reply = T._cmd_preview_delete_user("target@example.com")
    assert "DRY RUN" in reply
    assert "song_credits" in reply
    assert "confirm" in reply.lower()

    conn = sqlite3.connect(db_path)
    assert conn.execute("SELECT COUNT(*) FROM users").fetchone()[0] == 1
    conn.close()


def test_dry_run_is_logged(T, monkeypatch):
    logged = []
    monkeypatch.setattr(T, "_db_log_action", lambda chat_id, action, detail: logged.append((chat_id, action, detail)))
    T.parse_and_run("delete_user nobody@example.com", chat_id="c1")
    assert logged and logged[0][1] == "delete_user_preview"


# ── _cmd_confirm_delete_user ─────────────────────────────────────────────────

def test_confirm_reports_no_user_found_and_changes_nothing(T):
    reply = T._cmd_confirm_delete_user("nobody@example.com")
    assert "❓" in reply or "no user" in reply.lower()


def test_confirm_refuses_an_admin_account(T):
    import db as _db
    db_path = _db.get_db_path()
    _db.create_user(db_path, "admin@example.com", "x", "Admin", "now")
    conn = sqlite3.connect(db_path)
    conn.execute("UPDATE users SET is_admin = 1 WHERE email = 'admin@example.com'")
    conn.commit(); conn.close()

    reply = T._cmd_confirm_delete_user("admin@example.com")
    assert reply.startswith("❌")
    conn = sqlite3.connect(db_path)
    assert conn.execute("SELECT COUNT(*) FROM users WHERE email='admin@example.com'").fetchone()[0] == 1
    conn.close()


def test_confirm_actually_deletes_and_reports_what_was_removed(T):
    import db as _db
    db_path = _db.get_db_path()
    user = _db.create_user(db_path, "target@example.com", "x", "Target", "now")
    conn = sqlite3.connect(db_path)
    conn.execute("INSERT INTO song_credits (user_id, balance, monthly_allowance) VALUES (?, 2, 3)", (user["id"],))
    conn.commit(); conn.close()

    reply = T._cmd_confirm_delete_user("target@example.com")
    assert reply.startswith("✅")
    assert "song_credits" in reply

    conn = sqlite3.connect(db_path)
    assert conn.execute("SELECT COUNT(*) FROM users").fetchone()[0] == 0
    assert conn.execute("SELECT COUNT(*) FROM song_credits").fetchone()[0] == 0
    conn.close()


def test_every_confirm_run_is_logged_including_refusals(T, monkeypatch):
    """Unlike block/unblock (success-only log), delete_user confirm logs
    EVERY attempt — a refused/failed delete is exactly the kind of thing an
    audit trail needs to show, not just successes."""
    import db as _db
    db_path = _db.get_db_path()
    _db.create_user(db_path, "admin@example.com", "x", "Admin", "now")
    conn = sqlite3.connect(db_path)
    conn.execute("UPDATE users SET is_admin = 1 WHERE email = 'admin@example.com'")
    conn.commit(); conn.close()

    logged = []
    monkeypatch.setattr(T, "_db_log_action", lambda chat_id, action, detail: logged.append((chat_id, action, detail)))
    T.parse_and_run("delete_user admin@example.com confirm", chat_id="c1")
    assert logged and logged[0][1] == "delete_user"
    assert "refus" in logged[0][2].lower() or "fail" in logged[0][2].lower()


def test_a_successful_confirm_is_also_logged(T, monkeypatch):
    import db as _db
    db_path = _db.get_db_path()
    _db.create_user(db_path, "target@example.com", "x", "Target", "now")

    logged = []
    monkeypatch.setattr(T, "_db_log_action", lambda chat_id, action, detail: logged.append((chat_id, action, detail)))
    T.parse_and_run("delete_user target@example.com confirm", chat_id="c1")
    assert logged and logged[0][1] == "delete_user"
    assert "succeed" in logged[0][2].lower()


# ── _cmd_recount_clip_remixes ────────────────────────────────────────────────

def test_recount_reports_old_and_new_count(T):
    import db as _db
    import clips as _clips_mod
    db_path = _db.get_db_path()
    owner = _db.create_user(db_path, "owner@example.com", "x", "Owner", "now")
    conn = sqlite3.connect(db_path)
    conn.execute("INSERT INTO lyrics (id, user_id, brief, lyrics_text, title) VALUES (1, ?, '', 'la', 't')", (owner["id"],))
    conn.execute("INSERT INTO song_variants (id, lyric_id, user_id, style_prompt, status, mp3_url, is_public, created_at) "
                 "VALUES (1, 1, ?, 'p', 'complete', '/x.mp3', 1, 'now')", (owner["id"],))
    conn.execute("INSERT INTO clips (id, user_id, song_id, media_type, clip_start_time, clip_duration, "
                 "remix_count, created_at) VALUES (1, ?, 1, 'cover', 0, 15, 9, 'now')", (owner["id"],))
    conn.commit(); conn.close()

    reply = T._cmd_recount_clip_remixes("1")
    assert reply.startswith("✅")
    assert "9" in reply and "0" in reply
    assert _clips_mod.get_clip(db_path, 1)["remix_count"] == 0


def test_recount_rejects_a_non_numeric_clip_id(T):
    reply = T._cmd_recount_clip_remixes("not-a-number")
    assert reply.startswith("❌")


def test_recount_reports_unknown_clip(T):
    reply = T._cmd_recount_clip_remixes("99999")
    assert "❓" in reply
