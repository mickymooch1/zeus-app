"""invoice.paid is what Stripe actually sends on this account — dispatch had only
ever checked invoice.payment_succeeded, a different event name.

Found live, 2026-09-02, via ebrown9042@gmail.com's Music Starter purchase:
evt_1UB0XpK5Ou7aVaHMtRjC8OFV (type=invoice.paid) arrived, verified, returned
200 OK, and fell straight into "event type is not handled — no action taken".
No error, no alert — a webhook working exactly as coded, coded wrong.

Two things this file has to nail down, because either one alone would have
still left this customer with no credits even with the dispatch fixed:

  1. invoice.paid must actually reach _handle_invoice_paid.
  2. _handle_invoice_paid only fires on billing_reason == "subscription_cycle"
     (a RENEWAL). This customer's invoice was billing_reason=subscription_create
     (the FIRST invoice) — confirmed directly against the real Stripe invoice —
     so this handler was never going to provision him, dispatch bug or not.
     Initial provisioning is checkout.session.completed's job, a separate and
     also-broken piece of this incident (the webhook endpoint's enabled-events
     list is missing that event type entirely — a Stripe dashboard fix, not a
     code fix, tracked outside this file).
"""
import os
import pathlib
import sys

import pytest

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))
os.environ.setdefault("ANTHROPIC_API_KEY", "test-key-for-tests")

from unittest.mock import patch  # noqa: E402

import stripe  # noqa: E402
import db  # noqa: E402
import billing  # noqa: E402


def _make_stripe_event(event_type, obj):
    """Same shape stripe.Webhook.construct_event returns in production — a
    StripeObject, not a plain dict. Matches test_billing_webhook.py."""
    return stripe.Event.construct_from(
        {"id": "evt_test_invoice", "type": event_type, "data": {"object": obj}},
        "sk_test",
    )


@pytest.fixture
def db_path(tmp_path):
    p = tmp_path / "t.db"
    db.init_user_tables(p)
    # _handle_event (unlike the lower-level handlers) resolves db.get_db_path()
    # itself rather than taking db_path as an argument — without this patch every
    # test in this file silently queries whatever the real default path is instead
    # of the fixture, and "no user for customer_id" looks identical to the dispatch
    # bug this file exists to catch. Autouse per-file so no test can forget it.
    with patch.object(db, "get_db_path", return_value=p):
        yield p


@pytest.fixture
def subscriber(db_path):
    """A user already on a paid plan — i.e. checkout.session.completed already
    ran. This is the RENEWAL fixture; _handle_invoice_paid is never the thing
    that sets subscription_plan in the first place."""
    user = db.create_user(db_path, "renewer@test.com", "x", "Renewer", "2026-01-01")
    db.update_user(db_path, user["id"], stripe_customer_id="cus_renew",
                   subscription_plan="music_starter", subscription_status="active",
                   has_paid=1)
    db.upsert_song_credits(db_path, user["id"], balance=1, monthly_allowance=25)
    return user


def _invoice(billing_reason="subscription_cycle", customer="cus_renew"):
    return {
        "id": "in_test", "object": "invoice", "customer": customer,
        "billing_reason": billing_reason, "amount_paid": 900,
    }


def _bal(db_path, uid):
    c = db.get_song_credits(db_path, uid)
    return c["balance"] if c else 0


class TestInvoicePaidDispatch:
    def test_invoice_paid_resets_monthly_credits(self, db_path, subscriber):
        """The exact event type confirmed arriving in production."""
        event = _make_stripe_event("invoice.paid", _invoice())
        billing._handle_event(event)
        assert _bal(db_path, subscriber["id"]) == 25, (
            "invoice.paid must reach _handle_invoice_paid and reset the balance "
            "to the plan's monthly allowance"
        )

    def test_legacy_invoice_payment_succeeded_still_works(self, db_path, subscriber):
        """Kept as a harmless alias rather than replaced outright — some Stripe
        API versions/accounts still emit both events for the same invoice, and
        this handler resets to a fixed value rather than incrementing, so a
        duplicate call is a no-op, not a double-grant."""
        event = _make_stripe_event("invoice.payment_succeeded", _invoice())
        billing._handle_event(event)
        assert _bal(db_path, subscriber["id"]) == 25

    def test_both_events_for_the_same_invoice_do_not_double_grant(self, db_path, subscriber):
        billing._handle_event(_make_stripe_event("invoice.paid", _invoice()))
        billing._handle_event(_make_stripe_event("invoice.payment_succeeded", _invoice()))
        assert _bal(db_path, subscriber["id"]) == 25, (
            "reset-to-fixed-value must be idempotent across both event names"
        )

    def test_first_invoice_is_correctly_skipped_not_a_dispatch_bug(self, db_path, subscriber):
        """billing_reason=subscription_create is the FIRST invoice. Confirmed
        against the real Stripe invoice for this incident. Even with dispatch
        fixed, this handler must still decline to act — initial provisioning
        belongs to checkout.session.completed, not here. If this ever granted
        credits it would double-grant on top of _handle_checkout_completed."""
        db.upsert_song_credits(db_path, subscriber["id"], balance=1, monthly_allowance=25)
        event = _make_stripe_event("invoice.paid", _invoice(billing_reason="subscription_create"))
        billing._handle_event(event)
        assert _bal(db_path, subscriber["id"]) == 1, "must not touch balance on the first invoice"

    def test_unknown_customer_alerts_rather_than_silently_dropping(self, db_path, monkeypatch):
        calls = []
        monkeypatch.setattr(billing._alerts, "alert_credit_not_granted",
                            lambda *a, **k: calls.append((a, k)))
        event = _make_stripe_event("invoice.paid", _invoice(customer="cus_ghost"))
        billing._handle_event(event)
        assert len(calls) == 1

    def test_invoice_paid_is_in_handled_events(self):
        """Drives the 'handled=%s' log flag Railway is greped against — without
        this, a correctly-processed renewal still logs as if it were dropped."""
        assert "invoice.paid" in billing._HANDLED_EVENTS
