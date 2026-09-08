"""Authenticated Hub API, registered ahead of the existing SPA fallback."""
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel, Field

from auth import get_current_user
from db import get_db_path_dep
from .config import HubError, Settings
from .service import execute, fingerprint, prepare
from .store import Store

router = APIRouter(prefix='/api/hub', tags=['Zeus Hub'])


class Submission(BaseModel):
    request_id: UUID
    conversation_id: UUID | None = None
    feature: Literal['ask', 'council'] = 'ask'
    prompt: str = Field(min_length=1, max_length=12000)
    max_credits: int = Field(default=0, ge=0, le=100000)


def context(user=Depends(get_current_user), path=Depends(get_db_path_dep)):
    try:
        settings = Settings.from_env()
        settings.authorize(user['id'])
        store = Store(path)
        store.recover(user['id'])
        if settings.mode != 'disabled':
            if not user.get('email_verified'):
                raise HubError('Verify your email before using Zeus Hub.', 403)
            # One-time explicitly configured allowance; later configuration changes do not top up old accounts.
            with store.connection() as conn:
                granted = conn.execute("SELECT 1 FROM hub_ledger WHERE user_id=? AND mode=? AND reference='grant:initial-v1'", (user['id'], settings.mode)).fetchone()
            if not granted and settings.mode != 'beta':
                store.grant(user['id'], settings.mode, settings.initial_allowance, 'initial-v1')
        return store, settings, user
    except HubError as error:
        raise HTTPException(error.status, str(error)) from None


@router.get('/status')
def status(ctx=Depends(context)):
    store, settings, user = ctx
    # Outside beta, unchanged: council_enabled reflects whether a council is
    # configured at all. In beta, it's per-caller -- true only for the one
    # allowlisted private-Council-beta account; everyone else on the general
    # Hub beta still sees Council as disabled, exactly as before.
    council_enabled = (settings.mode != 'beta' and len(settings.members) >= 2) or (settings.mode == 'beta' and user['id'] in settings.council_beta_user_ids)
    return {'mode': settings.mode, 'balance': store.balance(user['id'], settings.mode), 'balance_name': 'Hub Beta Credits' if settings.mode == 'beta' else 'Zeus Hub credits',
            'enabled': settings.mode != 'disabled', 'council_enabled': council_enabled,
            'max_input_bytes': settings.max_input_bytes, 'message': 'Development simulation: no paid AI calls.' if settings.mode == 'development' else None}


@router.post('/quote')
def get_quote(body: Submission, ctx=Depends(context)):
    store, settings, user = ctx
    try:
        _, _, estimate = prepare(store, settings, user, body)
        return {**estimate, 'balance': store.balance(user['id'], settings.mode), 'mode': settings.mode}
    except HubError as error:
        raise HTTPException(error.status, str(error)) from None


@router.post('/requests', status_code=202)
def submit(body: Submission, background: BackgroundTasks, ctx=Depends(context)):
    store, settings, user = ctx
    request_id = str(body.request_id)
    digest = fingerprint(body, settings.mode)
    try:
        # Replays retrieve the original result even after context or prices have changed.
        try:
            old = store.request(user['id'], request_id)
        except HubError:
            old = None
        if old:
            with store.connection() as conn:
                old_digest = conn.execute('SELECT fingerprint FROM hub_requests WHERE user_id=? AND request_id=?', (user['id'], request_id)).fetchone()[0]
            if old_digest != digest:
                raise HubError('Request ID was already used for different content.', 409)
            return {'request_id': request_id, 'conversation_id': old['conversation_id']}
        messages, selected, estimate = prepare(store, settings, user, body)
        if body.max_credits < estimate['credits']:
            raise HubError('The credit quote changed. Review a new quote before sending.', 409)
        conversation_id = str(body.conversation_id or body.request_id)
        is_free = user.get('subscription_status') not in ('active', 'trialing')
        daily = settings.free_daily_requests if is_free else settings.daily_requests
        reserved = store.reserve(user['id'], settings.mode, request_id, conversation_id, body.feature, body.prompt,
                                 estimate['credits'], digest, settings.requests_per_minute, daily)
        if not reserved['duplicate']:
            background.add_task(execute, store, settings, user['id'], request_id, body.feature, messages, selected)
        return {'request_id': request_id, 'conversation_id': conversation_id}
    except HubError as error:
        raise HTTPException(error.status, str(error)) from None


@router.get('/requests/{request_id}')
def get_request(request_id: UUID, ctx=Depends(context)):
    store, settings, user = ctx
    try:
        result = store.request(user['id'], str(request_id))
        result['usage'] = store.usage(user['id'], str(request_id))
        return result
    except HubError as error:
        raise HTTPException(error.status, str(error)) from None


@router.get('/conversations')
def conversations(ctx=Depends(context)):
    store, settings, user = ctx
    return store.history(user['id'], settings.mode)


@router.get('/conversations/{conversation_id}')
def conversation(conversation_id: UUID, ctx=Depends(context)):
    store, settings, user = ctx
    try:
        return store.conversation(user['id'], settings.mode, str(conversation_id))
    except HubError as error:
        raise HTTPException(error.status, str(error)) from None


# ── Admin diagnostics — separate, stricter gate; does not touch context() ──
# Denies unless ALL three hold: is_admin, email_verified, and already on the
# existing Hub beta allowlist. A single generic 403 covers every failure so
# an unauthorized caller can't learn which condition they're missing.
def diagnostics_context(user=Depends(get_current_user), path=Depends(get_db_path_dep)):
    settings = Settings.from_env()
    if not (user.get('is_admin') and user.get('email_verified') and user['id'] in settings.beta_user_ids):
        raise HTTPException(403, 'Not authorized.')
    return Store(path)


@router.get('/diagnostics')
def diagnostics(store=Depends(diagnostics_context)):
    return {**store.diagnostics_stats(), 'requests': store.diagnostics_requests()}
