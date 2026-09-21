"""security_scan: the 3-day scan, the canary probes and the Monday weekly summary.

A scan that silently reports "clean" when it can't see a problem is worse than no
scan, so each check has a positive case (flags it) AND a boundary/negative case.
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
os.environ.setdefault("JWT_SECRET", "test-secret-for-security-scan-tests")

import bot_guard
import db
import security_scan as scan
import security_store as store

NOW = datetime(2026, 9, 21, 12, 0, 0, tzinfo=timezone.utc)       # a Monday
assert NOW.weekday() == 0


@pytest.fixture(autouse=True)
def _shadow(monkeypatch):
    monkeypatch.delenv("SECURITY_ENFORCE", raising=False)


@pytest.fixture
def path(tmp_path):
    p = tmp_path / "test.db"
    db.init_user_tables(p)
    return p


def ts(hours_ago=0.0, days_ago=0.0):
    return (NOW - timedelta(hours=hours_ago, days=days_ago)).strftime("%Y-%m-%d %H:%M:%S")


def ev(path_, kind, ip="45.13.7.2", p="/.git/config", status=404, *, hours_ago=1.0, days_ago=0.0):
    store.insert_events(path_, [(ts(hours_ago, days_ago), ip, kind, p, status, None)])


def add_user(path_, uid, email, admin=0):
    conn = sqlite3.connect(path_)
    conn.execute("INSERT INTO users (id, email, password_hash, is_admin, created_at, updated_at) "
                 "VALUES (?, ?, 'x', ?, ?, ?)", (uid, email, admin, ts(), ts()))
    conn.commit()
    conn.close()


def add_songs(path_, uid, n, hours_ago=1.0, days_ago=0.0):
    conn = sqlite3.connect(path_)
    conn.execute("INSERT OR IGNORE INTO lyrics (id, user_id, brief, lyrics_text) VALUES (1, ?, 'b', 'l')", (uid,))
    for _ in range(n):
        conn.execute("INSERT INTO song_variants (lyric_id, user_id, style_prompt, created_at) VALUES (1, ?, 's', ?)",
                     (uid, ts(hours_ago, days_ago)))
    conn.commit()
    conn.close()


def clean_canary():
    return []


def run(path_, **kw):
    kw.setdefault("canary", clean_canary)
    return scan.run_scan(path_, trigger="scheduled", now=NOW, **kw)


def texts(report):
    return " | ".join(f.text for f in report.findings)


# ── clean / always report ────────────────────────────────────────────────────

def test_an_empty_system_is_clean_and_says_so(path):
    r = run(path)
    assert r.findings == [] and r.status == "clean"
    msg = scan.format_scan(r)
    assert "✅" in msg and "Security scan clean" in msg
    row = store.last_scan(path, "scan", trigger="scheduled")
    assert row["status"] == "clean"


def test_the_message_states_the_mode(path, monkeypatch):
    assert "shadow" in scan.format_scan(run(path)).lower()
    monkeypatch.setenv("SECURITY_ENFORCE", "1")
    assert "enforcing" in scan.format_scan(run(path)).lower()


# ── check 1 & 2: slipped 200s and the canary ─────────────────────────────────

def test_a_200_on_a_scanner_path_is_a_critical_finding(path):
    ev(path, "blocked_path_200", p="/.env", status=200)
    ev(path, "blocked_path_200", p="/.env", status=200)
    r = run(path)
    assert r.status == "review"
    (f,) = [f for f in r.findings if f.level == "critical"]
    assert "/.env" in f.text and "2" in f.text
    assert "🚨" in scan.format_scan(r)


def test_canary_findings_are_included(path):
    bad = scan.Finding("critical", "canary: https://zeusbeats.com/.git/config returned 200")
    r = run(path, canary=lambda: [bad])
    assert bad in r.findings and r.status == "review"


# ── check 3: volume spike ────────────────────────────────────────────────────

def _hits(path_, n, *, hours_ago=1.0, days_ago=0.0):
    store.insert_events(path_, [(ts(hours_ago, days_ago), f"45.13.7.{i % 200}", "blocked_path", "/.git/config", 404, None)
                                for i in range(n)])


def test_a_big_spike_over_the_trailing_average_is_flagged(path):
    _hits(path, 150)                       # last 24h
    _hits(path, 7, days_ago=3)             # prior week: ~1/day
    assert "spike" in texts(run(path)).lower()


def test_small_volumes_and_normal_days_are_not_flagged(path):
    _hits(path, 90)                        # under the 100 floor
    assert "spike" not in texts(run(path)).lower()


def test_a_busy_baseline_raises_the_bar(path):
    _hits(path, 150)
    _hits(path, 280, days_ago=3)           # prior avg 40/day -> needs > 200
    assert "spike" not in texts(run(path)).lower()


# ── check 4: failed logins ───────────────────────────────────────────────────

def test_an_ip_with_many_failed_logins_is_flagged(path):
    for _ in range(25):
        ev(path, "auth_fail", ip="45.13.7.2", p="/auth/login", status=401)
    r = run(path)
    assert "45.13.7.2" in texts(r) and "25" in texts(r)


def test_a_few_failed_logins_are_not_flagged(path):
    for _ in range(19):
        ev(path, "auth_fail", ip="45.13.7.2", p="/auth/login", status=401)
    assert "45.13.7.2" not in texts(run(path))


# ── check 5: generation volume ───────────────────────────────────────────────

def test_a_user_far_above_their_own_baseline_is_flagged(path):
    add_user(path, "u1", "abuser@example.com")
    add_songs(path, "u1", 40)                         # last 24h
    add_songs(path, "u1", 14, days_ago=5)             # ~1/day before
    assert "abuser@example.com" in texts(run(path))


def test_a_heavy_but_consistent_user_is_not_flagged(path):
    add_user(path, "u1", "power@example.com")
    add_songs(path, "u1", 40)
    add_songs(path, "u1", 280, days_ago=5)            # 20/day baseline
    assert "power@example.com" not in texts(run(path))


def test_admins_are_excluded_from_the_per_user_check(path):
    add_user(path, "a1", "owner@example.com", admin=1)
    add_songs(path, "a1", 60)
    assert "owner@example.com" not in texts(run(path))


def test_a_global_generation_surge_is_flagged_but_small_totals_are_not(path):
    add_user(path, "u1", "a@example.com")
    add_user(path, "u2", "b@example.com")
    add_songs(path, "u1", 25)
    add_songs(path, "u2", 25)
    add_songs(path, "u1", 14, days_ago=5)             # 1/day baseline; 50 total in 24h
    assert "generation volume" in texts(run(path)).lower()


def test_low_totals_do_not_trigger_the_global_check(path):
    add_user(path, "u1", "a@example.com")
    add_songs(path, "u1", 30)
    add_songs(path, "u1", 14, days_ago=5)
    assert "generation volume" not in texts(run(path)).lower()


# ── check 6: new probe-path candidates ───────────────────────────────────────

def test_candidates_are_assoc_paths_not_already_blocked_ordered_by_count(path):
    for _ in range(2):
        ev(path, "assoc_path", p="/odd/thing", status=200)
    ev(path, "assoc_path", p="/roast", status=200)
    ev(path, "assoc_path", p="/", status=200)                  # the homepage is never a candidate
    ev(path, "assoc_path", p="/wp-admin/x", status=200)        # already covered by the blocklist
    r = run(path)
    assert r.candidates == [("/odd/thing", 2), ("/roast", 1)]
    assert r.status == "review" and "/odd/thing" in texts(r)


def test_previously_reported_candidates_are_not_reported_again(path):
    ev(path, "assoc_path", p="/odd/thing", status=200)
    assert run(path).candidates == [("/odd/thing", 1)]
    again = run(path)
    assert again.candidates == [] and again.status == "clean"


# ── canary_probe ─────────────────────────────────────────────────────────────

def _fetcher(overrides=None, seen=None):
    overrides = overrides or {}

    def fetch(host, p, headers):
        if seen is not None:
            seen.append((host, p, dict(headers)))
        return overrides.get(p, (404, "application/json", b'{"detail":"Not Found"}'))
    return fetch


def test_canary_is_clean_when_every_probe_is_refused():
    assert scan.canary_probe(["zeusbeats.com"], fetch=_fetcher()) == []


def test_canary_probes_each_host_with_the_canary_header():
    seen = []
    scan.canary_probe(["a.example", "b.example"], fetch=_fetcher(seen=seen))
    hosts = {h for h, _, _ in seen}
    paths = {p for _, p, _ in seen}
    assert hosts == {"a.example", "b.example"}
    assert {"/.git/config", "/.env", "/wp-admin", "/../app/requirements.txt"} <= paths
    assert all(hd.get("X-Security-Canary") == bot_guard.canary_token() for _, _, hd in seen)


def test_canary_flags_a_200_on_a_blocked_path():
    (f,) = scan.canary_probe(["zeusbeats.com"], fetch=_fetcher({"/.git/config": (200, "text/html", b"<html>")}))
    assert f.level == "critical" and "/.git/config" in f.text and "zeusbeats.com" in f.text


def test_canary_flags_a_traversal_that_returns_a_real_file():
    (f,) = scan.canary_probe(["zeusbeats.com"], fetch=_fetcher(
        {"/../app/requirements.txt": (200, "text/plain", b"fastapi>=0.115.0\nuvicorn")}))
    assert f.level == "critical" and "traversal" in f.text.lower()


def test_canary_does_not_cry_wolf_when_traversal_returns_the_html_shell():
    assert scan.canary_probe(["zeusbeats.com"], fetch=_fetcher(
        {"/../app/requirements.txt": (200, "text/html; charset=utf-8", b"<!doctype html>")})) == []


def test_an_unreachable_host_is_a_review_finding_not_a_crash():
    def fetch(host, p, headers):
        raise OSError("connection refused")
    findings = scan.canary_probe(["zeusbeats.com"], fetch=fetch)
    assert findings and all(f.level == "review" for f in findings)
    assert "could not reach" in findings[0].text.lower()


# ── run_if_due ───────────────────────────────────────────────────────────────

def test_run_if_due_runs_first_time_sends_and_prunes_old_events(path):
    store.insert_events(path, [(ts(days_ago=40), "1.2.3.4", "blocked_path", "/old", 404, None)])
    sent = []
    r = scan.run_if_due(now=NOW, db_path=path, canary=clean_canary, send=sent.append)
    assert r is not None and len(sent) == 1 and "Security scan clean" in sent[0]
    assert store.count_events(path, "blocked_path", NOW - timedelta(days=365)) == 0


def test_run_if_due_waits_three_days_with_an_hour_of_slack(path):
    scan.run_if_due(now=NOW, db_path=path, canary=clean_canary, send=lambda m: None)
    sent = []
    assert scan.run_if_due(now=NOW + timedelta(days=2), db_path=path, canary=clean_canary, send=sent.append) is None
    # A daily 09:30 job sees 2d23h59m55s and must still run, or the scan drifts to every 4 days.
    almost = NOW + timedelta(days=3) - timedelta(seconds=5)
    assert scan.run_if_due(now=almost, db_path=path, canary=clean_canary, send=sent.append) is not None
    assert len(sent) == 1


def test_a_manual_scan_does_not_reset_the_scheduled_clock(path):
    scan.run_scan(path, trigger="manual", now=NOW, canary=clean_canary)
    assert scan.run_if_due(now=NOW, db_path=path, canary=clean_canary, send=lambda m: None) is not None


# ── weekly summary ───────────────────────────────────────────────────────────

def _blocks(path_):
    store.add_blocked_ip(path_, "45.13.7.2", "5 probe attempts", now=NOW - timedelta(days=2))
    store.add_blocked_ip(path_, "45.13.7.3", "scanner tool sqlmap", now=NOW - timedelta(days=1))
    store.add_blocked_ip(path_, "45.13.7.4", "5 probe attempts", now=NOW - timedelta(days=1))
    store.add_blocked_ip(path_, "45.13.7.9", "old", now=NOW - timedelta(days=20))


def test_weekly_summary_lists_blocks_paths_and_a_clean_bill_of_health(path):
    _blocks(path)
    for _ in range(3):
        ev(path, "blocked_path", p="/.git/config", days_ago=2)
    ev(path, "blocked_path", p="/wp-login.php", days_ago=1)
    text, health = scan.weekly_summary(path, now=NOW)
    assert health == "clean" and "✅" in text
    assert "3" in text and "5 probe attempts" in text and "scanner tool sqlmap" in text
    assert "/.git/config" in text and "/wp-login.php" in text
    assert "45.13.7.9" not in text


def test_weekly_summary_needs_review_when_something_slipped(path):
    ev(path, "blocked_path_200", p="/.env", status=200, days_ago=1)
    text, health = scan.weekly_summary(path, now=NOW)
    assert health == "review" and "⚠️" in text


def test_weekly_summary_carries_the_weeks_scan_findings_as_new_threats(path):
    scan.run_scan(path, trigger="scheduled", now=NOW - timedelta(days=2),
                  canary=lambda: [scan.Finding("critical", "canary: X returned 200")])
    text, health = scan.weekly_summary(path, now=NOW)
    assert health == "review" and "canary: X returned 200" in text


def test_weekly_is_sent_on_mondays_only_and_only_once_a_week(path):
    sent = []
    tuesday = NOW + timedelta(days=1)
    assert scan.send_weekly_if_due(now=tuesday, db_path=path, send=sent.append) is False
    assert scan.send_weekly_if_due(now=NOW, db_path=path, send=sent.append) is True
    assert scan.send_weekly_if_due(now=NOW + timedelta(hours=3), db_path=path, send=sent.append) is False
    assert len(sent) == 1 and "Weekly security summary" in sent[0]
    assert scan.send_weekly_if_due(now=NOW + timedelta(days=7), db_path=path, send=sent.append) is True
