"""
zeus_ops_agent.py — Autonomous operations agent for Zeus Beats.

Scheduled jobs (registered in scheduler.py):
  health_check()   — daily at 9am UTC
                       • auto-fix songs stuck pending/generating > 15 min (mark failed + refund credit)
                       • check fal.ai balance — alert if < $5
                       • check Apiframe credits — alert if < 100

  daily_report()   — daily at 9am UTC
                       • total/new users, paid subscribers
                       • songs generated today + top genre, failed songs overnight
                       • songs last 24h split by type (normal/kids-story) and
                         success/fail — new subscriptions, renewals, errors
                         alerted (alerts.pop_digest_counters(), in-memory,
                         resets on each read — see alerts.py's note on the
                         redeploy-loses-count tradeoff, esp. for renewals)
                       • fal.ai / Apiframe balance status
                       • sends formatted Telegram DM to Michael

Event hooks (called from main.py / webhooks.py):
  on_new_signup(user_id, email)  — send welcome email via Resend
  on_song_failed(variant_id, error_msg) — retry once for free; refund the credit (once)
                                   when the retry fails too, or straight away for a
                                   content-policy refusal (never retried), and email
                                   the user. Refunds: db.refund_song_credit_once.

NO automatic song generation — this agent never creates songs on its own.
"""
import html as _html
import logging
import os
import sqlite3
from datetime import datetime, timezone

import requests

log = logging.getLogger("zeus.ops_agent")

# Public origin for song links in alerts. Songs live at /discover/<variant_id>.
_PUBLIC_BASE = os.environ.get("PUBLIC_SITE_URL", "https://zeusbeats.com").rstrip("/")

_DB_PATH_ENV = "DB_PATH"
_DB_DEFAULT  = "/data/zeus.db"

# ── Retry tracking ────────────────────────────────────────────────────────────
# Persistent: a retry row carries song_variants.retry_of = <original id>. This
# used to be two in-memory sets, lost on every redeploy, and a duplicate failed
# webhook re-ran the retry logic from scratch (2026-09-27).

# Provider refusals of the request itself. Retrying resubmits the same lyrics and
# style, so these cannot succeed — refund straight away instead. Matched on the
# provider's error text, lower-cased.
_CONTENT_REFUSAL_MARKERS = (
    "copyright",
    "inappropriate",
    "sensitive word",
    "content policy",
    "violates",
    "artist name",
)


def is_content_refusal(error_msg: str | None) -> bool:
    msg = (error_msg or "").lower()
    return any(m in msg for m in _CONTENT_REFUSAL_MARKERS)


def _db() -> str:
    return os.environ.get(_DB_PATH_ENV, _DB_DEFAULT)


# ── Health check ─────────────────────────────────────────────────────────────

def _fix_stuck_songs() -> list[str]:
    """Mark songs stuck pending/generating > 15 min as failed and refund credits.

    Returns a list of warning strings (empty = all OK).
    """
    warnings: list[str] = []
    try:
        import db as _dbmod
        conn = sqlite3.connect(_db())
        conn.row_factory = sqlite3.Row
        try:
            stuck = conn.execute(
                """SELECT id, user_id FROM song_variants
                   WHERE status IN ('pending', 'generating')
                   AND created_at <= datetime('now', '-15 minutes')"""
            ).fetchall()
        finally:
            conn.close()
        if not stuck:
            return []
        failed = refunded = 0
        for row in stuck:
            # Claim first: a late webhook may have failed/completed it meanwhile.
            if not _dbmod.claim_variant_failed(_db(), row["id"]):
                continue
            failed += 1
            # A stuck retry refunds its original; an uncharged song refunds nothing.
            did = _dbmod.refund_song_credit_once(_db(), row["id"], "stuck")
            refunded += int(did)
            log.warning(
                "ops_agent: auto-failed stuck variant %d (user=%s) — %s",
                row["id"], row["user_id"], "credit refunded" if did else "no refund due",
            )
        if failed:
            warnings.append(
                f"⏳ Auto-failed {failed} stuck song(s) (pending >15 min) — {refunded} credit(s) refunded"
            )
    except Exception:
        log.exception("ops_agent: _fix_stuck_songs raised")
    return warnings


def _send_recovery_notices() -> None:
    """Auto-resolve any incident quiet for incidents.AUTO_RESOLVE_QUIET_MINUTES+
    and ping a short recovered notice for each. Safe to call from multiple
    cycles (health_check daily, stuck_song_sweep every 15 min): resolving an
    incident that's already resolved is impossible by construction (the
    query only matches status='open'), so calling this more often only makes
    resolution more responsive, never double-fires.
    """
    import incidents
    from alerts import send_admin_alert

    try:
        resolved = incidents.resolve_stale()
    except Exception:
        log.exception("ops_agent: incidents.resolve_stale() raised")
        return
    for incident in resolved:
        try:
            send_admin_alert(
                f"✅ Recovered: {incident['title']} ({incident['category']})\n"
                f"No recurrence in {incidents.AUTO_RESOLVE_QUIET_MINUTES}+ min — "
                f"was open ×{incident['occurrence_count']} since {incident['first_seen'][:16]}"
            )
        except Exception:
            log.exception("ops_agent: recovery notice failed for category=%r", incident.get("category"))


def stuck_song_sweep() -> None:
    """Recover songs whose provider webhook never arrived. Runs every 15 min.

    _fix_stuck_songs() has always used a 15-minute threshold, but its only caller was
    health_check, which is a daily 09:00 cron — so the intent and the cadence
    disagreed by a factor of 96. A song whose webhook was lost at 20:41 stayed
    "generating" until 09:00 the next morning, holding the user's credit, with the UI
    polling it the entire time. That is exactly what happened to variants 1621/1622 on
    2026-08-28 and what prompted this job.

    This matters more than a normal retry loop because Apiframe v2 is webhook-only —
    there is no status or fetch endpoint to poll (every documented path 404s), so a
    dropped callback is unrecoverable and a sweep is the ONLY thing that ever ends a
    stuck song.

    Safe to run alongside health_check: _fix_stuck_songs flips status to 'failed', so
    a swept row no longer matches its own WHERE clause and cannot be refunded twice.
    """
    import incidents
    from alerts import send_admin_alert

    try:
        warnings = _fix_stuck_songs()
    except Exception:
        # _fix_stuck_songs already swallows its own errors; this is belt-and-braces so
        # a crash here can never kill the scheduler thread.
        log.exception("ops_agent: stuck_song_sweep raised")
        return

    if warnings:
        # Log BEFORE alerting, and never let the alert take down the job. The refund is
        # already committed by this point, so a Telegram outage must not turn a completed
        # recovery into a raised exception — the record of it has to survive regardless.
        log.warning("ops_agent stuck_song_sweep: %s", warnings)
        try:
            prefix = incidents.note("stuck_song_sweep", "\n".join(warnings))
            send_admin_alert(f"{prefix}\n⏳ <b>Zeus Ops</b> — stuck song sweep\n" + "\n".join(warnings))
        except Exception:
            log.exception("ops_agent: stuck_song_sweep alert failed (refund already applied)")
    else:
        log.info("ops_agent stuck_song_sweep: nothing stuck")

    # This is the most frequent cycle in the whole monitoring system (every 15
    # min, vs health_check's once a day) — running the auto-resolve sweep here
    # too, not just in health_check, is what actually makes "no new occurrence
    # for 60 minutes" a responsive check rather than a once-a-day one. Same
    # reasoning for expiring stale action offers: a 30-min TTL is only
    # actually enforced if something checks it more often than once a day.
    _send_recovery_notices()
    try:
        import incident_actions
        incident_actions.expire_stale_offers()
    except Exception:
        log.exception("ops_agent: incident_actions.expire_stale_offers() raised")


def health_check() -> None:
    """Run daily at 9am UTC.

    Fixes stuck songs, checks provider balances, alerts Michael if anything
    needs attention.
    """
    import incidents
    from alerts import _check_ai_providers, _check_apiframe_credits, _check_fal_balance, send_admin_alert

    warnings: list[str] = []

    stuck_warnings = _fix_stuck_songs()
    if stuck_warnings:
        try:
            prefix = incidents.note("stuck_song_sweep", "\n".join(stuck_warnings))
            stuck_warnings = [f"{prefix}\n{w}" for w in stuck_warnings]
        except Exception:
            log.exception("ops_agent health_check: incident tracking failed for stuck songs")
    warnings.extend(stuck_warnings)

    # (checker, category) pairs, explicit rather than derived from
    # checker.__name__ -- a name-string lookup would be one indirection away
    # from a category silently failing to match (a wrapped/mocked checker
    # with a different __name__, for instance) and incident tracking just
    # going quiet with no error. Pairing them directly can't drift apart.
    _CHECKERS = (
        (_check_fal_balance, "fal_balance"),
        (_check_apiframe_credits, "apiframe_credits"),
        (_check_ai_providers, "ai_providers"),
    )

    # A checker returns None ONLY when it positively read a healthy balance —
    # "couldn't check" comes back as a loud warning, never silence. If a checker
    # itself blows up, that is also reported rather than swallowed: a monitor
    # that fails quietly is worse than no monitor (see alerts.py header).
    for checker, category in _CHECKERS:
        # getattr guard: this is the error path, so it must not be able to throw.
        name = getattr(checker, "__name__", str(checker))
        try:
            w = checker()
        except Exception as exc:
            log.exception("ops_agent health_check: %s raised", name)
            w = (f"⁉️ {name} CRASHED — {type(exc).__name__}: {exc}. "
                 "Provider balance is currently unmonitored.")
        if w:
            try:
                severity = incidents.severity_from_checker_message(w)
                prefix = incidents.note(category, w, severity=severity)
                w = f"{prefix}\n{w}"
            except Exception:
                log.exception("ops_agent health_check: incident tracking failed for %s", category)
            warnings.append(w)

    if warnings:
        send_admin_alert("🚨 <b>Zeus Ops</b> — issues detected!\n" + "\n".join(warnings))
        log.warning("ops_agent health_check: %d warning(s) sent — %s", len(warnings), warnings)
    else:
        log.info("ops_agent health_check: all OK (fal.ai, Apiframe and every configured AI provider key)")

    _send_recovery_notices()


# ── Daily report ──────────────────────────────────────────────────────────────

def daily_report() -> None:
    """Run daily at 9am UTC.

    Queries the DB for key metrics and sends a formatted business report to Michael
    via Telegram DM. Also the (B) digest channel of the alerting build alongside the
    (A) immediate pings in alerts.py — piggybacked on this existing job rather than
    a separate schedule entry, since it already runs at the agreed 09:00 UTC time.
    """
    import alerts as _alerts

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

            # Songs by type, last 24h — split success/fail so a broken kids-story
            # path doesn't hide inside a healthy-looking normal-song number.
            type_rows = conn.execute(
                """SELECT COALESCE(l.kids_story, 0) AS kids_story, sv.status, COUNT(*) AS cnt
                   FROM song_variants sv LEFT JOIN lyrics l ON l.id = sv.lyric_id
                   WHERE sv.created_at >= datetime('now', '-24 hours')
                   GROUP BY 1, 2"""
            ).fetchall()
        finally:
            conn.close()

        by_type = {"normal": {"complete": 0, "failed": 0, "other": 0},
                   "kids-story": {"complete": 0, "failed": 0, "other": 0}}
        for row in type_rows:
            kind = "kids-story" if row["kids_story"] else "normal"
            bucket = row["status"] if row["status"] in ("complete", "failed") else "other"
            by_type[kind][bucket] += row["cnt"]

        overnight_note = (
            f"⚠️ {failed_overnight} song(s) failed overnight"
            if failed_overnight
            else "✅ No overnight failures"
        )

        counters = _alerts.pop_digest_counters()

        provider_lines = []
        for checker in (_alerts._check_fal_balance, _alerts._check_apiframe_credits, _alerts._check_ai_providers):
            try:
                warning = checker()
            except Exception:
                warning = f"⁉️ {checker.__name__} raised — check Railway logs"
            if warning:
                provider_lines.append(warning)
        if not provider_lines:
            provider_lines.append("✅ fal.ai, Apiframe and every configured AI provider key healthy")

        msg = (
            "📊 <b>Zeus Beats Daily Report</b>\n"
            f"👥 Total users: <b>{total_users}</b> (+{new_today} today)\n"
            f"💳 Paid subscribers: <b>{paid_count}</b>\n"
            f"🎵 Songs generated today: <b>{songs_today}</b>\n"
            f"🎼 Top genre today: <b>{top_genre}</b>\n"
            f"{overnight_note}\n"
            "\n"
            "🎵 <b>Songs, last 24h:</b>\n"
            f"  Normal: {by_type['normal']['complete']} ok, {by_type['normal']['failed']} failed, "
            f"{by_type['normal']['other']} in progress\n"
            f"  Kids-story: {by_type['kids-story']['complete']} ok, {by_type['kids-story']['failed']} failed, "
            f"{by_type['kids-story']['other']} in progress\n"
            "\n"
            f"💳 New subscriptions: {counters.get('new_subscriptions', 0)}\n"
            f"🔁 Renewals: {counters.get('renewals', 0)}\n"
            f"🚨 Errors alerted: {counters.get('errors', 0)}\n"
            "\n" + "\n".join(provider_lines)
        )
        # Bypass dedup — daily report must always send (message changes daily)
        _alerts._send_telegram(msg)
        log.info(
            "ops_agent: daily report sent — users=%d new=%d paid=%d songs=%d failed=%d counters=%s",
            total_users, new_today, paid_count, songs_today, failed_overnight, counters,
        )
    except Exception:
        log.exception("ops_agent: daily_report raised")

    # After (and independent of) the main report, so neither can break the other.
    _send_security_weekly()


def _send_security_weekly() -> None:
    """Monday-only security summary, riding on the daily report's 09:00 UTC slot
    (same piggyback precedent as the alert digest). send_weekly_if_due() itself
    checks the weekday and is idempotent, so a redeploy-triggered rerun is harmless."""
    try:
        import security_scan
        security_scan.send_weekly_if_due()
    except Exception:
        log.exception("ops_agent: weekly security summary failed")


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


# ── Discover monitor ───────────────────────────────────────────────────────────

_DISCOVER_MAX_LISTED = 10


def discover_monitor() -> None:
    """Alert when songs are shared to Discover. Runs every 30 min.

    Reports COALESCE(shared_at, created_at) — the same signal /api/discover/new-count
    uses for the badge — so the two can never disagree about what counts as new.

    Progress is tracked per row (discover_alerted_at) rather than by a global
    timestamp watermark. shared_at comes from CURRENT_TIMESTAMP and has one-second
    resolution, so two songs shared in the same second are identical to a
    `> watermark` comparison and the second is lost permanently. A NULL marker per
    row cannot collide, survives restarts, and is unaffected by a song arriving
    while the alert is being sent.

    Batched rather than per-share because the feed is bursty — eight songs in a day,
    then nothing for ten — and eight separate pings would be noise.

    On the very first run every existing public song is marked as already announced,
    so it stays silent instead of dumping all 145 at once. That is the same
    first-visit seeding the badge does.
    """
    import db as _db_mod
    from alerts import send_admin_alert

    try:
        db_path = _db_mod.get_db_path()
        pending = _db_mod.get_unalerted_discover_songs(db_path, limit=_DISCOVER_MAX_LISTED + 1)
    except Exception:
        log.exception("discover_monitor: query failed")
        return

    if not pending:
        log.info("discover_monitor: nothing new")
        return

    # First run: everything currently public predates the feature. Mark it seen
    # rather than announcing it.
    try:
        seeded = _db_mod.discover_alerts_initialised(db_path)
    except Exception:
        seeded = True   # never block on the check; worst case one extra alert
    if not seeded:
        try:
            all_public = _db_mod.get_unalerted_discover_songs(db_path, limit=100000)
            _db_mod.mark_discover_alerted(db_path, [s["variant_id"] for s in all_public])
            log.info("discover_monitor: seeded %d existing song(s) — silent first run",
                     len(all_public))
        except Exception:
            log.exception("discover_monitor: seeding failed")
        return

    listed = pending[:_DISCOVER_MAX_LISTED]
    overflow = len(pending) - len(listed)
    lines = [f"🎵 <b>{len(listed) + overflow} new on Discover</b>"]
    for s in listed:
        title = _html.escape(str(s.get("title") or f"Song #{s['variant_id']}"))
        artist = _html.escape(str(s.get("artist_name") or s.get("email") or "unknown"))
        genre = _html.escape(str(s.get("genre_tag") or ""))
        lines.append(f"• <b>{title}</b> — {artist}"
                     + (f" <i>({genre})</i>" if genre else "")
                     + f"\n  {_PUBLIC_BASE}/discover/{s['variant_id']}")
    if overflow:
        lines.append(f"…and {overflow} more")

    if send_admin_alert("\n".join(lines)):
        # Mark ONLY what was listed. Anything beyond the cap stays unalerted and is
        # picked up next run, so a large burst is announced across runs rather than
        # silently swallowed.
        try:
            _db_mod.mark_discover_alerted(db_path, [s["variant_id"] for s in listed])
            log.info("discover_monitor: announced %d song(s)", len(listed))
        except Exception:
            log.exception("discover_monitor: announced but could not mark — may repeat")
    else:
        # Leave them unmarked so the next run retries. A repeat ping beats a silent miss.
        log.warning("discover_monitor: alert not delivered — %d song(s) left pending", len(pending))


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

    # Only alert when something actually happened — new signups or upvote movement.
    # Silent when nothing changed so Michael isn't pinged every 30 min for "0 new".
    has_news = new_signups > 0 or ph_change > 0
    log.info(
        "ph_monitor: votes=%s ph_change=%d new_signups=%d total=%d has_news=%s",
        ph_votes, ph_change, new_signups, total_signups, has_news,
    )
    if not has_news:
        return

    parts = ["🚀 <b>Product Hunt update</b>"]
    if ph_votes is not None:
        change_str = f" (<b>+{ph_change}</b>)" if ph_change > 0 else ""
        parts.append(f"⬆️ Upvotes: <b>{ph_votes}</b>{change_str}")
    if new_signups > 0:
        parts.append(f"🆕 New signups: <b>+{new_signups}</b> 🔥")
    parts.append(f"👥 Total users: <b>{total_signups}</b>")

    token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    chat_id = _admin_chat_id()
    if token and chat_id:
        requests.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json={"chat_id": chat_id, "text": "\n".join(parts), "parse_mode": "HTML"},
            timeout=10,
        )


# ── Welcome email ─────────────────────────────────────────────────────────────

def on_new_signup(user_id: str, email: str, name: str = "") -> None:
    """Send a welcome email to a newly registered user.

    Called from main.py immediately after the user row is created.
    `name` is optional — it's an optional signup field, and is also collected
    after the user's first song. Greeting falls back to no name when absent.
    Fire-and-forget — never raises.
    """
    try:
        api_key = os.environ.get("RESEND_API_KEY", "").strip()
        if not api_key:
            log.warning("ops_agent: RESEND_API_KEY not set — skipping welcome email for %s", email)
            return
        from telegram_admin import _send_one_email
        subject = "Welcome to Zeus Beats 🎵"
        first_name = (name or "").strip().split(" ")[0]
        greeting = f"You're in, {first_name}!" if first_name else "You're in!"
        body = (
            f"{greeting}\n\n"
            "Your account is ready and you have 3 free songs waiting.\n\n"
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

def _send_failure_email(email: str, variant_id: int, name: str = "",
                        reason: str = "retry_failed", provider_msg: str = "") -> None:
    try:
        api_key = os.environ.get("RESEND_API_KEY", "").strip()
        if not api_key:
            return
        from telegram_admin import _send_one_email
        subject = "Your Zeus Beats song credit has been refunded"
        first_name = (name or "").strip().split(" ")[0]
        opener = f"Sorry {first_name} — your song" if first_name else "Sorry — your song"
        if reason == "content_refusal":
            # Not a blip and not retried — retrying the same words can't work.
            said = f'\n\nThe message we got back was: "{provider_msg.strip()}"' if provider_msg.strip() else ""
            body = (
                f"{opener} couldn't be made: our music AI refused the request, usually because "
                "the lyrics or style include copyrighted lyrics, an artist's name, or words it "
                f"won't sing.{said}\n\n"
                "We've refunded your credit. Change the lyrics (write your own words rather than "
                "an existing song's) and try again.\n\n"
                "If you think this is a mistake, reply to this email and we'll take a look."
            )
        else:
            body = (
                f"{opener} failed to generate this time.\n\n"
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

        # Insert new variant row — no credit deduction (covered by the original).
        # retry_of makes any refund for this row land on the charged original.
        conn = sqlite3.connect(_db())
        try:
            cur = conn.cursor()
            cur.execute(
                """INSERT INTO song_variants (lyric_id, user_id, style_prompt, genre_tag, status, take_number,
                                              credit_charged, retry_of)
                   VALUES (?, ?, ?, ?, 'pending', 1, 0, ?)""",
                (v["lyric_id"], v["user_id"], v["style_prompt"], v["genre_tag"], variant_id),
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


def _refund_and_notify(variant_id: int, reason: str = "retry_failed", provider_msg: str = "") -> bool:
    """Refund the credit behind variant_id (once — see db.refund_song_credit_once)
    and email the user. No email when nothing was refunded: it says "refunded"."""
    try:
        import db as _dbmod
        refunded = _dbmod.refund_song_credit_once(_db(), variant_id, reason)
        if not refunded:
            log.info("ops_agent: variant %d — no refund due (uncharged or already refunded)", variant_id)
            return False
        conn = sqlite3.connect(_db())
        conn.row_factory = sqlite3.Row
        try:
            row = conn.execute(
                """SELECT u.email, u.name FROM song_variants sv JOIN users u ON u.id = sv.user_id
                   WHERE sv.id = ?""",
                (variant_id,),
            ).fetchone()
        finally:
            conn.close()
        log.info("ops_agent: refunded credit for variant %d (%s)", variant_id, reason)
        if row:
            _send_failure_email(row["email"], variant_id, name=row["name"] or "",
                                reason=reason, provider_msg=provider_msg)
        return True
    except Exception:
        log.exception("ops_agent: _refund_and_notify raised for variant %d", variant_id)
        return False


def on_song_failed(variant_id: int, error_msg: str | None = None) -> None:
    """Called ONCE per failed variant — callers claim the failure first with
    db.claim_variant_failed, so a duplicate provider notice never gets here.

    Failed retry           → refund the charged original (once) + email.
    Content-policy refusal → no retry (it can't succeed); refund + email now.
    First ordinary failure → retry once for free; NO refund yet — if the retry
                             succeeds the user has their song.

    Never raises — all errors are logged; if something breaks mid-way the credit
    is refunded rather than left held (refunding is idempotent, so that's safe).
    """
    try:
        conn = sqlite3.connect(_db())
        try:
            row = conn.execute("SELECT retry_of FROM song_variants WHERE id = ?", (variant_id,)).fetchone()
            already_retried = conn.execute(
                "SELECT 1 FROM song_variants WHERE retry_of = ? LIMIT 1", (variant_id,)
            ).fetchone()
        finally:
            conn.close()
        if row is None:
            log.warning("ops_agent: on_song_failed(%d) — variant not found", variant_id)
            return

        if row[0] is not None:
            log.warning(
                "ops_agent: retry variant %d also failed (original=%d) — refunding",
                variant_id, row[0],
            )
            _refund_and_notify(variant_id)
            return

        if is_content_refusal(error_msg):
            log.info("ops_agent: variant %d refused by provider (%r) — refunding, not retrying",
                     variant_id, (error_msg or "")[:200])
            _refund_and_notify(variant_id, reason="content_refusal", provider_msg=error_msg or "")
            return

        if already_retried:
            log.info("ops_agent: variant %d already retried — ignoring repeat failure", variant_id)
            return

        log.info("ops_agent: first failure for variant %d — attempting retry", variant_id)
        if _retry_song(variant_id) is None:
            log.warning("ops_agent: retry submission failed for variant %d — refunding immediately", variant_id)
            _refund_and_notify(variant_id)

    except Exception:
        log.exception("ops_agent: on_song_failed(%d) raised unexpectedly — refunding", variant_id)
        _refund_and_notify(variant_id)
