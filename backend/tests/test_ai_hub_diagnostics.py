"""Admin diagnostics endpoint: strict three-way auth gate, read-only queries,
and no exposure of prompt/result/error content."""
import json
import time
from pathlib import Path

import pytest


@pytest.fixture
def beta_settings(monkeypatch):
    raw = json.loads((Path(__file__).parents[1] / 'ai/beta-config.example.json').read_text())
    raw['beta_user_ids'] = ['admin-in-beta']
    monkeypatch.setenv('ZEUS_HUB_MODE', 'beta')
    monkeypatch.setenv('ZEUS_HUB_CONFIG', json.dumps(raw))
    monkeypatch.setenv('ANTHROPIC_API_KEY', 'fake-test-key')


@pytest.fixture
def client(beta_settings, tmp_path, monkeypatch):
    monkeypatch.setenv('JWT_SECRET', 'diagnostics-tests-only-secret-1234567890')
    import auth
    import db
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from ai.api import router
    app = FastAPI()
    app.include_router(router)
    path = tmp_path / 'diagnostics.db'
    app.dependency_overrides[db.get_db_path_dep] = lambda: path
    with TestClient(app) as c:
        c._db_path = path
        yield c, auth, app


def _as(client_tuple, user):
    client, auth, app = client_tuple
    app.dependency_overrides[auth.get_current_user] = lambda: user
    return client


def test_denies_non_admin_even_if_beta_and_verified(client):
    c = _as(client, {'id': 'admin-in-beta', 'email_verified': 1, 'is_admin': False})
    assert c.get('/api/hub/diagnostics').status_code == 403


def test_denies_admin_not_email_verified(client):
    c = _as(client, {'id': 'admin-in-beta', 'email_verified': 0, 'is_admin': True})
    assert c.get('/api/hub/diagnostics').status_code == 403


def test_denies_admin_not_in_beta_allowlist(client):
    # Correctly configured admin, but a different user id than the one
    # seeded into beta_user_ids — "other admins must be denied".
    c = _as(client, {'id': 'other-admin', 'email_verified': 1, 'is_admin': True})
    assert c.get('/api/hub/diagnostics').status_code == 403


def test_allows_admin_that_is_verified_and_in_beta_allowlist(client):
    c = _as(client, {'id': 'admin-in-beta', 'email_verified': 1, 'is_admin': True})
    resp = c.get('/api/hub/diagnostics')
    assert resp.status_code == 200
    body = resp.json()
    for key in ('balance', 'credits_spent', 'provider_cost', 'avg_ask_cost', 'requests'):
        assert key in body


def test_response_never_contains_prompt_result_or_error(client):
    from ai.store import Store
    store = Store(client[0]._db_path)
    store.grant('someone', 'beta', 10, 'seed')
    store.reserve('someone', 'beta', 'req-1', 'conv-1', 'ask', 'a secret prompt nobody should see', 1, 'fp1', 100, 100)
    usage_id = store.start_usage('someone', 'req-1', __import__('ai.config', fromlist=['Model']).Model('anthropic', 'claude-haiku', 1, 1, 100), estimated_cost=0.002)
    store.finish_usage(usage_id, {'input_tokens': 10, 'output_tokens': 20, 'estimated_cost': 0.002}, status='succeeded')
    store.finish('someone', 'req-1', 'succeeded', {'text': 'a secret response nobody should see'}, 1, error=None)

    c = _as(client, {'id': 'admin-in-beta', 'email_verified': 1, 'is_admin': True})
    body = c.get('/api/hub/diagnostics').json()
    raw = json.dumps(body)
    assert 'a secret prompt' not in raw
    assert 'a secret response' not in raw
    for req in body['requests']:
        assert 'prompt' not in req and 'result' not in req and 'error' not in req


def test_stats_and_request_shape_reflect_seeded_data(client):
    from ai.store import Store
    from ai.config import Model
    store = Store(client[0]._db_path)
    store.grant('u1', 'beta', 5, 'seed1')
    store.reserve('u1', 'beta', 'req-a', 'conv-a', 'ask', 'p', 2, 'fp-a', 100, 100)
    usage_id = store.start_usage('u1', 'req-a', Model('anthropic', 'claude-haiku', 1, 1, 100), estimated_cost=0.01)
    store.finish_usage(usage_id, {'input_tokens': 5, 'output_tokens': 15, 'estimated_cost': 0.01}, status='succeeded')
    store.finish('u1', 'req-a', 'succeeded', {'text': 'ok'}, 2, error=None)

    # A council-style request: two provider usage rows under one request_id.
    store.grant('u1', 'beta', 5, 'seed2')
    store.reserve('u1', 'beta', 'req-b', 'conv-b', 'council', 'p2', 3, 'fp-b', 100, 100)
    u1 = store.start_usage('u1', 'req-b', Model('anthropic', 'claude-haiku', 1, 1, 100), estimated_cost=0.02)
    store.finish_usage(u1, {'input_tokens': 8, 'output_tokens': 12, 'estimated_cost': 0.02}, status='succeeded')
    u2 = store.start_usage('u1', 'req-b', Model('openai', 'gpt-mini', 1, 1, 100), estimated_cost=0.03)
    store.finish_usage(u2, {'input_tokens': 9, 'output_tokens': 13, 'estimated_cost': 0.03}, status='succeeded')
    store.finish('u1', 'req-b', 'succeeded', {'text': 'ok'}, 3, error=None)

    c = _as(client, {'id': 'admin-in-beta', 'email_verified': 1, 'is_admin': True})
    body = c.get('/api/hub/diagnostics').json()

    assert body['credits_spent'] == 5  # 2 + 3
    assert body['provider_cost'] == pytest.approx(0.06)  # 0.01 + 0.02 + 0.03
    assert body['avg_ask_cost'] == pytest.approx(0.01)  # only the 'ask' feature usage row

    by_id = {r['request_id']: r for r in body['requests']}
    assert by_id['req-a']['feature'] == 'ask'
    assert len(by_id['req-a']['providers']) == 1
    assert by_id['req-b']['feature'] == 'council'
    assert len(by_id['req-b']['providers']) == 2
    provider_names = {p['provider'] for p in by_id['req-b']['providers']}
    assert provider_names == {'anthropic', 'openai'}
