import pathlib
import sys

import pytest

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))

import db


@pytest.fixture
def db_path(tmp_path):
    path = tmp_path / "test_zeus.db"
    db.init_user_tables(path)
    return path


class TestRecordCreditGrant:
    def test_new_grant_is_recorded_and_returns_true(self, db_path):
        newly = db.record_credit_grant(
            db_path, "u1", "a@b.com", "song", 2, "checkout_topup", "pi_123"
        )
        assert newly is True
        row = db.get_credit_grant(db_path, "pi_123", "song")
        assert row is not None
        assert row["user_id"] == "u1"
        assert row["email"] == "a@b.com"
        assert row["credit_type"] == "song"
        assert row["amount"] == 2
        assert row["source"] == "checkout_topup"
        assert row["created_at"]

    def test_duplicate_payment_and_type_returns_false_no_second_row(self, db_path):
        # Same purchase arriving twice (e.g. checkout then payment_intent backup, or a
        # Stripe delivery retry) — keyed on payment_intent id + credit_type.
        assert db.record_credit_grant(
            db_path, "u1", "a@b.com", "song", 2, "checkout_topup", "pi_123"
        ) is True
        assert db.record_credit_grant(
            db_path, "u1", "a@b.com", "song", 2, "payment_intent_topup", "pi_123"
        ) is False

    def test_same_payment_different_credit_type_both_recorded(self, db_path):
        assert db.record_credit_grant(
            db_path, "u1", "a@b.com", "song", 2, "checkout_topup", "pi_123"
        ) is True
        assert db.record_credit_grant(
            db_path, "u1", "a@b.com", "premium", 1, "checkout_topup", "pi_123"
        ) is True

    def test_get_credit_grant_missing_returns_none(self, db_path):
        assert db.get_credit_grant(db_path, "pi_absent", "song") is None
