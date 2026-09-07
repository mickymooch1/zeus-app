# Memorial Product Section Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship `/memorials` (landing), `/memorials/create` (simplified wizard), and
`/memorial/:token` (public + owner memorial page), backed by a new one-off
"Memorial Package" Stripe purchase that's fully isolated from subscription
credits.

**Architecture:** Reuses the existing song-generation engine
(`POST /api/songs/generate` + `generationPoller.js`), the existing share-token,
photo-upload, and occasion systems unchanged at the data layer, and the existing
credit-ledger idempotency mechanism (`record_credit_grant`) for the new payment
path. Two existing frontend pieces (`PhotoCarousel`, `SongCard`) get extracted
into shared components so the memorial page can reuse them instead of
duplicating OAuth/polling logic.

**Tech Stack:** FastAPI + SQLite (backend/), React Router v6 + Vite (web-beats/),
Stripe Checkout Sessions (`mode: "payment"`), `qrcode.react`, plain `node --test`
for frontend logic tests, `pytest` for backend.

**Spec:** `docs/superpowers/specs/2026-09-07-memorial-product-section-design.md`

## Global Constraints

- `stripe>=15,<16` is already pinned (`backend/requirements.txt:16`) — do not
  touch this pin.
- Memorial checkout requires an account — no `customer_email`-only guest path
  (spec decision).
- Flat pricing, single SKU (`memorial_default`) — no tiers.
- `/memorial/:token` resolves **tokens only** — the frontend never constructs
  this URL with a numeric id.
- `/memorials`, `/memorials/create`, and any pricing/checkout UI must be gated
  `!isIOSWebView` (`web-beats/src/hooks/useIsIOSWebView.js`) per existing App
  Store compliance policy.
- Frontend has no component-rendering test framework — only plain `node --test`
  over `.test.mjs` files testing pure logic (confirmed: no vitest, no
  `@testing-library/react`, no jsdom installed). Do not write component-render
  tests; test extracted pure logic instead, and note where a task has no
  automated test because it's a thin presentational component.
- Every credit-ledger interaction for the new "memorial" credit type must go
  through `db.record_credit_grant`/`db.get_credit_grant` (already idempotent,
  keyed on `(stripe_payment_id, credit_type)`) — never a bare counter increment
  outside that gate.

## Implementation note vs. the spec

The spec (§3) describes extending `POST /api/songs/generate` to accept
`occasion`/`occasion_name`/`tribute_message` directly at creation time. Research
during planning found the actual `song_variants` row insert and per-genre credit
deduction happen inside `songs.generate_multiple_variants` (songs.py), not in
the `main.py` handler — so accepting those three fields there would mean
touching that function's signature. Instead: `POST /api/songs/generate` gains a
much smaller `is_memorial: bool` flag used **only** for credit gating (Task 6);
the wizard sets `occasion`/`occasion_name`/`tribute_message` via the existing
`POST /api/songs/variants/{id}/occasion` endpoint (extended in Task 5)
immediately after generation returns a `variant_id` — exactly the two-step
sequence `SongsPage.jsx` already uses today for non-memorial songs. Same
end-user behavior, no change to `songs.py`.

---

### Task 1: Memorial credit columns + db.py helpers

**Files:**
- Modify: `backend/db.py` (migration list inside `init_user_tables`, near the
  existing `occasion`/`share_token` `ALTER TABLE` lines)
- Modify: `backend/db.py` (new functions, placed near `increment_song_credits`)
- Test: `backend/tests/test_memorial_credits.py` (new)

**Interfaces:**
- Produces: `db.increment_memorial_credits(db_path, user_id, amount) -> None`,
  `db.decrement_memorial_credits(db_path, user_id, amount) -> None`,
  `db.decrement_song_credits(db_path, user_id, amount) -> None`,
  `users.memorial_credits_available` column,
  `song_variants.tribute_message` column.

- [ ] **Step 1: Write the failing tests**

```python
# backend/tests/test_memorial_credits.py
import os, pathlib, sys
import pytest

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))
os.environ.setdefault("ANTHROPIC_API_KEY", "test-key-for-tests")
import db


@pytest.fixture
def db_path(tmp_path):
    p = tmp_path / "t.db"
    db.init_user_tables(p)
    return p


@pytest.fixture
def user(db_path):
    return db.create_user(db_path, "buyer@test.com", "x", "Buyer", "2026-01-01")


def test_new_user_has_zero_memorial_credits(db_path, user):
    row = db.get_user_by_id(db_path, user["id"])
    assert row["memorial_credits_available"] == 0


def test_increment_memorial_credits(db_path, user):
    db.increment_memorial_credits(db_path, user["id"], 1)
    row = db.get_user_by_id(db_path, user["id"])
    assert row["memorial_credits_available"] == 1


def test_decrement_memorial_credits(db_path, user):
    db.increment_memorial_credits(db_path, user["id"], 2)
    db.decrement_memorial_credits(db_path, user["id"], 1)
    row = db.get_user_by_id(db_path, user["id"])
    assert row["memorial_credits_available"] == 1


def test_decrement_memorial_credits_floors_at_zero(db_path, user):
    db.decrement_memorial_credits(db_path, user["id"], 1)
    row = db.get_user_by_id(db_path, user["id"])
    assert row["memorial_credits_available"] == 0


def test_decrement_song_credits_floors_at_zero(db_path, user):
    db.upsert_song_credits(db_path, user["id"], balance=0, monthly_allowance=0)
    db.decrement_song_credits(db_path, user["id"], 1)
    c = db.get_song_credits(db_path, user["id"])
    assert c["balance"] == 0


def test_song_variant_tribute_message_column_exists(db_path, user):
    conn = db._conn(db_path)
    try:
        cols = [r[1] for r in conn.execute("PRAGMA table_info(song_variants)").fetchall()]
        assert "tribute_message" in cols
    finally:
        conn.close()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && python -m pytest tests/test_memorial_credits.py -v`
Expected: FAIL — `memorial_credits_available`/`tribute_message` columns don't
exist yet, `increment_memorial_credits`/etc. not defined.

- [ ] **Step 3: Add the migration lines**

In `backend/db.py`, find the migration list inside `init_user_tables` (the
linear list of `CREATE TABLE IF NOT EXISTS` / `ALTER TABLE ... ADD COLUMN`
strings — the existing `occasion`/`occasion_name` and `share_token` lines are
in this same list). Append:

```python
    "ALTER TABLE users ADD COLUMN memorial_credits_available INTEGER NOT NULL DEFAULT 0",
    "ALTER TABLE song_variants ADD COLUMN tribute_message TEXT",
```

- [ ] **Step 4: Add the db.py helper functions**

Place near `increment_song_credits`:

```python
def increment_memorial_credits(db_path: pathlib.Path, user_id: str, amount: int) -> None:
    conn = _conn(db_path)
    try:
        conn.execute(
            "UPDATE users SET memorial_credits_available = memorial_credits_available + ? WHERE id = ?",
            (amount, user_id),
        )
        conn.commit()
    finally:
        conn.close()


def decrement_memorial_credits(db_path: pathlib.Path, user_id: str, amount: int) -> None:
    conn = _conn(db_path)
    try:
        conn.execute(
            "UPDATE users SET memorial_credits_available = MAX(memorial_credits_available - ?, 0) WHERE id = ?",
            (amount, user_id),
        )
        conn.commit()
    finally:
        conn.close()


def decrement_song_credits(db_path: pathlib.Path, user_id: str, amount: int) -> None:
    conn = _conn(db_path)
    try:
        conn.execute(
            "UPDATE song_credits SET balance = MAX(balance - ?, 0) WHERE user_id = ?",
            (amount, user_id),
        )
        conn.commit()
    finally:
        conn.close()
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd backend && python -m pytest tests/test_memorial_credits.py -v`
Expected: PASS (6/6)

- [ ] **Step 6: Commit**

```bash
git add backend/db.py backend/tests/test_memorial_credits.py
git commit -m "$(cat <<'EOF'
feat: add memorial credit balance and tribute_message column

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01CgDcKoZT1GFwsuPbUBPiSg
EOF
)"
```

---

### Task 2: Memorial Package Stripe checkout session

**Files:**
- Modify: `backend/billing.py` (new `MEMORIAL_PACKS` dict + `create_memorial_checkout_session`, placed near `SONG_PACKS`/`create_song_pack_checkout_session`)
- Test: `backend/tests/test_memorial_checkout.py` (new)

**Interfaces:**
- Consumes: nothing new (uses `_get_stripe()`, already in billing.py).
- Produces: `billing.MEMORIAL_PACKS` (dict, one entry: `"memorial_default"`),
  `billing.create_memorial_checkout_session(user, success_url, cancel_url) -> str`.

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_memorial_checkout.py
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_memorial_checkout.py -v`
Expected: FAIL — `billing.MEMORIAL_PACKS` / `create_memorial_checkout_session`
not defined.

- [ ] **Step 3: Add MEMORIAL_PACKS and create_memorial_checkout_session**

In `backend/billing.py`, near `SONG_PACKS`:

```python
MEMORIAL_PACKS = {
    "memorial_default": {
        "credits": 1, "label": "Memorial Package", "price": "£49",
        "price_id": os.environ.get("STRIPE_MEMORIAL_PACKAGE_PRICE_ID", ""),
    },
}


def create_memorial_checkout_session(user: dict, success_url: str, cancel_url: str) -> str:
    """Create a one-time Stripe Checkout Session for a Memorial Package purchase.
    Account required — always keyed to a logged-in user, no guest customer_email-only path
    beyond what create_song_pack_checkout_session already does for an account with no
    stripe_customer_id yet."""
    stripe = _get_stripe()
    pack = "memorial_default"
    price_id = MEMORIAL_PACKS[pack]["price_id"]
    if not price_id:
        raise ValueError("No Stripe price ID configured for the Memorial Package — set STRIPE_MEMORIAL_PACKAGE_PRICE_ID")
    customer_id = user.get("stripe_customer_id")
    params: dict = {
        "payment_method_types": ["card"],
        "line_items": [{"price": price_id, "quantity": 1}],
        "mode": "payment",
        "success_url": success_url,
        "cancel_url": cancel_url,
        "metadata": {"user_id": user["id"], "memorial_package": pack},
        "payment_intent_data": {"metadata": {"user_id": user["id"], "memorial_package": pack}},
    }
    if customer_id:
        params["customer"] = customer_id
    else:
        params["customer_email"] = user["email"]
    session = stripe.checkout.Session.create(**params)
    return session.url
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/test_memorial_checkout.py -v`
Expected: PASS (2/2)

- [ ] **Step 5: Commit**

```bash
git add backend/billing.py backend/tests/test_memorial_checkout.py
git commit -m "$(cat <<'EOF'
feat: add Memorial Package one-off Stripe checkout session

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01CgDcKoZT1GFwsuPbUBPiSg
EOF
)"
```

---

### Task 3: `POST /api/memorials/checkout` route

**Files:**
- Modify: `backend/main.py` (new route, placed near the existing `POST /api/songs/payg` route)
- Test: `backend/tests/test_memorial_checkout_route.py` (new)

**Interfaces:**
- Consumes: `billing.create_memorial_checkout_session` (Task 2),
  `billing.stripe_enabled()` (existing), `auth.get_current_user` (existing).
- Produces: `POST /api/memorials/checkout` → `{"url": str}`.

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_memorial_checkout_route.py
import importlib, os, pathlib, sys
from unittest.mock import patch
import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))
os.environ.setdefault("ANTHROPIC_API_KEY", "test-key-for-tests")


@pytest.fixture()
def app_client(tmp_path, monkeypatch):
    monkeypatch.setenv("ZEUS_DATA_DIR", str(tmp_path))
    import db as _db
    importlib.reload(_db)
    db_path = _db.get_db_path()
    user = _db.create_user(db_path, email="buyer@example.com", password_hash="x", name="Buyer", tc_accepted_at="now")
    import main as _main
    importlib.reload(_main)
    client = TestClient(_main.app)
    token = _main.auth.create_access_token({"sub": user["id"]})
    return client, _db, _main, db_path, user, token


def test_memorial_checkout_requires_auth(app_client):
    client, *_ = app_client
    resp = client.post("/api/memorials/checkout")
    assert resp.status_code in (401, 403)


def test_memorial_checkout_returns_url(app_client):
    client, _db, _main, db_path, user, token = app_client
    with patch.object(_main.billing, "create_memorial_checkout_session", return_value="https://checkout.stripe.com/xyz"):
        resp = client.post(
            "/api/memorials/checkout",
            headers={"Authorization": f"Bearer {token}"},
        )
    assert resp.status_code == 200
    assert resp.json()["url"] == "https://checkout.stripe.com/xyz"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_memorial_checkout_route.py -v`
Expected: FAIL — 404, route doesn't exist yet.

- [ ] **Step 3: Add the route**

In `backend/main.py`, near `POST /api/songs/payg`:

```python
@app.post("/api/memorials/checkout")
async def memorials_checkout(
    current_user: dict = Depends(auth.get_current_user),
):
    if not billing.stripe_enabled():
        raise HTTPException(status_code=503, detail="Billing is not configured")
    origin = os.environ.get("FRONTEND_URL", "https://zeusbeats.com")
    success_url = f"{origin}/memorials/create?checkout=success"
    cancel_url = f"{origin}/memorials"
    try:
        url = billing.create_memorial_checkout_session(current_user, success_url, cancel_url)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception:
        log.exception("Memorial checkout error")
        raise HTTPException(status_code=500, detail="Failed to create checkout session")
    return {"url": url}
```

(If `create_access_token`/token-header conventions in the test above don't
match this codebase's actual auth test helper, check how
`backend/tests/test_song_photos.py` or `test_occasion.py` authenticate a
`TestClient` request and use that same helper instead — the assertions are
what matter, not the exact auth plumbing in the test.)

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/test_memorial_checkout_route.py -v`
Expected: PASS (2/2)

- [ ] **Step 5: Commit**

```bash
git add backend/main.py backend/tests/test_memorial_checkout_route.py
git commit -m "$(cat <<'EOF'
feat: add POST /api/memorials/checkout route

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01CgDcKoZT1GFwsuPbUBPiSg
EOF
)"
```

---

### Task 4: Webhook grant branches (checkout + payment_intent backup)

**Files:**
- Modify: `backend/billing.py` (`_grant_topup`, `_handle_checkout_completed`, `_handle_payment_intent_succeeded`)
- Test: `backend/tests/test_memorial_billing_idempotency.py` (new, mirrors `test_billing_idempotency.py`)

**Interfaces:**
- Consumes: `db.record_credit_grant`, `db.increment_memorial_credits` (Task 1),
  `billing.MEMORIAL_PACKS` (Task 2).
- Produces: memorial purchases granted idempotently through both webhook paths.

- [ ] **Step 1: Write the failing tests**

```python
# backend/tests/test_memorial_billing_idempotency.py
import os, pathlib, sys
import pytest

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))
os.environ.setdefault("ANTHROPIC_API_KEY", "test-key-for-tests")
import db
import billing


@pytest.fixture
def db_path(tmp_path):
    p = tmp_path / "t.db"
    db.init_user_tables(p)
    return p


@pytest.fixture
def user(db_path):
    return db.create_user(db_path, "buyer@test.com", "x", "Buyer", "2026-01-01")


def _memorial_session(pi="pi_mem_1", email="buyer@test.com"):
    return {
        "id": "cs_mem_1", "object": "checkout.session", "mode": "payment",
        "payment_status": "paid", "customer": "cus_1", "customer_email": email,
        "payment_intent": pi, "amount_total": 4900, "currency": "gbp",
        "metadata": {"memorial_package": "memorial_default", "user_id": ""},
    }


def _memorial_balance(db_path, uid):
    return db.get_user_by_id(db_path, uid)["memorial_credits_available"]


class TestMemorialTopupIdempotency:
    def test_checkout_grants_and_records_ledger(self, db_path, user):
        billing._handle_checkout_completed(db_path, _memorial_session())
        assert _memorial_balance(db_path, user["id"]) == 1
        grant = db.get_credit_grant(db_path, "pi_mem_1", "memorial")
        assert grant is not None
        assert grant["amount"] == 1

    def test_replayed_checkout_does_not_double_grant(self, db_path, user):
        billing._handle_checkout_completed(db_path, _memorial_session())
        billing._handle_checkout_completed(db_path, _memorial_session())
        assert _memorial_balance(db_path, user["id"]) == 1

    def test_payment_intent_backup_after_checkout_no_double_grant(self, db_path, user):
        billing._handle_checkout_completed(db_path, _memorial_session(pi="pi_mem_9"))
        pi = {"id": "pi_mem_9", "object": "payment_intent", "customer": "cus_1",
              "metadata": {"memorial_package": "memorial_default", "user_id": user["id"]}}
        billing._handle_payment_intent_succeeded(db_path, pi)
        assert _memorial_balance(db_path, user["id"]) == 1

    def test_payment_intent_alone_grants_when_checkout_never_fired(self, db_path, user):
        pi = {"id": "pi_mem_10", "object": "payment_intent", "customer": "cus_1",
              "metadata": {"memorial_package": "memorial_default", "user_id": user["id"]}}
        billing._handle_payment_intent_succeeded(db_path, pi)
        assert _memorial_balance(db_path, user["id"]) == 1

    def test_unrecognised_memorial_pack_does_not_crash_and_alerts(self, db_path, user, monkeypatch):
        called = {}
        monkeypatch.setattr(billing._alerts, "alert_credit_not_granted", lambda *a, **kw: called.setdefault("fired", True))
        session = _memorial_session()
        session["metadata"]["memorial_package"] = "nonexistent_pack"
        billing._handle_checkout_completed(db_path, session)
        assert _memorial_balance(db_path, user["id"]) == 0
        assert called.get("fired") is True
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && python -m pytest tests/test_memorial_billing_idempotency.py -v`
Expected: FAIL — memorial purchases aren't recognized by either handler yet
(balance stays 0, no ledger row).

- [ ] **Step 3: Extend `_grant_topup` with a memorial branch**

In `backend/billing.py`, inside `_grant_topup`, change:

```python
    if credit_type == "song":
        db.increment_song_credits(db_path, user["id"], credits)
    else:
        db.increment_premium_credits(db_path, user["id"], credits)
```

to:

```python
    if credit_type == "song":
        db.increment_song_credits(db_path, user["id"], credits)
    elif credit_type == "memorial":
        db.increment_memorial_credits(db_path, user["id"], credits)
    else:
        db.increment_premium_credits(db_path, user["id"], credits)
```

And the pack-config lookup line at the bottom of `_grant_topup`:

```python
    _pack_cfg = (SONG_PACKS if credit_type == "song" else ANIMATION_PACKS if credit_type == "premium" else MEMORIAL_PACKS).get(pack, {})
```

- [ ] **Step 4: Add the memorial branch to `_handle_checkout_completed`**

In the `mode == "payment"` block, alongside the existing `pack`/`anim_pack`
reads, add:

```python
        memorial_pack = session.get("metadata", {}).get("memorial_package")
```

Then extend the `if pack ... elif anim_pack ...` chain:

```python
        elif memorial_pack and memorial_pack in MEMORIAL_PACKS:
            if user:
                _grant_topup(db_path, user, "memorial", MEMORIAL_PACKS[memorial_pack]["credits"], "checkout_topup", pi_id, memorial_pack, amount_display)
            else:
                _alerts.alert_credit_not_granted(customer_email or "", amount_display, f"memorial top-up {memorial_pack}: user not found", pi_id or session_id)
        else:
            log.warning("checkout.session.completed payment: unrecognised pack song=%r anim=%r memorial=%r — ignoring", pack, anim_pack, memorial_pack)
            _alerts.alert_credit_not_granted(customer_email or "", amount_display, f"unrecognised pack (song={pack!r} anim={anim_pack!r} memorial={memorial_pack!r})", pi_id or session_id)
```

(This replaces the existing final `else` branch — keep everything above it
unchanged, just add the `memorial_pack` read and the new `elif` before that
`else`, and fold `memorial_pack` into the `else`'s log/alert message.)

- [ ] **Step 5: Add the memorial branch to `_handle_payment_intent_succeeded`**

Critical: the early-return guard must also check `memorial_pack`, or the Apple
Pay backup path silently skips memorial purchases:

```python
    song_pack = metadata.get("song_pack")
    anim_pack = metadata.get("animation_pack")
    memorial_pack = metadata.get("memorial_package")
    customer_id = payment_intent.get("customer")

    if not song_pack and not anim_pack and not memorial_pack:
        log.info("payment_intent.succeeded: no pack metadata — subscription payment, ignoring")
        return
```

And extend the final dispatch:

```python
    if song_pack and song_pack in SONG_PACKS:
        _grant_topup(db_path, user, "song", SONG_PACKS[song_pack]["credits"], "payment_intent_topup", pi_id, song_pack, amount_display)
    elif anim_pack and anim_pack in ANIMATION_PACKS:
        _grant_topup(db_path, user, "premium", ANIMATION_PACKS[anim_pack]["credits"], "payment_intent_topup", pi_id, anim_pack, amount_display)
    elif memorial_pack and memorial_pack in MEMORIAL_PACKS:
        _grant_topup(db_path, user, "memorial", MEMORIAL_PACKS[memorial_pack]["credits"], "payment_intent_topup", pi_id, memorial_pack, amount_display)
    else:
        _alerts.alert_credit_not_granted(user.get("email") or "", amount_display, f"payment_intent: unrecognised pack (song={song_pack!r} anim={anim_pack!r} memorial={memorial_pack!r})", pi_id)
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `cd backend && python -m pytest tests/test_memorial_billing_idempotency.py -v`
Expected: PASS (5/5)

- [ ] **Step 7: Run the full existing billing test suite to confirm no regression**

Run: `cd backend && python -m pytest tests/test_billing_idempotency.py tests/test_billing_safety_net.py -v`
Expected: PASS, unchanged (song/animation branches untouched in behavior).

- [ ] **Step 8: Commit**

```bash
git add backend/billing.py backend/tests/test_memorial_billing_idempotency.py
git commit -m "$(cat <<'EOF'
feat: grant Memorial Package credits idempotently via both webhook paths

Reuses the credit-ledger idempotency gate from the 2026-07-10 billing
safety net — same no-double-grant guarantee as song/animation top-ups.

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01CgDcKoZT1GFwsuPbUBPiSg
EOF
)"
```

---

### Task 5: Tribute message on the occasion endpoint

**Files:**
- Modify: `backend/main.py` (`SetOccasionRequest` model + `set_variant_occasion` handler)
- Test: `backend/tests/test_occasion.py` (extend existing file)

**Interfaces:**
- Produces: `POST /api/songs/variants/{id}/occasion` now also accepts/returns
  `tribute_message`.

- [ ] **Step 1: Write the failing test**

Add to `backend/tests/test_occasion.py`:

```python
def test_set_occasion_with_tribute_message(app_client):
    client, _db, _main, db_path, _, _ = app_client
    client.post("/api/songs/variants/1/occasion", json={
        "occasion": "memorial", "occasion_name": "Alex", "tribute_message": "Loved by everyone who met him.",
    })
    variant = _db.get_song_variant_by_id(db_path, 1)
    assert variant["tribute_message"] == "Loved by everyone who met him."


def test_tribute_message_over_1000_chars_rejected(app_client):
    client, _db, _main, db_path, _, _ = app_client
    resp = client.post("/api/songs/variants/1/occasion", json={
        "occasion": "memorial", "tribute_message": "x" * 1001,
    })
    assert resp.status_code == 400
```

(Match the exact `app_client` fixture shape already used elsewhere in this
file — it's the 5-tuple `(client, _db, _main, db_path, _)` already established
by the existing tests in this file, e.g. `test_whatsapp_crawler_gets_song`.)

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && python -m pytest tests/test_occasion.py -k tribute -v`
Expected: FAIL — `tribute_message` field/column not wired up in this endpoint.

- [ ] **Step 3: Extend the request model and handler**

In `backend/main.py`, find `class SetOccasionRequest` and add a field:

```python
class SetOccasionRequest(BaseModel):
    occasion: str | None = None
    occasion_name: str | None = None
    tribute_message: str | None = None
```

In `set_variant_occasion`, after the existing `occasion_name` line, add:

```python
    tribute_message = (body.tribute_message or "").strip() or None
    if tribute_message and len(tribute_message) > 1000:
        raise HTTPException(status_code=400, detail="Tribute message must be 1000 characters or fewer")
```

And update the persist + response lines:

```python
    db.update_song_variant(db_path, variant_id, occasion=occasion, occasion_name=occasion_name, tribute_message=tribute_message)
    return {"variant_id": variant_id, "occasion": occasion, "occasion_name": occasion_name, "tribute_message": tribute_message}
```

Check `db.update_song_variant`'s current signature: if it takes explicit
named kwargs (rather than `**kwargs` passed straight to a dynamic `UPDATE`),
add `tribute_message` to its parameter list and its `SET` clause the same way
`occasion_name` is already handled there.

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && python -m pytest tests/test_occasion.py -v`
Expected: PASS, including all pre-existing tests in this file (no regressions).

- [ ] **Step 5: Commit**

```bash
git add backend/main.py backend/tests/test_occasion.py
git commit -m "$(cat <<'EOF'
feat: accept tribute_message on the occasion endpoint

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01CgDcKoZT1GFwsuPbUBPiSg
EOF
)"
```

---

### Task 6: Memorial-credit gating on `POST /api/songs/generate`

**Files:**
- Modify: `backend/main.py` (`SongsGenerateRequest` model + `songs_generate` handler)
- Test: `backend/tests/test_memorial_generate_gating.py` (new)

**Interfaces:**
- Consumes: `db.decrement_memorial_credits`, `db.increment_memorial_credits`,
  `db.decrement_song_credits`, `db.increment_song_credits` (Task 1).
- Produces: `POST /api/songs/generate` accepts `is_memorial: bool = False`;
  when true, consumes `memorial_credits_available` instead of subscription
  song credits, net-zero effect on the song credit balance.

- [ ] **Step 1: Write the failing tests**

```python
# backend/tests/test_memorial_generate_gating.py
import importlib, os, pathlib, sys
from unittest.mock import patch
import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))
os.environ.setdefault("ANTHROPIC_API_KEY", "test-key-for-tests")


@pytest.fixture()
def app_client(tmp_path, monkeypatch):
    monkeypatch.setenv("ZEUS_DATA_DIR", str(tmp_path))
    import db as _db
    importlib.reload(_db)
    db_path = _db.get_db_path()
    user = _db.create_user(db_path, email="buyer@example.com", password_hash="x", name="Buyer", tc_accepted_at="now")
    _db.update_user(db_path, user["id"], email_verified=1)
    import main as _main
    importlib.reload(_main)
    client = TestClient(_main.app)
    token = _main.auth.create_access_token({"sub": user["id"]})
    return client, _db, _main, db_path, user, token


def _headers(token):
    return {"Authorization": f"Bearer {token}"}


def test_memorial_generate_without_credits_returns_402(app_client):
    client, _db, _main, db_path, user, token = app_client
    resp = client.post("/api/songs/generate", json={
        "genres": ["pop"], "brief": "a memorial song", "is_memorial": True,
    }, headers=_headers(token))
    assert resp.status_code == 402
    assert _db.get_user_by_id(db_path, user["id"])["memorial_credits_available"] == 0


def test_memorial_generate_consumes_memorial_credit_not_song_credit(app_client):
    client, _db, _main, db_path, user, token = app_client
    _db.increment_memorial_credits(db_path, user["id"], 1)
    _db.upsert_song_credits(db_path, user["id"], balance=0, monthly_allowance=0)

    fake_result = {"variants": [{"variant_id": 1, "status": "pending"}]}
    with patch.object(_main._songs_mod if hasattr(_main, "_songs_mod") else _main.songs, "generate_multiple_variants", return_value=fake_result):
        resp = client.post("/api/songs/generate", json={
            "genres": ["pop"], "brief": "a memorial song", "is_memorial": True,
        }, headers=_headers(token))

    assert resp.status_code == 200
    assert _db.get_user_by_id(db_path, user["id"])["memorial_credits_available"] == 0
    assert _db.get_song_credits(db_path, user["id"])["balance"] == 0


def test_memorial_generate_failure_rolls_back_memorial_credit(app_client):
    client, _db, _main, db_path, user, token = app_client
    _db.increment_memorial_credits(db_path, user["id"], 1)
    _db.upsert_song_credits(db_path, user["id"], balance=0, monthly_allowance=0)

    target = _main._songs_mod if hasattr(_main, "_songs_mod") else _main.songs
    with patch.object(target, "generate_multiple_variants", side_effect=ValueError("boom")):
        resp = client.post("/api/songs/generate", json={
            "genres": ["pop"], "brief": "a memorial song", "is_memorial": True,
        }, headers=_headers(token))

    assert resp.status_code == 400
    assert _db.get_user_by_id(db_path, user["id"])["memorial_credits_available"] == 1
    assert _db.get_song_credits(db_path, user["id"])["balance"] == 0


def test_non_memorial_generate_unaffected(app_client):
    client, _db, _main, db_path, user, token = app_client
    _db.upsert_song_credits(db_path, user["id"], balance=1, monthly_allowance=0)

    fake_result = {"variants": [{"variant_id": 1, "status": "pending"}]}
    target = _main._songs_mod if hasattr(_main, "_songs_mod") else _main.songs
    with patch.object(target, "generate_multiple_variants", return_value=fake_result):
        resp = client.post("/api/songs/generate", json={
            "genres": ["pop"], "brief": "a normal song",
        }, headers=_headers(token))

    assert resp.status_code == 200
    assert _db.get_user_by_id(db_path, user["id"])["memorial_credits_available"] == 0
```

Note: the exact mock target (`_main._songs_mod` vs `_main.songs` vs
`patch("songs.generate_multiple_variants", ...)`) depends on how `main.py`
imports the `songs` module at the call site (`import songs as _songs_mod`
inside the handler, per Task-6 research, means patching must target
`songs.generate_multiple_variants` directly — i.e. `patch("songs.generate_multiple_variants", ...)` — since the import happens fresh
inside the function body each call rather than at module load time as an
attribute of `main`). Adjust the `patch.object(...)` calls above to
`patch("songs.generate_multiple_variants", ...)` if the first form doesn't
take effect (check by running Step 2 and reading the failure).

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && python -m pytest tests/test_memorial_generate_gating.py -v`
Expected: FAIL — `is_memorial` field ignored, no gating logic yet, first test
likely gets a different status code than 402 (probably passes through to
normal credit-precheck logic and fails differently, or 500).

- [ ] **Step 3: Add `is_memorial` to `SongsGenerateRequest`**

Grep `class SongsGenerateRequest` in `backend/main.py` and add:

```python
    is_memorial: bool = False
```

- [ ] **Step 4: Add the memorial gating block**

In the `songs_generate` handler, immediately after the existing block:

```python
    credits_row = db.get_song_credits(db_path, user_id)
    if credits_row is None:
        db.upsert_song_credits(db_path, user_id, balance=billing.FREE_SONG_CREDITS, monthly_allowance=0)
        credits_row = db.get_song_credits(db_path, user_id)
```

and **before** the `# ── Credit pre-check` block, insert:

```python
    # ── Memorial credit gating ──────────────────────────────────────────────
    # A Memorial Package purchase pays for the song outright — it must not
    # touch the user's subscription/song credit balance (memorial spec §3).
    # Grant a temporary 1 song credit here (consumed by the existing
    # precheck/deduction below) and debit memorial_credits_available instead;
    # net effect on the song credit balance is zero. Rolled back in the
    # except blocks below if generation fails.
    _memorial_temp_credit_granted = False
    if body.is_memorial:
        _memorial_balance = db.get_user_by_id(db_path, user_id)["memorial_credits_available"]
        if _memorial_balance < 1:
            raise HTTPException(status_code=402, detail="No memorial credits available — purchase a Memorial Package first")
        db.decrement_memorial_credits(db_path, user_id, 1)
        db.increment_song_credits(db_path, user_id, 1)
        _memorial_temp_credit_granted = True
        credits_row = db.get_song_credits(db_path, user_id)
```

- [ ] **Step 5: Add rollback to the three except blocks**

Find:

```python
    except InsufficientCreditsError as exc:
        raise HTTPException(status_code=402, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Song submission failed: {exc}")
```

Replace with:

```python
    except InsufficientCreditsError as exc:
        if _memorial_temp_credit_granted:
            db.increment_memorial_credits(db_path, user_id, 1)
            db.decrement_song_credits(db_path, user_id, 1)
        raise HTTPException(status_code=402, detail=str(exc))
    except ValueError as exc:
        if _memorial_temp_credit_granted:
            db.increment_memorial_credits(db_path, user_id, 1)
            db.decrement_song_credits(db_path, user_id, 1)
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        if _memorial_temp_credit_granted:
            db.increment_memorial_credits(db_path, user_id, 1)
            db.decrement_song_credits(db_path, user_id, 1)
        raise HTTPException(status_code=500, detail=f"Song submission failed: {exc}")
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `cd backend && python -m pytest tests/test_memorial_generate_gating.py -v`
Expected: PASS (4/4)

- [ ] **Step 7: Run the full songs_generate test suite to confirm no regression**

Run: `cd backend && python -m pytest tests/ -k generate -v`
Expected: PASS, unchanged for non-memorial requests.

- [ ] **Step 8: Commit**

```bash
git add backend/main.py backend/tests/test_memorial_generate_gating.py
git commit -m "$(cat <<'EOF'
feat: gate memorial song generation on memorial_credits_available

Memorial credit is consumed instead of subscription/song credits, with
rollback on generation failure.

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01CgDcKoZT1GFwsuPbUBPiSg
EOF
)"
```

---

### Task 7: Photo cap raised to 10 for memorial variants

**Files:**
- Modify: `backend/main.py` (`upload_song_photo` handler)
- Test: `backend/tests/test_song_photos.py` (extend existing file)

**Interfaces:**
- Produces: photo upload allows 10 photos when `variant.occasion == 'memorial'`,
  still 5 otherwise.

- [ ] **Step 1: Write the failing test**

Add to `backend/tests/test_song_photos.py` (using its existing `app_client`
fixture and its variant-200 seed row — insert a second variant with
`occasion='memorial'` for this test, e.g. id 201, same shape as the existing
seed):

```python
def test_memorial_variant_allows_10_photos(app_client):
    client, _db, db_path, owner, other = app_client
    conn = _db._conn(db_path)
    try:
        conn.execute("""INSERT INTO song_variants (id, lyric_id, user_id, genre_tag, style_prompt, take_number, status, mp3_url, image_url, duration_seconds, occasion, created_at)
               VALUES (201, 1, ?, 'pop', 'a pop track', 1, 'complete', 'http://a.mp3', 'http://i.png', 180, 'memorial', datetime('now'))""", (owner["id"],))
        conn.commit()
    finally:
        conn.close()

    for i in range(10):
        resp = client.post(
            "/api/songs/variants/201/photos",
            files={"file": (f"p{i}.jpg", b"\xff\xd8\xff\xe0fakejpegdata", "image/jpeg")},
            headers=_auth_headers(owner),  # match whatever helper this file already uses for auth
        )
        assert resp.status_code == 200, resp.text

    resp = client.post(
        "/api/songs/variants/201/photos",
        files={"file": ("p11.jpg", b"\xff\xd8\xff\xe0fakejpegdata", "image/jpeg")},
        headers=_auth_headers(owner),
    )
    assert resp.status_code == 400
    assert "10" in resp.json()["detail"]
```

(Match the existing file's actual auth-header helper name/shape — inspect the
existing passing tests in `test_song_photos.py` for how they authenticate as
`owner` and reuse that exact helper instead of the placeholder
`_auth_headers` name above.)

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_song_photos.py -k memorial -v`
Expected: FAIL — 11th photo also rejected at count 5, not 10 (cap is still
hardcoded to 5).

- [ ] **Step 3: Make the cap conditional**

In `backend/main.py`'s `upload_song_photo` handler, find:

```python
    if db.count_song_variant_photos(db_path, variant_id) >= _PHOTO_MAX_COUNT:
        raise HTTPException(status_code=400, detail=f"Maximum {_PHOTO_MAX_COUNT} photos per song")
```

Replace with:

```python
    _photo_cap = 10 if variant.get("occasion") == "memorial" else _PHOTO_MAX_COUNT
    if db.count_song_variant_photos(db_path, variant_id) >= _photo_cap:
        raise HTTPException(status_code=400, detail=f"Maximum {_photo_cap} photos per song")
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && python -m pytest tests/test_song_photos.py -v`
Expected: PASS, including all pre-existing tests (non-memorial variants still
capped at 5).

- [ ] **Step 5: Commit**

```bash
git add backend/main.py backend/tests/test_song_photos.py
git commit -m "$(cat <<'EOF'
feat: allow up to 10 photos for memorial-occasion songs

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01CgDcKoZT1GFwsuPbUBPiSg
EOF
)"
```

---

### Task 8: Extract `PhotoCarousel` into a shared component

**Files:**
- Create: `web-beats/src/components/PhotoCarousel.jsx`
- Modify: `web-beats/src/pages/SongSharePage.jsx` (remove inline definition,
  import from the new file)

**Interfaces:**
- Produces: `import PhotoCarousel from '../components/PhotoCarousel'` —
  same props signature as the current inline component.

- [ ] **Step 1: Read the current inline component**

Read `web-beats/src/pages/SongSharePage.jsx` lines 111–210 (the full
`PhotoCarousel` component, per prior research) to get its exact current props
and implementation.

- [ ] **Step 2: Create the new file with the component moved verbatim**

Create `web-beats/src/components/PhotoCarousel.jsx` containing exactly what
was read in Step 1 (component body unchanged), plus whatever imports it uses
(e.g. `useState`, `useEffect` from `react`) at the top, and `export default
PhotoCarousel;` (or match whatever export style `SongSharePage.jsx` currently
uses internally) at the bottom.

- [ ] **Step 3: Replace the inline definition in SongSharePage.jsx**

Delete the component body from `SongSharePage.jsx` and add near the top of
the file:

```jsx
import PhotoCarousel from '../components/PhotoCarousel';
```

Leave every call site of `<PhotoCarousel ... />` in `SongSharePage.jsx`
unchanged — this is a pure extraction, no prop or behavior changes.

- [ ] **Step 4: Verify no regressions**

Run: `cd web-beats && npm test`
Expected: PASS, same results as before this task (this is logic-only test
coverage — there's no component-render test to catch a broken extraction, so
also grep for any other file importing `PhotoCarousel` from `SongSharePage.jsx`
directly (`grep -rn "PhotoCarousel" web-beats/src`) and confirm none exist yet
besides `SongSharePage.jsx` itself).

- [ ] **Step 5: Commit**

```bash
git add web-beats/src/components/PhotoCarousel.jsx web-beats/src/pages/SongSharePage.jsx
git commit -m "$(cat <<'EOF'
refactor: extract PhotoCarousel into a shared component

No behavior change — enables reuse from the new memorial page.

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01CgDcKoZT1GFwsuPbUBPiSg
EOF
)"
```

---

### Task 9: Extract `SongCard` into a shared component

**Files:**
- Create: `web-beats/src/components/SongCard.jsx`
- Modify: `web-beats/src/pages/SongsPage.jsx` (remove inline definition, import
  from the new file; keep the two call sites at ~4672/4852 unchanged)

**Interfaces:**
- Produces: `import SongCard from '../components/SongCard'` — same props
  signature as the current inline component. This unblocks Task 14's "More
  song tools" section, which reuses this component instead of re-implementing
  YouTube-OAuth/D-ID Avatar/Stems polling logic.

- [ ] **Step 1: Read the current inline component and its dependencies**

Read `web-beats/src/pages/SongsPage.jsx`:
- Lines 512–1606 (the full `SongCard` component body, per prior research —
  confirmed `memo()`-wrapped and purely props-driven, closing over nothing but
  props plus the module-level constants below).
- Lines ~48–92 (genre-label maps it references).
- Line ~311 (`actionBtnStyle`).
- Line ~498 (`OCCASION_OPTIONS`).
- Line ~506 (`UPGRADE_FEATURES`).

- [ ] **Step 2: Create the new file**

Create `web-beats/src/components/SongCard.jsx` containing: the `SongCard`
component body moved verbatim, plus the small module-level constants it
references (genre-label maps, `actionBtnStyle`, `OCCASION_OPTIONS`,
`UPGRADE_FEATURES`) either moved alongside it or imported from
`SongsPage.jsx` if any of those constants are also used elsewhere in
`SongsPage.jsx` outside `SongCard` (check each one's other usages before
deciding whether to move or share it — if a constant is used both inside and
outside `SongCard` in `SongsPage.jsx`, move it into `SongCard.jsx` and export
it, then import it back into `SongsPage.jsx` from there, rather than
duplicating it).

- [ ] **Step 3: Replace the inline definition in SongsPage.jsx**

Delete the component body (and any constants moved out in Step 2) from
`SongsPage.jsx`, add:

```jsx
import SongCard from '../components/SongCard';
```

Leave the two `<SongCard ... />` call sites (~4672, ~4852) unchanged — same
props in, same props out.

- [ ] **Step 4: Verify no regressions**

Run: `cd web-beats && npm test`
Expected: PASS, unchanged.

Run: `grep -rn "SongCard" web-beats/src` to confirm only `SongsPage.jsx`
(import + 2 call sites) and the new `components/SongCard.jsx` reference it —
no other file broke.

Since there's no component-render test infrastructure in this repo, also do a
manual check per the "run" skill if available: start the dev server, open
`/songs` while logged in with at least one existing song, and confirm a song
card still renders with all its action buttons (Telegram, YouTube, Avatar,
Stems, Remake, QR, Photos) working as before. Note in the task's completion
report whether this manual check was actually performed or whether it was
skipped (and why) — don't claim it passed without having done it.

- [ ] **Step 5: Commit**

```bash
git add web-beats/src/components/SongCard.jsx web-beats/src/pages/SongsPage.jsx
git commit -m "$(cat <<'EOF'
refactor: extract SongCard into a shared component

No behavior change — enables reuse from the new memorial page's "More
song tools" section instead of duplicating YouTube-OAuth/Avatar/Stems
polling logic.

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01CgDcKoZT1GFwsuPbUBPiSg
EOF
)"
```

---

### Task 10: `CollapsibleSection` component

**Files:**
- Create: `web-beats/src/components/CollapsibleSection.jsx`

**Interfaces:**
- Produces: `<CollapsibleSection title="More song tools">{children}</CollapsibleSection>`
  — internal open/close state, chevron toggle button, matches the visual
  pattern already used ad hoc for Stems/QR/Photos panels in `SongCard.jsx`
  (▲/▼ chevron on a full-width button).

- [ ] **Step 1: Create the component**

```jsx
// web-beats/src/components/CollapsibleSection.jsx
import { useState } from 'react';

export default function CollapsibleSection({ title, defaultOpen = false, children }) {
  const [open, setOpen] = useState(defaultOpen);
  return (
    <div>
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        style={{
          width: '100%',
          textAlign: 'left',
          background: 'none',
          border: 'none',
          cursor: 'pointer',
          padding: '8px 0',
          fontWeight: 600,
        }}
        aria-expanded={open}
      >
        {title} {open ? '▲' : '▼'}
      </button>
      {open && <div>{children}</div>}
    </div>
  );
}
```

This is a small, purely presentational component with no logic worth a
`node --test` unit test (per the Global Constraints note on this repo's
testing conventions) — no test step for this task.

- [ ] **Step 2: Commit**

```bash
git add web-beats/src/components/CollapsibleSection.jsx
git commit -m "$(cat <<'EOF'
feat: add reusable CollapsibleSection component

First shared instance of the open/close-panel pattern every SongCard
panel (Stems/QR/Photos) currently hand-rolls independently.

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01CgDcKoZT1GFwsuPbUBPiSg
EOF
)"
```

---

### Task 11: Routes — `/memorials`, `/memorials/create`, `/memorial/:token`

**Files:**
- Modify: `web-beats/src/App.jsx` (add lazy imports + three `<Route>` entries)

**Interfaces:**
- Consumes: `SchoolSafeRoute` (existing, `components/ProtectedRoute.jsx`).
- Produces: routes wired to `MemorialsLandingPage` (Task 12),
  `MemorialWizardPage` (Task 13), `MemorialPage` (Task 14) — created as empty
  placeholder-free stub components in this task so the routes resolve, then
  fleshed out in their own tasks. (To avoid a genuinely empty/placeholder
  component violating the No Placeholders rule, this task's stub renders real,
  minimal content: `"Loading…"` — a legitimate temporary loading state, not a
  TODO — and Tasks 12–14 replace it with the real page.)

- [ ] **Step 1: Add lazy imports**

In `web-beats/src/App.jsx`, alongside the existing `lazy()` imports (matching
the exact pattern the `/songs/share/:variantId` import already uses), add:

```jsx
const MemorialsLandingPage = lazy(() => import('./pages/MemorialsLandingPage'));
const MemorialWizardPage = lazy(() => import('./pages/MemorialWizardPage'));
const MemorialPage = lazy(() => import('./pages/MemorialPage'));
```

- [ ] **Step 2: Create minimal stub page files**

For each of the three, create the file with real (not placeholder) minimal
content so the app builds and the route resolves, e.g.:

```jsx
// web-beats/src/pages/MemorialsLandingPage.jsx
export default function MemorialsLandingPage() {
  return <div>Loading…</div>;
}
```

(repeat for `MemorialWizardPage.jsx` and `MemorialPage.jsx`, same body). These
get replaced with real content in Tasks 12–14.

- [ ] **Step 3: Add the three routes**

Add near the existing `/songs/share/:variantId` route (public, unwrapped):

```jsx
<Route path="/memorials" element={<MemorialsLandingPage />} />
<Route path="/memorial/:token" element={<MemorialPage />} />
```

Add near an existing `SchoolSafeRoute`-wrapped route (e.g. `/songs`), matching
its exact wrapping pattern:

```jsx
<Route path="/memorials/create" element={<SchoolSafeRoute><MemorialWizardPage /></SchoolSafeRoute>} />
```

- [ ] **Step 4: Verify the app builds and routes resolve**

Run: `cd web-beats && npm run build`
Expected: build succeeds.

Manually verify (via the `run` skill if available): start the dev server,
navigate to `/memorials`, `/memorials/create` (should redirect to `/login` if
logged out — that's `SchoolSafeRoute` working correctly), and
`/memorial/anything` — each should render the stub page or redirect, not
error.

- [ ] **Step 5: Commit**

```bash
git add web-beats/src/App.jsx web-beats/src/pages/MemorialsLandingPage.jsx web-beats/src/pages/MemorialWizardPage.jsx web-beats/src/pages/MemorialPage.jsx
git commit -m "$(cat <<'EOF'
feat: wire up /memorials, /memorials/create, /memorial/:token routes

Stub pages fleshed out in subsequent tasks.

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01CgDcKoZT1GFwsuPbUBPiSg
EOF
)"
```

---

### Task 12: `MemorialsLandingPage.jsx`

**Files:**
- Modify: `web-beats/src/pages/MemorialsLandingPage.jsx` (replace stub)

**Interfaces:**
- Consumes: `isIOSWebView` (`hooks/useIsIOSWebView.js`), `POST /api/memorials/checkout`
  (Task 3), auth context (however `SongsPage.jsx`/`BillingPage.jsx` currently
  access the logged-in user — check `BillingPage.jsx`'s import for the exact
  auth hook/context name and reuse it).

- [ ] **Step 1: Implement the landing page**

```jsx
// web-beats/src/pages/MemorialsLandingPage.jsx
import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { isIOSWebView } from '../hooks/useIsIOSWebView';
import IOSWebViewBanner from '../components/IOSWebViewBanner';
// Check BillingPage.jsx for the exact auth hook/context this app uses
// (e.g. `useAuth()` from a context, or a token read from localStorage) and
// import the same thing here instead of guessing at a new pattern.
import { useAuth } from '../context/AuthContext';

const BACKEND_URL = import.meta.env.VITE_BACKEND_URL || '';

export default function MemorialsLandingPage() {
  const navigate = useNavigate();
  const { user, token } = useAuth();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  async function handleCreate() {
    if (isIOSWebView) return; // CTA is hidden below in this case anyway
    if (!user) {
      navigate('/login?next=/memorials');
      return;
    }
    setLoading(true);
    setError('');
    try {
      if ((user.memorial_credits_available || 0) > 0) {
        navigate('/memorials/create');
        return;
      }
      const resp = await fetch(`${BACKEND_URL}/api/memorials/checkout`, {
        method: 'POST',
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!resp.ok) throw new Error('Could not start checkout');
      const data = await resp.json();
      window.location.href = data.url;
    } catch (err) {
      setError('Something went wrong — please try again.');
    } finally {
      setLoading(false);
    }
  }

  return (
    <div style={{ maxWidth: 640, margin: '0 auto', padding: '64px 24px', textAlign: 'center' }}>
      <h1 style={{ fontSize: 32, fontWeight: 600 }}>Create a Lasting Memorial Tribute</h1>
      <p style={{ opacity: 0.8, marginTop: 12 }}>
        Personalised song • Up to 10 photos • Slideshow • Memorial page • Permanent QR code
      </p>
      {isIOSWebView ? (
        <IOSWebViewBanner message="Visit zeusbeats.com to create a Memorial." />
      ) : (
        <>
          <button
            type="button"
            onClick={handleCreate}
            disabled={loading}
            style={{ marginTop: 32, padding: '14px 32px', fontSize: 16, borderRadius: 8, cursor: 'pointer' }}
          >
            {loading ? 'One moment…' : 'Create a Memorial'}
          </button>
          {error && <p style={{ color: 'crimson', marginTop: 12 }}>{error}</p>}
        </>
      )}
    </div>
  );
}
```

If `useAuth`/`AuthContext` isn't the actual name used in this codebase, grep
`BillingPage.jsx`'s imports for the real hook and substitute it — same for
`IOSWebViewBanner`'s exact import path and prop name (`message` is a guess;
check its actual prop signature at
`web-beats/src/components/IOSWebViewBanner.jsx` and match it).

- [ ] **Step 2: Verify manually**

Run the dev server (via the `run` skill if available), visit `/memorials`
logged out → click "Create a Memorial" → should redirect to
`/login?next=/memorials`. Log in as a user with 0 memorial credits → click
again → should hit the checkout route and redirect toward Stripe (safe to stop
short of completing a real payment here — Task 15 covers the full purchase).

- [ ] **Step 3: Commit**

```bash
git add web-beats/src/pages/MemorialsLandingPage.jsx
git commit -m "$(cat <<'EOF'
feat: build the /memorials landing page

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01CgDcKoZT1GFwsuPbUBPiSg
EOF
)"
```

---

### Task 13: `MemorialWizardPage.jsx`

**Files:**
- Modify: `web-beats/src/pages/MemorialWizardPage.jsx` (replace stub)

**Interfaces:**
- Consumes: `startGenerationPoll` (`utils/generationPoller.js`, existing),
  `POST /api/songs/generate` with `is_memorial: true` (Task 6),
  `POST /api/songs/variants/{id}/occasion` with `tribute_message` (Task 5),
  existing photo upload endpoint (`POST /api/songs/variants/{id}/photos`, now
  capped at 10 for memorial per Task 7), existing `mark-qr-generated` endpoint,
  `qrcode.react`.

- [ ] **Step 1: Implement the six-step wizard**

```jsx
// web-beats/src/pages/MemorialWizardPage.jsx
import { useState, useRef } from 'react';
import { QRCodeCanvas } from 'qrcode.react';
import { startGenerationPoll } from '../utils/generationPoller';
import { useAuth } from '../context/AuthContext'; // match SongsPage.jsx's actual import

const BACKEND_URL = import.meta.env.VITE_BACKEND_URL || '';
const STEPS = ['name', 'memories', 'song', 'photos', 'review', 'qr'];

export default function MemorialWizardPage() {
  const { token } = useAuth();
  const [stepIndex, setStepIndex] = useState(0);
  const [name, setName] = useState('');
  const [tribute, setTribute] = useState('');
  const [variantId, setVariantId] = useState(null);
  const [shareToken, setShareToken] = useState(null);
  const [songStatus, setSongStatus] = useState('idle'); // idle | generating | complete | failed
  const [photos, setPhotos] = useState([]);
  const [error, setError] = useState('');
  const pollRef = useRef(null);

  const step = STEPS[stepIndex];
  const next = () => setStepIndex((i) => Math.min(i + 1, STEPS.length - 1));
  const back = () => setStepIndex((i) => Math.max(i - 1, 0));

  async function generateSong() {
    setSongStatus('generating');
    setError('');
    try {
      const resp = await fetch(`${BACKEND_URL}/api/songs/generate`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
        body: JSON.stringify({
          genres: ['ambient'],
          brief: tribute || `A memorial song for ${name}`,
          is_memorial: true,
        }),
      });
      if (resp.status === 402) {
        setError('No memorial credits available — please purchase a Memorial Package.');
        setSongStatus('failed');
        return;
      }
      if (!resp.ok) throw new Error('Generation failed to start');
      const data = await resp.json();
      const firstVariant = data.variants[0];
      setVariantId(firstVariant.variant_id);

      pollRef.current = startGenerationPoll({
        trackedIds: [firstVariant.variant_id],
        fetchVariants: async () => {
          const r = await fetch(`${BACKEND_URL}/api/lyrics/${data.lyric_id}/variants`, {
            headers: { Authorization: `Bearer ${token}` },
          });
          return (await r.json()).variants;
        },
        onUpdate: () => {},
        onSettled: async (variants) => {
          const done = variants.find((v) => v.id === firstVariant.variant_id);
          if (done?.status === 'complete') {
            await fetch(`${BACKEND_URL}/api/songs/variants/${firstVariant.variant_id}/occasion`, {
              method: 'POST',
              headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
              body: JSON.stringify({ occasion: 'memorial', occasion_name: name, tribute_message: tribute }),
            });
            setSongStatus('complete');
            next();
          } else {
            setSongStatus('failed');
            setError('Song generation failed — please try again.');
          }
        },
        onTrouble: () => {},
      });
    } catch (err) {
      setSongStatus('failed');
      setError('Something went wrong starting generation.');
    }
  }

  async function uploadPhoto(file) {
    const form = new FormData();
    form.append('file', file);
    const resp = await fetch(`${BACKEND_URL}/api/songs/variants/${variantId}/photos`, {
      method: 'POST',
      headers: { Authorization: `Bearer ${token}` },
      body: form,
    });
    if (resp.ok) {
      const data = await resp.json();
      setPhotos((p) => [...p, data]);
      if (data.share_token) setShareToken(data.share_token);
    }
  }

  async function fetchShareToken() {
    const resp = await fetch(`${BACKEND_URL}/api/songs/variants/${variantId}/public`, {
      headers: { Authorization: `Bearer ${token}` },
    });
    if (resp.ok) {
      const data = await resp.json();
      if (data.share_token) setShareToken(data.share_token);
    }
  }

  async function markQrGenerated() {
    await fetch(`${BACKEND_URL}/api/songs/variants/${variantId}/mark-qr-generated`, {
      method: 'POST',
      headers: { Authorization: `Bearer ${token}` },
    });
  }

  return (
    <div style={{ maxWidth: 480, margin: '0 auto', padding: '48px 24px' }}>
      {step === 'name' && (
        <div>
          <h2>Whose memorial is this for?</h2>
          <input value={name} onChange={(e) => setName(e.target.value)} placeholder="Name" />
          <button type="button" onClick={next} disabled={!name.trim()}>Next</button>
        </div>
      )}
      {step === 'memories' && (
        <div>
          <h2>Share a memory or tribute</h2>
          <textarea
            value={tribute}
            onChange={(e) => setTribute(e.target.value.slice(0, 1000))}
            placeholder="In loving memory of..."
            rows={6}
          />
          <button type="button" onClick={back}>Back</button>
          <button type="button" onClick={next}>Next</button>
        </div>
      )}
      {step === 'song' && (
        <div>
          <h2>Create the song</h2>
          {songStatus === 'idle' && <button type="button" onClick={generateSong}>Create Song</button>}
          {songStatus === 'generating' && <p>Creating your song…</p>}
          {songStatus === 'failed' && <p style={{ color: 'crimson' }}>{error}</p>}
          <button type="button" onClick={back}>Back</button>
        </div>
      )}
      {step === 'photos' && (
        <div>
          <h2>Add photos (up to 10)</h2>
          <input
            type="file"
            accept="image/*,.heic,.heif"
            disabled={photos.length >= 10}
            onChange={(e) => e.target.files[0] && uploadPhoto(e.target.files[0])}
          />
          <p>{photos.length}/10 photos</p>
          <button type="button" onClick={async () => { await fetchShareToken(); next(); }}>Next</button>
        </div>
      )}
      {step === 'review' && (
        <div>
          <h2>Review</h2>
          <p>{name}</p>
          <p>{tribute}</p>
          <p>{photos.length} photo(s) added</p>
          <button type="button" disabled title="Coming soon">Download plaque artwork — coming soon</button>
          <button type="button" onClick={next}>Next</button>
        </div>
      )}
      {step === 'qr' && shareToken && (
        <div>
          <h2>Your memorial page is ready</h2>
          <p>{`${window.location.origin}/memorial/${shareToken}`}</p>
          <QRCodeCanvas value={`${window.location.origin}/memorial/${shareToken}`} size={200} id="memorial-qr" />
          <button
            type="button"
            onClick={async () => {
              const canvas = document.getElementById('memorial-qr');
              const url = canvas.toDataURL('image/png');
              const a = document.createElement('a');
              a.href = url;
              a.download = 'memorial-qr.png';
              a.click();
              await markQrGenerated();
            }}
          >
            Download QR code
          </button>
        </div>
      )}
    </div>
  );
}
```

Cross-check against `SongsPage.jsx`'s actual QR-download implementation
(`handleQrDownload`, ~line 640–675) and photo-upload fetch call for the exact
existing request/response shapes (field names like `share_token` in the photo
upload response are assumed above — verify against the real endpoint response
shape and adjust if it differs) before treating this as final.

- [ ] **Step 2: Verify manually end-to-end (no real Stripe purchase required for this step)**

Via the `run` skill if available: as a logged-in test user, manually grant
yourself a memorial credit (`db.increment_memorial_credits` via a Python
shell against the dev DB, or a temporary test-only endpoint), then walk
through all six steps and confirm a real song generates, photos upload, and a
QR renders pointing at `/memorial/{token}`.

- [ ] **Step 3: Commit**

```bash
git add web-beats/src/pages/MemorialWizardPage.jsx
git commit -m "$(cat <<'EOF'
feat: build the memorial creation wizard

Name -> Memories -> Song -> Photos -> Review -> QR, reusing the existing
generation poller, photo upload, and occasion endpoints.

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01CgDcKoZT1GFwsuPbUBPiSg
EOF
)"
```

---

### Task 14: `MemorialPage.jsx` — public + owner view

**Files:**
- Modify: `web-beats/src/pages/MemorialPage.jsx` (replace stub)

**Interfaces:**
- Consumes: `PhotoCarousel` (Task 8), `SongCard` (Task 9), `CollapsibleSection`
  (Task 10), `GET /api/songs/variants/{token}/public` (existing),
  `POST /api/songs/variants/{id}/occasion` (existing, extended Task 5).

- [ ] **Step 1: Implement token-shape validation + fetch**

```jsx
// web-beats/src/pages/MemorialPage.jsx
import { useEffect, useState } from 'react';
import { useParams } from 'react-router-dom';
import PhotoCarousel from '../components/PhotoCarousel';
import SongCard from '../components/SongCard';
import CollapsibleSection from '../components/CollapsibleSection';
import { useAuth } from '../context/AuthContext'; // match the real hook name used elsewhere

const BACKEND_URL = import.meta.env.VITE_BACKEND_URL || '';
// Share tokens are generated via secrets.token_urlsafe(24) (backend/db.py,
// get_or_create_share_token) — urlsafe base64, no padding, ~32 chars. A
// purely numeric string never matches this and must not be sent to the
// network — that's the enumeration-safety guard from the spec.
const TOKEN_SHAPE = /^[A-Za-z0-9_-]{16,}$/;

export default function MemorialPage() {
  const { token } = useParams();
  const { user, token: authToken } = useAuth();
  const [data, setData] = useState(null);
  const [notFound, setNotFound] = useState(false);
  const [isOwner, setIsOwner] = useState(false);

  useEffect(() => {
    document.title = 'Memorial';
    const meta = document.createElement('meta');
    meta.name = 'robots';
    meta.content = 'noindex, nofollow';
    document.head.appendChild(meta);
    return () => document.head.removeChild(meta);
  }, []);

  useEffect(() => {
    if (!TOKEN_SHAPE.test(token || '')) {
      setNotFound(true);
      return;
    }
    fetch(`${BACKEND_URL}/api/songs/variants/${token}/public`)
      .then((r) => {
        if (!r.ok) throw new Error('not found');
        return r.json();
      })
      .then((json) => {
        setData(json);
        if (user && authToken) {
          fetch(`${BACKEND_URL}/api/songs/variants/${json.variant_id}`, {
            headers: { Authorization: `Bearer ${authToken}` },
          }).then((r) => setIsOwner(r.ok));
        }
      })
      .catch(() => setNotFound(true));
  }, [token, user, authToken]);

  if (notFound) return <div>This memorial page could not be found.</div>;
  if (!data) return <div>Loading…</div>;

  return (
    <div style={{ maxWidth: 640, margin: '0 auto', padding: '48px 24px' }}>
      <h1>{data.occasion_name}</h1>
      {data.tribute_message && <p>{data.tribute_message}</p>}
      {data.photos?.length > 0 && <PhotoCarousel photos={data.photos} />}
      <audio controls src={data.mp3_url} />

      {isOwner && (
        <div style={{ marginTop: 32 }}>
          <h2>Manage this memorial</h2>
          {/* Edit name/tribute, photo add/remove, QR download reuse the same
              endpoints as MemorialWizardPage's Photos/QR steps (Task 13) —
              a follow-up UI-only task can factor those into a shared form if
              duplication becomes a problem; out of scope here per YAGNI. */}
          <CollapsibleSection title="More song tools">
            <SongCard variant={data} />
          </CollapsibleSection>
        </div>
      )}
    </div>
  );
}
```

Cross-check `GET /api/songs/variants/{identifier}/public`'s actual response
shape (field names like `occasion_name`, `tribute_message`, `photos`,
`mp3_url`, `variant_id`) against `SongSharePage.jsx`'s existing fetch/render
code (lines 224–256 per prior research) and correct any field-name mismatches
above before treating this as final — `SongSharePage.jsx` is the ground truth
for this endpoint's actual response shape since it already consumes it.

Also verify `SongCard`'s actual prop name (assumed `variant` above) matches
what Task 9's extraction produced, and that passing the `/public` payload
directly satisfies it — `SongCard` in `SongsPage.jsx` is normally fed from an
authenticated fetch of the user's own variant list, which may have a richer
shape than the public payload. If fields `SongCard` needs (e.g. an auth token
for its action buttons) aren't present in `data`, fetch the fuller
authenticated variant instead of the public payload once `isOwner` is
confirmed, and use that for the `SongCard` render.

- [ ] **Step 2: Verify manually**

Via the `run` skill if available: visit a real `/memorial/{token}` for a
memorial-occasion song created in Task 13's manual check, logged out (public
view — no edit controls, no "More song tools") and logged in as the owner
(owner view — "More song tools" collapsible present, expands to the real
SongCard actions). Visit `/memorial/12345` (numeric) and confirm it renders
"could not be found" without a network request (check the browser network tab).

- [ ] **Step 3: Commit**

```bash
git add web-beats/src/pages/MemorialPage.jsx
git commit -m "$(cat <<'EOF'
feat: build the public + owner memorial page

Token-only lookup (numeric ids rejected client-side before any network
call); owner view adds edit controls plus a collapsed "More song tools"
section reusing the extracted SongCard.

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01CgDcKoZT1GFwsuPbUBPiSg
EOF
)"
```

---

### Task 15: End-to-end Stripe test-mode verification (manual, required before launch)

**Files:** none (verification task, no code changes expected unless it
surfaces a bug — if it does, fix it, add a regression test in the relevant
earlier task's test file, then redo this task from the top).

This is the task the user specifically asked to see the result of before
calling the feature done — same rigor as the manual verification that would
have caught the 2026-07 billing gap before it shipped.

**Prerequisite (one-time, outside this plan's code):** a real Stripe test-mode
Product + Price for the Memorial Package must exist, with its price id set as
`STRIPE_MEMORIAL_PACKAGE_PRICE_ID` in the staging/dev environment. This is a
Stripe dashboard + environment-variable step, not a code change — do this
before Step 1 below, and stop and ask the user to do it if you don't have
Stripe dashboard access.

- [ ] **Step 1: Confirm test-mode environment**

Confirm `STRIPE_SECRET_KEY` (or however this codebase names it — check
`billing.py`'s `_get_stripe()`) is a `sk_test_...` key in the environment
you're about to run this in. Never run this task against a live key.

- [ ] **Step 2: Full purchase — checkout to credit**

As a real logged-in test account with `memorial_credits_available == 0`:
1. Visit `/memorials`, click "Create a Memorial".
2. Complete Stripe Checkout with a Stripe test card (`4242 4242 4242 4242`,
   any future expiry, any CVC).
3. Confirm redirect back to `/memorials/create?checkout=success`.
4. Query the dev DB directly: confirm `users.memorial_credits_available == 1`
   for this account, and a matching row in `credit_ledger` with
   `credit_type='memorial'`, `stripe_payment_id` set to the real
   `payment_intent` id from this purchase.

Record: pass/fail, the actual `payment_intent` id used, and the
`memorial_credits_available` value observed.

- [ ] **Step 3: Song generation consumes the memorial credit, not subscription credits**

Note the account's `song_credits.balance` before starting the wizard. Walk
through the wizard (Task 13) to completion.
1. Confirm the song generates successfully.
2. Query the DB: `memorial_credits_available` is now `0`.
3. Query the DB: `song_credits.balance` is unchanged from the value noted
   before starting (net zero — Task 6's gating logic).

Record: pass/fail, before/after `song_credits.balance`, before/after
`memorial_credits_available`.

- [ ] **Step 4: Webhook redelivery does not double-charge or double-grant**

Using the Stripe CLI in test mode (`stripe trigger checkout.session.completed`
replayed against the same event, or `stripe events resend <event_id>` for the
real event from Step 2 if the CLI supports resending a captured event —
whichever this environment's Stripe CLI setup supports): redeliver the exact
webhook event from Step 2's purchase.
1. Query the DB: `memorial_credits_available` for this account is still
   whatever it was before this redelivery (should NOT increase again — it was
   already consumed in Step 3, so redelivery should leave it at `0`, not `1`).
2. Confirm no second row was inserted into `credit_ledger` for the same
   `(stripe_payment_id, credit_type='memorial')` pair (the `UNIQUE` constraint
   plus `record_credit_grant`'s `ON CONFLICT DO NOTHING` should have silently
   no-opped — confirm via a DB query, not just absence of an error).
3. Check application logs for the `DUPLICATE credit grant skipped` log line
   from `_grant_topup` — its presence confirms the idempotency gate actually
   fired rather than the redelivery simply not reaching the handler for an
   unrelated reason.

Record: pass/fail, whether the dedupe log line appeared, final
`memorial_credits_available` and `credit_ledger` row count for this
`payment_intent`.

- [ ] **Step 5: Report the result**

Write up the pass/fail outcome of Steps 2–4 (with the recorded values) as a
message back to the user — this is the specific deliverable they asked to see
before calling this feature done. If any step failed, do not mark this task
complete — fix the underlying issue (in the relevant earlier task), add a
regression test for it there, and redo this task from Step 1.

---

## Self-review notes

- **Spec coverage:** §1 routes → Task 11; §2 data model → Tasks 1, 7; §3
  payment/entitlement → Tasks 2, 3, 4, 6; §4 wizard → Task 13; §5 public/owner
  page + more-tools collapse → Tasks 8, 9, 10, 14; §6 plaque artwork (stub) →
  Task 13's Review step; iOS compliance → Tasks 12/13 gating. All covered.
- **Placeholder scan:** the only literal `"Loading…"` text is a real interim
  loading/stub state used deliberately in Task 11 (replaced by Tasks 12–14),
  not a TODO — left in per the No-Placeholders exception for genuine loading
  states.
- **Type/name consistency:** `is_memorial` (generate request),
  `memorial_credits_available` (user column), `tribute_message` (variant
  column), `MEMORIAL_PACKS`/`"memorial_default"` (billing), and
  `credit_type="memorial"` are used identically across every task that
  touches them.
- **Known follow-up, not blocking:** Task 14's owner-edit controls (name/
  tribute/photo editing UI, distinct from the "More song tools" collapse)
  are noted inline but not fully built out with wizard-parity forms — flagged
  in Task 14 as an explicit YAGNI deferral rather than silently dropped;
  worth a small follow-up task once the core flow is live and real memorial
  owners ask for edits.
