"""Porick's conversation history must reflect what a tool call actually
returned, not just that the model decided to call it.

Root cause of the 2026-09-13 incident: _ai_parse() saves the model's raw
JSON decision (e.g. "call check_transaction") to admin_conversation_history
BEFORE that action is executed. When the action then crashed (an unhandled
500, no Telegram reply at all), history was left showing "I decided to call
this tool" with no result ever recorded -- so the next turn, seeing that
same decision recorded with nothing after it, the model narrated a
plausible-sounding but false "I've run this multiple times, what are you
seeing?" instead of just saying the call had failed.

parse_and_run() now appends a "[TOOL RESULT: ...]" note onto that same
saved assistant turn whenever the action's result starts with "❌" (this
codebase's established failure-message prefix), so a subsequent model call
can see the real outcome and report it honestly.
"""
import os
import pathlib
import sys
from types import SimpleNamespace
from unittest.mock import patch

import pytest

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))
os.environ.setdefault("ANTHROPIC_API_KEY", "test-key")
os.environ.setdefault("APIFRAME_API_KEY", "test-key")
os.environ.setdefault("SONG_STORAGE_PATH", "/tmp/test_songs")
os.environ.setdefault("SONG_PUBLIC_BASE_URL", "https://example.com/files/songs")
os.environ.setdefault("SONG_WEBHOOK_URL", "https://zeusaidesign.com/webhooks/apiframe")
os.environ.setdefault("JWT_SECRET", "test-secret-for-tool-failure-history-tests")

import db
import telegram_admin as ta


@pytest.fixture
def temp_db(tmp_path, monkeypatch):
    path = tmp_path / "test.db"
    db.init_user_tables(path)
    monkeypatch.setattr(db, "get_db_path", lambda: path)
    ta._ensure_admin_tables()
    return path


def _history_rows(chat_id):
    import sqlite3
    conn = sqlite3.connect(str(db.get_db_path()))
    try:
        return conn.execute(
            "SELECT role, content FROM admin_conversation_history WHERE chat_id = ? ORDER BY id", (chat_id,)
        ).fetchall()
    finally:
        conn.close()


class _FakeAnthropic:
    def __init__(self, response_text):
        self._response_text = response_text
        self.messages = self

    def create(self, **kwargs):
        return SimpleNamespace(content=[SimpleNamespace(text=self._response_text)], stop_reason="end_turn")


def _mock_model_response(monkeypatch, response_text):
    monkeypatch.setattr("anthropic.Anthropic", lambda **kw: _FakeAnthropic(response_text))


# ── _db_record_tool_failure: the underlying helper ──────────────────────────

def test_record_tool_failure_appends_to_the_most_recent_assistant_turn(temp_db):
    ta._db_save_exchange("chat1", "check payg purchases", '{"action": "check_transaction", "since": "24h"}')

    ta._db_record_tool_failure("chat1", "❌ check_transaction failed: boom")

    rows = _history_rows("chat1")
    assert rows[-1][0] == "assistant"
    assert '{"action": "check_transaction"' in rows[-1][1]
    assert "[TOOL RESULT: ❌ check_transaction failed: boom]" in rows[-1][1]


def test_record_tool_failure_does_nothing_if_no_history_exists_yet(temp_db):
    ta._db_record_tool_failure("brand-new-chat", "❌ some failure")  # must not raise
    assert _history_rows("brand-new-chat") == []


def test_record_tool_failure_never_raises(monkeypatch):
    monkeypatch.setattr(db, "get_db_path", lambda: pathlib.Path("Z:/does/not/exist/nope.db"))
    ta._db_record_tool_failure("chat1", "❌ boom")  # must not raise


# ── parse_and_run: end-to-end wiring ─────────────────────────────────────────

def test_a_failed_tool_call_is_recorded_in_history_for_the_next_turn(temp_db, monkeypatch):
    _mock_model_response(monkeypatch, '{"type": "action", "action": "check_transaction", "since": "24h", "category": "payg"}')
    monkeypatch.setattr(ta, "_check_transaction_impl",
                         lambda *a, **kw: (_ for _ in ()).throw(RuntimeError("simulated crash")))

    reply = ta.parse_and_run("check payg purchases in the last 24 hours", chat_id="chat42")

    assert reply.startswith("❌")
    assert "simulated crash" in reply

    rows = _history_rows("chat42")
    assert rows[0] == ("user", "check payg purchases in the last 24 hours")
    assistant_content = rows[1][1]
    assert "check_transaction" in assistant_content
    assert "[TOOL RESULT:" in assistant_content
    assert "simulated crash" in assistant_content


def test_a_successful_tool_call_is_not_flagged_as_a_failure_in_history(temp_db, monkeypatch):
    _mock_model_response(monkeypatch, '{"type": "action", "action": "check_incidents", "status": "open"}')

    reply = ta.parse_and_run("is anything broken", chat_id="chat43")

    assert not reply.startswith("❌")
    rows = _history_rows("chat43")
    assistant_content = rows[1][1]
    assert "[TOOL RESULT:" not in assistant_content


def test_repeated_identical_messages_after_a_failure_show_the_model_the_real_outcome(temp_db, monkeypatch):
    """Regression test for the exact 2026-09-13 scenario: the same admin
    message arrives more than once (Telegram's own webhook retry after a
    500), and the SECOND call's conversation history must show the first
    call's tool actually failed -- not just that it was "decided"."""
    _mock_model_response(monkeypatch, '{"type": "action", "action": "check_transaction", "since": "24h", "category": "payg"}')
    monkeypatch.setattr(ta, "_check_transaction_impl",
                         lambda *a, **kw: (_ for _ in ()).throw(RuntimeError("boom")))

    ta.parse_and_run("check payg purchases in the last 24 hours", chat_id="chat44")

    # Second, "retried" delivery of the identical message -- inspect what
    # history _ai_parse would now load for this chat.
    history = ta._db_load_history("chat44")
    assert len(history) == 2
    assert history[0]["role"] == "user"
    assert history[1]["role"] == "assistant"
    assert "[TOOL RESULT:" in history[1]["content"]
    assert "boom" in history[1]["content"]
