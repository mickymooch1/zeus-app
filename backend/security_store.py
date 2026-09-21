"""SQL accessors for the security monitor's three tables (DDL lives in db.py).

blocked_ips      - IPs the bot guard has flagged/blocked, with reason + expiry
security_events  - flagged requests only (blocked paths, auth failures, ...); pruned
security_scans   - history of scans and weekly summaries (also the "is a scan due?" clock)

Every function takes `db_path` first, like db.py. Timestamps are stored as
'YYYY-MM-DD HH:MM:SS' UTC so plain string comparison orders them correctly.
"""
from __future__ import annotations

import json
import pathlib
from datetime import datetime, timedelta, timezone

import db

_TS = "%Y-%m-%d %H:%M:%S"
_PATH_MAX, _UA_MAX = 300, 200


def _utc(now: datetime | None) -> datetime:
    return now or datetime.now(timezone.utc)


def _ts(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).strftime(_TS)


def _epoch(ts: str | None) -> float | None:
    if ts is None:
        return None
    return datetime.strptime(ts, _TS).replace(tzinfo=timezone.utc).timestamp()


# ── blocked_ips ──────────────────────────────────────────────────────────────

def add_blocked_ip(db_path: pathlib.Path, ip: str, reason: str, source: str = "auto",
                   ttl_days: int | None = 7, now: datetime | None = None) -> None:
    """Insert or re-arm a block. Re-blocking resets denied_requests and clears unblocked_at."""
    now = _utc(now)
    expires = None if ttl_days is None else _ts(now + timedelta(days=ttl_days))
    conn = db._conn(db_path)
    try:
        conn.execute(
            """INSERT INTO blocked_ips (ip, reason, source, blocked_at, expires_at, unblocked_at, denied_requests)
               VALUES (?, ?, ?, ?, ?, NULL, 0)
               ON CONFLICT(ip) DO UPDATE SET reason=excluded.reason, source=excluded.source,
                   blocked_at=excluded.blocked_at, expires_at=excluded.expires_at,
                   unblocked_at=NULL, denied_requests=0""",
            (ip, reason, source, _ts(now), expires),
        )
        conn.commit()
    finally:
        conn.close()


def unblock_ip(db_path: pathlib.Path, ip: str, now: datetime | None = None) -> bool:
    """Deactivate a block. True only if there was an active row to deactivate."""
    conn = db._conn(db_path)
    try:
        cur = conn.execute(
            "UPDATE blocked_ips SET unblocked_at = ? WHERE ip = ? AND unblocked_at IS NULL",
            (_ts(_utc(now)), ip),
        )
        conn.commit()
        return cur.rowcount > 0
    finally:
        conn.close()


def active_blocked(db_path: pathlib.Path, now: datetime | None = None) -> list[dict]:
    conn = db._conn(db_path)
    try:
        rows = conn.execute(
            """SELECT ip, reason, source, blocked_at, expires_at, denied_requests FROM blocked_ips
               WHERE unblocked_at IS NULL AND (expires_at IS NULL OR expires_at > ?)
               ORDER BY blocked_at DESC, ip""",
            (_ts(_utc(now)),),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def cache_rows(db_path: pathlib.Path, now: datetime | None = None) -> list[tuple[str, float | None]]:
    """(ip, expires_epoch | None) for every active block — what BlockCache.load wants."""
    return [(r["ip"], _epoch(r["expires_at"])) for r in active_blocked(db_path, now)]


def add_denied(db_path: pathlib.Path, counts: dict[str, int]) -> None:
    """Add to denied_requests for IPs that have a row; unknown IPs are ignored."""
    if not counts:
        return
    conn = db._conn(db_path)
    try:
        conn.executemany(
            "UPDATE blocked_ips SET denied_requests = denied_requests + ? WHERE ip = ?",
            [(n, ip) for ip, n in counts.items()],
        )
        conn.commit()
    finally:
        conn.close()


def blocked_since(db_path: pathlib.Path, since: datetime) -> list[dict]:
    """Every block created at/after `since`, in any state (for the weekly summary)."""
    conn = db._conn(db_path)
    try:
        rows = conn.execute(
            """SELECT ip, reason, source, blocked_at, expires_at, unblocked_at, denied_requests
               FROM blocked_ips WHERE blocked_at >= ? ORDER BY blocked_at DESC""",
            (_ts(since),),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


# ── security_events ──────────────────────────────────────────────────────────

def insert_events(db_path: pathlib.Path, rows) -> None:
    """rows: (ts, ip, kind, path, status, ua). Long path/ua values are truncated."""
    rows = [
        (ts, ip, kind, (path or "")[:_PATH_MAX] or None, status, (ua or "")[:_UA_MAX] or None)
        for ts, ip, kind, path, status, ua in rows
    ]
    if not rows:
        return
    conn = db._conn(db_path)
    try:
        conn.executemany(
            "INSERT INTO security_events (ts, ip, kind, path, status, ua) VALUES (?, ?, ?, ?, ?, ?)", rows)
        conn.commit()
    finally:
        conn.close()


def prune_events(db_path: pathlib.Path, days: int = 30, now: datetime | None = None) -> int:
    conn = db._conn(db_path)
    try:
        cur = conn.execute("DELETE FROM security_events WHERE ts < ?", (_ts(_utc(now) - timedelta(days=days)),))
        conn.commit()
        return cur.rowcount
    finally:
        conn.close()


def count_events(db_path: pathlib.Path, kind: str, since: datetime, until: datetime | None = None) -> int:
    conn = db._conn(db_path)
    try:
        sql, args = "SELECT COUNT(*) FROM security_events WHERE kind = ? AND ts >= ?", [kind, _ts(since)]
        if until is not None:
            sql += " AND ts < ?"
            args.append(_ts(until))
        return conn.execute(sql, args).fetchone()[0]
    finally:
        conn.close()


def _in(kinds) -> tuple[str, list]:
    kinds = list(kinds)
    return ",".join("?" * len(kinds)), kinds


def events_since(db_path: pathlib.Path, kinds, since: datetime) -> list[dict]:
    marks, args = _in(kinds)
    conn = db._conn(db_path)
    try:
        rows = conn.execute(
            f"SELECT ts, ip, kind, path, status, ua FROM security_events "
            f"WHERE kind IN ({marks}) AND ts >= ? ORDER BY ts, id", args + [_ts(since)]).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def top_paths(db_path: pathlib.Path, kinds, since: datetime, limit: int = 10) -> list[tuple[str, int]]:
    marks, args = _in(kinds)
    conn = db._conn(db_path)
    try:
        rows = conn.execute(
            f"SELECT path, COUNT(*) AS n FROM security_events "
            f"WHERE kind IN ({marks}) AND ts >= ? AND path IS NOT NULL "
            f"GROUP BY path ORDER BY n DESC, path LIMIT ?", args + [_ts(since), limit]).fetchall()
        return [(r["path"], r["n"]) for r in rows]
    finally:
        conn.close()


def ip_counts(db_path: pathlib.Path, kind: str, since: datetime, min_count: int = 1) -> list[tuple[str, int]]:
    conn = db._conn(db_path)
    try:
        rows = conn.execute(
            """SELECT ip, COUNT(*) AS n FROM security_events WHERE kind = ? AND ts >= ?
               GROUP BY ip HAVING n >= ? ORDER BY n DESC, ip""", (kind, _ts(since), min_count)).fetchall()
        return [(r["ip"], r["n"]) for r in rows]
    finally:
        conn.close()


# ── security_scans ───────────────────────────────────────────────────────────

def record_scan(db_path: pathlib.Path, kind: str, trigger: str, status: str, summary: str,
                details: dict, now: datetime | None = None) -> None:
    conn = db._conn(db_path)
    try:
        conn.execute(
            "INSERT INTO security_scans (ts, kind, trigger, status, summary, details) VALUES (?, ?, ?, ?, ?, ?)",
            (_ts(_utc(now)), kind, trigger, status, summary, json.dumps(details)))
        conn.commit()
    finally:
        conn.close()


def last_scan(db_path: pathlib.Path, kind: str, trigger: str | None = None) -> dict | None:
    conn = db._conn(db_path)
    try:
        sql, args = "SELECT ts, kind, trigger, status, summary, details FROM security_scans WHERE kind = ?", [kind]
        if trigger is not None:
            sql += " AND trigger = ?"
            args.append(trigger)
        row = conn.execute(sql + " ORDER BY ts DESC, id DESC LIMIT 1", args).fetchone()
        if row is None:
            return None
        out = dict(row)
        out["details"] = json.loads(out["details"]) if out["details"] else {}
        return out
    finally:
        conn.close()
