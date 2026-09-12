"""Zeus Hub (Ask Zeus / Council / search) wired into Porick's existing
alert/incident/diagnosis monitoring -- extends the same alert_*/
incidents.note() pattern already used for Beats (see test_service_error_alerts.py,
test_incidents.py), rather than a parallel mechanism.

Four new categories, all classified to service "hub" and a fixed severity
of "critical" (a Hub failure always means the customer's own request just
failed): provider_timeout, provider_unavailable, malformed_response,
search_failure. Deliberately NOT covered here: any new Stage 3 whitelisted
action for Hub -- see the "no action offered" tests below, which exist to
prove that omission rather than merely assume it.

The hard security requirement threaded through every alerting call site
added for this task: no alert message or incident evidence field may ever
contain the upstream request/response body, the user's prompt or search
query, or an API key -- only error type, provider name, HTTP status, and
timing. The sanitization tests below drive real secrets/prompts through the
real exception paths in ai/providers.py and ai/search.py and assert they
never surface, rather than trusting the design description alone.
"""
import logging
import os
import pathlib
import sys
from unittest.mock import MagicMock, patch

import httpx
import pytest

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))
os.environ.setdefault("ANTHROPIC_API_KEY", "test-key")
os.environ.setdefault("APIFRAME_API_KEY", "test-key")
os.environ.setdefault("SONG_STORAGE_PATH", "/tmp/test_songs")
os.environ.setdefault("SONG_PUBLIC_BASE_URL", "https://example.com/files/songs")
os.environ.setdefault("SONG_WEBHOOK_URL", "https://zeusaidesign.com/webhooks/apiframe")
os.environ.setdefault("JWT_SECRET", "test-secret-for-hub-monitoring-tests")

import alerts
import db
import incident_actions
import incidents
from ai.config import HubError, Model, Settings
from ai.providers import Provider

OPENAI_MODEL = Model(provider='openai', model='gpt-4.1-mini-2025-04-14',
                      input_per_million=0.40, output_per_million=1.60, max_output_tokens=400)


def _response(status, json_body=None, text_body=None):
    request = httpx.Request('POST', 'https://api.openai.com/v1/chat/completions')
    if json_body is not None:
        return httpx.Response(status, json=json_body, request=request)
    return httpx.Response(status, text=text_body or '', request=request)


@pytest.fixture
def temp_db(tmp_path, monkeypatch):
    path = tmp_path / "test.db"
    monkeypatch.setattr(db, "get_db_path", lambda: path)
    return path


@pytest.fixture(autouse=True)
def no_diagnosis(monkeypatch):
    monkeypatch.setattr(incidents, "_spawn_diagnosis", lambda incident: None)
    incidents._diagnosed_incident_ids.clear()
    yield
    incidents._diagnosed_incident_ids.clear()


@pytest.fixture(autouse=True)
def clean_alert_and_offer_state():
    alerts._ALERT_CATEGORY_STATE.clear()
    alerts._sent_alerts.clear()
    alerts._DIGEST_COUNTERS.clear()
    incident_actions._pending_offers.clear()
    yield
    alerts._ALERT_CATEGORY_STATE.clear()
    alerts._sent_alerts.clear()
    alerts._DIGEST_COUNTERS.clear()
    incident_actions._pending_offers.clear()


# ── New categories classify to service "hub", severity critical ────────────

@pytest.mark.parametrize("category", [
    "provider_timeout", "provider_unavailable", "malformed_response", "search_failure",
])
def test_new_hub_categories_classify_as_hub_critical(category):
    service, severity, title = incidents.classify(category)
    assert service == "hub"
    assert severity == "critical"
    assert title


def test_existing_beats_categories_are_unchanged():
    """Adding the Hub entries must not have touched a single existing key."""
    assert incidents.classify("stuck_song_sweep") == ("jobline", "warning", "Stuck songs recovered")
    assert incidents.classify("payment_failed") == ("billing", "critical", "Payment failed")
    assert incidents.classify("fal_balance") == ("provider", None, "fal.ai balance")
    assert incidents.classify("service_error:apiframe") == ("provider", None, "External service error")


def test_diagnosis_system_prompt_is_no_longer_beats_exclusive():
    """The prompt used to say 'Zeus Beats, an AI music generation platform' --
    a Beats-only framing that would mislead diagnosis for a Hub incident.
    Must now name both products."""
    assert "Zeus Hub" in incidents._DIAGNOSIS_SYSTEM_PROMPT
    assert "Zeus Beats" in incidents._DIAGNOSIS_SYSTEM_PROMPT


def test_gather_log_evidence_already_filters_hub_relevant_lines(monkeypatch):
    """No code change was needed here -- _SERVICE_LOG_KEYWORDS already had a
    "hub" entry before this task; this pins that it actually works end to
    end for the new categories' service="hub" incidents."""
    fake_lines = [
        "2026-09-12 info: user signed up",
        "2026-09-12 hub provider_error provider=openai status=429",
        "2026-09-12 council consult failed for member fast",
        "2026-09-12 unrelated billing log line",
    ]
    monkeypatch.setattr("telegram_admin._log_buffer", fake_lines)
    evidence = incidents._gather_log_evidence("hub")
    assert "provider_error" in evidence
    assert "council consult failed" in evidence
    assert "unrelated billing log line" not in evidence


# ── alerts.py: the 4 new alert_hub_* functions ──────────────────────────────

def test_alert_hub_provider_timeout_creates_incident_and_sends(temp_db, monkeypatch):
    sent = []
    monkeypatch.setattr(alerts, "_send_telegram", lambda msg: sent.append(msg) or True)
    alerts.alert_hub_provider_timeout("openai", 12.3)
    assert len(sent) == 1
    assert "PROVIDER TIMEOUT" in sent[0]
    assert "openai" in sent[0]
    open_incidents = incidents.list_open()
    assert len(open_incidents) == 1
    assert open_incidents[0]["category"] == "provider_timeout"
    assert open_incidents[0]["service"] == "hub"
    assert open_incidents[0]["severity"] == "critical"


def test_alert_hub_provider_unavailable_dedupes_like_beats(temp_db, monkeypatch):
    sent = []
    monkeypatch.setattr(alerts, "_send_telegram", lambda msg: sent.append(msg) or True)
    alerts.alert_hub_provider_unavailable("anthropic", 429, "rate_limit_error", "rate_limited")
    alerts.alert_hub_provider_unavailable("anthropic", 429, "rate_limit_error", "rate_limited")
    assert len(sent) == 1  # same category -> deduped, matching send_admin_alert_deduped everywhere else


def test_alert_hub_malformed_response_records_reason(temp_db, monkeypatch):
    sent = []
    monkeypatch.setattr(alerts, "_send_telegram", lambda msg: sent.append(msg) or True)
    alerts.alert_hub_malformed_response("gemini", "KeyError")
    assert "KeyError" in sent[0]
    assert incidents.list_open()[0]["category"] == "malformed_response"


def test_alert_hub_search_failure_records(temp_db, monkeypatch):
    sent = []
    monkeypatch.setattr(alerts, "_send_telegram", lambda msg: sent.append(msg) or True)
    alerts.alert_hub_search_failure("missing_api_key")
    assert incidents.list_open()[0]["category"] == "search_failure"


def test_hub_alerts_never_raise(monkeypatch):
    monkeypatch.setattr(alerts, "send_admin_alert_deduped", MagicMock(side_effect=RuntimeError("telegram down")))
    alerts.alert_hub_provider_timeout("openai", 1.0)
    alerts.alert_hub_provider_unavailable("openai", 500)
    alerts.alert_hub_malformed_response("openai", "ValueError")
    alerts.alert_hub_search_failure("ConnectError")


def test_hub_alerts_bump_the_shared_errors_digest_counter(temp_db, monkeypatch):
    monkeypatch.setattr(alerts, "_send_telegram", lambda msg: True)
    alerts.alert_hub_provider_timeout("openai", 1.0)
    assert alerts.pop_digest_counters().get("errors") == 1


def test_alert_hub_provider_unavailable_has_no_free_text_message_parameter():
    """Structural guarantee, not just a runtime one: this function cannot be
    called with a raw error_message/body/prompt at all, so there is nothing
    for a caller to accidentally pass through."""
    import inspect
    params = set(inspect.signature(alerts.alert_hub_provider_unavailable).parameters)
    assert params == {"provider", "status_code", "error_type", "error_code"}


def test_existing_alert_service_error_unchanged(temp_db, monkeypatch):
    """Confirms the pre-existing Beats alert path is untouched by this change."""
    sent = []
    monkeypatch.setattr(alerts, "_send_telegram", lambda msg: sent.append(msg) or True)
    alerts.alert_service_error("apiframe", 401, "bad key")
    assert len(sent) == 1
    incident = incidents.list_open()[0]
    assert incident["category"] == "service_error:apiframe:401"
    assert incident["service"] == "provider"


# ── Sanitization guarantee: ai/providers.py ─────────────────────────────────

@pytest.mark.asyncio
async def test_provider_timeout_alert_never_leaks_key_or_prompt(temp_db, monkeypatch):
    fake_key = "sk-should-never-leak-abcdefgh12345678"
    monkeypatch.setenv('OPENAI_API_KEY', fake_key)
    fake_prompt = "my secret user query about my divorce lawyer"

    async def fake_post(self, url, headers=None, json=None):
        raise httpx.TimeoutException('timed out')
    monkeypatch.setattr(httpx.AsyncClient, 'post', fake_post)

    sent = []
    monkeypatch.setattr(alerts, "_send_telegram", lambda msg: sent.append(msg) or True)

    settings = Settings(mode='beta', timeout_seconds=30)
    provider = Provider(OPENAI_MODEL, settings)
    with pytest.raises(HubError):
        await provider.generate([{'role': 'user', 'content': fake_prompt}])

    assert len(sent) == 1
    assert fake_key not in sent[0]
    assert fake_prompt not in sent[0]

    incident = incidents.list_open()[0]
    assert incident["category"] == "provider_timeout"
    evidence_text = incident["symptoms"] + (incident["evidence"] or "")
    assert fake_key not in evidence_text
    assert fake_prompt not in evidence_text


@pytest.mark.asyncio
async def test_provider_unavailable_alert_never_leaks_body_content(temp_db, monkeypatch):
    fake_key = "sk-should-never-leak-secondcase-8765"
    monkeypatch.setenv('OPENAI_API_KEY', fake_key)
    fake_prompt = "another private prompt that must never be logged"
    secret_in_body = "sk-leaked-in-provider-body-987654321"

    async def fake_post(self, url, headers=None, json=None):
        return _response(429, {'error': {'message': f'quota exceeded, offending key {secret_in_body}',
                                          'type': 'insufficient_quota', 'code': 'insufficient_quota'}})
    monkeypatch.setattr(httpx.AsyncClient, 'post', fake_post)

    sent = []
    monkeypatch.setattr(alerts, "_send_telegram", lambda msg: sent.append(msg) or True)

    settings = Settings(mode='beta', timeout_seconds=30)
    provider = Provider(OPENAI_MODEL, settings)
    with pytest.raises(HubError):
        await provider.generate([{'role': 'user', 'content': fake_prompt}])

    assert len(sent) == 1
    assert fake_key not in sent[0]
    assert fake_prompt not in sent[0]
    assert secret_in_body not in sent[0]

    incident = incidents.list_open()[0]
    assert incident["category"] == "provider_unavailable"
    evidence_text = incident["symptoms"] + (incident["evidence"] or "")
    assert fake_key not in evidence_text
    assert fake_prompt not in evidence_text
    assert secret_in_body not in evidence_text


@pytest.mark.asyncio
async def test_malformed_response_alert_never_leaks_prompt(temp_db, monkeypatch):
    monkeypatch.setenv('OPENAI_API_KEY', 'sk-not-a-real-key-1234567890')
    fake_prompt = "a third private prompt that must never be logged"

    async def fake_post(self, url, headers=None, json=None):
        return _response(200, {'choices': [{}]})  # missing message.content -> KeyError
    monkeypatch.setattr(httpx.AsyncClient, 'post', fake_post)

    sent = []
    monkeypatch.setattr(alerts, "_send_telegram", lambda msg: sent.append(msg) or True)

    settings = Settings(mode='beta', timeout_seconds=30)
    provider = Provider(OPENAI_MODEL, settings)
    with pytest.raises(HubError):
        await provider.generate([{'role': 'user', 'content': fake_prompt}])

    assert len(sent) == 1
    assert fake_prompt not in sent[0]
    incident = incidents.list_open()[0]
    assert incident["category"] == "malformed_response"
    evidence_text = incident["symptoms"] + (incident["evidence"] or "")
    assert fake_prompt not in evidence_text


@pytest.mark.asyncio
async def test_empty_answer_alert_never_leaks_prompt(temp_db, monkeypatch):
    monkeypatch.setenv('OPENAI_API_KEY', 'sk-not-a-real-key-1234567890')
    fake_prompt = "a fourth private prompt, this one triggers the empty-answer branch"

    async def fake_post(self, url, headers=None, json=None):
        return _response(200, {'choices': [{'message': {'content': '   '}}], 'usage': {}})
    monkeypatch.setattr(httpx.AsyncClient, 'post', fake_post)

    sent = []
    monkeypatch.setattr(alerts, "_send_telegram", lambda msg: sent.append(msg) or True)

    settings = Settings(mode='beta', timeout_seconds=30)
    provider = Provider(OPENAI_MODEL, settings)
    with pytest.raises(HubError):
        await provider.generate([{'role': 'user', 'content': fake_prompt}])

    assert len(sent) == 1
    assert fake_prompt not in sent[0]
    assert incidents.list_open()[0]["category"] == "malformed_response"


# ── Sanitization guarantee: ai/search.py ────────────────────────────────────

def test_missing_serper_key_fires_search_failure_alert(temp_db, monkeypatch):
    import asyncio
    import ai.search as search_mod
    monkeypatch.delenv('SERPER_API_KEY', raising=False)
    sent = []
    monkeypatch.setattr(alerts, "_send_telegram", lambda msg: sent.append(msg) or True)

    with pytest.raises(HubError):
        asyncio.run(search_mod.search("a legit public query"))

    assert len(sent) == 1
    assert incidents.list_open()[0]["category"] == "search_failure"


def test_search_network_failure_alert_never_leaks_query(temp_db, monkeypatch):
    import asyncio
    import ai.search as search_mod
    monkeypatch.setenv('SERPER_API_KEY', 'fake-serper-key-should-not-leak')
    fake_query_fragment = "shady-business-practices-query-marker"

    def _boom(self, method, url, headers=None, json=None):
        # The query never legitimately reaches an exception message in real
        # code -- this simulates the worst case (some future bug echoing it)
        # to prove the alert path only ever forwards the exception's type.
        raise httpx.ConnectError(f"network exploded: {fake_query_fragment}")
    monkeypatch.setattr(httpx.AsyncClient, 'stream', _boom)

    sent = []
    monkeypatch.setattr(alerts, "_send_telegram", lambda msg: sent.append(msg) or True)

    with pytest.raises(HubError):
        asyncio.run(search_mod.search("a legit public query"))

    assert len(sent) == 1
    assert fake_query_fragment not in sent[0]
    assert "ConnectError" in sent[0]
    incident = incidents.list_open()[0]
    assert incident["category"] == "search_failure"
    evidence_text = incident["symptoms"] + (incident["evidence"] or "")
    assert fake_query_fragment not in evidence_text


class _FakeStreamResponse:
    def __init__(self, body: bytes):
        self._body = body

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

    def raise_for_status(self):
        pass

    async def aiter_bytes(self):
        yield self._body


def test_no_relevant_search_results_does_not_fire_an_alert(temp_db, monkeypatch):
    """Deliberate scope decision: zero relevant results after filtering is a
    routine, expected outcome (many businesses have no online presence at
    all) -- not a technical failure -- so it must NOT page the admin the
    way a real infrastructure failure does."""
    import asyncio
    import ai.search as search_mod
    monkeypatch.setenv('SERPER_API_KEY', 'fake-serper-key')
    sent = []
    monkeypatch.setattr(alerts, "_send_telegram", lambda msg: sent.append(msg) or True)
    monkeypatch.setattr(httpx.AsyncClient, 'stream',
                         lambda self, method, url, headers=None, json=None: _FakeStreamResponse(b'{"organic": []}'))

    with pytest.raises(HubError):
        asyncio.run(search_mod.search("a genuinely obscure query with no results"))

    assert sent == []
    assert incidents.list_open() == []


# ── Sanitization guarantee: ai/service.py orchestration-level failures ─────

@pytest.fixture
def hub_client(tmp_path, monkeypatch):
    monkeypatch.setenv('ZEUS_HUB_MODE', 'development')
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    import auth
    path = tmp_path / 'api.db'
    db.init_user_tables(path)
    app = FastAPI()
    from ai.api import router
    app.include_router(router)
    app.dependency_overrides[db.get_db_path_dep] = lambda: path
    app.dependency_overrides[auth.get_current_user] = lambda: {'id': 'alice', 'email_verified': 1, 'subscription_status': 'free'}
    with TestClient(app) as client:
        yield client


@pytest.mark.parametrize("failure,expected_category", [
    ("timeout", "provider_timeout"),
    ("outage", "malformed_response"),
])
def test_orchestration_level_failure_creates_incident_without_leaking(hub_client, temp_db, monkeypatch, failure, expected_category):
    """Mirrors test_ai_hub.py's test_provider_failure_refunds_without_secret_leak
    (same fixture shape, same injected failure), but asserts on the NEW
    alerting behaviour rather than just the API response."""
    import uuid
    from ai.providers import Provider

    sent = []
    monkeypatch.setattr(alerts, "_send_telegram", lambda msg: sent.append(msg) or True)

    async def fail(self, messages):
        if failure == "timeout":
            raise TimeoutError("secret-should-never-appear")
        raise RuntimeError("secret-should-never-appear")
    monkeypatch.setattr(Provider, "generate", fail)

    body = {"request_id": str(uuid.uuid4()), "prompt": "Hello", "feature": "ask", "max_credits": 100}
    assert hub_client.post("/api/hub/requests", json=body).status_code == 202
    result = hub_client.get("/api/hub/requests/" + body["request_id"])
    assert result.json()["status"] == "failed"

    assert len(sent) == 1
    assert "secret-should-never-appear" not in sent[0]

    open_incidents = incidents.list_open()
    assert len(open_incidents) == 1
    assert open_incidents[0]["category"] == expected_category
    assert open_incidents[0]["service"] == "hub"
    evidence_text = open_incidents[0]["symptoms"] + (open_incidents[0]["evidence"] or "")
    assert "secret-should-never-appear" not in evidence_text


def test_orchestration_failure_does_not_double_alert_a_provider_level_huberror(hub_client, temp_db, monkeypatch):
    """A HubError already raised (and already alerted) by ai/providers.py
    must NOT trigger a second alert in ai/service.py's outer catch."""
    import uuid
    from ai.providers import Provider

    sent = []
    monkeypatch.setattr(alerts, "_send_telegram", lambda msg: sent.append(msg) or True)

    async def fail(self, messages):
        raise HubError("The AI provider is unavailable. Please try a new request later.", 502)
    monkeypatch.setattr(Provider, "generate", fail)

    body = {"request_id": str(uuid.uuid4()), "prompt": "Hello", "feature": "ask", "max_credits": 100}
    assert hub_client.post("/api/hub/requests", json=body).status_code == 202
    result = hub_client.get("/api/hub/requests/" + body["request_id"])
    assert result.json()["status"] == "failed"

    # providers.py's own alerting only fires from inside Provider.generate's
    # real exception handlers, which are bypassed here (the whole method is
    # mocked) -- so no alert at all is expected in this specific scenario,
    # and in particular NOT a second, generic "orchestration" one.
    assert sent == []
    assert incidents.list_open() == []


# ── Stage 3: no whitelisted action is ever offered for a Hub incident ──────

@pytest.mark.parametrize("category", [
    "provider_timeout", "provider_unavailable", "malformed_response", "search_failure",
])
@pytest.mark.parametrize("cause", [
    "code", "api_credits", "database", "deployment", "third_party_outage", "configuration",
])
def test_hub_categories_never_offer_a_stage3_action(temp_db, monkeypatch, category, cause):
    monkeypatch.setattr("alerts.send_admin_alert", lambda msg: True)
    row = incidents.record(category, "symptom text", severity="critical")
    incident_actions.maybe_offer_action(dict(row), cause=cause, confidence="high")
    assert incident_actions._pending_offers == {}


def test_hub_incident_still_gets_diagnosed_stage2_despite_no_stage3_action(temp_db, monkeypatch):
    """Confirms Stage 2 (diagnosis trigger) is untouched by the Stage 3
    whitelist being empty for Hub -- they're independent gates."""
    triggered = []
    monkeypatch.setattr(incidents, "_spawn_diagnosis", lambda incident: triggered.append(incident))
    incidents.record("provider_timeout", "provider=openai: timed out", severity="critical")
    assert len(triggered) == 1
    assert triggered[0]["category"] == "provider_timeout"
