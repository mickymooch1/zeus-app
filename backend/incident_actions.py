"""
incident_actions.py — Safe, whitelisted action execution for Porick, gated by
incidents.py's automatic diagnosis.

The only trigger for an action offer is incidents._diagnose_in_background()
finishing a diagnosis with confidence "medium" or "high": that is the one and
only place likely_cause ever gets set (see incidents.py), so it is the one
and only moment "an incident has a likely_cause with confidence medium/high"
newly becomes true. maybe_offer_action() is called from there with the raw
cause_category/confidence the model returned (not the formatted likely_cause
string), which avoids re-parsing incidents.py's human-readable format.

Every action requires an explicit "yes" from TELEGRAM_ADMIN_USER_ID within
_OFFER_TTL_MINUTES of the offer -- nothing here ever executes automatically.
Offers live in memory only (same tradeoff as zeus_ops_agent's _retry_attempted
/_retry_map and alerts.py's digest counters: resets on redeploy, acceptable
because a lost offer just means re-diagnosing next time the category recurs,
never a silently-executed action).

Whitelist entries are ONLY ever dispatched through _EXECUTORS, a hard-coded
dict with exactly 4 entries. Editing ACTION_WHITELIST (even at runtime, even
by a bug) can never make a forbidden action type executable: execute_action()
refuses anything in FORBIDDEN_ACTION_TYPES or missing from _EXECUTORS before
it ever looks at the whitelist's own description/category/cause fields.
"""
import logging
import os
import sqlite3
from datetime import datetime, timezone

log = logging.getLogger("zeus.incident_actions")

_OFFER_TTL_MINUTES = 30

# action_type -> whitelist entry. "categories" are exact incident.category
# matches; "category_prefixes" match a leading segment (mirrors incidents.py's
# own _CATEGORY_PREFIX_TABLE convention for f-string-built categories like
# "service_error:apiframe:401"). "causes" is the set of incidents.py
# CAUSE_CATEGORIES this action applies to, or None if the action is
# cause-agnostic (fires for any cause, once confidence is medium/high).
ACTION_WHITELIST: dict[str, dict] = {
    "restart_worker": {
        "categories": {"stuck_song_sweep"},
        "causes": {"deployment", "code"},
        "description": "restart the app (Railway redeploy) — the stuck-song pattern looks like our own code or deploy, not the provider",
    },
    "retry_job": {
        "categories": {"stuck_song_sweep"},
        "causes": {"third_party_outage", "api_credits"},
        "description": "retry the currently stuck song(s) instead of just refunding them",
    },
    "refund_stuck_song": {
        "categories": {"stuck_song_sweep"},
        "causes": None,
        "description": "refund credits for the currently stuck song(s) (existing auto-refund rule)",
    },
    "switch_provider": {
        "categories": {"fal_balance", "apiframe_credits", "ai_providers"},
        "category_prefixes": ("service_error:",),
        "causes": {"api_credits", "configuration", "third_party_outage"},
        "description": "switch to the configured backup provider",
    },
}

# Checked first, in this order, so exactly one action is ever offered per
# incident (stuck_song_sweep can in principle match three entries -- only
# the first match in this order wins).
_MATCH_ORDER = ("restart_worker", "retry_job", "refund_stuck_song", "switch_provider")

# Hard-coded, independent of ACTION_WHITELIST's contents. Billing changes
# beyond refund_stuck_song's existing rule, data deletion, deployments (a
# restart/redeploy of the SAME code is not a deployment of new code/config),
# and config/credential changes are never offered or executed as actions,
# regardless of what a future whitelist entry might claim.
FORBIDDEN_ACTION_TYPES = frozenset({
    "billing_change",
    "data_deletion",
    "deployment_change",
    "credential_change",
})

_KNOWN_PROVIDER_SLOTS = ("anthropic", "openai", "gemini", "grok", "openrouter", "fal", "apiframe")

# incident_id -> {action_type, description, extra, offered_at}
_pending_offers: dict[int, dict] = {}


def _category_matches(entry: dict, category: str) -> bool:
    if category in entry.get("categories", ()):
        return True
    for prefix in entry.get("category_prefixes", ()):
        if category.startswith(prefix):
            return True
    return False


def _match_whitelist(category: str, cause: str) -> str | None:
    """The action_type that applies to this (category, cause) pair, or None."""
    for action_type in _MATCH_ORDER:
        entry = ACTION_WHITELIST.get(action_type)
        if entry is None:
            continue
        if action_type in FORBIDDEN_ACTION_TYPES or action_type not in _EXECUTORS:
            continue
        if not _category_matches(entry, category):
            continue
        causes = entry.get("causes")
        if causes is not None and cause not in causes:
            continue
        return action_type
    return None


def _extract_provider_slot(category: str, symptoms: str) -> str | None:
    if category == "fal_balance":
        return "fal"
    if category == "apiframe_credits":
        return "apiframe"
    if category.startswith("service_error:"):
        parts = category.split(":")
        return parts[1] if len(parts) >= 2 and parts[1] else None
    if category == "ai_providers":
        low = (symptoms or "").lower()
        matches = [p for p in _KNOWN_PROVIDER_SLOTS if p in low]
        return matches[0] if len(matches) == 1 else None
    return None


def _configured_backup(provider_slot: str) -> str | None:
    """The ONLY source of truth for 'a backup is explicitly configured for
    this provider slot'. Porick never invents or auto-selects a fallback --
    if an admin hasn't set this env var by hand, switch_provider is never
    offered or executed for that slot, full stop."""
    val = os.environ.get(f"{provider_slot.upper()}_BACKUP_PROVIDER", "").strip()
    return val or None


# ── Offering ──────────────────────────────────────────────────────────────

def maybe_offer_action(incident: dict, cause: str, confidence: str) -> None:
    """Called once per incident, right after diagnosis writes likely_cause/
    confidence. Never raises -- this must not affect the diagnosis it's
    piggybacking on."""
    try:
        if confidence not in ("medium", "high"):
            return
        category = incident.get("category", "")
        action_type = _match_whitelist(category, cause)
        if action_type is None:
            return
        entry = ACTION_WHITELIST[action_type]
        extra = None
        if action_type == "switch_provider":
            extra = _extract_provider_slot(category, incident.get("symptoms", ""))
            if not extra or not _configured_backup(extra):
                return
        _pending_offers[incident["id"]] = {
            "action_type": action_type,
            "description": entry["description"],
            "extra": extra,
            "offered_at": datetime.now(timezone.utc),
        }
        _send_offer_message(incident["title"], entry["description"])
    except Exception:
        log.exception("incident_actions: maybe_offer_action failed for incident id=%s", incident.get("id"))


def _send_offer_message(incident_title: str, description: str) -> None:
    from alerts import send_admin_alert
    send_admin_alert(f"🔧 {incident_title} — I can {description}. Reply yes to proceed.")


# ── Expiry ────────────────────────────────────────────────────────────────

def _is_expired(offer: dict) -> bool:
    age = datetime.now(timezone.utc) - offer["offered_at"]
    return age.total_seconds() > _OFFER_TTL_MINUTES * 60


def expire_stale_offers() -> None:
    """Silently marks any offer older than _OFFER_TTL_MINUTES as expired --
    no Telegram message (the spec is explicit: no further nudging on a
    timeout). Safe to call often; called from zeus_ops_agent.stuck_song_sweep
    (every 15 min) so an expiry is reflected within that window even if the
    admin never sends another message."""
    expired_ids = [iid for iid, offer in _pending_offers.items() if _is_expired(offer)]
    for iid in expired_ids:
        _pending_offers.pop(iid, None)
        try:
            _write_actions_attempted(iid, "expired")
        except Exception:
            log.exception("incident_actions: could not write expired status for incident id=%s", iid)


def _pop_latest_pending_offer() -> tuple[int, dict] | None:
    expire_stale_offers()
    if not _pending_offers:
        return None
    incident_id = max(_pending_offers, key=lambda k: _pending_offers[k]["offered_at"])
    return incident_id, _pending_offers.pop(incident_id)


# ── Reply handling ───────────────────────────────────────────────────────

def handle_admin_reply(text: str) -> str | None:
    """Returns a reply string if `text` was a yes/no consumed by a pending
    offer, else None (caller should fall through to normal command parsing)."""
    stripped = text.strip().lower()
    if stripped not in ("yes", "no"):
        return None
    picked = _pop_latest_pending_offer()
    if picked is None:
        return None
    incident_id, offer = picked
    if stripped == "no":
        _write_actions_attempted(incident_id, "declined")
        return f"👍 Skipped: {offer['description']}"
    return execute_action(incident_id, offer)


# ── Execution ────────────────────────────────────────────────────────────

def _exec_restart_worker(incident: dict, extra) -> str:
    import telegram_admin
    result = telegram_admin._cmd_redeploy()
    return f"failed: {result}" if result.startswith("❌") else f"executed: {result}"


def _exec_retry_job(incident: dict, extra) -> str:
    import zeus_ops_agent as ops
    try:
        conn = sqlite3.connect(ops._db())
        conn.row_factory = sqlite3.Row
        try:
            stuck = conn.execute(
                """SELECT id FROM song_variants
                   WHERE status IN ('pending', 'generating')
                   AND created_at <= datetime('now', '-15 minutes')"""
            ).fetchall()
        finally:
            conn.close()
    except Exception as exc:
        return f"failed: could not query stuck songs ({exc})"
    if not stuck:
        return "executed: no currently stuck songs to retry"
    retried, failed = 0, 0
    for row in stuck:
        new_vid = ops._retry_song(row["id"])
        if new_vid is not None:
            retried += 1
        else:
            failed += 1
    if retried == 0:
        return f"failed: all {failed} retry attempt(s) failed"
    tail = f", {failed} failed" if failed else ""
    return f"executed: retried {retried} song(s){tail}"


def _exec_refund_stuck_song(incident: dict, extra) -> str:
    import zeus_ops_agent as ops
    try:
        warnings = ops._fix_stuck_songs()
    except Exception as exc:
        return f"failed: {exc}"
    if not warnings:
        return "executed: no currently stuck songs to refund"
    return f"executed: {'; '.join(warnings)}"


def _exec_switch_provider(incident: dict, extra) -> str:
    provider_slot = extra
    backup = _configured_backup(provider_slot) if provider_slot else None
    if not backup:
        return "failed: no backup provider configured for this slot"
    import telegram_admin
    result = telegram_admin._cmd_var_set(f"{provider_slot.upper()}_ACTIVE_PROVIDER_OVERRIDE", backup)
    return f"failed: {result}" if result.startswith("❌") else f"executed: switched {provider_slot} to configured backup '{backup}'"


# Hard-coded, exactly 4 entries. This dict -- not ACTION_WHITELIST -- is what
# actually makes an action type runnable. A whitelist entry with no matching
# key here can never execute, no matter what its category/cause fields say.
_EXECUTORS = {
    "restart_worker": _exec_restart_worker,
    "retry_job": _exec_retry_job,
    "refund_stuck_song": _exec_refund_stuck_song,
    "switch_provider": _exec_switch_provider,
}


def execute_action(incident_id: int, offer: dict) -> str:
    action_type = offer["action_type"]
    if action_type in FORBIDDEN_ACTION_TYPES or action_type not in _EXECUTORS:
        _write_actions_attempted(incident_id, "refused: forbidden action type")
        return "⛔ That action type is not permitted to execute — refusing."
    executor = _EXECUTORS[action_type]
    try:
        outcome = executor({"id": incident_id}, offer.get("extra"))
    except Exception as exc:
        log.exception("incident_actions: executor for %s raised", action_type)
        outcome = f"failed: {type(exc).__name__}: {exc}"
    _write_actions_attempted(incident_id, outcome)
    if outcome.startswith("failed"):
        detail = outcome[len("failed: "):] if outcome.startswith("failed: ") else outcome
        return f"❌ {offer['description']} failed — {detail}"
    detail = outcome[len("executed: "):] if outcome.startswith("executed: ") else outcome
    return f"✅ Done: {offer['description']} — {detail}"


def _write_actions_attempted(incident_id: int, value: str) -> None:
    import incidents
    conn = incidents._connect()
    try:
        conn.execute("UPDATE incidents SET actions_attempted = ? WHERE id = ?", (value, incident_id))
        conn.commit()
    finally:
        conn.close()
