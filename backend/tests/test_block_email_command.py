"""Zeus Clips Phase 3 — "Block user v1" (build brief) + the 2026-09-23
hardening follow-up: a Porick command, `block EMAIL`, writing to the EXISTING
abuse_blocklist table (db.py) — the same table/mechanism a prior abuse case
(paulgb189@gmail.com, see db.py's migration) already uses. Admin-only
(Telegram, not a web endpoint), no web UI, exactly as scoped. Exact-match,
bypasses the AI parser, same as every other precision command in
telegram_admin.py (unblock ip, security scan, ...).

The follow-up closed the original v1's real gap: abuse_blocklist only ever
gated REGISTRATION, so a blocked email's EXISTING account could keep
publishing/uploading/liking/reporting/remixing freely. block EMAIL now also
auto-hides every clip that account currently has published
(clips.hide_clips_for_blocked_user — see test_blocked_user_clip_access.py for
the endpoint-level enforcement), and `unblock EMAIL` reverses both: removes
the blocklist row and restores exactly the clips THAT hid for (not one an
admin separately moderated — see hidden_reason in test_clips_db.py).
"""
import importlib
import os
import pathlib
import sqlite3
import sys
from datetime import datetime, timezone

import pytest

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))
os.environ.setdefault("ANTHROPIC_API_KEY", "test-key")
os.environ.setdefault("APIFRAME_API_KEY", "test-key")
os.environ.setdefault("SONG_STORAGE_PATH", "/tmp/test_songs")
os.environ.setdefault("SONG_PUBLIC_BASE_URL", "https://example.com/files/songs")
os.environ.setdefault("SONG_WEBHOOK_URL", "https://zeusaidesign.com/webhooks/apiframe")
os.environ.setdefault("JWT_SECRET", "test-secret-for-block-email-tests")


@pytest.fixture
def T(tmp_path, monkeypatch):
    monkeypatch.setenv("ZEUS_DATA_DIR", str(tmp_path))
    import db as _db
    importlib.reload(_db)
    import telegram_admin as _T
    importlib.reload(_T)
    return _T


def no_ai(monkeypatch, T):
    def boom(*a, **k):
        raise AssertionError("block must not be routed through the AI parser")
    monkeypatch.setattr(T, "_ai_parse", boom)


# ── routing — exact match, bypasses the AI, same convention as `unblock` ─────

@pytest.mark.parametrize("text,expected_email", [
    ("block joe@example.com", "joe@example.com"),
    ("Porick block joe@example.com", "joe@example.com"),
    ("BLOCK JOE@EXAMPLE.COM", "JOE@EXAMPLE.COM"),
])
def test_block_is_exact_match_and_bypasses_the_ai(T, monkeypatch, text, expected_email):
    no_ai(monkeypatch, T)
    calls = []
    monkeypatch.setattr(T, "_cmd_block_email", lambda *a: calls.append(a) or "OK")
    assert T.parse_and_run(text, chat_id="c1") == "OK"
    assert calls == [(expected_email,)]


def test_unblock_ip_is_not_mistaken_for_block_email(T, monkeypatch):
    """'unblock' must never route to the email-block handler — anchored
    matching (^block, not a bare substring) is what keeps these apart."""
    calls = []
    monkeypatch.setattr(T, "_cmd_block_email", lambda *a: calls.append(a) or "SHOULD NOT BE CALLED")
    monkeypatch.setattr(T, "_cmd_unblock_ip", lambda *a: "unblocked")
    result = T.parse_and_run("unblock 1.2.3.4", chat_id="c1")
    assert calls == []
    assert result == "unblocked"


@pytest.mark.parametrize("text,expected_email", [
    ("unblock joe@example.com", "joe@example.com"),
    ("Porick unblock joe@example.com", "joe@example.com"),
])
def test_unblock_email_is_exact_match_and_bypasses_the_ai(T, monkeypatch, text, expected_email):
    no_ai(monkeypatch, T)
    calls = []
    monkeypatch.setattr(T, "_cmd_unblock_email", lambda *a: calls.append(a) or "OK")
    assert T.parse_and_run(text, chat_id="c1") == "OK"
    assert calls == [(expected_email,)]


def test_unblock_email_is_not_mistaken_for_unblock_ip(T, monkeypatch):
    """The inverse of test_unblock_ip_is_not_mistaken_for_block_email — an
    email must not fall through to the generic (\\S+) IP-unblock regex, which
    would otherwise happily 'match' it and fail with a bogus IP error."""
    calls = []
    monkeypatch.setattr(T, "_cmd_unblock_ip", lambda *a: calls.append(a) or "SHOULD NOT BE CALLED")
    monkeypatch.setattr(T, "_cmd_unblock_email", lambda *a: "unblocked email")
    result = T.parse_and_run("unblock joe@example.com", chat_id="c1")
    assert calls == []
    assert result == "unblocked email"


def test_unblock_a_real_ip_still_works_after_adding_email_unblock(T, monkeypatch):
    """Regression: adding email-unblock routing must not break plain IP unblock."""
    calls = []
    monkeypatch.setattr(T, "_cmd_unblock_ip", lambda *a: calls.append(a) or "unblocked ip")
    result = T.parse_and_run("unblock 45.13.7.2", chat_id="c1")
    assert calls == [("45.13.7.2",)]
    assert result == "unblocked ip"


def test_help_documents_the_block_command(T):
    assert "block" in T.HELP_TEXT.lower()
    assert "unblock email" in T.HELP_TEXT.lower()


# ── _cmd_block_email ──────────────────────────────────────────────────────────

def test_blocking_an_email_adds_it_to_the_existing_blocklist_table(T):
    import db as _db
    reply = T._cmd_block_email("abuser@example.com")
    assert reply.startswith("✅")
    assert _db.is_email_blocklisted(_db.get_db_path(), "abuser@example.com") is not None


def test_blocking_normalises_the_email_gmail_plus_alias(T):
    """abuser+spam@gmail.com and abuser@gmail.com must block the same person —
    same canonicalisation db.is_email_blocklisted's own callers already rely on."""
    import db as _db
    T._cmd_block_email("abuser+spam@gmail.com")
    assert _db.is_email_blocklisted(_db.get_db_path(), "abuser@gmail.com") is not None


def test_blocking_an_already_blocked_email_says_so_without_erroring(T):
    T._cmd_block_email("abuser@example.com")
    reply = T._cmd_block_email("abuser@example.com")
    assert reply.startswith("ℹ️")


def test_a_freshly_blocked_email_cannot_register(T):
    """End-to-end: the command actually prevents what it claims to prevent."""
    import importlib
    import main as _main
    importlib.reload(_main)
    from fastapi.testclient import TestClient

    T._cmd_block_email("abuser@example.com")
    with TestClient(_main.app) as client:
        r = client.post("/auth/register", json={
            "email": "abuser@example.com", "password": "correcthorsebattery",
            "tc_accepted": True, "app": "beats",
        })
    assert r.status_code == 403


def test_blocking_logs_the_admin_action(T, monkeypatch):
    logged = []
    monkeypatch.setattr(T, "_db_log_action", lambda chat_id, action, detail: logged.append((chat_id, action, detail)))
    T.parse_and_run("block abuser@example.com", chat_id="c1")
    assert logged and logged[0][1] == "block_email"


def test_blocking_an_email_with_no_registered_account_does_not_crash(T):
    """The common case: reported abuse from an address that never signed up
    (or hasn't yet) — nothing to auto-hide, must not error."""
    reply = T._cmd_block_email("never-signed-up@example.com")
    assert reply.startswith("✅")


# ── auto-hide on block / restore on unblock ─────────────────────────────────

NOW = datetime(2026, 9, 23, 12, 0, 0, tzinfo=timezone.utc)


def _seed_user_with_a_published_clip(db_path, email="abuser@example.com"):
    import db as _db
    user = _db.create_user(db_path, email, "x", "Abuser", "now")
    conn = sqlite3.connect(db_path)
    conn.execute("INSERT INTO lyrics (id, user_id, brief, lyrics_text, title) VALUES "
                 "(1, ?, 'b', 'la la', 'T')", (user["id"],))
    conn.execute("INSERT INTO song_variants (id, lyric_id, user_id, style_prompt, genre_tag, status, "
                 "mp3_url, is_public, created_at) VALUES "
                 "(1, 1, ?, 'pop', 'pop', 'complete', '/files/songs/1.mp3', 1, ?)",
                 (user["id"], NOW.isoformat()))
    conn.commit()
    conn.close()
    import clips as _clips_mod
    clip_id = _clips_mod.create_clip(db_path, user["id"], 1, "", "cover", None, 0, 15)
    return user, clip_id


def test_blocking_hides_the_users_existing_clips(T):
    import db as _db
    import clips as _clips_mod
    db_path = _db.get_db_path()
    user, clip_id = _seed_user_with_a_published_clip(db_path)

    reply = T._cmd_block_email(user["email"])

    assert "1 existing clip" in reply
    assert _clips_mod.get_clip(db_path, clip_id) is None  # hidden — excluded from the default query


def test_unblocking_restores_the_clips_it_hid(T):
    import db as _db
    import clips as _clips_mod
    db_path = _db.get_db_path()
    user, clip_id = _seed_user_with_a_published_clip(db_path)
    T._cmd_block_email(user["email"])

    reply = T._cmd_unblock_email(user["email"])

    assert "1 clip" in reply
    assert _clips_mod.get_clip(db_path, clip_id) is not None
    assert _db.is_email_blocklisted(db_path, user["email"]) is None


def test_unblocking_leaves_an_admin_moderated_clip_hidden(T):
    """The scenario hidden_reason exists for: block auto-hides, an admin
    separately confirms the clip is genuinely bad and re-hides it with their
    own reason — unblocking must not silently bring it back."""
    import db as _db
    import clips as _clips_mod
    db_path = _db.get_db_path()
    user, clip_id = _seed_user_with_a_published_clip(db_path)
    T._cmd_block_email(user["email"])
    _clips_mod.set_clip_status(db_path, clip_id, "hidden", reason="admin_moderation")

    T._cmd_unblock_email(user["email"])

    assert _clips_mod.get_clip(db_path, clip_id) is None  # still hidden


def test_unblocking_an_email_that_was_never_blocked_says_so(T):
    reply = T._cmd_unblock_email("never-blocked@example.com")
    assert reply.startswith("ℹ️")


def test_unblocking_logs_the_admin_action(T, monkeypatch):
    T._cmd_block_email("abuser@example.com")
    logged = []
    monkeypatch.setattr(T, "_db_log_action", lambda chat_id, action, detail: logged.append((chat_id, action, detail)))
    T.parse_and_run("unblock abuser@example.com", chat_id="c1")
    assert logged and logged[0][1] == "unblock_email"
