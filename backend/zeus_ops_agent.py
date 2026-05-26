"""
zeus_ops_agent.py — Autonomous operations agent for Zeus Beats.

Scheduled jobs (registered in scheduler.py):
  health_check()   — every 30 min
                       • auto-fix songs stuck pending/generating > 15 min (mark failed + refund credit)
                       • check fal.ai balance — alert if < $5
                       • check Apiframe credits — alert if < 100

  daily_report()   — daily at 9am UTC
                       • total/new users, paid subscribers
                       • songs generated today + top genre
                       • failed songs overnight
                       • sends formatted Telegram DM to Michael

Event hooks (called from main.py / webhooks.py):
  on_new_signup(user_id, email)  — send welcome email via Resend
  on_song_failed(variant_id)     — retry once for free; on retry failure refund credit
                                   and email user "sorry, credit refunded"

NO automatic song generation — this agent never creates songs on its own.
"""
import logging
import os
import sqlite3

import requests

log = logging.getLogger("zeus.ops_agent")

_DB_PATH_ENV = "DB_PATH"
_DB_DEFAULT  = "/data/zeus.db"

# ── Retry tracking ────────────────────────────────────────────────────────────
# In-memory only; resets on redeploy. The 30-min dedup window in alerts.py
# ensures we don't spam Michael if the process restarts mid-retry.
#
# _retry_attempted  — original variant_ids we have already retried once
# _retry_map        — {retry_variant_id: original_variant_id}
_retry_attempted: set[int] = set()
_retry_map: dict[int, int] = {}


def _db() -> str:
    return os.environ.get(_DB_PATH_ENV, _DB_DEFAULT)


# ── Health check ─────────────────────────────────────────────────────────────

def _fix_stuck_songs() -> list[str]:
    """Mark songs stuck pending/generating > 15 min as failed and refund credits.

    Returns a list of warning strings (empty = all OK).
    """
    warnings: list[str] = []
    try:
        conn = sqlite3.connect(_db())
        conn.row_factory = sqlite3.Row
        try:
            stuck = conn.execute(
                """SELECT id, user_id FROM song_variants
                   WHERE status IN ('pending', 'generating')
                   AND created_at <= datetime('now', '-15 minutes')"""
            ).fetchall()
            if not stuck:
                return []
            for row in stuck:
                conn.execute(
                    "UPDATE song_variants SET status = 'failed' WHERE id = ?",
                    (row["id"],),
                )
                conn.execute(
                    "UPDATE song_credits SET balance = balance + 1 WHERE user_id = ?",
                    (row["user_id"],),
                )
                log.warning(
                    "ops_agent: auto-failed stuck variant %d (user=%s) — credit refunded",
                    row["id"], row["user_id"],
                )
            conn.commit()
            warnings.append(
                f"⏳ Auto-failed {len(stuck)} stuck song(s) (pending >15 min) — credits refunded"
            )
        finally:
            conn.close()
    except Exception:
        log.exception("ops_agent: _fix_stuck_songs raised")
    return warnings


def health_check() -> None:
    """Run every 30 min.

    Fixes stuck songs, checks provider balances, alerts Michael if anything
    needs attention.
    """
    from alerts import _check_apiframe_credits, _check_fal_balance, send_admin_alert

    warnings: list[str] = []

    warnings.extend(_fix_stuck_songs())

    for checker in (_check_fal_balance, _check_apiframe_credits):
        w = checker()
        if w:
            warnings.append(w)

    if warnings:
        send_admin_alert("🚨 <b>Zeus Ops</b> — issues detected!\n" + "\n".join(warnings))
        log.warning("ops_agent health_check: %d warning(s) sent", len(warnings))
    else:
        log.info("ops_agent health_check: all OK")


# ── Daily report ──────────────────────────────────────────────────────────────

def daily_report() -> None:
    """Run daily at 9am UTC.

    Queries the DB for key metrics and sends a formatted business report to Michael
    via Telegram DM.
    """
    from alerts import send_admin_alert

    try:
        conn = sqlite3.connect(_db())
        conn.row_factory = sqlite3.Row
        try:
            total_users = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
            new_today = conn.execute(
                "SELECT COUNT(*) FROM users WHERE date(created_at) = date('now')"
            ).fetchone()[0]
            paid_count = conn.execute(
                "SELECT COUNT(*) FROM users WHERE subscription_status = 'active'"
            ).fetchone()[0]
            songs_today = conn.execute(
                """SELECT COUNT(*) FROM song_variants
                   WHERE status = 'complete' AND date(completed_at) = date('now')"""
            ).fetchone()[0]
            failed_overnight = conn.execute(
                """SELECT COUNT(*) FROM song_variants
                   WHERE status = 'failed'
                   AND created_at >= datetime('now', '-24 hours')"""
            ).fetchone()[0]
            top_row = conn.execute(
                """SELECT genre_tag, COUNT(*) AS cnt FROM song_variants
                   WHERE status = 'complete' AND date(completed_at) = date('now')
                   AND genre_tag IS NOT NULL
                   GROUP BY genre_tag ORDER BY cnt DESC LIMIT 1"""
            ).fetchone()
            top_genre = top_row["genre_tag"] if top_row else "—"
        finally:
            conn.close()

        overnight_note = (
            f"⚠️ {failed_overnight} song(s) failed overnight"
            if failed_overnight
            else "✅ No overnight failures"
        )

        msg = (
            "📊 <b>Zeus Beats Daily Report</b>\n"
            f"👥 Total users: <b>{total_users}</b> (+{new_today} today)\n"
            f"💳 Paid subscribers: <b>{paid_count}</b>\n"
            f"🎵 Songs generated today: <b>{songs_today}</b>\n"
            f"🎼 Top genre today: <b>{top_genre}</b>\n"
            f"{overnight_note}"
        )
        # Bypass dedup — daily report must always send (message changes daily)
        from alerts import _admin_chat_id
        token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
        chat_id = _admin_chat_id()
        if token and chat_id:
            requests.post(
                f"https://api.telegram.org/bot{token}/sendMessage",
                json={"chat_id": chat_id, "text": msg, "parse_mode": "HTML"},
                timeout=10,
            )
        log.info(
            "ops_agent: daily report sent — users=%d new=%d paid=%d songs=%d failed=%d",
            total_users, new_today, paid_count, songs_today, failed_overnight,
        )
    except Exception:
        log.exception("ops_agent: daily_report raised")


# ── Evening check-in ──────────────────────────────────────────────────────────

def evening_checkin() -> None:
    """Send Michael a 7pm check-in asking what he wants to ship tonight."""
    from alerts import _admin_chat_id
    try:
        conn = sqlite3.connect(_db())
        conn.row_factory = sqlite3.Row
        try:
            pending = conn.execute(
                "SELECT COUNT(*) FROM song_variants WHERE status IN ('pending','generating')"
            ).fetchone()[0]
            new_today = conn.execute(
                "SELECT COUNT(*) FROM users WHERE date(created_at) = date('now')"
            ).fetchone()[0]
            songs_today = conn.execute(
                "SELECT COUNT(*) FROM song_variants WHERE status='complete' AND date(completed_at)=date('now')"
            ).fetchone()[0]
        finally:
            conn.close()

        parts = ["🌆 Evening mate — anything you want to ship tonight? 💪"]
        if new_today:
            parts.append(f"👥 {new_today} new signup(s) today")
        if songs_today:
            parts.append(f"🎵 {songs_today} songs generated today")
        if pending:
            parts.append(f"⏳ {pending} song(s) still processing")
        parts.append("\nJust tell me what you need and I'll sort it.")

        token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
        chat_id = _admin_chat_id()
        if token and chat_id:
            requests.post(
                f"https://api.telegram.org/bot{token}/sendMessage",
                json={"chat_id": chat_id, "text": "\n".join(parts), "parse_mode": "HTML"},
                timeout=10,
            )
        log.info("ops_agent: evening check-in sent")
    except Exception:
        log.exception("ops_agent: evening_checkin raised")


# ── Product Hunt monitor ───────────────────────────────────────────────────────

_ph_last_votes: int | None = None
_ph_last_signup_count: int | None = None


def ph_monitor() -> None:
    """Run every 30 min to track Product Hunt upvotes and new signups.

    Configure PRODUCTHUNT_SLUG env var to the product's PH slug
    (e.g. "zeus-beats" for producthunt.com/posts/zeus-beats).
    """
    global _ph_last_votes, _ph_last_signup_count
    from alerts import _admin_chat_id

    try:
        conn = sqlite3.connect(_db())
        conn.row_factory = sqlite3.Row
        try:
            total_signups = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
        finally:
            conn.close()
    except Exception:
        log.exception("ph_monitor: DB error")
        return

    new_signups = 0
    if _ph_last_signup_count is not None:
        new_signups = max(0, total_signups - _ph_last_signup_count)
    _ph_last_signup_count = total_signups

    ph_votes: int | None = None
    ph_change = 0
    slug = os.environ.get("PRODUCTHUNT_SLUG", "").strip()
    if slug:
        try:
            import re
            resp = requests.get(
                f"https://www.producthunt.com/posts/{slug}",
                headers={"User-Agent": "Mozilla/5.0 (compatible; ZeusBeatsMonitor/1.0)"},
                timeout=15,
            )
            m = re.search(r'"votesCount":\s*(\d+)', resp.text)
            if m:
                ph_votes = int(m.group(1))
            else:
                # Fallback: look for vote count in OG description
                m2 = re.search(r'(\d+)\s+(?:upvotes?|votes?)', resp.text, re.IGNORECASE)
                if m2:
                    ph_votes = int(m2.group(1))
        except Exception as exc:
            log.warning("ph_monitor: could not fetch PH page for %s: %s", slug, exc)

    if ph_votes is not None:
        ph_change = ph_votes - (_ph_last_votes or ph_votes)
        _ph_last_votes = ph_votes

    parts = ["🚀 <b>Product Hunt — 30min update</b>"]
    if slug:
        if ph_votes is not None:
            change_str = f" (<b>+{ph_change}</b>)" if ph_change > 0 else ""
            parts.append(f"⬆️ Upvotes: <b>{ph_votes}</b>{change_str}")
        else:
            parts.append("⬆️ Upvotes: couldn't fetch (check PRODUCTHUNT_SLUG)")
    else:
        parts.append("⬆️ Upvotes: set PRODUCTHUNT_SLUG env var to track")

    if new_signups > 0:
        parts.append(f"🆕 New signups (30 min): <b>+{new_signups}</b> 🔥")
    else:
        parts.append("🆕 New signups (30 min): 0")
    parts.append(f"👥 Total users: <b>{total_signups}</b>")

    token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    chat_id = _admin_chat_id()
    if token and chat_id:
        msg = "\n".join(parts)
        requests.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json={"chat_id": chat_id, "text": msg, "parse_mode": "HTML"},
            timeout=10,
        )
    log.info(
        "ph_monitor: votes=%s new_signups=%d total=%d",
        ph_votes, new_signups, total_signups,
    )


# ── Welcome email ─────────────────────────────────────────────────────────────

def on_new_signup(user_id: str, email: str) -> None:
    """Send a welcome email to a newly registered user.

    Called from main.py immediately after the user row is created.
    Fire-and-forget — never raises.
    """
    try:
        api_key = os.environ.get("RESEND_API_KEY", "").strip()
        if not api_key:
            log.warning("ops_agent: RESEND_API_KEY not set — skipping welcome email for %s", email)
            return
        from telegram_admin import _send_one_email
        subject = "Welcome to Zeus Beats 🎵"
        body = (
            "You're in!\n\n"
            "Your account is ready and you have 5 free songs waiting.\n\n"
            "Here's how to get started:\n\n"
            "1. Tell Zeus what kind of song you want — describe the vibe, genre, or mood\n"
            "2. Zeus writes the lyrics and generates your track\n"
            "3. Download, share, or post it directly to your Telegram channel\n\n"
            "Your first song takes about 2 minutes. We think you'll love it 🎧\n\n"
            "If you have any questions just reply to this email."
        )
        ok = _send_one_email(email, subject, body, api_key)
        if ok:
            log.info("ops_agent: welcome email sent to %s", email)
        else:
            log.warning("ops_agent: welcome email failed for %s", email)
    except Exception:
        log.exception("ops_agent: on_new_signup raised for %s", email)


# ── Song failure retry ────────────────────────────────────────────────────────

def _send_failure_email(email: str, variant_id: int) -> None:
    try:
        api_key = os.environ.get("RESEND_API_KEY", "").strip()
        if not api_key:
            return
        from telegram_admin import _send_one_email
        subject = "Your Zeus Beats song credit has been refunded"
        body = (
            "Sorry — your song failed to generate this time.\n\n"
            "We automatically retried but hit the same error, so we've refunded your credit "
            "and you can try again straight away.\n\n"
            "This is usually a temporary blip with our music AI. Just head back to Zeus Beats "
            "and give it another go — it normally works first time!\n\n"
            "If it keeps happening, reply to this email and we'll sort it out personally."
        )
        _send_one_email(email, subject, body, api_key)
        log.info("ops_agent: failure email sent to %s (variant %d)", email, variant_id)
    except Exception:
        log.exception("ops_agent: _send_failure_email raised for variant %d", variant_id)


def _retry_song(variant_id: int) -> int | None:
    """Re-submit a failed variant to Apiframe without deducting another credit.

    Creates a new song_variants row and fires the API call.
    Returns the new variant_id on success, None on any error.
    """
    try:
        conn = sqlite3.connect(_db())
        conn.row_factory = sqlite3.Row
        try:
            v = conn.execute(
                "SELECT lyric_id, user_id, style_prompt, genre_tag FROM song_variants WHERE id = ?",
                (variant_id,),
            ).fetchone()
            if not v:
                log.warning("ops_agent: _retry_song: variant %d not found", variant_id)
                return None
            lyric_row = conn.execute(
                "SELECT lyrics_text FROM lyrics WHERE id = ?",
                (v["lyric_id"],),
            ).fetchone()
            if not lyric_row:
                log.warning("ops_agent: _retry_song: lyric %d not found", v["lyric_id"])
                return None
            lyrics = lyric_row["lyrics_text"]
        finally:
            conn.close()

        # Insert new variant row — no credit deduction (covered by the original)
        conn = sqlite3.connect(_db())
        try:
            cur = conn.cursor()
            cur.execute(
                """INSERT INTO song_variants (lyric_id, user_id, style_prompt, genre_tag, status, take_number)
                   VALUES (?, ?, ?, ?, 'pending', 1)""",
                (v["lyric_id"], v["user_id"], v["style_prompt"], v["genre_tag"]),
            )
            new_vid = cur.lastrowid
            conn.commit()
        finally:
            conn.close()

        webhook_url = os.environ.get("SONG_WEBHOOK_URL", "").strip().rstrip("/")
        apiframe_key = os.environ.get("APIFRAME_API_KEY", "").strip()
        if not webhook_url or not apiframe_key:
            log.warning("ops_agent: _retry_song: env vars missing")
            return None

        resp = requests.post(
            "https://api.apiframe.ai/v2/music/generate",
            headers={"X-API-Key": apiframe_key, "Content-Type": "application/json"},
            json={
                "prompt": lyrics,
                "model": "suno",
                "webhookUrl": f"{webhook_url}?variant_id={new_vid}",
                "webhookEvents": ["completed", "failed"],
                "sunoParams": {
                    "custom_mode": True,
                    "instrumental": False,
                    "model_version": "V5",
                    "style": v["style_prompt"][:1000],
                },
            },
            timeout=30,
        )
        resp.raise_for_status()
        job_id = resp.json().get("jobId")

        if job_id:
            conn = sqlite3.connect(_db())
            try:
                conn.execute(
                    "UPDATE song_variants SET provider_job_id = ?, status = 'generating' WHERE id = ?",
                    (job_id, new_vid),
                )
                conn.commit()
            finally:
                conn.close()

        log.info("ops_agent: retried variant %d → new variant %d (job=%s)", variant_id, new_vid, job_id)
        return new_vid

    except Exception:
        log.exception("ops_agent: _retry_song raised for variant %d", variant_id)
        return None


def _refund_and_notify(variant_id: int) -> None:
    """Refund the song credit for the user of variant_id and email them."""
    try:
        conn = sqlite3.connect(_db())
        conn.row_factory = sqlite3.Row
        try:
            row = conn.execute(
                """SELECT sv.user_id, u.email
                   FROM song_variants sv JOIN users u ON u.id = sv.user_id
                   WHERE sv.id = ?""",
                (variant_id,),
            ).fetchone()
            if not row:
                log.warning("ops_agent: _refund_and_notify: variant %d not found", variant_id)
                return
            conn.execute(
                "UPDATE song_credits SET balance = balance + 1 WHERE user_id = ?",
                (row["user_id"],),
            )
            conn.commit()
            log.info("ops_agent: refunded credit for user %s (variant %d)", row["user_id"], variant_id)
        finally:
            conn.close()
        _send_failure_email(row["email"], variant_id)
    except Exception:
        log.exception("ops_agent: _refund_and_notify raised for variant %d", variant_id)


def on_song_failed(variant_id: int) -> None:
    """Called whenever a song variant is marked failed.

    First failure  → retry once (new variant, no extra credit deducted).
    Retry failure  → refund original credit + email user.

    Never raises — all errors are logged and swallowed.
    """
    try:
        # Is this the failure of a retry we launched?
        if variant_id in _retry_map:
            original_id = _retry_map.pop(variant_id)
            _retry_attempted.discard(original_id)
            log.warning(
                "ops_agent: retry variant %d also failed (original=%d) — refunding",
                variant_id, original_id,
            )
            _refund_and_notify(original_id)
            return

        # Have we already retried this variant? (shouldn't happen, but guard it)
        if variant_id in _retry_attempted:
            log.debug("ops_agent: on_song_failed(%d) — already in retry set, ignoring", variant_id)
            return

        # First failure — attempt retry
        _retry_attempted.add(variant_id)
        log.info("ops_agent: first failure for variant %d — attempting retry", variant_id)

        new_vid = _retry_song(variant_id)
        if new_vid:
            _retry_map[new_vid] = variant_id
        else:
            # Retry submission itself failed — refund immediately
            _retry_attempted.discard(variant_id)
            log.warning("ops_agent: retry submission failed for variant %d — refunding immediately", variant_id)
            _refund_and_notify(variant_id)

    except Exception:
        log.exception("ops_agent: on_song_failed(%d) raised unexpectedly", variant_id)
