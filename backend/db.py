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


def get_db_path() -> pathlib.Path:
    """Return path to zeus.db — same logic as HistoryStore in zeus_agent.py."""
    _railway = bool(
        os.environ.get("RAILWAY_ENVIRONMENT") or os.environ.get("RAILWAY_PROJECT_ID")
    )
    default = (
        os.environ.get("ZEUS_DATA_DIR")
        or ("/data" if _railway else str(_safe_home() / ".zeus"))
    )
    data_dir = pathlib.Path(default)
    data_dir.mkdir(parents=True, exist_ok=True)
    return data_dir / "zeus.db"


def get_db_path_dep() -> pathlib.Path:
    """FastAPI dependency wrapper for get_db_path."""
    return get_db_path()


def _conn(db_path: pathlib.Path):
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def init_user_tables(db_path: pathlib.Path) -> None:
    """Create users and monthly_usage tables if they don't exist."""
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
                created_at          TEXT NOT NULL,
                updated_at          TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS monthly_usage (
                user_id     TEXT NOT NULL,
                month       TEXT NOT NULL,
                messages    INTEGER DEFAULT 0,
                PRIMARY KEY (user_id, month)
            );
        """)
        conn.commit()
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
