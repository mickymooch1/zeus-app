"""Safe action execution for Porick, gated by incidents.py's automatic
diagnosis (incident_actions.py).

maybe_offer_action() is the only entry point that ever creates a pending
offer, and it is only ever called from incidents._diagnose_in_background()
with the raw cause_category/confidence the diagnosis model returned. These
tests call it directly rather than driving a real diagnosis, matching how
test_incident_diagnosis.py isolates the diagnosis step itself.

Every action requires an explicit "yes" from the admin -- nothing here ever
executes on its own. The forbidden-action test is the one safety property
that must hold even if ACTION_WHITELIST is tampered with at runtime.
"""
import os
import pathlib
import sys
from datetime import datetime, timedelta, timezone

import pytest

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))
os.environ.setdefault("ANTHROPIC_API_KEY", "test-key")
os.environ.setdefault("APIFRAME_API_KEY", "test-key")
os.environ.setdefault("SONG_STORAGE_PATH", "/tmp/test_songs")
os.environ.setdefault("SONG_PUBLIC_BASE_URL", "https://example.com/files/songs")
os.environ.setdefault("SONG_WEBHOOK_URL", "https://zeusaidesign.com/webhooks/apiframe")
os.environ.setdefault("JWT_SECRET", "test-secret-for-incident-action-tests")

import db
import incident_actions
import incidents


@pytest.fixture
def temp_db(tmp_path, monkeypatch):
    path = tmp_path / "test.db"
    monkeypatch.setattr(db, "get_db_path", lambda: path)
    return path


@pytest.fixture(autouse=True)
def no_diagnosis(monkeypatch):
    """These tests call maybe_offer_action directly; nothing here should
    spawn a real diagnosis thread."""
    monkeypatch.setattr(incidents, "_spawn_diagnosis", lambda incident: None)
    incidents._diagnosed_incident_ids.clear()
    yield
    incidents._diagnosed_incident_ids.clear()


@pytest.fixture(autouse=True)
def clean_pending_offers():
    """_pending_offers is module-level in-memory state -- never let one test
    leak a pending offer into the next."""
    incident_actions._pending_offers.clear()
    yield
    incident_actions._pending_offers.clear()


def _make_incident(temp_db, category="stuck_song_sweep", severity="critical"):
    row = incidents.record(category, "3 songs stuck > 15 min", severity=severity)
    assert row is not None
    return dict(row)


def _actions_attempted(temp_db, incident_id):
    conn = incidents._connect()
    try:
        row = conn.execute("SELECT actions_attempted FROM incidents WHERE id = ?", (incident_id,)).fetchone()
        return row["actions_attempted"]
    finally:
        conn.close()


# ── Offer gating ─────────────────────────────────────────────────────────────

def test_low_confidence_diagnosis_never_offers_an_action(temp_db, monkeypatch):
    sent = []
    monkeypatch.setattr("alerts.send_admin_alert", lambda msg: sent.append(msg) or True)
    incident = _make_incident(temp_db)

    # cause="deployment" on category="stuck_song_sweep" would match
    # restart_worker at medium/high confidence -- "low" must still block it.
    incident_actions.maybe_offer_action(incident, cause="deployment", confidence="low")

    assert incident_actions._pending_offers == {}
    assert sent == []
    assert _actions_attempted(temp_db, incident["id"]) is None


def test_non_whitelisted_category_never_offers_an_action(temp_db, monkeypatch):
    """No action type in ACTION_WHITELIST covers "payment_failed" at all, so
    no cause/confidence combination for it can ever produce an offer."""
    sent = []
    monkeypatch.setattr("alerts.send_admin_alert", lambda msg: sent.append(msg) or True)
    incident = _make_incident(temp_db, category="payment_failed")

    incident_actions.maybe_offer_action(incident, cause="code", confidence="high")

    assert incident_actions._pending_offers == {}
    assert sent == []
    assert _actions_attempted(temp_db, incident["id"]) is None


def test_matching_category_and_cause_at_high_confidence_offers_an_action(temp_db, monkeypatch):
    sent = []
    monkeypatch.setattr("alerts.send_admin_alert", lambda msg: sent.append(msg) or True)
    incident = _make_incident(temp_db)

    incident_actions.maybe_offer_action(incident, cause="deployment", confidence="high")

    assert incident["id"] in incident_actions._pending_offers
    offer = incident_actions._pending_offers[incident["id"]]
    assert offer["action_type"] == "restart_worker"
    assert len(sent) == 1
    assert incident["title"] in sent[0]
    assert "Reply yes to proceed" in sent[0]


# ── Reply handling: yes / no / timeout ───────────────────────────────────────

def test_yes_executes_and_logs(temp_db, monkeypatch):
    incident = _make_incident(temp_db)
    incident_actions._pending_offers[incident["id"]] = {
        "action_type": "refund_stuck_song",
        "description": "refund credits for the currently stuck song(s) (existing auto-refund rule)",
        "extra": None,
        "offered_at": datetime.now(timezone.utc),
    }
    monkeypatch.setattr("zeus_ops_agent._fix_stuck_songs", lambda: ["⏳ Auto-failed 2 stuck song(s) — credits refunded"])

    reply = incident_actions.handle_admin_reply("yes")

    assert reply is not None
    assert reply.startswith("✅")
    assert incident["id"] not in incident_actions._pending_offers
    logged = _actions_attempted(temp_db, incident["id"])
    assert logged.startswith("executed:")
    assert "Auto-failed 2 stuck song" in logged


def test_yes_reports_failure_plainly_without_retrying(temp_db, monkeypatch):
    incident = _make_incident(temp_db)
    incident_actions._pending_offers[incident["id"]] = {
        "action_type": "refund_stuck_song",
        "description": "refund credits for the currently stuck song(s) (existing auto-refund rule)",
        "extra": None,
        "offered_at": datetime.now(timezone.utc),
    }
    calls = []

    def _boom():
        calls.append(1)
        raise RuntimeError("db is locked")

    monkeypatch.setattr("zeus_ops_agent._fix_stuck_songs", _boom)

    reply = incident_actions.handle_admin_reply("yes")

    assert reply.startswith("❌")
    assert "db is locked" in reply
    assert len(calls) == 1  # no automatic retry
    assert _actions_attempted(temp_db, incident["id"]).startswith("failed:")


def test_no_declines_and_logs(temp_db):
    incident = _make_incident(temp_db)
    incident_actions._pending_offers[incident["id"]] = {
        "action_type": "restart_worker",
        "description": "restart the app",
        "extra": None,
        "offered_at": datetime.now(timezone.utc),
    }

    reply = incident_actions.handle_admin_reply("NO")  # case-insensitive

    assert "Skipped" in reply
    assert incident["id"] not in incident_actions._pending_offers
    assert _actions_attempted(temp_db, incident["id"]) == "declined"


def test_timeout_expires_and_logs(temp_db, monkeypatch):
    sent = []
    monkeypatch.setattr("alerts.send_admin_alert", lambda msg: sent.append(msg) or True)
    incident = _make_incident(temp_db)
    incident_actions._pending_offers[incident["id"]] = {
        "action_type": "restart_worker",
        "description": "restart the app",
        "extra": None,
        "offered_at": datetime.now(timezone.utc) - timedelta(minutes=31),
    }

    incident_actions.expire_stale_offers()

    assert incident["id"] not in incident_actions._pending_offers
    assert _actions_attempted(temp_db, incident["id"]) == "expired"
    assert sent == []  # no nudging on timeout


def test_yes_with_nothing_pending_falls_through(temp_db):
    assert incident_actions.handle_admin_reply("yes") is None


def test_expired_offer_is_not_honoured_by_a_late_yes(temp_db):
    incident = _make_incident(temp_db)
    incident_actions._pending_offers[incident["id"]] = {
        "action_type": "restart_worker",
        "description": "restart the app",
        "extra": None,
        "offered_at": datetime.now(timezone.utc) - timedelta(minutes=45),
    }

    reply = incident_actions.handle_admin_reply("yes")

    assert reply is None
    assert _actions_attempted(temp_db, incident["id"]) == "expired"


# ── Hard-coded forbidden action enforcement ─────────────────────────────────

def test_forbidden_action_type_cannot_execute_even_if_added_to_whitelist(temp_db, monkeypatch):
    incident = _make_incident(temp_db)
    monkeypatch.setitem(incident_actions.ACTION_WHITELIST, "billing_change", {
        "categories": {"stuck_song_sweep"},
        "causes": None,
        "description": "issue a discretionary billing credit",
    })
    assert "billing_change" not in incident_actions._EXECUTORS

    offer = {"action_type": "billing_change", "description": "issue a discretionary billing credit", "extra": None}
    reply = incident_actions.execute_action(incident["id"], offer)

    assert "⛔" in reply
    assert _actions_attempted(temp_db, incident["id"]) == "refused: forbidden action type"


def test_forbidden_action_type_is_never_matched_by_the_whitelist_lookup(monkeypatch):
    """Even if a forbidden type is added with categories/causes broad enough
    to match anything, _match_whitelist must never select it."""
    monkeypatch.setitem(incident_actions.ACTION_WHITELIST, "data_deletion", {
        "categories": {"stuck_song_sweep"},
        "causes": None,
        "description": "purge old rows",
    })
    action_type = incident_actions._match_whitelist("stuck_song_sweep", "deployment")
    assert action_type != "data_deletion"
