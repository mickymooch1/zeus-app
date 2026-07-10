"""
billing.py — Stripe integration for Zeus SaaS platform.
Gracefully disabled if STRIPE_SECRET_KEY is not set.
"""
import logging
import os
from datetime import datetime, timezone

import db
import alerts as _alerts

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

FREE_SONG_CREDITS = 3  # reduced from 5 — existing free users keep their balance

_PLAN_SONG_CREDITS = {
    "pro":           20,
    "agency":        70,
    "enterprise":    100,
    "music_starter": 25,
    "music_pro":     55,
    "music_agency":  110,
}

_PLAN_VIDEO_CREDITS = {
    "agency":       5,
    "enterprise":   15,
    "music_pro":    3,
    "music_agency": 10,
}

_PLAN_PREMIUM_CREDITS = {
    "pro":           10,
    "agency":        20,
    "enterprise":    50,
    "music_starter": 3,
    "music_pro":     10,
    "music_agency":  20,
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
            "55 AI songs/month",
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
            "110 AI songs/month",
            "YouTube upload",
            "10 avatar videos/month",
            "Song download & share",
            "All music genres",
            "No website builder",
        ],
    },
}

STRIPE_ANIMATION_PACK_5_PRICE_ID  = os.environ.get("STRIPE_ANIMATION_PACK_5_PRICE_ID", "")
STRIPE_ANIMATION_PACK_15_PRICE_ID = os.environ.get("STRIPE_ANIMATION_PACK_15_PRICE_ID", "")

ANIMATION_PACKS = {
    "animation_pack_5": {
        "credits": 5,
        "label": "5 animations",
        "price": "£2",
        "price_id": STRIPE_ANIMATION_PACK_5_PRICE_ID,
    },
    "animation_pack_15": {
        "credits": 15,
        "label": "15 animations",
        "price": "£5",
        "price_id": STRIPE_ANIMATION_PACK_15_PRICE_ID,
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
        # Auto-apply 50% off first month. Note: allow_promotion_codes cannot be
        # used alongside discounts — manual promo codes are intentionally disabled.
        "discounts": [{"coupon": "FIRST_MONTH_50"}],
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
        # Propagate metadata to payment intent so payment_intent.succeeded
        # can identify the user and pack (needed for Apple Pay backup flow)
        "payment_intent_data": {
            "metadata": {
                "user_id": user["id"],
                "song_pack": pack,
            },
        },
    }

    if customer_id:
        params["customer"] = customer_id
    else:
        params["customer_email"] = user["email"]

    session = stripe.checkout.Session.create(**params)
    return session.url


def create_animation_pack_checkout_session(user: dict, pack: str, success_url: str, cancel_url: str) -> str:
    """Create a one-time Stripe Checkout Session for an animation credit top-up pack."""
    stripe = _get_stripe()

    if pack not in ANIMATION_PACKS:
        raise ValueError(f"Unknown animation pack: {pack}")

    price_id = ANIMATION_PACKS[pack]["price_id"]
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
            "animation_pack": pack,
        },
        # Propagate metadata to payment intent so payment_intent.succeeded
        # can identify the user and pack (needed for Apple Pay backup flow)
        "payment_intent_data": {
            "metadata": {
                "user_id": user["id"],
                "animation_pack": pack,
            },
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


def ensure_promo_codes() -> None:
    """Create Stripe coupons at startup. Idempotent — safe to re-run.

    FIRST_MONTH_50: auto-applied coupon (50% off first month) on all new subscriptions.
    """
    if not stripe_enabled():
        return
    try:
        stripe = _get_stripe()
        try:
            stripe.Coupon.retrieve("FIRST_MONTH_50")
            log.info("billing: FIRST_MONTH_50 coupon already exists — skipping creation")
        except Exception:
            stripe.Coupon.create(
                id="FIRST_MONTH_50",
                percent_off=50,
                duration="once",
                name="50% off first month",
                metadata={"source": "auto_applied"},
            )
            log.info("billing: Created FIRST_MONTH_50 coupon (50%% off first month, auto-applied to all new subscriptions)")
    except Exception as exc:
        log.warning("billing: ensure_promo_codes failed: %s", exc)


class WebhookSignatureError(Exception):
    """Raised when a webhook payload fails Stripe signature verification.

    Almost always a bot/scanner probing the public webhook URL with junk — NOT a
    real payment that failed to process. Callers log it quietly and do NOT raise a
    Telegram alert, so genuine processing-error alerts stay meaningful.
    """


def handle_webhook(payload: bytes, sig: str) -> None:
    """
    Handle incoming Stripe webhook events.
    Updates user subscription status in the database.
    """
    stripe = _get_stripe()

    log.info("handle_webhook: payload_bytes=%d sig_present=%s secret_configured=%s",
             len(payload), bool(sig), bool(_STRIPE_WEBHOOK_SECRET))

    if not _STRIPE_WEBHOOK_SECRET:
        log.warning("STRIPE_WEBHOOK_SECRET not set — skipping signature verification (events accepted unsigned)")
        import json
        event = stripe.Event.construct_from(json.loads(payload), stripe.api_key)
    else:
        try:
            event = stripe.Webhook.construct_event(payload, sig, _STRIPE_WEBHOOK_SECRET)
        except stripe.error.SignatureVerificationError as exc:
            # Usually a bot probing the public URL with junk — log quietly, no alert.
            log.warning("Stripe webhook: invalid signature — ignoring (usually a bot probing the URL): %s", exc)
            raise WebhookSignatureError(str(exc)) from exc

    _handle_event(event)


_HANDLED_EVENTS = frozenset({
    "checkout.session.completed",
    "checkout.session.async_payment_succeeded",
    "checkout.session.async_payment_failed",
    "invoice.payment_succeeded",
    "customer.subscription.updated",
    "customer.subscription.deleted",
    "payment_intent.succeeded",
})

# Events we acknowledge but intentionally do nothing with
_IGNORED_EVENTS = frozenset({
    "invoice.upcoming",
    "payment_intent.created",
    "charge.succeeded",
    "charge.updated",
})


def _handle_event(event) -> None:
    """Dispatch Stripe event to the appropriate handler."""
    # stripe-python 15.x returns a StripeObject, whose ``.get()`` raises
    # AttributeError('get') (attribute access routes through __getattr__). Every
    # handler below — and the logging line at 480 — treats the event/session/
    # invoice/payment_intent as a plain dict via ``.get()``. Convert the whole
    # event to a fully-plain nested dict once at ingress so all of that works.
    import json
    event = json.loads(str(event))

    db_path = db.get_db_path()
    event_type = event["type"]
    data = event["data"]["object"]

    # Log at INFO so this always appears in Railway logs
    log.info(
        "Stripe webhook received: type=%s id=%s (handled=%s)",
        event_type, event.get("id", "?"), event_type in _HANDLED_EVENTS,
    )

    if event_type in _IGNORED_EVENTS:
        log.info("Stripe webhook: event type %r acknowledged and ignored", event_type)
        return

    try:
        if event_type in ("checkout.session.completed", "checkout.session.async_payment_succeeded"):
            _handle_checkout_completed(db_path, data)
        elif event_type == "checkout.session.async_payment_failed":
            _handle_async_payment_failed(db_path, data)
        elif event_type == "invoice.payment_succeeded":
            _handle_invoice_paid(db_path, data)
        elif event_type == "payment_intent.succeeded":
            _handle_payment_intent_succeeded(db_path, data)
        elif event_type == "customer.subscription.updated":
            _handle_subscription_updated(db_path, data)
        elif event_type == "customer.subscription.deleted":
            _handle_subscription_deleted(db_path, data)
        else:
            # Must be INFO not DEBUG — Railway default level is INFO so debug never appears
            log.info("Stripe webhook: event type %r is not handled — no action taken", event_type)
    except Exception:
        # Defence-in-depth: a crash in ONE handler must NOT bubble up to a 500 — Stripe
        # disables endpoints that keep erroring, which would break ALL crediting. Log the
        # exact event type + id (this is what pinpoints the culprit in Railway logs), then
        # swallow so the webhook still acknowledges with 200.
        log.exception(
            "Stripe webhook: handler for type=%s id=%s CRASHED — logged & acknowledged, NOT retried",
            event_type, event.get("id", "?"),
        )


def _send_notification_email(to_email: str, subject: str, body: str) -> None:
    """Best-effort transactional email via Gmail SMTP. Never raises — a Stripe
    webhook must still return 200 even if the notification email fails."""
    import smtplib
    from email.mime.text import MIMEText
    from email.mime.multipart import MIMEMultipart

    smtp_email = os.environ.get("SMTP_EMAIL", "").strip()
    smtp_password = os.environ.get("SMTP_PASSWORD", "").strip()
    if not smtp_email or not smtp_password:
        log.warning("notification email NOT sent (SMTP_EMAIL/SMTP_PASSWORD unset) — to=%r subject=%r", to_email, subject)
        return
    try:
        msg = MIMEMultipart()
        msg["From"] = f"Zeus <{smtp_email}>"
        msg["To"] = to_email
        msg["Subject"] = subject
        msg.attach(MIMEText(body, "plain"))
        with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=20) as server:
            server.login(smtp_email, smtp_password)
            server.sendmail(smtp_email, [to_email], msg.as_string())
        log.info("notification email sent to %r (subject=%r)", to_email, subject)
    except Exception as exc:
        log.error("notification email FAILED to %r (subject=%r) — %s", to_email, subject, exc)


def _handle_async_payment_failed(db_path, session) -> None:
    """A delayed/async payment method (e.g. bank transfer) failed after checkout.

    Per Stripe's "Fulfil orders with Checkout" delayed-notification guidance, no
    credits were ever granted (the payment_status guard in
    _handle_checkout_completed withheld them), so there is nothing to revoke —
    we just notify the customer so they can place the order again."""
    customer_email = session.get("customer_email")
    customer_id = session.get("customer")
    session_id = session.get("id", "?")

    user = None
    if customer_email:
        user = db.get_user_by_email(db_path, customer_email)
    if not user and customer_id:
        user = _find_user_by_customer(db_path, customer_id)
    to_email = (user.get("email") if user else None) or customer_email

    log.warning(
        "checkout.session.async_payment_failed: session=%s user=%s email=%r — delayed payment "
        "FAILED, no credits granted (none were), notifying customer + admin",
        session_id, (user["id"] if user else "NOT FOUND"), to_email,
    )
    # Internal Telegram alert so we know immediately — not just the customer.
    # alert_payment_failed is best-effort (swallows its own errors), so it can't
    # break the webhook ack.
    _alerts.alert_payment_failed(to_email or "", session_id)
    if to_email:
        _send_notification_email(
            to_email,
            "Your Zeus payment didn't go through",
            "Hi,\n\nYour recent payment to Zeus didn't complete — delayed payment methods "
            "(such as bank transfers) can take a few days and occasionally fail. No credits "
            "were added and you have not been charged.\n\nTo get your credits, please place "
            "the order again at zeusbeats.com.\n\nThanks,\nThe Zeus team",
        )


def _grant_topup(db_path, user, credit_type: str, credits: int, source: str, pi_id, pack) -> None:
    """Grant a one-time credit top-up idempotently.

    The credit_ledger insert (keyed on payment_intent id + credit_type) is the
    idempotency gate: if this payment was already credited — by the other webhook
    path (checkout vs payment_intent backup) or a Stripe delivery retry — the
    increment is skipped. credit_type is 'song' or 'premium'.
    """
    email = user.get("email")
    if not pi_id:
        log.warning("Top-up with no payment_intent id (pack=%s user=%s) — cannot dedupe, granting once",
                    pack, user["id"])
    newly = db.record_credit_grant(db_path, user["id"], email, credit_type, credits, source, pi_id)
    if not newly:
        log.info("DUPLICATE credit grant skipped: %s top-up %d (%s) pi=%s already credited — user %s",
                 credit_type, credits, pack, pi_id, user["id"])
        return
    if credit_type == "song":
        db.increment_song_credits(db_path, user["id"], credits)
    else:
        db.increment_premium_credits(db_path, user["id"], credits)
    db.update_user(db_path, user["id"], has_paid=1)
    log.info("CREDITS GRANTED: %s top-up %d credits (%s) → user %s email=%s pi=%s",
             credit_type, credits, pack, user["id"], email, pi_id)


def _handle_checkout_completed(db_path, session) -> None:
    """Handle successful checkout — subscription activation or song credit top-up."""
    customer_email = session.get("customer_email")
    customer_id = session.get("customer")
    subscription_id = session.get("subscription")
    user_id = session.get("metadata", {}).get("user_id")
    session_id = session.get("id", "?")
    mode = session.get("mode", "?")

    payment_status = session.get("payment_status", "?")
    log.info(
        "checkout.session.completed: session=%s mode=%s payment_status=%s customer_email=%r customer_id=%r subscription_id=%r user_id_meta=%r",
        session_id, mode, payment_status, customer_email, customer_id, subscription_id, user_id,
    )

    # For one-time payments, Stripe fires checkout.session.completed immediately
    # even for async payment methods (bank transfer etc) where payment_status="unpaid".
    # Only grant credits once payment_status is "paid" or it's a subscription (handled by invoice event).
    if mode == "payment" and payment_status != "paid":
        log.warning(
            "checkout.session.completed: mode=payment but payment_status=%r — NOT granting credits yet "
            "(will fire checkout.session.async_payment_succeeded when paid)",
            payment_status,
        )
        return

    # ── One-time payment: song or animation credit top-up ────────────────────
    if mode == "payment":
        pack = session.get("metadata", {}).get("song_pack")
        anim_pack = session.get("metadata", {}).get("animation_pack")
        pi_id = session.get("payment_intent")
        amount_display = f"£{(session.get('amount_total') or 0) / 100:.2f}"
        log.info("checkout one-time payment: song_pack=%r anim_pack=%r pi=%s", pack, anim_pack, pi_id)

        user = None
        if customer_email:
            user = db.get_user_by_email(db_path, customer_email)
            log.info("checkout user lookup by email=%r: found=%s", customer_email, bool(user))
        if not user and customer_id:
            user = _find_user_by_customer(db_path, customer_id)
            log.info("checkout user lookup by customer_id=%r: found=%s", customer_id, bool(user))
        if not user and user_id:
            user = db.get_user_by_id(db_path, user_id)
            log.info("checkout user lookup by user_id_meta=%r: found=%s", user_id, bool(user))

        if pack and pack in SONG_PACKS:
            if user:
                _grant_topup(db_path, user, "song", SONG_PACKS[pack]["credits"], "checkout_topup", pi_id, pack)
            else:
                log.error("CREDITS FAILED: song top-up pack=%s — user NOT FOUND (email=%r customer=%r user_id_meta=%r)",
                          pack, customer_email, customer_id, user_id)
                _alerts.alert_credit_not_granted(customer_email or "", amount_display,
                                                 f"song top-up {pack}: user not found", pi_id or session_id)
        elif anim_pack and anim_pack in ANIMATION_PACKS:
            if user:
                _grant_topup(db_path, user, "premium", ANIMATION_PACKS[anim_pack]["credits"], "checkout_topup", pi_id, anim_pack)
            else:
                log.error("CREDITS FAILED: animation top-up pack=%s — user NOT FOUND (email=%r customer=%r user_id_meta=%r)",
                          anim_pack, customer_email, customer_id, user_id)
                _alerts.alert_credit_not_granted(customer_email or "", amount_display,
                                                 f"animation top-up {anim_pack}: user not found", pi_id or session_id)
        else:
            log.warning("checkout.session.completed payment: unrecognised pack song=%r anim=%r — ignoring", pack, anim_pack)
            _alerts.alert_credit_not_granted(customer_email or "", amount_display,
                                             f"unrecognised pack (song={pack!r} anim={anim_pack!r})", pi_id or session_id)
        return

    # ── Subscription ─────────────────────────────────────────────────────────
    # Determine plan from the subscription's price ID
    plan = None
    price_id = None
    if subscription_id:
        try:
            stripe = _get_stripe()
            sub = stripe.Subscription.retrieve(subscription_id)
            price_id = sub["items"]["data"][0]["price"]["id"]
            plan = _PRICE_ID_TO_PLAN.get(price_id)
            log.info("checkout subscription price_id=%r → plan=%r (known_price_ids=%s)",
                     price_id, plan, list(_PRICE_ID_TO_PLAN.keys()))
            if not plan:
                log.error("checkout.session.completed: price_id %r not in _PRICE_ID_TO_PLAN — credits will NOT be granted. "
                          "Fix: add this price_id to _PRICE_ID_TO_PLAN or set the correct env var.", price_id)
        except Exception as exc:
            log.warning("Could not retrieve subscription %r to determine plan: %s", subscription_id, exc)

    # Fall back to metadata plan if price_id lookup failed
    if not plan:
        plan = session.get("metadata", {}).get("plan")
        log.info("checkout plan fallback to metadata: plan=%r", plan)

    # Find user — by email first, then by Stripe customer ID, then by metadata user_id
    user = None
    if customer_email:
        user = db.get_user_by_email(db_path, customer_email)
        log.info("checkout user lookup by email=%r: found=%s", customer_email, bool(user))
    if not user and customer_id:
        user = _find_user_by_customer(db_path, customer_id)
        log.info("checkout user lookup by customer_id=%r: found=%s", customer_id, bool(user))
    if not user and user_id:
        user = db.get_user_by_id(db_path, user_id)
        log.info("checkout user lookup by user_id_meta=%r: found=%s", user_id, bool(user))

    if not user:
        log.error(
            "CREDITS FAILED: checkout.session.completed — user NOT FOUND "
            "(email=%r customer=%r user_id_meta=%r plan=%r session=%s)",
            customer_email, customer_id, user_id, plan, session_id,
        )
        _alerts.alert_credit_not_granted(
            customer_email or "", f"£{(session.get('amount_total') or 0) / 100:.2f}",
            f"subscription {plan}: user not found", subscription_id or session_id)
        return

    updates = {
        "subscription_status": "active",
        "subscription_plan": plan,
        "has_paid": 1,
    }
    if customer_id:
        updates["stripe_customer_id"] = customer_id
    if subscription_id:
        updates["subscription_id"] = subscription_id

    db.update_user(db_path, user["id"], **updates)
    log.info("Activated %s plan for user %s (email=%s) — has_paid=1", plan, user["id"], user.get("email"))

    amount_pence = session.get("amount_total") or 0
    _alerts.alert_payment(
        user.get("email") or customer_email or "",
        plan or "",
        f"£{amount_pence / 100:.2f}",
    )

    allowance = _PLAN_SONG_CREDITS.get(plan, FREE_SONG_CREDITS)
    db.upsert_song_credits(db_path, user["id"], balance=allowance, monthly_allowance=allowance)
    log.info("CREDITS GRANTED: %d song credits (%s plan) → user %s email=%s", allowance, plan, user["id"], user.get("email"))

    video_allowance = _PLAN_VIDEO_CREDITS.get(plan, 0)
    if video_allowance > 0:
        db.upsert_video_credits(db_path, user["id"], balance=video_allowance, monthly_allowance=video_allowance)
        log.info("CREDITS GRANTED: %d video credits (%s plan) → user %s", video_allowance, plan, user["id"])

    anim_allowance = _PLAN_PREMIUM_CREDITS.get(plan, 0)
    db.upsert_premium_credits(db_path, user["id"], balance=anim_allowance, monthly_allowance=anim_allowance)
    log.info("CREDITS GRANTED: %d premium credits (%s plan) → user %s", anim_allowance, plan, user["id"])


def _handle_invoice_paid(db_path, invoice) -> None:
    """Reset monthly song credit balance on recurring Stripe invoice."""
    billing_reason = invoice.get("billing_reason")
    customer_id = invoice.get("customer")
    log.info("invoice.payment_succeeded: billing_reason=%r customer_id=%r", billing_reason, customer_id)

    if billing_reason != "subscription_cycle":
        log.info("invoice.payment_succeeded: skipping (not subscription_cycle, reason=%r)", billing_reason)
        return
    if not customer_id:
        return
    user = _find_user_by_customer(db_path, customer_id)
    if not user:
        log.error("CREDITS FAILED: invoice.payment_succeeded — no user for customer_id=%r", customer_id)
        _alerts.alert_credit_not_granted(
            "", f"£{(invoice.get('amount_paid') or 0) / 100:.2f}",
            "subscription renewal: no user for customer", invoice.get("id") or customer_id)
        return
    plan = user.get("subscription_plan")
    # Free plan is one-time signup credits only — never reset monthly
    if not plan or plan == "free" or plan not in _PLAN_SONG_CREDITS:
        log.info("invoice.payment_succeeded: skipping free/unknown plan user %s (plan=%s)", user["id"], plan)
        return
    allowance = _PLAN_SONG_CREDITS[plan]
    db.upsert_song_credits(db_path, user["id"], balance=allowance, monthly_allowance=allowance)
    log.info("Monthly song credits reset for user %s: %d credits (%s plan)", user["id"], allowance, plan)

    video_allowance = _PLAN_VIDEO_CREDITS.get(plan, 0)
    if video_allowance > 0:
        db.upsert_video_credits(db_path, user["id"], balance=video_allowance, monthly_allowance=video_allowance)
        log.info("Monthly video credits reset for user %s: %d credits (%s plan)", user["id"], video_allowance, plan)

    anim_allowance = _PLAN_PREMIUM_CREDITS.get(plan, 0)
    db.upsert_premium_credits(db_path, user["id"], balance=anim_allowance, monthly_allowance=anim_allowance)
    log.info("Monthly premium credits reset for user %s: %d credits (%s plan)", user["id"], anim_allowance, plan)


def _handle_payment_intent_succeeded(db_path, payment_intent) -> None:
    """Backup credit handler for payment_intent.succeeded — covers Apple Pay and other flows
    where checkout.session.completed may not fire or may have fired with payment_status=unpaid.

    Only acts when payment intent metadata contains song_pack or animation_pack (PAYG purchases).
    Subscriptions are handled by checkout.session.completed / invoice.payment_succeeded.
    Idempotency note: if checkout.session.completed already granted credits this will double-grant.
    The guard: we only act when metadata has pack keys — subscription payment intents have none.
    """
    pi_id = payment_intent.get("id", "?")
    metadata = payment_intent.get("metadata", {})
    user_id = metadata.get("user_id")
    song_pack = metadata.get("song_pack")
    anim_pack = metadata.get("animation_pack")
    customer_id = payment_intent.get("customer")

    log.info(
        "payment_intent.succeeded: id=%s customer_id=%r user_id_meta=%r song_pack=%r anim_pack=%r",
        pi_id, customer_id, user_id, song_pack, anim_pack,
    )

    # No pack metadata means this is a subscription payment intent — skip
    if not song_pack and not anim_pack:
        log.info("payment_intent.succeeded: no pack metadata — subscription payment, ignoring")
        return

    # Find the user — prefer metadata user_id (most reliable), then customer_id
    user = None
    if user_id:
        user = db.get_user_by_id(db_path, user_id)
        log.info("payment_intent user lookup by user_id_meta=%r: found=%s", user_id, bool(user))
    if not user and customer_id:
        user = _find_user_by_customer(db_path, customer_id)
        log.info("payment_intent user lookup by customer_id=%r: found=%s", customer_id, bool(user))

    amount_display = f"£{(payment_intent.get('amount') or 0) / 100:.2f}"

    if not user:
        log.error(
            "CREDITS FAILED: payment_intent.succeeded — user NOT FOUND "
            "(user_id_meta=%r customer_id=%r song_pack=%r anim_pack=%r pi=%s)",
            user_id, customer_id, song_pack, anim_pack, pi_id,
        )
        _alerts.alert_credit_not_granted(
            "", amount_display,
            f"payment_intent top-up (song={song_pack!r} anim={anim_pack!r}): user not found", pi_id)
        return

    # Idempotent: keyed on the payment_intent id, so if checkout.session.completed
    # already credited this same purchase, this backup path skips.
    if song_pack and song_pack in SONG_PACKS:
        _grant_topup(db_path, user, "song", SONG_PACKS[song_pack]["credits"],
                     "payment_intent_topup", pi_id, song_pack)
    elif anim_pack and anim_pack in ANIMATION_PACKS:
        _grant_topup(db_path, user, "premium", ANIMATION_PACKS[anim_pack]["credits"],
                     "payment_intent_topup", pi_id, anim_pack)
    else:
        log.warning(
            "payment_intent.succeeded: unrecognised pack song=%r anim=%r — no credits granted (pi=%s)",
            song_pack, anim_pack, pi_id,
        )
        _alerts.alert_credit_not_granted(
            user.get("email") or "", amount_display,
            f"payment_intent: unrecognised pack (song={song_pack!r} anim={anim_pack!r})", pi_id)


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

    old_plan = user.get("subscription_plan") or ""
    db.update_user(db_path, user["id"],
                   subscription_status="free",
                   subscription_plan=None,
                   subscription_id=None,
                   cancel_at=None)
    db.reset_monthly_usage(db_path, user["id"])
    log.info("Subscription cancelled for user %s — reverted to free, usage reset", user["id"])
    _alerts.alert_subscription_cancelled(user.get("email") or "", old_plan)


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
