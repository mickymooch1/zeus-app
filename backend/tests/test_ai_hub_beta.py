"""Public beta access and one-time Hub credits; provider traffic is mocked."""
import asyncio
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from ai.config import HubError, Settings
from ai.service import execute, prepare
from ai.store import Store


def test_public_beta_allows_verified_unlisted_user_and_exposes_council(beta, tmp_path, monkeypatch):
    import uuid
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    monkeypatch.setenv('JWT_SECRET', 'public-beta-tests-only-secret-1234567890')
    import auth
    import db
    from ai.api import router
    app = FastAPI()
    app.include_router(router)
    path = tmp_path / 'api.db'
    app.dependency_overrides[db.get_db_path_dep] = lambda: path
    app.dependency_overrides[auth.get_current_user] = lambda: {'id': 'outsider', 'email_verified': 1, 'subscription_status': 'free'}
    with TestClient(app) as client:
        status = client.get('/api/hub/status').json()
        assert status['balance_name'] == 'Hub Beta Credits'
        assert status['balance'] == 20 and status['council_enabled'] is True
        body = {'request_id': str(uuid.uuid4()), 'prompt': 'Hello', 'max_credits': 100}
        assert client.post('/api/hub/quote', json=body).status_code == 200
        body['feature'] = 'council'
        assert client.post('/api/hub/quote', json=body).status_code == 200


def test_unverified_user_cannot_access_hub_or_receive_allowance(beta, tmp_path, monkeypatch):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    monkeypatch.setenv('JWT_SECRET', 'unverified-beta-tests-only-secret-1234567890')
    import auth
    import db
    from ai.api import router
    from ai.store import Store
    app = FastAPI()
    app.include_router(router)
    path = tmp_path / 'unverified.db'
    app.dependency_overrides[db.get_db_path_dep] = lambda: path
    app.dependency_overrides[auth.get_current_user] = lambda: {'id': 'unverified', 'email_verified': 0}
    with TestClient(app) as client:
        assert client.get('/api/hub/status').status_code == 403
        assert Store(path).balance('unverified', 'beta') == 0


def test_public_beta_allowance_is_one_time_and_adds_to_existing_balance(beta, tmp_path, monkeypatch):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    monkeypatch.setenv('JWT_SECRET', 'grant-beta-tests-only-secret-1234567890')
    import auth
    import db
    from ai.api import router
    from ai.store import Store
    app = FastAPI()
    app.include_router(router)
    path = tmp_path / 'grant.db'
    app.dependency_overrides[db.get_db_path_dep] = lambda: path
    app.dependency_overrides[auth.get_current_user] = lambda: {'id': 'existing', 'email_verified': 1}
    store = Store(path)
    store.grant('existing', 'beta', 7, 'paid-topup')
    store.grant('existing', 'beta', 3, 'initial-v1')
    with TestClient(app) as client:
        assert client.get('/api/hub/status').json()['balance'] == 30
        # A fresh authenticated session for the same user must not grant again.
        app.dependency_overrides[auth.get_current_user] = lambda: {'id': 'existing', 'email_verified': 1}
        assert client.get('/api/hub/status').json()['balance'] == 30
        assert client.get('/api/hub/status').json()['balance'] == 30
    with store.connection() as conn:
        grants = conn.execute("SELECT COUNT(*) FROM hub_ledger WHERE user_id=? AND mode='beta' AND reference='grant:public-beta-v1'", ('existing',)).fetchone()[0]
        previous = conn.execute("SELECT delta FROM hub_ledger WHERE user_id=? AND mode='beta' AND reference='grant:initial-v1'", ('existing',)).fetchone()
    assert grants == 1 and previous['delta'] == 3


def test_zero_allowance_during_deploy_does_not_consume_public_grant(beta, tmp_path, monkeypatch):
    monkeypatch.setenv('JWT_SECRET', 'rollout-beta-tests-only-secret-1234567890')
    from ai.api import context
    from ai.config import Settings
    raw = json.loads((Path(__file__).parents[1] / 'ai/beta-config.example.json').read_text())
    raw['initial_allowance'] = 0  # deployed code may start before Railway is updated
    monkeypatch.setenv('ZEUS_HUB_CONFIG', json.dumps(raw))
    from_env = Settings.from_env
    zero_settings = from_env()
    monkeypatch.setattr(Settings, 'from_env', lambda: zero_settings)
    path = tmp_path / 'rollout.db'
    user = {'id': 'rollout-user', 'email_verified': 1}

    store, _, _ = context(user, path)
    assert store.balance(user['id'], 'beta') == 0
    with store.connection() as conn:
        assert conn.execute("SELECT 1 FROM hub_ledger WHERE user_id=? AND mode='beta' AND reference='grant:public-beta-v1'", (user['id'],)).fetchone() is None

    raw['initial_allowance'] = 20
    monkeypatch.setenv('ZEUS_HUB_CONFIG', json.dumps(raw))
    public_settings = from_env()
    monkeypatch.setattr(Settings, 'from_env', lambda: public_settings)
    store, _, _ = context(user, path)
    assert store.balance(user['id'], 'beta') == 20


def test_insufficient_council_balance_stops_before_provider_or_search(beta, tmp_path, monkeypatch):
    import uuid
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    monkeypatch.setenv('JWT_SECRET', 'insufficient-beta-tests-only-secret-1234567890')
    import auth
    import db
    import ai.service as service
    from ai.api import router
    from ai.providers import Provider
    from ai.store import Store
    app = FastAPI()
    app.include_router(router)
    path = tmp_path / 'insufficient.db'
    app.dependency_overrides[db.get_db_path_dep] = lambda: path
    app.dependency_overrides[auth.get_current_user] = lambda: {'id': 'outsider', 'email_verified': 1, 'subscription_status': 'free'}
    store = Store(path)
    def unexpected(*args, **kwargs):
        raise AssertionError('paid work must not run without sufficient Hub credits')
    monkeypatch.setattr(service, 'search', unexpected)
    async def unexpected_provider(self, messages, **kwargs):
        raise AssertionError('provider must not run without sufficient Hub credits')
    monkeypatch.setattr(Provider, 'generate', unexpected_provider)
    with TestClient(app) as client:
        # First verified Hub access grants the one-time allowance; reduce it
        # below the 15-credit Council reservation to exercise the guard.
        assert client.get('/api/hub/status').json()['balance'] == 20
        with store.connection(True) as conn:
            conn.execute("UPDATE hub_balances SET balance=14 WHERE user_id='outsider' AND mode='beta'")
        response = client.post('/api/hub/requests', json={
            'request_id': str(uuid.uuid4()), 'feature': 'council', 'prompt': 'Compare options',
            'max_credits': 100, 'web_search': True, 'search_query': 'public comparison',
        })
        assert response.status_code == 402
    assert store.history('outsider', 'beta') == []


@pytest.fixture
def beta(monkeypatch):
    raw = json.loads((Path(__file__).parents[1] / 'ai/beta-config.example.json').read_text())
    raw['beta_user_ids'] = ['tester']
    monkeypatch.setenv('ZEUS_HUB_MODE', 'beta')
    monkeypatch.setenv('ZEUS_HUB_CONFIG', json.dumps(raw))
    monkeypatch.setenv('ANTHROPIC_API_KEY', 'fake-test-key')
    monkeypatch.setenv('OPENAI_API_KEY', 'fake-test-key')
    monkeypatch.setenv('GEMINI_API_KEY', 'fake-test-key')
    monkeypatch.setenv('OPENROUTER_API_KEY', 'fake-test-key')
    return Settings.from_env()


def test_allowlist_does_not_block_ask_or_council_preflight(beta, tmp_path):
    store = Store(tmp_path / 'db')
    body = SimpleNamespace(feature='ask', prompt='Hello', conversation_id=None)
    assert prepare(store, beta, {'id': 'outsider'}, body)[1] == 'beta'
    body.feature = 'council'
    assert prepare(store, beta, {'id': 'outsider'}, body)[2]['credits'] == 15
    assert store.history('tester', 'beta') == []


def test_beta_uses_one_anthropic_model_with_capped_output(beta, monkeypatch):
    import httpx
    from ai.providers import Provider
    original = httpx.AsyncClient
    calls = []
    def transport(request):
        body = json.loads(request.content)
        calls.append(body)
        assert str(request.url) == 'https://api.anthropic.com/v1/messages'
        return httpx.Response(200, json={'model': body['model'], 'content': [{'type': 'text', 'text': 'Hello'}],
                                       'usage': {'input_tokens': 100, 'output_tokens': 50}})
    monkeypatch.setattr(httpx, 'AsyncClient', lambda **kwargs: original(transport=httpx.MockTransport(transport), **kwargs))
    result = asyncio.run(Provider(beta.models['beta'], beta).generate([{'role': 'user', 'content': 'Hello'}]))
    assert len(calls) == 1
    assert calls[0]['max_tokens'] == 512
    assert calls[0]['model'] == 'claude-haiku-4-5-20251001'
    assert result['estimated_cost'] == 0.00035


@pytest.mark.parametrize('change', [
    {'beta_user_ids': []}, {'initial_allowance': -1}, {'initial_allowance': 19},
    {'members': ['beta'], 'judge': 'beta'},
])
def test_beta_invalid_configuration_fails_closed(beta, monkeypatch, change):
    import os
    raw = json.loads(os.environ['ZEUS_HUB_CONFIG'])
    raw.update(change)
    monkeypatch.setenv('ZEUS_HUB_CONFIG', json.dumps(raw))
    with pytest.raises(HubError):
        Settings.from_env()


@pytest.mark.parametrize('failure', [False, True])
def test_beta_grant_usage_charge_and_refund(beta, tmp_path, monkeypatch, failure):
    from ai.providers import Provider
    store = Store(tmp_path / 'db')
    store.grant('tester', 'beta', 100, 'private-beta-v1')
    store.grant('tester', 'beta', 100, 'private-beta-v1')
    assert store.balance('tester', 'beta') == 100
    assert store.balance('tester', 'live') == store.balance('tester', 'development') == 0
    body = SimpleNamespace(feature='ask', prompt='Hello', conversation_id=None)
    messages, selected, quote = prepare(store, beta, {'id': 'tester'}, body)
    store.reserve('tester', 'beta', 'request', 'conversation', 'ask', 'Hello', quote['credits'], 'hash', 3, 20)

    async def generate(self, messages):
        usage = dict(provider='anthropic', model=self.model.model, input_tokens=100, output_tokens=50,
                     estimated_cost=0.00035, usage_known=True, text='Hello back')
        if failure:
            raise HubError('Provider failed', usage=usage)
        return usage

    monkeypatch.setattr(Provider, 'generate', generate)
    asyncio.run(execute(store, beta, 'tester', 'request', 'ask', messages, selected))
    request = store.request('tester', 'request')
    usage = store.usage('tester', 'request')[0]
    charged = 0 if failure else 1
    assert request['status'] == ('failed' if failure else 'succeeded')
    assert store.balance('tester', 'beta') == 100 - charged
    assert usage['provider'] == 'anthropic'
    assert usage['model'] == 'claude-haiku-4-5-20251001'
    assert (usage['input_tokens'], usage['output_tokens']) == (100, 50)
    assert usage['estimated_cost'] == 0.00035
    assert usage['zeus_credits_charged'] == charged
