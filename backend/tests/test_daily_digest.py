"""Steps 4/5 of the alerting build: the (B) morning-digest channel, piggybacked on
zeus_ops_agent.daily_report() — the job that's actually scheduled at 09:00 UTC —
rather than the dead alerts.send_daily_summary() (zero callers, now removed, same
two-implementations-one-dead trap as the earlier run_health_check cleanup).

Covers: the in-memory digest-counter helper, each alert_* that bumps it, the
renewal counter threaded from billing's invoice.paid handler, and daily_report()
itself producing the extended content (songs by type, counters, provider status).
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
os.environ.setdefault("JWT_SECRET", "test-secret")

import alerts  # noqa: E402


def _reset():
    alerts._DIGEST_COUNTERS.clear()
    alerts._ALERT_CATEGORY_STATE.clear()
    alerts._sent_alerts.clear()


# ── counter primitive ────────────────────────────────────────────────────────

def test_bump_and_pop_counters():
    _reset()
    alerts._bump_digest_counter("errors")
    alerts._bump_digest_counter("errors")
    alerts._bump_digest_counter("new_subscriptions")
    counters = alerts.pop_digest_counters()
    assert counters == {"errors": 2, "new_subscriptions": 1}


def test_pop_resets_the_counters():
    _reset()
    alerts._bump_digest_counter("errors")
    alerts.pop_digest_counters()
    assert alerts.pop_digest_counters() == {}


def test_send_daily_summary_is_gone():
    """Confirmed dead code (zero callers) — removed rather than left to rot
    alongside the live daily_report()."""
    assert not hasattr(alerts, "send_daily_summary")


# ── alert_* functions bump the right counters ───────────────────────────────

@pytest.mark.parametrize("call", [
    lambda: alerts.alert_payment_failed("a@x.co"),
    lambda: alerts.alert_webhook_error("evt", "id", "boom"),
    lambda: alerts.alert_credit_not_granted("a@x.co", "£9", "no user"),
    lambda: alerts.alert_lyrics_generation_failed("a@x.co", "normal", "boom"),
    lambda: alerts.alert_service_error("apiframe", 401, "boom"),
    lambda: alerts.alert_song_failed("a@x.co", 1),
])
def test_failure_alerts_bump_the_errors_counter(monkeypatch, call):
    _reset()
    monkeypatch.setattr(alerts, "_send_telegram", lambda msg: True)
    call()
    assert alerts.pop_digest_counters().get("errors") == 1


def test_errors_counter_counts_every_occurrence_even_when_the_send_is_suppressed(monkeypatch):
    """The digest should reflect real incident volume, not just how many Telegram
    messages made it out through the category dedup — a 10-failure burst that
    sends only 1 message must still count as 10 errors."""
    _reset()
    monkeypatch.setattr(alerts, "_send_telegram", lambda msg: True)
    for i in range(10):
        alerts.alert_service_error("apiframe", 401, f"boom {i}")
    assert alerts.pop_digest_counters()["errors"] == 10


def test_alert_payment_bumps_new_subscriptions_not_errors(monkeypatch):
    _reset()
    monkeypatch.setattr(alerts, "_send_telegram", lambda msg: True)
    alerts.alert_payment("a@x.co", "music_starter", "£9")
    counters = alerts.pop_digest_counters()
    assert counters == {"new_subscriptions": 1}


# ── billing.py: renewals bump the renewals counter ──────────────────────────

def _make_stripe_event(event_type, obj):
    import stripe
    return stripe.Event.construct_from(
        {"id": "evt_test", "type": event_type, "data": {"object": obj}}, "sk_test",
    )


@pytest.fixture
def billing_db(tmp_path):
    import db
    p = tmp_path / "t.db"
    db.init_user_tables(p)
    with patch.object(db, "get_db_path", return_value=p):
        yield p


@pytest.fixture
def subscriber(billing_db):
    import db
    user = db.create_user(billing_db, "renewer@test.com", "x", "Renewer", "2026-01-01")
    db.update_user(billing_db, user["id"], stripe_customer_id="cus_renew",
                   subscription_plan="music_starter", subscription_status="active", has_paid=1)
    db.upsert_song_credits(billing_db, user["id"], balance=1, monthly_allowance=25)
    return user


def test_renewal_bumps_the_renewals_counter(billing_db, subscriber):
    import billing
    _reset()
    event = _make_stripe_event(
        "invoice.paid",
        {"id": "in_1", "object": "invoice", "customer": "cus_renew",
         "billing_reason": "subscription_cycle", "amount_paid": 900},
    )
    billing._handle_event(event)
    assert alerts.pop_digest_counters().get("renewals") == 1


def test_first_invoice_does_not_bump_renewals(billing_db, subscriber):
    """subscription_create (the first invoice) is initial provisioning, not a
    renewal — must not inflate the renewal count."""
    import billing
    _reset()
    event = _make_stripe_event(
        "invoice.paid",
        {"id": "in_1", "object": "invoice", "customer": "cus_renew",
         "billing_reason": "subscription_create", "amount_paid": 900},
    )
    billing._handle_event(event)
    assert "renewals" not in alerts.pop_digest_counters()


# ── zeus_ops_agent.daily_report(): extended digest content ─────────────────

@pytest.fixture
def ops_db(tmp_path, monkeypatch):
    import db
    p = tmp_path / "ops.db"
    db.init_user_tables(p)
    monkeypatch.setenv("DB_PATH", str(p))
    return db, p


def test_daily_report_includes_songs_by_type_and_counters(ops_db, monkeypatch):
    _reset()
    db, p = ops_db
    u = db.create_user(p, "d@x.co", "x", "D", "2026-01-01")
    conn = db._conn(p)
    try:
        conn.execute("INSERT INTO lyrics (id,user_id,title,brief,lyrics_text,kids_story,created_at) "
                     "VALUES (1,?,'T','b','la',0,datetime('now'))", (u["id"],))
        conn.execute("INSERT INTO lyrics (id,user_id,title,brief,lyrics_text,kids_story,created_at) "
                     "VALUES (2,?,'T','b','la',1,datetime('now'))", (u["id"],))
        conn.execute("INSERT INTO song_variants (id,lyric_id,user_id,style_prompt,genre_tag,status,take_number,created_at) "
                     "VALUES (1,1,?,'s','pop','complete',1,datetime('now'))", (u["id"],))
        conn.execute("INSERT INTO song_variants (id,lyric_id,user_id,style_prompt,genre_tag,status,take_number,created_at) "
                     "VALUES (2,2,?,'s','pop','failed',1,datetime('now'))", (u["id"],))
        conn.commit()
    finally:
        conn.close()

    alerts._bump_digest_counter("new_subscriptions")
    alerts._bump_digest_counter("renewals")
    alerts._bump_digest_counter("errors")

    import zeus_ops_agent as _ops
    monkeypatch.setattr(alerts, "_check_fal_balance", lambda: None)
    monkeypatch.setattr(alerts, "_check_apiframe_credits", lambda: None)
    sent = []
    monkeypatch.setattr(alerts, "_send_telegram", lambda msg: sent.append(msg) or True)

    _ops.daily_report()

    assert len(sent) == 1
    msg = sent[0]
    assert "Normal: 1 ok, 0 failed" in msg
    assert "Kids-story: 0 ok, 1 failed" in msg
    assert "New subscriptions: 1" in msg
    assert "Renewals: 1" in msg
    assert "Errors alerted: 1" in msg
    assert "fal.ai + Apiframe balances healthy" in msg
    # Counters must reset after being read into the digest
    assert alerts.pop_digest_counters() == {}


def test_daily_report_surfaces_low_provider_balance(ops_db, monkeypatch):
    _reset()
    db, p = ops_db
    import zeus_ops_agent as _ops
    monkeypatch.setattr(alerts, "_check_fal_balance", lambda: "⚠️ fal.ai balance low: $3.00")
    monkeypatch.setattr(alerts, "_check_apiframe_credits", lambda: None)
    sent = []
    monkeypatch.setattr(alerts, "_send_telegram", lambda msg: sent.append(msg) or True)

    _ops.daily_report()

    assert "fal.ai balance low" in sent[0]
    assert "healthy" not in sent[0]


def test_daily_report_never_raises_if_a_balance_checker_throws(ops_db, monkeypatch):
    _reset()
    db, p = ops_db
    import zeus_ops_agent as _ops
    monkeypatch.setattr(alerts, "_check_fal_balance", lambda: (_ for _ in ()).throw(RuntimeError("down")))
    monkeypatch.setattr(alerts, "_check_apiframe_credits", lambda: None)
    sent = []
    monkeypatch.setattr(alerts, "_send_telegram", lambda msg: sent.append(msg) or True)

    _ops.daily_report()  # must not raise

    assert len(sent) == 1
    assert "raised" in sent[0]
