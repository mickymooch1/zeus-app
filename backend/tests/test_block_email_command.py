"""Zeus Clips Phase 3 — "Block user v1" (build brief): a Porick command,
`/block <email>`, writing to the EXISTING abuse_blocklist table (db.py) —
the same table/mechanism a prior abuse case (paulgb189@gmail.com, see db.py's
migration) already uses. Admin-only (Telegram, not a web endpoint), no web UI,
exactly as scoped. Exact-match, bypasses the AI parser, same as every other
precision command in telegram_admin.py (unblock, security scan, ...).

Deliberately does NOT touch an already-registered account's ability to
generate — abuse_blocklist has only ever gated registration (see
db.is_email_blocklisted's three call sites: register, school register,
change-email); this matches that exactly rather than inventing a new
enforcement point the brief didn't ask for.
"""
import importlib
import os
import pathlib
import sys

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


def test_help_documents_the_block_command(T):
    assert "block" in T.HELP_TEXT.lower()


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
