import os, pathlib, sys
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


def _memorial_session(pi="pi_mem_1", email="buyer@test.com"):
    return {
        "id": "cs_mem_1", "object": "checkout.session", "mode": "payment",
        "payment_status": "paid", "customer": "cus_1", "customer_email": email,
        "payment_intent": pi, "amount_total": 4900, "currency": "gbp",
        "metadata": {"memorial_package": "memorial_default", "user_id": ""},
    }


def _memorial_balance(db_path, uid):
    return db.get_user_by_id(db_path, uid)["memorial_credits_available"]


class TestMemorialTopupIdempotency:
    def test_checkout_grants_and_records_ledger(self, db_path, user):
        billing._handle_checkout_completed(db_path, _memorial_session())
        assert _memorial_balance(db_path, user["id"]) == 1
        grant = db.get_credit_grant(db_path, "pi_mem_1", "memorial")
        assert grant is not None
        assert grant["amount"] == 1

    def test_replayed_checkout_does_not_double_grant(self, db_path, user):
        billing._handle_checkout_completed(db_path, _memorial_session())
        billing._handle_checkout_completed(db_path, _memorial_session())
        assert _memorial_balance(db_path, user["id"]) == 1

    def test_payment_intent_backup_after_checkout_no_double_grant(self, db_path, user):
        billing._handle_checkout_completed(db_path, _memorial_session(pi="pi_mem_9"))
        pi = {"id": "pi_mem_9", "object": "payment_intent", "customer": "cus_1",
              "metadata": {"memorial_package": "memorial_default", "user_id": user["id"]}}
        billing._handle_payment_intent_succeeded(db_path, pi)
        assert _memorial_balance(db_path, user["id"]) == 1

    def test_payment_intent_alone_grants_when_checkout_never_fired(self, db_path, user):
        pi = {"id": "pi_mem_10", "object": "payment_intent", "customer": "cus_1",
              "metadata": {"memorial_package": "memorial_default", "user_id": user["id"]}}
        billing._handle_payment_intent_succeeded(db_path, pi)
        assert _memorial_balance(db_path, user["id"]) == 1

    def test_unrecognised_memorial_pack_does_not_crash_and_alerts(self, db_path, user, monkeypatch):
        called = {}
        monkeypatch.setattr(billing._alerts, "alert_credit_not_granted", lambda *a, **kw: called.setdefault("fired", True))
        session = _memorial_session()
        session["metadata"]["memorial_package"] = "nonexistent_pack"
        billing._handle_checkout_completed(db_path, session)
        assert _memorial_balance(db_path, user["id"]) == 0
        assert called.get("fired") is True
