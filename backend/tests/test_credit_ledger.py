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


class TestGetRecentCreditGrant:
    def test_finds_recent_matching_grant(self, db_path):
        db.record_credit_grant(db_path, "u1", "a@b.com", "song", 10, "manual", "manual:admin:t1")
        g = db.get_recent_credit_grant(db_path, "u1", "song", 10, within_hours=24)
        assert g is not None and g["amount"] == 10 and g["source"] == "manual"

    def test_matches_across_sources_incl_webhook(self, db_path):
        # A prior WEBHOOK grant must also be seen (so a manual grant after a webhook warns).
        db.record_credit_grant(db_path, "u1", "a@b.com", "song", 2, "checkout_topup", "pi_1")
        assert db.get_recent_credit_grant(db_path, "u1", "song", 2, within_hours=24) is not None

    def test_none_when_amount_differs(self, db_path):
        db.record_credit_grant(db_path, "u1", "a@b.com", "song", 10, "manual", "r1")
        assert db.get_recent_credit_grant(db_path, "u1", "song", 5, within_hours=24) is None

    def test_none_when_type_differs(self, db_path):
        db.record_credit_grant(db_path, "u1", "a@b.com", "song", 10, "manual", "r1")
        assert db.get_recent_credit_grant(db_path, "u1", "premium", 10, within_hours=24) is None

    def test_none_when_user_differs(self, db_path):
        db.record_credit_grant(db_path, "u1", "a@b.com", "song", 10, "manual", "r1")
        assert db.get_recent_credit_grant(db_path, "u2", "song", 10, within_hours=24) is None

    def test_none_when_older_than_window(self, db_path):
        import sqlite3
        conn = sqlite3.connect(str(db_path))
        conn.execute(
            "INSERT INTO credit_ledger (user_id,email,credit_type,amount,source,stripe_payment_id,created_at) "
            "VALUES (?,?,?,?,?,?,?)",
            ("u1", "a@b.com", "song", 10, "manual", "old_ref", "2020-01-01T00:00:00+00:00"),
        )
        conn.commit()
        conn.close()
        assert db.get_recent_credit_grant(db_path, "u1", "song", 10, within_hours=24) is None
        # a very wide window does find it
        assert db.get_recent_credit_grant(db_path, "u1", "song", 10, within_hours=24 * 365 * 100) is not None
