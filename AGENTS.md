# Zeus Beats — Project Conventions

## Temporary / one-off patches must be marked

Any code that is a genuine one-off or temporary patch — not a permanent
behavior change — must be marked clearly, so it's grep-able and can't be
silently forgotten. This covers things like: capping or overriding a
specific user's data to unblock them urgently, a manual data correction, a
stopgap shipped before the real fix, a debug/diagnostic block added to chase
down one incident, etc.

Mark every such patch with a comment in this exact form:

```
# TEMP FIX (YYYY-MM-DD) — remove once <condition>
```

Example:

```python
# TEMP FIX (2026-09-16) — remove once laky120@yahoo.com confirms her
# credits look right. Unblocks her immediately; the real fix is the
# renewal-allowance reconciliation landing in the same commit.
```

**Before writing any one-off/temporary patch:**
- Add the `# TEMP FIX (date) — remove once ...` comment above it.
- Prefer making it self-limiting — a `WHERE` clause (or equivalent guard)
  that only matches the broken state, so re-running it after the real fix
  lands is a no-op — over relying on someone remembering to delete the code.
- If it touches a specific user's data (credits, subscription, account
  flags, etc.), treat it like any other production billing/customer-data
  change: check with Michael before shipping it.
- Once the underlying issue is actually fixed, remove the patch. A `# TEMP
  FIX` comment with no removal is exactly the failure mode this rule exists
  to prevent.

**Why this exists:** On 2026-09-16, four unmarked, unguarded "one-time"
patches were found still running on every single deploy — months after they
were written to fix one-off incidents. One of them (targeting
laky120@yahoo.com) silently re-capped a paying customer's song credits below
her plan's real allowance on every redeploy, directly contradicting Zeus
Beats' own "credits never expire" promise. None of the four were marked or
gated to run once. See `backend/billing.py`'s
`reconcile_stale_credit_override()` and the commit that removed them for the
full incident.

This rule applies to any agent or developer working in this repo — Claude
Code, Codex, or a human.
