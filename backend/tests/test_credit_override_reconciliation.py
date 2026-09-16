"""One-off correction for the laky120@yahoo.com credit-cap incident (2026-09-16).

A leftover "one-time" startup patch in main.py hardcoded her song_credits to
monthly_allowance=25 / balance floored at 23 on EVERY deploy — not the 30 her
music_starter plan actually grants. It was never gated to run once, so it
silently re-clamped her account on every redeploy, contradicting Zeus Beats'
own "credits never expire" promise. billing.reconcile_stale_credit_override()
replaces that hardcoded patch: it only acts if the account is still stuck at
the exact stale value, and derives the correction from the CURRENT plan
config (_PLAN_SONG_CREDITS) rather than hardcoding a new magic number — so it
can't repeat the same class of mistake, and is safe to leave deployed
permanently (a no-op once corrected).
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
os.environ.setdefault("JWT_SECRET", "test-secret-for-credit-override-tests")

import billing
import db


@pytest.fixture
def temp_db(tmp_path, monkeypatch):
    path = tmp_path / "test.db"
    db.init_user_tables(path)
    monkeypatch.setattr(db, "get_db_path", lambda: path)
    return path


def _make_user(temp_db, email, plan, balance, monthly_allowance):
    user = db.create_user(temp_db, email=email, password_hash="x", name="Test", tc_accepted_at="now")
    db.update_user(temp_db, user["id"], subscription_plan=plan, subscription_status="active", has_paid=1)
    db.upsert_song_credits(temp_db, user["id"], balance=balance, monthly_allowance=monthly_allowance)
    return user


def test_reconciles_stale_override_to_the_plans_correct_allowance(temp_db):
    _make_user(temp_db, "laky120@yahoo.com", "music_starter", balance=23, monthly_allowance=25)

    corrected = billing.reconcile_stale_credit_override(temp_db, "laky120@yahoo.com", stale_allowance=25)

    assert corrected is True
    user = db.get_user_by_email(temp_db, "laky120@yahoo.com")
    credits = db.get_song_credits(temp_db, user["id"])
    assert credits["balance"] == 30
    assert credits["monthly_allowance"] == 30


def test_derives_the_target_from_the_current_plan_not_a_hardcoded_number(temp_db):
    """Same stale allowance, different plan -- proves the correction reads
    _PLAN_SONG_CREDITS rather than always writing 30."""
    _make_user(temp_db, "someone@example.com", "music_pro", balance=25, monthly_allowance=25)

    corrected = billing.reconcile_stale_credit_override(temp_db, "someone@example.com", stale_allowance=25)

    assert corrected is True
    user = db.get_user_by_email(temp_db, "someone@example.com")
    credits = db.get_song_credits(temp_db, user["id"])
    assert credits["balance"] == 75
    assert credits["monthly_allowance"] == 75


def test_is_a_noop_once_already_corrected(temp_db):
    """Safe to leave deployed permanently -- running it again after the fix
    already landed must not touch a correct balance."""
    _make_user(temp_db, "laky120@yahoo.com", "music_starter", balance=30, monthly_allowance=30)

    corrected = billing.reconcile_stale_credit_override(temp_db, "laky120@yahoo.com", stale_allowance=25)

    assert corrected is False
    user = db.get_user_by_email(temp_db, "laky120@yahoo.com")
    credits = db.get_song_credits(temp_db, user["id"])
    assert credits["balance"] == 30
    assert credits["monthly_allowance"] == 30


def test_is_a_noop_when_monthly_allowance_does_not_match_the_stale_value(temp_db):
    """Guards against ever matching an account that legitimately has whatever
    number is passed as stale_allowance for an unrelated reason."""
    _make_user(temp_db, "laky120@yahoo.com", "music_starter", balance=10, monthly_allowance=30)

    corrected = billing.reconcile_stale_credit_override(temp_db, "laky120@yahoo.com", stale_allowance=25)

    assert corrected is False
    user = db.get_user_by_email(temp_db, "laky120@yahoo.com")
    credits = db.get_song_credits(temp_db, user["id"])
    assert credits["balance"] == 10
    assert credits["monthly_allowance"] == 30


def test_is_a_noop_for_an_unknown_user(temp_db):
    corrected = billing.reconcile_stale_credit_override(temp_db, "nobody@example.com", stale_allowance=25)
    assert corrected is False


def test_is_a_noop_when_the_users_plan_has_no_configured_allowance(temp_db):
    """A free-plan (or unrecognised-plan) user must never be "corrected" into
    getting a paid plan's credits."""
    _make_user(temp_db, "freeuser@example.com", "free", balance=25, monthly_allowance=25)

    corrected = billing.reconcile_stale_credit_override(temp_db, "freeuser@example.com", stale_allowance=25)

    assert corrected is False
    user = db.get_user_by_email(temp_db, "freeuser@example.com")
    credits = db.get_song_credits(temp_db, user["id"])
    assert credits["balance"] == 25
    assert credits["monthly_allowance"] == 25
