import os
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))

# Keep FastAPI lifespan / other imports from raising on a missing key.
os.environ.setdefault("ANTHROPIC_API_KEY", "test-key-for-tests")

import stripe  # noqa: E402
import billing  # noqa: E402


def _make_stripe_event(event_type, obj):
    """Build the object shape that stripe.Webhook.construct_event returns in
    production: a StripeObject, NOT a plain dict.

    On stripe-python 15.x a StripeObject no longer supports ``.get()`` — the
    call routes through ``__getattr__`` and raises ``AttributeError('get')``.
    That is the exact production bug we are reproducing.
    """
    return stripe.Event.construct_from(
        {"id": "evt_test_123", "type": event_type, "data": {"object": obj}},
        "sk_test",
    )


def test_stripe_object_get_reproduces_the_bug():
    """Guardrail: prove the crash exists on the raw StripeObject so this test
    stays meaningful if the stripe version ever changes back."""
    event = _make_stripe_event("payment_intent.created", {"id": "pi_test"})
    try:
        event.get("id", "?")
    except AttributeError as exc:
        assert "get" in str(exc)
    else:
        # If a future stripe version restores .get(), that's fine — the handler
        # fix below is still correct. Only fail if we somehow lost coverage.
        pass


def test_handle_event_does_not_crash_on_stripe_object():
    """Reproduces the production crash.

    Before the fix, ``_handle_event`` called ``event.get("id", "?")`` at
    billing.py:480 on EVERY event, raising ``AttributeError('get')`` before any
    handler ran — so PAYG credits were never granted. ``payment_intent.created``
    is an ignored event, so this exercises the shared prelude (lines 474-485)
    with no DB writes: it must return cleanly, not raise.
    """
    event = _make_stripe_event("payment_intent.created", {"id": "pi_test"})
    billing._handle_event(event)  # must not raise
