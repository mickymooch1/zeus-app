"""Generic backfill for stale plan credit allowances (2026-09-16, follow-up to
the laky120 incident).

_PLAN_SONG_CREDITS has been bumped multiple times historically (music_starter
10->15->25->30, music_pro 3->30->40->55->75) with no backfill for existing
subscribers -- only a checkout or that user's NEXT renewal refreshes their
stored monthly_allowance. A production query found three active subscribers
stuck on stale (lower) allowances: tinayarowle@icloud.com and
ebrown9042@gmail.com (music_starter, stuck at 25) and review@zeusbeats.com
(music_pro, stuck at 55).

billing.backfill_stale_plan_allowances() replaces the earlier laky120-only
reconcile_stale_credit_override(): it scans every active subscriber, and for
anyone below their plan's CURRENT correct allowance, raises monthly_allowance
to the correct value and ADDS the shortfall to balance -- never resets it, so
nobody loses credits they haven't used yet. Self-limiting (only acts when
strictly below correct) and plan-driven (reads _PLAN_SONG_CREDITS live), so
it is safe to run on every deploy indefinitely and automatically catches any
future allowance increase without a new per-user patch.
"""
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
os.environ.setdefault("JWT_SECRET", "test-secret-for-credit-backfill-tests")

import billing
import db


@pytest.fixture
def temp_db(tmp_path, monkeypatch):
    path = tmp_path / "test.db"
    db.init_user_tables(path)
    monkeypatch.setattr(db, "get_db_path", lambda: path)
    return path


def _make_subscriber(temp_db, email, plan, balance, monthly_allowance, status="active"):
    user = db.create_user(temp_db, email=email, password_hash="x", name="Test", tc_accepted_at="now")
    db.update_user(temp_db, user["id"], subscription_plan=plan, subscription_status=status, has_paid=1)
    db.upsert_song_credits(temp_db, user["id"], balance=balance, monthly_allowance=monthly_allowance)
    return user


def _credits_for(temp_db, email):
    user = db.get_user_by_email(temp_db, email)
    return db.get_song_credits(temp_db, user["id"])


def test_tops_up_a_stale_music_starter_subscriber_adding_the_shortfall(temp_db):
    """Matches the production tinayarowle/ebrown9042 case exactly: stuck at
    25, plan's real allowance is 30, balance must gain the 5-credit
    shortfall rather than being reset to 30."""
    _make_subscriber(temp_db, "tinayarowle@icloud.com", "music_starter", balance=5, monthly_allowance=25)

    corrections = billing.backfill_stale_plan_allowances(temp_db)

    assert len(corrections) == 1
    assert corrections[0]["email"] == "tinayarowle@icloud.com"
    assert corrections[0]["credited"] == 5
    credits = _credits_for(temp_db, "tinayarowle@icloud.com")
    assert credits["monthly_allowance"] == 30
    assert credits["balance"] == 10  # 5 + shortfall of 5, NOT reset to 30


def test_tops_up_a_stale_music_pro_subscriber(temp_db):
    """Matches the production review@zeusbeats.com case: stuck at 55, real
    allowance is 75, a 20-credit shortfall."""
    _make_subscriber(temp_db, "review@zeusbeats.com", "music_pro", balance=54, monthly_allowance=55)

    corrections = billing.backfill_stale_plan_allowances(temp_db)

    assert len(corrections) == 1
    assert corrections[0]["credited"] == 20
    credits = _credits_for(temp_db, "review@zeusbeats.com")
    assert credits["monthly_allowance"] == 75
    assert credits["balance"] == 74  # 54 + 20, NOT reset to 75


def test_corrects_multiple_stale_subscribers_across_different_plans_in_one_pass(temp_db):
    """The exact production scenario: three different stale accounts across
    two plans, fixed in a single call."""
    _make_subscriber(temp_db, "tinayarowle@icloud.com", "music_starter", balance=5, monthly_allowance=25)
    _make_subscriber(temp_db, "ebrown9042@gmail.com", "music_starter", balance=2, monthly_allowance=25)
    _make_subscriber(temp_db, "review@zeusbeats.com", "music_pro", balance=54, monthly_allowance=55)

    corrections = billing.backfill_stale_plan_allowances(temp_db)

    assert len(corrections) == 3
    assert _credits_for(temp_db, "tinayarowle@icloud.com")["balance"] == 10
    assert _credits_for(temp_db, "ebrown9042@gmail.com")["balance"] == 7
    assert _credits_for(temp_db, "review@zeusbeats.com")["balance"] == 74


def test_is_a_noop_for_a_subscriber_already_at_the_correct_allowance(temp_db):
    _make_subscriber(temp_db, "correct@example.com", "music_starter", balance=12, monthly_allowance=30)

    corrections = billing.backfill_stale_plan_allowances(temp_db)

    assert corrections == []
    credits = _credits_for(temp_db, "correct@example.com")
    assert credits["balance"] == 12
    assert credits["monthly_allowance"] == 30


def test_is_a_noop_for_a_subscriber_above_the_correct_allowance(temp_db):
    """A promo/manual grant that pushed someone above the plan default must
    never be clawed back by this backfill."""
    _make_subscriber(temp_db, "bonus@example.com", "music_starter", balance=100, monthly_allowance=40)

    corrections = billing.backfill_stale_plan_allowances(temp_db)

    assert corrections == []
    credits = _credits_for(temp_db, "bonus@example.com")
    assert credits["balance"] == 100
    assert credits["monthly_allowance"] == 40


def test_ignores_free_plan_users(temp_db):
    _make_subscriber(temp_db, "freeuser@example.com", "free", balance=3, monthly_allowance=0)

    corrections = billing.backfill_stale_plan_allowances(temp_db)

    assert corrections == []


def test_ignores_cancelled_subscribers_even_if_stale(temp_db):
    """A cancelled subscriber shouldn't be topped up -- they're not
    currently paying for the plan's allowance."""
    _make_subscriber(
        temp_db, "cancelled@example.com", "music_starter",
        balance=5, monthly_allowance=25, status="cancelled",
    )

    corrections = billing.backfill_stale_plan_allowances(temp_db)

    assert corrections == []
    credits = _credits_for(temp_db, "cancelled@example.com")
    assert credits["monthly_allowance"] == 25


def test_is_idempotent_running_twice_only_corrects_once(temp_db):
    _make_subscriber(temp_db, "tinayarowle@icloud.com", "music_starter", balance=5, monthly_allowance=25)

    first = billing.backfill_stale_plan_allowances(temp_db)
    second = billing.backfill_stale_plan_allowances(temp_db)

    assert len(first) == 1
    assert second == []
    assert _credits_for(temp_db, "tinayarowle@icloud.com")["balance"] == 10
