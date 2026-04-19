"""
db.py — User database module for Zeus SaaS platform.
Uses the SAME SQLite file as HistoryStore (zeus_agent.py).
Path priority: ZEUS_DATA_DIR → /data (Railway) → ~/.zeus (local)
"""
import os
import pathlib
import sqlite3
import uuid
from datetime import datetime, timezone


def _safe_home() -> pathlib.Path:
    try:
        return pathlib.Path.home()
    except Exception:
        return pathlib.Path("/tmp")


_db_initialised = False


def get_db_path() -> pathlib.Path:
    """Return path to zeus.db and ensure user tables exist."""
    global _db_initialised
    _railway = bool(
        os.environ.get("RAILWAY_ENVIRONMENT") or os.environ.get("RAILWAY_PROJECT_ID")
    )
    default = (
        os.environ.get("ZEUS_DATA_DIR")
        or ("/data" if _railway else str(_safe_home() / ".zeus"))
    )
    data_dir = pathlib.Path(default)
    data_dir.mkdir(parents=True, exist_ok=True)
    path = data_dir / "zeus.db"
    if not _db_initialised:
        init_user_tables(path)
        _db_initialised = True
    return path


def get_db_path_dep() -> pathlib.Path:
    """FastAPI dependency wrapper for get_db_path."""
    return get_db_path()


def _conn(db_path: pathlib.Path):
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def init_user_tables(db_path: pathlib.Path) -> None:
    """Create users, monthly_usage, tasks, and scheduled_tasks tables if they don't exist."""
    conn = _conn(db_path)
    try:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS users (
                id                  TEXT PRIMARY KEY,
                email               TEXT UNIQUE NOT NULL,
                password_hash       TEXT NOT NULL,
                name                TEXT,
                stripe_customer_id  TEXT,
                subscription_status TEXT DEFAULT 'free',
                subscription_plan   TEXT,
                subscription_id     TEXT,
                tc_accepted_at      TEXT,
                is_admin            INTEGER NOT NULL DEFAULT 0,
                created_at          TEXT NOT NULL,
                updated_at          TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS monthly_usage (
                user_id     TEXT NOT NULL,
                month       TEXT NOT NULL,
                messages    INTEGER NOT NULL DEFAULT 0,
                builds      INTEGER NOT NULL DEFAULT 0,
                PRIMARY KEY (user_id, month)
            );

            CREATE TABLE IF NOT EXISTS tasks (
                id           TEXT PRIMARY KEY,
                user_id      TEXT NOT NULL,
                description  TEXT NOT NULL,
                status       TEXT NOT NULL DEFAULT 'pending',
                result       TEXT,
                live_url     TEXT,
                created_at   TEXT NOT NULL,
                completed_at TEXT
            );
            CREATE INDEX IF NOT EXISTS idx_tasks_user ON tasks (user_id);

            CREATE TABLE IF NOT EXISTS scheduled_tasks (
                id               TEXT PRIMARY KEY,
                user_id          TEXT NOT NULL,
                task_description TEXT NOT NULL,
                cron_expression  TEXT NOT NULL,
                schedule_label   TEXT NOT NULL,
                timezone         TEXT NOT NULL DEFAULT 'UTC',
                is_active        INTEGER NOT NULL DEFAULT 1,
                last_run         TEXT,
                next_run         TEXT NOT NULL,
                created_at       TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_scheduled_tasks_user
                ON scheduled_tasks (user_id);

            CREATE TABLE IF NOT EXISTS websites (
                id                TEXT PRIMARY KEY,
                user_id           TEXT NOT NULL,
                netlify_site_id   TEXT NOT NULL,
                netlify_site_name TEXT NOT NULL,
                site_url          TEXT NOT NULL,
                client_name       TEXT,
                files_json        TEXT,
                created_at        TEXT NOT NULL,
                updated_at        TEXT NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users(id)
            );
            CREATE INDEX IF NOT EXISTS idx_websites_user ON websites (user_id);
        """)
        # Migrate existing tables — ignore error if column already exists
        for _migration in [
            "ALTER TABLE users ADD COLUMN is_admin INTEGER NOT NULL DEFAULT 0",
            "ALTER TABLE monthly_usage ADD COLUMN builds INTEGER NOT NULL DEFAULT 0",
        ]:
            try:
                conn.execute(_migration)
                conn.commit()
            except Exception:
                pass
    finally:
        conn.close()


def _row_to_dict(row) -> dict:
    return dict(row) if row else None


def create_user(
    db_path: pathlib.Path,
    email: str,
    password_hash: str,
    name: str,
    tc_accepted_at: str,
) -> dict:
    """Insert a new user and return the user dict."""
    now = datetime.now(timezone.utc).isoformat()
    user_id = str(uuid.uuid4())
    conn = _conn(db_path)
    try:
        conn.execute(
            """
            INSERT INTO users (id, email, password_hash, name, subscription_status,
                               tc_accepted_at, created_at, updated_at)
            VALUES (?, ?, ?, ?, 'free', ?, ?, ?)
            """,
            (user_id, email.lower().strip(), password_hash, name, tc_accepted_at, now, now),
        )
        conn.commit()
        return get_user_by_id(db_path, user_id)
    finally:
        conn.close()


def get_user_by_email(db_path: pathlib.Path, email: str) -> dict | None:
    """Look up a user by email (case-insensitive)."""
    conn = _conn(db_path)
    try:
        row = conn.execute(
            "SELECT * FROM users WHERE lower(email) = lower(?)", (email.strip(),)
        ).fetchone()
        return _row_to_dict(row)
    finally:
        conn.close()


def get_user_by_id(db_path: pathlib.Path, user_id: str) -> dict | None:
    """Look up a user by ID."""
    conn = _conn(db_path)
    try:
        row = conn.execute(
            "SELECT * FROM users WHERE id = ?", (user_id,)
        ).fetchone()
        return _row_to_dict(row)
    finally:
        conn.close()


def update_user_by_email(db_path: pathlib.Path, email: str, **fields) -> bool:
    """Update one or more columns for a user looked up by email. Returns True if found."""
    if not fields:
        return False
    now = datetime.now(timezone.utc).isoformat()
    fields["updated_at"] = now
    set_clause = ", ".join(f"{k} = ?" for k in fields)
    values = list(fields.values()) + [email.lower().strip()]
    conn = _conn(db_path)
    try:
        cur = conn.execute(
            f"UPDATE users SET {set_clause} WHERE lower(email) = ?", values
        )
        conn.commit()
        return cur.rowcount > 0
    finally:
        conn.close()


def update_user(db_path: pathlib.Path, user_id: str, **fields) -> None:
    """Update one or more columns on a user row."""
    if not fields:
        return
    now = datetime.now(timezone.utc).isoformat()
    fields["updated_at"] = now
    set_clause = ", ".join(f"{k} = ?" for k in fields)
    values = list(fields.values()) + [user_id]
    conn = _conn(db_path)
    try:
        conn.execute(
            f"UPDATE users SET {set_clause} WHERE id = ?", values
        )
        conn.commit()
    finally:
        conn.close()


def get_monthly_usage(db_path: pathlib.Path, user_id: str, month: str) -> int:
    """Return message count for user in given month (YYYY-MM)."""
    conn = _conn(db_path)
    try:
        row = conn.execute(
            "SELECT messages FROM monthly_usage WHERE user_id = ? AND month = ?",
            (user_id, month),
        ).fetchone()
        return row["messages"] if row else 0
    finally:
        conn.close()


def increment_usage(db_path: pathlib.Path, user_id: str, month: str) -> None:
    """Upsert monthly_usage, incrementing messages by 1."""
    conn = _conn(db_path)
    try:
        conn.execute(
            """
            INSERT INTO monthly_usage (user_id, month, messages)
            VALUES (?, ?, 1)
            ON CONFLICT(user_id, month) DO UPDATE SET messages = messages + 1
            """,
            (user_id, month),
        )
        conn.commit()
    finally:
        conn.close()


def reset_monthly_usage(db_path: pathlib.Path, user_id: str) -> None:
    """Delete all monthly usage records for a user (e.g. on subscription downgrade)."""
    conn = _conn(db_path)
    try:
        conn.execute("DELETE FROM monthly_usage WHERE user_id = ?", (user_id,))
        conn.commit()
    finally:
        conn.close()


def get_monthly_builds(db_path: pathlib.Path, user_id: str, month: str) -> int:
    """Return build count for user in given month (YYYY-MM)."""
    conn = _conn(db_path)
    try:
        row = conn.execute(
            "SELECT builds FROM monthly_usage WHERE user_id = ? AND month = ?",
            (user_id, month),
        ).fetchone()
        return row["builds"] if row else 0
    finally:
        conn.close()


def increment_builds_count(db_path: pathlib.Path, user_id: str, month: str) -> None:
    """Upsert monthly_usage, incrementing builds by 1."""
    conn = _conn(db_path)
    try:
        conn.execute(
            """
            INSERT INTO monthly_usage (user_id, month, messages, builds)
            VALUES (?, ?, 0, 1)
            ON CONFLICT(user_id, month) DO UPDATE SET builds = builds + 1
            """,
            (user_id, month),
        )
        conn.commit()
    finally:
        conn.close()


# ── Background task CRUD ──────────────────────────────────────────────────────

def create_task(db_path: pathlib.Path, user_id: str, description: str) -> dict:
    """Insert a new pending task and return the row as a dict."""
    now = datetime.now(timezone.utc).isoformat()
    task_id = str(uuid.uuid4())
    conn = _conn(db_path)
    try:
        conn.execute(
            """
            INSERT INTO tasks (id, user_id, description, status, created_at)
            VALUES (?, ?, ?, 'pending', ?)
            """,
            (task_id, user_id, description, now),
        )
        conn.commit()
        return get_task(db_path, task_id)
    finally:
        conn.close()


def update_task(db_path: pathlib.Path, task_id: str, **fields) -> None:
    """Update one or more columns on a task row."""
    if not fields:
        return
    set_clause = ", ".join(f"{k} = ?" for k in fields)
    values = list(fields.values()) + [task_id]
    conn = _conn(db_path)
    try:
        conn.execute(f"UPDATE tasks SET {set_clause} WHERE id = ?", values)
        conn.commit()
    finally:
        conn.close()


def get_task(db_path: pathlib.Path, task_id: str) -> dict | None:
    """Fetch a single task by ID."""
    conn = _conn(db_path)
    try:
        row = conn.execute(
            "SELECT * FROM tasks WHERE id = ?", (task_id,)
        ).fetchone()
        return _row_to_dict(row)
    finally:
        conn.close()


def get_tasks_for_user(db_path: pathlib.Path, user_id: str) -> list:
    """Return all tasks for a user, newest first."""
    conn = _conn(db_path)
    try:
        rows = conn.execute(
            "SELECT * FROM tasks WHERE user_id = ? ORDER BY created_at DESC",
            (user_id,),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def get_all_tasks(db_path: pathlib.Path, limit: int = 500) -> list:
    """Return all tasks across all users, joined with user email, newest first."""
    conn = _conn(db_path)
    try:
        rows = conn.execute(
            """
            SELECT t.id, t.user_id, t.description, t.status,
                   t.created_at, t.completed_at,
                   u.email AS user_email
            FROM tasks t
            LEFT JOIN users u ON t.user_id = u.id
            ORDER BY t.created_at DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def delete_task(db_path: pathlib.Path, task_id: str, user_id: str) -> bool:
    """Delete a task. Returns True if a row was deleted, False if not found."""
    conn = _conn(db_path)
    try:
        cur = conn.execute(
            "DELETE FROM tasks WHERE id = ? AND user_id = ?",
            (task_id, user_id),
        )
        conn.commit()
        return cur.rowcount > 0
    finally:
        conn.close()


def fail_stale_tasks(db_path: pathlib.Path) -> None:
    """Mark any 'running' tasks as 'failed' — called at startup after a restart."""
    now = datetime.now(timezone.utc).isoformat()
    conn = _conn(db_path)
    try:
        conn.execute(
            "UPDATE tasks SET status = 'failed', completed_at = ? WHERE status = 'running'",
            (now,),
        )
        conn.commit()
    finally:
        conn.close()


def get_all_users(db_path: pathlib.Path) -> list:
    """Return all users ordered by creation date descending."""
    import logging as _logging
    _log = _logging.getLogger("zeus.db")
    _log.info("get_all_users: db_path=%s (exists=%s)", db_path, db_path.exists())
    conn = _conn(db_path)
    try:
        rows = conn.execute(
            "SELECT * FROM users ORDER BY created_at DESC"
        ).fetchall()
        result = [dict(r) for r in rows]
        _log.info("get_all_users: returned %d user(s)", len(result))
        return result
    finally:
        conn.close()


# ── Scheduled Tasks ─────────────────────────────────────────────────────────


def create_scheduled_task(
    db_path: pathlib.Path,
    user_id: str,
    task_description: str,
    cron_expression: str,
    schedule_label: str,
    next_run: str,
    tz: str = "UTC",
) -> dict:
    """Insert a new scheduled task and return the created row."""
    now = datetime.now(timezone.utc).isoformat()
    task_id = str(uuid.uuid4())
    conn = _conn(db_path)
    try:
        conn.execute(
            """
            INSERT INTO scheduled_tasks
                (id, user_id, task_description, cron_expression, schedule_label,
                 timezone, is_active, last_run, next_run, created_at)
            VALUES (?, ?, ?, ?, ?, ?, 1, NULL, ?, ?)
            """,
            (task_id, user_id, task_description, cron_expression, schedule_label,
             tz, next_run, now),
        )
        conn.commit()
        return get_scheduled_task(db_path, task_id)
    finally:
        conn.close()


def get_scheduled_tasks_for_user(db_path: pathlib.Path, user_id: str) -> list[dict]:
    """Return all scheduled tasks for a user, most recent first."""
    conn = _conn(db_path)
    try:
        rows = conn.execute(
            "SELECT * FROM scheduled_tasks WHERE user_id = ? ORDER BY created_at DESC",
            (user_id,),
        ).fetchall()
        return [_row_to_dict(r) for r in rows]
    finally:
        conn.close()


def get_all_active_scheduled_tasks(db_path: pathlib.Path) -> list[dict]:
    """Return all rows where is_active = 1 — used by scheduler on startup."""
    conn = _conn(db_path)
    try:
        rows = conn.execute(
            "SELECT * FROM scheduled_tasks WHERE is_active = 1"
        ).fetchall()
        return [_row_to_dict(r) for r in rows]
    finally:
        conn.close()


def get_scheduled_task(db_path: pathlib.Path, task_id: str) -> dict | None:
    """Return a single scheduled task by ID."""
    conn = _conn(db_path)
    try:
        row = conn.execute(
            "SELECT * FROM scheduled_tasks WHERE id = ?", (task_id,)
        ).fetchone()
        return _row_to_dict(row)
    finally:
        conn.close()


def update_scheduled_task(db_path: pathlib.Path, task_id: str, **fields) -> None:
    """Update arbitrary columns on a scheduled task row."""
    if not fields:
        return
    set_clause = ", ".join(f"{k} = ?" for k in fields)
    values = list(fields.values()) + [task_id]
    conn = _conn(db_path)
    try:
        conn.execute(
            f"UPDATE scheduled_tasks SET {set_clause} WHERE id = ?", values
        )
        conn.commit()
    finally:
        conn.close()


def delete_scheduled_task(db_path: pathlib.Path, task_id: str, user_id: str) -> bool:
    """Delete a scheduled task owned by user_id. Returns True if deleted."""
    conn = _conn(db_path)
    try:
        cur = conn.execute(
            "DELETE FROM scheduled_tasks WHERE id = ? AND user_id = ?",
            (task_id, user_id),
        )
        conn.commit()
        return cur.rowcount > 0
    finally:
        conn.close()


def count_active_scheduled_tasks(db_path: pathlib.Path, user_id: str) -> int:
    """Count is_active = 1 rows for user — used for plan limit check."""
    conn = _conn(db_path)
    try:
        row = conn.execute(
            "SELECT COUNT(*) AS cnt FROM scheduled_tasks WHERE user_id = ? AND is_active = 1",
            (user_id,),
        ).fetchone()
        return row["cnt"] if row else 0
    finally:
        conn.close()


# ── Website CRUD ──────────────────────────────────────────────────────────────

def create_website(
    db_path: pathlib.Path,
    user_id: str,
    netlify_site_id: str,
    netlify_site_name: str,
    site_url: str,
    client_name: str | None,
    files_json: str | None,
) -> dict:
    """Insert a new website record and return it as a dict."""
    now = datetime.now(timezone.utc).isoformat()
    website_id = str(uuid.uuid4())
    conn = _conn(db_path)
    try:
        conn.execute(
            """
            INSERT INTO websites
                (id, user_id, netlify_site_id, netlify_site_name, site_url,
                 client_name, files_json, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (website_id, user_id, netlify_site_id, netlify_site_name, site_url,
             client_name, files_json, now, now),
        )
        conn.commit()
        return get_website_by_id(db_path, website_id, user_id)
    finally:
        conn.close()


def get_websites_for_user(db_path: pathlib.Path, user_id: str) -> list[dict]:
    """Return all website records for a user, newest first."""
    conn = _conn(db_path)
    try:
        rows = conn.execute(
            "SELECT * FROM websites WHERE user_id = ? ORDER BY updated_at DESC",
            (user_id,),
        ).fetchall()
        return [_row_to_dict(r) for r in rows]
    finally:
        conn.close()


def get_website_by_id(
    db_path: pathlib.Path, website_id: str, user_id: str
) -> dict | None:
    """Return a website record only if it belongs to user_id."""
    conn = _conn(db_path)
    try:
        row = conn.execute(
            "SELECT * FROM websites WHERE id = ? AND user_id = ?",
            (website_id, user_id),
        ).fetchone()
        return _row_to_dict(row)
    finally:
        conn.close()


def get_website_by_netlify_id(
    db_path: pathlib.Path, netlify_site_id: str, user_id: str
) -> dict | None:
    """Return a website record by its Netlify site ID for a given user."""
    conn = _conn(db_path)
    try:
        row = conn.execute(
            "SELECT * FROM websites WHERE netlify_site_id = ? AND user_id = ?",
            (netlify_site_id, user_id),
        ).fetchone()
        return _row_to_dict(row)
    finally:
        conn.close()


def update_website(db_path: pathlib.Path, website_id: str, **fields) -> bool:
    """Update one or more columns on a website row. Returns True if found."""
    if not fields:
        return False
    now = datetime.now(timezone.utc).isoformat()
    fields["updated_at"] = now
    set_clause = ", ".join(f"{k} = ?" for k in fields)
    values = list(fields.values()) + [website_id]
    conn = _conn(db_path)
    try:
        cur = conn.execute(
            f"UPDATE websites SET {set_clause} WHERE id = ?", values
        )
        conn.commit()
        return cur.rowcount > 0
    finally:
        conn.close()


def delete_website(db_path: pathlib.Path, website_id: str, user_id: str) -> bool:
    """Delete a website record. Returns True if deleted, False if not found."""
    conn = _conn(db_path)
    try:
        cur = conn.execute(
            "DELETE FROM websites WHERE id = ? AND user_id = ?",
            (website_id, user_id),
        )
        conn.commit()
        return cur.rowcount > 0
    finally:
        conn.close()


def count_websites_for_user(db_path: pathlib.Path, user_id: str) -> int:
    """Return how many website records a user has."""
    conn = _conn(db_path)
    try:
        row = conn.execute(
            "SELECT COUNT(*) as n FROM websites WHERE user_id = ?", (user_id,)
        ).fetchone()
        return row["n"] if row else 0
    finally:
        conn.close()
