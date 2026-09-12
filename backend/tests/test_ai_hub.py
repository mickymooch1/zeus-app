"""Hub behavior against isolated databases; never uses live AI credentials."""
import asyncio
import pathlib
import sys
from concurrent.futures import ThreadPoolExecutor

import pytest

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))


def test_hub_defaults_disabled(monkeypatch):
    monkeypatch.delenv('ZEUS_HUB_MODE', raising=False)
    from ai.config import Settings
    assert Settings.from_env().mode == 'disabled'


def test_live_requires_explicit_rates_and_allowances(monkeypatch):
    monkeypatch.setenv('ZEUS_HUB_MODE', 'live')
    monkeypatch.delenv('ZEUS_HUB_CONFIG', raising=False)
    from ai.config import Settings, HubError
    with pytest.raises(HubError):
        Settings.from_env()


def _hub_config(monkeypatch, models):
    """Minimal valid ZEUS_HUB_CONFIG with the given models substituted in."""
    import json
    raw = {'models': models, 'routes': {'default': next(iter(models))},
           'credit_usd': 1, 'council_multiplier': 1, 'initial_allowance': 0,
           'free_daily_requests': 5, 'max_request_usd': 1}
    monkeypatch.setenv('ZEUS_HUB_MODE', 'live')
    monkeypatch.setenv('ZEUS_HUB_CONFIG', json.dumps(raw))


def test_anthropic_model_rejected_if_slash_qualified_like_openrouter(monkeypatch):
    """A slash in the model id is how OpenRouter names models — an Anthropic
    or OpenAI model id never has one, so this is either a stray OpenRouter-style
    id on a direct provider, or (more dangerously) provider was meant to say
    'openrouter' and got left as 'anthropic'/'openai' by mistake."""
    _hub_config(monkeypatch, {'fast': {'provider': 'anthropic', 'model': 'anthropic/claude-sonnet-4-6',
                                        'input_per_million': 1, 'output_per_million': 1}})
    from ai.config import Settings, HubError
    with pytest.raises(HubError):
        Settings.from_env()


def test_openai_model_rejected_if_slash_qualified(monkeypatch):
    _hub_config(monkeypatch, {'fast': {'provider': 'openai', 'model': 'openai/gpt-5',
                                        'input_per_million': 1, 'output_per_million': 1}})
    from ai.config import Settings, HubError
    with pytest.raises(HubError):
        Settings.from_env()


def test_openrouter_model_rejected_without_vendor_prefix(monkeypatch):
    """OpenRouter model ids are always vendor/model-name; a bare id here means
    this model almost certainly belongs on a direct provider instead."""
    _hub_config(monkeypatch, {'fast': {'provider': 'openrouter', 'model': 'claude-sonnet-4-6',
                                        'input_per_million': 1, 'output_per_million': 1}})
    from ai.config import Settings, HubError
    with pytest.raises(HubError):
        Settings.from_env()


def test_openrouter_rejected_for_anthropic_or_openai_vendor_prefix(monkeypatch):
    """Anthropic and OpenAI both have direct options — routing them through
    OpenRouter anyway is exactly the hard dependency this guards against."""
    _hub_config(monkeypatch, {'fast': {'provider': 'openrouter', 'model': 'anthropic/claude-3-opus',
                                        'input_per_million': 1, 'output_per_million': 1}})
    from ai.config import Settings, HubError
    with pytest.raises(HubError):
        Settings.from_env()


def test_openrouter_accepted_for_a_vendor_with_no_direct_option(monkeypatch):
    """Mistral (or anything else with no direct provider slot) is exactly what
    OpenRouter is meant to carry, and must keep working."""
    _hub_config(monkeypatch, {'fast': {'provider': 'openrouter', 'model': 'mistralai/mistral-large-2411',
                                        'input_per_million': 1, 'output_per_million': 1}})
    from ai.config import Settings
    assert Settings.from_env().models['fast'].provider == 'openrouter'


def test_routing_conservative():
    from ai.routing import classify
    assert classify('Hello there') == 'default'
    assert classify('Debug this Python code') == 'coding'
    assert classify('Analyse the trade-offs of these alternatives') == 'reasoning'
    assert classify('Write a long article about gardening') == 'writing'


@pytest.fixture
def store(tmp_path):
    from ai.store import Store
    return Store(tmp_path / 'hub.db')


def test_reserve_refund_and_no_other_wallets(store):
    from ai.config import HubError
    store.grant('alice', 'live', 10, 'grant-1')
    store.grant('alice', 'live', 10, 'grant-1')
    assert store.balance('alice', 'live') == 10
    store.reserve('alice', 'live', 'r1', 'c1', 'ask', 'hello', 7, 'hash1', 10, 100)
    assert store.balance('alice', 'live') == 3
    with pytest.raises(HubError) as exc:
        store.reserve('alice', 'live', 'r2', 'c2', 'ask', 'another', 7, 'hash2', 10, 100)
    assert exc.value.status == 402
    store.finish('alice', 'r1', 'failed', None, 0, 'Provider unavailable')
    store.finish('alice', 'r1', 'failed', None, 0, 'Provider unavailable')
    assert store.balance('alice', 'live') == 10
    assert store.history('bob', 'live') == []
    with pytest.raises(HubError):
        store.request('bob', 'r1')


def test_idempotency_payload_and_concurrent_balance(store):
    from ai.config import HubError
    store.grant('alice', 'live', 10, 'grant')
    def reserve(i):
        try:
            return store.reserve('alice', 'live', f'r{i}', f'c{i}', 'ask', str(i), 7, str(i), 20, 100)
        except HubError as e:
            return e.status
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(reserve, [1, 2]))
    assert results.count(402) == 1
    assert store.balance('alice', 'live') == 3
    i = 1 if results[0] != 402 else 2
    duplicate = store.reserve('alice', 'live', f'r{i}', f'c{i}', 'ask', str(i), 7, str(i), 20, 100)
    assert duplicate['duplicate'] is True
    with pytest.raises(HubError) as exc:
        store.reserve('alice', 'live', f'r{i}', f'c{i}', 'ask', 'changed', 7, 'different', 20, 100)
    assert exc.value.status == 409


def test_development_wallet_is_separate(store):
    store.grant('alice', 'development', 100, 'test')
    assert store.balance('alice', 'live') == 0


def test_council_survives_one_failed_member():
    from ai.council import consult
    async def run():
        async def generate(member, messages):
            if member == 'b':
                raise RuntimeError('unavailable')
            return {'text': f'Conclusion from {member}'}
        async def progress(text):
            pass
        result = await consult(['a', 'b', 'c'], 'judge', [{'role': 'user', 'content': 'Question'}], generate, progress)
        assert len(result['members']) == 2
        assert result['unavailable'] == 1
        assert result['unavailable_members'] == ['b']
        assert 'judge' in result['text']
    asyncio.run(run())


def test_council_requires_two_conclusions():
    from ai.council import consult
    from ai.config import HubError
    async def run():
        async def generate(member, messages):
            raise RuntimeError('outage')
        async def progress(text):
            pass
        with pytest.raises(HubError):
            await consult(['a', 'b', 'c'], 'judge', [], generate, progress)
    asyncio.run(run())


@pytest.fixture
def client(tmp_path, monkeypatch):
    import os
    os.environ.setdefault('JWT_SECRET', 'hub-tests-only-not-a-real-secret-1234567890')
    monkeypatch.setenv('ZEUS_HUB_MODE', 'development')
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    import auth
    import db
    from ai.api import router
    path = tmp_path / 'api.db'
    db.init_user_tables(path)
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[db.get_db_path_dep] = lambda: path
    app.dependency_overrides[auth.get_current_user] = lambda: {'id': 'alice', 'email_verified': 1, 'subscription_status': 'free'}
    with TestClient(app) as client:
        yield client, app, path


def test_api_quote_chat_history_and_duplicate(client):
    import uuid
    c, app, path = client
    body = {'request_id': str(uuid.uuid4()), 'feature': 'ask', 'prompt': 'Hello Zeus'}
    quote = c.post('/api/hub/quote', json=body)
    assert quote.status_code == 200
    assert quote.json()['credits'] > 0
    body['max_credits'] = quote.json()['credits']
    result = c.post('/api/hub/requests', json=body)
    assert result.status_code == 202
    request_id = body['request_id']
    done = c.get(f'/api/hub/requests/{request_id}').json()
    assert done['status'] == 'succeeded'
    assert done['zeus_credits_charged'] == 0
    assert 'simulation' in done['result']['text']
    assert len(done['usage']) == 1
    assert c.post('/api/hub/requests', json=body).status_code == 202
    assert len(c.get(f'/api/hub/requests/{request_id}').json()['usage']) == 1
    history = c.get('/api/hub/conversations').json()
    assert len(history) == 1
    assert c.get('/api/hub/conversations/' + history[0]['id']).status_code == 200
    body['prompt'] = 'changed'
    assert c.post('/api/hub/requests', json=body).status_code == 409


def test_api_auth_ownership_and_size(client):
    import auth
    import uuid
    c, app, path = client
    body = {'request_id': str(uuid.uuid4()), 'prompt': 'Test', 'feature': 'ask', 'max_credits': 100}
    assert c.post('/api/hub/requests', json=body).status_code == 202
    app.dependency_overrides[auth.get_current_user] = lambda: {'id': 'bob', 'email_verified': 1}
    assert c.get('/api/hub/requests/' + body['request_id']).status_code == 404
    assert c.get('/api/hub/conversations').json() == []
    assert c.post('/api/hub/quote', json={**body, 'prompt': 'x' * 12001}).status_code == 422
    app.dependency_overrides.pop(auth.get_current_user)
    assert c.get('/api/hub/status').status_code == 401


def test_api_disabled_and_no_balance(client, monkeypatch):
    import uuid
    from ai.store import Store
    c, app, path = client
    body = {'request_id': str(uuid.uuid4()), 'prompt': 'Hello', 'feature': 'ask', 'max_credits': 100}
    monkeypatch.setenv('ZEUS_HUB_MODE', 'disabled')
    assert c.post('/api/hub/requests', json=body).status_code == 503
    monkeypatch.setenv('ZEUS_HUB_MODE', 'development')
    c.get('/api/hub/status')
    store = Store(path)
    with store.connection(True) as conn:
        conn.execute('UPDATE hub_balances SET balance=0')
    assert c.post('/api/hub/requests', json=body).status_code == 402
    assert store.usage('alice', body['request_id']) == []


def test_persisted_rate_limit_and_crash_refund(store):
    from ai.config import HubError
    store.grant('alice', 'live', 100, 'grant')
    store.reserve('alice', 'live', 'r1', 'c1', 'ask', 'hello', 7, 'h', 1, 10)
    store.finish('alice', 'r1', 'failed', None, 0)
    with pytest.raises(HubError) as exc:
        store.reserve('alice', 'live', 'r2', 'c2', 'ask', 'hello', 7, 'h', 1, 10)
    assert exc.value.status == 429
    store.reserve('alice', 'live', 'r3', 'c3', 'ask', 'hello', 7, 'h', 10, 10)
    with store.connection(True) as conn:
        conn.execute('UPDATE hub_requests SET expires_at=0')
    store.recover('alice')
    store.recover('alice')
    assert store.balance('alice', 'live') == 100
    assert store.request('alice', 'r3')['status'] == 'failed'


def test_failed_call_gets_no_credit_allocation(store):
    from ai.config import Model
    store.grant('alice', 'live', 100, 'grant')
    store.reserve('alice', 'live', 'r1', 'c1', 'council', 'hello', 10, 'h', 10, 10)
    first = store.start_usage('alice', 'r1', Model('openai', 'a', 1, 1), 0.1)
    store.finish_usage(first, {'input_tokens': 1, 'output_tokens': 1, 'estimated_cost': 0.01})
    last = store.start_usage('alice', 'r1', Model('openai', 'b', 1, 1), 0.1)
    store.finish_usage(last, status='failed')
    store.finish('alice', 'r1', 'succeeded', {'text': 'answer'}, 3)
    calls = store.usage('alice', 'r1')
    assert calls[0]['zeus_credits_charged'] == 3
    assert calls[1]['zeus_credits_charged'] == 0


@pytest.mark.parametrize('failure', ['outage', 'timeout'])
def test_provider_failure_refunds_without_secret_leak(client, monkeypatch, failure):
    import uuid
    from ai.providers import Provider
    c, app, path = client
    async def fail(self, messages):
        if failure == 'timeout':
            raise TimeoutError('secret-should-never-appear')
        raise RuntimeError('secret-should-never-appear')
    monkeypatch.setattr(Provider, 'generate', fail)
    body = {'request_id': str(uuid.uuid4()), 'prompt': 'Hello', 'max_credits': 100}
    assert c.post('/api/hub/requests', json=body).status_code == 202
    result = c.get('/api/hub/requests/' + body['request_id'])
    assert result.json()['status'] == 'failed'
    assert result.json()['zeus_credits_charged'] == 0
    assert 'secret-should-never-appear' not in result.text
    assert c.get('/api/hub/status').json()['balance'] == 100


def test_live_cost_settlement_and_council_preflight(client, monkeypatch):
    import uuid
    from ai.config import Settings, Model
    from ai.providers import Provider
    from ai.store import Store
    c, app, path = client
    settings = Settings(mode='live', models={n: Model('openai', n, 1, 2) for n in ('a', 'b', 'c')},
                        routes={'default': 'a'}, members=['a', 'b', 'c'], judge='a', initial_allowance=10,
                        credit_usd=0.01, max_request_usd=1)
    monkeypatch.setattr(Settings, 'from_env', lambda: settings)
    monkeypatch.setenv('OPENAI_API_KEY', 'test-only-key-not-real')
    calls = []
    async def generate(self, messages):
        calls.append(self.model.model)
        if self.model.model == 'b':
            raise RuntimeError('unavailable')
        return {'text': 'A final conclusion', 'input_tokens': 100, 'output_tokens': 100,
                'estimated_cost': 0.0003, 'usage_known': True, 'provider': 'openai', 'model': self.model.model}
    monkeypatch.setattr(Provider, 'generate', generate)
    body = {'request_id': str(uuid.uuid4()), 'feature': 'council', 'prompt': 'Compare these options', 'max_credits': 100}
    quote = c.post('/api/hub/quote', json=body).json()
    assert quote['credits'] > 1
    store = Store(path)
    with store.connection(True) as conn:
        conn.execute("UPDATE hub_balances SET balance=1 WHERE mode='live'")
    assert c.post('/api/hub/requests', json=body).status_code == 402
    assert calls == []
    store.grant('alice', 'live', 20, 'extra')
    assert c.post('/api/hub/requests', json=body).status_code == 202
    result = c.get('/api/hub/requests/' + body['request_id']).json()
    assert result['status'] == 'succeeded'
    assert result['result']['unavailable'] == 1
    assert result['result']['unavailable_members'] == ['b']
    assert result['zeus_credits_charged'] == 1
    assert len(result['usage']) == 4
    assert store.balance('alice', 'live') == 20
    assert all(row['zeus_credits_charged'] == 0 for row in result['usage'] if row['status'] == 'failed')


def test_provider_adapter_reads_only_final_text(monkeypatch):
    import httpx
    from ai.config import Settings, Model
    from ai.providers import Provider
    monkeypatch.setenv('OPENAI_API_KEY', 'test-only-key')
    real_client = httpx.AsyncClient
    sent = []
    def transport(request):
        import json
        sent.append(json.loads(request.content))
        return httpx.Response(200, json={'model': 'actual-model-snapshot', 'choices': [{'message': {'content': 'Final answer', 'reasoning_content': 'hidden'}}],
                                       'usage': {'prompt_tokens': 5, 'completion_tokens': 9}})
    monkeypatch.setattr(httpx, 'AsyncClient', lambda **kwargs: real_client(transport=httpx.MockTransport(transport), **kwargs))
    result = asyncio.run(Provider(Model('openai', 'test', 1, 2), Settings(mode='live')).generate([{'role': 'user', 'content': 'Hi'}]))
    assert result['text'] == 'Final answer'
    assert result['model'] == 'actual-model-snapshot'
    assert 'hidden' not in str(result)
    assert result['input_tokens'] == 5 and result['output_tokens'] == 9
    assert sent[0]['max_completion_tokens'] == 1024


def test_development_never_creates_http_client(monkeypatch):
    import httpx
    from ai.config import Settings
    from ai.providers import Provider
    monkeypatch.setenv('ZEUS_HUB_MODE', 'development')
    def forbidden(**kwargs):
        raise AssertionError('Development must never call HTTP')
    monkeypatch.setattr(httpx, 'AsyncClient', forbidden)
    settings = Settings.from_env()
    result = asyncio.run(Provider(settings.models['fast'], settings).generate([{'role': 'user', 'content': 'Hi'}]))
    assert result['estimated_cost'] == 0


def test_existing_credit_tables_untouched(client):
    import uuid
    import sqlite3
    c, app, path = client
    with sqlite3.connect(path) as conn:
        conn.execute("INSERT INTO song_credits(user_id,balance,monthly_allowance) VALUES('alice',73,20)")
        conn.execute("INSERT INTO video_credits(user_id,balance,monthly_allowance) VALUES('alice',9,3)")
        before = {table: conn.execute('SELECT * FROM ' + table).fetchall() for table in ('song_credits', 'video_credits', 'credit_ledger')}
    c.post('/api/hub/requests', json={'request_id': str(uuid.uuid4()), 'prompt': 'Hello', 'max_credits': 100})
    with sqlite3.connect(path) as conn:
        after = {table: conn.execute('SELECT * FROM ' + table).fetchall() for table in before}
    assert after == before


def test_empty_answer_retains_provider_usage(client, monkeypatch):
    import uuid
    import httpx
    from ai.config import Settings, Model
    c, app, path = client
    settings = Settings(mode='live', models={'fast': Model('openai', 'test', 1, 2)}, routes={'default': 'fast'}, initial_allowance=10)
    monkeypatch.setattr(Settings, 'from_env', lambda: settings)
    monkeypatch.setenv('OPENAI_API_KEY', 'test-only-key')
    original = httpx.AsyncClient
    def transport(request):
        return httpx.Response(200, json={'choices': [{'message': {'content': '', 'reasoning_content': 'never expose'}}],
                                       'usage': {'prompt_tokens': 100, 'completion_tokens': 200}})
    monkeypatch.setattr(httpx, 'AsyncClient', lambda **kwargs: original(transport=httpx.MockTransport(transport), **kwargs))
    body = {'request_id': str(uuid.uuid4()), 'prompt': 'A question', 'max_credits': 100}
    assert c.post('/api/hub/requests', json=body).status_code == 202
    result = c.get('/api/hub/requests/' + body['request_id']).json()
    assert result['status'] == 'failed'
    assert result['zeus_credits_charged'] == 0
    assert result['usage'][0]['input_tokens'] == 100
    assert result['usage'][0]['output_tokens'] == 200
    assert result['usage'][0]['estimated_cost'] == 0.0005
    assert 'never expose' not in str(result)


@pytest.mark.parametrize('provider,key', [('anthropic', 'ANTHROPIC_API_KEY'), ('gemini', 'GEMINI_API_KEY'), ('grok', 'XAI_API_KEY'), ('openrouter', 'OPENROUTER_API_KEY')])
def test_other_provider_protocols(monkeypatch, provider, key):
    import json
    import httpx
    from ai.config import Model, Settings
    from ai.providers import Provider
    monkeypatch.setenv(key, 'test-key-not-real')
    original = httpx.AsyncClient
    captured = []
    def transport(request):
        captured.append(json.loads(request.content))
        if provider == 'anthropic':
            assert request.headers['anthropic-version'] == '2023-06-01'
            payload = {'content': [{'type': 'thinking', 'thinking': 'hidden'}, {'type': 'text', 'text': 'Answer'}], 'usage': {'input_tokens': 5, 'output_tokens': 10}}
        else:
            payload = {'choices': [{'message': {'content': 'Answer'}}], 'usage': {'prompt_tokens': 5, 'completion_tokens': 10}}
        return httpx.Response(200, json=payload)
    monkeypatch.setattr(httpx, 'AsyncClient', lambda **kwargs: original(transport=httpx.MockTransport(transport), **kwargs))
    result = asyncio.run(Provider(Model(provider, 'test-model', 1, 2), Settings(mode='live')).generate([{'role': 'user', 'content': 'Hello'}]))
    assert result['text'] == 'Answer'
    assert result['estimated_cost'] == 0.000025
    assert captured[0]['max_tokens'] == 1024
    if provider == 'anthropic':
        assert 'system' in captured[0] and all(m['role'] != 'system' for m in captured[0]['messages'])
    if provider == 'openrouter':
        assert captured[0]['provider']['allow_fallbacks'] is False


def test_timeout_is_enforced(client, monkeypatch):
    import uuid
    from ai.config import Settings
    from ai.providers import Provider
    c, app, path = client
    settings = Settings.from_env()
    settings.timeout_seconds = 0.01
    monkeypatch.setattr(Settings, 'from_env', lambda: settings)
    cancelled = []
    async def stalled(self, messages):
        try:
            await asyncio.sleep(60)
        finally:
            cancelled.append(True)
    monkeypatch.setattr(Provider, 'generate', stalled)
    body = {'request_id': str(uuid.uuid4()), 'prompt': 'Hello', 'max_credits': 100}
    assert c.post('/api/hub/requests', json=body).status_code == 202
    assert cancelled == [True]
    result = c.get('/api/hub/requests/' + body['request_id']).json()
    assert result['status'] == 'failed' and result['usage'][0]['status'] == 'timeout'
    assert c.get('/api/hub/status').json()['balance'] == 100


def test_invalid_rates_fail_closed_with_python_optimization(monkeypatch):
    import json
    import subprocess
    import os
    raw = {'models': {'fast': {'provider': 'openai', 'model': 'test', 'input_per_million': 0, 'output_per_million': 0}},
           'routes': {'default': 'fast'}, 'credit_usd': 1, 'council_multiplier': 1, 'initial_allowance': 0,
           'free_daily_requests': 5, 'max_request_usd': 1}
    monkeypatch.setenv('ZEUS_HUB_MODE', 'live')
    monkeypatch.setenv('ZEUS_HUB_CONFIG', json.dumps(raw))
    code = 'from ai.config import Settings, HubError\ntry:\n Settings.from_env()\nexcept HubError:\n raise SystemExit(0)\nraise SystemExit(1)'
    env = {**os.environ, 'PYTHONPATH': str(pathlib.Path(__file__).parent.parent)}
    result = subprocess.run([sys.executable, '-O', '-c', code], env=env, capture_output=True)
    assert result.returncode == 0
