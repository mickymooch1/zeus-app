"""
billing.py — Stripe integration for Zeus SaaS platform.
Gracefully disabled if STRIPE_SECRET_KEY is not set.
"""
import logging
import os
from datetime import datetime, timezone

import db

log = logging.getLogger("zeus.billing")

# ── Plan configuration ────────────────────────────────────────────────────────

PLANS: dict = {
    "pro": {
        "name": "Professional",
        "price": "£29/mo",
        "price_id": os.environ.get("STRIPE_PRO_PRICE_ID", ""),
        "features": [
            "Unlimited messages",
            "Persistent memory & learning",
            "Client & project tracking",
            "Website builder",
            "Email drafting",
            "Content & copy generation",
            "Netlify deployment integration",
            "Business operations assistant",
            "Priority response",
        ],
    },
    "agency": {
        "name": "Agency",
        "price": "£79/mo",
        "price_id": os.environ.get("STRIPE_AGENCY_PRICE_ID", ""),
        "features": [
            "Everything in Professional",
            "Team features (coming soon)",
            "Multiple workspaces (coming soon)",
            "Priority support",
            "Custom integrations",
            "White-label options (coming soon)",
            "Dedicated account manager",
        ],
    },
}

FREE_LIMIT = 20

# Hardcoded Stripe price IDs — used to map a completed payment to a plan
PRO_PRICE_ID = "price_1TJKE4K5Ou7aVaHMesQe02B5"
AGENCY_PRICE_ID = "price_1TJKF9K5Ou7aVaHMqijE70Hw"

_PRICE_ID_TO_PLAN = {
    PRO_PRICE_ID: "pro",
    AGENCY_PRICE_ID: "agency",
}

# ── Stripe setup ──────────────────────────────────────────────────────────────

_STRIPE_SECRET_KEY = os.environ.get("STRIPE_SECRET_KEY", "")
_STRIPE_WEBHOOK_SECRET = os.environ.get("STRIPE_WEBHOOK_SECRET", "")

_stripe = None


def stripe_enabled() -> bool:
    """Return True if Stripe is configured."""
    return bool(_STRIPE_SECRET_KEY)


def _get_stripe():
    global _stripe
    if _stripe is None:
        if not stripe_enabled():
            raise RuntimeError("Stripe is not configured (STRIPE_SECRET_KEY not set)")
        import stripe as _stripe_lib
        _stripe_lib.api_key = _STRIPE_SECRET_KEY
        _stripe = _stripe_lib
    return _stripe


# ── Public functions ──────────────────────────────────────────────────────────

def create_checkout_session(user: dict, plan: str, success_url: str, cancel_url: str) -> str:
    """
    Create a Stripe Checkout Session for the given plan.
    Returns the checkout URL.
    """
    stripe = _get_stripe()

    if plan not in PLANS:
        raise ValueError(f"Unknown plan: {plan}")

    price_id = PLANS[plan]["price_id"]
    if not price_id:
        raise ValueError(f"No Stripe price ID configured for plan '{plan}'")

    customer_id = user.get("stripe_customer_id")

    params: dict = {
        "payment_method_types": ["card"],
        "line_items": [{"price": price_id, "quantity": 1}],
        "mode": "subscription",
        "success_url": success_url,
        "cancel_url": cancel_url,
        "metadata": {
            "user_id": user["id"],
            "plan": plan,
        },
        "subscription_data": {
            "metadata": {
                "user_id": user["id"],
                "plan": plan,
            }
        },
    }

    if customer_id:
        params["customer"] = customer_id
    else:
        params["customer_email"] = user["email"]

    session = stripe.checkout.Session.create(**params)
    return session.url


def create_portal_session(customer_id: str, return_url: str) -> str:
    """
    Create a Stripe Customer Portal session.
    Returns the portal URL.
    """
    stripe = _get_stripe()
    session = stripe.billing_portal.Session.create(
        customer=customer_id,
        return_url=return_url,
    )
    return session.url


def create_stripe_customer(user: dict) -> str | None:
    """
    Create a Stripe customer for the user. Returns customer ID or None on failure.
    """
    if not stripe_enabled():
        return None
    try:
        stripe = _get_stripe()
        customer = stripe.Customer.create(
            email=user["email"],
            name=user.get("name", ""),
            metadata={"user_id": user["id"]},
        )
        return customer.id
    except Exception as exc:
        log.warning("Could not create Stripe customer: %s", exc)
        return None


def handle_webhook(payload: bytes, sig: str) -> None:
    """
    Handle incoming Stripe webhook events.
    Updates user subscription status in the database.
    """
    stripe = _get_stripe()

    if not _STRIPE_WEBHOOK_SECRET:
        log.warning("STRIPE_WEBHOOK_SECRET not set — skipping signature verification")
        import json
        event = stripe.Event.construct_from(json.loads(payload), stripe.api_key)
    else:
        try:
            event = stripe.Webhook.construct_event(payload, sig, _STRIPE_WEBHOOK_SECRET)
        except stripe.error.SignatureVerificationError as exc:
            log.error("Stripe webhook signature verification failed: %s", exc)
            raise ValueError("Invalid Stripe signature") from exc

    _handle_event(event)


def _handle_event(event) -> None:
    """Dispatch Stripe event to the appropriate handler."""
    db_path = db.get_db_path()
    event_type = event["type"]
    data = event["data"]["object"]

    log.info("Stripe webhook: %s", event_type)

    if event_type == "checkout.session.completed":
        _handle_checkout_completed(db_path, data)
    elif event_type == "customer.subscription.updated":
        _handle_subscription_updated(db_path, data)
    elif event_type == "customer.subscription.deleted":
        _handle_subscription_deleted(db_path, data)
    else:
        log.debug("Unhandled Stripe event type: %s", event_type)


def _handle_checkout_completed(db_path, session) -> None:
    """Handle successful checkout — activate subscription."""
    customer_email = session.get("customer_email")
    customer_id = session.get("customer")
    subscription_id = session.get("subscription")
    user_id = session.get("metadata", {}).get("user_id")

    # Determine plan from the subscription's price ID
    plan = None
    if subscription_id:
        try:
            stripe = _get_stripe()
            sub = stripe.Subscription.retrieve(subscription_id)
            price_id = sub["items"]["data"][0]["price"]["id"]
            plan = _PRICE_ID_TO_PLAN.get(price_id)
            if not plan:
                log.warning("checkout.session.completed: unknown price_id %s", price_id)
        except Exception as exc:
            log.warning("Could not retrieve subscription to determine plan: %s", exc)

    # Fall back to metadata plan if price_id lookup failed
    if not plan:
        plan = session.get("metadata", {}).get("plan")

    # Find user — by email first, then by Stripe customer ID, then by metadata user_id
    user = None
    if customer_email:
        user = db.get_user_by_email(db_path, customer_email)
    if not user and customer_id:
        user = _find_user_by_customer(db_path, customer_id)
    if not user and user_id:
        user = db.get_user_by_id(db_path, user_id)

    if not user:
        log.warning(
            "checkout.session.completed: could not find user "
            "(email=%s, customer=%s, user_id=%s)",
            customer_email, customer_id, user_id,
        )
        return

    updates = {
        "subscription_status": "active",
        "subscription_plan": plan,
    }
    if customer_id:
        updates["stripe_customer_id"] = customer_id
    if subscription_id:
        updates["subscription_id"] = subscription_id

    db.update_user(db_path, user["id"], **updates)
    log.info("Activated %s plan for user %s", plan, user["id"])


def _handle_subscription_updated(db_path, subscription) -> None:
    """Handle subscription update — sync status and plan."""
    customer_id = subscription.get("customer")
    status = subscription.get("status")  # active, past_due, canceled, etc.
    subscription_id = subscription.get("id")

    if not customer_id:
        return

    user = _find_user_by_customer(db_path, customer_id)
    if not user:
        log.warning("subscription.updated: no user found for customer %s", customer_id)
        return

    # Try to extract plan from subscription metadata
    plan = subscription.get("metadata", {}).get("plan") or user.get("subscription_plan")

    # Map Stripe status to our status
    our_status = "active" if status in ("active", "trialing") else status

    db.update_user(db_path, user["id"],
                   subscription_status=our_status,
                   subscription_plan=plan,
                   subscription_id=subscription_id)
    log.info("Updated subscription for user %s: status=%s plan=%s", user["id"], our_status, plan)


def _handle_subscription_deleted(db_path, subscription) -> None:
    """Handle subscription cancellation — revert to free and reset message count."""
    customer_id = subscription.get("customer")
    if not customer_id:
        return

    user = _find_user_by_customer(db_path, customer_id)
    if not user:
        log.warning("subscription.deleted: no user found for customer %s", customer_id)
        return

    db.update_user(db_path, user["id"],
                   subscription_status="free",
                   subscription_plan=None,
                   subscription_id=None)
    db.reset_monthly_usage(db_path, user["id"])
    log.info("Subscription cancelled for user %s — reverted to free, usage reset", user["id"])


def _find_user_by_customer(db_path, customer_id: str) -> dict | None:
    """Look up a user by their Stripe customer ID."""
    import sqlite3
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    try:
        row = conn.execute(
            "SELECT * FROM users WHERE stripe_customer_id = ?", (customer_id,)
        ).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def get_subscription_status(user: dict) -> dict:
    """
    Return subscription status dict for a user.
    """
    db_path = db.get_db_path()
    month = datetime.now(timezone.utc).strftime("%Y-%m")
    messages_used = db.get_monthly_usage(db_path, user["id"], month)

    status = user.get("subscription_status", "free")
    plan = user.get("subscription_plan")

    is_admin = bool(user.get("is_admin", 0))
    is_paid = status == "active" and plan in PLANS
    messages_limit = None if (is_paid or is_admin) else FREE_LIMIT

    return {
        "status": status,
        "plan": plan,
        "plan_name": PLANS.get(plan, {}).get("name", "Free") if plan else "Free",
        "messages_used": messages_used,
        "messages_limit": messages_limit,
        "is_active": is_paid,
    }
