"""Provider-failure diagnostic logging: enough detail to tell rate-limit vs
quota vs bad-request apart from Railway logs alone, without ever logging a
secret, the request payload, the user's prompt, or the model's output."""
import logging

import httpx
import pytest

from ai.config import HubError, Model, Settings
from ai.providers import Provider, _error_detail, _sanitize

OPENAI_MODEL = Model(provider='openai', model='gpt-4.1-mini-2025-04-14', input_per_million=0.40, output_per_million=1.60, max_output_tokens=400)


def _response(status, json_body=None, text_body=None):
    request = httpx.Request('POST', 'https://api.openai.com/v1/chat/completions')
    if json_body is not None:
        return httpx.Response(status, json=json_body, request=request)
    return httpx.Response(status, text=text_body or '', request=request)


def test_sanitize_redacts_common_secret_shapes_and_truncates():
    text = 'call failed for key sk-abcdEFGH12345678 and Bearer abcde.fghij.klmno and AIzaSyABCDEFGHIJKLMNOPQRSTUVWXYZ1234'
    cleaned = _sanitize(text)
    assert 'sk-abcdEFGH12345678' not in cleaned
    assert 'Bearer abcde.fghij.klmno' not in cleaned
    assert 'AIzaSyABCDEFGHIJKLMNOPQRSTUVWXYZ1234' not in cleaned
    assert '[redacted]' in cleaned
    assert len(_sanitize('x' * 1000)) == 300


def test_error_detail_extracts_openai_style_error_body():
    detail = _error_detail(_response(429, {'error': {'message': 'You exceeded your current quota.', 'type': 'insufficient_quota', 'code': 'insufficient_quota'}}))
    assert detail == {'error_type': 'insufficient_quota', 'error_code': 'insufficient_quota', 'error_message': 'You exceeded your current quota.'}


def test_error_detail_extracts_anthropic_style_error_body_with_no_code():
    detail = _error_detail(_response(400, {'type': 'error', 'error': {'type': 'invalid_request_error', 'message': 'max_tokens is too large.'}}))
    assert detail['error_type'] == 'invalid_request_error'
    assert detail['error_code'] is None
    assert detail['error_message'] == 'max_tokens is too large.'


def test_error_detail_extracts_gemini_style_error_body_with_numeric_code():
    detail = _error_detail(_response(404, {'error': {'code': 404, 'message': 'Model not found.', 'status': 'NOT_FOUND'}}))
    assert detail['error_type'] == 'NOT_FOUND'
    assert detail['error_code'] == '404'
    assert detail['error_message'] == 'Model not found.'


def test_error_detail_falls_back_to_sanitized_text_for_non_json_body():
    detail = _error_detail(_response(404, text_body='<html>404 Not Found</html>'))
    assert detail['error_type'] is None
    assert detail['error_code'] is None
    assert detail['error_message'] == '<html>404 Not Found</html>'


def test_error_detail_falls_back_when_json_body_has_no_error_key():
    detail = _error_detail(_response(500, {'message': 'internal error, no error key here'}))
    assert detail['error_type'] is None
    assert detail['error_code'] is None
    assert isinstance(detail['error_message'], str)


@pytest.mark.asyncio
async def test_failed_provider_call_logs_sanitized_detail_and_raises_same_generic_error(monkeypatch, caplog):
    monkeypatch.setenv('OPENAI_API_KEY', 'sk-not-a-real-key-1234567890')
    secret_in_body = 'sk-should-never-reach-logs-abcdefgh'

    async def fake_post(self, url, headers=None, json=None):
        return _response(429, {'error': {'message': f'quota exceeded, offending key {secret_in_body}', 'type': 'insufficient_quota', 'code': 'insufficient_quota'}})
    monkeypatch.setattr(httpx.AsyncClient, 'post', fake_post)

    settings = Settings(mode='beta', timeout_seconds=30)
    provider = Provider(OPENAI_MODEL, settings)
    with caplog.at_level(logging.WARNING, logger='zeus.hub'):
        with pytest.raises(HubError) as exc_info:
            await provider.generate([{'role': 'user', 'content': 'a private user prompt that must never be logged'}])

    # Same user-facing failure as before this change -- generic message, 502.
    assert exc_info.value.status == 502
    assert str(exc_info.value) == 'The AI provider is unavailable. Please try a new request later.'

    [record] = [r for r in caplog.records if r.name == 'zeus.hub']
    assert 'provider=openai' in record.message
    assert 'status=429' in record.message
    assert 'insufficient_quota' in record.message
    # Never the API key, never the request payload, never the user's prompt.
    assert 'sk-not-a-real-key-1234567890' not in record.message
    assert secret_in_body not in record.message
    assert '[redacted]' in record.message
    assert 'a private user prompt that must never be logged' not in record.message


@pytest.mark.asyncio
async def test_timeout_path_is_unaffected_by_the_new_error_logging(monkeypatch, caplog):
    monkeypatch.setenv('OPENAI_API_KEY', 'sk-not-a-real-key-1234567890')

    async def fake_post(self, url, headers=None, json=None):
        raise httpx.TimeoutException('timed out')
    monkeypatch.setattr(httpx.AsyncClient, 'post', fake_post)

    settings = Settings(mode='beta', timeout_seconds=30)
    provider = Provider(OPENAI_MODEL, settings)
    with caplog.at_level(logging.WARNING, logger='zeus.hub'):
        with pytest.raises(HubError) as exc_info:
            await provider.generate([{'role': 'user', 'content': 'hi'}])
    assert exc_info.value.status == 504
    assert not [r for r in caplog.records if r.name == 'zeus.hub' and 'provider_error' in r.message]
