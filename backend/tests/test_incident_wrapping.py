"""Incident tracking wrapped AROUND the existing alert_* triggers/dedup and
the Porickbot health-check cycle -- not changing either. Pins:
  * alerts.py: a severity prefix (and, on repeat, an occurrence line) is
    prepended to the message the existing dedup layer already sends; the
    existing exact-text / category-keyed dedup decisions are untouched.
  * zeus_ops_agent.py: health_check()/stuck_song_sweep() record an incident
    per issue found, and auto-resolve quiet ones via incidents.resolve_stale(),
    sending a short recovered notice for each.
  * telegram_admin.py: "incidents" / "history <category>" are answered by
    plain Python (never routed to the AI command parser).
"""
import os
import pathlib
import sys
from unittest.mock import patch

import pytest

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))
os.environ.setdefault("ANTHROPIC_API_KEY", "test-key")
os.environ.setdefault("APIFRAME_API_KEY", "test-key")
os.environ.setdefault("SONG_STORAGE_PATH", "/tmp/test_songs")
os.environ.setdefault("SONG_PUBLIC_BASE_URL", "https://example.com/files/songs")
os.environ.setdefault("SONG_WEBHOOK_URL", "https://zeusaidesign.com/webhooks/apiframe")
os.environ.setdefault("JWT_SECRET", "test-secret-for-incident-wrapping-tests")

import db
import alerts
import incidents


@pytest.fixture
def temp_db(tmp_path, monkeypatch):
    """Points BOTH db.get_db_path() (incidents.py) and zeus_ops_agent's own
    DB_PATH-based _db() (its direct sqlite3 calls) at the same file, since
    the two currently resolve the db path two different ways."""
    path = tmp_path / "test.db"
    monkeypatch.setattr(db, "get_db_path", lambda: path)
    monkeypatch.setenv("DB_PATH", str(path))
    alerts._DIGEST_COUNTERS.clear()
    alerts._ALERT_CATEGORY_STATE.clear()
    alerts._sent_alerts.clear()
    return path


# ── alerts.py wrapping ───────────────────────────────────────────────────────

def test_critical_alert_gets_the_critical_prefix(temp_db):
    sent = []
    with patch.object(alerts, "_send_telegram", side_effect=lambda m: sent.append(m) or True):
        alerts.alert_payment_failed("a@b.com", "sess_1")
    assert sent and sent[0].startswith("🔴 CRITICAL")


def test_info_alert_gets_the_info_prefix(temp_db):
    sent = []
    with patch.object(alerts, "_send_telegram", side_effect=lambda m: sent.append(m) or True):
        alerts.alert_new_user("a@b.com")
    assert sent and sent[0].startswith("🔵 INFO")


def test_warning_alert_gets_the_warning_prefix(temp_db):
    sent = []
    with patch.object(alerts, "_send_telegram", side_effect=lambda m: sent.append(m) or True):
        alerts.alert_fade_out_failed(42, "ffmpeg missing")
    assert sent and sent[0].startswith("🟡 WARNING")


def test_service_error_severity_follows_status_code(temp_db):
    sent = []
    with patch.object(alerts, "_send_telegram", side_effect=lambda m: sent.append(m) or True):
        alerts.alert_service_error("apiframe", 401, "unauthorized")
    assert sent[-1].startswith("🔴 CRITICAL")
    sent.clear()
    with patch.object(alerts, "_send_telegram", side_effect=lambda m: sent.append(m) or True):
        alerts.alert_service_error("apiframe", 429, "rate limited")
    assert sent[-1].startswith("🟡 WARNING")


def test_repeat_occurrence_gets_the_nth_time_line(temp_db):
    # alert_subscription_cancelled uses send_admin_alert's exact-text dedup,
    # not the category-keyed cooldown -- different emails per call means
    # both actually send, so this isolates the occurrence-line behaviour
    # from send_admin_alert_deduped's own (unrelated, unchanged) suppression.
    sent = []
    with patch.object(alerts, "_send_telegram", side_effect=lambda m: sent.append(m) or True):
        alerts.alert_subscription_cancelled("a@b.com", "music_pro")
        alerts.alert_subscription_cancelled("c@d.com", "music_pro")
    assert len(sent) == 2
    assert "2nd time in 24h" in sent[-1]


def test_category_dedup_cooldown_is_unchanged(temp_db):
    """Incident tracking must not affect send_admin_alert_deduped's own
    suppression -- lyrics_failed is deduped per song_type with a 15-min
    default cooldown; two calls in immediate succession still send once."""
    sent = []
    with patch.object(alerts, "_send_telegram", side_effect=lambda m: sent.append(m) or True):
        alerts.alert_lyrics_generation_failed("a@b.com", "normal", "boom")
        alerts.alert_lyrics_generation_failed("c@d.com", "normal", "boom again")
    assert len(sent) == 1, "category dedup should still suppress the second occurrence"
    # But the incident itself recorded BOTH occurrences regardless of dedup.
    row = incidents.list_open()[0]
    assert row["occurrence_count"] == 2


def test_incident_recorded_even_when_telegram_send_is_suppressed(temp_db):
    """occurrence_count must reflect every real occurrence, not just every
    Telegram message that made it out past dedup."""
    with patch.object(alerts, "_send_telegram", return_value=True):
        alerts.alert_fade_out_failed(1, "x")
        alerts.alert_fade_out_failed(2, "x")  # same category -- still recorded
    rows = incidents.list_open()
    assert len(rows) == 1
    assert rows[0]["occurrence_count"] == 2


def test_a_failing_incident_lookup_does_not_break_the_alert(temp_db):
    """If incidents.py's own DB access falls over, the alert must still send
    -- incident bookkeeping is not allowed to become a new way to lose an
    alert that used to go out unconditionally."""
    sent = []
    with patch.object(alerts, "_send_telegram", side_effect=lambda m: sent.append(m) or True), \
         patch.object(incidents, "record", side_effect=RuntimeError("db is gone")):
        alerts.alert_payment_failed("a@b.com")
    assert sent, "the alert must still be sent even if incident tracking fails"


# ── zeus_ops_agent.py: health_check / stuck_song_sweep wrapping ─────────────

def test_health_check_prefixes_a_low_balance_warning(temp_db):
    import zeus_ops_agent as ops
    sent = []
    with patch.object(ops, "_fix_stuck_songs", return_value=[]), \
         patch("alerts._check_fal_balance", return_value="⚠️ fal.ai balance low: $4.00"), \
         patch("alerts._check_apiframe_credits", return_value=None), \
         patch("alerts._check_ai_providers", return_value=None), \
         patch.object(alerts, "send_admin_alert", side_effect=lambda m: sent.append(m) or True):
        ops.health_check()
    assert sent and "🟡 WARNING" in sent[0]
    assert incidents.list_open()[0]["category"] == "fal_balance"


def test_health_check_prefixes_a_critical_provider_failure(temp_db):
    import zeus_ops_agent as ops
    sent = []
    with patch.object(ops, "_fix_stuck_songs", return_value=[]), \
         patch("alerts._check_fal_balance", return_value=None), \
         patch("alerts._check_apiframe_credits", return_value=None), \
         patch("alerts._check_ai_providers", return_value="🔴 CRITICAL: Anthropic auth failed."), \
         patch.object(alerts, "send_admin_alert", side_effect=lambda m: sent.append(m) or True):
        ops.health_check()
    assert sent and "🔴 CRITICAL" in sent[0]
    row = incidents.list_open()[0]
    assert row["category"] == "ai_providers" and row["severity"] == "critical"


def test_stuck_song_sweep_records_and_prefixes(temp_db):
    import zeus_ops_agent as ops
    sent = []
    with patch.object(ops, "_fix_stuck_songs", return_value=["⏳ Auto-failed 1 stuck song(s)"]), \
         patch.object(alerts, "send_admin_alert", side_effect=lambda m: sent.append(m) or True):
        ops.stuck_song_sweep()
    assert sent and sent[0].startswith("🟡 WARNING")
    assert incidents.list_open()[0]["category"] == "stuck_song_sweep"


def test_health_check_sends_a_recovered_notice_for_a_quiet_incident(temp_db):
    import zeus_ops_agent as ops
    from datetime import datetime, timedelta, timezone

    incidents.record("fal_balance", "was low", severity="warning")
    conn = incidents._connect()
    stale = (datetime.now(timezone.utc) - timedelta(minutes=90)).isoformat()
    conn.execute("UPDATE incidents SET last_seen = ? WHERE category = 'fal_balance'", (stale,))
    conn.commit()
    conn.close()

    sent = []
    with patch.object(ops, "_fix_stuck_songs", return_value=[]), \
         patch("alerts._check_fal_balance", return_value=None), \
         patch("alerts._check_apiframe_credits", return_value=None), \
         patch("alerts._check_ai_providers", return_value=None), \
         patch.object(alerts, "send_admin_alert", side_effect=lambda m: sent.append(m) or True):
        ops.health_check()
    assert any("Recovered" in m for m in sent)
    assert incidents.list_open() == []


def test_stuck_song_sweep_also_runs_the_recovery_sweep(temp_db):
    """The 15-min cycle resolves stale incidents too, not just the daily one --
    that's what makes auto-resolve responsive rather than once-a-day."""
    import zeus_ops_agent as ops
    from datetime import datetime, timedelta, timezone

    incidents.record("payment_failed", "old")
    conn = incidents._connect()
    stale = (datetime.now(timezone.utc) - timedelta(minutes=90)).isoformat()
    conn.execute("UPDATE incidents SET last_seen = ? WHERE category = 'payment_failed'", (stale,))
    conn.commit()
    conn.close()

    sent = []
    with patch.object(ops, "_fix_stuck_songs", return_value=[]), \
         patch.object(alerts, "send_admin_alert", side_effect=lambda m: sent.append(m) or True):
        ops.stuck_song_sweep()
    assert any("Recovered" in m for m in sent)


# ── telegram_admin.py: "incidents" / "history <category>" ──────────────────

def test_incidents_command_lists_open_incidents(temp_db):
    import telegram_admin as ta
    incidents.record("payment_failed", "x")
    with patch.object(ta, "_ai_parse", side_effect=AssertionError("must not call the AI parser")):
        reply = ta.parse_and_run("incidents")
    assert "payment_failed" in reply
    assert "🔴 CRITICAL" in reply


def test_porick_incidents_prefix_also_works(temp_db):
    import telegram_admin as ta
    incidents.record("fade_out_failed", "x")
    with patch.object(ta, "_ai_parse", side_effect=AssertionError("must not call the AI parser")):
        reply = ta.parse_and_run("porick incidents")
    assert "fade_out_failed" in reply


def test_incidents_command_reports_none_open(temp_db):
    import telegram_admin as ta
    with patch.object(ta, "_ai_parse", side_effect=AssertionError("must not call the AI parser")):
        reply = ta.parse_and_run("incidents")
    assert "No open incidents" in reply


def test_history_command_shows_resolved_incidents_with_cause_and_resolution(temp_db):
    import telegram_admin as ta
    from datetime import datetime, timedelta, timezone

    incidents.record("fade_out_failed", "x")
    conn = incidents._connect()
    stale = (datetime.now(timezone.utc) - timedelta(minutes=90)).isoformat()
    conn.execute("UPDATE incidents SET last_seen = ? WHERE category = 'fade_out_failed'", (stale,))
    conn.commit()
    conn.close()
    incidents.resolve_stale()

    with patch.object(ta, "_ai_parse", side_effect=AssertionError("must not call the AI parser")):
        reply = ta.parse_and_run("history fade_out_failed")
    assert "fade_out_failed" in reply
    assert "cause:" in reply and "resolution:" in reply


def test_history_command_handles_an_unknown_category(temp_db):
    import telegram_admin as ta
    with patch.object(ta, "_ai_parse", side_effect=AssertionError("must not call the AI parser")):
        reply = ta.parse_and_run("history nothing_like_this_exists")
    assert "No resolved incidents" in reply


def test_incidents_and_history_never_reach_the_ai_parser(temp_db):
    """The whole point: these two commands cost nothing to run."""
    import telegram_admin as ta
    with patch.object(ta, "_ai_parse") as mock_parse:
        ta.parse_and_run("incidents")
        ta.parse_and_run("porick incidents")
        ta.parse_and_run("history payment_failed")
        ta.parse_and_run("porick history payment_failed")
    mock_parse.assert_not_called()
