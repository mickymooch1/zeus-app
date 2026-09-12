"""Automatic diagnosis for Porickbot's incident tracking (incidents.py).

Covers: triggering (first critical occurrence only, never a re-diagnosis),
evidence gathering (log buffer filtered by service, git commits via the
GitHub API since .git isn't present in the deployed container), the model
call and its response contract (cause classification, confidence, and the
"insufficient evidence" / low-confidence safety net when evidence doesn't
clearly point to a cause), writing only evidence/likely_cause/confidence,
the Telegram follow-up phrasing, non-blocking dispatch, and fail-silent
behaviour on any failure.

No test here makes a real network call: the Anthropic client and `requests`
are always mocked. The "ambiguous evidence" test simulates a well-behaved
model response (cause_category="unknown", confidence="low") to prove the
SYSTEM correctly relays and stores that as "insufficient evidence" rather
than substituting a fabricated cause -- it is not a test of the real model's
judgment, which cannot be exercised without a live API call.
"""
import json
import os
import pathlib
import sys
import threading
import time
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))
os.environ.setdefault("ANTHROPIC_API_KEY", "test-key")
os.environ.setdefault("APIFRAME_API_KEY", "test-key")
os.environ.setdefault("SONG_STORAGE_PATH", "/tmp/test_songs")
os.environ.setdefault("SONG_PUBLIC_BASE_URL", "https://example.com/files/songs")
os.environ.setdefault("SONG_WEBHOOK_URL", "https://zeusaidesign.com/webhooks/apiframe")
os.environ.setdefault("JWT_SECRET", "test-secret-for-incident-diagnosis-tests")
os.environ.setdefault("GITHUB_TOKEN", "test-github-token")

import db
import incidents


@pytest.fixture
def temp_db(tmp_path, monkeypatch):
    path = tmp_path / "test.db"
    monkeypatch.setattr(db, "get_db_path", lambda: path)
    return path


@pytest.fixture(autouse=True)
def clean_diagnosis_state():
    incidents._diagnosed_incident_ids.clear()
    yield
    incidents._diagnosed_incident_ids.clear()


def _mock_model_response(cause, confidence, reasoning=""):
    payload = json.dumps({"cause_category": cause, "confidence": confidence, "reasoning": reasoning})
    resp = MagicMock()
    resp.content = [MagicMock(text=payload)]
    return resp


# ── Triggering: only the first critical occurrence ──────────────────────────

def test_new_critical_incident_triggers_diagnosis(temp_db):
    with patch.object(incidents, "_spawn_diagnosis") as spawn:
        incidents.record("payment_failed", "x")
    spawn.assert_called_once()
    assert spawn.call_args.args[0]["category"] == "payment_failed"


def test_new_non_critical_incident_does_not_trigger(temp_db):
    with patch.object(incidents, "_spawn_diagnosis") as spawn:
        incidents.record("fade_out_failed", "x")
    spawn.assert_not_called()


def test_repeat_critical_occurrence_does_not_retrigger(temp_db):
    """Spec: occurrence_count increasing must not cause a second diagnosis."""
    with patch.object(incidents, "_spawn_diagnosis") as spawn:
        incidents.record("payment_failed", "first")
        incidents.record("payment_failed", "second")
        incidents.record("payment_failed", "third")
    assert spawn.call_count == 1


def test_escalation_from_warning_to_critical_triggers(temp_db):
    """A category whose severity is computed per-occurrence (e.g. a checker
    or alert_service_error) can start non-critical and later escalate on the
    SAME open incident -- that transition must still trigger diagnosis."""
    with patch.object(incidents, "_spawn_diagnosis") as spawn:
        incidents.record("service_error:apiframe:429", "rate limited", severity="warning")
        spawn.assert_not_called()
        incidents.record("service_error:apiframe:429", "now failing hard", severity="critical")
    spawn.assert_called_once()


def test_severity_never_downgrades_on_an_open_incident(temp_db):
    row1 = incidents.record("service_error:apiframe:429", "x", severity="critical")
    assert row1["severity"] == "critical"
    with patch.object(incidents, "_spawn_diagnosis"):
        row2 = incidents.record("service_error:apiframe:429", "y", severity="warning")
    assert row2["severity"] == "critical"


def test_an_incident_that_already_has_a_likely_cause_never_retriggers(temp_db):
    """Even a brand-new critical occurrence of a category that somehow
    already carries a likely_cause (e.g. it was diagnosed, then recurred
    before auto-resolving) must not diagnose again."""
    row = incidents.record("payment_failed", "first")
    conn = incidents._connect()
    conn.execute("UPDATE incidents SET likely_cause = 'billing: already diagnosed' WHERE id = ?", (row["id"],))
    conn.commit()
    conn.close()
    with patch.object(incidents, "_spawn_diagnosis") as spawn:
        incidents.record("payment_failed", "second")
    spawn.assert_not_called()


def test_in_memory_guard_prevents_a_double_trigger_race(temp_db):
    """Even without the DB round-trip settling likely_cause yet, the
    in-memory _diagnosed_incident_ids set stops a second thread being
    spawned for the same incident id within this process."""
    row = incidents.record("payment_failed", "x")
    with patch.object(incidents, "_spawn_diagnosis") as spawn:
        incidents._maybe_trigger_diagnosis(row)
        incidents._maybe_trigger_diagnosis(row)
    spawn.assert_not_called()  # already added to the set by the real record() call above


# ── Non-blocking dispatch ────────────────────────────────────────────────────

def test_record_returns_before_diagnosis_finishes(temp_db):
    """The core requirement: the alert path must never wait on diagnosis."""
    started = threading.Event()

    def slow_diagnose(incident):
        started.set()
        time.sleep(0.3)

    with patch.object(incidents, "_diagnose_in_background", side_effect=slow_diagnose):
        t0 = time.monotonic()
        row = incidents.record("payment_failed", "x")
        elapsed = time.monotonic() - t0

    assert row is not None
    assert elapsed < 0.2, f"record() took {elapsed:.2f}s -- it must not wait on diagnosis"
    assert started.wait(timeout=2), "the background diagnosis thread should still have run"


# ── Evidence gathering: logs ─────────────────────────────────────────────────

def test_log_evidence_filters_by_service_keywords():
    fake_lines = [
        "INFO stripe webhook received",
        "INFO song variant 42 complete",
        "WARNING apiframe credits low",
        "INFO user logged in",
    ]
    with patch("telegram_admin._log_buffer", fake_lines):
        billing_evidence = incidents._gather_log_evidence("billing")
        jobline_evidence = incidents._gather_log_evidence("jobline")
    assert "stripe" in billing_evidence.lower()
    assert "song variant" not in billing_evidence.lower()
    assert "song variant" in jobline_evidence.lower()
    assert "stripe" not in jobline_evidence.lower()


def test_log_evidence_falls_back_to_raw_lines_when_nothing_matches():
    fake_lines = ["INFO totally unrelated line"]
    with patch("telegram_admin._log_buffer", fake_lines):
        evidence = incidents._gather_log_evidence("billing")
    assert "totally unrelated line" in evidence


def test_log_evidence_respects_the_limit():
    fake_lines = [f"INFO line {i}" for i in range(80)]
    with patch("telegram_admin._log_buffer", fake_lines):
        evidence = incidents._gather_log_evidence("beats", limit=50)
    assert evidence.count("\n") == 49  # 50 lines = 49 newlines
    assert "line 79" in evidence and "line 29" not in evidence


def test_log_evidence_handles_buffer_import_failure():
    with patch.dict("sys.modules", {"telegram_admin": None}):
        evidence = incidents._gather_log_evidence("beats")
    assert "unavailable" in evidence.lower()


def test_log_evidence_empty_buffer():
    with patch("telegram_admin._log_buffer", []):
        evidence = incidents._gather_log_evidence("beats")
    assert "no relevant log lines" in evidence.lower()


# ── Evidence gathering: git commits (GitHub API, no local git log) ─────────

def test_git_evidence_uses_the_github_api_not_a_local_git_log():
    list_resp = MagicMock(status_code=200)
    list_resp.json.return_value = [{"sha": "abc1234567", "commit": {"message": "fix: something\n\nlonger body"}}]
    list_resp.raise_for_status = lambda: None
    detail_resp = MagicMock(status_code=200)
    detail_resp.json.return_value = {
        "commit": {"message": "fix: something\n\nlonger body"},
        "files": [{"filename": "backend/main.py"}, {"filename": "backend/db.py"}],
    }
    detail_resp.raise_for_status = lambda: None

    def fake_get(url, **kwargs):
        return list_resp if url.endswith("/commits") else detail_resp

    with patch("incidents.requests.get", side_effect=fake_get) as mock_get:
        evidence = incidents._gather_git_evidence(count=5)

    assert "abc1234" in evidence
    assert "fix: something" in evidence
    assert "backend/main.py" in evidence and "backend/db.py" in evidence
    # No diffs requested anywhere.
    for call in mock_get.call_args_list:
        assert "diff" not in call.args[0].lower()


def test_git_evidence_handles_a_commit_with_no_message_without_crashing():
    """Regression: an empty/missing commit message must not raise
    (str.splitlines()[0] on an empty string is an IndexError) -- one
    malformed commit must not abort the whole evidence-gathering pass."""
    list_resp = MagicMock(status_code=200)
    list_resp.json.return_value = [{"sha": "abc1234567", "commit": {}}]
    list_resp.raise_for_status = lambda: None
    detail_resp = MagicMock(status_code=200)
    detail_resp.json.return_value = {"commit": {}, "files": []}
    detail_resp.raise_for_status = lambda: None

    def fake_get(url, **kwargs):
        return list_resp if url.endswith("/commits") else detail_resp

    with patch("incidents.requests.get", side_effect=fake_get):
        evidence = incidents._gather_git_evidence(count=5)  # must not raise
    assert "abc1234" in evidence


def test_git_evidence_without_github_token():
    with patch.dict(os.environ, {"GITHUB_TOKEN": ""}):
        evidence = incidents._gather_git_evidence()
    assert "unavailable" in evidence.lower()


def test_git_evidence_handles_api_failure_gracefully():
    with patch("incidents.requests.get", side_effect=RuntimeError("network down")):
        evidence = incidents._gather_git_evidence()
    assert "unavailable" in evidence.lower()


# ── The model call and its response contract ─────────────────────────────────

def test_call_diagnosis_model_parses_a_valid_response():
    with patch("anthropic.Anthropic") as client:
        client.return_value.messages.create.return_value = _mock_model_response(
            "api_credits", "high", "Anthropic returned 401 in the last log line."
        )
        result = incidents._call_diagnosis_model(
            {"title": "t", "symptoms": "s", "service": "provider"}, "logs", "commits"
        )
    assert result == {
        "cause_category": "api_credits",
        "confidence": "high",
        "reasoning": "Anthropic returned 401 in the last log line.",
    }


def test_call_diagnosis_model_uses_the_specified_model():
    with patch("anthropic.Anthropic") as client:
        client.return_value.messages.create.return_value = _mock_model_response("unknown", "low")
        incidents._call_diagnosis_model({"title": "t", "symptoms": "s", "service": "beats"}, "l", "g")
    _, kwargs = client.return_value.messages.create.call_args
    assert kwargs["model"] == "claude-sonnet-4-6"


def test_call_diagnosis_model_returns_none_without_api_key():
    with patch.dict(os.environ, {"ANTHROPIC_API_KEY": ""}), patch("anthropic.Anthropic") as client:
        result = incidents._call_diagnosis_model({"title": "t", "symptoms": "s", "service": "beats"}, "l", "g")
    assert result is None
    client.assert_not_called()


def test_call_diagnosis_model_returns_none_on_api_error():
    with patch("anthropic.Anthropic", side_effect=RuntimeError("down")):
        result = incidents._call_diagnosis_model({"title": "t", "symptoms": "s", "service": "beats"}, "l", "g")
    assert result is None


def test_call_diagnosis_model_returns_none_on_unparseable_response():
    with patch("anthropic.Anthropic") as client:
        resp = MagicMock()
        resp.content = [MagicMock(text="not json at all")]
        client.return_value.messages.create.return_value = resp
        result = incidents._call_diagnosis_model({"title": "t", "symptoms": "s", "service": "beats"}, "l", "g")
    assert result is None


def test_call_diagnosis_model_rejects_an_invalid_cause_category():
    with patch("anthropic.Anthropic") as client:
        client.return_value.messages.create.return_value = _mock_model_response(
            "the aliens did it", "high", "reasoning"
        )
        result = incidents._call_diagnosis_model({"title": "t", "symptoms": "s", "service": "beats"}, "l", "g")
    assert result["cause_category"] == "unknown"


def test_call_diagnosis_model_rejects_an_invalid_confidence_level():
    with patch("anthropic.Anthropic") as client:
        client.return_value.messages.create.return_value = _mock_model_response(
            "code", "super-sure", "reasoning"
        )
        result = incidents._call_diagnosis_model({"title": "t", "symptoms": "s", "service": "beats"}, "l", "g")
    assert result["confidence"] == "low"


def test_unknown_cause_always_forces_low_confidence_even_if_model_disagrees():
    """Defense in depth: never trust a contradictory model response over the
    rule that 'unknown' cannot carry anything but low confidence."""
    with patch("anthropic.Anthropic") as client:
        client.return_value.messages.create.return_value = _mock_model_response(
            "unknown", "high", "not sure really"
        )
        result = incidents._call_diagnosis_model({"title": "t", "symptoms": "s", "service": "beats"}, "l", "g")
    assert result["cause_category"] == "unknown"
    assert result["confidence"] == "low"


def test_ambiguous_evidence_produces_insufficient_evidence_not_a_fabricated_cause(temp_db):
    """The required test: a critical incident whose gathered evidence is
    ambiguous/irrelevant must end up with likely_cause = insufficient
    evidence and confidence = low -- never a specific, unsupported cause.

    This simulates a model that correctly followed the system prompt's rule
    1 (say "insufficient evidence" / low confidence rather than guess) --
    it is a test of this module's handling of that response, not of the
    real model's judgment, which cannot be exercised here.
    """
    incident = {
        "id": 1, "service": "beats", "title": "Mystery signup drop",
        "symptoms": "New signups fell to zero for an hour", "likely_cause": None,
    }
    with patch("telegram_admin._log_buffer", ["INFO unrelated line about something else entirely"]), \
         patch("incidents.requests.get", side_effect=RuntimeError("no commits reachable")), \
         patch("anthropic.Anthropic") as client, \
         patch.object(incidents, "_write_diagnosis") as write, \
         patch.object(incidents, "_send_diagnosis_followup") as followup:
        client.return_value.messages.create.return_value = _mock_model_response(
            "unknown", "low", "insufficient evidence to determine a cause"
        )
        incidents._diagnose_in_background(incident)

    write.assert_called_once()
    _, args, _ = write.mock_calls[0]
    incident_id, evidence, likely_cause, confidence = args
    assert incident_id == 1
    assert "insufficient evidence" in likely_cause.lower()
    assert confidence == "low"
    # And no invented specific cause anywhere in what got stored.
    for fabricated in incidents.CAUSE_CATEGORIES:
        if fabricated not in ("unknown",):
            assert fabricated not in likely_cause.lower()
    followup.assert_called_once_with("unknown", "low", "insufficient evidence to determine a cause")


# ── Writing results: only evidence/likely_cause/confidence ─────────────────

def test_write_diagnosis_leaves_actions_attempted_and_resolution_untouched(temp_db):
    row = incidents.record("payment_failed", "x")
    incidents._write_diagnosis(row["id"], "some evidence", "code: a bug", "medium")
    conn = incidents._connect()
    updated = conn.execute("SELECT * FROM incidents WHERE id = ?", (row["id"],)).fetchone()
    conn.close()
    assert updated["evidence"] == "some evidence"
    assert updated["likely_cause"] == "code: a bug"
    assert updated["confidence"] == "medium"
    assert updated["actions_attempted"] is None
    assert updated["resolution"] is None


# ── Telegram follow-up phrasing ───────────────────────────────────────────────

def test_followup_uses_likely_cause_for_medium_and_high_confidence():
    sent = []
    with patch("alerts.send_admin_alert", side_effect=lambda m: sent.append(m) or True):
        incidents._send_diagnosis_followup("api_credits", "high", "auth errors in the logs")
    assert sent[0] == "🔍 Likely cause: api_credits (confidence: high) — auth errors in the logs"

    sent.clear()
    with patch("alerts.send_admin_alert", side_effect=lambda m: sent.append(m) or True):
        incidents._send_diagnosis_followup("code", "medium", "a recent commit touched this path")
    assert sent[0].startswith("🔍 Likely cause: code (confidence: medium)")


def test_followup_uses_possible_cause_for_low_confidence():
    sent = []
    with patch("alerts.send_admin_alert", side_effect=lambda m: sent.append(m) or True):
        incidents._send_diagnosis_followup("database", "low", "a tentative guess")
    assert sent[0].startswith("🔍 Possible cause: database (confidence: low)")


def test_followup_displays_insufficient_evidence_for_unknown_cause():
    sent = []
    with patch("alerts.send_admin_alert", side_effect=lambda m: sent.append(m) or True):
        incidents._send_diagnosis_followup("unknown", "low", "insufficient evidence to determine a cause")
    assert sent[0] == ("🔍 Possible cause: insufficient evidence (confidence: low) "
                        "— insufficient evidence to determine a cause")


# ── Fail-silent end to end ────────────────────────────────────────────────────

def test_diagnose_in_background_fails_silently_when_the_model_call_fails(temp_db):
    row = incidents.record("payment_failed", "x")
    with patch("telegram_admin._log_buffer", []), \
         patch("incidents.requests.get", side_effect=RuntimeError("down")), \
         patch("anthropic.Anthropic", side_effect=RuntimeError("api down")), \
         patch("alerts.send_admin_alert") as followup:
        incidents._diagnose_in_background(dict(row))  # must not raise
    followup.assert_not_called()
    conn = incidents._connect()
    updated = conn.execute("SELECT * FROM incidents WHERE id = ?", (row["id"],)).fetchone()
    conn.close()
    assert updated["likely_cause"] is None
    assert updated["confidence"] is None
    assert updated["evidence"] is None


def test_diagnose_in_background_never_raises_even_if_write_fails(temp_db):
    row = incidents.record("payment_failed", "x")
    with patch("telegram_admin._log_buffer", []), \
         patch("incidents.requests.get", side_effect=RuntimeError("down")), \
         patch("anthropic.Anthropic") as client, \
         patch.object(incidents, "_write_diagnosis", side_effect=RuntimeError("disk full")):
        client.return_value.messages.create.return_value = _mock_model_response("unknown", "low", "x")
        incidents._diagnose_in_background(dict(row))  # must not raise


def test_full_pipeline_writes_the_diagnosis_and_sends_the_followup(temp_db):
    row = incidents.record("payment_failed", "x")
    sent = []
    with patch("telegram_admin._log_buffer", ["ERROR stripe webhook signature invalid"]), \
         patch("incidents.requests.get", side_effect=RuntimeError("no commits")), \
         patch("anthropic.Anthropic") as client, \
         patch("alerts.send_admin_alert", side_effect=lambda m: sent.append(m) or True):
        client.return_value.messages.create.return_value = _mock_model_response(
            "third_party_outage", "high", "Stripe webhook signature errors in the logs."
        )
        incidents._diagnose_in_background(dict(row))

    conn = incidents._connect()
    updated = conn.execute("SELECT * FROM incidents WHERE id = ?", (row["id"],)).fetchone()
    conn.close()
    assert updated["likely_cause"] == "third_party_outage: Stripe webhook signature errors in the logs."
    assert updated["confidence"] == "high"
    assert "stripe webhook signature invalid" in updated["evidence"].lower()
    assert sent and sent[0].startswith("🔍 Likely cause: third_party_outage")
