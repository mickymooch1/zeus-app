"""Five providers, one final-text interface. Endpoints and keys are server-only."""
import asyncio
import logging
import os
import re
from typing import Protocol

import httpx

from .config import HubError
from .pricing import cost
from .search import WEB_RULES

log = logging.getLogger('zeus.hub')

ENDPOINTS = {
    'openai': ('https://api.openai.com/v1/chat/completions', 'OPENAI_API_KEY'),
    'anthropic': ('https://api.anthropic.com/v1/messages', 'ANTHROPIC_API_KEY'),
    'gemini': ('https://generativelanguage.googleapis.com/v1beta/openai/chat/completions', 'GEMINI_API_KEY'),
    'grok': ('https://api.x.ai/v1/chat/completions', 'XAI_API_KEY'),
    'openrouter': ('https://openrouter.ai/api/v1/chat/completions', 'OPENROUTER_API_KEY'),
}
SYSTEM = 'You are Zeus, a helpful AI assistant. Return only the useful final answer, with concise explanations and uncertainty where needed. Do not reveal hidden reasoning. You cannot browse, execute code, deploy websites or take external actions in this chat.'

# Diagnostic logging for a failed provider HTTP response -- never the request
# (headers/payload, so the API key can't appear) and never the user's prompt
# or the model's generated text (those aren't in an error response at all).
# Only a truncated, secret-scrubbed slice of the provider's own error body.
_SECRET_PATTERN = re.compile(r'(sk|pk)-[A-Za-z0-9_-]{8,}|AIza[A-Za-z0-9_-]{10,}|xai-[A-Za-z0-9_-]{8,}|Bearer\s+\S+', re.IGNORECASE)


def _sanitize(text, limit=300):
    if not isinstance(text, str):
        return None
    text = _SECRET_PATTERN.sub('[redacted]', text)
    # Collapse newlines/control whitespace so one provider error can never
    # split into multiple Railway log lines (pretty-printed JSON bodies do
    # this by default -- e.g. Gemini's error responses).
    return re.sub(r'\s+', ' ', text).strip()[:limit]


def _error_detail(response):
    try:
        body = response.json()
    except ValueError:
        return {'error_type': None, 'error_code': None, 'error_message': _sanitize(response.text)}
    # Most providers return a bare {"error": {...}} object; Gemini's
    # OpenAI-compatibility endpoint instead wraps it in a one-element list.
    if isinstance(body, list) and body and isinstance(body[0], dict):
        body = body[0]
    error = body.get('error') if isinstance(body, dict) else None
    if not isinstance(error, dict):
        return {'error_type': None, 'error_code': None, 'error_message': _sanitize(response.text)}
    error_type, error_code, message = error.get('type') or error.get('status'), error.get('code'), error.get('message')
    return {'error_type': _sanitize(str(error_type), limit=100) if error_type is not None else None,
            'error_code': _sanitize(str(error_code), limit=100) if error_code is not None else None,
            'error_message': _sanitize(message) if isinstance(message, str) else None}


class AIProvider(Protocol):
    provider_name: str
    model_name: str

    async def generate(self, messages: list[dict]) -> dict: ...


def available(model):
    return model.provider == 'simulated' or bool(os.environ.get(ENDPOINTS[model.provider][1], '').strip())


class Provider:
    def __init__(self, model, settings):
        self.model = model
        self.settings = settings
        self.provider_name = model.provider
        self.model_name = model.model

    async def generate(self, messages, *, web_context=None):
        model = self.model
        if self.settings.mode == 'development' and model.provider == 'simulated':
            await asyncio.sleep(0.05)
            text = ('**Development simulation — no AI provider was called.**\n\n'
                    'Zeus received your request. Live answers will be available after Hub model rates and allowances are configured.')
            if 'Council conclusions' in messages[-1]['content']:
                text += '\n\n## Zeus Verdict\nThis is a simulated verdict.\n\n### Agreement\nThe test members responded.\n\n### Disagreement\nNo real analysis was performed.\n\n### Risks and uncertainties\nDo not use this simulated result as advice.'
            return {'text': text, 'provider': 'simulated', 'model': model.model, 'input_tokens': 0,
                    'output_tokens': 0, 'estimated_cost': 0.0, 'usage_known': True}
        if self.settings.mode not in ('live', 'beta') or model.provider not in ENDPOINTS:
            raise HubError('Live AI calls are disabled.')
        url, key_name = ENDPOINTS[model.provider]
        key = os.environ.get(key_name, '').strip()
        if not key:
            raise HubError('The selected AI provider is not configured.')
        system = SYSTEM
        if web_context is not None:
            system += ' ' + WEB_RULES
            messages = messages + [{'role': 'user', 'content': web_context}]
        headers = {'Authorization': f'Bearer {key}'}
        payload = {'model': model.model, 'messages': [{'role': 'system', 'content': system}] + messages}
        if model.provider == 'anthropic':
            headers = {'x-api-key': key, 'anthropic-version': '2023-06-01'}
            payload.update(messages=messages, system=system, max_tokens=model.max_output_tokens)
        else:
            limit_key = 'max_completion_tokens' if model.provider == 'openai' else 'max_tokens'
            payload[limit_key] = model.max_output_tokens
            if model.provider == 'openrouter':
                payload['provider'] = {'allow_fallbacks': False, 'require_parameters': True}
        try:
            async with httpx.AsyncClient(timeout=self.settings.timeout_seconds, follow_redirects=False) as client:
                response = await client.post(url, headers=headers, json=payload)
                response.raise_for_status()
                data = response.json()
            usage = data.get('usage') or {}
            if model.provider == 'anthropic':
                text = '\n'.join(part['text'] for part in data['content'] if part.get('type') == 'text')
                incoming, outgoing = usage.get('input_tokens'), usage.get('output_tokens')
            else:
                text = data['choices'][0]['message'].get('content')
                incoming, outgoing = usage.get('prompt_tokens'), usage.get('completion_tokens')
            known = type(incoming) is int and type(outgoing) is int and incoming >= 0 and outgoing >= 0
            actual_model = data.get('model')
            if not isinstance(actual_model, str) or not actual_model or len(actual_model) > 200:
                actual_model = model.model
            measured = {'provider': model.provider, 'model': actual_model,
                        'input_tokens': incoming if known else None, 'output_tokens': outgoing if known else None,
                        'estimated_cost': cost(model, incoming, outgoing) if known else None, 'usage_known': known}
            if not isinstance(text, str) or not text.strip():
                raise HubError('The AI provider returned no usable answer.', 502, usage=measured)
            # Hidden reasoning fields are deliberately ignored.
            text = text.encode('utf-8')[:model.max_output_tokens * 8].decode('utf-8', errors='ignore')
            return {'text': text, **measured}
        except httpx.TimeoutException:
            raise HubError('The AI provider timed out. Your Hub credits will be refunded.', 504) from None
        except httpx.HTTPStatusError as error:
            detail = _error_detail(error.response)
            log.warning('hub provider_error provider=%s status=%s error_type=%s error_code=%s error_message=%s',
                        model.provider, error.response.status_code, detail['error_type'], detail['error_code'], detail['error_message'])
            raise HubError('The AI provider is unavailable. Please try a new request later.', 502) from None
        except (httpx.HTTPError, ValueError, KeyError, IndexError, TypeError):
            raise HubError('The AI provider is unavailable. Please try a new request later.', 502) from None
