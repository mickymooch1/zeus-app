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

            CREATE TABLE IF NOT EXISTS lyrics (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id    TEXT NOT NULL,
                brief      TEXT NOT NULL,
                lyrics_text TEXT NOT NULL,
                title      TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id)
            );

            CREATE TABLE IF NOT EXISTS song_variants (
                id               INTEGER PRIMARY KEY AUTOINCREMENT,
                lyric_id         INTEGER NOT NULL,
                user_id          TEXT NOT NULL,
                style_prompt     TEXT NOT NULL,
                genre_tag        TEXT,
                provider_job_id  TEXT,
                status           TEXT DEFAULT 'pending',
                mp3_url          TEXT,
                image_url        TEXT,
                duration_seconds INTEGER,
                take_number      INTEGER DEFAULT 1,
                webhook_secret   TEXT,
                created_at       TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                completed_at     TIMESTAMP,
                FOREIGN KEY (lyric_id) REFERENCES lyrics(id),
                FOREIGN KEY (user_id) REFERENCES users(id)
            );

            CREATE TABLE IF NOT EXISTS song_credits (
                user_id           TEXT PRIMARY KEY,
                balance           INTEGER NOT NULL DEFAULT 0,
                monthly_allowance INTEGER NOT NULL DEFAULT 0,
                last_reset        TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id)
            );

            CREATE TABLE IF NOT EXISTS video_credits (
                user_id           TEXT PRIMARY KEY,
                balance           INTEGER NOT NULL DEFAULT 0,
                monthly_allowance INTEGER NOT NULL DEFAULT 0,
                last_reset        TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id)
            );

            CREATE INDEX IF NOT EXISTS idx_song_variants_status ON song_variants(status);
            CREATE INDEX IF NOT EXISTS idx_song_variants_lyric  ON song_variants(lyric_id);

            CREATE TABLE IF NOT EXISTS fal_image_jobs (
                job_id         TEXT PRIMARY KEY,
                fal_request_id TEXT NOT NULL,
                image_url      TEXT,
                created_at     TEXT DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS message_usage (
                user_id TEXT NOT NULL,
                date    TEXT NOT NULL,
                count   INTEGER NOT NULL DEFAULT 0,
                PRIMARY KEY (user_id, date)
            );

            CREATE TABLE IF NOT EXISTS deletion_requests (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id      TEXT NOT NULL,
                email        TEXT NOT NULL,
                requested_at TEXT NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users(id)
            );
            CREATE INDEX IF NOT EXISTS idx_deletion_requests_user ON deletion_requests (user_id);

            CREATE TABLE IF NOT EXISTS password_reset_tokens (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id    TEXT NOT NULL,
                token      TEXT NOT NULL UNIQUE,
                expires_at TEXT NOT NULL,
                used       INTEGER NOT NULL DEFAULT 0,
                FOREIGN KEY (user_id) REFERENCES users(id)
            );
            CREATE INDEX IF NOT EXISTS idx_prt_token ON password_reset_tokens (token);

            CREATE TABLE IF NOT EXISTS email_verification_tokens (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id    TEXT NOT NULL,
                token      TEXT NOT NULL UNIQUE,
                expires_at TEXT NOT NULL,
                used       INTEGER NOT NULL DEFAULT 0,
                FOREIGN KEY (user_id) REFERENCES users(id)
            );
            CREATE INDEX IF NOT EXISTS idx_evt_token ON email_verification_tokens (token);

            CREATE TABLE IF NOT EXISTS registration_attempts (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                ip_address   TEXT NOT NULL,
                attempted_at TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_reg_attempts_ip
                ON registration_attempts (ip_address, attempted_at);
        """)
        # Migrate existing tables — ignore error if column already exists
        for _migration in [
            "ALTER TABLE users ADD COLUMN is_admin INTEGER NOT NULL DEFAULT 0",
            "ALTER TABLE monthly_usage ADD COLUMN builds INTEGER NOT NULL DEFAULT 0",
            "ALTER TABLE song_variants ADD COLUMN take_number INTEGER DEFAULT 1",
            "ALTER TABLE song_variants ADD COLUMN webhook_secret TEXT",
            "ALTER TABLE song_variants ADD COLUMN image_url TEXT",
            "ALTER TABLE users ADD COLUMN youtube_refresh_token TEXT",
            "ALTER TABLE song_variants ADD COLUMN youtube_url TEXT",
            "ALTER TABLE song_variants ADD COLUMN did_job_id TEXT",
            "ALTER TABLE song_variants ADD COLUMN video_url TEXT",
            "ALTER TABLE fal_image_jobs ADD COLUMN image_url TEXT",
            "ALTER TABLE song_variants ADD COLUMN kling_request_id TEXT",
            "ALTER TABLE song_variants ADD COLUMN music_video_url TEXT",
            "ALTER TABLE users ADD COLUMN cancel_at TEXT",
            "ALTER TABLE users ADD COLUMN email_verified INTEGER NOT NULL DEFAULT 0",
            "ALTER TABLE users ADD COLUMN artist_name TEXT",
            "ALTER TABLE song_variants ADD COLUMN is_favourite INTEGER NOT NULL DEFAULT 0",
        ]:
            try:
                conn.execute(_migration)
                conn.commit()
            except Exception:
                pass
    finally:
        conn.close()


def check_and_record_registration_attempt(db_path: pathlib.Path, ip_address: str) -> bool:
    """Return True (allowed) if fewer than 3 registrations from this IP in the last 24 h.
    Records the attempt when allowed; returns False when the limit is reached."""
    from datetime import datetime, timedelta, timezone
    cutoff = (datetime.now(timezone.utc) - timedelta(hours=24)).isoformat()
    conn = _conn(db_path)
    try:
        row = conn.execute(
            "SELECT COUNT(*) FROM registration_attempts WHERE ip_address = ? AND attempted_at > ?",
            (ip_address, cutoff),
        ).fetchone()
        if row[0] >= 3:
            return False
        conn.execute(
            "INSERT INTO registration_attempts (ip_address, attempted_at) VALUES (?, ?)",
            (ip_address, datetime.now(timezone.utc).isoformat()),
        )
        conn.commit()
        return True
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


# ── Song credits CRUD ─────────────────────────────────────────────────────────

def get_song_credits(db_path: pathlib.Path, user_id: str) -> dict | None:
    conn = _conn(db_path)
    try:
        row = conn.execute(
            "SELECT * FROM song_credits WHERE user_id = ?", (user_id,)
        ).fetchone()
        return _row_to_dict(row)
    finally:
        conn.close()


def get_song_stats_for_admin(db_path: pathlib.Path, month_start: str) -> dict:
    """Return per-user song stats for the admin dashboard.

    Returns a dict keyed by user_id:
        total_songs, songs_this_month, last_song_at, credits_remaining
    month_start should be 'YYYY-MM-01' (ISO date string).
    """
    conn = _conn(db_path)
    try:
        variant_rows = conn.execute(
            """
            SELECT
                user_id,
                COUNT(*)                                                  AS total_songs,
                SUM(CASE WHEN created_at >= ? THEN 1 ELSE 0 END)         AS songs_this_month,
                MAX(created_at)                                           AS last_song_at
            FROM song_variants
            GROUP BY user_id
            """,
            (month_start,),
        ).fetchall()
        stats: dict = {r["user_id"]: {
            "total_songs":      r["total_songs"],
            "songs_this_month": r["songs_this_month"] or 0,
            "last_song_at":     r["last_song_at"],
            "credits_remaining": 0,
        } for r in variant_rows}

        credit_rows = conn.execute(
            "SELECT user_id, balance FROM song_credits"
        ).fetchall()
        for cr in credit_rows:
            uid = cr["user_id"]
            if uid in stats:
                stats[uid]["credits_remaining"] = cr["balance"]
            else:
                stats[uid] = {
                    "total_songs": 0, "songs_this_month": 0,
                    "last_song_at": None, "credits_remaining": cr["balance"],
                }
        return stats
    finally:
        conn.close()


def upsert_song_credits(
    db_path: pathlib.Path,
    user_id: str,
    balance: int,
    monthly_allowance: int,
) -> None:
    conn = _conn(db_path)
    try:
        conn.execute(
            """INSERT INTO song_credits (user_id, balance, monthly_allowance, last_reset)
               VALUES (?, ?, ?, CURRENT_TIMESTAMP)
               ON CONFLICT(user_id) DO UPDATE SET
                   balance = ?,
                   monthly_allowance = ?,
                   last_reset = CURRENT_TIMESTAMP""",
            (user_id, balance, monthly_allowance, balance, monthly_allowance),
        )
        conn.commit()
    finally:
        conn.close()


def ensure_free_song_credits(db_path: pathlib.Path, user_id: str, balance: int = 5, monthly_allowance: int = 5) -> dict:
    """Create a song_credits record if one doesn't exist yet. Returns the (possibly new) row."""
    conn = _conn(db_path)
    try:
        conn.execute(
            """INSERT OR IGNORE INTO song_credits (user_id, balance, monthly_allowance, last_reset)
               VALUES (?, ?, ?, CURRENT_TIMESTAMP)""",
            (user_id, balance, monthly_allowance),
        )
        conn.commit()
        row = conn.execute("SELECT * FROM song_credits WHERE user_id = ?", (user_id,)).fetchone()
        return _row_to_dict(row)
    finally:
        conn.close()


def reset_free_tier_song_credits(db_path: pathlib.Path, free_credits: int = 5) -> int:
    """
    Reset song credit balance to free_credits for any free-tier user whose
    last_reset is over 28 days ago (or NULL). Returns the number of users reset.
    """
    conn = _conn(db_path)
    try:
        cur = conn.execute(
            """UPDATE song_credits
               SET balance = ?, last_reset = CURRENT_TIMESTAMP
               WHERE user_id IN (
                   SELECT sc.user_id FROM song_credits sc
                   JOIN users u ON u.id = sc.user_id
                   WHERE (u.subscription_status IS NULL OR u.subscription_status = 'free')
                     AND (sc.last_reset IS NULL
                          OR julianday('now') - julianday(sc.last_reset) >= 28)
               )""",
            (free_credits,),
        )
        conn.commit()
        return cur.rowcount
    finally:
        conn.close()


def backfill_missing_song_credits(db_path: pathlib.Path, plan_credits: dict, free_credits: int = 5) -> int:
    """
    One-time migration: create song_credits rows for any user who doesn't have one.
    Paid users get their plan's allowance; free users get free_credits.
    Returns count of rows created.
    """
    conn = _conn(db_path)
    try:
        users = conn.execute(
            """SELECT u.id, u.subscription_plan, u.subscription_status
               FROM users u
               LEFT JOIN song_credits sc ON sc.user_id = u.id
               WHERE sc.user_id IS NULL"""
        ).fetchall()
        count = 0
        for row in users:
            plan = row["subscription_plan"]
            status = row["subscription_status"]
            if status == "active" and plan in plan_credits:
                credits = plan_credits[plan]
            else:
                credits = free_credits
            conn.execute(
                """INSERT OR IGNORE INTO song_credits (user_id, balance, monthly_allowance, last_reset)
                   VALUES (?, ?, ?, CURRENT_TIMESTAMP)""",
                (row["id"], credits, credits),
            )
            count += 1
        conn.commit()
        return count
    finally:
        conn.close()


def increment_song_credits(db_path: pathlib.Path, user_id: str, amount: int) -> None:
    conn = _conn(db_path)
    try:
        conn.execute(
            """INSERT INTO song_credits (user_id, balance, monthly_allowance)
               VALUES (?, ?, 0)
               ON CONFLICT(user_id) DO UPDATE SET balance = balance + ?""",
            (user_id, amount, amount),
        )
        conn.commit()
    finally:
        conn.close()


# ── Lyrics CRUD ───────────────────────────────────────────────────────────────

def get_lyric_title(db_path: pathlib.Path, lyric_id: int) -> str | None:
    """Return the title of a lyric row with no user filter (used by public share endpoint)."""
    conn = _conn(db_path)
    try:
        row = conn.execute("SELECT title FROM lyrics WHERE id = ?", (lyric_id,)).fetchone()
        return row["title"] if row else None
    finally:
        conn.close()


def get_lyric(db_path: pathlib.Path, lyric_id: int, user_id: str) -> dict | None:
    conn = _conn(db_path)
    try:
        row = conn.execute(
            "SELECT * FROM lyrics WHERE id = ? AND user_id = ?", (lyric_id, user_id)
        ).fetchone()
        return _row_to_dict(row)
    finally:
        conn.close()


def update_song_variant(db_path: pathlib.Path, variant_id: int, **fields) -> None:
    """Update one or more columns on a song_variants row."""
    if not fields:
        return
    set_clause = ", ".join(f"{k} = ?" for k in fields)
    values = list(fields.values()) + [variant_id]
    conn = _conn(db_path)
    try:
        conn.execute(f"UPDATE song_variants SET {set_clause} WHERE id = ?", values)
        conn.commit()
    finally:
        conn.close()


def get_song_variant_by_did_job_id(db_path: pathlib.Path, job_id: str) -> dict | None:
    """Look up a song_variants row by did_job_id — used by the D-ID webhook."""
    conn = _conn(db_path)
    try:
        row = conn.execute(
            "SELECT * FROM song_variants WHERE did_job_id = ?", (job_id,)
        ).fetchone()
        return _row_to_dict(row)
    finally:
        conn.close()


def get_song_variant_by_id(db_path: pathlib.Path, variant_id: int) -> dict | None:
    """Look up a song_variants row by ID (no user filter — used by webhook)."""
    conn = _conn(db_path)
    try:
        row = conn.execute(
            "SELECT * FROM song_variants WHERE id = ?", (variant_id,)
        ).fetchone()
        return _row_to_dict(row)
    finally:
        conn.close()


def delete_song_variant(db_path: pathlib.Path, variant_id: int, user_id: str) -> bool:
    """Delete a song_variants row owned by user_id. Returns True if deleted."""
    conn = _conn(db_path)
    try:
        cur = conn.execute(
            "DELETE FROM song_variants WHERE id = ? AND user_id = ?",
            (variant_id, user_id),
        )
        conn.commit()
        return cur.rowcount > 0
    finally:
        conn.close()


def get_song_variants_for_lyric(
    db_path: pathlib.Path, lyric_id: int, user_id: str
) -> list[dict]:
    conn = _conn(db_path)
    try:
        rows = conn.execute(
            """SELECT * FROM song_variants
               WHERE lyric_id = ? AND user_id = ?
               ORDER BY created_at ASC""",
            (lyric_id, user_id),
        ).fetchall()
        return [_row_to_dict(r) for r in rows]
    finally:
        conn.close()


def list_lyrics_for_user(db_path: pathlib.Path, user_id: str) -> list[dict]:
    conn = _conn(db_path)
    try:
        rows = conn.execute(
            "SELECT id, title, created_at FROM lyrics WHERE user_id = ? ORDER BY id DESC",
            (user_id,),
        ).fetchall()
        return [_row_to_dict(r) for r in rows]
    finally:
        conn.close()


def reset_song_credits_balance(db_path: pathlib.Path, user_id: str) -> None:
    """Reset balance back to monthly_allowance — called on Stripe monthly renewal."""
    conn = _conn(db_path)
    try:
        conn.execute(
            """UPDATE song_credits
               SET balance = monthly_allowance, last_reset = CURRENT_TIMESTAMP
               WHERE user_id = ?""",
            (user_id,),
        )
        conn.commit()
    finally:
        conn.close()


# ── Video credits CRUD ────────────────────────────────────────────────────────

def get_video_credits(db_path: pathlib.Path, user_id: str) -> dict | None:
    conn = _conn(db_path)
    try:
        row = conn.execute(
            "SELECT * FROM video_credits WHERE user_id = ?", (user_id,)
        ).fetchone()
        return _row_to_dict(row)
    finally:
        conn.close()


def upsert_video_credits(
    db_path: pathlib.Path,
    user_id: str,
    balance: int,
    monthly_allowance: int,
) -> None:
    conn = _conn(db_path)
    try:
        conn.execute(
            """INSERT INTO video_credits (user_id, balance, monthly_allowance, last_reset)
               VALUES (?, ?, ?, CURRENT_TIMESTAMP)
               ON CONFLICT(user_id) DO UPDATE SET
                   balance = ?,
                   monthly_allowance = ?,
                   last_reset = CURRENT_TIMESTAMP""",
            (user_id, balance, monthly_allowance, balance, monthly_allowance),
        )
        conn.commit()
    finally:
        conn.close()


def check_and_deduct_video_credit(db_path: pathlib.Path, user_id: str) -> bool:
    """Atomically deduct 1 credit. Returns True on success, False if balance is 0."""
    conn = _conn(db_path)
    try:
        row = conn.execute(
            "SELECT balance FROM video_credits WHERE user_id = ?", (user_id,)
        ).fetchone()
        if not row or row["balance"] < 1:
            return False
        conn.execute(
            "UPDATE video_credits SET balance = balance - 1 WHERE user_id = ?",
            (user_id,),
        )
        conn.commit()
        return True
    finally:
        conn.close()


def refund_video_credit(db_path: pathlib.Path, user_id: str) -> None:
    conn = _conn(db_path)
    try:
        conn.execute(
            "UPDATE video_credits SET balance = balance + 1 WHERE user_id = ?",
            (user_id,),
        )
        conn.commit()
    finally:
        conn.close()


def save_fal_image_job(db_path: pathlib.Path, job_id: str, fal_request_id: str) -> None:
    """Persist a fal.ai job_id → request_id mapping for later polling."""
    conn = _conn(db_path)
    try:
        conn.execute(
            "INSERT OR REPLACE INTO fal_image_jobs (job_id, fal_request_id) VALUES (?, ?)",
            (job_id, fal_request_id),
        )
        conn.commit()
    finally:
        conn.close()


def get_fal_request_id(db_path: pathlib.Path, job_id: str) -> str | None:
    """Return the fal.ai request_id for a local job_id, or None if not found."""
    conn = _conn(db_path)
    try:
        row = conn.execute(
            "SELECT fal_request_id FROM fal_image_jobs WHERE job_id = ?",
            (job_id,),
        ).fetchone()
        return row["fal_request_id"] if row else None
    finally:
        conn.close()


def get_pending_fal_image_jobs(db_path: pathlib.Path) -> list[dict]:
    """Return all fal_image_jobs rows where image_url is NULL."""
    conn = _conn(db_path)
    try:
        rows = conn.execute(
            "SELECT job_id, fal_request_id, created_at FROM fal_image_jobs WHERE image_url IS NULL"
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def update_fal_image_job_url(db_path: pathlib.Path, job_id: str, image_url: str) -> None:
    """Set image_url on a fal_image_jobs row once the image has been downloaded."""
    conn = _conn(db_path)
    try:
        conn.execute(
            "UPDATE fal_image_jobs SET image_url = ? WHERE job_id = ?",
            (image_url, job_id),
        )
        conn.commit()
    finally:
        conn.close()


# ── Daily message usage ───────────────────────────────────────────────────────

def get_daily_message_count(db_path: pathlib.Path, user_id: str, date: str) -> int:
    """Return message count for user on a given date (YYYY-MM-DD)."""
    conn = _conn(db_path)
    try:
        row = conn.execute(
            "SELECT count FROM message_usage WHERE user_id = ? AND date = ?",
            (user_id, date),
        ).fetchone()
        return row["count"] if row else 0
    finally:
        conn.close()


def increment_daily_message_count(db_path: pathlib.Path, user_id: str, date: str) -> None:
    """Upsert message_usage, incrementing count by 1 for the given date."""
    conn = _conn(db_path)
    try:
        conn.execute(
            """
            INSERT INTO message_usage (user_id, date, count)
            VALUES (?, ?, 1)
            ON CONFLICT(user_id, date) DO UPDATE SET count = count + 1
            """,
            (user_id, date),
        )
        conn.commit()
    finally:
        conn.close()


def create_reset_token(db_path: pathlib.Path, user_id: str, token: str, expires_at: str) -> None:
    """Insert a new password reset token."""
    conn = _conn(db_path)
    try:
        conn.execute(
            "INSERT INTO password_reset_tokens (user_id, token, expires_at) VALUES (?, ?, ?)",
            (user_id, token, expires_at),
        )
        conn.commit()
    finally:
        conn.close()


def get_reset_token(db_path: pathlib.Path, token: str) -> dict | None:
    """Fetch a reset token row by token string."""
    conn = _conn(db_path)
    try:
        row = conn.execute(
            "SELECT * FROM password_reset_tokens WHERE token = ?", (token,)
        ).fetchone()
        return _row_to_dict(row)
    finally:
        conn.close()


def mark_reset_token_used(db_path: pathlib.Path, token: str) -> None:
    """Mark a reset token as used."""
    conn = _conn(db_path)
    try:
        conn.execute("UPDATE password_reset_tokens SET used = 1 WHERE token = ?", (token,))
        conn.commit()
    finally:
        conn.close()


def create_verification_token(db_path: pathlib.Path, user_id: str, token: str, expires_at: str) -> None:
    """Insert a new email verification token."""
    conn = _conn(db_path)
    try:
        conn.execute(
            "INSERT INTO email_verification_tokens (user_id, token, expires_at) VALUES (?, ?, ?)",
            (user_id, token, expires_at),
        )
        conn.commit()
    finally:
        conn.close()


def get_verification_token(db_path: pathlib.Path, token: str) -> dict | None:
    """Fetch a verification token row by token string."""
    conn = _conn(db_path)
    try:
        row = conn.execute(
            "SELECT * FROM email_verification_tokens WHERE token = ?", (token,)
        ).fetchone()
        return _row_to_dict(row)
    finally:
        conn.close()


def mark_verification_token_used(db_path: pathlib.Path, token: str) -> None:
    """Mark a verification token as used."""
    conn = _conn(db_path)
    try:
        conn.execute("UPDATE email_verification_tokens SET used = 1 WHERE token = ?", (token,))
        conn.commit()
    finally:
        conn.close()
