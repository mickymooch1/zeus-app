"""Porick's check_transaction chat tool (telegram_admin.py): does a purchase
or subscription actually go through -- checking BOTH the real Stripe payment
status and whether the corresponding credits/subscription state landed in
our own database, reported separately so a mismatch between the two is
never hidden. Wired into the AI action-routing layer the same way
check_deploy_status/check_incidents already are.

Stripe is stood in with REAL stripe.Charge SDK objects (via
stripe.Charge.construct_from(...), the library's own documented way to
build one from a plain dict without a network call) -- never plain
dicts. This matters: a stripe.Charge is NOT dict-like in the installed
stripe-python -- ch.get(...) raises "AttributeError: 'get' is a dict
method, but a Charge is not a dict", and every plain-dict-mocked test in
an earlier version of this file happily let .get()-based production code
ship completely broken (2026-09-13 incident: check_transaction crashed
with an unhandled 500 on every real call). construct_from() is what
closes that gap -- it fails the exact same way a real Charge does if
production code ever regresses to .get().
"""
import os
import pathlib
import sys
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import patch

import pytest
import stripe as stripe_lib

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))
os.environ.setdefault("ANTHROPIC_API_KEY", "test-key")
os.environ.setdefault("APIFRAME_API_KEY", "test-key")
os.environ.setdefault("SONG_STORAGE_PATH", "/tmp/test_songs")
os.environ.setdefault("SONG_PUBLIC_BASE_URL", "https://example.com/files/songs")
os.environ.setdefault("SONG_WEBHOOK_URL", "https://zeusaidesign.com/webhooks/apiframe")
os.environ.setdefault("JWT_SECRET", "test-secret-for-check-transaction-tests")
os.environ.setdefault("STRIPE_SECRET_KEY", "sk_test_should_never_appear_in_any_reply")

import billing
import db
import telegram_admin as ta

_NOW = datetime.now(timezone.utc)


@pytest.fixture
def temp_db(tmp_path, monkeypatch):
    path = tmp_path / "test.db"
    db.init_user_tables(path)
    monkeypatch.setattr(db, "get_db_path", lambda: path)
    return path


def _make_user(temp_db, email, customer_id=None, **extra_fields):
    user = db.create_user(temp_db, email=email, password_hash="x", name="U", tc_accepted_at="n")
    fields = {"stripe_customer_id": customer_id, **extra_fields} if customer_id else extra_fields
    if fields:
        db.update_user(temp_db, user["id"], **fields)
    return db.get_user_by_id(temp_db, user["id"])


def _charge(*, id="ch_1", payment_intent="pi_1", amount=999, created=None, status="succeeded",
            paid=True, refunded=False, customer=None, invoice=None, email=None,
            card_last4="4242", card_brand="visa", secret_marker="sk_live_should_never_leak_ABCDEF123456"):
    """A REAL stripe.Charge SDK object -- constructed via the library's own
    construct_from(), not a plain dict, so a test using it exercises the
    exact same attribute-access behaviour (and the exact same failure mode
    if production code regresses to .get()) as a real API response.
    Includes payment_method_details and a fake secret-shaped string so
    tests can assert they never reach the reply.
    """
    created = created if created is not None else int(_NOW.timestamp())
    data = {
        "id": id,
        "object": "charge",
        "payment_intent": payment_intent,
        "amount": amount,
        "created": created,
        "status": status,
        "paid": paid,
        "refunded": refunded,
        "customer": customer,
        "invoice": invoice,
        "billing_details": {"email": email},
        "payment_method_details": {
            "card": {"last4": card_last4, "brand": card_brand, "exp_month": 1, "exp_year": 2030}
        },
        "description": f"internal note containing {secret_marker}",
    }
    return stripe_lib.Charge.construct_from(data, "sk_test_fake_key_for_construct_from")


class _FakeChargeList:
    def __init__(self, charges):
        self._charges = charges

    def auto_paging_iter(self):
        return iter(self._charges)


def _mock_stripe(monkeypatch, charges):
    """Real Stripe filters server-side by `customer` and `created` -- this
    fake must too, or a test could wrongly "leak" another customer's charge
    that a real API call would never have returned in the first place.
    Uses getattr (not .get()) since `charges` are real Charge objects."""
    def _list(**kwargs):
        result = charges
        customer = kwargs.get("customer")
        if customer:
            result = [c for c in result if getattr(c, "customer", None) == customer]
        gte = (kwargs.get("created") or {}).get("gte")
        if gte is not None:
            result = [c for c in result if getattr(c, "created", 0) >= gte]
        return _FakeChargeList(result)

    fake_stripe = SimpleNamespace(Charge=SimpleNamespace(list=_list))
    monkeypatch.setattr(billing, "_get_stripe", lambda: fake_stripe)
    return fake_stripe


# ── Regression guard: real Stripe SDK objects are not dict-like ────────────
#
# 2026-09-13 incident: every real check_transaction call crashed with an
# unhandled 500 ("AttributeError: 'get' is a dict method, but a Charge is
# not a dict") because the code used ch.get(...) on a real stripe.Charge.
# Every test in this file builds charges via _charge() -> stripe.Charge.
# construct_from(...), a REAL SDK object, specifically so this class of bug
# can never hide behind a plain-dict mock again. This test makes that
# guarantee explicit and self-documenting rather than merely implicit.

def test_charge_fixture_is_a_real_stripe_object_not_dict_like():
    charge = _charge()
    assert isinstance(charge, stripe_lib.StripeObject)
    assert not isinstance(charge, dict)
    with pytest.raises(AttributeError):
        charge.get("paid")  # the exact call that crashed production
    # Real attribute access (what the fixed code actually uses) works fine.
    assert charge.paid is True
    assert charge.status == "succeeded"


def test_check_transaction_survives_a_real_charge_end_to_end(temp_db, monkeypatch):
    """Would have raised the production AttributeError before the fix --
    now must return a normal, well-formed result."""
    charges = [_charge(id="ch_1", payment_intent="pi_real", email="rex@example.com", customer="cus_rex")]
    _mock_stripe(monkeypatch, charges)
    rex = _make_user(temp_db, "rex@example.com", customer_id="cus_rex")
    db.record_credit_grant(temp_db, rex["id"], "rex@example.com", "song", 10, "checkout_topup", "pi_real")

    result = ta._cmd_check_transaction(email="rex@example.com")

    assert "❌" not in result
    assert "Payment: succeeded" in result
    assert "Credits: landed (+10 song)" in result


# ── Input validation ─────────────────────────────────────────────────────────

def test_requires_at_least_one_of_email_user_id_since():
    result = ta._cmd_check_transaction()
    assert "❓" in result
    assert "email" in result.lower() or "user id" in result.lower() or "time window" in result.lower()


def test_a_bug_that_crashes_reports_a_plain_error_not_a_raw_crash(temp_db, monkeypatch):
    """Whatever goes wrong inside check_transaction, the admin must always
    get a plain reply -- never a swallowed exception with no Telegram
    message at all (the actual production symptom on 2026-09-13: three
    unhandled 500s, three requests where Porick never replied)."""
    monkeypatch.setattr(ta, "_check_transaction_impl",
                         lambda *a, **kw: (_ for _ in ()).throw(RuntimeError("boom, unexpected bug")))

    result = ta._cmd_check_transaction(since="2h")

    assert result.startswith("❌")
    assert "boom, unexpected bug" in result


# ── since-window lookup with no email/user_id ───────────────────────────────

def test_since_window_lookup_with_no_email_returns_recent_matches(temp_db, monkeypatch):
    """"all PAYG purchases in the last 2 hours" -- no specific person named."""
    charges = [
        _charge(id="ch_1", payment_intent="pi_1", email="alice@example.com", customer="cus_alice"),
        _charge(id="ch_2", payment_intent="pi_2", email="bob@example.com", customer="cus_bob"),
    ]
    _mock_stripe(monkeypatch, charges)
    alice = _make_user(temp_db, "alice@example.com", customer_id="cus_alice")
    db.record_credit_grant(temp_db, alice["id"], "alice@example.com", "song", 10, "checkout_topup", "pi_1")
    bob = _make_user(temp_db, "bob@example.com", customer_id="cus_bob")
    db.record_credit_grant(temp_db, bob["id"], "bob@example.com", "song", 10, "checkout_topup", "pi_2")

    result = ta._cmd_check_transaction(since="2h")

    assert "alice@example.com" in result
    assert "bob@example.com" in result
    assert "2 matching transaction" in result


def test_since_window_only_scopes_by_time_not_by_customer(temp_db, monkeypatch):
    """No email/user_id given -> the Stripe query must not be scoped to any
    single customer (that would silently miss everyone else's transactions
    in the window)."""
    charges = [_charge(id="ch_1", payment_intent="pi_1", email="carol@example.com", customer="cus_carol")]
    fake_stripe = _mock_stripe(monkeypatch, charges)
    captured_kwargs = {}
    fake_stripe.Charge.list = lambda **kw: captured_kwargs.update(kw) or _FakeChargeList(charges)
    carol = _make_user(temp_db, "carol@example.com", customer_id="cus_carol")
    db.record_credit_grant(temp_db, carol["id"], "carol@example.com", "song", 5, "checkout_topup", "pi_1")

    ta._cmd_check_transaction(since="2h")

    assert "customer" not in captured_kwargs


# ── Payment succeeded but credits missing: the mismatch case ────────────────

def test_payment_succeeded_but_credits_missing_is_flagged_as_a_mismatch(temp_db, monkeypatch):
    charges = [_charge(id="ch_1", payment_intent="pi_missing", email="dana@example.com", customer="cus_dana", status="succeeded", paid=True)]
    _mock_stripe(monkeypatch, charges)
    _make_user(temp_db, "dana@example.com", customer_id="cus_dana")
    # Deliberately no db.record_credit_grant call -- credits never landed.

    result = ta._cmd_check_transaction(email="dana@example.com")

    assert "Payment: succeeded" in result
    assert "Credits: NOT found" in result
    assert "mismatch" in result.lower()


def test_payment_succeeded_and_credits_landed_reports_both_clearly(temp_db, monkeypatch):
    charges = [_charge(id="ch_1", payment_intent="pi_landed", email="erin@example.com", customer="cus_erin")]
    _mock_stripe(monkeypatch, charges)
    erin = _make_user(temp_db, "erin@example.com", customer_id="cus_erin")
    db.record_credit_grant(temp_db, erin["id"], "erin@example.com", "song", 10, "checkout_topup", "pi_landed")

    result = ta._cmd_check_transaction(email="erin@example.com")

    assert "Payment: succeeded" in result
    assert "Credits: landed (+10 song)" in result
    assert "mismatch" not in result.lower()


def test_subscription_active_reports_landed(temp_db, monkeypatch):
    charges = [_charge(id="ch_1", payment_intent="pi_sub", email="fay@example.com",
                        customer="cus_fay", invoice="in_1")]
    _mock_stripe(monkeypatch, charges)
    _make_user(temp_db, "fay@example.com", customer_id="cus_fay",
               subscription_status="active", subscription_plan="music_starter", has_paid=1)

    result = ta._cmd_check_transaction(email="fay@example.com")

    assert "Payment: succeeded" in result
    assert "Subscription: active" in result
    assert "music_starter" in result


def test_subscription_not_active_is_flagged_as_mismatch(temp_db, monkeypatch):
    charges = [_charge(id="ch_1", payment_intent="pi_sub2", email="gary@example.com",
                        customer="cus_gary", invoice="in_2")]
    _mock_stripe(monkeypatch, charges)
    _make_user(temp_db, "gary@example.com", customer_id="cus_gary",
               subscription_status="free", has_paid=0)

    result = ta._cmd_check_transaction(email="gary@example.com")

    assert "Subscription: NOT active" in result
    assert "mismatch" in result.lower()


def test_failed_payment_reports_its_own_real_status_not_succeeded(temp_db, monkeypatch):
    charges = [_charge(id="ch_1", payment_intent="pi_failed", email="quinn@example.com",
                        customer="cus_quinn", status="failed", paid=False)]
    _mock_stripe(monkeypatch, charges)
    _make_user(temp_db, "quinn@example.com", customer_id="cus_quinn")

    result = ta._cmd_check_transaction(email="quinn@example.com")

    assert "Payment: failed" in result
    assert "Payment: succeeded" not in result


# ── No-match case ────────────────────────────────────────────────────────────

def test_no_matching_transactions_says_so_plainly(temp_db, monkeypatch):
    _mock_stripe(monkeypatch, [])
    _make_user(temp_db, "hank@example.com", customer_id="cus_hank")

    result = ta._cmd_check_transaction(email="hank@example.com")

    assert "📭" in result
    assert "no matching transactions" in result.lower()


def test_no_matching_transactions_in_a_time_window_says_so_plainly(temp_db, monkeypatch):
    _mock_stripe(monkeypatch, [])
    result = ta._cmd_check_transaction(since="30m")
    assert "no matching transactions" in result.lower()


def test_unknown_user_says_so_rather_than_querying_stripe_blind(temp_db, monkeypatch):
    fake_stripe = _mock_stripe(monkeypatch, [])
    result = ta._cmd_check_transaction(email="nobody@example.com")
    assert "📭" in result
    assert "no user found" in result.lower()


def test_user_with_no_stripe_customer_says_so(temp_db, monkeypatch):
    _mock_stripe(monkeypatch, [])
    _make_user(temp_db, "no-stripe@example.com")  # no customer_id
    result = ta._cmd_check_transaction(email="no-stripe@example.com")
    assert "📭" in result
    assert "no stripe customer" in result.lower()


# ── category filter ──────────────────────────────────────────────────────────

def test_category_payg_filters_out_subscription_charges(temp_db, monkeypatch):
    charges = [
        _charge(id="ch_payg", payment_intent="pi_payg", email="ivy@example.com", customer="cus_ivy", invoice=None),
        _charge(id="ch_sub", payment_intent="pi_subivy", email="ivy@example.com", customer="cus_ivy", invoice="in_ivy"),
    ]
    _mock_stripe(monkeypatch, charges)
    ivy = _make_user(temp_db, "ivy@example.com", customer_id="cus_ivy",
                      subscription_status="active", has_paid=1)
    db.record_credit_grant(temp_db, ivy["id"], "ivy@example.com", "song", 10, "checkout_topup", "pi_payg")

    result = ta._cmd_check_transaction(email="ivy@example.com", category="payg")

    assert "1 matching transaction" in result
    assert "Credits: landed" in result
    assert "Subscription:" not in result


# ── Sensitive data never appears in the response ────────────────────────────

def test_no_sensitive_fields_ever_appear_in_the_response(temp_db, monkeypatch):
    charges = [_charge(id="ch_1", payment_intent="pi_1", email="jill@example.com", customer="cus_jill",
                        card_last4="1234", card_brand="mastercard",
                        secret_marker="sk_live_totally_secret_value_should_never_leak")]
    _mock_stripe(monkeypatch, charges)
    jill = _make_user(temp_db, "jill@example.com", customer_id="cus_jill")
    db.record_credit_grant(temp_db, jill["id"], "jill@example.com", "song", 10, "checkout_topup", "pi_1")

    result = ta._cmd_check_transaction(email="jill@example.com")

    assert "1234" not in result
    assert "mastercard" not in result
    assert "sk_live_totally_secret_value_should_never_leak" not in result
    assert os.environ["STRIPE_SECRET_KEY"] not in result


def test_no_sensitive_fields_leak_in_a_since_window_scan_across_multiple_customers(temp_db, monkeypatch):
    """Broader than the single-user case: scanning a whole time window must
    not spill one customer's card details into the reply either."""
    charges = [
        _charge(id="ch_1", payment_intent="pi_1", email="ken@example.com", customer="cus_ken",
                card_last4="9999", card_brand="amex"),
        _charge(id="ch_2", payment_intent="pi_2", email="liz@example.com", customer="cus_liz",
                card_last4="8888", card_brand="discover"),
    ]
    _mock_stripe(monkeypatch, charges)
    _make_user(temp_db, "ken@example.com", customer_id="cus_ken")
    _make_user(temp_db, "liz@example.com", customer_id="cus_liz")

    result = ta._cmd_check_transaction(since="1h")

    for leaked in ("9999", "8888", "amex", "discover"):
        assert leaked not in result


def test_no_match_response_reveals_nothing_about_unrelated_transactions(temp_db, monkeypatch):
    """A search that finds nothing for the requested person must not leak
    ANY detail about other charges that happened to be scanned along the way."""
    charges = [_charge(id="ch_other", payment_intent="pi_other", email="mona@example.com",
                        customer="cus_mona", card_last4="5555")]
    _mock_stripe(monkeypatch, charges)
    _make_user(temp_db, "nora@example.com", customer_id="cus_nora")

    result = ta._cmd_check_transaction(email="nora@example.com")

    assert "mona" not in result.lower()
    assert "5555" not in result


# ── Wiring into the AI action-routing layer ─────────────────────────────────

class _FakeAnthropic:
    def __init__(self, response_text):
        self._response_text = response_text
        self.messages = self

    def create(self, **kwargs):
        return SimpleNamespace(content=[SimpleNamespace(text=self._response_text)], stop_reason="end_turn")


def _mock_model_response(monkeypatch, response_text):
    monkeypatch.setattr("anthropic.Anthropic", lambda **kw: _FakeAnthropic(response_text))


def test_payment_question_triggers_check_transaction_via_ai_routing(temp_db, monkeypatch):
    _mock_model_response(monkeypatch, '{"type": "action", "action": "check_transaction", "email": "olive@example.com"}')
    charges = [_charge(id="ch_1", payment_intent="pi_olive", email="olive@example.com", customer="cus_olive")]
    _mock_stripe(monkeypatch, charges)
    olive = _make_user(temp_db, "olive@example.com", customer_id="cus_olive")
    db.record_credit_grant(temp_db, olive["id"], "olive@example.com", "song", 10, "checkout_topup", "pi_olive")

    reply = ta.parse_and_run("did olive's payment go through", chat_id="")

    assert "Payment: succeeded" in reply
    assert "Credits: landed" in reply


def test_since_window_question_triggers_check_transaction_without_asking_for_email(temp_db, monkeypatch):
    _mock_model_response(monkeypatch, '{"type": "action", "action": "check_transaction", "since": "2h", "category": "payg"}')
    charges = [_charge(id="ch_1", payment_intent="pi_pat", email="pat@example.com", customer="cus_pat")]
    _mock_stripe(monkeypatch, charges)
    pat = _make_user(temp_db, "pat@example.com", customer_id="cus_pat")
    db.record_credit_grant(temp_db, pat["id"], "pat@example.com", "song", 10, "checkout_topup", "pi_pat")

    reply = ta.parse_and_run("any PAYG purchases in the last 2 hours", chat_id="")

    assert "pat@example.com" in reply
    assert "Credits: landed" in reply


# ── System prompt content (regression guard) ────────────────────────────────

def test_system_prompt_lists_check_transaction_and_prefers_time_window_over_asking():
    prompt = ta.ADMIN_SYSTEM_PROMPT
    assert "check_transaction" in prompt
    assert "credits landed" in prompt.lower() or "credit" in prompt.lower()
    assert "time window" in prompt.lower()


def test_system_prompt_includes_check_transaction_in_the_never_guess_rule():
    prompt = " ".join(ta.ADMIN_SYSTEM_PROMPT.split())  # collapse line-wrap whitespace
    assert "check_deploy_status, check_incidents, or check_transaction" in prompt


# ── _cmd_revenue: the same .get()-on-a-real-Charge bug, same fix ───────────
#
# _cmd_revenue predates check_transaction and used the identical ch.get(...)
# pattern that crashed check_transaction on 2026-09-13 -- except _cmd_revenue
# already wraps its whole body in try/except, so instead of a raw 500 it
# was silently reporting "❌ Stripe error: ..." (always £0.00) for however
# long the installed stripe-python has forbidden .get() on a Charge. These
# tests use the same real-Charge-object fixture as check_transaction's own
# tests specifically so this class of bug can't hide behind a dict mock here
# either.

def test_cmd_revenue_reports_a_real_total_with_real_charge_objects(monkeypatch):
    charges = [
        _charge(id="ch_1", amount=1000, status="succeeded", paid=True, refunded=False),
        _charge(id="ch_2", amount=500, status="succeeded", paid=True, refunded=False),
        _charge(id="ch_3", amount=2000, status="succeeded", paid=True, refunded=True),  # refunded, excluded
    ]
    _mock_stripe(monkeypatch, charges)

    result = ta._cmd_revenue()

    assert "❌" not in result
    assert "£15.00" in result  # 1000 + 500 pence = £15.00, refunded charge excluded


def test_cmd_revenue_never_raises_a_raw_attributeerror_on_real_charges(monkeypatch):
    """Would have returned "❌ Stripe error: 'get' is a dict method..." before
    the fix -- now must report a real number instead."""
    charges = [_charge(id="ch_1", amount=999, status="succeeded", paid=True, refunded=False)]
    _mock_stripe(monkeypatch, charges)

    result = ta._cmd_revenue()

    assert "dict method" not in result
    assert "AttributeError" not in result
