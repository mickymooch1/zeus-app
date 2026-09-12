"""Porick's chat-mode tools: check_deploy_status and check_incidents, wired
into the existing AI action-routing layer in telegram_admin.py the same way
"logs" already is (see ADMIN_SYSTEM_PROMPT / _execute_action), plus the new
system-prompt rule that stops Porick stating unverified deploy/incident
claims as fact.

The underlying Claude Haiku call in _ai_parse is inherently non-deterministic,
so these tests pin two different things:
1. THE WIRING -- given a model response that chooses a tool, parse_and_run
   dispatches to the real Python function and relays its real answer, not
   free text from the model. _FakeAnthropic stands in for the real model so
   this is deterministic and makes no network call.
2. THE SYSTEM PROMPT CONTENT that is supposed to produce that model
   behaviour -- a plain regression guard so the instruction can't be quietly
   deleted or weakened later.
"""
import os
import pathlib
import sys
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))
os.environ.setdefault("ANTHROPIC_API_KEY", "test-key")
os.environ.setdefault("APIFRAME_API_KEY", "test-key")
os.environ.setdefault("SONG_STORAGE_PATH", "/tmp/test_songs")
os.environ.setdefault("SONG_PUBLIC_BASE_URL", "https://example.com/files/songs")
os.environ.setdefault("SONG_WEBHOOK_URL", "https://zeusaidesign.com/webhooks/apiframe")
os.environ.setdefault("JWT_SECRET", "test-secret-for-porick-chat-tools")
os.environ.setdefault("GITHUB_TOKEN", "test-github-token")

import db
import incidents
import telegram_admin as ta


@pytest.fixture
def temp_db(tmp_path, monkeypatch):
    path = tmp_path / "test.db"
    monkeypatch.setattr(db, "get_db_path", lambda: path)
    return path


@pytest.fixture(autouse=True)
def no_diagnosis(monkeypatch):
    monkeypatch.setattr(incidents, "_spawn_diagnosis", lambda incident: None)
    incidents._diagnosed_incident_ids.clear()
    yield
    incidents._diagnosed_incident_ids.clear()


class _FakeAnthropic:
    """Canned stand-in for anthropic.Anthropic(...): returns a fixed
    response text regardless of what was sent, so _ai_parse's JSON-parsing
    and dispatch wiring can be tested deterministically, without a real
    (non-deterministic, networked) model call."""
    def __init__(self, response_text):
        self._response_text = response_text
        self.messages = self

    def create(self, **kwargs):
        return SimpleNamespace(content=[SimpleNamespace(text=self._response_text)], stop_reason="end_turn")


def _mock_model_response(monkeypatch, response_text):
    monkeypatch.setattr("anthropic.Anthropic", lambda **kw: _FakeAnthropic(response_text))


# ── Tool wiring: check_deploy_status ────────────────────────────────────────

def test_deploy_status_question_triggers_the_tool_not_a_guess(temp_db, monkeypatch):
    """When the model correctly chooses check_deploy_status for a deploy
    question, parse_and_run must call the REAL git/GitHub lookup and relay
    its actual answer -- not free text invented by the model."""
    _mock_model_response(monkeypatch, '{"type": "action", "action": "check_deploy_status"}')
    monkeypatch.setattr(incidents, "get_latest_master_commit", lambda: {"sha": "abc1234", "message": "fix: something real"})

    reply = ta.parse_and_run("is the update live", chat_id="")

    assert "abc1234" in reply
    assert "fix: something real" in reply


def test_deploy_status_tool_is_honest_when_github_is_unreachable(temp_db, monkeypatch):
    _mock_model_response(monkeypatch, '{"type": "action", "action": "check_deploy_status"}')
    monkeypatch.setattr(incidents, "get_latest_master_commit", lambda: None)

    reply = ta.parse_and_run("did the fix ship yet", chat_id="")

    assert "❓" in reply
    assert "couldn't check github" in reply.lower()


# ── Tool wiring: check_incidents ────────────────────────────────────────────

def test_broken_question_triggers_check_incidents(temp_db, monkeypatch):
    _mock_model_response(monkeypatch, '{"type": "action", "action": "check_incidents", "status": "open"}')
    incidents.record("provider_timeout", "provider=openai: timed out", severity="critical")

    reply = ta.parse_and_run("is anything broken right now", chat_id="")

    assert "provider_timeout" in reply


def test_no_open_incidents_reports_healthy_not_silence(temp_db, monkeypatch):
    _mock_model_response(monkeypatch, '{"type": "action", "action": "check_incidents", "status": "open"}')
    reply = ta.parse_and_run("anything broken?", chat_id="")
    assert "no open incidents" in reply.lower()


def test_check_incidents_resolved_status_lists_recently_fixed_across_categories(temp_db, monkeypatch):
    row = incidents.record("provider_timeout", "provider=openai: timed out", severity="critical")
    conn = incidents._connect()
    try:
        conn.execute("UPDATE incidents SET status='resolved', resolved_at=datetime('now') WHERE id=?", (row["id"],))
        conn.commit()
    finally:
        conn.close()

    _mock_model_response(monkeypatch, '{"type": "action", "action": "check_incidents", "status": "resolved"}')
    reply = ta.parse_and_run("what's been fixed lately", chat_id="")
    assert "Recently resolved" in reply
    assert "provider_timeout" in reply


# ── No matching tool → honest "I don't know" ────────────────────────────────

def test_question_with_no_matching_tool_gets_i_dont_know_not_an_invented_answer(temp_db, monkeypatch):
    _mock_model_response(monkeypatch, "{\"type\": \"message\", \"text\": \"I don't know, mate \\u2014 want me to check the logs?\"}")
    reply = ta.parse_and_run("is my nan's broadband working", chat_id="")
    assert "don't know" in reply.lower()
    assert "logs" in reply.lower()


# ── Existing banter/chat behaviour is unchanged ─────────────────────────────

def test_banter_message_still_relays_unchanged(temp_db, monkeypatch):
    _mock_model_response(monkeypatch, "{\"type\": \"message\", \"text\": \"Ha, you're a mess mate \\ud83d\\ude02\"}")
    reply = ta.parse_and_run("you're useless today", chat_id="")
    assert reply == "Ha, you're a mess mate 😂"


def test_existing_action_dispatch_still_works_alongside_the_new_tools(temp_db, monkeypatch):
    """Confirms adding check_deploy_status/check_incidents to the
    if/elif dispatcher didn't disturb an unrelated existing action."""
    _mock_model_response(monkeypatch, '{"type": "action", "action": "recent_users"}')
    with patch.object(ta, "_cmd_recent_users", return_value="👤 no one yet") as mock_cmd:
        reply = ta.parse_and_run("who signed up recently", chat_id="")
    mock_cmd.assert_called_once()
    assert reply == "👤 no one yet"


# ── System prompt content (regression guard on the model's instructions) ───

def test_system_prompt_lists_the_new_tools_and_when_to_use_them():
    prompt = ta.ADMIN_SYSTEM_PROMPT
    assert "check_deploy_status" in prompt
    assert "check_incidents" in prompt
    assert "is the update live" in prompt


def test_system_prompt_forbids_stating_deploy_or_incident_claims_without_a_tool_call():
    prompt = ta.ADMIN_SYSTEM_PROMPT
    assert "check_deploy_status or check_incidents" in prompt
    assert "I don't know" in prompt
    assert "never" in prompt.lower() and "guess" in prompt.lower()


def test_system_prompt_still_preserves_banter_personality_instructions():
    """The new factual-claims rule must be additive, not a replacement of
    the existing tone instructions."""
    prompt = ta.ADMIN_SYSTEM_PROMPT
    assert "banter" in prompt.lower()
    assert "cheeky" in prompt.lower()
    assert "speculating" in prompt.lower() or "speculation" in prompt.lower()


# ── Direct command-function tests (no model involved) ──────────────────────

def test_cmd_check_deploy_status_reports_the_real_commit(monkeypatch):
    monkeypatch.setattr(incidents, "get_latest_master_commit", lambda: {"sha": "def5678", "message": "feat: thing"})
    result = ta._cmd_check_deploy_status()
    assert "def5678" in result
    assert "feat: thing" in result


def test_cmd_check_deploy_status_is_honest_when_it_cannot_check(monkeypatch):
    monkeypatch.setattr(incidents, "get_latest_master_commit", lambda: None)
    result = ta._cmd_check_deploy_status()
    assert "❓" in result


def test_cmd_check_incidents_open_reuses_existing_cmd_incidents(temp_db):
    with patch.object(ta, "_cmd_incidents", return_value="reused output") as mock_cmd:
        result = ta._cmd_check_incidents("open")
    mock_cmd.assert_called_once()
    assert result == "reused output"


def test_cmd_check_incidents_defaults_to_open_for_an_unrecognised_status(temp_db):
    with patch.object(ta, "_cmd_incidents", return_value="reused output") as mock_cmd:
        result = ta._cmd_check_incidents("banana")
    mock_cmd.assert_called_once()
    assert result == "reused output"


def test_cmd_check_incidents_resolved_lists_across_all_categories(temp_db):
    row1 = incidents.record("provider_timeout", "s1", severity="critical")
    row2 = incidents.record("stuck_song_sweep", "s2", severity="warning")
    conn = incidents._connect()
    try:
        conn.execute("UPDATE incidents SET status='resolved', resolved_at=datetime('now') WHERE id IN (?, ?)",
                     (row1["id"], row2["id"]))
        conn.commit()
    finally:
        conn.close()
    result = ta._cmd_check_incidents("resolved")
    assert "provider_timeout" in result
    assert "stuck_song_sweep" in result


def test_cmd_check_incidents_resolved_with_nothing_resolved(temp_db):
    result = ta._cmd_check_incidents("resolved")
    assert "nothing resolved" in result.lower()


# ── incidents.get_latest_master_commit: reuses the diagnosis feature's own
#    GitHub API access pattern ───────────────────────────────────────────────

def test_get_latest_master_commit_uses_the_same_github_api_pattern_as_diagnosis():
    resp = MagicMock(status_code=200)
    resp.json.return_value = {"sha": "1234567890abcdef", "commit": {"message": "feat: real change\n\nlonger body"}}
    resp.raise_for_status = lambda: None

    with patch("incidents.requests.get", return_value=resp) as mock_get:
        result = incidents.get_latest_master_commit()

    assert result == {"sha": "1234567", "message": "feat: real change"}
    call_url = mock_get.call_args.args[0] if mock_get.call_args.args else mock_get.call_args.kwargs.get("url")
    assert "mickymooch1/zeus-app" in call_url
    assert "master" in call_url
    assert "diff" not in call_url.lower()


def test_get_latest_master_commit_handles_a_commit_with_no_message():
    resp = MagicMock(status_code=200)
    resp.json.return_value = {"sha": "abc1234567", "commit": {}}
    resp.raise_for_status = lambda: None
    with patch("incidents.requests.get", return_value=resp):
        result = incidents.get_latest_master_commit()
    assert result == {"sha": "abc1234", "message": "(no commit message)"}


def test_get_latest_master_commit_returns_none_without_a_token():
    with patch.dict(os.environ, {"GITHUB_TOKEN": ""}):
        assert incidents.get_latest_master_commit() is None


def test_get_latest_master_commit_returns_none_on_network_failure():
    with patch("incidents.requests.get", side_effect=RuntimeError("network down")):
        assert incidents.get_latest_master_commit() is None
