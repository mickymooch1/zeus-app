"""
db.py — User database module for Zeus SaaS platform.
Uses the SAME SQLite file as HistoryStore (zeus_agent.py).
Path priority: ZEUS_DATA_DIR → /data (Railway) → ~/.zeus (local)
"""
import logging
import os
import pathlib
import sqlite3
import uuid
from datetime import datetime, timezone

_log = logging.getLogger(__name__)


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

            CREATE TABLE IF NOT EXISTS pin_reset_tokens (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id    TEXT NOT NULL,
                token      TEXT NOT NULL UNIQUE,
                expires_at TEXT NOT NULL,
                used       INTEGER NOT NULL DEFAULT 0,
                FOREIGN KEY (user_id) REFERENCES users(id)
            );
            CREATE INDEX IF NOT EXISTS idx_pint_token ON pin_reset_tokens (token);

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
            "ALTER TABLE users ADD COLUMN has_paid INTEGER NOT NULL DEFAULT 0",
            "ALTER TABLE song_variants ADD COLUMN animate_cover INTEGER NOT NULL DEFAULT 1",
            "ALTER TABLE song_credits ADD COLUMN animation_balance INTEGER NOT NULL DEFAULT 0",
            "ALTER TABLE song_credits ADD COLUMN animation_monthly_allowance INTEGER NOT NULL DEFAULT 0",
            "ALTER TABLE song_variants ADD COLUMN is_public INTEGER NOT NULL DEFAULT 0",
            """CREATE TABLE IF NOT EXISTS song_variant_likes (
                variant_id INTEGER NOT NULL,
                user_id    TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (variant_id, user_id)
            )""",
            """CREATE TABLE IF NOT EXISTS playlists (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id    TEXT NOT NULL,
                name       TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )""",
            """CREATE TABLE IF NOT EXISTS playlist_songs (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                playlist_id INTEGER NOT NULL,
                variant_id  INTEGER NOT NULL,
                position    INTEGER NOT NULL DEFAULT 0,
                added_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(playlist_id, variant_id)
            )""",
            """CREATE TABLE IF NOT EXISTS song_play_events (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                variant_id INTEGER NOT NULL,
                user_id    TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )""",
            """CREATE INDEX IF NOT EXISTS idx_play_events_user
               ON song_play_events(user_id)""",
            "ALTER TABLE song_variants ADD COLUMN refunded_at TIMESTAMP",
            # Premium Credits: rename animation columns (SQLite 3.25+ RENAME COLUMN)
            "ALTER TABLE song_credits RENAME COLUMN animation_balance TO premium_balance",
            "ALTER TABLE song_credits RENAME COLUMN animation_monthly_allowance TO premium_monthly_allowance",
            # Stems columns on song_variants
            "ALTER TABLE song_variants ADD COLUMN stems_status TEXT",
            "ALTER TABLE song_variants ADD COLUMN stems_vocals_url TEXT",
            "ALTER TABLE song_variants ADD COLUMN stems_drums_url TEXT",
            "ALTER TABLE song_variants ADD COLUMN stems_bass_url TEXT",
            "ALTER TABLE song_variants ADD COLUMN stems_other_url TEXT",
            "ALTER TABLE users ADD COLUMN sound_persona_id TEXT",
            "ALTER TABLE users ADD COLUMN sound_persona_variant_id INTEGER",
            "ALTER TABLE users ADD COLUMN sound_persona_title TEXT",
            "ALTER TABLE song_variants ADD COLUMN provider TEXT DEFAULT 'apiframe'",
            """CREATE TABLE IF NOT EXISTS device_fingerprints (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                fp_hash     TEXT NOT NULL UNIQUE,
                user_id     TEXT,
                created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )""",
            # Audit log of every credit grant. Doubles as the idempotency gate for
            # one-time top-ups: UNIQUE(stripe_payment_id, credit_type) means the same
            # payment can't be credited twice (checkout vs payment_intent overlap, or
            # a Stripe delivery retry).
            """CREATE TABLE IF NOT EXISTS credit_ledger (
                id                INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id           TEXT NOT NULL,
                email             TEXT,
                credit_type       TEXT NOT NULL,
                amount            INTEGER NOT NULL,
                source            TEXT NOT NULL,
                stripe_payment_id TEXT,
                created_at        TEXT NOT NULL,
                UNIQUE(stripe_payment_id, credit_type)
            )""",
            "ALTER TABLE users ADD COLUMN account_type TEXT NOT NULL DEFAULT 'standard'",
            "ALTER TABLE users ADD COLUMN kids_pin_hash TEXT",
            "ALTER TABLE users ADD COLUMN school_verified INTEGER NOT NULL DEFAULT 0",
            "ALTER TABLE song_variants ADD COLUMN subtitles_url TEXT",
            "ALTER TABLE lyrics ADD COLUMN kids_story INTEGER NOT NULL DEFAULT 0",
            "ALTER TABLE users ADD COLUMN custom_voice_id TEXT",
            # Canonical (normalised) email — defeats the Gmail +alias/dot tricks.
            # Deliberately NOT UNIQUE: historical duplicates may already exist and
            # must not break startup or logins.
            "ALTER TABLE users ADD COLUMN email_canonical TEXT",
            "CREATE INDEX IF NOT EXISTS idx_users_email_canonical ON users (email_canonical)",
            # One row per signup per device — the legacy device_fingerprints table
            # has fp_hash UNIQUE, so it can only ever hold one account per device
            # and cannot answer "how many accounts came from here?".
            """CREATE TABLE IF NOT EXISTS device_signups (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                fp_hash    TEXT NOT NULL,
                user_id    TEXT,
                created_at TEXT NOT NULL
            )""",
            "CREATE INDEX IF NOT EXISTS idx_device_signups_fp ON device_signups (fp_hash)",
            # Soft abuse signals. Recorded, alerted on, never used to block.
            """CREATE TABLE IF NOT EXISTS signup_flags (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id    TEXT,
                email      TEXT,
                ip_address TEXT,
                reason     TEXT NOT NULL,
                detail     TEXT,
                created_at TEXT NOT NULL
            )""",
            "CREATE INDEX IF NOT EXISTS idx_signup_flags_created ON signup_flags (created_at)",
            # Supports the single-query library load (get_all_variants_for_user),
            # which filters song_variants by user_id.
            "CREATE INDEX IF NOT EXISTS idx_song_variants_user ON song_variants (user_id)",
            # Platform attribution (added 2026-08-04). One of web / android / ios
            # / unknown. Cannot be backfilled — rows created before this ships stay
            # NULL, so always report "since <date>" rather than implying all-time.
            # signup_platform = where the account was acquired;
            # song_variants.platform = where each song was actually made.
            "ALTER TABLE users ADD COLUMN signup_platform TEXT",
            "ALTER TABLE song_variants ADD COLUMN platform TEXT",
            "CREATE INDEX IF NOT EXISTS idx_song_variants_platform ON song_variants (platform)",
        ]:
            try:
                conn.execute(_migration)
                conn.commit()
            except Exception:
                pass

        _backfill_email_canonical(conn)
    finally:
        conn.close()


def _backfill_email_canonical(conn) -> None:
    """Populate users.email_canonical for rows predating the column.

    Only touches NULL rows, so this costs nothing after the first boot. Gmail dot
    stripping can't be expressed in SQL, hence the Python loop.
    """
    try:
        import signup_guard
        rows = conn.execute(
            "SELECT id, email FROM users WHERE email_canonical IS NULL AND email IS NOT NULL"
        ).fetchall()
        for row in rows:
            conn.execute(
                "UPDATE users SET email_canonical = ? WHERE id = ?",
                (signup_guard.normalize_email(row["email"]), row["id"]),
            )
        if rows:
            conn.commit()
            _log.info("db: backfilled email_canonical for %d user(s)", len(rows))
    except Exception:
        _log.exception("db: email_canonical backfill failed (non-fatal)")


def record_registration_attempt(db_path: pathlib.Path, ip_address: str) -> None:
    """Log a signup attempt against an IP. Always succeeds, never blocks."""
    from datetime import datetime, timezone
    conn = _conn(db_path)
    try:
        conn.execute(
            "INSERT INTO registration_attempts (ip_address, attempted_at) VALUES (?, ?)",
            (ip_address, datetime.now(timezone.utc).isoformat()),
        )
        conn.commit()
    finally:
        conn.close()


def count_registrations_from_ip(db_path: pathlib.Path, ip_address: str, hours: int) -> int:
    """How many signups this IP has attempted in the last `hours` hours."""
    from datetime import datetime, timedelta, timezone
    cutoff = (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()
    conn = _conn(db_path)
    try:
        row = conn.execute(
            "SELECT COUNT(*) FROM registration_attempts WHERE ip_address = ? AND attempted_at > ?",
            (ip_address, cutoff),
        ).fetchone()
        return int(row[0]) if row else 0
    finally:
        conn.close()


def is_ip_allowlisted(ip_address: str) -> bool:
    """True if REGISTRATION_ALLOWLIST names this IP — exempt from the hard cap."""
    import os
    allowlist = {ip.strip() for ip in os.environ.get("REGISTRATION_ALLOWLIST", "").split(",") if ip.strip()}
    return bool(ip_address) and ip_address in allowlist


def count_device_signups(db_path: pathlib.Path, fp_hash: str) -> int:
    """How many accounts have been created from this device fingerprint.

    Reads `device_signups`, which (unlike the legacy `device_fingerprints`
    table, whose fp_hash is UNIQUE) records every signup — so reuse is
    countable. Used as a soft flag only; shared devices are normal.
    """
    conn = _conn(db_path)
    try:
        row = conn.execute(
            "SELECT COUNT(*) FROM device_signups WHERE fp_hash = ?", (fp_hash,)
        ).fetchone()
        return int(row[0]) if row else 0
    finally:
        conn.close()


def record_device_signup(db_path: pathlib.Path, fp_hash: str, user_id: str) -> None:
    """Append a (device, user) signup pair. One row per signup, never deduped."""
    from datetime import datetime, timezone
    conn = _conn(db_path)
    try:
        conn.execute(
            "INSERT INTO device_signups (fp_hash, user_id, created_at) VALUES (?, ?, ?)",
            (fp_hash, user_id, datetime.now(timezone.utc).isoformat()),
        )
        conn.commit()
    finally:
        conn.close()


def record_signup_flag(
    db_path: pathlib.Path,
    user_id: str,
    email: str,
    ip_address: str,
    reason: str,
    detail: str = "",
) -> None:
    """Record a soft abuse signal for later review. Never affects the signup."""
    from datetime import datetime, timezone
    conn = _conn(db_path)
    try:
        conn.execute(
            """INSERT INTO signup_flags (user_id, email, ip_address, reason, detail, created_at)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (user_id, email, ip_address, reason, detail,
             datetime.now(timezone.utc).isoformat()),
        )
        conn.commit()
    finally:
        conn.close()


def get_recent_signup_flags(db_path: pathlib.Path, limit: int = 100) -> list[dict]:
    """Most recent soft abuse signals, newest first — for admin review."""
    conn = _conn(db_path)
    try:
        rows = conn.execute(
            "SELECT * FROM signup_flags ORDER BY id DESC LIMIT ?", (limit,)
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def check_device_fingerprint_exists(db_path: pathlib.Path, fp_hash: str) -> bool:
    """Read-only check — True if fingerprint already registered. No side effects."""
    conn = _conn(db_path)
    try:
        return bool(conn.execute(
            "SELECT id FROM device_fingerprints WHERE fp_hash = ?", (fp_hash,)
        ).fetchone())
    finally:
        conn.close()


def record_device_fingerprint(db_path: pathlib.Path, fp_hash: str, user_id: str) -> None:
    """Record a device fingerprint after successful registration. Idempotent."""
    conn = _conn(db_path)
    try:
        conn.execute(
            "INSERT OR IGNORE INTO device_fingerprints (fp_hash, user_id) VALUES (?, ?)",
            (fp_hash, user_id),
        )
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
    import signup_guard
    now = datetime.now(timezone.utc).isoformat()
    user_id = str(uuid.uuid4())
    conn = _conn(db_path)
    try:
        conn.execute(
            """
            INSERT INTO users (id, email, email_canonical, password_hash, name,
                               subscription_status, tc_accepted_at, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, 'free', ?, ?, ?)
            """,
            (user_id, email.lower().strip(), signup_guard.normalize_email(email),
             password_hash, name, tc_accepted_at, now, now),
        )
        conn.commit()
        return get_user_by_id(db_path, user_id)
    finally:
        conn.close()


def get_user_by_canonical_email(db_path: pathlib.Path, email: str) -> dict | None:
    """Find a user whose normalised email matches this address.

    Catches the Gmail +alias and dot tricks: name+1@gmail.com and n.a.m.e@gmail.com
    both resolve to the same canonical form as name@gmail.com.
    """
    import signup_guard
    canonical = signup_guard.normalize_email(email)
    if not canonical:
        return None
    conn = _conn(db_path)
    try:
        row = conn.execute(
            "SELECT * FROM users WHERE email_canonical = ?", (canonical,)
        ).fetchone()
        return _row_to_dict(row)
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


def set_kids_pin(db_path: pathlib.Path, user_id: str, pin_hash: str) -> None:
    """Store a bcrypt-hashed 4-digit PIN for kids mode."""
    update_user(db_path, user_id, kids_pin_hash=pin_hash)


def get_kids_pin_hash(db_path: pathlib.Path, user_id: str) -> str | None:
    """Return the stored PIN hash, or None if not set."""
    user = get_user_by_id(db_path, user_id)
    return user.get("kids_pin_hash") if user else None


def set_school_verified(db_path: pathlib.Path, user_id: str, verified: bool) -> None:
    update_user(db_path, user_id, school_verified=1 if verified else 0)


def set_sound_persona(
    db_path: pathlib.Path,
    user_id: str,
    *,
    persona_id: str,
    variant_id: int,
    title: str,
) -> None:
    now = datetime.now(timezone.utc).isoformat()
    conn = _conn(db_path)
    try:
        conn.execute(
            "UPDATE users SET sound_persona_id = ?, sound_persona_variant_id = ?, sound_persona_title = ?, updated_at = ? WHERE id = ?",
            (persona_id, variant_id, title, now, user_id),
        )
        conn.commit()
    finally:
        conn.close()


def clear_sound_persona(db_path: pathlib.Path, user_id: str) -> None:
    now = datetime.now(timezone.utc).isoformat()
    conn = _conn(db_path)
    try:
        conn.execute(
            "UPDATE users SET sound_persona_id = NULL, sound_persona_variant_id = NULL, sound_persona_title = NULL, updated_at = ? WHERE id = ?",
            (now, user_id),
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
                allowance = credits
            else:
                credits = free_credits
                allowance = 0  # free users have no periodic refill
            conn.execute(
                """INSERT OR IGNORE INTO song_credits (user_id, balance, monthly_allowance, last_reset)
                   VALUES (?, ?, ?, CURRENT_TIMESTAMP)""",
                (row["id"], credits, allowance),
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


# ── Credit ledger (audit log + idempotency gate) ──────────────────────────────

def record_credit_grant(
    db_path: pathlib.Path,
    user_id: str,
    email: str | None,
    credit_type: str,
    amount: int,
    source: str,
    stripe_payment_id: str | None,
) -> bool:
    """Record a credit grant in the audit ledger.

    Returns True if this is a newly-recorded grant, or False if a grant for the
    same (stripe_payment_id, credit_type) already exists. Callers use the False
    return to SKIP re-crediting — this is the idempotency gate for one-time
    top-ups (checkout vs payment_intent backup for the same payment, and Stripe
    delivery retries).

    Note: SQLite treats NULLs as distinct, so a NULL stripe_payment_id can never
    conflict — a missing id means "cannot dedupe", and every call records + returns
    True. Callers should pass the payment_intent id whenever they have one.
    """
    from datetime import datetime, timezone
    conn = _conn(db_path)
    try:
        cur = conn.execute(
            """INSERT INTO credit_ledger
                   (user_id, email, credit_type, amount, source, stripe_payment_id, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT(stripe_payment_id, credit_type) DO NOTHING""",
            (user_id, email, credit_type, amount, source, stripe_payment_id,
             datetime.now(timezone.utc).isoformat()),
        )
        conn.commit()
        return cur.rowcount > 0
    finally:
        conn.close()


def get_credit_grant(db_path: pathlib.Path, stripe_payment_id: str, credit_type: str) -> dict | None:
    """Return the ledger row for a (payment, credit_type), or None if not granted."""
    conn = _conn(db_path)
    try:
        row = conn.execute(
            "SELECT * FROM credit_ledger WHERE stripe_payment_id = ? AND credit_type = ?",
            (stripe_payment_id, credit_type),
        ).fetchone()
        return _row_to_dict(row) if row else None
    finally:
        conn.close()


def get_recent_credit_grant(
    db_path: pathlib.Path, user_id: str, credit_type: str, amount: int, within_hours: int = 24
) -> dict | None:
    """Return the most recent matching ledger grant (same user + credit_type + amount)
    within the window, across ANY source (webhook or manual), or None.

    Powers the admin duplicate-grant warning: a manual grant that matches a recent
    grant (manual OR webhook) is flagged before it double-credits.
    """
    from datetime import datetime, timezone, timedelta
    cutoff = (datetime.now(timezone.utc) - timedelta(hours=within_hours)).isoformat()
    conn = _conn(db_path)
    try:
        row = conn.execute(
            """SELECT * FROM credit_ledger
               WHERE user_id = ? AND credit_type = ? AND amount = ? AND created_at >= ?
               ORDER BY created_at DESC LIMIT 1""",
            (user_id, credit_type, amount, cutoff),
        ).fetchone()
        return _row_to_dict(row) if row else None
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


def get_all_variants_for_user(db_path: pathlib.Path, user_id: str) -> list[dict]:
    """Every variant the user owns, with its lyric title — in ONE query.

    Replaces the old library load, which issued a separate request (and three
    SQLite connection opens) per lyric. On an account with ~400 songs that was
    ~400 HTTP requests and ~1200 connection opens to render one page, which
    saturated the single uvicorn worker and made loads fail intermittently.

    Ordered newest-variant-first so the caller doesn't need to re-sort.
    """
    conn = _conn(db_path)
    try:
        rows = conn.execute(
            """SELECT sv.*, l.title AS lyric_title
               FROM song_variants sv
               JOIN lyrics l ON l.id = sv.lyric_id
               WHERE sv.user_id = ?
               ORDER BY sv.id DESC""",
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


# ── Premium credits CRUD ──────────────────────────────────────────────────────

def get_premium_credits(db_path: pathlib.Path, user_id: str) -> dict | None:
    """Return premium_balance and premium_monthly_allowance from song_credits."""
    conn = _conn(db_path)
    try:
        row = conn.execute(
            "SELECT premium_balance, premium_monthly_allowance FROM song_credits WHERE user_id = ?",
            (user_id,),
        ).fetchone()
        return {"premium_balance": row["premium_balance"], "premium_monthly_allowance": row["premium_monthly_allowance"]} if row else None
    finally:
        conn.close()


def upsert_premium_credits(
    db_path: pathlib.Path,
    user_id: str,
    balance: int,
    monthly_allowance: int,
) -> None:
    """Set premium credit columns on song_credits row, creating it if absent."""
    conn = _conn(db_path)
    try:
        conn.execute(
            """INSERT INTO song_credits (user_id, balance, monthly_allowance, premium_balance, premium_monthly_allowance, last_reset)
               VALUES (?, 0, 0, ?, ?, CURRENT_TIMESTAMP)
               ON CONFLICT(user_id) DO UPDATE SET
                   premium_balance = ?,
                   premium_monthly_allowance = ?""",
            (user_id, balance, monthly_allowance, balance, monthly_allowance),
        )
        conn.commit()
    finally:
        conn.close()


def check_and_deduct_premium_credit(db_path: pathlib.Path, user_id: str) -> bool:
    """Atomically deduct 1 premium credit. Returns True on success, False if balance is 0."""
    conn = _conn(db_path)
    try:
        row = conn.execute(
            "SELECT premium_balance FROM song_credits WHERE user_id = ?", (user_id,)
        ).fetchone()
        if not row or row["premium_balance"] < 1:
            return False
        conn.execute(
            "UPDATE song_credits SET premium_balance = premium_balance - 1 WHERE user_id = ?",
            (user_id,),
        )
        conn.commit()
        return True
    finally:
        conn.close()


def increment_premium_credits(db_path: pathlib.Path, user_id: str, amount: int) -> None:
    """Add premium credits to song_credits row (for top-up pack purchases and refunds)."""
    conn = _conn(db_path)
    try:
        conn.execute(
            """INSERT INTO song_credits (user_id, balance, monthly_allowance, premium_balance, premium_monthly_allowance)
               VALUES (?, 0, 0, ?, 0)
               ON CONFLICT(user_id) DO UPDATE SET premium_balance = premium_balance + ?""",
            (user_id, amount, amount),
        )
        conn.commit()
    finally:
        conn.close()


def reset_premium_credits_balance(db_path: pathlib.Path, user_id: str) -> None:
    """Reset premium_balance back to premium_monthly_allowance — called on Stripe monthly renewal."""
    conn = _conn(db_path)
    try:
        conn.execute(
            """UPDATE song_credits
               SET premium_balance = premium_monthly_allowance
               WHERE user_id = ?""",
            (user_id,),
        )
        conn.commit()
    finally:
        conn.close()


def save_stems(
    db_path: pathlib.Path,
    variant_id: int,
    *,
    vocals_url: str,
    drums_url: str,
    bass_url: str,
    other_url: str,
) -> None:
    """Save completed Demucs stem URLs and mark stems_status='complete'."""
    conn = _conn(db_path)
    try:
        conn.execute(
            """UPDATE song_variants
               SET stems_status='complete', stems_vocals_url=?, stems_drums_url=?,
                   stems_bass_url=?, stems_other_url=?
               WHERE id=?""",
            (vocals_url, drums_url, bass_url, other_url, variant_id),
        )
        conn.commit()
    finally:
        conn.close()


def fail_stems(db_path: pathlib.Path, variant_id: int) -> None:
    """Mark stems_status='failed' on a variant."""
    conn = _conn(db_path)
    try:
        conn.execute(
            "UPDATE song_variants SET stems_status='failed' WHERE id=?", (variant_id,)
        )
        conn.commit()
    finally:
        conn.close()


def get_stems(db_path: pathlib.Path, variant_id: int) -> dict | None:
    """Return stems status and URLs for a variant."""
    conn = _conn(db_path)
    try:
        row = conn.execute(
            """SELECT stems_status, stems_vocals_url, stems_drums_url,
                      stems_bass_url, stems_other_url
               FROM song_variants WHERE id=?""",
            (variant_id,),
        ).fetchone()
        return dict(row) if row else None
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


def create_pin_reset_token(db_path: pathlib.Path, user_id: str, token: str, expires_at: str) -> None:
    conn = _conn(db_path)
    try:
        conn.execute(
            "INSERT INTO pin_reset_tokens (user_id, token, expires_at) VALUES (?, ?, ?)",
            (user_id, token, expires_at),
        )
        conn.commit()
    finally:
        conn.close()


def get_pin_reset_token(db_path: pathlib.Path, token: str) -> dict | None:
    conn = _conn(db_path)
    try:
        row = conn.execute("SELECT * FROM pin_reset_tokens WHERE token = ?", (token,)).fetchone()
        return _row_to_dict(row)
    finally:
        conn.close()


def mark_pin_reset_token_used(db_path: pathlib.Path, token: str) -> None:
    conn = _conn(db_path)
    try:
        conn.execute("UPDATE pin_reset_tokens SET used = 1 WHERE token = ?", (token,))
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


# ── Playlists ─────────────────────────────────────────────────────────────────

def create_playlist(db_path: pathlib.Path, user_id: str, name: str) -> dict:
    conn = _conn(db_path)
    try:
        cur = conn.execute(
            "INSERT INTO playlists (user_id, name) VALUES (?, ?)", (user_id, name)
        )
        conn.commit()
        row = conn.execute("SELECT * FROM playlists WHERE id = ?", (cur.lastrowid,)).fetchone()
        return _row_to_dict(row)
    finally:
        conn.close()


def get_playlists(db_path: pathlib.Path, user_id: str) -> list:
    conn = _conn(db_path)
    try:
        rows = conn.execute(
            """SELECT p.*, COUNT(ps.id) AS song_count
               FROM playlists p
               LEFT JOIN playlist_songs ps ON ps.playlist_id = p.id
               WHERE p.user_id = ?
               GROUP BY p.id
               ORDER BY p.created_at DESC""",
            (user_id,),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def get_playlist_by_id(db_path: pathlib.Path, playlist_id: int, user_id: str) -> dict | None:
    conn = _conn(db_path)
    try:
        row = conn.execute(
            "SELECT * FROM playlists WHERE id = ? AND user_id = ?", (playlist_id, user_id)
        ).fetchone()
        return _row_to_dict(row)
    finally:
        conn.close()


def delete_playlist(db_path: pathlib.Path, playlist_id: int, user_id: str) -> bool:
    conn = _conn(db_path)
    try:
        conn.execute("DELETE FROM playlist_songs WHERE playlist_id = ?", (playlist_id,))
        cur = conn.execute(
            "DELETE FROM playlists WHERE id = ? AND user_id = ?", (playlist_id, user_id)
        )
        conn.commit()
        return cur.rowcount > 0
    finally:
        conn.close()


def add_song_to_playlist(db_path: pathlib.Path, playlist_id: int, variant_id: int) -> bool:
    conn = _conn(db_path)
    try:
        row = conn.execute(
            "SELECT COALESCE(MAX(position), -1) + 1 AS next_pos FROM playlist_songs WHERE playlist_id = ?",
            (playlist_id,),
        ).fetchone()
        next_pos = row["next_pos"] if row else 0
        cur = conn.execute(
            "INSERT OR IGNORE INTO playlist_songs (playlist_id, variant_id, position) VALUES (?, ?, ?)",
            (playlist_id, variant_id, next_pos),
        )
        conn.commit()
        return cur.rowcount > 0
    finally:
        conn.close()


def remove_song_from_playlist(db_path: pathlib.Path, playlist_id: int, variant_id: int) -> bool:
    conn = _conn(db_path)
    try:
        cur = conn.execute(
            "DELETE FROM playlist_songs WHERE playlist_id = ? AND variant_id = ?",
            (playlist_id, variant_id),
        )
        conn.commit()
        return cur.rowcount > 0
    finally:
        conn.close()


def get_playlist_songs(db_path: pathlib.Path, playlist_id: int) -> list:
    conn = _conn(db_path)
    try:
        rows = conn.execute(
            """SELECT sv.*, sv.id AS variant_id, l.title, ps.position
               FROM playlist_songs ps
               JOIN song_variants sv ON sv.id = ps.variant_id
               LEFT JOIN lyrics l ON l.id = sv.lyric_id
               WHERE ps.playlist_id = ?
               ORDER BY ps.position ASC""",
            (playlist_id,),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def reorder_playlist_songs(db_path: pathlib.Path, playlist_id: int, variant_ids: list) -> None:
    conn = _conn(db_path)
    try:
        for pos, vid in enumerate(variant_ids):
            conn.execute(
                "UPDATE playlist_songs SET position = ? WHERE playlist_id = ? AND variant_id = ?",
                (pos, playlist_id, vid),
            )
        conn.commit()
    finally:
        conn.close()


def get_user_songs_for_ai(db_path: pathlib.Path, user_id: str) -> list[dict]:
    """Return all completed songs for a user: variant_id, title, genre_tag, style_prompt."""
    conn = _conn(db_path)
    try:
        rows = conn.execute(
            """SELECT sv.id AS variant_id,
                      l.title,
                      sv.genre_tag,
                      sv.style_prompt
               FROM song_variants sv
               JOIN lyrics l ON l.id = sv.lyric_id
               WHERE sv.user_id = ?
                 AND sv.status = 'complete'
                 AND sv.mp3_url IS NOT NULL
               ORDER BY sv.created_at DESC""",
            (user_id,),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def log_play_event(db_path: pathlib.Path, variant_id: int, user_id: str | None) -> None:
    """Record that a user started playing a discover song."""
    conn = _conn(db_path)
    try:
        conn.execute(
            "INSERT INTO song_play_events (variant_id, user_id) VALUES (?, ?)",
            (variant_id, user_id),
        )
        conn.commit()
    finally:
        conn.close()


def get_for_you_songs(db_path: pathlib.Path, user_id: str, limit: int = 20) -> list[dict]:
    """Personalised feed using both likes and play history.

    Ranking logic:
    - Infer preferred genres from likes (weight 2) + plays (weight 1)
    - Exclude songs the user has already played or liked
    - Order by recency (newest first) — deliberately different from trending
    - Falls back to trending only when the user has zero activity at all
    """
    conn = _conn(db_path)
    try:
        # ── 1. Collect genre preferences from both likes and plays ────────────
        liked_tags = conn.execute(
            """SELECT sv.genre_tag, COUNT(*) AS n
               FROM song_variant_likes svl
               JOIN song_variants sv ON sv.id = svl.variant_id
               WHERE svl.user_id = ? AND sv.genre_tag IS NOT NULL
               GROUP BY sv.genre_tag""",
            (user_id,),
        ).fetchall()

        played_tags = conn.execute(
            """SELECT sv.genre_tag, COUNT(*) AS n
               FROM song_play_events spe
               JOIN song_variants sv ON sv.id = spe.variant_id
               WHERE spe.user_id = ? AND sv.genre_tag IS NOT NULL
               GROUP BY sv.genre_tag""",
            (user_id,),
        ).fetchall()

        # Merge weights: likes count double vs plays
        genre_weights: dict[str, int] = {}
        for (tag, n) in liked_tags:
            for part in [tag] + tag.split("__"):
                if part:
                    genre_weights[part] = genre_weights.get(part, 0) + n * 2
        for (tag, n) in played_tags:
            for part in [tag] + tag.split("__"):
                if part:
                    genre_weights[part] = genre_weights.get(part, 0) + n

        # Top genres by combined weight
        top_genres = sorted(genre_weights, key=genre_weights.__getitem__, reverse=True)

        # ── 2. Build exclusion list: played + liked ───────────────────────────
        played_ids = [r[0] for r in conn.execute(
            "SELECT DISTINCT variant_id FROM song_play_events WHERE user_id = ?", (user_id,),
        ).fetchall()]
        liked_ids = [r[0] for r in conn.execute(
            "SELECT variant_id FROM song_variant_likes WHERE user_id = ?", (user_id,),
        ).fetchall()]
        exclude_ids = list(set(played_ids) | set(liked_ids))
        has_activity = bool(played_ids or liked_ids)

        _log.info(
            "For You: user=%s top_genres=%s played=%d liked=%d exclude=%d",
            user_id, top_genres[:6], len(played_ids), len(liked_ids), len(exclude_ids),
        )

        base_select = """SELECT sv.id AS variant_id,
                                sv.genre_tag,
                                sv.mp3_url,
                                sv.image_url  AS cover_url,
                                sv.music_video_url,
                                sv.duration_seconds,
                                l.title,
                                u.artist_name,
                                (SELECT COUNT(*) FROM song_variant_likes lk
                                 WHERE lk.variant_id = sv.id) AS like_count
                         FROM song_variants sv
                         JOIN lyrics l ON l.id = sv.lyric_id
                         JOIN users  u ON u.id = sv.user_id
                         WHERE sv.is_public = 1
                           AND sv.status = 'complete'
                           AND sv.mp3_url IS NOT NULL"""

        def _excl_clause(ids: list) -> tuple[str, list]:
            if not ids:
                return "", []
            ph = ",".join("?" * len(ids))
            return f" AND sv.id NOT IN ({ph})", ids

        # ── 3. Personalised: genres user has engaged with, ordered by recency ─
        if top_genres and has_activity:
            genre_ph = ",".join("?" * len(top_genres))
            like_clauses: list[str] = []
            like_params: list[str] = []
            for g in top_genres:
                if "__" not in g:
                    like_clauses.append("sv.genre_tag LIKE ? OR sv.genre_tag LIKE ?")
                    like_params += [f"{g}__%", f"%__{g}"]

            if like_clauses:
                genre_filter = f"(sv.genre_tag IN ({genre_ph}) OR {' OR '.join(like_clauses)})"
                genre_params: list = top_genres + like_params
            else:
                genre_filter = f"sv.genre_tag IN ({genre_ph})"
                genre_params = top_genres

            excl_sql, excl_p = _excl_clause(exclude_ids)
            # Order by recency — intentionally different from trending (which is like_count)
            sql = (f"{base_select} AND {genre_filter}{excl_sql}"
                   f" ORDER BY COALESCE(sv.completed_at, sv.created_at) DESC LIMIT ?")
            rows = conn.execute(sql, genre_params + excl_p + [limit]).fetchall()
            results = [dict(r) for r in rows]
            _log.info("For You: personalised returned %d songs", len(results))
            if results:
                return results
            _log.info("For You: personalised empty (all heard?) — expanding to any genre")

        # ── 4. Soft fallback: any unheard public songs, newest first ──────────
        excl_sql, excl_p = _excl_clause(exclude_ids)
        sql = f"{base_select}{excl_sql} ORDER BY COALESCE(sv.completed_at, sv.created_at) DESC LIMIT ?"
        rows = conn.execute(sql, excl_p + [limit]).fetchall()
        results = [dict(r) for r in rows]
        _log.info("For You: unheard fallback returned %d songs", len(results))
        if results:
            return results

        # ── 5. Last resort: trending regardless of play history ───────────────
        sql = f"{base_select} ORDER BY like_count DESC, sv.completed_at DESC LIMIT ?"
        rows = conn.execute(sql, [limit]).fetchall()
        results = [dict(r) for r in rows]
        _log.info("For You: trending last-resort returned %d songs", len(results))
        return results
    finally:
        conn.close()
