"""Stuck-song recovery must run at the cadence it tests for.

_fix_stuck_songs() has always used a 15-minute threshold, but its only caller was
health_check — a daily 09:00 cron. Intent and cadence disagreed by a factor of 96,
so a song whose provider webhook was lost at 20:41 stayed "generating" until 09:00
the next morning: the user's credit held, the UI polling it the whole time. That is
what happened to variants 1621/1622 on 2026-08-28.

This matters more than an ordinary retry gap because Apiframe v2 is webhook-only —
there is no status or fetch endpoint to poll (every documented path 404s) — so a
dropped callback is unrecoverable and this sweep is the ONLY thing that ever ends a
stuck song.

What must hold:
  * the sweep is actually scheduled, at 15 minutes, or none of this runs
  * a song past the threshold is failed AND its credit returned
  * a song inside the threshold is left alone — it may still land
  * running twice cannot refund twice
  * a completed song is never touched
"""
import inspect
import os
import pathlib
import sqlite3
import sys
from unittest.mock import patch

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))
os.environ.setdefault("ANTHROPIC_API_KEY", "test-key")
os.environ.setdefault("APIFRAME_API_KEY", "test-key")
os.environ.setdefault("SONG_WEBHOOK_URL", "https://example.com/webhooks/apiframe")

import zeus_ops_agent as ops


def _db(tmp_path, variants):
    """variants: list of (id, status, age_minutes)."""
    p = tmp_path / "sweep.db"
    c = sqlite3.connect(str(p))
    c.execute("""CREATE TABLE song_variants
                 (id INTEGER PRIMARY KEY, user_id TEXT, status TEXT, created_at TEXT)""")
    c.execute("CREATE TABLE song_credits (user_id TEXT PRIMARY KEY, balance INTEGER)")
    c.execute("INSERT INTO song_credits VALUES ('u', 10)")
    for vid, status, age in variants:
        c.execute(
            "INSERT INTO song_variants VALUES (?, 'u', ?, datetime('now', ?))",
            (vid, status, f"-{age} minutes"),
        )
    c.commit()
    c.close()
    return p


def _run(p, sweep=True):
    """Run the sweep (or the raw fixer) against a temp DB; return alerts sent."""
    sent = []
    with patch.object(ops, "_db", return_value=str(p)), \
         patch("alerts.send_admin_alert", side_effect=lambda m: sent.append(m) or True):
        if sweep:
            ops.stuck_song_sweep()
        else:
            ops._fix_stuck_songs()
    return sent


def _state(p):
    c = sqlite3.connect(str(p))
    rows = {r[0]: r[1] for r in c.execute("SELECT id, status FROM song_variants")}
    bal = c.execute("SELECT balance FROM song_credits WHERE user_id='u'").fetchone()[0]
    c.close()
    return rows, bal


# ── The wiring, without which nothing above runs ─────────────────────────────

def test_the_sweep_is_scheduled_at_fifteen_minutes():
    """The whole bug was a function that tested for 15 minutes running once a day."""
    import scheduler

    src = inspect.getsource(scheduler.init_scheduler)
    assert "stuck_song_sweep" in src, "the sweep must actually be registered to ever run"

    idx = src.index("stuck_song_sweep")
    block = src[idx:idx + 400]
    assert "IntervalTrigger(minutes=15)" in block, (
        "must run every 15 minutes — the cadence has to match the threshold "
        "_fix_stuck_songs tests for, or stuck songs sit for hours"
    )


def test_health_check_still_fixes_stuck_songs_too():
    """Belt and braces: the daily pass keeps its call. Safe because a swept row is
    already 'failed' and no longer matches its own WHERE clause."""
    assert "_fix_stuck_songs" in inspect.getsource(ops.health_check)


# ── Behaviour ────────────────────────────────────────────────────────────────

def test_a_song_past_the_threshold_is_failed_and_refunded(tmp_path):
    p = _db(tmp_path, [(1, "generating", 40)])
    sent = _run(p)
    rows, bal = _state(p)
    assert rows[1] == "failed"
    assert bal == 11, "the user's credit must come back"
    assert sent and "stuck song" in sent[0].lower()


def test_a_song_inside_the_threshold_is_left_alone(tmp_path):
    """Variant 1622 was 11 minutes old and correctly survived the manual run — a
    song can still land, and failing it early destroys work the user paid for."""
    p = _db(tmp_path, [(1, "generating", 11)])
    sent = _run(p)
    rows, bal = _state(p)
    assert rows[1] == "generating"
    assert bal == 10, "no refund for a song that may still complete"
    assert sent == [], "and nothing to report"


def test_pending_counts_as_stuck_too(tmp_path):
    p = _db(tmp_path, [(1, "pending", 40)])
    _run(p)
    rows, bal = _state(p)
    assert rows[1] == "failed" and bal == 11


def test_running_twice_does_not_refund_twice(tmp_path):
    """health_check and the 15-min sweep both call this; overlap must be harmless."""
    p = _db(tmp_path, [(1, "generating", 40)])
    _run(p)
    _run(p)
    rows, bal = _state(p)
    assert rows[1] == "failed"
    assert bal == 11, "a second pass must not hand out another credit"


def test_completed_songs_are_never_touched(tmp_path):
    p = _db(tmp_path, [(1, "complete", 999), (2, "failed", 999)])
    sent = _run(p)
    rows, bal = _state(p)
    assert rows == {1: "complete", 2: "failed"}
    assert bal == 10
    assert sent == []


def test_a_mixed_batch_only_sweeps_the_stale_ones(tmp_path):
    p = _db(tmp_path, [(1, "generating", 40), (2, "generating", 3), (3, "complete", 40)])
    _run(p)
    rows, bal = _state(p)
    assert rows == {1: "failed", 2: "generating", 3: "complete"}
    assert bal == 11, "exactly one refund"


def test_a_failed_alert_does_not_crash_the_sweep(tmp_path):
    """The scheduler thread must survive a Telegram outage."""
    p = _db(tmp_path, [(1, "generating", 40)])
    with patch.object(ops, "_db", return_value=str(p)), \
         patch("alerts.send_admin_alert", side_effect=RuntimeError("telegram down")):
        ops.stuck_song_sweep()          # must not raise
    rows, _ = _state(p)
    assert rows[1] == "failed", "the refund still happened even though the alert failed"
