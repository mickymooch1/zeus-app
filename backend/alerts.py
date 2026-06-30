"""
alerts.py — Proactive Telegram DM alerts for Zeus Beats admin monitoring.

Sends messages to TELEGRAM_ADMIN_USER_ID (falls back to ADMIN_TELEGRAM_CHAT_ID).
All public functions are fire-and-forget: they log warnings on failure but never raise.
"""
import hashlib
import logging
import os
import sqlite3
import time

import requests

log = logging.getLogger("zeus.alerts")

# ── Deduplication ─────────────────────────────────────────────────────────────
# Tracks recently sent alert hashes to suppress repeats within 30 minutes.
# Keyed by MD5(message) → timestamp of last send.

_DEDUP_WINDOW = 1800   # 30 minutes: suppress identical messages
_DEDUP_TTL    = 3600   # 1 hour: evict stale entries to prevent memory growth

_sent_alerts: dict[str, float] = {}


def _should_send_alert(message: str) -> bool:
    """Return True if this message has not been sent in the last 30 minutes."""
    key = hashlib.md5(message.encode()).hexdigest()
    now = time.time()

    # Evict entries older than 1 hour
    stale = [k for k, ts in _sent_alerts.items() if now - ts > _DEDUP_TTL]
    for k in stale:
        del _sent_alerts[k]

    if key in _sent_alerts and now - _sent_alerts[key] < _DEDUP_WINDOW:
        log.debug("Alert suppressed (duplicate within 30 min): %s", message[:80])
        return False

    _sent_alerts[key] = now
    return True

_PLAN_DISPLAY = {
    "music_starter": "Music Starter £9",
    "music_pro":     "Music Pro £19",
    "music_agency":  "Music Agency £39",
    "pro":           "Pro £29",
    "agency":        "Agency £79",
    "enterprise":    "Enterprise £150",
}


# ── Core Telegram helper ──────────────────────────────────────────────────────

def _admin_chat_id() -> str:
    return (
        os.environ.get("TELEGRAM_ADMIN_USER_ID", "").strip()
        or os.environ.get("ADMIN_TELEGRAM_CHAT_ID", "").strip()
    )


def send_admin_alert(message: str) -> bool:
    """Send a plain-text DM to the admin. Returns True on success.

    Identical messages are suppressed if already sent within the last 30 minutes.
    """
    if not _should_send_alert(message):
        return False
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    chat_id = _admin_chat_id()
    if not token or not chat_id:
        log.warning("Admin alert (Telegram not configured): %s", message[:200])
        return False
    try:
        resp = requests.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json={"chat_id": chat_id, "text": message, "parse_mode": "HTML"},
            timeout=10,
        )
        if resp.status_code >= 300:
            log.warning("Admin alert failed: %d %s", resp.status_code, resp.text[:200])
            return False
        return True
    except Exception:
        log.exception("Admin alert send failed")
        return False


# ── Event alerts ──────────────────────────────────────────────────────────────

def alert_new_user(email: str) -> None:
    try:
        send_admin_alert(
            "👤 New signup!\n"
            f"📧 {email}\n"
            "📅 Just now\n"
            "🎵 Plan: Free (5 songs)"
        )
    except Exception:
        log.debug("alert_new_user failed (non-fatal)")


def alert_payment(email: str, plan_key: str, amount_display: str) -> None:
    try:
        plan_display = _PLAN_DISPLAY.get(plan_key, plan_key or "Unknown plan")
        send_admin_alert(
            "💰 New payment!\n"
            f"📧 {email}\n"
            f"💳 Plan: {plan_display}\n"
            f"💵 Amount: {amount_display}"
        )
    except Exception:
        log.debug("alert_payment failed (non-fatal)")


def alert_payment_failed(email: str, session_id: str = "") -> None:
    try:
        send_admin_alert(
            "🚨 Payment FAILED (delayed payment method)\n"
            f"📧 {email or 'unknown'}\n"
            f"🧾 session={session_id or 'n/a'}\n"
            "💳 No credits granted — customer emailed to retry\n"
            "🔍 Check Stripe Dashboard"
        )
    except Exception:
        log.debug("alert_payment_failed failed (non-fatal)")


def alert_song_failed(email: str, variant_id: int) -> None:
    try:
        send_admin_alert(
            "⚠️ Song generation failed!\n"
            f"👤 {email}\n"
            f"🎵 variant_id={variant_id}\n"
            "🔍 Check Railway logs"
        )
    except Exception:
        log.debug("alert_song_failed failed (non-fatal)")


def alert_subscription_cancelled(email: str, plan_key: str) -> None:
    try:
        plan_display = _PLAN_DISPLAY.get(plan_key, plan_key or "Unknown plan")
        send_admin_alert(
            "😢 Subscription cancelled\n"
            f"📧 {email}\n"
            f"💳 Was on: {plan_display}"
        )
    except Exception:
        log.debug("alert_subscription_cancelled failed (non-fatal)")


# ── Health checks ─────────────────────────────────────────────────────────────

def _check_fal_balance() -> str | None:
    """Return a warning string if fal.ai balance is below $5, else None."""
    fal_key = os.environ.get("FAL_API_KEY", "").strip()
    if not fal_key:
        return None
    try:
        resp = requests.get(
            "https://api.fal.ai/billing/balance",
            headers={"Authorization": f"Key {fal_key}"},
            timeout=8,
        )
        if resp.status_code == 200:
            balance = resp.json().get("balance")
            if balance is not None and float(balance) < 5.0:
                return f"❌ fal.ai balance low: ${float(balance):.2f}"
        else:
            log.debug("fal.ai balance check: status=%d", resp.status_code)
    except Exception as exc:
        log.debug("fal.ai balance check failed: %s", exc)
    return None


def _check_apiframe_credits() -> str | None:
    """Return a warning string if Apiframe credits are below 100, else None."""
    api_key = os.environ.get("APIFRAME_API_KEY", "").strip()
    if not api_key:
        return None
    try:
        resp = requests.get(
            "https://api.apiframe.ai/account",
            headers={"X-API-Key": api_key},
            timeout=8,
        )
        if resp.status_code == 200:
            data = resp.json()
            # Try both possible response shapes
            remaining = (data.get("credits") or {}).get("remaining")
            if remaining is None:
                remaining = data.get("remaining_credits")
            if remaining is not None and int(remaining) < 100:
                return f"❌ Apiframe credits low: {int(remaining)} remaining"
        else:
            log.debug("Apiframe credits check: status=%d", resp.status_code)
    except Exception as exc:
        log.debug("Apiframe credits check failed: %s", exc)
    return None


def _check_stuck_songs(db_path: str) -> str | None:
    """Return a warning string if songs are stuck pending/generating > 10 min."""
    try:
        conn = sqlite3.connect(db_path)
        try:
            row = conn.execute(
                """SELECT COUNT(*) FROM song_variants
                   WHERE status IN ('pending', 'generating')
                   AND created_at <= datetime('now', '-10 minutes')"""
            ).fetchone()
            count = row[0] if row else 0
            if count > 0:
                return f"⏳ {count} song(s) stuck pending/generating >10 min"
        finally:
            conn.close()
    except Exception as exc:
        log.debug("Stuck songs check failed: %s", exc)
    return None


def run_health_check() -> None:
    """Run all health checks; alert admin if anything is wrong."""
    try:
        import db as _db
        db_path = str(_db.get_db_path())
    except Exception:
        log.exception("Health check: could not get DB path")
        return

    warnings = []
    for checker in (_check_fal_balance, _check_apiframe_credits):
        w = checker()
        if w:
            warnings.append(w)
    w = _check_stuck_songs(db_path)
    if w:
        warnings.append(w)

    if warnings:
        send_admin_alert("🚨 Health check warning!\n" + "\n".join(warnings))
        log.warning("Health check: %d warning(s) — alert sent", len(warnings))
    else:
        log.info("Health check: all OK")


# ── Daily summary ─────────────────────────────────────────────────────────────

def send_daily_summary() -> None:
    """Query the DB and send the morning summary to admin."""
    try:
        import db as _db
        db_path = str(_db.get_db_path())
        conn = sqlite3.connect(db_path)
        try:
            total_users = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
            new_today = conn.execute(
                "SELECT COUNT(*) FROM users WHERE date(created_at) = date('now')"
            ).fetchone()[0]
            songs_today = conn.execute(
                """SELECT COUNT(*) FROM song_variants
                   WHERE status = 'complete'
                   AND date(completed_at) = date('now')"""
            ).fetchone()[0]
        finally:
            conn.close()

        send_admin_alert(
            "📊 Zeus Beats Daily Summary\n"
            f"👥 Total users: {total_users} ({new_today} new today)\n"
            f"🎵 Songs generated today: {songs_today}\n"
            "✅ Everything running normally"
        )
        log.info("Daily summary sent: users=%d new=%d songs=%d", total_users, new_today, songs_today)
    except Exception:
        log.exception("Daily summary failed")
