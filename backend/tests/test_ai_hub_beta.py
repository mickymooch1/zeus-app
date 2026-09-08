"""Private beta isolation; all provider traffic is mocked."""
import asyncio
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from ai.config import HubError, Settings
from ai.service import execute, prepare
from ai.store import Store


def test_beta_http_access_and_zero_balance(beta, tmp_path, monkeypatch):
    import uuid
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    monkeypatch.setenv('JWT_SECRET', 'private-beta-tests-only-secret-1234567890')
    import auth
    import db
    from ai.api import router
    app = FastAPI()
    app.include_router(router)
    path = tmp_path / 'api.db'
    app.dependency_overrides[db.get_db_path_dep] = lambda: path
    app.dependency_overrides[auth.get_current_user] = lambda: {'id': 'tester', 'email_verified': 1}
    with TestClient(app) as client:
        status = client.get('/api/hub/status').json()
        assert status['balance_name'] == 'Hub Beta Credits'
        assert status['balance'] == 0 and status['council_enabled'] is False
        body = {'request_id': str(uuid.uuid4()), 'prompt': 'Hello', 'max_credits': 100}
        assert client.post('/api/hub/requests', json=body).status_code == 402
        body['feature'] = 'council'
        assert client.post('/api/hub/quote', json=body).status_code == 503
        assert client.post('/api/hub/requests', json=body).status_code == 503
        app.dependency_overrides[auth.get_current_user] = lambda: {'id': 'outsider', 'email_verified': 1, 'is_admin': True}
        assert client.get('/api/hub/status').status_code == 403
        assert client.post('/api/hub/requests', json=body).status_code == 403


@pytest.fixture
def beta(monkeypatch):
    raw = json.loads((Path(__file__).parents[1] / 'ai/beta-config.example.json').read_text())
    raw['beta_user_ids'] = ['tester']
    monkeypatch.setenv('ZEUS_HUB_MODE', 'beta')
    monkeypatch.setenv('ZEUS_HUB_CONFIG', json.dumps(raw))
    monkeypatch.setenv('ANTHROPIC_API_KEY', 'fake-test-key')
    return Settings.from_env()


def test_beta_allowlist_and_council_block_before_work(beta, tmp_path):
    store = Store(tmp_path / 'db')
    body = SimpleNamespace(feature='ask', prompt='Hello', conversation_id=None)
    with pytest.raises(HubError, match='invitation-only'):
        prepare(store, beta, {'id': 'outsider'}, body)
    body.feature = 'council'
    with pytest.raises(HubError, match='Council live calls are disabled'):
        prepare(store, beta, {'id': 'tester'}, body)
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
    {'beta_user_ids': []}, {'initial_allowance': 100},
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
