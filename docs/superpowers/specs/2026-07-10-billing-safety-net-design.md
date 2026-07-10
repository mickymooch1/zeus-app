# Billing Safety Net — credit ledger, idempotent grants, webhook alerts

**Date:** 2026-07-10
**Context:** A stripe-python 15.x upgrade broke `StripeObject.get()`, crashing every
Stripe webhook silently (returned 200 `{"status":"error_logged"}`). PAYG credits went
ungranted for ~2.5 weeks before a customer complaint surfaced it. This spec hardens
billing so the failure class can't recur silently, and closes the double-grant risk.

## Goals

1. **Never silently fail again** — alert Porickbot (Telegram) the moment a paid webhook
   errors or fails to grant credits.
2. **Retroactively verifiable crediting** — a ledger row per grant, so we never again
   have to guess whether a customer was already credited.
3. **No double-grants** — idempotent one-time top-ups keyed on payment_intent id.
4. **Pin stripe** — stop unpinned dependency drift from breaking billing.

## 1. Pin stripe

`backend/requirements.txt`: `stripe>=8.0.0` → `stripe>=15,<16`.

## 2. Credit ledger

New table (created via `init_user_tables`, `CREATE TABLE IF NOT EXISTS` — auto-migrates
on deploy):

```
credit_ledger(
  id                INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id           TEXT NOT NULL,
  email             TEXT,               -- denormalised; reconcile needs no join
  credit_type       TEXT NOT NULL,      -- 'song' | 'premium' | 'video'
  amount            INTEGER NOT NULL,
  source            TEXT NOT NULL,      -- 'checkout_topup' | 'payment_intent_topup'
                                        --  | 'subscription' | 'invoice_renewal' | 'manual'
  stripe_payment_id TEXT,               -- pi_… (one-time), in_…/cs_… (subscription)
  created_at        TEXT NOT NULL,
  UNIQUE(stripe_payment_id, credit_type)
)
```

New DB helpers in `db.py`:

- `record_credit_grant(db_path, user_id, email, credit_type, amount, source, stripe_payment_id) -> bool`
  Inserts via `ON CONFLICT(stripe_payment_id, credit_type) DO NOTHING`. Returns `True`
  if newly recorded, `False` if this (payment_id, type) was already granted.
- `get_credit_grant(db_path, stripe_payment_id, credit_type) -> dict | None` — for reconcile / verification.

## 3. Idempotent top-up grants

The ledger insert **is** the idempotency gate. At each one-time top-up site, record first;
only increment if the record was new:

```python
newly = db.record_credit_grant(db_path, user["id"], email, "song", credits,
                               "checkout_topup", pi_id)
if not newly:
    log.info("DUPLICATE credit grant skipped: song top-up pi=%s already credited", pi_id)
else:
    db.increment_song_credits(db_path, user["id"], credits)
    db.update_user(db_path, user["id"], has_paid=1)
    log.info("CREDITS GRANTED: ...")
```

Applies to all four additive sites, keyed on **payment_intent id**:

- `_handle_checkout_completed` song top-up (was billing.py:632) — `session["payment_intent"]`
- `_handle_checkout_completed` animation top-up (was :642) — `session["payment_intent"]`
- `_handle_payment_intent_succeeded` song top-up (was :809) — `payment_intent["id"]`
- `_handle_payment_intent_succeeded` animation top-up (was :817) — `payment_intent["id"]`

Because checkout.session.completed and the payment_intent.succeeded backup share the same
`payment_intent` id, whichever fires first grants; the second sees the ledger row and skips.
This closes the Apple-Pay overlap (previously only guarded by a comment at billing.py:770)
**and** Stripe delivery-retry double-grants.

If `payment_intent` id is missing (shouldn't happen for paid top-ups), fall back to
incrementing and log a warning — can't dedupe without a key.

Subscription / invoice grants use absolute `upsert_*` (set balance = allowance), which is
already retry-safe, so they are **recorded** for audit (source `subscription` /
`invoice_renewal`, keyed on session / invoice id) but not guarded.

## 4. Safety alerts (Porickbot)

Reuse `alerts.send_admin_alert` (already DMs Porickbot, 30-min dedup suppresses
Stripe-retry spam). Two new fire-and-forget helpers in `alerts.py`:

- `alert_webhook_error(event_type, event_id, error)` — the `error_logged` catch-all.
- `alert_credit_not_granted(email, amount, detail, ref)` — paid but no credit.

Wired at:

- `main.py` — both webhook `except` blocks (`/webhook/stripe`, `/billing/webhook`).
- `billing.py` — the `CREDITS FAILED` (user-not-found) sites and the unrecognised-pack
  branches, where a payment succeeded but no credit was granted.

## 5. Reconcile upgrade

`reconcile_payments.py` consults `get_credit_grant` for one-time top-ups, replacing the
unverifiable `REVIEW` verdict with precise `CREDITED` / `LIKELY_UNCREDITED`.

## Testing (TDD)

- `record_credit_grant`: inserts; second call same (payment_id, type) returns `False`, no
  duplicate row; different credit_type for same payment inserts.
- Replayed checkout top-up increments credits exactly once (idempotency end-to-end,
  temp sqlite db + real user).
- payment_intent backup after checkout for same pi does not double-grant.
- `alert_webhook_error` / `alert_credit_not_granted` call `send_admin_alert` with expected
  content (monkeypatched).
- `main.py` error path and billing user-not-found path trigger an alert (monkeypatched).

## Out of scope

- Widening the backfill window (staying at 2026-06-23 per decision).
- Backfilling the two known-affected customers (done manually via Porickbot).
