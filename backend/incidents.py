"""
incidents.py — Incident tracking and automatic diagnosis for Porickbot's
monitoring.

Wraps the EXISTING alert triggers and dedup in alerts.py; does not change
either. Every alert still fires exactly when and as often as it did before,
and the existing exact-text / category-keyed dedup in alerts.py is
untouched. This module just also keeps a durable, queryable record: one
open row per category, occurrence_count bumped on every repeat, closed
automatically after AUTO_RESOLVE_QUIET_MINUTES of quiet.

Severity classification (which categories are critical/warning/info) is a
plain lookup table — no model call. The ONE thing in this file that does
call a model is automatic diagnosis: the first time an incident reaches
critical severity (creation or escalation) and has no likely_cause yet, a
background thread gathers evidence (recent log lines + recent git commits)
and asks claude-sonnet-4-6 to classify a likely cause. This never blocks or
delays the alert that triggered it — see record()/_maybe_trigger_diagnosis()
— and fails completely silently: any failure just leaves likely_cause/
confidence/evidence NULL, exactly as if diagnosis had never run.
"""
import json
import logging
import os
import sqlite3
import threading
from datetime import datetime, timedelta, timezone

import requests

import db as _db

log = logging.getLogger("zeus.incidents")

AUTO_RESOLVE_QUIET_MINUTES = 60

VALID_SERVICES = {"beats", "hub", "jobline", "provider", "billing"}
VALID_SEVERITIES = {"info", "warning", "critical"}

SEVERITY_PREFIX = {
    "critical": "🔴 CRITICAL",
    "warning": "🟡 WARNING",
    "info": "🔵 INFO",
}

SCHEMA = """
CREATE TABLE IF NOT EXISTS incidents (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    service           TEXT NOT NULL,
    category          TEXT NOT NULL,
    severity          TEXT NOT NULL,
    title             TEXT NOT NULL,
    symptoms          TEXT NOT NULL,
    evidence          TEXT,
    likely_cause      TEXT,
    confidence        TEXT,
    actions_attempted TEXT,
    resolution        TEXT,
    first_seen        TEXT NOT NULL,
    last_seen         TEXT NOT NULL,
    occurrence_count  INTEGER NOT NULL DEFAULT 1,
    status            TEXT NOT NULL DEFAULT 'open',
    resolved_at       TEXT
);
CREATE INDEX IF NOT EXISTS idx_incidents_category_status ON incidents(category, status);
CREATE INDEX IF NOT EXISTS idx_incidents_status_last_seen ON incidents(status, last_seen);
"""

# category -> (service, severity, title). Categories ending in ":" are
# matched as a prefix (the alert_* functions in alerts.py build these with
# an f-string per song_type/service/status_code -- this table classifies
# the categories they already use for dedup, it doesn't invent new ones).
# A severity of None means "the caller computes it per-occurrence" (status
# code, or a keyword already in a composed checker message).
_CATEGORY_TABLE: dict[str, tuple[str, str, str]] = {
    "new_signup":             ("beats", "info", "New signup"),
    "contact_submission":     ("beats", "info", "Contact form submission"),
    "signup_flag":            ("beats", "info", "Signup flagged"),
    "new_subscription":       ("billing", "info", "New payment"),
    "payment_failed":         ("billing", "critical", "Payment failed"),
    "payg_purchase":          ("billing", "info", "PAYG purchase"),
    "stripe_webhook_error":   ("billing", "critical", "Stripe webhook crashed"),
    "credit_not_granted":     ("billing", "critical", "Paid but no credits granted"),
    "subscription_cancelled": ("billing", "info", "Subscription cancelled"),
    "fade_out_failed":        ("jobline", "warning", "Song fade-out failed"),
    "stuck_song_sweep":       ("jobline", "warning", "Stuck songs recovered"),
    "fal_balance":            ("provider", None, "fal.ai balance"),
    "apiframe_credits":       ("provider", None, "Apiframe credits"),
    "ai_providers":           ("provider", None, "AI provider health"),
}
_CATEGORY_PREFIX_TABLE: dict[str, tuple[str, str, str]] = {
    "lyrics_failed:": ("jobline", "critical", "Song generation failed (lyrics)"),
    "song_failed:": ("jobline", "critical", "Song generation failed (music)"),
    "service_error:": ("provider", None, "External service error"),
}

# Substrings that mean "this occurrence could not be confirmed healthy at
# all" across every checker message currently in alerts.py -- both the
# older fal.ai/Apiframe emoji style and the newer explicit CRITICAL/WARNING
# labels used by the AI-provider checks.
_CRITICAL_MARKERS = ("CRITICAL", "EXHAUSTED", "UNREADABLE")


def severity_from_checker_message(message: str) -> str:
    """For the balance/health checkers, whose severity depends on the
    occurrence's own text rather than a fixed per-category value."""
    return "critical" if any(marker in message for marker in _CRITICAL_MARKERS) else "warning"


def severity_from_status_code(status_code) -> str:
    """For alert_service_error: an outright auth/quota failure (the service
    is not usable at all) is critical; anything else (rate limiting, a
    transient 5xx) is degraded, not down."""
    try:
        code = int(status_code)
    except (TypeError, ValueError):
        return "warning"
    return "critical" if code in (401, 402, 403) else "warning"


def classify(category: str) -> tuple[str, str | None, str]:
    """Return (service, severity, title) for a category string. severity is
    None where the caller must supply one (see the table above). Falls back
    to a safe default for an unrecognised category rather than raising --
    an incident row with a generic title beats no incident row at all."""
    if category in _CATEGORY_TABLE:
        return _CATEGORY_TABLE[category]
    for prefix, classification in _CATEGORY_PREFIX_TABLE.items():
        if category.startswith(prefix):
            return classification
    log.warning("incidents: unrecognised category %r, defaulting to provider/warning", category)
    return "provider", "warning", category


def _ordinal(n: int) -> str:
    if 10 <= n % 100 <= 20:
        suffix = "th"
    else:
        suffix = {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
    return f"{n}{suffix}"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(str(_db.get_db_path()), timeout=15)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.executescript(SCHEMA)
    return conn


_SEVERITY_RANK = {"info": 0, "warning": 1, "critical": 2}


def record(category: str, symptoms: str, *, severity: str | None = None) -> sqlite3.Row | None:
    """Find the open incident for `category`; if found, bump occurrence_count
    and last_seen. If not, create one. Returns the resulting row, or None if
    incident tracking itself failed -- which must never take down the alert
    it's describing, so every exception is caught here.

    Severity on an existing open incident only ever escalates (the higher of
    the stored value and this occurrence's), never silently downgrades --
    once something has been critical, that stays visible until the incident
    resolves. This is also what lets automatic diagnosis detect "escalated
    to critical": see _maybe_trigger_diagnosis() below.
    """
    try:
        auto_service, auto_severity, title = classify(category)
        severity = severity or auto_severity
        if severity not in VALID_SEVERITIES:
            log.warning("incidents: invalid severity %r for category %r, defaulting to warning", severity, category)
            severity = "warning"
        service = auto_service if auto_service in VALID_SERVICES else "provider"
        now = _now_iso()
        conn = _connect()
        try:
            row = conn.execute(
                "SELECT * FROM incidents WHERE category = ? AND status = 'open'", (category,)
            ).fetchone()
            if row:
                stored_severity = row["severity"]
                new_severity = severity if _SEVERITY_RANK.get(severity, 0) > _SEVERITY_RANK.get(stored_severity, 0) else stored_severity
                conn.execute(
                    "UPDATE incidents SET occurrence_count = occurrence_count + 1, last_seen = ?, severity = ? WHERE id = ?",
                    (now, new_severity, row["id"]),
                )
                incident_id = row["id"]
            else:
                cur = conn.execute(
                    """INSERT INTO incidents
                       (service, category, severity, title, symptoms, first_seen, last_seen,
                        occurrence_count, status)
                       VALUES (?, ?, ?, ?, ?, ?, ?, 1, 'open')""",
                    (service, category, severity, title, symptoms, now, now),
                )
                incident_id = cur.lastrowid
            conn.commit()
            result = conn.execute("SELECT * FROM incidents WHERE id = ?", (incident_id,)).fetchone()
        finally:
            conn.close()
        _maybe_trigger_diagnosis(result)
        return result
    except Exception:
        log.exception("incidents: record() failed for category=%r (alert itself is unaffected)", category)
        return None


# ── Automatic diagnosis ──────────────────────────────────────────────────────
#
# Triggered from record() the moment an incident first reaches critical
# severity (creation or escalation) with no likely_cause yet. In-memory guard
# below covers the race where two rapid occurrences of the same brand-new
# critical incident both see likely_cause still NULL before the background
# diagnosis has had a chance to write it -- cheap to avoid, so avoided,
# even though the DB-level guard (likely_cause IS NULL) already makes a
# second real diagnosis attempt merely wasteful rather than harmful.

_diagnosed_incident_ids: set[int] = set()

_DIAGNOSIS_MODEL = "claude-sonnet-4-6"

CAUSE_CATEGORIES = ("code", "api_credits", "database", "deployment",
                     "third_party_outage", "configuration", "unknown")
CONFIDENCE_LEVELS = ("low", "medium", "high")

_DIAGNOSIS_SYSTEM_PROMPT = f"""You are diagnosing a production incident for Zeus Beats, an AI \
music generation platform. You are given the incident's title, its symptoms, and evidence: \
recent application log lines and the last few git commits on master (commit message and changed \
file list only, no diffs). Identify the LIKELY CAUSE from that evidence alone.

Classify the cause as exactly one of: {", ".join(CAUSE_CATEGORIES)}.
Rate your confidence as exactly one of: {", ".join(CONFIDENCE_LEVELS)}.

Rules, in order of importance:
1. Only state a specific cause if the evidence you were given actually supports it. If the logs \
and commits do not clearly point to a cause, you MUST use cause_category "unknown", confidence \
"low", and say so plainly in your reasoning ("insufficient evidence to determine a cause") -- do \
not guess, and do not invent a plausible-sounding explanation that isn't grounded in what you \
were actually shown.
2. A recent commit touching a related file is evidence for "deployment" or "code"; a log line \
naming a specific failing service or provider is evidence for "third_party_outage", \
"api_credits", or "configuration"; a database error string is evidence for "database". The mere \
absence of an obvious alternative is never, by itself, evidence for any specific cause.
3. Never invent specifics (file names, error codes, commit hashes, service names) that do not \
appear in the evidence you were given.

Respond with ONLY a JSON object, no other text before or after it, in exactly this shape:
{{"cause_category": "<one of the categories above>", "confidence": "<low|medium|high>", \
"reasoning": "<one sentence, grounded only in the evidence given>"}}"""

# Keyword filter applied to the shared log ring buffer so "relevant to the
# incident's service" means something -- the buffer itself mixes every
# service's log lines together with no partitioning of its own. An empty
# tuple (beats) means no narrow filter: general app/user activity doesn't
# have a small distinguishing vocabulary the way the others do.
_SERVICE_LOG_KEYWORDS: dict[str, tuple[str, ...]] = {
    "billing": ("stripe", "billing", "credit", "webhook", "subscription", "payment", "invoice"),
    "jobline": ("song", "lyric", "variant", "apiframe", "generat", "fade"),
    "provider": ("anthropic", "openai", "gemini", "grok", "xai", "openrouter",
                 "fal.ai", "apiframe", "provider"),
    "hub": ("hub", "council", "ask zeus"),
    "beats": (),
}

_GITHUB_REPO = "mickymooch1/zeus-app"
_GITHUB_API = "https://api.github.com"


def _maybe_trigger_diagnosis(row: sqlite3.Row | None) -> None:
    """The only place diagnosis gets triggered from. Runs synchronously
    (it's just a cheap condition check) but the actual work is dispatched to
    a background thread by _spawn_diagnosis so this returns immediately --
    record()'s caller (an alert_* function that's about to send a Telegram
    message) is never delayed by it.
    """
    try:
        if row is None or row["severity"] != "critical" or row["likely_cause"] is not None:
            return
        incident_id = row["id"]
        if incident_id in _diagnosed_incident_ids:
            return
        _diagnosed_incident_ids.add(incident_id)
        _spawn_diagnosis(dict(row))
    except Exception:
        log.exception("incidents: could not evaluate whether to trigger diagnosis")


def _spawn_diagnosis(incident: dict) -> None:
    """Thin wrapper around the background thread -- kept separate so tests
    can monkeypatch just this one thing (e.g. to run _diagnose_in_background
    synchronously with a mocked model call) instead of dealing with a real
    thread making a real network call."""
    threading.Thread(target=_diagnose_in_background, args=(incident,), daemon=True).start()


def _diagnose_in_background(incident: dict) -> None:
    """Runs off the alert path entirely -- by the time this executes,
    send_admin_alert has already returned, so nothing here can delay or
    block the alert that triggered it. Every failure is swallowed: the
    incident simply keeps its empty diagnosis fields (the 'fail silently'
    contract). Nothing is ever shown to the admin except a successful
    diagnosis's own follow-up message, sent a few seconds after the original.
    """
    try:
        log_evidence = _gather_log_evidence(incident.get("service", ""))
        git_evidence = _gather_git_evidence()
        diagnosis = _call_diagnosis_model(incident, log_evidence, git_evidence)
        if diagnosis is None:
            return
        cause, confidence, reasoning = diagnosis["cause_category"], diagnosis["confidence"], diagnosis["reasoning"]
        likely_cause = (f"insufficient evidence — {reasoning}" if cause == "unknown" and reasoning
                         else "insufficient evidence" if cause == "unknown"
                         else f"{cause}: {reasoning}" if reasoning else cause)
        evidence_blob = f"--- Recent log lines ---\n{log_evidence}\n\n--- Recent commits on master ---\n{git_evidence}"
        _write_diagnosis(incident["id"], evidence_blob, likely_cause, confidence)
        _send_diagnosis_followup(cause, confidence, reasoning)
    except Exception:
        log.exception("incidents: diagnosis failed for incident id=%s (fields remain empty)", incident.get("id"))


def _gather_log_evidence(service: str, limit: int = 50) -> str:
    """The last (up to) `limit` in-memory log lines relevant to `service`.
    Reuses telegram_admin._log_buffer -- the same ring buffer Porick's own
    "show logs" command already reads, and the only log-fetching mechanism
    that exists anywhere in this codebase. It only holds this process's last
    100 lines and resets on redeploy, so a diagnosis triggered right after a
    restart may have little to work with -- exactly the case the system
    prompt's "insufficient evidence" instruction exists for.
    """
    try:
        from telegram_admin import _log_buffer
        lines = list(_log_buffer)
    except Exception:
        log.exception("incidents: could not read the log buffer")
        return "(log buffer unavailable)"
    keywords = _SERVICE_LOG_KEYWORDS.get(service, ())
    if keywords:
        filtered = [line for line in lines if any(k in line.lower() for k in keywords)]
        if filtered:
            lines = filtered
    lines = lines[-limit:]
    return "\n".join(lines) if lines else "(no relevant log lines captured)"


def _gather_git_evidence(count: int = 5) -> str:
    """The last `count` commits on master: message + changed file list, no
    diffs. Via the GitHub API rather than a local `git log` -- the deployed
    container is built from just the backend/ subdirectory (see Dockerfile),
    so .git is never present at runtime and a local git log would have
    nothing to read. Uses the same GITHUB_TOKEN + repo already established in
    github_push.py.
    """
    token = os.environ.get("GITHUB_TOKEN", "").strip()
    if not token:
        return "(git history unavailable — GITHUB_TOKEN not set)"
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    try:
        resp = requests.get(
            f"{_GITHUB_API}/repos/{_GITHUB_REPO}/commits",
            headers=headers, params={"sha": "master", "per_page": count}, timeout=10,
        )
        resp.raise_for_status()
        commits = resp.json()
    except Exception as exc:
        return f"(git history unavailable — {type(exc).__name__}: {exc})"

    lines = []
    for c in commits[:count]:
        sha = c.get("sha", "")
        raw_message = (c.get("commit", {}).get("message") or "").strip()
        message = raw_message.splitlines()[0][:200] if raw_message else "(no commit message)"
        files_str = "(file list unavailable)"
        try:
            detail = requests.get(f"{_GITHUB_API}/repos/{_GITHUB_REPO}/commits/{sha}", headers=headers, timeout=10)
            detail.raise_for_status()
            files = [f["filename"] for f in detail.json().get("files", [])][:20]
            if files:
                files_str = ", ".join(files)
        except Exception:
            pass
        lines.append(f"{sha[:7]} — {message}\n  files: {files_str}")
    return "\n".join(lines) if lines else "(no recent commits found)"


def _call_diagnosis_model(incident: dict, log_evidence: str, git_evidence: str) -> dict | None:
    """Direct to api.anthropic.com (the `anthropic` SDK, no base_url override
    -- matching every other Anthropic call site in this codebase). Returns
    None on any failure (missing key, network error, timeout, unparseable
    response) so the caller can fail silently, per spec.
    """
    api_key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    if not api_key:
        return None
    user_content = (
        f"Incident title: {incident['title']}\n"
        f"Symptoms: {incident['symptoms']}\n\n"
        f"Recent application log lines (service={incident.get('service', 'unknown')}):\n{log_evidence}\n\n"
        f"Last commits on master:\n{git_evidence}"
    )
    try:
        from anthropic import Anthropic
        resp = Anthropic(api_key=api_key, timeout=20.0).messages.create(
            model=_DIAGNOSIS_MODEL,
            max_tokens=300,
            system=_DIAGNOSIS_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_content}],
        )
        text = (resp.content[0].text or "").strip()
    except Exception:
        log.exception("incidents: diagnosis model call failed")
        return None

    try:
        data = json.loads(text)
        cause = str(data.get("cause_category", "")).strip().lower()
        confidence = str(data.get("confidence", "")).strip().lower()
        reasoning = str(data.get("reasoning", "")).strip()
    except Exception:
        log.exception("incidents: diagnosis response was not valid JSON: %r", text[:300])
        return None

    if cause not in CAUSE_CATEGORIES:
        cause = "unknown"
    if confidence not in CONFIDENCE_LEVELS:
        confidence = "low"
    # Defense in depth: "unknown" can never carry anything but low confidence,
    # regardless of what the model returned -- the prompt already instructs
    # this, but a contradictory response must not be trusted over the rule.
    if cause == "unknown":
        confidence = "low"
        if not reasoning:
            reasoning = "insufficient evidence to determine a cause"

    return {"cause_category": cause, "confidence": confidence, "reasoning": reasoning}


def _write_diagnosis(incident_id: int, evidence: str, likely_cause: str, confidence: str) -> None:
    """Writes ONLY evidence/likely_cause/confidence. actions_attempted and
    resolution are untouched -- those belong to a later stage."""
    conn = _connect()
    try:
        conn.execute(
            "UPDATE incidents SET evidence = ?, likely_cause = ?, confidence = ? WHERE id = ?",
            (evidence, likely_cause, confidence, incident_id),
        )
        conn.commit()
    finally:
        conn.close()


def _send_diagnosis_followup(cause: str, confidence: str, reasoning: str) -> None:
    """A short follow-up message, sent a few seconds after the original
    alert (this only runs from the background diagnosis thread). "Likely
    cause" for medium/high confidence, "Possible cause" for low -- including
    the "unknown" / insufficient-evidence case, which is always low."""
    from alerts import send_admin_alert

    label = "Possible cause" if confidence == "low" else "Likely cause"
    display_cause = "insufficient evidence" if cause == "unknown" else cause
    tail = f" — {reasoning}" if reasoning else ""
    send_admin_alert(f"🔍 {label}: {display_cause} (confidence: {confidence}){tail}")


def note(category: str, symptoms: str, *, severity: str | None = None) -> str:
    """Record this occurrence and return the text to prepend to the alert
    message: a severity prefix, plus an 'Nth time in 24h — first seen HH:MM'
    line if this incident has recurred. Never raises -- on any internal
    failure this still returns a plain severity prefix (computed without
    touching the DB) so the caller's alert is never blocked by bookkeeping.
    """
    auto_service, auto_severity, _title = classify(category)
    resolved_severity = severity or auto_severity
    if resolved_severity not in VALID_SEVERITIES:
        resolved_severity = "warning"
    prefix = SEVERITY_PREFIX[resolved_severity]
    # record() already catches its own errors and returns None on failure --
    # but this call is wrapped independently too (belt-and-braces, matching
    # every alert_* function's own style in alerts.py): note()'s contract is
    # "never raises" on its own terms, not "never raises because record()
    # currently happens to handle its own failures."
    try:
        row = record(category, symptoms, severity=severity)
    except Exception:
        log.exception("incidents: record() call raised inside note() for category=%r", category)
        row = None
    if row is not None and row["occurrence_count"] > 1:
        try:
            first_seen = datetime.fromisoformat(row["first_seen"]).strftime("%H:%M")
            prefix += f"\n{_ordinal(row['occurrence_count'])} time in 24h — first seen {first_seen}"
        except Exception:
            log.exception("incidents: could not format occurrence line for category=%r", category)
    return prefix


def resolve_stale() -> list[dict]:
    """Auto-resolve any open incident with no new occurrence in the last
    AUTO_RESOLVE_QUIET_MINUTES. Call this AFTER recording this cycle's
    occurrences (if any): a category that just recurred this cycle already
    has a fresh last_seen and will not match here, so a still-failing
    category never gets auto-resolved out from under itself -- the call
    ordering alone is what keeps it open, no extra "is it still broken"
    signal needs to be threaded through.

    Returns the newly-resolved rows (as plain dicts) so the caller can send
    a "recovered" notice for each.
    """
    resolved: list[dict] = []
    try:
        cutoff = (datetime.now(timezone.utc) - timedelta(minutes=AUTO_RESOLVE_QUIET_MINUTES)).isoformat()
        conn = _connect()
        try:
            rows = conn.execute(
                "SELECT * FROM incidents WHERE status = 'open' AND last_seen <= ?", (cutoff,)
            ).fetchall()
            now = _now_iso()
            for row in rows:
                conn.execute(
                    "UPDATE incidents SET status = 'resolved', resolved_at = ? WHERE id = ?",
                    (now, row["id"]),
                )
                updated = dict(row)
                updated["status"] = "resolved"
                updated["resolved_at"] = now
                resolved.append(updated)
            conn.commit()
        finally:
            conn.close()
    except Exception:
        log.exception("incidents: resolve_stale() failed")
    return resolved


def list_open() -> list[dict]:
    """Open incidents, most severe and most recent first."""
    try:
        conn = _connect()
        try:
            rows = conn.execute(
                """SELECT * FROM incidents WHERE status = 'open'
                   ORDER BY CASE severity WHEN 'critical' THEN 0 WHEN 'warning' THEN 1 ELSE 2 END,
                            last_seen DESC"""
            ).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()
    except Exception:
        log.exception("incidents: list_open() failed")
        return []


def list_history(category: str, limit: int = 5) -> list[dict]:
    """The most recent resolved incidents for one category, newest first."""
    try:
        conn = _connect()
        try:
            rows = conn.execute(
                """SELECT * FROM incidents WHERE category = ? AND status = 'resolved'
                   ORDER BY resolved_at DESC LIMIT ?""",
                (category, limit),
            ).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()
    except Exception:
        log.exception("incidents: list_history() failed for category=%r", category)
        return []


def humanize_age(iso_timestamp: str) -> str:
    """'2h 15m', '3d 4h', '5m' -- relative to now, for the open-incidents list."""
    try:
        then = datetime.fromisoformat(iso_timestamp)
        delta = datetime.now(timezone.utc) - then
        total_minutes = max(0, int(delta.total_seconds() // 60))
        days, rem_minutes = divmod(total_minutes, 1440)
        hours, minutes = divmod(rem_minutes, 60)
        if days:
            return f"{days}d {hours}h"
        if hours:
            return f"{hours}h {minutes}m"
        return f"{minutes}m"
    except Exception:
        return "unknown age"
