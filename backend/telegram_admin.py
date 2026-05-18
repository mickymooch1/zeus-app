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
<code>db query "SELECT ..."</code>
<code>db fix youtube EMAIL</code>
<code>db credits EMAIL +10</code>

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
    if not sql.strip().upper().startswith("SELECT"):
        return "❌ Only SELECT queries allowed"
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

    # db query "SQL" (allow multi-word SQL inside quotes)
    m = re.match(r'^db\s+query\s+"(.+)"$', t, re.IGNORECASE | re.DOTALL)
    if m:
        return _cmd_db_query(m.group(1))

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

    # post "message" — caller handles the async Telegram send
    m = re.match(r'^post\s+"(.+)"$', t, re.IGNORECASE | re.DOTALL)
    if m:
        return f"__POST__:{m.group(1)}"

    # post song VARIANT_ID
    m = re.match(r'^post\s+song\s+(\d+)$', t, re.IGNORECASE)
    if m:
        return f"__POST_SONG__:{m.group(1)}"

    return f"❓ Unknown command. Type <code>help</code> for the full list."


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
