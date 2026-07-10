#!/usr/bin/env python3
"""reconcile_payments.py — find customers who PAID but may NOT have been credited.

Context: the Stripe webhook was returning HTTP 500 on some events (June 23rd
onwards), so a paid checkout/invoice may never have triggered crediting. This
script cross-references Stripe's record of paid payments against the local DB
and flags anyone who looks uncredited, so they can be restored (e.g. via
Porickbot).

READ-ONLY: it never writes to the DB, never touches Stripe state, never refunds.
It only reports. Restoration is a deliberate manual step.

Run on Railway (where STRIPE_SECRET_KEY and the DB live):
    python reconcile_payments.py                 # since 2026-06-23 (UTC)
    python reconcile_payments.py --since 2026-06-23
    python reconcile_payments.py --days 14
    python reconcile_payments.py --csv out.csv   # also write a CSV

Verdicts:
    OK                 — subscription active + has_paid; looks credited.
    CREDITED           — one-time top-up with a matching credit_ledger row → credited.
    LIKELY_UNCREDITED  — paid in Stripe but not credited (sub: has_paid=0/no plan;
                         top-up: no credit_ledger row) → RESTORE.
    USER_NOT_FOUND     — paid in Stripe but no matching DB user → investigate.
"""
import argparse
import csv as _csv
import json
import os
import sys
from datetime import datetime, timezone

import db
import billing

SINCE_DEFAULT = "2026-06-23"


def _stripe():
    key = os.environ.get("STRIPE_SECRET_KEY", "").strip()
    if not key:
        sys.exit("ERROR: STRIPE_SECRET_KEY is not set — run this where the key is configured (Railway).")
    import stripe
    stripe.api_key = key
    return stripe


def _since_ts(args) -> int:
    if args.days:
        from datetime import timedelta
        return int((datetime.now(timezone.utc) - timedelta(days=args.days)).timestamp())
    dt = datetime.strptime(args.since, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    return int(dt.timestamp())


def _resolve_user(db_path, *, user_id, email, customer_id):
    """Best-effort user lookup mirroring the webhook's own resolution order."""
    if user_id:
        u = db.get_user_by_id(db_path, user_id)
        if u:
            return u
    if email:
        u = db.get_user_by_email(db_path, email)
        if u:
            return u
    if customer_id:
        u = billing._find_user_by_customer(db_path, customer_id)
        if u:
            return u
    return None


def _is_credited_subscription(user: dict) -> bool:
    # A credited subscriber has has_paid flipped and a plan recorded. (subscription_status
    # may lag, so don't hard-require 'active' — has_paid + plan is the crediting signal.)
    return bool(user.get("has_paid")) and bool(user.get("subscription_plan"))


def _amount(obj) -> str:
    cents = obj.get("amount_total") if "amount_total" in obj else obj.get("amount_paid", 0)
    cur = (obj.get("currency") or "gbp").upper()
    return f"{(cents or 0) / 100:.2f} {cur}"


def reconcile(args) -> None:
    stripe = _stripe()
    db_path = db.get_db_path()
    since = _since_ts(args)
    since_human = datetime.fromtimestamp(since, timezone.utc).strftime("%Y-%m-%d")
    print(f"Reconciling Stripe payments since {since_human} (UTC) against DB {db_path}\n")

    rows = []

    # ── Paid Checkout Sessions (new subscriptions + one-time top-ups) ────────────
    for s in stripe.checkout.Session.list(created={"gte": since}, limit=100).auto_paging_iter():
        s = json.loads(str(s))  # stripe 15.x StripeObject has no working .get(); use a plain dict
        if s.get("status") != "complete":
            continue
        pay_status = s.get("payment_status")
        if pay_status != "paid":
            # 'unpaid' = delayed method still pending/failed; 'no_payment_required' = free.
            if pay_status == "unpaid":
                rows.append(_row(s, "session", "PENDING/UNPAID", db_path, stripe, note="delayed payment not yet paid"))
            continue
        rows.append(_row(s, "session", None, db_path, stripe))

    # ── Paid subscription RENEWAL invoices (initial create is covered by session) ─
    for inv in stripe.Invoice.list(created={"gte": since}, status="paid", limit=100).auto_paging_iter():
        inv = json.loads(str(inv))  # stripe 15.x StripeObject has no working .get(); use a plain dict
        if inv.get("billing_reason") not in ("subscription_cycle", "subscription_update"):
            continue
        rows.append(_row(inv, "invoice_renewal", None, db_path, stripe))

    _report(rows, args)


def _row(obj, source, forced_verdict, db_path, stripe, note=""):
    created = datetime.fromtimestamp(obj.get("created", 0), timezone.utc).strftime("%Y-%m-%d %H:%M")
    cust_details = obj.get("customer_details") or {}
    email = cust_details.get("email") or obj.get("customer_email")
    customer_id = obj.get("customer")
    meta = obj.get("metadata") or {}
    user_id = meta.get("user_id")
    mode = obj.get("mode", "subscription" if source.startswith("invoice") else "?")

    # What was bought
    if mode == "payment":
        pack = meta.get("song_pack") or meta.get("animation_pack") or "?"
        bought = f"top-up:{pack}"
        is_sub = False
    else:
        bought = "subscription"
        is_sub = True

    user = _resolve_user(db_path, user_id=user_id, email=email, customer_id=customer_id)

    if forced_verdict:
        verdict = forced_verdict
    elif not user:
        verdict = "USER_NOT_FOUND"
    elif is_sub:
        verdict = "OK" if _is_credited_subscription(user) else "LIKELY_UNCREDITED"
    else:  # one-time top-up — now verifiable via the credit ledger (keyed on payment_intent id)
        pi_id = obj.get("payment_intent")
        credit_type = "song" if meta.get("song_pack") else "premium"
        grant = db.get_credit_grant(db_path, pi_id, credit_type) if pi_id else None
        verdict = "CREDITED" if grant else "LIKELY_UNCREDITED"

    return {
        "created": created,
        "email": email or "?",
        "customer_id": customer_id or "?",
        "object_id": obj.get("id", "?"),
        "source": source,
        "bought": bought,
        "amount": _amount(obj),
        "user_found": bool(user),
        "has_paid": (user.get("has_paid") if user else ""),
        "db_plan": (user.get("subscription_plan") if user else ""),
        "verdict": verdict,
        "note": note,
    }


def _report(rows, args):
    order = {"LIKELY_UNCREDITED": 0, "USER_NOT_FOUND": 1, "PENDING/UNPAID": 2, "REVIEW": 3, "OK": 4, "CREDITED": 5}
    rows.sort(key=lambda r: (order.get(r["verdict"], 9), r["created"]))

    cols = ["created", "verdict", "email", "amount", "bought", "source", "has_paid", "db_plan", "object_id", "note"]
    widths = {c: max(len(c), *(len(str(r[c])) for r in rows)) if rows else len(c) for c in cols}
    line = "  ".join(c.upper().ljust(widths[c]) for c in cols)
    print(line)
    print("-" * len(line))
    for r in rows:
        print("  ".join(str(r[c]).ljust(widths[c]) for c in cols))

    from collections import Counter
    counts = Counter(r["verdict"] for r in rows)
    print("\nSummary:", dict(counts))
    flagged = [r for r in rows if r["verdict"] in ("LIKELY_UNCREDITED", "USER_NOT_FOUND")]
    print(f"\n[!] {len(flagged)} payment(s) need restoration/investigation:")
    for r in flagged:
        print(f"  - {r['email']}  {r['amount']}  {r['bought']}  ({r['object_id']})")

    if args.csv:
        with open(args.csv, "w", newline="", encoding="utf-8") as f:
            w = _csv.DictWriter(f, fieldnames=cols)
            w.writeheader()
            for r in rows:
                w.writerow({c: r[c] for c in cols})
        print(f"\nCSV written: {args.csv}")


if __name__ == "__main__":
    p = argparse.ArgumentParser(description="Find paid-but-uncredited Stripe customers (read-only).")
    g = p.add_mutually_exclusive_group()
    g.add_argument("--since", default=SINCE_DEFAULT, help="UTC date YYYY-MM-DD (default 2026-06-23)")
    g.add_argument("--days", type=int, help="look back this many days instead of --since")
    p.add_argument("--csv", help="also write results to this CSV path")
    reconcile(p.parse_args())
