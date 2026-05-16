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
    "enterprise": {
        "name": "Enterprise",
        "price": "£150/mo",
        "price_id": os.environ.get("STRIPE_ENTERPRISE_PRICE_ID", "price_1TK3elK5Ou7aVaHMiJ3jg3L4"),
        "features": [
            "Multi-agent AI",
            "Background tasks",
            "Scheduled automation",
            "Appointment booking",
            "Priority support",
        ],
    },
}

FREE_LIMIT = 20
DAILY_FREE_LIMIT = 30

# Hardcoded Stripe price IDs — used to map a completed payment to a plan
PRO_PRICE_ID = "price_1TJKE4K5Ou7aVaHMesQe02B5"
AGENCY_PRICE_ID = "price_1TJKF9K5Ou7aVaHMqijE70Hw"
ENTERPRISE_PRICE_ID = "price_1TK3elK5Ou7aVaHMiJ3jg3L4"

MUSIC_STARTER_PRICE_ID = os.environ.get("STRIPE_MUSIC_STARTER_PRICE_ID", "")
MUSIC_PRO_PRICE_ID     = os.environ.get("STRIPE_MUSIC_PRO_PRICE_ID", "")
MUSIC_AGENCY_PRICE_ID  = os.environ.get("STRIPE_MUSIC_AGENCY_PRICE_ID", "")

MUSIC_PLAN_KEYS = frozenset({"music_starter", "music_pro", "music_agency"})

_PRICE_ID_TO_PLAN = {
    PRO_PRICE_ID: "pro",
    AGENCY_PRICE_ID: "agency",
    ENTERPRISE_PRICE_ID: "enterprise",
}
if MUSIC_STARTER_PRICE_ID:
    _PRICE_ID_TO_PLAN[MUSIC_STARTER_PRICE_ID] = "music_starter"
if MUSIC_PRO_PRICE_ID:
    _PRICE_ID_TO_PLAN[MUSIC_PRO_PRICE_ID] = "music_pro"
if MUSIC_AGENCY_PRICE_ID:
    _PRICE_ID_TO_PLAN[MUSIC_AGENCY_PRICE_ID] = "music_agency"

FREE_SONG_CREDITS = 5

_PLAN_SONG_CREDITS = {
    "pro":           20,
    "agency":        70,
    "enterprise":    100,
    "music_starter": 25,
    "music_pro":     40,
    "music_agency":  80,
}

_PLAN_VIDEO_CREDITS = {
    "agency":       5,
    "enterprise":   15,
    "music_pro":    3,
    "music_agency": 10,
}

MUSIC_PLANS: dict = {
    "music_starter": {
        "name": "Music Starter",
        "price": "£9/mo",
        "price_id": MUSIC_STARTER_PRICE_ID,
        "features": [
            "25 AI songs/month",
            "YouTube upload",
            "Song download & share",
            "All music genres",
            "No website builder",
        ],
    },
    "music_pro": {
        "name": "Music Pro",
        "price": "£19/mo",
        "price_id": MUSIC_PRO_PRICE_ID,
        "features": [
            "40 AI songs/month",
            "YouTube upload",
            "3 avatar videos/month",
            "Song download & share",
            "All music genres",
            "No website builder",
        ],
    },
    "music_agency": {
        "name": "Music Agency",
        "price": "£39/mo",
        "price_id": MUSIC_AGENCY_PRICE_ID,
        "features": [
            "80 AI songs/month",
            "YouTube upload",
            "10 avatar videos/month",
            "Song download & share",
            "All music genres",
            "No website builder",
        ],
    },
}

SONG_PACKS = {
    # Pay-as-you-go packs (small, no subscription required)
    "song_pack_099": {
        "credits": 2,
        "label": "2 songs",
        "price": "£0.99",
        "price_id": os.environ.get("STRIPE_SONG_PACK_099_PRICE_ID", ""),
    },
    "song_pack_200": {
        "credits": 5,
        "label": "5 songs",
        "price": "£2.00",
        "price_id": os.environ.get("STRIPE_SONG_PACK_200_PRICE_ID", ""),
    },
    "song_pack_400": {
        "credits": 10,
        "label": "10 songs",
        "price": "£4.00",
        "price_id": os.environ.get("STRIPE_SONG_PACK_400_PRICE_ID", ""),
    },
    # Subscriber top-up packs (bulk credits for existing subscribers)
    "song_pack_10": {
        "credits": 10,
        "label": "10 songs",
        "price": "£8",
        "price_id": os.environ.get("STRIPE_SONG_PACK_10_PRICE_ID", ""),
    },
    "song_pack_50": {
        "credits": 50,
        "label": "50 songs",
        "price": "£30",
        "price_id": os.environ.get("STRIPE_SONG_PACK_50_PRICE_ID", ""),
    },
    "song_pack_200_sub": {
        "credits": 200,
        "label": "200 songs",
        "price": "£99",
        "price_id": os.environ.get("STRIPE_SONG_PACK_200_SUB_PRICE_ID", ""),
    },
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

    _all_plans = {**PLANS, **MUSIC_PLANS}
    if plan not in _all_plans:
        raise ValueError(f"Unknown plan: {plan}")

    price_id = _all_plans[plan]["price_id"]
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


def create_song_pack_checkout_session(user: dict, pack: str, success_url: str, cancel_url: str) -> str:
    """Create a one-time Stripe Checkout Session for a song credit top-up pack."""
    stripe = _get_stripe()

    if pack not in SONG_PACKS:
        raise ValueError(f"Unknown song pack: {pack}")

    price_id = SONG_PACKS[pack]["price_id"]
    if not price_id:
        raise ValueError(f"No Stripe price ID configured for pack '{pack}' — set STRIPE_{pack.upper()}_PRICE_ID")

    customer_id = user.get("stripe_customer_id")

    params: dict = {
        "payment_method_types": ["card"],
        "line_items": [{"price": price_id, "quantity": 1}],
        "mode": "payment",
        "success_url": success_url,
        "cancel_url": cancel_url,
        "metadata": {
            "user_id": user["id"],
            "song_pack": pack,
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
    elif event_type == "invoice.payment_succeeded":
        _handle_invoice_paid(db_path, data)
    elif event_type == "customer.subscription.updated":
        _handle_subscription_updated(db_path, data)
    elif event_type == "customer.subscription.deleted":
        _handle_subscription_deleted(db_path, data)
    else:
        log.debug("Unhandled Stripe event type: %s", event_type)


def _handle_checkout_completed(db_path, session) -> None:
    """Handle successful checkout — subscription activation or song credit top-up."""
    customer_email = session.get("customer_email")
    customer_id = session.get("customer")
    subscription_id = session.get("subscription")
    user_id = session.get("metadata", {}).get("user_id")

    # ── One-time payment: song credit top-up ─────────────────────────────────
    if session.get("mode") == "payment":
        pack = session.get("metadata", {}).get("song_pack")
        if pack and pack in SONG_PACKS:
            user = None
            if customer_email:
                user = db.get_user_by_email(db_path, customer_email)
            if not user and customer_id:
                user = _find_user_by_customer(db_path, customer_id)
            if not user and user_id:
                user = db.get_user_by_id(db_path, user_id)
            if user:
                credits = SONG_PACKS[pack]["credits"]
                db.increment_song_credits(db_path, user["id"], credits)
                log.info("Song top-up: added %d credits (%s) to user %s", credits, pack, user["id"])
            else:
                log.warning("Song top-up: could not find user (email=%s customer=%s user_id=%s)",
                            customer_email, customer_id, user_id)
        else:
            log.warning("checkout.session.completed payment: unrecognised pack %r — ignoring", pack)
        return

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

    allowance = _PLAN_SONG_CREDITS.get(plan, FREE_SONG_CREDITS)
    db.upsert_song_credits(db_path, user["id"], balance=allowance, monthly_allowance=allowance)
    log.info("Granted %d song credits (%s plan) to user %s", allowance, plan, user["id"])

    video_allowance = _PLAN_VIDEO_CREDITS.get(plan, 0)
    if video_allowance > 0:
        db.upsert_video_credits(db_path, user["id"], balance=video_allowance, monthly_allowance=video_allowance)
        log.info("Granted %d video credits (%s plan) to user %s", video_allowance, plan, user["id"])


def _handle_invoice_paid(db_path, invoice) -> None:
    """Reset monthly song credit balance on recurring Stripe invoice."""
    if invoice.get("billing_reason") != "subscription_cycle":
        return
    customer_id = invoice.get("customer")
    if not customer_id:
        return
    user = _find_user_by_customer(db_path, customer_id)
    if not user:
        log.warning("invoice.payment_succeeded: no user for customer %s", customer_id)
        return
    plan = user.get("subscription_plan")
    if not plan or plan not in _PLAN_SONG_CREDITS:
        log.info("invoice.payment_succeeded: skipping free/unknown plan user %s (plan=%s)", user["id"], plan)
        return
    allowance = _PLAN_SONG_CREDITS[plan]
    db.upsert_song_credits(db_path, user["id"], balance=allowance, monthly_allowance=allowance)
    log.info("Monthly song credits reset for user %s: %d credits (%s plan)", user["id"], allowance, plan)

    video_allowance = _PLAN_VIDEO_CREDITS.get(plan, 0)
    if video_allowance > 0:
        db.upsert_video_credits(db_path, user["id"], balance=video_allowance, monthly_allowance=video_allowance)
        log.info("Monthly video credits reset for user %s: %d credits (%s plan)", user["id"], video_allowance, plan)


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
                   subscription_id=None,
                   cancel_at=None)
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
    is_paid = status == "active" and (plan in PLANS or plan in MUSIC_PLAN_KEYS)
    messages_limit = None if (is_paid or is_admin) else FREE_LIMIT

    _all_plans = {**PLANS, **MUSIC_PLANS}
    return {
        "status": status,
        "plan": plan,
        "plan_name": _all_plans.get(plan, {}).get("name", "Free") if plan else "Free",
        "messages_used": messages_used,
        "messages_limit": messages_limit,
        "is_active": is_paid,
        "is_admin": is_admin,
        "cancel_at": user.get("cancel_at"),
    }
