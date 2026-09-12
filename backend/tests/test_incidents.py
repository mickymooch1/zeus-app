"""Incident tracking for Porickbot's monitoring (incidents.py).

Wraps the existing alert_* triggers and dedup in alerts.py without changing
either -- these tests pin: the wrapping (severity prefix + occurrence line
prepended to messages already sent), the storage contract (find-or-create by
open category, bump occurrence_count/last_seen, severity escalates but never
downgrades), auto-resolve after 60 minutes of quiet, and the two read-only
Telegram commands.

Severity classification itself is a plain lookup table, no model call. A
critical incident CAN trigger the automatic-diagnosis model call (see
record()) -- that flow, including the model call itself, is covered
separately in test_incident_diagnosis.py. Here, `no_diagnosis` is applied
autouse so creating a critical incident in these tests never spawns a real
background thread making a real network call.
"""
import os
import pathlib
import sys
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pytest

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))
os.environ.setdefault("ANTHROPIC_API_KEY", "test-key")
os.environ.setdefault("APIFRAME_API_KEY", "test-key")
os.environ.setdefault("SONG_STORAGE_PATH", "/tmp/test_songs")
os.environ.setdefault("SONG_PUBLIC_BASE_URL", "https://example.com/files/songs")
os.environ.setdefault("SONG_WEBHOOK_URL", "https://zeusaidesign.com/webhooks/apiframe")
os.environ.setdefault("JWT_SECRET", "test-secret-for-incident-tests")

import db
import incidents


@pytest.fixture
def temp_db(tmp_path, monkeypatch):
    path = tmp_path / "test.db"
    monkeypatch.setattr(db, "get_db_path", lambda: path)
    return path


@pytest.fixture(autouse=True)
def no_diagnosis(monkeypatch):
    """Prevent record() from ever spawning a real diagnosis thread in this
    file -- these tests aren't about diagnosis, and without this a
    critical-severity call here would make a real network call."""
    monkeypatch.setattr(incidents, "_spawn_diagnosis", lambda incident: None)
    incidents._diagnosed_incident_ids.clear()
    yield
    incidents._diagnosed_incident_ids.clear()


# ── classify() / severity helpers ────────────────────────────────────────────

def test_classify_known_categories():
    assert incidents.classify("new_signup") == ("beats", "info", "New signup")
    assert incidents.classify("payment_failed")[1] == "critical"
    assert incidents.classify("fade_out_failed")[1] == "warning"


def test_classify_prefix_categories():
    service, severity, title = incidents.classify("lyrics_failed:kids-story")
    assert service == "jobline" and severity == "critical"
    service, severity, title = incidents.classify("song_failed:normal")
    assert service == "jobline" and severity == "critical"


def test_classify_service_error_has_no_fixed_severity():
    """severity is None here on purpose -- alert_service_error computes it
    per status code and passes it explicitly to note()."""
    service, severity, title = incidents.classify("service_error:apiframe:429")
    assert service == "provider"
    assert severity is None


def test_classify_unknown_category_defaults_safely():
    service, severity, title = incidents.classify("something_nobody_registered")
    assert service in incidents.VALID_SERVICES
    assert severity in incidents.VALID_SEVERITIES


def test_severity_from_status_code():
    assert incidents.severity_from_status_code(401) == "critical"
    assert incidents.severity_from_status_code(402) == "critical"
    assert incidents.severity_from_status_code(403) == "critical"
    assert incidents.severity_from_status_code(429) == "warning"
    assert incidents.severity_from_status_code(500) == "warning"
    assert incidents.severity_from_status_code("not-a-number") == "warning"


def test_severity_from_checker_message():
    assert incidents.severity_from_checker_message("🔴 CRITICAL: Anthropic auth failed.") == "critical"
    assert incidents.severity_from_checker_message("🛑 fal.ai balance EXHAUSTED ($0.00)") == "critical"
    assert incidents.severity_from_checker_message("⁉️ Apiframe credits UNREADABLE — HTTP 404") == "critical"
    assert incidents.severity_from_checker_message("🟡 WARNING: OpenRouter balance low: $2.00.") == "warning"
    assert incidents.severity_from_checker_message("⚠️ fal.ai balance low: $4.00") == "warning"


# ── record() ─────────────────────────────────────────────────────────────────

def test_record_creates_a_new_open_incident(temp_db):
    row = incidents.record("fade_out_failed", "variant_id=1: ffmpeg missing")
    assert row["status"] == "open"
    assert row["occurrence_count"] == 1
    assert row["service"] == "jobline"
    assert row["severity"] == "warning"
    assert row["title"] == "Song fade-out failed"
    assert row["symptoms"] == "variant_id=1: ffmpeg missing"
    assert row["first_seen"] == row["last_seen"]
    # Diagnosis columns are created but must stay empty -- a later stage fills them.
    for col in ("evidence", "likely_cause", "confidence", "actions_attempted", "resolution"):
        assert row[col] is None


def test_record_bumps_an_existing_open_incident_instead_of_duplicating(temp_db):
    first = incidents.record("fade_out_failed", "variant_id=1")
    second = incidents.record("fade_out_failed", "variant_id=2")
    assert second["id"] == first["id"]
    assert second["occurrence_count"] == 2
    assert second["first_seen"] == first["first_seen"]
    assert second["last_seen"] >= first["last_seen"]


def test_record_does_not_touch_symptoms_title_or_severity_on_repeat(temp_db):
    """Spec is explicit: on repeat, only occurrence_count and last_seen change."""
    incidents.record("fade_out_failed", "original symptoms")
    second = incidents.record("fade_out_failed", "a completely different symptom string")
    assert second["symptoms"] == "original symptoms"


def test_record_two_different_categories_stay_independent(temp_db):
    incidents.record("fade_out_failed", "x")
    incidents.record("payment_failed", "y")
    open_rows = incidents.list_open()
    assert {r["category"] for r in open_rows} == {"fade_out_failed", "payment_failed"}
    assert all(r["occurrence_count"] == 1 for r in open_rows)


def test_record_explicit_severity_overrides_the_table(temp_db):
    row = incidents.record("service_error:apiframe:401", "x", severity="critical")
    assert row["severity"] == "critical"


def test_record_never_raises_on_a_broken_connection(temp_db):
    with patch.object(incidents, "_connect", side_effect=RuntimeError("disk full")):
        assert incidents.record("fade_out_failed", "x") is None


# ── note() — the Telegram-message wrapping ──────────────────────────────────

def test_note_first_occurrence_has_no_nth_time_line(temp_db):
    prefix = incidents.note("payment_failed", "first failure")
    assert prefix == "🔴 CRITICAL"


def test_note_repeat_occurrence_adds_the_nth_time_line(temp_db):
    incidents.note("fade_out_failed", "first")
    incidents.note("fade_out_failed", "second")
    prefix = incidents.note("fade_out_failed", "third")
    assert prefix.startswith("🟡 WARNING\n")
    assert "3rd time in 24h — first seen " in prefix


def test_note_ordinal_suffixes():
    assert incidents._ordinal(1) == "1st"
    assert incidents._ordinal(2) == "2nd"
    assert incidents._ordinal(3) == "3rd"
    assert incidents._ordinal(4) == "4th"
    assert incidents._ordinal(11) == "11th"
    assert incidents._ordinal(12) == "12th"
    assert incidents._ordinal(21) == "21st"
    assert incidents._ordinal(101) == "101st"


def test_note_never_raises_even_if_recording_fails(temp_db):
    with patch.object(incidents, "record", side_effect=RuntimeError("boom")):
        prefix = incidents.note("payment_failed", "x")
    assert prefix == "🔴 CRITICAL"


# ── resolve_stale() — auto-resolve after 60 minutes of quiet ─────────────────

def _age_last_seen(category: str, minutes: int) -> None:
    conn = incidents._connect()
    stale = (datetime.now(timezone.utc) - timedelta(minutes=minutes)).isoformat()
    conn.execute("UPDATE incidents SET last_seen = ? WHERE category = ?", (stale, category))
    conn.commit()
    conn.close()


def test_resolve_stale_leaves_a_recently_seen_incident_open(temp_db):
    incidents.record("fade_out_failed", "x")
    _age_last_seen("fade_out_failed", minutes=10)
    resolved = incidents.resolve_stale()
    assert resolved == []
    assert len(incidents.list_open()) == 1


def test_resolve_stale_closes_a_quiet_incident(temp_db):
    incidents.record("fade_out_failed", "x")
    _age_last_seen("fade_out_failed", minutes=61)
    resolved = incidents.resolve_stale()
    assert len(resolved) == 1
    assert resolved[0]["category"] == "fade_out_failed"
    assert resolved[0]["status"] == "resolved"
    assert resolved[0]["resolved_at"] is not None
    assert incidents.list_open() == []


def test_resolve_stale_does_not_close_a_category_that_just_recurred(temp_db):
    """A category recorded again THIS cycle has a fresh last_seen -- the
    ordering (record before resolve_stale) is what keeps it open, no extra
    'still failing' flag needs to be threaded through."""
    incidents.record("fade_out_failed", "old occurrence")
    _age_last_seen("fade_out_failed", minutes=90)
    incidents.record("fade_out_failed", "brand new occurrence")  # refreshes last_seen
    resolved = incidents.resolve_stale()
    assert resolved == []
    assert len(incidents.list_open()) == 1


def test_resolve_stale_only_touches_the_stale_one(temp_db):
    incidents.record("fade_out_failed", "x")
    incidents.record("payment_failed", "y")
    _age_last_seen("fade_out_failed", minutes=90)
    resolved = incidents.resolve_stale()
    assert [r["category"] for r in resolved] == ["fade_out_failed"]
    remaining = incidents.list_open()
    assert len(remaining) == 1 and remaining[0]["category"] == "payment_failed"


def test_resolve_stale_never_raises(temp_db):
    with patch.object(incidents, "_connect", side_effect=RuntimeError("boom")):
        assert incidents.resolve_stale() == []


# ── list_open() / list_history() ─────────────────────────────────────────────

def test_list_open_orders_critical_before_warning_before_info(temp_db):
    incidents.record("new_signup", "x")       # info
    incidents.record("fade_out_failed", "x")  # warning
    incidents.record("payment_failed", "x")   # critical
    rows = incidents.list_open()
    assert [r["severity"] for r in rows] == ["critical", "warning", "info"]


def test_list_history_returns_only_resolved_for_that_category_newest_first(temp_db):
    incidents.record("fade_out_failed", "occurrence 1")
    _age_last_seen("fade_out_failed", minutes=90)
    incidents.resolve_stale()

    incidents.record("fade_out_failed", "occurrence 2")
    _age_last_seen("fade_out_failed", minutes=90)
    incidents.resolve_stale()

    incidents.record("payment_failed", "unrelated, still open")

    history = incidents.list_history("fade_out_failed")
    assert len(history) == 2
    assert all(row["status"] == "resolved" for row in history)
    assert history[0]["symptoms"] == "occurrence 2"  # newest first


def test_list_history_respects_limit(temp_db):
    for i in range(7):
        incidents.record("fade_out_failed", f"occurrence {i}")
        _age_last_seen("fade_out_failed", minutes=90)
        incidents.resolve_stale()
    assert len(incidents.list_history("fade_out_failed", limit=5)) == 5


def test_list_history_empty_for_unknown_category(temp_db):
    assert incidents.list_history("nothing_ever_happened_here") == []


# ── humanize_age() ────────────────────────────────────────────────────────────

def test_humanize_age_minutes_hours_days():
    now = datetime.now(timezone.utc)
    assert incidents.humanize_age((now - timedelta(minutes=5)).isoformat()) == "5m"
    assert incidents.humanize_age((now - timedelta(hours=2, minutes=15)).isoformat()) == "2h 15m"
    assert incidents.humanize_age((now - timedelta(days=3, hours=4)).isoformat()) == "3d 4h"


def test_humanize_age_never_raises_on_garbage_input():
    assert incidents.humanize_age("not a timestamp") == "unknown age"


# ── Schema ────────────────────────────────────────────────────────────────────

def test_incidents_table_has_every_required_column(temp_db):
    row = incidents.record("fade_out_failed", "x")
    expected = {
        "id", "service", "category", "severity", "title", "symptoms", "evidence",
        "likely_cause", "confidence", "actions_attempted", "resolution",
        "first_seen", "last_seen", "occurrence_count", "status", "resolved_at",
    }
    assert expected <= set(row.keys())
