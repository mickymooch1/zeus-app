import os, pathlib, sys
from unittest.mock import MagicMock, patch
import pytest

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))
os.environ.setdefault("ANTHROPIC_API_KEY", "test-key-for-tests")
import billing


def _user():
    return {"id": "u1", "email": "buyer@test.com", "stripe_customer_id": None}


def test_create_memorial_checkout_session_no_price_id_raises(monkeypatch):
    monkeypatch.delenv("STRIPE_MEMORIAL_PACKAGE_PRICE_ID", raising=False)
    billing.MEMORIAL_PACKS["memorial_default"]["price_id"] = ""
    with pytest.raises(ValueError, match="No Stripe price ID"):
        billing.create_memorial_checkout_session(_user(), "https://ok", "https://cancel")


def test_create_memorial_checkout_session_builds_payment_mode_session(monkeypatch):
    billing.MEMORIAL_PACKS["memorial_default"]["price_id"] = "price_test123"
    fake_session = MagicMock(url="https://checkout.stripe.com/test")
    with patch.object(billing, "_get_stripe") as mock_stripe:
        mock_stripe.return_value.checkout.Session.create.return_value = fake_session
        url = billing.create_memorial_checkout_session(_user(), "https://ok", "https://cancel")
    assert url == "https://checkout.stripe.com/test"
    call_kwargs = mock_stripe.return_value.checkout.Session.create.call_args.kwargs
    assert call_kwargs["mode"] == "payment"
    assert call_kwargs["customer_email"] == "buyer@test.com"
    assert call_kwargs["metadata"]["memorial_package"] == "memorial_default"
    assert call_kwargs["payment_intent_data"]["metadata"]["memorial_package"] == "memorial_default"
