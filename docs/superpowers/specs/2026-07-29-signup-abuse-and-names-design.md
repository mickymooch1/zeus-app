# Signup abuse protection + optional name collection

**Date:** 2026-07-29
**Goal:** Stop casual/lazy free-credit farming cheaply, and collect user names for
personalisation — without adding any friction that can block a genuine user.

## Guiding principle

Only two things may ever hard-block a signup:

1. The email domain is a known disposable/throwaway service.
2. The email resolves to an account that already exists (after normalisation).

Everything else — device reuse, IP volume — is a **soft signal** that flags for
review. Families, offices, cafés, student halls and shared devices are normal and
must never be locked out.

The economic backstop is a modest free tier (3 songs), not a fortress. If abuse
gets through, it is worth very little.

## What exists today (and what's wrong with it)

| Current behaviour | Location | Problem |
|---|---|---|
| ~45 disposable domains blocked, exact match only | `main.py:846` | Misses subdomains and several common services (mail-tester, temp-mail.io, …) |
| No email normalisation | — | `name+1@gmail.com`, `name+2@gmail.com`, `n.a.m.e@gmail.com` are three separate free-credit accounts |
| **Hard block: 1 signup per IP per 7 days** | `main.py:858` | Brutal. Blocks the second genuine user on any shared IP for a week; barely slows an abuser with a phone hotspot |
| **Hard block: 1 signup per device fingerprint, ever** | `main.py:875` | Locks out families sharing a laptop, permanently |
| Name field removed from signup form | `RegisterPage.jsx:72` | Sends `''`; no names collected at all |
| Welcome email promises "5 free songs" | `zeus_ops_agent.py:332` | `FREE_SONG_CREDITS = 3` — a broken promise |

## Part 1 — Anti-abuse

### 1a. Disposable domain blocklist (hard block, kept and widened)

New module `backend/signup_guard.py` owns the list. `main._BLOCKED_EMAIL_DOMAINS`
becomes an alias so the existing guard test keeps working.

- Add missing services: `mail-tester.com`, `temp-mail.io`, `tempmail.plus`,
  `minuteinbox.com`, `mailcatch.com`, `dropmail.me`, `tempail.com`,
  `email-temp.com`, `mailtemp.net`, `20minutemail.com`, and similar.
- Match **parent domains** too, so `foo.mailinator.com` is caught by
  `mailinator.com`. Walk the label suffixes; never match a bare TLD.

Message stays user-friendly: "Please use a real email address to register."

### 1b. Email normalisation (hard block on collision)

`signup_guard.normalize_email(email)`:

- Lowercase and trim.
- Strip `+tag` from the local part — **all domains**. Plus-addressing is standard
  across Gmail, Outlook, Proton, Fastmail, iCloud.
- Strip dots from the local part and canonicalise the domain to `gmail.com` —
  **`gmail.com` / `googlemail.com` only**. Dots are genuinely significant on
  other providers, so `john.smith@outlook.com` and `johnsmith@outlook.com` are
  two different real people and must not collide.
- Defensive fallbacks: no `@`, or an empty local part after stripping, returns
  the plain lowercased address rather than something malformed.

Storage: new `users.email_canonical` column, indexed, populated on
`create_user`. Existing rows are backfilled lazily on startup (only rows where
the column is `NULL`, so it costs nothing after the first boot). **No UNIQUE
constraint** — historical duplicates may already exist and must not break
startup or logins.

Signup then rejects with the existing 409 ("An account with that email already
exists") when either the exact email or the canonical form is taken.

### 1c. IP velocity (flag, with a loose script-catcher backstop)

Replaces the 7-day block entirely.

- Every signup attempt is recorded against its IP (`registration_attempts`,
  already exists).
- **Flag** at ≥ 3 signups per IP per 24h: warning log + Telegram alert + row in
  `signup_flags`. Signup proceeds normally.
- **Hard block** only above 10 signups per IP in 1 hour → 429. A family, office
  or café never reaches this; a script farming emails does. Message tells the
  user to try again shortly rather than accusing them.
- `REGISTRATION_ALLOWLIST` env var still exempts known-good IPs from the block.

Thresholds live as named constants in `signup_guard.py` so they're tunable in one
place.

### 1d. Device fingerprint (flag only)

- The hard block at `main.py:875` is removed.
- Every signup records `(fp_hash, user_id)` in a new `device_signups` table
  (no UNIQUE on `fp_hash`, indexed) so repeat use is *countable* — the legacy
  `device_fingerprints` table has `fp_hash UNIQUE`, which by construction can
  only ever hold one account per device. Legacy table keeps being written for
  historical continuity.
- **Flag** when a device has ≥ 2 signups (or appears in the legacy table).
  Never blocks.
- `DEVICE_FINGERPRINT_ALLOWLIST` becomes dead and is removed — nothing blocks on
  fingerprint any more.

### 1e. Flag storage

New table `signup_flags (id, user_id, email, ip_address, reason, detail,
created_at)`. Reasons: `device_reuse`, `ip_velocity`. Written after the user row
exists so it's always attributable. Each flag also emits
`alerts.alert_signup_flag(...)` to Telegram, so patterns are visible without
querying anything.

### 1f. Free tier

`FREE_SONG_CREDITS` stays at **3**. Product Hunt referrals keep their 5. The
welcome email is corrected from "5 free songs" to "3 free songs".

## Part 2 — Name collection (never gates signup)

### 2a. Optional field at signup

`RegisterPage.jsx` gets a name input labelled clearly optional, placed above
email. It is not validated, not required, and an empty value submits fine.
`RegisterRequest.name` gains a `""` default so clients that omit it (iOS) keep
working.

### 2b. Post-first-song prompt

The real capture point — the user has just heard their first track and is warm.

- Hook: `SongsPage.jsx:1584`, where a generation job settles.
- Show a friendly "What should we call you?" modal when: the job produced at
  least one complete variant, the user has no name set, and the prompt hasn't
  been dismissed before (`localStorage: zeus_name_prompt_done`).
- Both "Save" and skip/dismiss are first-class. Skipping costs nothing and never
  reappears.
- Saves via new `PATCH /api/users/name` (max 60 chars, trimmed), then
  `refreshUser()` so the greeting updates immediately.

### 2c. Using the name

- In-app welcome banner greets by first name when known.
- Welcome email greets by name when it was given at signup.
- Stored on `users.name`, which already exists and is already returned by
  `_safe_user`, so the frontend gets it for free.

## Testing

New `backend/tests/test_signup_guard.py` covering:

- `name+1@gmail.com`, `name+2@gmail.com`, `n.a.m.e@gmail.com`,
  `NAME@googlemail.com` all normalise to one canonical address.
- `john.smith@outlook.com` and `johnsmith@outlook.com` stay **distinct**.
- `user+tag@outlook.com` normalises to `user@outlook.com`.
- Disposable detection: exact match, subdomain match, and that a legitimate
  domain (`gmail.com`, `nhs.uk`) is never flagged.
- Malformed input doesn't raise.
- Threshold constants are ordered sanely (flag < block) and the blocklist still
  contains the domains the existing guard test names.

Existing `test_signup_no_verify_gate.py` must keep passing unchanged.

Note: 9 tests already fail on a clean tree in this repo (pre-existing, ordering
pollution in `test_your_sound`). Only a delta against that baseline counts.

## Explicitly out of scope

- CAPTCHA, email verification gates, phone verification, paid-only signup.
- Blocking VPNs or datacentre IP ranges.
- Any change that can tell a genuine user "no".
