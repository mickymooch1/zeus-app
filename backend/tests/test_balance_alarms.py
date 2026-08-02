"""Provider balance alarms must never fail silently (2026-08-02).

Both endpoints had rotted (fal.ai -> 404, Apiframe /account -> 400 "that key is
v2, this endpoint is v1") and every failure was swallowed at log.debug, so
health_check() reported "all OK" while it could read neither balance. The fal.ai
account then ran to zero unnoticed and every song's cover art began failing with
HTTP 403 "User is locked. Reason: Exhausted balance."

The contract these tests pin:
  * a checker returns None ONLY when it positively read a healthy balance
  * anything else — bad status, unparseable body, missing key, network error,
    changed response shape — returns a LOUD warning string
  * health_check() surfaces a crashing checker instead of swallowing it
"""
import os
import pathlib
import sys
from unittest.mock import patch

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))
os.environ.setdefault("ANTHROPIC_API_KEY", "test-key")
os.environ.setdefault("APIFRAME_API_KEY", "test-key")
os.environ.setdefault("SONG_STORAGE_PATH", "/tmp/test_songs")
os.environ.setdefault("SONG_PUBLIC_BASE_URL", "https://example.com/files/songs")
os.environ.setdefault("SONG_WEBHOOK_URL", "https://zeusaidesign.com/webhooks/apiframe")
os.environ.setdefault("JWT_SECRET", "test-secret-for-balance-alarm-tests")

import alerts


class _Resp:
    def __init__(self, status, payload=None, text=""):
        self.status_code = status
        self._payload = payload
        self.text = text or str(payload)

    def json(self):
        if isinstance(self._payload, Exception):
            raise self._payload
        return self._payload


# ── Correct endpoints are pinned (they were wrong before) ────────────────────

def test_endpoints_are_the_verified_current_ones():
    assert alerts.FAL_BALANCE_URL == "https://rest.alpha.fal.ai/billing/user_balance"
    assert alerts.APIFRAME_ACCOUNT_URL == "https://api.apiframe.ai/v2/me"
    # The dead ones must not come back.
    assert "api.fal.ai/billing/balance" not in alerts.FAL_BALANCE_URL
    assert alerts.APIFRAME_ACCOUNT_URL.rstrip("/").split("/")[-1] != "account"


# ── fal.ai ───────────────────────────────────────────────────────────────────

def test_fal_healthy_balance_is_silent():
    with patch.object(alerts.requests, "get", return_value=_Resp(200, 42.5)):
        assert alerts._check_fal_balance() is None


def test_fal_bare_number_body_is_parsed():
    """The live endpoint returns a bare JSON number, not an object."""
    with patch.object(alerts.requests, "get", return_value=_Resp(200, 3.0)):
        out = alerts._check_fal_balance()
    assert out and "3.00" in out          # below the $10 warn threshold


def test_fal_exhausted_balance_screams():
    with patch.object(alerts.requests, "get", return_value=_Resp(200, 0.0)):
        out = alerts._check_fal_balance()
    assert out and "EXHAUSTED" in out
    assert "fal.ai/dashboard/billing" in out


def test_fal_low_balance_warns_before_running_out():
    with patch.object(alerts.requests, "get", return_value=_Resp(200, 4.0)):
        out = alerts._check_fal_balance()
    assert out and "low" in out.lower()


def test_fal_404_is_LOUD_not_silent():
    """The exact regression: the endpoint moved and nobody was told."""
    with patch.object(alerts.requests, "get",
                      return_value=_Resp(404, {"error": "Route not found"}, '{"error":"Route not found"}')):
        out = alerts._check_fal_balance()
    assert out is not None, "a dead endpoint must never be silent"
    assert "UNREADABLE" in out and "404" in out


def test_fal_network_error_is_loud():
    with patch.object(alerts.requests, "get", side_effect=OSError("connection reset")):
        out = alerts._check_fal_balance()
    assert out and "UNREADABLE" in out


def test_fal_unparseable_body_is_loud():
    with patch.object(alerts.requests, "get", return_value=_Resp(200, ValueError("nope"), "<html>")):
        out = alerts._check_fal_balance()
    assert out and "UNREADABLE" in out


def test_fal_missing_key_is_loud():
    with patch.dict(os.environ, {"FAL_API_KEY": ""}):
        out = alerts._check_fal_balance()
    assert out and "UNREADABLE" in out


# ── Apiframe ─────────────────────────────────────────────────────────────────

_OK = {"user": {"email": "x@y.z"}, "team": {"credits": 3644, "plan": "af_basic"}}


def test_apiframe_healthy_is_silent():
    with patch.object(alerts.requests, "get", return_value=_Resp(200, _OK)):
        assert alerts._check_apiframe_credits() is None


def test_apiframe_reads_credits_from_team_object():
    low = {"user": {}, "team": {"credits": 12}}
    with patch.object(alerts.requests, "get", return_value=_Resp(200, low)):
        out = alerts._check_apiframe_credits()
    assert out and "12" in out


def test_apiframe_exhausted_screams():
    with patch.object(alerts.requests, "get", return_value=_Resp(200, {"team": {"credits": 0}})):
        out = alerts._check_apiframe_credits()
    assert out and "EXHAUSTED" in out


def test_apiframe_v1_v2_mismatch_is_LOUD():
    """The real failure: v1 endpoint + v2 key returned 400 and was swallowed."""
    body = '{"error":"Your API key starts with \'afk_\' which means you are on Apiframe v2."}'
    with patch.object(alerts.requests, "get", return_value=_Resp(400, {"error": "v1/v2"}, body)):
        out = alerts._check_apiframe_credits()
    assert out is not None
    assert "UNREADABLE" in out and "400" in out


def test_apiframe_changed_shape_is_loud():
    with patch.object(alerts.requests, "get", return_value=_Resp(200, {"something": "else"})):
        out = alerts._check_apiframe_credits()
    assert out and "UNREADABLE" in out


def test_apiframe_missing_key_is_loud():
    with patch.dict(os.environ, {"APIFRAME_API_KEY": ""}):
        out = alerts._check_apiframe_credits()
    assert out and "UNREADABLE" in out


# ── health_check wiring ──────────────────────────────────────────────────────

def test_health_check_alerts_when_a_balance_is_unreadable():
    import zeus_ops_agent as ops
    sent = []
    with patch.object(ops, "_fix_stuck_songs", return_value=[]), \
         patch("alerts._check_fal_balance", return_value="⁉️ fal.ai balance UNREADABLE — HTTP 404"), \
         patch("alerts._check_apiframe_credits", return_value=None), \
         patch("alerts.send_admin_alert", side_effect=lambda m: sent.append(m)):
        ops.health_check()
    assert sent, "an unreadable balance must raise a Telegram alert"
    assert "UNREADABLE" in sent[0]


def test_health_check_reports_a_crashing_checker():
    import zeus_ops_agent as ops
    sent = []
    with patch.object(ops, "_fix_stuck_songs", return_value=[]), \
         patch("alerts._check_fal_balance", side_effect=RuntimeError("boom")), \
         patch("alerts._check_apiframe_credits", return_value=None), \
         patch("alerts.send_admin_alert", side_effect=lambda m: sent.append(m)):
        ops.health_check()
    assert sent, "a crashing checker must not be swallowed"
    assert "CRASHED" in sent[0]


def test_health_check_stays_quiet_when_both_balances_are_healthy():
    import zeus_ops_agent as ops
    sent = []
    with patch.object(ops, "_fix_stuck_songs", return_value=[]), \
         patch("alerts._check_fal_balance", return_value=None), \
         patch("alerts._check_apiframe_credits", return_value=None), \
         patch("alerts.send_admin_alert", side_effect=lambda m: sent.append(m)):
        ops.health_check()
    assert sent == []
