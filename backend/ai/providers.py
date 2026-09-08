"""Five providers, one final-text interface. Endpoints and keys are server-only."""
import asyncio
import os
from typing import Protocol

import httpx

from .config import HubError
from .pricing import cost

ENDPOINTS = {
    'openai': ('https://api.openai.com/v1/chat/completions', 'OPENAI_API_KEY'),
    'anthropic': ('https://api.anthropic.com/v1/messages', 'ANTHROPIC_API_KEY'),
    'gemini': ('https://generativelanguage.googleapis.com/v1beta/openai/chat/completions', 'GEMINI_API_KEY'),
    'grok': ('https://api.x.ai/v1/chat/completions', 'XAI_API_KEY'),
    'openrouter': ('https://openrouter.ai/api/v1/chat/completions', 'OPENROUTER_API_KEY'),
}
SYSTEM = 'You are Zeus, a helpful AI assistant. Return only the useful final answer, with concise explanations and uncertainty where needed. Do not reveal hidden reasoning. You cannot browse, execute code, deploy websites or take external actions in this chat.'


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

    async def generate(self, messages):
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
        headers = {'Authorization': f'Bearer {key}'}
        payload = {'model': model.model, 'messages': [{'role': 'system', 'content': SYSTEM}] + messages}
        if model.provider == 'anthropic':
            headers = {'x-api-key': key, 'anthropic-version': '2023-06-01'}
            payload.update(messages=messages, system=SYSTEM, max_tokens=model.max_output_tokens)
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
        except (httpx.HTTPError, ValueError, KeyError, IndexError, TypeError):
            raise HubError('The AI provider is unavailable. Please try a new request later.', 502) from None
