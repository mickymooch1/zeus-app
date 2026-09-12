"""Public Zeus Council beta: global Council config, fixed 15/12/refund settlement, and an explicit per-request
cost cap. All provider traffic is mocked -- no real network/API calls."""
import json
import uuid
from pathlib import Path

import pytest

from ai.config import HubError, Settings

COUNCIL_USER = 'council-test-user'
OTHER_BETA_USER = 'ordinary-beta-user'


def _raw_config():
    raw = json.loads((Path(__file__).parents[1] / 'ai/beta-config.example.json').read_text())
    raw['beta_user_ids'] = [COUNCIL_USER]
    raw['council_beta_user_ids'] = []
    return raw


@pytest.fixture
def council_settings(monkeypatch):
    monkeypatch.setenv('ZEUS_HUB_MODE', 'beta')
    monkeypatch.setenv('ZEUS_HUB_CONFIG', json.dumps(_raw_config()))
    monkeypatch.setenv('ANTHROPIC_API_KEY', 'fake-test-key')
    monkeypatch.setenv('OPENAI_API_KEY', 'fake-test-key')
    monkeypatch.setenv('GEMINI_API_KEY', 'fake-test-key')
    return Settings.from_env()


def test_council_beta_config_validates_and_matches_expected_shape(council_settings):
    s = council_settings
    assert s.council_beta_user_ids == []
    assert len(s.members) == 3 and len(set(s.members)) == 3
    assert s.judge and s.judge in s.models
    assert s.council_max_request_usd == pytest.approx(0.06)
    # Ask Zeus's own model entry is untouched and still exactly one.
    assert s.models['beta'].model == 'claude-haiku-4-5-20251001'


def test_council_allowed_for_verified_user_outside_both_allowlists(council_settings):
    council_settings.authorize(OTHER_BETA_USER, 'council')
    council_settings.authorize(OTHER_BETA_USER, 'ask')


def test_council_authorization_does_not_require_allowlisted_id(council_settings):
    council_settings.authorize('nobody', 'council')


def test_council_allowed_for_council_beta_user(council_settings):
    council_settings.authorize(COUNCIL_USER, 'council')  # does not raise
    council_settings.authorize(COUNCIL_USER, 'ask')  # does not raise


def test_ask_zeus_authorize_unaffected_by_council_allowlist(council_settings):
    # Someone on beta_user_ids but absent from council_beta_user_ids still
    # gets ordinary Ask Zeus access -- the two allowlists are independent.
    council_settings.authorize(OTHER_BETA_USER, 'ask')
    council_settings.authorize(OTHER_BETA_USER, None)


def test_worst_case_council_cost_stays_under_the_cap(council_settings):
    from ai.pricing import input_bound, quote
    s = council_settings
    prompt = 'x' * s.max_input_bytes  # worst-case allowed prompt length
    messages = [{'role': 'user', 'content': prompt}]
    estimate = quote(s, 'council', messages, None)
    assert estimate['estimated_cost'] <= s.council_max_request_usd, (
        f"worst-case council cost {estimate['estimated_cost']} exceeds the "
        f"configured cap {s.council_max_request_usd} -- token caps or pricing drifted"
    )
    assert estimate['credits'] == 15  # fixed reservation, not dollar-derived


@pytest.fixture
def api_client(council_settings, tmp_path, monkeypatch):
    monkeypatch.setenv('JWT_SECRET', 'council-beta-tests-only-secret-1234567890')
    import auth
    import db
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from ai.api import router
    from ai.config import Settings
    monkeypatch.setattr(Settings, 'from_env', lambda: council_settings)
    app = FastAPI()
    app.include_router(router)
    path = tmp_path / 'council.db'
    db.init_user_tables(path)
    app.dependency_overrides[db.get_db_path_dep] = lambda: path
    app.dependency_overrides[auth.get_current_user] = lambda: {'id': COUNCIL_USER, 'email_verified': 1, 'subscription_status': 'free'}
    with TestClient(app) as c:
        from ai.store import Store
        Store(path).grant(COUNCIL_USER, 'beta', 15, 'seed')
        yield c, path


def _submit(c):
    body = {'request_id': str(uuid.uuid4()), 'feature': 'council', 'prompt': 'Compare two approaches', 'max_credits': 100}
    quote = c.post('/api/hub/quote', json=body).json()
    assert quote['credits'] == 15
    resp = c.post('/api/hub/requests', json=body)
    assert resp.status_code == 202
    return c.get('/api/hub/requests/' + body['request_id']).json()


def _balance(c):
    return c.get('/api/hub/status').json()['balance']


def test_status_reports_global_council_enabled_and_preserves_diagnostics_gate(council_settings, tmp_path, monkeypatch):
    # Regression: /api/hub/status must actually reflect council access per
    # caller in beta mode -- the frontend's whole Council UI (HubChatPage's
    # featureEnabled) gates on this exact field. Getting it wrong makes the
    # feature unreachable even for the one account it was built for.
    monkeypatch.setenv('JWT_SECRET', 'council-status-tests-only-secret-1234567890')
    import auth
    import db
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from ai.api import router
    app = FastAPI()
    app.include_router(router)
    path = tmp_path / 'status.db'
    db.init_user_tables(path)
    app.dependency_overrides[db.get_db_path_dep] = lambda: path
    with TestClient(app) as c:
        app.dependency_overrides[auth.get_current_user] = lambda: {'id': COUNCIL_USER, 'email_verified': 1, 'subscription_status': 'free'}
        assert c.get('/api/hub/status').json()['council_enabled'] is True
        app.dependency_overrides[auth.get_current_user] = lambda: {'id': OTHER_BETA_USER, 'email_verified': 1, 'subscription_status': 'free'}
        public_status = c.get('/api/hub/status').json()
        assert public_status['council_enabled'] is True


def test_full_success_charges_exactly_15(api_client, monkeypatch):
    from ai.providers import Provider
    c, path = api_client
    async def generate(self, messages):
        return {'text': f'answer from {self.model.model}', 'input_tokens': 50, 'output_tokens': 50,
                'estimated_cost': 0.001, 'usage_known': True, 'provider': self.model.provider, 'model': self.model.model}
    monkeypatch.setattr(Provider, 'generate', generate)
    result = _submit(c)
    assert result['status'] == 'succeeded'
    assert result['zeus_credits_charged'] == 15
    assert _balance(c) == 20


def test_one_member_failure_charges_exactly_12(api_client, monkeypatch):
    from ai.providers import Provider
    c, path = api_client
    async def generate(self, messages):
        if self.model.model == 'gemini-3.5-flash-lite':
            raise RuntimeError('provider outage')
        return {'text': f'answer from {self.model.model}', 'input_tokens': 50, 'output_tokens': 50,
                'estimated_cost': 0.001, 'usage_known': True, 'provider': self.model.provider, 'model': self.model.model}
    monkeypatch.setattr(Provider, 'generate', generate)
    result = _submit(c)
    assert result['status'] == 'succeeded'
    assert result['zeus_credits_charged'] == 12
    assert _balance(c) == 23  # public allowance plus the 3 refunded credits


def test_two_member_failures_refund_all_15(api_client, monkeypatch):
    from ai.providers import Provider
    c, path = api_client
    failed = {'gpt-4.1-mini-2025-04-14', 'gemini-3.5-flash-lite'}
    async def generate(self, messages):
        if self.model.model in failed:
            raise RuntimeError('provider outage')
        return {'text': 'answer', 'input_tokens': 50, 'output_tokens': 50,
                'estimated_cost': 0.001, 'usage_known': True, 'provider': self.model.provider, 'model': self.model.model}
    monkeypatch.setattr(Provider, 'generate', generate)
    result = _submit(c)
    assert result['status'] == 'failed'
    assert result['zeus_credits_charged'] == 0
    assert _balance(c) == 35  # original 15 plus public allowance; fully refunded


def test_judge_failure_refunds_all_15_even_if_every_member_succeeded(api_client, monkeypatch):
    from ai.providers import Provider
    c, path = api_client
    async def generate(self, messages):
        # The judge call is distinguishable: it's the only one whose prompt
        # contains the council-conclusions synthesis instruction.
        if 'Council conclusions' in messages[-1]['content']:
            raise RuntimeError('judge provider outage')
        return {'text': 'a member answer', 'input_tokens': 50, 'output_tokens': 50,
                'estimated_cost': 0.001, 'usage_known': True, 'provider': self.model.provider, 'model': self.model.model}
    monkeypatch.setattr(Provider, 'generate', generate)
    result = _submit(c)
    assert result['status'] == 'failed'
    assert result['zeus_credits_charged'] == 0
    assert _balance(c) == 35


def test_cost_cap_rejects_a_request_that_would_exceed_it(api_client, monkeypatch):
    from ai.config import Settings
    tight = api_client  # reuse the fixture's settings object indirectly via monkeypatch below
    c, path = api_client
    import ai.api as api_module
    original = Settings.from_env
    cheap_cap_settings = original()
    cheap_cap_settings.council_max_request_usd = 0.00001  # effectively unreachable
    monkeypatch.setattr(Settings, 'from_env', lambda: cheap_cap_settings)
    body = {'request_id': str(uuid.uuid4()), 'feature': 'council', 'prompt': 'Compare two approaches', 'max_credits': 100}
    resp = c.post('/api/hub/quote', json=body)
    assert resp.status_code == 422
