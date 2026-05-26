"""
telegram_admin.py — Admin command handler for @porickbot.

Only responds to TELEGRAM_ADMIN_USER_ID. Commands are parsed synchronously;
async actions (Telegram posts) return sentinel strings handled by main.py.

Natural language messages are handled by Claude Haiku — Michael can just
talk to Porick conversationally and it figures out the right action.
Precision commands (raw SQL, Railway vars) still use exact-match parsing
to avoid AI misinterpretation.
"""
import json
import logging
import os
import re
import sqlite3
import time
from collections import deque

import requests

log = logging.getLogger("zeus.admin_bot")

# Ring buffer: last 100 log lines, populated by install_log_buffer()
_log_buffer: deque = deque(maxlen=100)

_RAILWAY_GQL = "https://backboard.railway.app/graphql/v2"

HELP_TEXT = """🤖 <b>Porick — Zeus Beats Admin Bot</b>

Just talk to me naturally, mate! Examples:
• <i>"How's everything going?"</i>
• <i>"What are the latest signups?"</i>
• <i>"Give laky120@yahoo.com 20 more songs"</i>
• <i>"Upgrade anne to music_pro for free"</i>
• <i>"Post on the channel that we have new genres"</i>
• <i>"Email all users about the new playlist feature"</i>
• <i>"Show me the logs"</i>
• <i>"Refund people who had failures"</i>
• <i>"What's today's revenue?"</i>
• <i>"Top genres this week"</i>
• <i>"Tell Claude Code to fix the stems button on mobile"</i>
• <i>"Log a feature: dark mode for the app"</i>

<b>Precision commands (exact syntax required)</b>
<code>db query "SELECT ..."</code> — read-only SQL
<code>db exec "UPDATE/INSERT ..."</code> — write SQL
<code>var set KEY=VALUE</code> — Railway env var
<code>var get KEY</code>
<code>stripe product "Name" £9.99</code>
<code>stripe list</code>
<code>post song VARIANT_ID</code> — post a specific song
<code>broadcast Subject | Message body</code> — email ALL Zeus Beats users
<code>refund failures</code> — refund 1 credit per song failed in last 24h
<code>help</code>"""


# ── Railway helpers ──────────────────────────────────────────────────────────

def _gql(query: str, variables: dict) -> dict:
    token = os.environ.get("RAILWAY_API_TOKEN", "").strip()
    if not token:
        return {"error": "RAILWAY_API_TOKEN not set in Railway variables"}
    try:
        r = requests.post(
            _RAILWAY_GQL,
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
            json={"query": query, "variables": variables},
            timeout=20,
        )
        return r.json()
    except Exception as exc:
        return {"error": str(exc)}


def _cmd_var_set(key: str, value: str) -> str:
    result = _gql(
        "mutation($input: VariableUpsertInput!) { variableUpsert(input: $input) }",
        {"input": {
            "name": key, "value": value,
            "projectId": os.environ.get("RAILWAY_PROJECT_ID", ""),
            "environmentId": os.environ.get("RAILWAY_ENVIRONMENT_ID", ""),
            "serviceId": os.environ.get("RAILWAY_SERVICE_ID", ""),
        }},
    )
    if "error" in result:
        return f"❌ {result['error']}"
    if result.get("errors"):
        return f"❌ {result['errors'][0]['message']}"
    return f"✅ Set <code>{key}</code>"


def _cmd_var_get(key: str) -> str:
    result = _gql(
        """query($projectId: String!, $environmentId: String!, $serviceId: String!) {
            variables(projectId: $projectId, environmentId: $environmentId, serviceId: $serviceId)
        }""",
        {
            "projectId": os.environ.get("RAILWAY_PROJECT_ID", ""),
            "environmentId": os.environ.get("RAILWAY_ENVIRONMENT_ID", ""),
            "serviceId": os.environ.get("RAILWAY_SERVICE_ID", ""),
        },
    )
    if "error" in result:
        return f"❌ {result['error']}"
    if result.get("errors"):
        return f"❌ {result['errors'][0]['message']}"
    variables = result.get("data", {}).get("variables") or {}
    if key not in variables:
        return f"❓ Variable <code>{key}</code> not found"
    val = variables[key]
    # Mask secrets: show first 4 chars + length
    if len(val) > 8:
        display = val[:4] + "…" + f" ({len(val)} chars)"
    else:
        display = "***"
    return f"🔑 <code>{key}</code> = {display}"


def _cmd_logs() -> str:
    lines = list(_log_buffer)[-20:]
    if not lines:
        return "📋 No log lines captured yet (buffer fills as the app runs)"
    return "<pre>" + "\n".join(lines[-20:]) + "</pre>"


def _cmd_redeploy() -> str:
    result = _gql(
        """mutation($environmentId: String!, $serviceId: String!) {
            serviceInstanceRedeploy(environmentId: $environmentId, serviceId: $serviceId)
        }""",
        {
            "environmentId": os.environ.get("RAILWAY_ENVIRONMENT_ID", ""),
            "serviceId": os.environ.get("RAILWAY_SERVICE_ID", ""),
        },
    )
    if "error" in result:
        return f"❌ {result['error']}"
    if result.get("errors"):
        return f"❌ {result['errors'][0]['message']}"
    return "🚀 Redeploy triggered — check Railway dashboard for progress"


# ── Stripe helpers ───────────────────────────────────────────────────────────

def _cmd_stripe_product(name: str, amount_pence: int) -> str:
    try:
        import billing
        stripe = billing.get_stripe()
        product = stripe.Product.create(name=name)
        price = stripe.Price.create(
            product=product.id,
            unit_amount=amount_pence,
            currency="gbp",
            recurring={"interval": "month"},
        )
        return (
            f"✅ <b>Created Stripe product</b>\n"
            f"Name: {name}\n"
            f"Price: £{amount_pence / 100:.2f}/mo\n"
            f"Product ID: <code>{product.id}</code>\n"
            f"Price ID: <code>{price.id}</code>"
        )
    except Exception as exc:
        return f"❌ Stripe error: {exc}"


def _cmd_stripe_list() -> str:
    try:
        import billing
        stripe = billing.get_stripe()
        products = stripe.Product.list(limit=10, active=True)
        lines = []
        for p in products.data:
            prices = stripe.Price.list(product=p.id, active=True, limit=3)
            for pr in prices.data:
                interval = pr.recurring.interval if pr.recurring else "one-time"
                amt = f"£{pr.unit_amount / 100:.2f}"
                lines.append(f"• {p.name} — {amt}/{interval}\n  <code>{pr.id}</code>")
        return "\n".join(lines) if lines else "No active Stripe products found"
    except Exception as exc:
        return f"❌ Stripe error: {exc}"


# ── Database helpers ─────────────────────────────────────────────────────────

def _cmd_db_query(sql: str) -> str:
    """Read-only SELECT queries."""
    if not sql.strip().upper().startswith("SELECT"):
        return "❌ Only SELECT queries allowed via <code>db query</code>. Use <code>db exec</code> for writes."
    try:
        import db as _db
        db_path = _db.get_db_path()
        conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
        conn.row_factory = sqlite3.Row
        try:
            rows = conn.execute(sql).fetchmany(20)
            if not rows:
                return "✅ Query returned 0 rows"
            keys = list(rows[0].keys())
            header = " | ".join(keys)
            body = "\n".join(" | ".join(str(row[k]) for k in keys) for row in rows)
            result = f"{header}\n{'-' * len(header)}\n{body}"
            return f"<pre>{result[:3500]}</pre>"
        finally:
            conn.close()
    except Exception as exc:
        return f"❌ DB error: {exc}"


def _cmd_db_exec(sql: str) -> str:
    """Execute any write SQL statement (UPDATE, INSERT, DELETE, etc.)."""
    try:
        import db as _db
        db_path = _db.get_db_path()
        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row
        try:
            conn.execute(sql)
            rows_changed = conn.execute("SELECT changes()").fetchone()[0]
            conn.commit()
            log.info("db exec by admin: %r — rows affected: %d", sql[:200], rows_changed)
            return f"✅ Executed. Rows affected: <b>{rows_changed}</b>"
        finally:
            conn.close()
    except Exception as exc:
        return f"❌ DB error: {exc}"


def _cmd_db_verify_email(email: str) -> str:
    """Set email_verified=1 for a user by email."""
    try:
        import db as _db
        db_path = _db.get_db_path()
        conn = sqlite3.connect(str(db_path))
        try:
            conn.execute(
                "UPDATE users SET email_verified = 1 WHERE lower(email) = lower(?)", (email,)
            )
            rows_changed = conn.execute("SELECT changes()").fetchone()[0]
            conn.commit()
        finally:
            conn.close()
        if rows_changed:
            log.info("db verify email: verified %s", email)
            return f"✅ Email verified for <code>{email}</code>"
        return f"❓ No user found with email <code>{email}</code>"
    except Exception as exc:
        return f"❌ DB error: {exc}"


def _cmd_db_unverify_email(email: str) -> str:
    """Set email_verified=0 for a user by email."""
    try:
        import db as _db
        db_path = _db.get_db_path()
        conn = sqlite3.connect(str(db_path))
        try:
            conn.execute(
                "UPDATE users SET email_verified = 0 WHERE lower(email) = lower(?)", (email,)
            )
            rows_changed = conn.execute("SELECT changes()").fetchone()[0]
            conn.commit()
        finally:
            conn.close()
        if rows_changed:
            log.info("db unverify email: unverified %s", email)
            return f"✅ Email unverified for <code>{email}</code>"
        return f"❓ No user found with email <code>{email}</code>"
    except Exception as exc:
        return f"❌ DB error: {exc}"


def _cmd_db_user(email: str) -> str:
    """Show full details for a user by email."""
    try:
        import db as _db
        db_path = _db.get_db_path()
        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row
        try:
            row = conn.execute(
                """SELECT u.email, u.subscription_status, u.subscription_plan, u.has_paid,
                          u.email_verified, u.created_at,
                          sc.balance, sc.monthly_allowance,
                          sc.premium_balance, sc.premium_monthly_allowance
                   FROM users u
                   LEFT JOIN song_credits sc ON sc.user_id = u.id
                   WHERE lower(u.email) = lower(?)""",
                (email,),
            ).fetchone()
        finally:
            conn.close()
        if not row:
            return f"❓ No user found: <code>{email}</code>"
        verified = "✅" if row["email_verified"] else "❌"
        return (
            f"📧 <b>{row['email']}</b>\n"
            f"💳 Plan: <b>{row['subscription_plan'] or 'free'}</b>\n"
            f"✅ Status: {row['subscription_status'] or 'none'}\n"
            f"💰 Has paid: {bool(row['has_paid'])}\n"
            f"📨 Email verified: {verified}\n"
            f"🎵 Song credits: {row['balance']} (allowance: {row['monthly_allowance']})\n"
            f"⭐ Premium credits: {row['premium_balance']} (allowance: {row['premium_monthly_allowance']})\n"
            f"📅 Created: {(row['created_at'] or '')[:10]}"
        )
    except Exception as exc:
        return f"❌ DB error: {exc}"


def _cmd_db_fix_youtube(email: str) -> str:
    try:
        import db as _db
        db_path = _db.get_db_path()
        user = _db.get_user_by_email(db_path, email)
        if not user:
            return f"❌ User not found: <code>{email}</code>"
        _db.update_user(db_path, user["id"], youtube_refresh_token=None)
        return f"✅ YouTube token cleared for <code>{email}</code>"
    except Exception as exc:
        return f"❌ Error: {exc}"


def _cmd_db_credits(email: str, delta: int) -> str:
    try:
        import db as _db
        db_path = _db.get_db_path()
        user = _db.get_user_by_email(db_path, email)
        if not user:
            return f"❌ User not found: <code>{email}</code>"
        _db.increment_song_credits(db_path, user["id"], delta)
        credits = _db.get_song_credits(db_path, user["id"])
        new_balance = credits["balance"] if credits else "unknown"
        sign = "+" if delta >= 0 else ""
        return f"✅ {sign}{delta} credits → <code>{email}</code>\nNew balance: <b>{new_balance}</b>"
    except Exception as exc:
        return f"❌ Error: {exc}"


# ── Upgrade user ─────────────────────────────────────────────────────────────

def _cmd_upgrade_user(email: str, plan: str) -> str:
    """Upgrade a user to any plan without touching Stripe (admin override)."""
    try:
        import billing as _billing
        import db as _db
        all_plans = {**_billing.PLANS, **_billing.MUSIC_PLANS}
        if plan not in all_plans:
            return f"❌ Unknown plan: <code>{plan}</code>. Valid: {', '.join(sorted(all_plans))}"
        db_path = _db.get_db_path()
        user = _db.get_user_by_email(db_path, email)
        if not user:
            return f"❓ No user found: <code>{email}</code>"
        uid = user["id"]
        _db.update_user(db_path, uid, subscription_plan=plan, subscription_status="active", has_paid=1)
        song_credits = _billing._PLAN_SONG_CREDITS.get(plan, 0)
        if song_credits:
            _db.upsert_song_credits(db_path, uid, balance=song_credits, monthly_allowance=song_credits)
        premium_credits = _billing._PLAN_PREMIUM_CREDITS.get(plan, 0)
        if premium_credits:
            _db.upsert_premium_credits(db_path, uid, balance=premium_credits, monthly_allowance=premium_credits)
        video_credits = _billing._PLAN_VIDEO_CREDITS.get(plan, 0)
        if video_credits:
            try:
                _db.upsert_video_credits(db_path, uid, balance=video_credits, monthly_allowance=video_credits)
            except Exception:
                pass
        plan_name = all_plans[plan].get("name", plan)
        log.info("admin: upgraded user %s to plan %s", email, plan)
        msg = (
            f"✅ <b>{email}</b> → <b>{plan_name}</b>\n"
            f"🎵 Song credits: {song_credits}\n"
            f"⭐ Premium credits: {premium_credits}"
        )
        if video_credits:
            msg += f"\n🎬 Video credits: {video_credits}"
        return msg
    except Exception as exc:
        return f"❌ Error: {exc}"


# ── Recent users ─────────────────────────────────────────────────────────────

def _cmd_recent_users(n: int = 5) -> str:
    try:
        import db as _db
        db_path = _db.get_db_path()
        conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
        conn.row_factory = sqlite3.Row
        try:
            rows = conn.execute(
                """SELECT email, subscription_plan, created_at
                   FROM users ORDER BY created_at DESC LIMIT ?""",
                (n,),
            ).fetchall()
        finally:
            conn.close()
        if not rows:
            return "No users yet 👀"
        lines = [f"👥 <b>Last {n} signups</b>"]
        for r in rows:
            plan = r["subscription_plan"] or "free"
            ts = (r["created_at"] or "")[:16]
            lines.append(f"• {r['email']} — {plan} ({ts})")
        return "\n".join(lines)
    except Exception as exc:
        return f"❌ DB error: {exc}"


# ── Revenue ──────────────────────────────────────────────────────────────────

def _cmd_revenue() -> str:
    try:
        import billing as _billing
        from datetime import datetime, timezone, timedelta
        stripe = _billing._get_stripe()
        now = datetime.now(timezone.utc)
        today_start = int(datetime(now.year, now.month, now.day, tzinfo=timezone.utc).timestamp())
        week_start = int((now - timedelta(days=7)).timestamp())
        month_start = int(datetime(now.year, now.month, 1, tzinfo=timezone.utc).timestamp())

        def _total(since: int) -> float:
            total = 0.0
            charges = stripe.Charge.list(created={"gte": since}, limit=100)
            for ch in charges.auto_paging_iter():
                if ch.get("paid") and not ch.get("refunded"):
                    total += ch["amount"] / 100
            return total

        today_rev = _total(today_start)
        week_rev = _total(week_start)
        month_rev = _total(month_start)
        return (
            f"💰 <b>Revenue</b>\n"
            f"📅 Today: <b>£{today_rev:.2f}</b>\n"
            f"📆 This week: <b>£{week_rev:.2f}</b>\n"
            f"🗓 This month: <b>£{month_rev:.2f}</b>"
        )
    except Exception as exc:
        return f"❌ Stripe error: {exc}"


# ── Top genres ───────────────────────────────────────────────────────────────

def _cmd_top_genres(n: int = 5) -> str:
    try:
        import db as _db
        db_path = _db.get_db_path()
        conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
        conn.row_factory = sqlite3.Row
        try:
            rows = conn.execute(
                """SELECT genre_tag, COUNT(*) AS cnt FROM song_variants
                   WHERE status = 'complete'
                     AND created_at >= datetime('now', '-7 days')
                     AND genre_tag IS NOT NULL AND genre_tag != ''
                   GROUP BY genre_tag ORDER BY cnt DESC LIMIT ?""",
                (n,),
            ).fetchall()
        finally:
            conn.close()
        if not rows:
            return "No completed songs this week yet"
        lines = [f"🎼 <b>Top genres this week</b>"]
        medals = ["🥇", "🥈", "🥉"] + ["🎵"] * 10
        for i, r in enumerate(rows):
            lines.append(f"{medals[i]} {r['genre_tag']}: <b>{r['cnt']}</b>")
        return "\n".join(lines)
    except Exception as exc:
        return f"❌ DB error: {exc}"


# ── Claude Code queue + feature requests ─────────────────────────────────────

_CLAUDE_QUEUE_PATH = os.environ.get("DATA_DIR", "/data") + "/claude_queue.txt"
_FEATURE_LOG_PATH  = os.environ.get("DATA_DIR", "/data") + "/feature_requests.txt"


def _cmd_tell_claude_code(message: str) -> str:
    """Append a message to the Claude Code queue file for Michael to review."""
    try:
        from datetime import datetime, timezone
        ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
        entry = f"[{ts}] {message}\n"
        with open(_CLAUDE_QUEUE_PATH, "a", encoding="utf-8") as f:
            f.write(entry)
        log.info("tell_claude_code: queued message — %s", message[:120])
        return f"✅ Queued for Claude Code review:\n<i>{message[:300]}</i>"
    except Exception as exc:
        return f"❌ Queue write failed: {exc}"


def _cmd_feature_request(description: str) -> str:
    """Log a feature request to the feature requests file."""
    try:
        from datetime import datetime, timezone
        ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
        entry = f"[{ts}] {description}\n"
        with open(_FEATURE_LOG_PATH, "a", encoding="utf-8") as f:
            f.write(entry)
        log.info("feature_request: logged — %s", description[:120])
        return f"📝 Feature logged:\n<i>{description[:300]}</i>"
    except Exception as exc:
        return f"❌ Log write failed: {exc}"


# ── Email helpers ────────────────────────────────────────────────────────────

_EMAIL_HTML_TEMPLATE = """\
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <meta name="color-scheme" content="dark">
  <title>{subject}</title>
</head>
<body style="margin:0;padding:0;background:#0a0a12;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Helvetica,Arial,sans-serif;">
  <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:#0a0a12;padding:40px 16px;">
    <tr><td align="center">
      <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="max-width:580px;">

        <!-- Logo -->
        <tr>
          <td style="text-align:center;padding-bottom:28px;">
            <span style="font-size:26px;font-weight:800;letter-spacing:-0.5px;line-height:1;">
              <span style="color:#00f0ff;">Zeus</span><span style="color:#a78bfa;"> Beats</span>
            </span>
          </td>
        </tr>

        <!-- Card -->
        <tr>
          <td style="background:#0f0f1e;border:1px solid rgba(0,240,255,0.12);border-radius:14px;padding:36px 32px;">

            <!-- Greeting -->
            <p style="margin:0 0 20px;font-size:16px;color:#e2d9f3;line-height:1.6;">Hi there,</p>

            <!-- Body -->
            <div style="font-size:16px;color:#c4b5fd;line-height:1.75;white-space:pre-wrap;">{body}</div>

            <!-- Signature -->
            <p style="margin:28px 0 0;font-size:15px;color:#e2d9f3;line-height:1.6;">
              Talk soon,<br>
              <strong style="color:#00f0ff;">Michael</strong><br>
              <span style="color:#666;font-size:13px;">Zeus Beats</span>
            </p>

          </td>
        </tr>

        <!-- Footer -->
        <tr>
          <td style="padding:24px 0 8px;text-align:center;">
            <p style="margin:0 0 8px;font-size:12px;color:#444;">
              Zeus Beats &middot;
              <a href="https://zeusbeats.com" style="color:#555;text-decoration:none;">zeusbeats.com</a>
            </p>
            <p style="margin:0;font-size:11px;color:#333;">
              You're receiving this because you signed up for Zeus Beats.
              If you'd rather not hear from us,
              <a href="mailto:hello@zeusbeats.com?subject=Unsubscribe" style="color:#444;text-decoration:underline;">unsubscribe here</a>.
            </p>
          </td>
        </tr>

      </table>
    </td></tr>
  </table>
</body>
</html>"""


def _build_plain_text(body: str) -> str:
    return (
        "Hi there,\n\n"
        f"{body}\n\n"
        "Talk soon,\n"
        "Michael\n"
        "Zeus Beats\n\n"
        "---\n"
        "You're receiving this because you signed up for Zeus Beats.\n"
        "To unsubscribe, reply with 'unsubscribe' or email hello@zeusbeats.com"
    )


def _send_one_email(to: str, subject: str, body: str, api_key: str) -> bool:
    html = _EMAIL_HTML_TEMPLATE.format(subject=subject, body=body)
    text = _build_plain_text(body)
    try:
        resp = requests.post(
            "https://api.resend.com/emails",
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json={
                "from": "Zeus Beats <hello@zeusbeats.com>",
                "to": [to],
                "subject": subject,
                "html": html,
                "text": text,
                "reply_to": "hello@zeusbeats.com",
            },
            timeout=15,
        )
        if resp.status_code < 300:
            return True
        log.error("_send_one_email: FAIL to=%s status=%d body=%r", to, resp.status_code, resp.text[:200])
        return False
    except Exception as exc:
        log.exception("_send_one_email: exception to=%s: %s", to, exc)
        return False


def _cmd_email_single(to: str, subject: str, body: str) -> str:
    api_key = os.environ.get("RESEND_API_KEY", "").strip()
    if not api_key:
        return "❌ RESEND_API_KEY not set in Railway variables"
    ok = _send_one_email(to, subject, body, api_key)
    if ok:
        return f"✅ Email sent to <code>{to}</code>"
    return f"❌ Failed to send email to <code>{to}</code> — check Railway logs"


def _cmd_email_bulk(audience: str, subject: str, body: str) -> str:
    """audience: 'all' | 'free' | 'paid'"""
    api_key = os.environ.get("RESEND_API_KEY", "").strip()
    if not api_key:
        return "❌ RESEND_API_KEY not set in Railway variables"

    try:
        import db as _db
        db_path = _db.get_db_path()
        conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
        try:
            if audience == "all":
                rows = conn.execute(
                    "SELECT email FROM users WHERE email IS NOT NULL AND email != ''"
                ).fetchall()
            elif audience == "free":
                rows = conn.execute(
                    """SELECT email FROM users
                       WHERE email IS NOT NULL AND email != ''
                         AND (subscription_status IS NULL OR subscription_status != 'active')"""
                ).fetchall()
            elif audience == "paid":
                rows = conn.execute(
                    """SELECT email FROM users
                       WHERE email IS NOT NULL AND email != ''
                         AND subscription_status = 'active'"""
                ).fetchall()
            else:
                return f"❌ Unknown audience: {audience}"
        finally:
            conn.close()
    except Exception as exc:
        return f"❌ DB error: {exc}"

    emails = [r[0] for r in rows if r[0]]
    if not emails:
        return f"❌ No users found for audience: {audience}"

    sent = 0
    failed = 0
    for i, addr in enumerate(emails):
        if _send_one_email(addr, subject, body, api_key):
            sent += 1
        else:
            failed += 1
            log.warning("email bulk: failed to send to %s", addr)
        if i % 10 == 9:
            time.sleep(1)

    log.info("email bulk: audience=%s sent=%d failed=%d subject=%r", audience, sent, failed, subject[:60])
    result = f"✅ Email sent to {sent} users"
    if failed:
        result += f"\n❌ Failed: {failed} (logged)"
    return result


# ── Refund helpers ───────────────────────────────────────────────────────────

def _cmd_refund_failures() -> str:
    """Refund 1 song credit per song that failed in the last 24h.

    Idempotent: variants with refunded_at set are skipped, so re-running
    after a daily report won't double-refund.
    """
    try:
        import db as _db
        db_path = _db.get_db_path()
        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row
        try:
            rows = conn.execute(
                """SELECT sv.id, sv.user_id, u.email
                   FROM song_variants sv
                   LEFT JOIN users u ON u.id = sv.user_id
                   WHERE sv.status = 'failed'
                     AND sv.created_at >= datetime('now', '-24 hours')
                     AND sv.refunded_at IS NULL"""
            ).fetchall()
        finally:
            conn.close()

        if not rows:
            return "✅ No unrefunded failures in the last 24h"

        per_user: dict[str, int] = {}
        per_user_email: dict[str, str] = {}
        variant_ids: list[int] = []
        for row in rows:
            uid = row["user_id"]
            per_user[uid] = per_user.get(uid, 0) + 1
            per_user_email[uid] = row["email"] or uid
            variant_ids.append(row["id"])

        for uid, count in per_user.items():
            _db.increment_song_credits(db_path, uid, count)

        # Mark refunded so a re-run is a no-op
        conn = sqlite3.connect(str(db_path))
        try:
            placeholders = ",".join("?" for _ in variant_ids)
            conn.execute(
                f"UPDATE song_variants SET refunded_at = datetime('now') "
                f"WHERE id IN ({placeholders})",
                variant_ids,
            )
            conn.commit()
        finally:
            conn.close()

        total_failures = len(variant_ids)
        n_users = len(per_user)
        log.info(
            "refund failures: refunded %d credits to %d users for %d failed songs",
            total_failures, n_users, total_failures,
        )

        detail_lines = [
            f"• <code>{per_user_email[uid]}</code>: +{count}"
            for uid, count in sorted(per_user.items(), key=lambda kv: -kv[1])
        ]
        detail = "\n".join(detail_lines[:20])
        more = f"\n…and {len(detail_lines) - 20} more" if len(detail_lines) > 20 else ""
        return (
            f"✅ Refunded credits to <b>{n_users}</b> user(s) "
            f"for <b>{total_failures}</b> failed song(s)\n{detail}{more}"
        )
    except Exception as exc:
        return f"❌ Refund error: {exc}"


# ── Status ───────────────────────────────────────────────────────────────────

def _cmd_status() -> str:
    try:
        import db as _db
        from datetime import datetime, timezone
        db_path = _db.get_db_path()
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        try:
            user_count = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
            today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
            songs_today = conn.execute(
                "SELECT COUNT(*) FROM song_variants WHERE status='complete' AND DATE(completed_at)=?",
                (today,)
            ).fetchone()[0]
            total_credits = conn.execute("SELECT SUM(balance) FROM song_credits").fetchone()[0] or 0
            pending = conn.execute(
                "SELECT COUNT(*) FROM song_variants WHERE status='pending'"
            ).fetchone()[0]
        finally:
            conn.close()
        return (
            f"📊 <b>Zeus Status</b>\n"
            f"👥 Users: {user_count}\n"
            f"🎵 Songs today: {songs_today}\n"
            f"⏳ Pending jobs: {pending}\n"
            f"💳 Total credits: {total_credits}"
        )
    except Exception as exc:
        return f"❌ Status error: {exc}"


# ── Conversation history ──────────────────────────────────────────────────────

# Last 20 messages (10 user + 10 assistant turns) for per-session context.
_conversation_history: deque = deque(maxlen=20)


# ── AI natural language layer ─────────────────────────────────────────────────

ADMIN_SYSTEM_PROMPT = """\
You are Porick, Michael's right-hand admin assistant for Zeus Beats. You have \
banter and personality — call him "mate", "Michael" or even "dickhead" when he \
makes mistakes (playfully). Be direct, helpful and a bit cheeky. Match the \
casual UK tone Michael uses with you. You're not a corporate bot — you're his \
mate who happens to run Zeus Beats infrastructure.

Your capabilities:
- status — users, songs, pending jobs, credits
- logs — recent app logs
- redeploy — trigger Railway redeploy
- post_channel — post to @zeusbeatsmusic Telegram channel
- email_user — send email to one user
- email_bulk — bulk email (audience: all / free / paid)
- add_credits — give or remove song credits for a user (negative to remove)
- upgrade_user — upgrade user to any plan for free (no Stripe needed)
- verify_email / unverify_email
- user_details — full user lookup by email
- refund_failures — refund song credits for songs that failed in last 24h
- recent_users — last 5 signups
- revenue — today / week / month revenue from Stripe
- top_genres — most popular genres this week
- tell_claude_code — queue a message for Claude Code review
- feature_request — log a feature idea

Respond with ONLY a JSON object — no extra text, no markdown fences.

Action schemas:
{"action": "status"}
{"action": "logs"}
{"action": "redeploy"}
{"action": "post_channel", "message": "..."}
{"action": "email_user", "email": "...", "subject": "...", "body": "..."}
{"action": "email_bulk", "audience": "all|free|paid", "subject": "...", "body": "..."}
{"action": "add_credits", "email": "...", "amount": 10}
{"action": "upgrade_user", "email": "...", "plan": "music_starter|music_pro|music_agency|pro|agency|enterprise"}
{"action": "verify_email", "email": "..."}
{"action": "unverify_email", "email": "..."}
{"action": "user_details", "email": "..."}
{"action": "refund_failures"}
{"action": "recent_users"}
{"action": "revenue"}
{"action": "top_genres"}
{"action": "tell_claude_code", "message": "..."}
{"action": "feature_request", "description": "..."}
{"action": "chat", "message": "..."}

Rules:
- Use "chat" for banter, confirmations, or when you need more info.
- Use conversation history to resolve "him", "her", "that user" etc.
- For post_channel, write the full ready-to-post message with emojis.
- For email actions, write proper subject + body in Zeus Beats brand voice.
- Use negative amounts for add_credits to remove credits.
- For upgrade_user: plan must be one of the exact plan keys listed above.

Examples:
"give laky120@yahoo.com 20 more songs" → {"action": "add_credits", "email": "laky120@yahoo.com", "amount": 20}
"anne is on free, give her music starter" → {"action": "upgrade_user", "email": "cummins.anne@yahoo.co.uk", "plan": "music_starter"}
"how's everything going" → {"action": "status"}
"check the logs" → {"action": "logs"}
"redeploy" → {"action": "redeploy"}
"post on the channel that we have new genres" → {"action": "post_channel", "message": "🎵 New genres just dropped on Zeus Beats!\\n\\nFresh sounds added — go create your next hit now 🚀\\n\\nzeusbeats.com"}
"what's the latest signup" → {"action": "recent_users"}
"refund failed songs today" → {"action": "refund_failures"}
"email all users about the new playlist feature" → {"action": "email_bulk", "audience": "all", "subject": "New: AI Playlist Builder on Zeus Beats 🎵", "body": "We've just launched AI playlists — ask Zeus to build you a playlist from your songs.\\n\\nLog in and try it now!"}
"verify dom@email.com" → {"action": "verify_email", "email": "dom@email.com"}
"what was today's revenue" → {"action": "revenue"}
"tell me about user X" → {"action": "user_details", "email": "X"}
"give him 20 more" → use email from conversation context, then {"action": "add_credits", "email": "...", "amount": 20}
"log a feature: dark mode for the app" → {"action": "feature_request", "description": "Dark mode for the app"}
"tell claude code to fix the stems button on mobile" → {"action": "tell_claude_code", "message": "Fix the stems button on mobile — not tapping properly on small screens"}
"""


def _ai_parse(text: str) -> dict:
    """Call Claude Haiku with conversation history to interpret admin message.
    Returns a parsed action dict; falls back to a chat error on failure.
    """
    raw = ""
    try:
        import anthropic
        client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY", ""))
        messages = list(_conversation_history) + [{"role": "user", "content": text}]
        resp = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=800,
            system=ADMIN_SYSTEM_PROMPT,
            messages=messages,
        )
        raw = resp.content[0].text.strip() if resp.content else ""
        # Strip markdown fences
        raw = re.sub(r'^```[a-z]*\n?', '', raw)
        raw = re.sub(r'\n?```$', '', raw).strip()

        if not raw:
            log.warning("_ai_parse: empty response — stop_reason=%s", getattr(resp, "stop_reason", "?"))
            return {"action": "chat", "message": "Got an empty response, try again mate."}

        # If the JSON object isn't at the start, extract it
        if not raw.startswith('{'):
            start = raw.find('{')
            end = raw.rfind('}')
            if start != -1 and end > start:
                raw = raw[start:end + 1]

        _conversation_history.append({"role": "user", "content": text})
        _conversation_history.append({"role": "assistant", "content": raw})
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        log.warning("_ai_parse: JSON parse error — raw=%r — %s", raw[:300], exc)
        return {"action": "chat", "message": f"❌ Couldn't parse AI response. Raw: {raw[:100]!r}"}
    except Exception as exc:
        log.warning("_ai_parse failed — %s", exc)
        return {"action": "chat", "message": f"❌ AI error: {exc}"}


def _execute_action(action: dict) -> str:
    """Execute a parsed action dict and return a reply string (or sentinel)."""
    act = action.get("action", "chat")

    if act == "status":
        return _cmd_status()

    if act == "logs":
        return _cmd_logs()

    if act == "redeploy":
        return _cmd_redeploy()

    if act == "post_channel":
        msg = action.get("message", "").strip()[:4096]
        if not msg:
            return "❌ No message to post"
        return f"__POST__:{msg}"

    if act == "email_user":
        email = action.get("email", "").strip()
        subject = action.get("subject", "A message from Zeus Beats").strip()
        body = action.get("body", "").strip()
        if not email:
            return "❌ No email address — ask Michael for it"
        return _cmd_email_single(email, subject, body)

    if act == "email_bulk":
        audience = action.get("audience", "all").lower()
        subject = action.get("subject", "A message from Zeus Beats").strip()
        body = action.get("body", "").strip()
        return _cmd_email_bulk(audience, subject, body)

    if act == "add_credits":
        email = action.get("email", "").strip()
        try:
            delta = int(action.get("amount", 0))
        except (ValueError, TypeError):
            return "❌ Invalid credit amount"
        if not email:
            return "❌ No email address — ask Michael for it"
        return _cmd_db_credits(email, delta)

    if act == "verify_email":
        email = action.get("email", "").strip()
        if not email:
            return "❌ No email address"
        return _cmd_db_verify_email(email)

    if act == "unverify_email":
        email = action.get("email", "").strip()
        if not email:
            return "❌ No email address"
        return _cmd_db_unverify_email(email)

    if act == "user_details":
        email = action.get("email", "").strip()
        if not email:
            return "❌ No email address"
        return _cmd_db_user(email)

    if act == "refund_failures":
        return _cmd_refund_failures()

    if act == "upgrade_user":
        email = action.get("email", "").strip()
        plan = action.get("plan", "").strip().lower()
        if not email:
            return "❌ No email address"
        if not plan:
            return "❌ No plan specified"
        return _cmd_upgrade_user(email, plan)

    if act == "recent_users":
        return _cmd_recent_users()

    if act == "revenue":
        return _cmd_revenue()

    if act == "top_genres":
        return _cmd_top_genres()

    if act == "tell_claude_code":
        msg = action.get("message", "").strip()
        if not msg:
            return "❌ No message provided"
        return _cmd_tell_claude_code(msg)

    if act == "feature_request":
        desc = action.get("description", "").strip()
        if not desc:
            return "❌ No description provided"
        return _cmd_feature_request(desc)

    if act == "chat":
        return action.get("message", "👋")

    log.warning("_execute_action: unknown action %r", act)
    return f"❓ Unknown action: {act}"


# ── Public parse entrypoint ──────────────────────────────────────────────────

def parse_and_run(text: str) -> str:
    """Parse admin command text, run it, return a reply string.

    Precision / dangerous commands use exact-match parsing to avoid AI
    misinterpretation (raw SQL, Railway vars, Stripe, post song N).
    Everything else goes through Claude Haiku for natural language handling.

    Special sentinels returned for async actions the caller must handle:
      __POST__:<message>
      __POST_SONG__:<variant_id>
    """
    t = text.strip()
    tl = t.lower()

    if tl == "help":
        return HELP_TEXT

    # ── Precision commands — exact match, bypass AI ───────────────────────────

    # db exec / db query — raw SQL (too dangerous to let AI interpret)
    m = re.match(r'^db\s+exec\s+"(.+)"$', t, re.IGNORECASE | re.DOTALL)
    if m:
        return _cmd_db_exec(m.group(1))

    m = re.match(r'^db\s+query\s+"(.+)"$', t, re.IGNORECASE | re.DOTALL)
    if m:
        return _cmd_db_query(m.group(1))

    # var set/get — Railway env vars (exact key=value required)
    m = re.match(r'^var\s+set\s+(\S+)=(.+)$', t, re.IGNORECASE)
    if m:
        return _cmd_var_set(m.group(1).strip(), m.group(2).strip())

    m = re.match(r'^var\s+get\s+(\S+)$', t, re.IGNORECASE)
    if m:
        return _cmd_var_get(m.group(1).strip())

    # stripe — exact amount parsing
    m = re.match(r'^stripe\s+product\s+"([^"]+)"\s+[£$]?(\d+(?:\.\d+)?)\s*$', t, re.IGNORECASE)
    if m:
        return _cmd_stripe_product(m.group(1), int(round(float(m.group(2)) * 100)))

    if re.match(r'^stripe\s+list$', t, re.IGNORECASE):
        return _cmd_stripe_list()

    # broadcast — email all users; subject and body separated by |
    # Usage: broadcast Subject here | Full message body here
    m = re.match(r'^broadcast\s+(.+?)\s*\|\s*(.+)$', t, re.IGNORECASE | re.DOTALL)
    if m:
        subject = m.group(1).strip()
        body = m.group(2).strip()
        log.info("broadcast: subject=%r body_len=%d", subject[:60], len(body))
        return _cmd_email_bulk("all", subject, body)

    # refund failures — exact command; NL variants go through the AI layer
    if re.match(r'^refund\s+failures?$', t, re.IGNORECASE):
        return _cmd_refund_failures()

    # post song VARIANT_ID — numeric ID must be exact
    m = re.match(r'^post\s+song\s+(\d+)$', t, re.IGNORECASE)
    if m:
        return f"__POST_SONG__:{m.group(1)}"

    # ── Everything else → Claude Haiku natural language ───────────────────────
    log.info("telegram_admin: routing to AI — %r", t[:80])
    action = _ai_parse(t)
    log.info("telegram_admin: AI action=%r", action)
    return _execute_action(action)


# ── Log buffer setup ─────────────────────────────────────────────────────────

class _LogBufferHandler(logging.Handler):
    def emit(self, record: logging.LogRecord) -> None:
        try:
            _log_buffer.append(self.format(record))
        except Exception:
            pass


def install_log_buffer() -> None:
    """Attach ring-buffer handler to root logger. Call once at app startup."""
    handler = _LogBufferHandler()
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s",
                                           datefmt="%H:%M:%S"))
    handler.setLevel(logging.INFO)
    logging.getLogger().addHandler(handler)
    log.info("telegram_admin: log buffer installed")
