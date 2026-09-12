"""AI provider health checks added to the existing Porickbot monitoring cycle
(zeus_ops_agent.health_check / daily_report).

Same contract as the pre-existing fal.ai/Apiframe checkers (see
test_balance_alarms.py): a checker returns None ONLY when it positively
confirmed the provider healthy. Two severities only:
  * CRITICAL — the key itself is bad, or the provider couldn't be confirmed
    healthy at all (auth rejected, unreachable, unexpected response shape).
  * WARNING  — auth is fine, balance is just running low.
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
os.environ.setdefault("JWT_SECRET", "test-secret-for-ai-provider-health-tests")

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


# ── Anthropic — auth + balance ──────────────────────────────────────────────

def test_anthropic_healthy_balance_is_silent():
    body = {"balance": {"available": [{"amount": 5000, "currency": "USD"}]}}
    with patch.object(alerts.requests, "get", return_value=_Resp(200, body)):
        assert alerts._check_anthropic_provider("sk-ant-real") is None


def test_anthropic_low_balance_warns():
    body = {"balance": {"available": [{"amount": 300, "currency": "USD"}]}}
    with patch.object(alerts.requests, "get", return_value=_Resp(200, body)):
        out = alerts._check_anthropic_provider("sk-ant-real")
    assert out and "WARNING" in out and "3.00" in out


def test_anthropic_no_balance_field_is_not_a_failure():
    """Some accounts (pay-as-you-go, no prepaid grant) just don't expose one."""
    with patch.object(alerts.requests, "get", return_value=_Resp(200, {"balance": {"available": []}})):
        assert alerts._check_anthropic_provider("sk-ant-real") is None


def test_anthropic_401_is_critical_auth_failure():
    with patch.object(alerts.requests, "get", return_value=_Resp(401, {"error": "invalid api key"})):
        out = alerts._check_anthropic_provider("bad-key")
    assert out and "CRITICAL" in out and "auth failed" in out.lower()


def test_anthropic_network_error_is_critical():
    with patch.object(alerts.requests, "get", side_effect=OSError("connection reset")):
        out = alerts._check_anthropic_provider("sk-ant-real")
    assert out and "CRITICAL" in out


# ── OpenAI — auth only, no public balance endpoint ──────────────────────────

def test_openai_healthy_is_silent():
    with patch.object(alerts.requests, "get", return_value=_Resp(200, {"data": []})):
        assert alerts._check_openai_provider("sk-real") is None


def test_openai_403_is_critical_auth_failure():
    with patch.object(alerts.requests, "get", return_value=_Resp(403, {"error": "forbidden"})):
        out = alerts._check_openai_provider("bad-key")
    assert out and "CRITICAL" in out and "auth failed" in out.lower()


# ── Gemini — auth only, key travels in the query string ─────────────────────

def test_gemini_healthy_is_silent():
    with patch.object(alerts.requests, "get", return_value=_Resp(200, {"models": []})):
        assert alerts._check_gemini_provider("AIzaReal") is None


def test_gemini_auth_failure_never_leaks_the_key_in_the_message():
    with patch.object(alerts.requests, "get", return_value=_Resp(400, {"error": "API key not valid"})) as mock_get:
        out = alerts._check_gemini_provider("AIzaSuperSecretKey123")
    assert out and "CRITICAL" in out
    assert "AIzaSuperSecretKey123" not in out
    # The key must travel as a param, never baked into a logged/returned URL.
    assert mock_get.call_args.kwargs.get("params") == {"key": "AIzaSuperSecretKey123"}


# ── Grok (xAI) — auth only ───────────────────────────────────────────────────

def test_grok_healthy_is_silent():
    with patch.object(alerts.requests, "get", return_value=_Resp(200, {"data": []})):
        assert alerts._check_grok_provider("xai-real") is None


def test_grok_401_is_critical():
    with patch.object(alerts.requests, "get", return_value=_Resp(401, {"error": "unauthorized"})):
        out = alerts._check_grok_provider("bad-key")
    assert out and "CRITICAL" in out


# ── OpenRouter — auth + balance, the one legitimate non-direct provider ─────

def test_openrouter_healthy_balance_is_silent():
    body = {"data": {"total_credits": 50.0, "total_usage": 10.0}}
    with patch.object(alerts.requests, "get", return_value=_Resp(200, body)):
        assert alerts._check_openrouter_provider("sk-or-real") is None


def test_openrouter_low_balance_warns():
    body = {"data": {"total_credits": 10.0, "total_usage": 9.0}}
    with patch.object(alerts.requests, "get", return_value=_Resp(200, body)):
        out = alerts._check_openrouter_provider("sk-or-real")
    assert out and "WARNING" in out and "1.00" in out


def test_openrouter_401_is_critical():
    with patch.object(alerts.requests, "get", return_value=_Resp(401, {"error": "invalid key"})):
        out = alerts._check_openrouter_provider("bad-key")
    assert out and "CRITICAL" in out and "auth failed" in out.lower()


def test_openrouter_unexpected_shape_does_not_crash():
    with patch.object(alerts.requests, "get", return_value=_Resp(200, {"data": {"something": "else"}})):
        assert alerts._check_openrouter_provider("sk-or-real") is None


# ── _check_ai_providers wrapper ──────────────────────────────────────────────

def test_unset_provider_keys_are_skipped_not_reported():
    """Not every provider needs to be in use — Grok/Gemini are optional."""
    env = {"ANTHROPIC_API_KEY": "", "OPENAI_API_KEY": "", "GEMINI_API_KEY": "",
           "XAI_API_KEY": "", "OPENROUTER_API_KEY": ""}
    with patch.dict(os.environ, env):
        assert alerts._check_ai_providers() is None


def test_aggregates_multiple_provider_issues():
    env = {"ANTHROPIC_API_KEY": "sk-ant-real", "OPENAI_API_KEY": "sk-real",
           "GEMINI_API_KEY": "", "XAI_API_KEY": "", "OPENROUTER_API_KEY": ""}
    with patch.dict(os.environ, env), \
         patch.object(alerts, "_check_anthropic_provider", return_value="🔴 CRITICAL: Anthropic auth failed."), \
         patch.object(alerts, "_check_openai_provider", return_value="🟡 WARNING: OpenAI thing."):
        out = alerts._check_ai_providers()
    assert out and "Anthropic auth failed" in out and "OpenAI thing" in out


def test_a_crashing_checker_is_reported_not_swallowed():
    env = {"ANTHROPIC_API_KEY": "sk-ant-real", "OPENAI_API_KEY": "", "GEMINI_API_KEY": "",
           "XAI_API_KEY": "", "OPENROUTER_API_KEY": ""}
    with patch.dict(os.environ, env), \
         patch.object(alerts, "_check_anthropic_provider", side_effect=RuntimeError("boom")):
        out = alerts._check_ai_providers()
    assert out and "CRITICAL" in out and "boom" in out
