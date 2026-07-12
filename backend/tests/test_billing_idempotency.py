import os
import pathlib
import sys

import pytest

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))
os.environ.setdefault("ANTHROPIC_API_KEY", "test-key-for-tests")

import db
import billing


@pytest.fixture
def db_path(tmp_path):
    p = tmp_path / "t.db"
    db.init_user_tables(p)
    return p


@pytest.fixture
def user(db_path):
    return db.create_user(db_path, "buyer@test.com", "x", "Buyer", "2026-01-01")


def _session(pi="pi_1", pack="song_pack_099", email="buyer@test.com"):
    return {
        "id": "cs_1", "object": "checkout.session", "mode": "payment",
        "payment_status": "paid", "customer": "cus_1", "customer_email": email,
        "payment_intent": pi, "amount_total": 99, "currency": "gbp",
        "metadata": {"song_pack": pack, "user_id": ""},
    }


def _bal(db_path, uid):
    c = db.get_song_credits(db_path, uid)
    return c["balance"] if c else 0


class TestTopupIdempotency:
    def test_checkout_topup_grants_and_records_ledger(self, db_path, user):
        billing._handle_checkout_completed(db_path, _session())
        assert _bal(db_path, user["id"]) == 2
        grant = db.get_credit_grant(db_path, "pi_1", "song")
        assert grant is not None
        assert grant["amount"] == 2
        assert grant["user_id"] == user["id"]

    def test_replayed_checkout_does_not_double_grant(self, db_path, user):
        billing._handle_checkout_completed(db_path, _session())
        billing._handle_checkout_completed(db_path, _session())  # Stripe retry, same pi
        assert _bal(db_path, user["id"]) == 2

    def test_checkout_topup_sets_has_paid(self, db_path, user):
        # PAYG purchases must flip has_paid=1 too (not just subscriptions) — a fresh
        # user starts at 0; the crashed 07-03 webhook is why cummins.anne stayed 0.
        assert not db.get_user_by_id(db_path, user["id"]).get("has_paid")
        billing._handle_checkout_completed(db_path, _session())
        assert db.get_user_by_id(db_path, user["id"])["has_paid"] == 1

    def test_payment_intent_backup_topup_sets_has_paid(self, db_path, user):
        pi = {
            "id": "pi_pay", "object": "payment_intent", "customer": "cus_1",
            "metadata": {"song_pack": "song_pack_099", "user_id": user["id"]},
        }
        billing._handle_payment_intent_succeeded(db_path, pi)
        assert db.get_user_by_id(db_path, user["id"])["has_paid"] == 1

    def test_payment_intent_backup_after_checkout_no_double_grant(self, db_path, user):
        # The Apple-Pay overlap: checkout.session.completed AND payment_intent.succeeded
        # both fire for the same payment_intent id.
        billing._handle_checkout_completed(db_path, _session(pi="pi_9"))
        pi = {
            "id": "pi_9", "object": "payment_intent", "customer": "cus_1",
            "metadata": {"song_pack": "song_pack_099", "user_id": user["id"]},
        }
        billing._handle_payment_intent_succeeded(db_path, pi)
        assert _bal(db_path, user["id"]) == 2


class TestPaygSuccessAlert:
    def test_successful_checkout_topup_fires_payg_alert(self, db_path, user, monkeypatch):
        calls = []
        monkeypatch.setattr(billing._alerts, "alert_payg_purchase",
                            lambda *a, **k: calls.append((a, k)))
        billing._handle_checkout_completed(db_path, _session())
        assert len(calls) == 1

    def test_payment_intent_topup_fires_payg_alert(self, db_path, user, monkeypatch):
        calls = []
        monkeypatch.setattr(billing._alerts, "alert_payg_purchase",
                            lambda *a, **k: calls.append((a, k)))
        pi = {
            "id": "pi_pay2", "object": "payment_intent", "customer": "cus_1", "amount": 99,
            "metadata": {"song_pack": "song_pack_099", "user_id": user["id"]},
        }
        billing._handle_payment_intent_succeeded(db_path, pi)
        assert len(calls) == 1

    def test_duplicate_topup_does_not_fire_payg_alert(self, db_path, user, monkeypatch):
        billing._handle_checkout_completed(db_path, _session())  # first grant
        calls = []
        monkeypatch.setattr(billing._alerts, "alert_payg_purchase",
                            lambda *a, **k: calls.append((a, k)))
        billing._handle_checkout_completed(db_path, _session())  # replay — no new grant
        assert len(calls) == 0


class TestCreditFailureAlert:
    def test_user_not_found_triggers_alert(self, db_path, monkeypatch):
        calls = []
        monkeypatch.setattr(
            billing._alerts, "alert_credit_not_granted",
            lambda *a, **k: calls.append((a, k)),
        )
        billing._handle_checkout_completed(db_path, _session(email="ghost@nope.com"))
        assert len(calls) == 1

    def test_payment_intent_user_not_found_triggers_alert(self, db_path, monkeypatch):
        calls = []
        monkeypatch.setattr(
            billing._alerts, "alert_credit_not_granted",
            lambda *a, **k: calls.append((a, k)),
        )
        pi = {
            "id": "pi_x", "object": "payment_intent", "customer": "cus_none",
            "metadata": {"song_pack": "song_pack_099", "user_id": "nobody"},
        }
        billing._handle_payment_intent_succeeded(db_path, pi)
        assert len(calls) == 1
