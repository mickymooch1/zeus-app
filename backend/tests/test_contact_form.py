"""Contact form submissions must never be silently lost.

Found 2026-08-20: /api/contact only ever attempted an SMTP send to
hello@zeusbeats.com, caught any failure as a log warning, stored nothing, and
returned {"ok": true, "message": "Thanks! We'll be in touch within 24 hours."}
regardless. Gmail had been rejecting the credentials (535 BadCredentials), so
every enquiry was being dropped while the submitter was told otherwise — and
because nothing was persisted, there was no way to find out how many.

The invariants pinned here:
  * the submission is PERSISTED before any notifier runs
  * a Telegram alert is sent, and that is the primary channel
  * a failing notifier does not lose the enquiry
  * a failing DATABASE does not stop the notification either
  * losing it entirely is logged at ERROR, not swallowed
"""
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
os.environ.setdefault("JWT_SECRET", "test-secret-for-contact-tests")

_BODY = {
    "name": "Ada Lovelace",
    "email": "ada@example.com",
    "subject": "Booking enquiry",
    "message": "Can you make a track for a wedding in September?",
}


def _post(**patches):
    """POST /api/contact with db + alert layers patched out.

    The endpoint is rate-limited to 5/minute and TestClient presents a stable
    address, so several tests in one file trip the limiter. Disable it here — the
    limit itself is not what this file is testing.
    """
    import main as _main
    _main.limiter.enabled = False
    defaults = {
        "db.save_contact_submission": 42,
        "db.mark_contact_notified": None,
        "alerts.alert_contact_submission": True,
    }
    defaults.update(patches)
    ctxs = []
    for target, value in defaults.items():
        p = patch(target, side_effect=value) if isinstance(value, Exception) else patch(target, return_value=value)
        ctxs.append(p)
    started = [c.start() for c in ctxs]
    try:
        with TestClient(_main.app) as client:
            resp = client.post("/api/contact", json=_BODY)
        return resp, dict(zip(defaults.keys(), started))
    finally:
        for c in ctxs:
            c.stop()


def test_submission_is_persisted():
    resp, mocks = _post()
    assert resp.status_code == 200
    save = mocks["db.save_contact_submission"]
    save.assert_called_once()
    kwargs = save.call_args.kwargs
    assert kwargs["email"] == "ada@example.com"
    assert kwargs["message"].startswith("Can you make a track")


def test_telegram_alert_is_sent():
    _, mocks = _post()
    alert = mocks["alerts.alert_contact_submission"]
    alert.assert_called_once()
    args = alert.call_args.args
    assert "ada@example.com" in args
    assert "Booking enquiry" in args


def test_persist_runs_before_notify_so_a_failing_notifier_cannot_lose_it():
    """The whole point: notification is best-effort, the row is not."""
    resp, mocks = _post(**{"alerts.alert_contact_submission": False})
    assert resp.status_code == 200
    mocks["db.save_contact_submission"].assert_called_once()
    # Not marked notified, because nothing delivered — but the row exists.
    mocks["db.mark_contact_notified"].assert_not_called()


def test_a_broken_database_still_notifies():
    """Inverse direction: persistence failing must not suppress the alert."""
    resp, mocks = _post(**{"db.save_contact_submission": RuntimeError("db down")})
    assert resp.status_code == 200
    mocks["alerts.alert_contact_submission"].assert_called_once()


def test_notified_flag_is_set_only_on_successful_delivery():
    _, mocks = _post()
    mocks["db.mark_contact_notified"].assert_called_once()


def test_total_loss_is_logged_at_error():
    """If nothing landed anywhere, that must be loud — the submitter has just been
    told we will be in touch."""
    import main as _main
    with patch.object(_main.log, "error") as err:
        _post(**{
            "db.save_contact_submission": RuntimeError("db down"),
            "alerts.alert_contact_submission": False,
        })
    joined = " ".join(str(c) for c in err.call_args_list)
    assert "SUBMISSION LOST" in joined


def test_endpoint_still_thanks_the_visitor():
    """Infrastructure problems must not be leaked to the person submitting."""
    resp, _ = _post()
    assert resp.json()["ok"] is True
    assert "touch" in resp.json()["message"].lower()
