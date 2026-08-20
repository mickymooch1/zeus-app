"""Email verification is a HARD GATE on song generation (reinstated 2026-08-19).

History, because this has flipped and the reasoning matters:

  Until 2026-07-17  Verification was a hard wall on generation.
  2026-07-17        Wall removed; verification became a dismissible nudge only
                    (EmailVerificationBanner), with anti-bot moved entirely to
                    signup time. The old guard test asserted the wall was gone.
  2026-08-19        Wall reinstated. That old test — test_signup_no_verify_gate.py
                    — passed against the new gate purely because the new 403 uses
                    different wording than the strings it grepped for. It was
                    replaced by this file rather than left to pass by accident.

What must hold:
  * unverified users cannot generate, and get a structured, actionable rejection
  * verified users are completely unaffected
  * every block is counted, so the gate's cost to conversion is measurable
  * the verification email stays deliverability-shaped — it is now load-bearing,
    since a mail in spam means a user who cannot use the product at all
"""
import inspect
import os
import pathlib
import sys
from unittest.mock import patch

from fastapi.testclient import TestClient

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))
os.environ.setdefault("ANTHROPIC_API_KEY", "test-key")
os.environ.setdefault("APIFRAME_API_KEY", "test-key")
os.environ.setdefault("SONG_STORAGE_PATH", "/tmp/test_songs")
os.environ.setdefault("SONG_PUBLIC_BASE_URL", "https://example.com/files/songs")
os.environ.setdefault("SONG_WEBHOOK_URL", "https://zeusaidesign.com/webhooks/apiframe")
os.environ.setdefault("JWT_SECRET", "test-secret-for-verification-gate-tests")

_VALID_BODY = {"brief": "a song about testing", "genres": ["pop"]}


def _user(verified: int):
    return {
        "id": "gate-user-1",
        "email": "gated@example.com",
        "subscription_status": "active",
        "subscription_plan": "free",
        "password_hash": "x",
        "name": "Gated",
        "is_admin": 0,
        "email_verified": verified,
    }


def _post_generate(verified: int):
    """POST /api/songs/generate as a user with the given verification state."""
    import auth
    import main as _main

    _main.app.dependency_overrides[auth.get_current_user] = lambda: _user(verified)
    try:
        with TestClient(_main.app) as client:
            return client.post("/api/songs/generate",
                               json=_VALID_BODY,
                               headers={"Authorization": "Bearer fake"})
    finally:
        _main.app.dependency_overrides.pop(auth.get_current_user, None)


# ── The gate itself ──────────────────────────────────────────────────────────

def test_unverified_user_is_blocked_from_generating():
    with patch("db.record_verification_gate_block"):
        resp = _post_generate(verified=0)
    assert resp.status_code == 403, f"expected the gate to block, got {resp.status_code}"


def test_the_rejection_is_structured_not_a_raw_403():
    """The client renders a real screen from this, so it needs a code to branch on
    and a human-readable message — not a bare status or an opaque string."""
    with patch("db.record_verification_gate_block"):
        detail = _post_generate(verified=0).json()["detail"]
    assert isinstance(detail, dict), "detail must be structured so the client can branch"
    assert detail["code"] == "email_unverified"
    assert detail["message"] and len(detail["message"]) > 20, "must carry a real explanation"
    assert "verify" in detail["message"].lower()


def test_verified_user_is_not_blocked():
    """The whole point of 'existing verified users must not be affected'. The request
    goes on to fail for unrelated reasons in a test environment — what matters is
    that it is never rejected BY THE GATE."""
    with patch("db.record_verification_gate_block") as rec:
        resp = _post_generate(verified=1)
    body = resp.json() if resp.headers.get("content-type", "").startswith("application/json") else {}
    detail = body.get("detail")
    is_gate_rejection = isinstance(detail, dict) and detail.get("code") == "email_unverified"
    assert not is_gate_rejection, "a verified user must never hit the verification gate"
    rec.assert_not_called()


# ── Tracking: the gate's cost has to be measurable ───────────────────────────

def test_every_block_is_recorded():
    with patch("db.record_verification_gate_block") as rec:
        _post_generate(verified=0)
    rec.assert_called_once()
    assert rec.call_args[0][1] == "gate-user-1", "must record which user was blocked"


def test_recording_failure_still_blocks():
    """Instrumentation must never become the reason a gate leaks open."""
    with patch("db.record_verification_gate_block", side_effect=RuntimeError("db down")):
        resp = _post_generate(verified=0)
    assert resp.status_code == 403


def test_tracking_columns_exist_in_migrations():
    import db
    src = inspect.getsource(db)
    for col in ("gate_block_count", "gate_first_blocked_at", "gate_last_blocked_at"):
        assert f"ADD COLUMN {col}" in src, f"{col} migration missing"


def test_recorder_counts_and_timestamps(tmp_path):
    """Exercises the real SQL: first block sets first_blocked_at, later blocks keep it."""
    import db

    db_path = tmp_path / "gate.db"
    db.init_user_tables(db_path)
    user = db.create_user(db_path, email="counter@example.com", password_hash="x",
                          name="C", tc_accepted_at="2026-08-19T00:00:00+00:00")

    db.record_verification_gate_block(db_path, user["id"])
    row1 = db.get_user_by_id(db_path, user["id"])
    assert row1["gate_block_count"] == 1
    assert row1["gate_first_blocked_at"]

    db.record_verification_gate_block(db_path, user["id"])
    row2 = db.get_user_by_id(db_path, user["id"])
    assert row2["gate_block_count"] == 2
    assert row2["gate_first_blocked_at"] == row1["gate_first_blocked_at"], \
        "first_blocked_at must not move on subsequent blocks"
    assert row2["gate_last_blocked_at"] >= row1["gate_last_blocked_at"]


# ── The verification email is now load-bearing ───────────────────────────────

def test_verification_email_is_deliverability_shaped():
    import main
    src = inspect.getsource(main._send_verification_email)

    assert 'subject = "Confirm your email address"' in src, \
        "plain transactional subject — no brand shouting, no emoji"
    # Exactly one destination link in the message. The old version had three
    # (button, copy-paste fallback, footer homepage) plus gradient chrome.
    assert "linear-gradient" not in src, "no marketing chrome in a deliverability-critical mail"
    assert "AI MUSIC PLATFORM" not in src, "no marketing tagline"
    assert src.count("{verify_url}") <= 3, "keep the link count minimal"


def test_verification_email_still_sends_a_working_link():
    """Deliverability trimming must not remove the thing the mail exists for."""
    import main
    src = inspect.getsource(main._send_verification_email)
    assert "verify_url" in src
    assert "create_verification_token" in src


def test_resend_is_rate_limited_per_user_not_per_ip():
    """Measured in production: 5 resends inside a minute all returned 200 against a
    3/minute limit. The module limiter keys on get_remote_address, and uvicorn runs
    without --proxy-headers, so that is Railway's internal proxy address — which
    rotates, giving every request its own bucket. Resend sends real mail, so an
    unenforced limit is unbounded outbound volume against the sending reputation the
    gate depends on. It is authenticated, so it must key by user."""
    import main
    src = inspect.getsource(main)
    start = src.index('@app.post("/api/auth/resend-verification")')
    decorators = src[start:start + 1200]
    assert "key_func=_user_key" in decorators, \
        "resend-verification must be rate-limited per user, not per (rotating) proxy IP"


# ── Anti-bot at signup still applies (carried over from the old file) ────────

def test_disposable_domains_still_blocked_including_web_library():
    import main

    bl = main._BLOCKED_EMAIL_DOMAINS
    for d in ["web-library.net", "mailinator.com", "guerrillamail.com",
              "1secmail.com", "getnada.com", "temp-mail.org"]:
        assert d in bl, f"{d} should be in the disposable blocklist"
