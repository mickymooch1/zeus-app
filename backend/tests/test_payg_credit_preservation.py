"""PAYG (pay-as-you-go top-up) credits must never be wiped by subscription
renewal, new-subscription activation, or an admin-triggered plan change
(2026-09-17).

PAYG top-ups and subscription credits share one column, song_credits.balance
-- there is no separate PAYG ledger. Top-ups are added correctly
(db.increment_song_credits, additive). But three call sites RESET balance to
a flat plan allowance instead of topping it up:

  - billing._handle_invoice_paid       (automatic monthly renewal)
  - billing._handle_checkout_completed (new subscription activation)
  - telegram_admin._cmd_upgrade_user   (admin-triggered plan change)

Any of these firing while a customer has unspent PAYG credits on top of
their subscription balance would silently discard the PAYG credits.

Fix: billing._grant_or_preserve_song_credits(db_path, user_id, allowance)
sets monthly_allowance to the plan's number and raises balance to AT LEAST
that number -- balance = max(current_balance, allowance) -- never reduces
it. When current_balance <= allowance (the ordinary case, no PAYG on top)
this is identical to the old reset-to-allowance behavior, preserving the
already-confirmed "no rollover of unused subscription credits" decision.
When current_balance > allowance (PAYG credits, or any other extra grant),
the excess survives untouched.
"""
import os
import pathlib
import sys
from unittest.mock import patch

import pytest
import stripe

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))
os.environ.setdefault("ANTHROPIC_API_KEY", "test-key")
os.environ.setdefault("APIFRAME_API_KEY", "test-key")
os.environ.setdefault("SONG_STORAGE_PATH", "/tmp/test_songs")
os.environ.setdefault("SONG_PUBLIC_BASE_URL", "https://example.com/files/songs")
os.environ.setdefault("SONG_WEBHOOK_URL", "https://zeusaidesign.com/webhooks/apiframe")
os.environ.setdefault("JWT_SECRET", "test-secret-for-payg-preservation-tests")

import db
import billing
import telegram_admin


@pytest.fixture
def db_path(tmp_path):
    p = tmp_path / "t.db"
    db.init_user_tables(p)
    return p


def _bal(db_path, uid):
    c = db.get_song_credits(db_path, uid)
    return c["balance"] if c else 0


def _allowance(db_path, uid):
    c = db.get_song_credits(db_path, uid)
    return c["monthly_allowance"] if c else 0


# ── billing._grant_or_preserve_song_credits — the shared fix ────────────────

class TestGrantOrPreserveSongCredits:
    def test_preserves_a_balance_above_the_allowance(self, db_path):
        """The exact real-world scenario found live tonight: an enterprise
        subscriber (allowance 100) sitting on 124 after a legitimate PAYG-style
        top-up. A renewal must not claw that back down to 100."""
        user = db.create_user(db_path, "payg@test.com", "x", "PAYG", "2026-01-01")
        db.upsert_song_credits(db_path, user["id"], balance=124, monthly_allowance=100)

        billing._grant_or_preserve_song_credits(db_path, user["id"], allowance=100)

        assert _bal(db_path, user["id"]) == 124
        assert _allowance(db_path, user["id"]) == 100

    def test_resets_up_to_the_allowance_when_there_is_no_excess(self, db_path):
        """The ordinary case -- no PAYG on top -- must behave exactly like
        before: reset to the fresh allowance, not rollover the unused amount."""
        user = db.create_user(db_path, "ordinary@test.com", "x", "Ordinary", "2026-01-01")
        db.upsert_song_credits(db_path, user["id"], balance=1, monthly_allowance=30)

        billing._grant_or_preserve_song_credits(db_path, user["id"], allowance=30)

        assert _bal(db_path, user["id"]) == 30

    def test_handles_a_user_with_no_song_credits_row_yet(self, db_path):
        user = db.create_user(db_path, "fresh@test.com", "x", "Fresh", "2026-01-01")

        billing._grant_or_preserve_song_credits(db_path, user["id"], allowance=30)

        assert _bal(db_path, user["id"]) == 30
        assert _allowance(db_path, user["id"]) == 30


# ── _handle_invoice_paid (renewal) ──────────────────────────────────────────

def _make_stripe_event(event_type, obj):
    return stripe.Event.construct_from(
        {"id": "evt_test", "type": event_type, "data": {"object": obj}}, "sk_test",
    )


def _invoice(billing_reason="subscription_cycle", customer="cus_renew"):
    return {"id": "in_test", "object": "invoice", "customer": customer,
            "billing_reason": billing_reason, "amount_paid": 900}


class TestRenewalPreservesPayg:
    @pytest.fixture
    def subscriber_with_payg(self, db_path):
        with patch.object(db, "get_db_path", return_value=db_path):
            user = db.create_user(db_path, "renewer@test.com", "x", "Renewer", "2026-01-01")
            db.update_user(db_path, user["id"], stripe_customer_id="cus_renew",
                           subscription_plan="music_starter", subscription_status="active", has_paid=1)
            # 30 allowance + 20 unspent PAYG top-up sitting on top
            db.upsert_song_credits(db_path, user["id"], balance=50, monthly_allowance=30)
            yield user

    def test_renewal_does_not_touch_payg_credits_sitting_on_top(self, db_path, subscriber_with_payg):
        billing._handle_event(_make_stripe_event("invoice.paid", _invoice()))
        assert _bal(db_path, subscriber_with_payg["id"]) == 50

    def test_renewal_still_resets_to_allowance_with_no_payg(self, db_path):
        with patch.object(db, "get_db_path", return_value=db_path):
            user = db.create_user(db_path, "plain@test.com", "x", "Plain", "2026-01-01")
            db.update_user(db_path, user["id"], stripe_customer_id="cus_plain",
                           subscription_plan="music_starter", subscription_status="active", has_paid=1)
            db.upsert_song_credits(db_path, user["id"], balance=2, monthly_allowance=30)
            billing._handle_event(_make_stripe_event("invoice.paid", _invoice(customer="cus_plain")))
        assert _bal(db_path, user["id"]) == 30


# ── _handle_checkout_completed (new subscription activation) ───────────────

def _checkout_session(customer="cus_new", email="newsub@test.com", plan="music_starter"):
    return {
        "id": "cs_1", "object": "checkout.session", "mode": "subscription",
        "payment_status": "paid", "customer": customer, "customer_email": email,
        "subscription": "sub_1", "amount_total": 900, "currency": "gbp",
        "metadata": {"plan": plan, "user_id": ""},
    }


class TestActivationPreservesPayg:
    def test_subscribing_does_not_wipe_existing_payg_credits(self, db_path):
        """A free user who bought a PAYG top-up pack, then subscribes. Their
        leftover PAYG credits must not be discarded by the new subscription's
        flat allowance if the PAYG amount happens to exceed it."""
        user = db.create_user(db_path, "newsub@test.com", "x", "NewSub", "2026-01-01")
        db.upsert_song_credits(db_path, user["id"], balance=40, monthly_allowance=0)  # 40 PAYG credits

        billing._handle_checkout_completed(db_path, _checkout_session())  # music_starter allowance=30

        assert _bal(db_path, user["id"]) == 40

    def test_activation_still_grants_the_full_allowance_with_no_prior_credits(self, db_path):
        user = db.create_user(db_path, "brandnew@test.com", "x", "BrandNew", "2026-01-01")

        billing._handle_checkout_completed(db_path, _checkout_session(customer="cus_bn", email="brandnew@test.com"))

        assert _bal(db_path, user["id"]) == 30


# ── telegram_admin._cmd_upgrade_user (admin-triggered plan change) ─────────

class TestAdminUpgradePreservesPayg:
    def test_admin_upgrade_does_not_wipe_existing_payg_credits(self, db_path, monkeypatch):
        monkeypatch.setattr(db, "get_db_path", lambda: db_path)
        user = db.create_user(db_path, "adminupgrade@test.com", "x", "AdminUpgrade", "2026-01-01")
        db.upsert_song_credits(db_path, user["id"], balance=60, monthly_allowance=0)  # 60 PAYG credits

        telegram_admin._cmd_upgrade_user("adminupgrade@test.com", "music_starter")  # allowance=30

        assert _bal(db_path, user["id"]) == 60

    def test_admin_upgrade_still_grants_the_full_allowance_with_no_prior_credits(self, db_path, monkeypatch):
        monkeypatch.setattr(db, "get_db_path", lambda: db_path)
        user = db.create_user(db_path, "adminfresh@test.com", "x", "AdminFresh", "2026-01-01")

        telegram_admin._cmd_upgrade_user("adminfresh@test.com", "music_starter")

        assert _bal(db_path, user["id"]) == 30
