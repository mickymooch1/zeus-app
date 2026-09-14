"""Abuse blocklist (2026-09-14): closes the "make a second free-trial account
from the same device" loophole -- reported case: paulgb189@gmail.com made 2
accounts, same device, to farm multiple free-trial credit grants.

Deliberate design, per explicit instruction:
  * EMAIL is a HARD block, at both registration and login — near-zero
    false-positive risk, it's already the account identity.
  * DEVICE FINGERPRINT and IP are SOFT signals only, even when they match a
    known-blocked entry — a device/network can be legitimately shared by more
    than one real person. A match never rejects; it's flagged to the admin
    (via the same signup_flags/alert_signup_flag pipeline device_reuse/
    ip_velocity already use) so a human can decide case-by-case.

These tests exercise the real db.py functions against a real temp SQLite DB,
and the real /auth/register + /auth/login HTTP endpoints end to end (no
mocking of the blocklist check itself) -- this is security-sensitive enough
that a source-inspection-only test wouldn't be enough assurance.
"""
import os
import pathlib
import sys
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))
os.environ.setdefault("ANTHROPIC_API_KEY", "test-key")
os.environ.setdefault("APIFRAME_API_KEY", "test-key")
os.environ.setdefault("SONG_STORAGE_PATH", "/tmp/test_songs")
os.environ.setdefault("SONG_PUBLIC_BASE_URL", "https://example.com/files/songs")
os.environ.setdefault("SONG_WEBHOOK_URL", "https://zeusaidesign.com/webhooks/apiframe")
os.environ.setdefault("JWT_SECRET", "test-secret-for-abuse-blocklist-tests")

import db
import signup_guard


@pytest.fixture
def temp_db(tmp_path, monkeypatch):
    path = tmp_path / "test.db"
    db.init_user_tables(path)
    monkeypatch.setattr(db, "get_db_path", lambda: path)
    return path


# ── db.py: the blocklist primitives ─────────────────────────────────────────

def test_is_email_blocklisted_matches_exact_canonical_value(temp_db):
    db.add_to_blocklist(temp_db, "email", "bad@example.com", "test reason")
    assert db.is_email_blocklisted(temp_db, "bad@example.com") == "test reason"
    assert db.is_email_blocklisted(temp_db, "someone-else@example.com") is None


def test_is_email_blocklisted_requires_the_caller_to_normalise(temp_db):
    """The function itself does no normalisation -- callers pass the
    canonical form (matching how get_user_by_canonical_email works), so an
    alias only matches if the caller normalised it first."""
    canonical = signup_guard.normalize_email("bad+trick@gmail.com")
    db.add_to_blocklist(temp_db, "email", canonical, "test reason")
    assert db.is_email_blocklisted(temp_db, signup_guard.normalize_email("bad+other@gmail.com")) == "test reason"
    assert db.is_email_blocklisted(temp_db, "bad+trick@gmail.com") is None  # raw, un-normalised form


def test_find_blocklisted_device_signal_matches_ip_and_fp_independently(temp_db):
    db.add_to_blocklist(temp_db, "ip", "1.2.3.4", "known bad IP")
    db.add_to_blocklist(temp_db, "device_fp", "deadbeef", "known bad device")

    assert db.find_blocklisted_device_signal(temp_db, ip_address="1.2.3.4")["reason"] == "known bad IP"
    assert db.find_blocklisted_device_signal(temp_db, fp_hash="deadbeef")["reason"] == "known bad device"
    assert db.find_blocklisted_device_signal(temp_db, ip_address="9.9.9.9", fp_hash="cafebabe") is None


def test_find_blocklisted_device_signal_with_no_signals_given(temp_db):
    assert db.find_blocklisted_device_signal(temp_db) is None


def test_add_to_blocklist_is_idempotent(temp_db):
    assert db.add_to_blocklist(temp_db, "email", "x@example.com", "first") is True
    assert db.add_to_blocklist(temp_db, "email", "x@example.com", "second attempt") is False
    # First reason wins -- OR IGNORE never overwrites.
    assert db.is_email_blocklisted(temp_db, "x@example.com") == "first"


# ── Migration seed: paulgb189@gmail.com ─────────────────────────────────────

def test_paulgb189_is_seeded_as_a_hard_email_block_on_a_fresh_db(temp_db):
    """init_user_tables' migration list seeds this entry -- no manual step
    needed for the reported case to take effect on deploy."""
    reason = db.is_email_blocklisted(temp_db, "paulgb189@gmail.com")
    assert reason is not None
    assert "device" in reason.lower() or "trial" in reason.lower()


def test_seeding_is_safe_to_run_twice(tmp_path):
    """init_user_tables is called on every startup -- the seed must not
    error or duplicate on a second run against the same DB."""
    path = tmp_path / "twice.db"
    db.init_user_tables(path)
    db.init_user_tables(path)  # must not raise
    conn = db._conn(path)
    try:
        count = conn.execute(
            "SELECT COUNT(*) FROM abuse_blocklist WHERE signal_type='email' AND signal_value='paulgb189@gmail.com'"
        ).fetchone()[0]
    finally:
        conn.close()
    assert count == 1


# ── /auth/register and /auth/login end to end ───────────────────────────────

def _client():
    import main as _main
    _main.limiter.enabled = False
    return _main.app


def _register(client, email, password="password123", fingerprint=None, name="Test", headers=None):
    body = {"email": email, "password": password, "name": name, "tc_accepted": True}
    if fingerprint is not None:
        body["fingerprint"] = fingerprint
    return client.post("/auth/register", json=body, headers=headers or {})


def _login(client, email, password="password123", headers=None):
    return client.post("/auth/login", json={"email": email, "password": password}, headers=headers or {})


@pytest.fixture
def app_client(temp_db):
    app = _client()
    with TestClient(app) as client:
        yield client


def test_blocklisted_email_is_rejected_at_registration(app_client):
    resp = _register(app_client, "paulgb189@gmail.com")
    assert resp.status_code == 403
    assert "can't be created" in resp.json()["detail"]


def test_blocklisted_email_alias_is_also_rejected_at_registration(app_client):
    """paulgb189+newaccount@gmail.com must not dodge the block the same way
    it can't dodge the existing duplicate-account check."""
    resp = _register(app_client, "paulgb189+newaccount@gmail.com")
    assert resp.status_code == 403


def test_non_blocklisted_email_registers_normally(app_client):
    resp = _register(app_client, "genuinely-new-user@example.com")
    assert resp.status_code == 200
    assert resp.json()["user"]["email"] == "genuinely-new-user@example.com"


def test_blocklisted_email_login_is_rejected_after_correct_password(temp_db):
    """Login must not merely fail to authenticate the blocked email -- it
    must actively account-exist-and-reject with a clear message, once the
    real password is supplied."""
    app = _client()
    with TestClient(app) as client:
        reg = _register(client, "toblock@example.com")
        assert reg.status_code == 200
        db.add_to_blocklist(temp_db, "email", signup_guard.normalize_email("toblock@example.com"), "manual test block")

        resp = _login(client, "toblock@example.com")
        assert resp.status_code == 403
        assert "suspended" in resp.json()["detail"].lower()


def test_wrong_password_still_gets_the_generic_message_not_the_block_message(temp_db):
    """A blocked account must not leak its block status to someone who
    doesn't even know the password -- they get the same generic failure
    as any other wrong-password attempt."""
    app = _client()
    with TestClient(app) as client:
        reg = _register(client, "toblock2@example.com")
        assert reg.status_code == 200
        db.add_to_blocklist(temp_db, "email", signup_guard.normalize_email("toblock2@example.com"), "manual test block")

        resp = _login(client, "toblock2@example.com", password="totally-wrong-password")
        assert resp.status_code == 401
        assert "suspended" not in resp.json()["detail"].lower()


def test_non_blocklisted_login_is_unaffected(app_client):
    reg = _register(app_client, "fine-user@example.com")
    assert reg.status_code == 200
    resp = _login(app_client, "fine-user@example.com")
    assert resp.status_code == 200
    assert resp.json()["user"]["email"] == "fine-user@example.com"


# ── Device/IP: soft-flag only, NEVER a hard block ───────────────────────────

def test_blocklisted_device_fingerprint_does_not_block_registration(app_client, temp_db):
    """The central requirement: a device/IP match must never reject a
    signup, however strong the match, because a real person may
    legitimately share that device with the blocked user."""
    db.add_to_blocklist(temp_db, "device_fp", "known-bad-device-hash", "linked to paulgb189")

    import hashlib
    fake_fingerprint_source = "some-browser-fingerprint-string"
    fp_hash = hashlib.sha256(fake_fingerprint_source.encode()).hexdigest()
    db.add_to_blocklist(temp_db, "device_fp", fp_hash, "linked to paulgb189")

    with patch("alerts.alert_signup_flag") as alert_fn:
        resp = _register(app_client, "innocent-housemate@example.com", fingerprint=fake_fingerprint_source)

    assert resp.status_code == 200, "device/IP match must never block registration"
    alert_fn.assert_called_once()
    call_args = alert_fn.call_args[0]
    assert call_args[1] == "blocklisted_device"


def test_blocklisted_ip_does_not_block_registration_but_is_flagged(app_client, temp_db):
    db.add_to_blocklist(temp_db, "ip", "testclient", "linked to paulgb189")  # TestClient's default client IP

    with patch("alerts.alert_signup_flag") as alert_fn:
        resp = _register(app_client, "another-innocent-user@example.com")

    assert resp.status_code == 200
    assert alert_fn.call_count == 1
    assert alert_fn.call_args[0][1] == "blocklisted_device"


def test_no_alert_fires_for_an_unmatched_device_or_ip(app_client, temp_db):
    with patch("alerts.alert_signup_flag") as alert_fn:
        resp = _register(app_client, "totally-unrelated@example.com")
    assert resp.status_code == 200
    for call in alert_fn.call_args_list:
        assert call[0][1] != "blocklisted_device"


# ── Wiring guard (mirrors test_signup_guard.py's existing style) ───────────

def test_email_block_raises_but_device_ip_block_never_does():
    import inspect
    import main as _main

    register_src = inspect.getsource(_main.register)
    login_src = inspect.getsource(_main.login)

    assert "is_email_blocklisted" in register_src
    assert "is_email_blocklisted" in login_src
    assert "find_blocklisted_device_signal" in register_src
    # The device/IP lookup result must feed a flag call, never a raise on its own.
    assert "_record_signup_flag" in register_src
