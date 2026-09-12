"""
incidents.py — Incident tracking for Porickbot's monitoring.

Wraps the EXISTING alert triggers and dedup in alerts.py; does not change
either. Every alert still fires exactly when and as often as it did before,
and the existing exact-text / category-keyed dedup in alerts.py is
untouched. This module just also keeps a durable, queryable record: one
open row per category, occurrence_count bumped on every repeat, closed
automatically after AUTO_RESOLVE_QUIET_MINUTES of quiet.

No AI model calls anywhere in this file. Severity is a plain lookup table
keyed on category (a handful of categories need a small deterministic rule
instead of a fixed value — a status code range, or a keyword in an
already-composed message — but that's still ordinary Python, not a model
call). This must cost nothing to run beyond the SQLite writes it was
already going to make room for.

The diagnosis columns (evidence, likely_cause, confidence, actions_attempted,
resolution) are created here but deliberately left NULL — a later stage
fills them in. Nothing in this module writes to them.
"""
import logging
import sqlite3
from datetime import datetime, timedelta, timezone

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


def record(category: str, symptoms: str, *, severity: str | None = None) -> sqlite3.Row | None:
    """Find the open incident for `category`; if found, bump occurrence_count
    and last_seen. If not, create one. Returns the resulting row, or None if
    incident tracking itself failed -- which must never take down the alert
    it's describing, so every exception is caught here.
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
                conn.execute(
                    "UPDATE incidents SET occurrence_count = occurrence_count + 1, last_seen = ? WHERE id = ?",
                    (now, row["id"]),
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
            return conn.execute("SELECT * FROM incidents WHERE id = ?", (incident_id,)).fetchone()
        finally:
            conn.close()
    except Exception:
        log.exception("incidents: record() failed for category=%r (alert itself is unaffected)", category)
        return None


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
