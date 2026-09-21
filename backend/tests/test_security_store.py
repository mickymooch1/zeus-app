"""security_store: blocked_ips / security_events / security_scans persistence.

Real temp SQLite through db.init_user_tables, so the DDL in db.py is exercised
too (a missing table or index would fail here, not in production).
"""
import os
import pathlib
import sqlite3
import sys
from datetime import datetime, timedelta, timezone

import pytest

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))
os.environ.setdefault("ANTHROPIC_API_KEY", "test-key")
os.environ.setdefault("APIFRAME_API_KEY", "test-key")
os.environ.setdefault("SONG_STORAGE_PATH", "/tmp/test_songs")
os.environ.setdefault("SONG_PUBLIC_BASE_URL", "https://example.com/files/songs")
os.environ.setdefault("SONG_WEBHOOK_URL", "https://zeusaidesign.com/webhooks/apiframe")
os.environ.setdefault("JWT_SECRET", "test-secret-for-security-store-tests")

import db
import security_store as store

NOW = datetime(2026, 9, 21, 12, 0, 0, tzinfo=timezone.utc)


@pytest.fixture
def path(tmp_path):
    p = tmp_path / "test.db"
    db.init_user_tables(p)
    return p


def _ts(days_ago=0, hours_ago=0):
    return (NOW - timedelta(days=days_ago, hours=hours_ago)).strftime("%Y-%m-%d %H:%M:%S")


def test_init_creates_the_three_tables_and_is_idempotent(path):
    db.init_user_tables(path)  # second run must not raise
    conn = sqlite3.connect(path)
    names = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    conn.close()
    assert {"blocked_ips", "security_events", "security_scans"} <= names


# ── blocked_ips ──────────────────────────────────────────────────────────────

def test_auto_block_defaults_to_a_seven_day_expiry(path):
    store.add_blocked_ip(path, "45.13.7.2", "5 probe attempts", now=NOW)
    (row,) = store.active_blocked(path, now=NOW)
    assert row["ip"] == "45.13.7.2" and row["reason"] == "5 probe attempts"
    assert row["source"] == "auto"
    assert row["expires_at"] == _ts(days_ago=-7)
    assert row["denied_requests"] == 0


def test_manual_block_can_be_permanent(path):
    store.add_blocked_ip(path, "45.13.7.2", "abuse", source="manual", ttl_days=None, now=NOW)
    (row,) = store.active_blocked(path, now=NOW + timedelta(days=3650))
    assert row["expires_at"] is None and row["source"] == "manual"


def test_expired_blocks_are_not_active(path):
    store.add_blocked_ip(path, "45.13.7.2", "x", now=NOW)
    assert store.active_blocked(path, now=NOW + timedelta(days=7, seconds=1)) == []


def test_unblock_deactivates_and_reports_whether_anything_changed(path):
    store.add_blocked_ip(path, "45.13.7.2", "x", now=NOW)
    assert store.unblock_ip(path, "45.13.7.2", now=NOW) is True
    assert store.active_blocked(path, now=NOW) == []
    assert store.unblock_ip(path, "45.13.7.2", now=NOW) is False   # already unblocked
    assert store.unblock_ip(path, "8.8.8.8", now=NOW) is False     # never blocked


def test_reblocking_rearms_an_unblocked_ip_without_duplicating(path):
    store.add_blocked_ip(path, "45.13.7.2", "first", now=NOW)
    store.add_denied(path, {"45.13.7.2": 5})
    store.unblock_ip(path, "45.13.7.2", now=NOW)
    store.add_blocked_ip(path, "45.13.7.2", "second", now=NOW)
    (row,) = store.active_blocked(path, now=NOW)
    assert row["reason"] == "second" and row["denied_requests"] == 0
    conn = sqlite3.connect(path)
    assert conn.execute("SELECT COUNT(*) FROM blocked_ips").fetchone()[0] == 1
    conn.close()


def test_add_denied_counts_only_known_ips(path):
    store.add_blocked_ip(path, "45.13.7.2", "x", now=NOW)
    store.add_denied(path, {"45.13.7.2": 3, "8.8.8.8": 9})
    store.add_denied(path, {"45.13.7.2": 2})
    (row,) = store.active_blocked(path, now=NOW)
    assert row["denied_requests"] == 5


def test_cache_rows_gives_epoch_expiries_for_the_block_cache(path):
    store.add_blocked_ip(path, "45.13.7.2", "auto", now=NOW)
    store.add_blocked_ip(path, "8.8.8.8", "manual", source="manual", ttl_days=None, now=NOW)
    rows = dict(store.cache_rows(path, now=NOW))
    assert rows["8.8.8.8"] is None
    assert rows["45.13.7.2"] == pytest.approx((NOW + timedelta(days=7)).timestamp())


def test_blocked_since_lists_recent_blocks_in_any_state(path):
    store.add_blocked_ip(path, "45.13.7.2", "old", now=NOW - timedelta(days=10))
    store.add_blocked_ip(path, "8.8.8.8", "recent", now=NOW - timedelta(days=2))
    store.unblock_ip(path, "8.8.8.8", now=NOW)
    rows = store.blocked_since(path, NOW - timedelta(days=7))
    assert [r["ip"] for r in rows] == ["8.8.8.8"]


# ── security_events ──────────────────────────────────────────────────────────

def _events(path):
    store.insert_events(path, [
        (_ts(hours_ago=1), "45.13.7.2", "blocked_path", "/.git/config", 404, "sqlmap"),
        (_ts(hours_ago=1), "45.13.7.2", "blocked_path", "/.git/config", 404, None),
        (_ts(hours_ago=2), "8.8.8.8", "blocked_path", "/wp-admin", 404, None),
        (_ts(hours_ago=3), "8.8.8.8", "auth_fail", "/auth/login", 401, None),
        (_ts(days_ago=9), "8.8.8.8", "blocked_path", "/old", 404, None),
    ])


def test_count_events_respects_kind_and_window(path):
    _events(path)
    assert store.count_events(path, "blocked_path", NOW - timedelta(days=1)) == 3
    assert store.count_events(path, "blocked_path", NOW - timedelta(days=30)) == 4
    assert store.count_events(path, "blocked_path", NOW - timedelta(days=30), until=NOW - timedelta(days=5)) == 1
    assert store.count_events(path, "auth_fail", NOW - timedelta(days=1)) == 1


def test_top_paths_orders_by_frequency(path):
    _events(path)
    assert store.top_paths(path, ["blocked_path"], NOW - timedelta(days=1)) == [
        ("/.git/config", 2), ("/wp-admin", 1)]
    assert store.top_paths(path, ["blocked_path"], NOW - timedelta(days=1), limit=1) == [("/.git/config", 2)]


def test_ip_counts_applies_the_minimum(path):
    _events(path)
    assert store.ip_counts(path, "blocked_path", NOW - timedelta(days=1), min_count=2) == [("45.13.7.2", 2)]
    assert store.ip_counts(path, "auth_fail", NOW - timedelta(days=1), min_count=1) == [("8.8.8.8", 1)]


def test_events_since_returns_dicts_for_the_requested_kinds(path):
    _events(path)
    rows = store.events_since(path, ["auth_fail"], NOW - timedelta(days=1))
    assert [(r["ip"], r["path"], r["status"]) for r in rows] == [("8.8.8.8", "/auth/login", 401)]


def test_prune_events_deletes_only_rows_older_than_the_retention(path):
    _events(path)
    store.insert_events(path, [(_ts(days_ago=40), "1.2.3.4", "blocked_path", "/ancient", 404, None)])
    assert store.prune_events(path, days=30, now=NOW) == 1
    assert store.count_events(path, "blocked_path", NOW - timedelta(days=365)) == 4


def test_insert_events_truncates_long_fields(path):
    store.insert_events(path, [(_ts(), "45.13.7.2", "blocked_path", "/" + "a" * 2000, 404, "u" * 2000)])
    (row,) = store.events_since(path, ["blocked_path"], NOW - timedelta(days=1))
    assert len(row["path"]) <= 300 and len(row["ua"]) <= 200


# ── security_scans ───────────────────────────────────────────────────────────

def test_scans_since_returns_a_kinds_rows_in_the_window_oldest_first(path):
    store.record_scan(path, "scan", "scheduled", "clean", "old", {"n": 0}, now=NOW - timedelta(days=9))
    store.record_scan(path, "scan", "scheduled", "review", "a", {"n": 1}, now=NOW - timedelta(days=3))
    store.record_scan(path, "scan", "manual", "clean", "b", {"n": 2}, now=NOW - timedelta(days=1))
    store.record_scan(path, "weekly", "scheduled", "clean", "w", {}, now=NOW - timedelta(days=1))
    rows = store.scans_since(path, "scan", NOW - timedelta(days=7))
    assert [(r["summary"], r["status"], r["details"]) for r in rows] == [
        ("a", "review", {"n": 1}), ("b", "clean", {"n": 2})]


def test_last_scan_returns_the_newest_row_with_parsed_details(path):
    store.record_scan(path, "scan", "scheduled", "clean", "all good", {"n": 1}, now=NOW - timedelta(days=4))
    store.record_scan(path, "scan", "manual", "review", "hmm", {"n": 2}, now=NOW - timedelta(days=2))
    store.record_scan(path, "weekly", "scheduled", "clean", "weekly", {}, now=NOW - timedelta(days=1))
    assert store.last_scan(path, "scan")["details"] == {"n": 2}
    assert store.last_scan(path, "scan", trigger="scheduled")["details"] == {"n": 1}
    assert store.last_scan(path, "weekly")["summary"] == "weekly"
    assert store.last_scan(path, "scan", trigger="nope") is None
