import os
import pathlib
import sys

import pytest

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))
os.environ.setdefault("ANTHROPIC_API_KEY", "test-key-for-tests")

import db
import telegram_admin as ta


@pytest.fixture
def db_path(tmp_path, monkeypatch):
    p = tmp_path / "t.db"
    db.init_user_tables(p)
    # _cmd_db_credits resolves the path internally via db.get_db_path()
    monkeypatch.setattr(db, "get_db_path", lambda: p)
    return p


@pytest.fixture
def user(db_path):
    return db.create_user(db_path, "buyer@test.com", "x", "Buyer", "2026-01-01")


def _bal(db_path, uid):
    c = db.get_song_credits(db_path, uid)
    return c["balance"] if c else 0


class TestManualGrantLedger:
    def test_grant_writes_manual_ledger_row(self, db_path, user):
        res = ta._cmd_db_credits("buyer@test.com", 10, admin="999")
        assert "✅" in res
        row = db.get_recent_credit_grant(db_path, user["id"], "song", 10, within_hours=24)
        assert row is not None
        assert row["source"] == "manual"
        assert row["stripe_payment_id"].startswith("manual:999:")

    def test_duplicate_within_window_warns_and_does_not_grant(self, db_path, user):
        ta._cmd_db_credits("buyer@test.com", 10, admin="999")
        bal = _bal(db_path, user["id"])
        res2 = ta._cmd_db_credits("buyer@test.com", 10, admin="999")
        assert "⚠️" in res2
        assert "yes" in res2.lower()
        assert _bal(db_path, user["id"]) == bal  # NOT granted again

    def test_force_grants_despite_duplicate(self, db_path, user):
        ta._cmd_db_credits("buyer@test.com", 10, admin="999")
        b1 = _bal(db_path, user["id"])
        res2 = ta._cmd_db_credits("buyer@test.com", 10, admin="999", force=True)
        assert "✅" in res2
        assert _bal(db_path, user["id"]) == b1 + 10

    def test_different_amount_not_flagged(self, db_path, user):
        ta._cmd_db_credits("buyer@test.com", 10, admin="999")
        res2 = ta._cmd_db_credits("buyer@test.com", 5, admin="999")
        assert "✅" in res2  # 5 != 10, no warning

    def test_negative_delta_not_guarded_and_no_ledger(self, db_path, user):
        ta._cmd_db_credits("buyer@test.com", 10, admin="999", force=True)
        res = ta._cmd_db_credits("buyer@test.com", -5, admin="999")
        assert "✅" in res
        # removal must not create a "grant" ledger row for -5
        assert db.get_recent_credit_grant(db_path, user["id"], "song", -5, within_hours=24) is None

    def test_manual_grant_seen_by_webhook_style_duplicate_check(self, db_path, user):
        # A webhook grant lands first (in ledger); a matching manual grant then warns.
        db.record_credit_grant(db_path, user["id"], user["email"], "song", 2, "checkout_topup", "pi_abc")
        res = ta._cmd_db_credits("buyer@test.com", 2, admin="999")
        assert "⚠️" in res
