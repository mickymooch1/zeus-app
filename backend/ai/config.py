"""Server-only configuration. No paid defaults and no production billing mutations."""
import json
import math
import os
from dataclasses import dataclass, field


def _require(condition):
    if not condition:
        raise ValueError('Invalid Hub configuration')


class HubError(Exception):
    def __init__(self, message, status=503, usage=None):
        super().__init__(message)
        self.status = status
        self.usage = usage


# Fixed public-beta Council settlement policy — deliberately not
# Railway-configurable, so changing it requires a reviewed code change,
# not a variable edit. reserve == full: a full-success request charges
# exactly what it reserved (no rounding). One member failing (of three)
# still charges the flat partial rate; any other failure path (judge
# fails, or two-plus members fail) is unaffected here — it already
# refunds the full reservation via the existing generic failure path.
COUNCIL_BETA_RESERVE_CREDITS = 15
COUNCIL_BETA_FULL_CREDITS = 15
COUNCIL_BETA_PARTIAL_CREDITS = 12


@dataclass(frozen=True)
class Model:
    provider: str
    model: str
    input_per_million: float
    output_per_million: float
    max_output_tokens: int = 1024


@dataclass
class Settings:
    mode: str = 'disabled'
    models: dict = field(default_factory=dict)
    routes: dict = field(default_factory=dict)
    members: list = field(default_factory=list)
    judge: str = ''
    credit_usd: float = 0.01
    council_multiplier: float = 1.0
    initial_allowance: int = 0
    free_daily_requests: int = 5
    daily_requests: int = 50
    requests_per_minute: int = 5
    timeout_seconds: int = 45
    max_request_usd: float = 0.5
    max_input_bytes: int = 12000
    max_context_bytes: int = 24000
    beta_user_ids: list = field(default_factory=list)
    council_beta_user_ids: list = field(default_factory=list)
    council_max_request_usd: float = 0

    def authorize(self, user_id, feature=None):
        # Public beta access is gated by the authenticated, verified API
        # context; Council configuration and Hub credit reservation enforce
        # feature availability and affordability.
        return None

    @classmethod
    def from_env(cls):
        mode = os.environ.get('ZEUS_HUB_MODE', 'disabled')
        if mode == 'disabled':
            return cls()
        if mode == 'development':
            return cls(mode=mode, models={n: Model('simulated', n, 1, 2, 512) for n in ['fast', 'careful', 'creative']},
                       routes={'default': 'fast', 'coding': 'careful', 'reasoning': 'careful', 'writing': 'creative'},
                       members=['fast', 'careful', 'creative'], judge='careful', initial_allowance=100)
        if mode not in ('live', 'beta'):
            raise HubError('Invalid Hub mode; live calls are disabled.')
        try:
            raw = json.loads(os.environ['ZEUS_HUB_CONFIG'])
            settings = cls(mode=mode, **{k: v for k, v in raw.items() if k != 'models'})
            settings.models = {name: Model(**value) for name, value in raw['models'].items()}
            if mode == 'beta':
                # Keep this legacy list for the separate diagnostics gate;
                # membership here does not authorize Hub requests.
                _require(isinstance(settings.beta_user_ids, list) and len(settings.beta_user_ids) > 0)
                _require(all(isinstance(value, str) and value.strip() for value in settings.beta_user_ids))
                # Council shape is validated from its global member config,
                # independent of the legacy per-user Council allowlist.
                if settings.members:
                    _require(len(settings.members) == 3 and bool(settings.judge))
                    _require(len(settings.models) - len(set(settings.members) | {settings.judge}) == 1)
                    _require(math.isfinite(settings.council_max_request_usd) and settings.council_max_request_usd > 0)
                else:
                    _require(len(settings.models) == 1 and not settings.judge)
                # Accept the pre-rollout Railway value during code deployment,
                # but never mint or mark a zero-credit public-beta grant.
                _require(settings.initial_allowance in (0, 20))
            for key in ('credit_usd', 'council_multiplier', 'initial_allowance', 'free_daily_requests', 'max_request_usd'):
                _require(key in raw)
            for key in ('credit_usd', 'council_multiplier', 'max_request_usd'):
                _require(math.isfinite(getattr(settings, key)) and getattr(settings, key) > 0)
            for key in ('initial_allowance', 'free_daily_requests', 'daily_requests', 'requests_per_minute'):
                value = getattr(settings, key)
                _require(type(value) is int and 0 <= value <= 100000)
            _require(1 <= settings.timeout_seconds <= 60)
            _require(1 <= settings.max_input_bytes <= 12000)
            _require(settings.max_input_bytes <= settings.max_context_bytes <= 24000)
            _require(settings.routes['default'] in settings.models)
            _require(all(v in settings.models for v in settings.routes.values()))
            _require(0 <= len(settings.members) <= 3 and len(set(settings.members)) == len(settings.members))
            _require(all(v in settings.models for v in settings.members))
            if settings.members:
                _require(len(settings.members) >= 2 and settings.judge in settings.models)
                _require(len({(settings.models[v].provider, settings.models[v].model) for v in settings.members}) == len(settings.members))
            for model in settings.models.values():
                _require(model.provider in {'openai', 'anthropic', 'gemini', 'grok', 'openrouter'})
                _require(isinstance(model.model, str) and 0 < len(model.model) <= 200)
                _require(all(math.isfinite(x) and x > 0 for x in (model.input_per_million, model.output_per_million)))
                _require(type(model.max_output_tokens) is int and 128 <= model.max_output_tokens <= 2048)
                # Anthropic and OpenAI must never be reached via OpenRouter, and
                # OpenRouter must only carry models with no direct option (e.g.
                # Mistral). OpenRouter's own API requires a "vendor/model-name"
                # model id; Anthropic's and OpenAI's native APIs never accept a
                # slash in the model id. That's a hard fact of both APIs, not a
                # convention, so it catches both directions of misconfiguration:
                # an Anthropic/OpenAI model accidentally pointed at OpenRouter
                # (which would silently make OpenRouter a hard dependency for a
                # model that doesn't need it), and a slash-qualified model (no
                # direct provider here) accidentally pointed at a direct
                # provider (which would otherwise 404 at request time instead
                # of failing config validation up front).
                if model.provider in ('anthropic', 'openai'):
                    _require('/' not in model.model)
                if model.provider == 'openrouter':
                    _require('/' in model.model)
                    _require(model.model.split('/', 1)[0].lower() not in ('anthropic', 'openai'))
            return settings
        except (KeyError, TypeError, ValueError, AttributeError):
            raise HubError('Hub model rates and allowances need valid server configuration before live use.') from None

