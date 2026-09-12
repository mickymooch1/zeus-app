"""Request execution; reservations always precede calls, failures refund atomically."""
import asyncio
import hashlib
import json
import logging

from .config import COUNCIL_BETA_FULL_CREDITS, COUNCIL_BETA_PARTIAL_CREDITS, HubError
from .council import consult
from .pricing import cost, credits, input_bound, quote
from .providers import Provider, available
from .routing import AIRouter
from .search import WEB_CONTEXT_BYTES, cite, reservation_messages, search, validate_query

log = logging.getLogger('zeus.hub')


def _alert_orchestration_failure(feature: str, error: BaseException) -> None:
    """Fires only for a failure that is NOT already a HubError -- a
    provider-level failure (timeout/non-2xx/malformed) already raised as a
    HubError from ai/providers.py and was already alerted right there;
    alerting again here would double-count the same root cause. What
    reaches this instead is an orchestration-level failure: the outer
    asyncio.timeout(...) in execute() firing (distinct from any single
    provider's own httpx timeout, see generate()'s inner asyncio.wait_for),
    or an unexpected bug in council/routing/search glue code. Only the
    exception's TYPE name is ever passed on -- never str(error), which
    could in principle contain fragments of the request.
    """
    try:
        import alerts
        if isinstance(error, TimeoutError):
            alerts.alert_hub_provider_timeout(f'{feature}(orchestration)')
        else:
            alerts.alert_hub_malformed_response(f'{feature}(orchestration)', type(error).__name__)
    except Exception:
        log.exception('hub: could not record incident for orchestration failure')


def fingerprint(body, mode):
    parts = [mode, body.feature, body.prompt, str(body.conversation_id or '')]
    # Keep old/OFF fingerprints stable, including recovery of pre-feature requests.
    if getattr(body, 'web_search', False):
        parts.extend([True, body.search_query])
    return hashlib.sha256(json.dumps(parts, ensure_ascii=False).encode()).hexdigest()


def prepare(store, settings, user, body):
    web_search = getattr(body, 'web_search', False)
    if web_search:
        validate_query(body.search_query)
    settings.authorize(user['id'], body.feature)
    if settings.mode == 'disabled':
        raise HubError('Zeus Hub is not enabled yet. The existing Zeus assistant is still available.')
    if not body.prompt.strip() or len(body.prompt.encode('utf-8')) > settings.max_input_bytes:
        raise HubError(f'Enter a shorter prompt (maximum {settings.max_input_bytes:,} UTF-8 bytes).', 422)
    extra_bytes = WEB_CONTEXT_BYTES if web_search and settings.mode != 'development' else 0
    if extra_bytes and len(body.prompt.encode('utf-8')) + extra_bytes > settings.max_context_bytes:
        raise HubError('Shorten your message to leave room for web search evidence.', 422)
    messages = []
    if body.conversation_id:
        history = store.conversation(user['id'], settings.mode, str(body.conversation_id), body.feature)
        if len(history['requests']) >= 100:
            raise HubError('This conversation is full. Please start a new chat.', 422)
        for request in history['requests']:
            if request['status'] == 'succeeded':
                messages.extend([{'role': 'user', 'content': request['prompt']}, {'role': 'assistant', 'content': request['result']['text']}])
    # Retain the most recent complete turns within a bounded provider context.
    while messages and (len(messages) > 18 or sum(len(m['content'].encode()) for m in messages) + len(body.prompt.encode()) + extra_bytes > settings.max_context_bytes):
        messages = messages[2:]
    messages.append({'role': 'user', 'content': body.prompt.strip()})
    selected = AIRouter(settings).select(body.prompt)
    names = [selected] if body.feature == 'ask' else settings.members + [settings.judge]
    if body.feature == 'council' and len(settings.members) < 2:
        raise HubError('Council needs at least two configured models.')
    if any(not available(settings.models[name]) for name in names):
        raise HubError('The selected AI providers are not configured yet.')
    estimate = quote(settings, body.feature, reservation_messages(messages) if extra_bytes else messages, selected)
    cap = settings.council_max_request_usd if (body.feature == 'council' and settings.mode == 'beta') else settings.max_request_usd
    if estimate['estimated_cost'] > cap:
        raise HubError('This request exceeds the configured Hub cost limit. Please shorten your request.', 422)
    return messages, selected, estimate


async def execute(store, settings, user_id, request_id, feature, messages, selected, *, search_query=None):
    web_context = None
    sources = []
    async def generate(name, conversation):
        model = settings.models[name]
        bound = cost(model, input_bound(reservation_messages(conversation) if web_context is not None else conversation), model.max_output_tokens)
        usage_id = store.start_usage(user_id, request_id, model, bound)
        try:
            provider = Provider(model, settings)
            call = provider.generate(conversation, web_context=web_context) if web_context is not None else provider.generate(conversation)
            result = await asyncio.wait_for(call, timeout=settings.timeout_seconds)
            store.finish_usage(usage_id, result, 'succeeded' if result['usage_known'] else 'succeeded_usage_unknown')
            log.info('hub request_id=%s provider=%s model=%s input_tokens=%s output_tokens=%s estimated_cost=%s status=succeeded',
                     request_id, model.provider, result['model'], result['input_tokens'], result['output_tokens'], result['estimated_cost'])
            return result
        except BaseException as error:
            store.finish_usage(usage_id, result=error.usage if isinstance(error, HubError) else None,
                               status='timeout' if isinstance(error, (TimeoutError, asyncio.CancelledError)) else 'failed')
            log.warning('hub request_id=%s provider=%s model=%s status=failed', request_id, model.provider, model.model)
            raise

    async def progress(message):
        store.progress(user_id, request_id, message)

    try:
        async with asyncio.timeout(settings.timeout_seconds * 2 + 10):
            # One search after reservation; the shared callback supplies identical
            # bounded evidence to every member and the judge, without duplicating it.
            if search_query is not None and settings.mode != 'development':
                await progress('Zeus is searching the web…')
                web_context, sources = await search(search_query, prompt=messages[-1]['content'])
            if feature == 'council':
                result = await consult(settings.members, settings.judge, messages, generate, progress)
            else:
                await progress('Zeus is working…')
                result = await generate(selected, messages)
            if sources:
                result['text'] = cite(result['text'], sources)
                result['sources'] = sources
                # Preserve raw member IDs during synthesis so link expansion cannot
                # inflate the judge input beyond its existing conservative quote.
                for member in result.get('members', []):
                    member['text'] = cite(member['text'], sources)
        # Only successful calls with reported tokens are charged. Unknown/failed work is waived.
        usd = sum(row['estimated_cost'] or 0 for row in store.usage(user_id, request_id) if row['status'] == 'succeeded')
        if feature == 'council' and settings.mode == 'beta':
            # Fixed private-beta settlement: full rate unless exactly one of
            # three members failed. consult() requires >=2 successful members
            # to return at all, so 'unavailable' here is always 0 or 1 --
            # every other failure (judge fails, or 2+ members fail) already
            # takes the exception path below, which refunds the full 15.
            charge = COUNCIL_BETA_FULL_CREDITS if result.get('unavailable', 0) == 0 else COUNCIL_BETA_PARTIAL_CREDITS
        else:
            charge = 0 if settings.mode == 'development' else credits(settings, usd, feature)
        result['selection_note'] = 'Zeus selected the best AI for this task.'
        result['simulated'] = settings.mode == 'development'
        store.finish(user_id, request_id, 'succeeded', result, charge)
    except BaseException as error:
        message = str(error) if isinstance(error, HubError) else 'Zeus could not complete this request. Your reserved Hub credits were refunded.'
        store.finish(user_id, request_id, 'failed', None, 0, message)
        if isinstance(error, (asyncio.CancelledError, KeyboardInterrupt, SystemExit)):
            raise
        if not isinstance(error, HubError):
            _alert_orchestration_failure(feature, error)
