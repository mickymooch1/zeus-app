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

log = logging.getLogger('zeus.hub')


def fingerprint(body, mode):
    return hashlib.sha256(json.dumps([mode, body.feature, body.prompt, str(body.conversation_id or '')], ensure_ascii=False).encode()).hexdigest()


def prepare(store, settings, user, body):
    settings.authorize(user['id'], body.feature)
    if settings.mode == 'disabled':
        raise HubError('Zeus Hub is not enabled yet. The existing Zeus assistant is still available.')
    if not body.prompt.strip() or len(body.prompt.encode('utf-8')) > settings.max_input_bytes:
        raise HubError(f'Enter a shorter prompt (maximum {settings.max_input_bytes:,} UTF-8 bytes).', 422)
    messages = []
    if body.conversation_id:
        history = store.conversation(user['id'], settings.mode, str(body.conversation_id), body.feature)
        if len(history['requests']) >= 100:
            raise HubError('This conversation is full. Please start a new chat.', 422)
        for request in history['requests']:
            if request['status'] == 'succeeded':
                messages.extend([{'role': 'user', 'content': request['prompt']}, {'role': 'assistant', 'content': request['result']['text']}])
    # Retain the most recent complete turns within a bounded provider context.
    while messages and (len(messages) > 18 or sum(len(m['content'].encode()) for m in messages) + len(body.prompt.encode()) > settings.max_context_bytes):
        messages = messages[2:]
    messages.append({'role': 'user', 'content': body.prompt.strip()})
    selected = AIRouter(settings).select(body.prompt)
    names = [selected] if body.feature == 'ask' else settings.members + [settings.judge]
    if body.feature == 'council' and len(settings.members) < 2:
        raise HubError('Council needs at least two configured models.')
    if any(not available(settings.models[name]) for name in names):
        raise HubError('The selected AI providers are not configured yet.')
    estimate = quote(settings, body.feature, messages, selected)
    cap = settings.council_max_request_usd if (body.feature == 'council' and settings.mode == 'beta') else settings.max_request_usd
    if estimate['estimated_cost'] > cap:
        raise HubError('This request exceeds the configured Hub cost limit. Please shorten your request.', 422)
    return messages, selected, estimate


async def execute(store, settings, user_id, request_id, feature, messages, selected):
    async def generate(name, conversation):
        model = settings.models[name]
        bound = cost(model, input_bound(conversation), model.max_output_tokens)
        usage_id = store.start_usage(user_id, request_id, model, bound)
        try:
            result = await asyncio.wait_for(Provider(model, settings).generate(conversation), timeout=settings.timeout_seconds)
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
            if feature == 'council':
                result = await consult(settings.members, settings.judge, messages, generate, progress)
            else:
                await progress('Zeus is working…')
                result = await generate(selected, messages)
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
