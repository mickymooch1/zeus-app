"""
telegram_admin.py — Admin command handler for @porickbot.

Only responds to TELEGRAM_ADMIN_USER_ID. Commands are parsed synchronously;
async actions (Telegram posts) return sentinel strings handled by main.py.
"""
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

HELP_TEXT = """🤖 <b>Zeus Admin Commands</b>

<b>Railway</b>
<code>var set KEY=VALUE</code>
<code>var get KEY</code>
<code>logs</code> — last 20 app log lines
<code>redeploy</code> — trigger a redeploy

<b>Stripe</b>
<code>stripe product "Name" £9.99</code>
<code>stripe list</code>

<b>Database</b>
<code>db user EMAIL</code> — full user details
<code>db query "SELECT ..."</code> — read-only
<code>db exec "UPDATE/INSERT/DELETE ..."</code> — write SQL
<code>db verify EMAIL</code> — mark email as verified
<code>db unverify EMAIL</code> — revoke email verification
<code>db fix youtube EMAIL</code>
<code>db credits EMAIL +10</code>

<b>Email</b>
<code>email USER@EMAIL.COM Subject line | Body text</code>
<code>email all Subject line | Body text</code> — all users
<code>email free Subject line | Body text</code> — free plan
<code>email paid Subject line | Body text</code> — paying subscribers

<b>Telegram</b>
<code>post "message"</code>
<code>post song VARIANT_ID</code>

<b>Other</b>
<code>status</code>
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
                          sc.animation_balance, sc.animation_monthly_allowance
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
            f"🎬 Animation credits: {row['animation_balance']} (allowance: {row['animation_monthly_allowance']})\n"
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


# ── Public parse entrypoint ──────────────────────────────────────────────────

def parse_and_run(text: str) -> str:
    """Parse admin command text, run it, return a reply string.

    Special sentinels returned for async actions the caller must handle:
      __POST__:<message>
      __POST_SONG__:<variant_id>
    """
    t = text.strip()
    tl = t.lower()

    if tl == "help":
        return HELP_TEXT

    if tl == "status":
        return _cmd_status()

    if tl == "logs":
        return _cmd_logs()

    if tl == "redeploy":
        return _cmd_redeploy()

    # var set KEY=VALUE
    m = re.match(r'^var\s+set\s+(\S+)=(.+)$', t, re.IGNORECASE)
    if m:
        return _cmd_var_set(m.group(1).strip(), m.group(2).strip())

    # var get KEY
    m = re.match(r'^var\s+get\s+(\S+)$', t, re.IGNORECASE)
    if m:
        return _cmd_var_get(m.group(1).strip())

    # stripe product "Name" £9.99 or $9.99 or 9.99
    m = re.match(r'^stripe\s+product\s+"([^"]+)"\s+[£$]?(\d+(?:\.\d+)?)\s*$', t, re.IGNORECASE)
    if m:
        amount_pence = int(round(float(m.group(2)) * 100))
        return _cmd_stripe_product(m.group(1), amount_pence)

    if re.match(r'^stripe\s+list$', t, re.IGNORECASE):
        return _cmd_stripe_list()

    # db query "SQL" — read-only SELECT
    m = re.match(r'^db\s+query\s+"(.+)"$', t, re.IGNORECASE | re.DOTALL)
    if m:
        return _cmd_db_query(m.group(1))

    # db exec "SQL" — any write SQL
    m = re.match(r'^db\s+exec\s+"(.+)"$', t, re.IGNORECASE | re.DOTALL)
    if m:
        return _cmd_db_exec(m.group(1))

    # db user EMAIL
    m = re.match(r'^db\s+user\s+(\S+)$', t, re.IGNORECASE)
    if m:
        return _cmd_db_user(m.group(1))

    # db verify EMAIL
    m = re.match(r'^db\s+verify\s+(\S+)$', t, re.IGNORECASE)
    if m:
        return _cmd_db_verify_email(m.group(1))

    # db unverify EMAIL
    m = re.match(r'^db\s+unverify\s+(\S+)$', t, re.IGNORECASE)
    if m:
        return _cmd_db_unverify_email(m.group(1))

    # db fix youtube EMAIL
    m = re.match(r'^db\s+fix\s+youtube\s+(\S+)$', t, re.IGNORECASE)
    if m:
        return _cmd_db_fix_youtube(m.group(1))

    # db credits EMAIL +/-N  or  db credits EMAIL N
    m = re.match(r'^db\s+credits\s+(\S+)\s+([+-]?\d+)$', t, re.IGNORECASE)
    if m:
        try:
            delta = int(m.group(2))
        except ValueError:
            return "❌ Invalid credit amount"
        return _cmd_db_credits(m.group(1), delta)

    # email USER@EMAIL.COM Subject | Body
    # email all/free/paid Subject | Body
    m = re.match(r'^email\s+(\S+)\s+(.+)$', t, re.IGNORECASE | re.DOTALL)
    if m:
        target = m.group(1).strip()
        message = m.group(2).strip()
        # Split on first " | " to get subject and body
        if " | " in message:
            subject_part, body_part = message.split(" | ", 1)
        else:
            subject_part = "A message from Zeus Beats"
            body_part = message
        subject_part = subject_part.strip()
        body_part = body_part.strip()
        if target.lower() in ("all", "free", "paid"):
            return _cmd_email_bulk(target.lower(), subject_part, body_part)
        return _cmd_email_single(target, subject_part, body_part)

    # post "message" — caller handles the async Telegram send
    m = re.match(r'^post\s+"(.+)"$', t, re.IGNORECASE | re.DOTALL)
    if m:
        return f"__POST__:{m.group(1)}"

    # post song VARIANT_ID
    m = re.match(r'^post\s+song\s+(\d+)$', t, re.IGNORECASE)
    if m:
        return f"__POST_SONG__:{m.group(1)}"

    # Unknown admin command — do NOT fall through to Claude AI
    log.warning("telegram_admin: unrecognised command: %r", t[:100])
    return f"❓ Unknown command: <code>{t[:80]}</code>\n\nType <code>help</code> for available commands."


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
