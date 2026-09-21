"""Porick security commands, scheduler jobs and the Monday weekly-summary hook.

Commands are exact-match (no AI): a misread "unblock" or "security scan" must never
be left to a language model. `unblock` is the safety valve for a wrongly blocked
legitimate IP, so it is tested end to end (DB row AND in-memory cache).
"""
import importlib
import os
import pathlib
import sys
from datetime import datetime, timedelta, timezone

import pytest

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))
os.environ.setdefault("ANTHROPIC_API_KEY", "test-key")
os.environ.setdefault("APIFRAME_API_KEY", "test-key")
os.environ.setdefault("SONG_STORAGE_PATH", "/tmp/test_songs")
os.environ.setdefault("SONG_PUBLIC_BASE_URL", "https://example.com/files/songs")
os.environ.setdefault("SONG_WEBHOOK_URL", "https://zeusaidesign.com/webhooks/apiframe")
os.environ.setdefault("JWT_SECRET", "test-secret-for-security-command-tests")

HOSTILE = 'x <script>alert(1)</script> & "y"'


@pytest.fixture
def T(tmp_path, monkeypatch):
    monkeypatch.setenv("ZEUS_DATA_DIR", str(tmp_path))
    monkeypatch.delenv("SECURITY_ENFORCE", raising=False)
    import db as _db
    importlib.reload(_db)
    import telegram_admin as _T
    importlib.reload(_T)
    import bot_guard
    bot_guard.guard.cache.load([])
    bot_guard.guard._loaded = False
    return _T


@pytest.fixture
def store(T):
    import security_store
    return security_store


def dbp():
    import db
    return db.get_db_path()


def no_ai(monkeypatch, T):
    def boom(*a, **k):
        raise AssertionError("security commands must not be routed through the AI parser")
    monkeypatch.setattr(T, "_ai_parse", boom)


# ── routing ──────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("text,handler,args", [
    ("security status", "_cmd_security_status", ()),
    ("Porick security status", "_cmd_security_status", ()),
    ("SECURITY  STATUS", "_cmd_security_status", ()),
    ("security scan", "_cmd_security_scan", ()),
    ("blocked ips", "_cmd_blocked_ips", ()),
    ("blocked ip", "_cmd_blocked_ips", ()),
    ("porick blocked ips", "_cmd_blocked_ips", ()),
    ("unblock 45.13.7.2", "_cmd_unblock_ip", ("45.13.7.2",)),
    ("unblock ip 45.13.7.2", "_cmd_unblock_ip", ("45.13.7.2",)),
    ("Porick unblock 2001:4860:4860::8888", "_cmd_unblock_ip", ("2001:4860:4860::8888",)),
])
def test_commands_are_exact_match_and_bypass_the_ai(T, monkeypatch, text, handler, args):
    no_ai(monkeypatch, T)
    calls = []
    monkeypatch.setattr(T, handler, lambda *a: calls.append(a) or "OK")
    assert T.parse_and_run(text, chat_id="c1") == "OK"
    assert calls == [args]


def test_similar_sentences_still_go_to_the_ai_layer(T, monkeypatch):
    routed = []
    monkeypatch.setattr(T, "_ai_parse", lambda t, c="": routed.append(t) or {"action": "none"})
    monkeypatch.setattr(T, "_execute_action", lambda a, c="": "AI")
    T.parse_and_run("how is security looking today", chat_id="c1")
    assert routed == ["how is security looking today"]


def test_help_documents_every_security_command(T):
    for cmd in ("security status", "blocked ips", "unblock", "security scan"):
        assert cmd in T.HELP_TEXT


# ── security status ──────────────────────────────────────────────────────────

def test_status_with_no_history_says_never_and_shows_the_mode(T):
    text = T._cmd_security_status()
    assert "never" in text.lower() and "shadow" in text.lower()


def test_status_shows_the_last_scan_active_blocks_and_recent_flags(T, store):
    store.record_scan(dbp(), "scan", "scheduled", "review", "1 finding(s)",
                      {"findings": [{"level": "review", "text": "Possible brute force from 8.8.8.8"}]})
    store.add_blocked_ip(dbp(), "45.13.7.2", HOSTILE)
    text = T._cmd_security_status()
    assert "review" in text.lower() and "Possible brute force from 8.8.8.8" in text
    assert "45.13.7.2" in text and "<script>" not in text and "&lt;script&gt;" in text
    assert "1" in text  # active block count


def test_status_reflects_enforcement(T, monkeypatch):
    monkeypatch.setenv("SECURITY_ENFORCE", "1")
    assert "enforcing" in T._cmd_security_status().lower()


# ── blocked ips ──────────────────────────────────────────────────────────────

def test_blocked_ips_when_empty(T):
    assert "No IPs" in T._cmd_blocked_ips()


def test_blocked_ips_lists_ip_reason_source_expiry_and_denials(T, store):
    store.add_blocked_ip(dbp(), "45.13.7.2", "5 probe attempts")
    store.add_blocked_ip(dbp(), "45.13.7.3", HOSTILE, source="manual", ttl_days=None)
    store.add_denied(dbp(), {"45.13.7.2": 7})
    text = T._cmd_blocked_ips()
    assert "45.13.7.2" in text and "5 probe attempts" in text and "7" in text
    assert "45.13.7.3" in text and "manual" in text and "permanent" in text.lower()
    assert "<script>" not in text and "&lt;script&gt;" in text


def test_blocked_ips_warns_in_shadow_mode_only(T, store, monkeypatch):
    store.add_blocked_ip(dbp(), "45.13.7.2", "x")
    assert "NOT" in T._cmd_blocked_ips()                 # shadow: flagged but not blocked
    monkeypatch.setenv("SECURITY_ENFORCE", "1")
    assert "NOT" not in T._cmd_blocked_ips()


def test_expired_and_unblocked_ips_are_not_listed(T, store):
    store.add_blocked_ip(dbp(), "45.13.7.2", "x", now=datetime.now(timezone.utc) - timedelta(days=30))
    store.add_blocked_ip(dbp(), "45.13.7.3", "y")
    store.unblock_ip(dbp(), "45.13.7.3")
    assert "No IPs" in T._cmd_blocked_ips()


# ── unblock ──────────────────────────────────────────────────────────────────

def test_unblock_clears_the_db_row_and_the_in_memory_cache(T, store):
    import bot_guard
    store.add_blocked_ip(dbp(), "45.13.7.2", "x")
    bot_guard.guard.init(dbp())
    assert bot_guard.guard.is_blocked("45.13.7.2")
    reply = T._cmd_unblock_ip("45.13.7.2")
    assert reply.startswith("✅") and "45.13.7.2" in reply
    assert store.active_blocked(dbp()) == []
    assert not bot_guard.guard.is_blocked("45.13.7.2")


def test_unblock_of_an_ip_that_is_not_blocked_says_so(T):
    assert T._cmd_unblock_ip("45.13.7.2").startswith("ℹ️")


@pytest.mark.parametrize("bad", ["not-an-ip", "999.1.1.1", "1.2.3", "'; DROP TABLE users;--"])
def test_unblock_rejects_anything_that_is_not_an_ip(T, bad):
    assert T._cmd_unblock_ip(bad).startswith("❌")


def test_unblock_through_parse_and_run_logs_the_action_without_raising(T, store):
    store.add_blocked_ip(dbp(), "45.13.7.2", "x")
    assert T.parse_and_run("unblock 45.13.7.2", chat_id="c1").startswith("✅")


# ── security scan ────────────────────────────────────────────────────────────

def test_manual_scan_returns_the_report_and_records_a_manual_scan_row(T, store, monkeypatch):
    import security_scan
    monkeypatch.setattr(security_scan, "canary_probe", lambda *a, **k: [])
    reply = T.parse_and_run("security scan", chat_id="c1")
    assert "Security scan clean" in reply
    assert store.last_scan(dbp(), "scan", trigger="manual")["status"] == "clean"
    assert store.last_scan(dbp(), "scan", trigger="scheduled") is None


# ── scheduler ────────────────────────────────────────────────────────────────

def test_scheduler_registers_the_flush_and_daily_scan_jobs(tmp_path, monkeypatch):
    monkeypatch.setenv("ZEUS_DATA_DIR", str(tmp_path))
    import db as _db
    importlib.reload(_db)
    import apscheduler.schedulers.asyncio as aps

    class FakeScheduler:
        running = False

        def __init__(self):
            self.jobs = {}

        def start(self):
            pass

        def add_job(self, func, trigger=None, id=None, **kw):
            self.jobs[id] = (func, trigger, kw)

    monkeypatch.setattr(aps, "AsyncIOScheduler", FakeScheduler)
    import scheduler
    monkeypatch.setattr(scheduler, "_scheduler", None)
    scheduler.init_scheduler(history_store=object())
    jobs = scheduler._scheduler.jobs

    import bot_guard
    import security_scan
    flush_fn, flush_trigger, _ = jobs["__security_flush__"]
    assert flush_fn == bot_guard.flush and "seconds=30" in repr(flush_trigger)
    scan_fn, scan_trigger, scan_kw = jobs["__security_scan__"]
    assert scan_fn == security_scan.run_if_due
    assert "hour='9'" in str(scan_trigger) and "minute='30'" in str(scan_trigger)
    assert scan_kw.get("misfire_grace_time", 0) >= 1800
    monkeypatch.setattr(scheduler, "_scheduler", None)


# ── weekly hook in the daily report ──────────────────────────────────────────

def test_daily_report_triggers_the_weekly_security_summary_check():
    import inspect
    import zeus_ops_agent as ops
    assert "_send_security_weekly()" in inspect.getsource(ops.daily_report)


def test_weekly_hook_calls_send_weekly_if_due(monkeypatch):
    import security_scan
    import zeus_ops_agent as ops
    calls = []
    monkeypatch.setattr(security_scan, "send_weekly_if_due", lambda *a, **k: calls.append(1) or True)
    ops._send_security_weekly()
    assert calls == [1]


def test_weekly_hook_never_raises_into_the_daily_report(monkeypatch):
    import security_scan
    import zeus_ops_agent as ops

    def boom(*a, **k):
        raise RuntimeError("weekly exploded")
    monkeypatch.setattr(security_scan, "send_weekly_if_due", boom)
    ops._send_security_weekly()  # must not raise
