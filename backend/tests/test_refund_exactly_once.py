"""A charged song is refunded exactly once — never more, never for a free retry.

Found 2026-09-27: a new free user (3 credits) ended on 10. Her custom lyrics were
refused by Apiframe ("copyrighted material") four times, and every failure paid out
up to three refunds for one charge:
  1. the Apiframe FAILED webhook refunded the original — fine;
  2. the ops agent retried it as a new, uncharged variant; that retry failed too and
     the webhook refunded IT as well;
  3. the ops agent then refunded the original AGAIN ("retry also failed — refunding");
  4. a duplicate failed webhook re-ran the retry logic → another retry → more refunds.
The admin `refund failures` command could add a fourth refund on top: it only skips
rows with refunded_at set, and no automatic refund ever set it.

What must hold now (one gate: db.refund_song_credit_once, keyed on refunded_at):
  * the charged original is refunded once, whichever path gets there first/again
  * a retry is never refunded itself — its failure refunds the original
  * no refund while a retry is still in flight (a retry that succeeds = no refund)
  * a content-policy refusal is refunded at once and NOT retried — it can't succeed
  * a duplicate failure notice changes nothing
  * an uncharged song (admin) is never "refunded"
"""
import os
import pathlib
import sqlite3
import sys
import threading
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))
os.environ.setdefault("ANTHROPIC_API_KEY", "test-key")
os.environ.setdefault("APIFRAME_API_KEY", "test-key")
os.environ.setdefault("SONG_STORAGE_PATH", "/tmp/test_songs")
os.environ.setdefault("SONG_PUBLIC_BASE_URL", "https://example.com/files/songs")
os.environ.setdefault("SONG_WEBHOOK_URL", "https://zeusaidesign.com/webhooks/apiframe")
os.environ.setdefault("JWT_SECRET", "test-secret-for-refund-once-tests")

import db as _db  # noqa: E402

COPYRIGHT = "Your lyrics contain copyrighted material. Please change it and try again."
TRANSIENT = "Suno render error: internal timeout"
START = 5   # balance AFTER the original song was charged


def _setup(tmp_path, credit_charged=1, balance=START):
    p = tmp_path / "refund.db"
    _db.init_user_tables(p)
    u = _db.create_user(p, email="refund@test.co", password_hash="x", name="Rae Fund", tc_accepted_at="n")
    conn = _db._conn(p)
    try:
        conn.execute("INSERT OR REPLACE INTO song_credits (user_id, balance, monthly_allowance) VALUES (?, ?, 0)",
                     (u["id"], balance))
        conn.execute("INSERT INTO lyrics (id,user_id,title,brief,lyrics_text,created_at) "
                     "VALUES (1,?,'T','b','la la',datetime('now'))", (u["id"],))
        conn.execute("INSERT INTO song_variants (id,lyric_id,user_id,style_prompt,genre_tag,status,take_number,credit_charged) "
                     "VALUES (1,1,?,'blues rock','bluesrock','generating',1,?)", (u["id"], credit_charged))
        conn.commit()
    finally:
        conn.close()
    return p, u


def _balance(p, uid):
    c = sqlite3.connect(str(p))
    try:
        return c.execute("SELECT balance FROM song_credits WHERE user_id=?", (uid,)).fetchone()[0]
    finally:
        c.close()


def _variants(p):
    c = sqlite3.connect(str(p))
    c.row_factory = sqlite3.Row
    try:
        return {r["id"]: dict(r) for r in c.execute(
            "SELECT id, status, retry_of, credit_charged, refunded_at FROM song_variants ORDER BY id")}
    finally:
        c.close()


class _Harness:
    """Real webhook endpoint + real ops agent; only outbound HTTP/email are fakes."""

    def __init__(self, p, retry_submit_fails=False):
        import webhooks as wh
        import zeus_ops_agent as ops
        import main
        self.p = p
        self.emails = []
        self.retry_posts = 0

        def fake_post(*a, **kw):
            if retry_submit_fails:
                raise RuntimeError("apiframe down")
            self.retry_posts += 1
            r = MagicMock()
            r.raise_for_status.return_value = None
            r.json.return_value = {"jobId": f"retry-job-{self.retry_posts}"}
            return r

        self._patches = [
            patch.object(wh, "DB_PATH", str(p)),
            patch.object(ops, "_db", return_value=str(p)),
            patch.object(ops.requests, "post", side_effect=fake_post),
            patch.object(ops, "_send_failure_email",
                         side_effect=lambda email, vid, name="", **kw: self.emails.append((vid, kw))),
            patch("alerts.alert_song_failed"),
        ]
        for pt in self._patches:
            pt.start()
        self.client = TestClient(main.app)

    def fail(self, vid, error=TRANSIENT):
        r = self.client.post(f"/webhooks/apiframe?variant_id={vid}", json={"event": "failed", "error": error})
        assert r.status_code == 200, r.text
        return r.json()

    def retry_id(self, of):
        return next(v["id"] for v in _variants(self.p).values() if v["retry_of"] == of)

    def close(self):
        for pt in reversed(self._patches):
            pt.stop()


@pytest.fixture
def harness_factory():
    made = []

    def make(p, **kw):
        h = _Harness(p, **kw)
        made.append(h)
        return h
    yield make
    for h in made:
        h.close()


# ── The reported case, end to end ────────────────────────────────────────────

def test_failure_then_failed_retry_refunds_exactly_one_credit(tmp_path, harness_factory):
    p, u = _setup(tmp_path)
    h = harness_factory(p)

    h.fail(1)
    assert _balance(p, u["id"]) == START, "no refund while the free retry is still in flight"
    rid = h.retry_id(1)
    v = _variants(p)[rid]
    assert v["credit_charged"] == 0 and v["status"] == "generating"

    h.fail(rid)
    assert _balance(p, u["id"]) == START + 1
    vs = _variants(p)
    assert vs[1]["refunded_at"] is not None, "the refund is recorded on the charged original"
    assert vs[rid]["refunded_at"] is None, "the free retry is never refunded itself"
    assert len(h.emails) == 1


def test_duplicate_failure_notices_change_nothing(tmp_path, harness_factory):
    """Apiframe re-sent a failed webhook for the same variant on 2026-09-27."""
    p, u = _setup(tmp_path)
    h = harness_factory(p)

    h.fail(1)
    h.fail(1)                      # duplicate before the retry resolves
    assert h.retry_posts == 1, "a duplicate notice must not launch a second retry"
    rid = h.retry_id(1)
    h.fail(rid)
    h.fail(rid)                    # duplicate for the retry
    h.fail(1)                      # and a late one for the original
    assert h.retry_posts == 1
    assert _balance(p, u["id"]) == START + 1
    assert len(h.emails) == 1


def test_content_policy_refusal_is_refunded_once_and_not_retried(tmp_path, harness_factory):
    p, u = _setup(tmp_path)
    h = harness_factory(p)

    h.fail(1, error=COPYRIGHT)
    assert h.retry_posts == 0, "a refusal cannot succeed on retry — don't spend on it"
    assert not any(v["retry_of"] for v in _variants(p).values())
    assert _balance(p, u["id"]) == START + 1
    assert len(h.emails) == 1
    assert h.emails[0][1].get("reason") == "content_refusal"
    h.fail(1, error=COPYRIGHT)
    assert _balance(p, u["id"]) == START + 1


@pytest.mark.parametrize("msg", [
    COPYRIGHT,
    "Lyrics contain copyrighted content",
    "Prompt contains inappropriate content",
    "The prompt includes sensitive words",
    "Request violates our content policy",
    "Artist names are not allowed in the style",
])
def test_known_refusal_wordings_are_recognised(msg):
    import zeus_ops_agent as ops
    assert ops.is_content_refusal(msg)


@pytest.mark.parametrize("msg", [None, "", TRANSIENT, "unknown error", "Service temporarily unavailable", "Timeout"])
def test_ordinary_failures_are_not_refusals(msg):
    import zeus_ops_agent as ops
    assert not ops.is_content_refusal(msg)


def test_retry_that_is_still_running_is_not_refunded(tmp_path, harness_factory):
    """If the retry goes on to succeed the user got their song — so no refund."""
    p, u = _setup(tmp_path)
    h = harness_factory(p)
    h.fail(1)
    assert _balance(p, u["id"]) == START
    assert _variants(p)[1]["refunded_at"] is None


def test_retry_submission_failure_refunds_once(tmp_path, harness_factory):
    p, u = _setup(tmp_path)
    h = harness_factory(p, retry_submit_fails=True)
    h.fail(1)
    h.fail(1)
    assert _balance(p, u["id"]) == START + 1
    assert len(h.emails) == 1


def test_uncharged_song_is_never_refunded(tmp_path, harness_factory):
    """Admins aren't charged — they were still getting +3 per failed song."""
    p, u = _setup(tmp_path, credit_charged=0)
    h = harness_factory(p)
    h.fail(1)
    h.fail(h.retry_id(1))
    assert _balance(p, u["id"]) == START
    assert h.emails == [], "the email says 'credit refunded' — don't send it when nothing was"


def test_song_created_before_this_fix_counts_as_charged(tmp_path, harness_factory):
    p, u = _setup(tmp_path, credit_charged=None)
    h = harness_factory(p)
    h.fail(1, error=COPYRIGHT)
    assert _balance(p, u["id"]) == START + 1


def test_other_failure_shapes_also_refund_once(tmp_path, harness_factory):
    """no_result / no_tracks branches, then the sweeper and a FAILED webhook on top."""
    import zeus_ops_agent as ops
    p, u = _setup(tmp_path)
    h = harness_factory(p)
    r = h.client.post("/webhooks/apiframe?variant_id=1", json={"event": "completed", "status": "COMPLETED"})
    assert r.status_code == 200
    h.fail(1)
    ops._fix_stuck_songs()
    assert _balance(p, u["id"]) == START + 1


# ── The single gate ──────────────────────────────────────────────────────────

def test_refund_once_is_idempotent_and_resolves_retries(tmp_path):
    p, u = _setup(tmp_path)
    c = sqlite3.connect(str(p))
    c.execute("INSERT INTO song_variants (id,lyric_id,user_id,style_prompt,genre_tag,status,take_number,retry_of,credit_charged) "
              "VALUES (2,1,?,'s','g','failed',1,1,0)", (u["id"],))
    c.commit()
    c.close()
    assert _db.refund_song_credit_once(p, 2, "test") is True     # retry → pays back the original
    assert _db.refund_song_credit_once(p, 1, "test") is False
    assert _db.refund_song_credit_once(p, 2, "test") is False
    assert _db.refund_song_credit_once(p, 999, "test") is False  # unknown variant
    assert _balance(p, u["id"]) == START + 1


def test_concurrent_refunds_pay_out_once(tmp_path):
    p, u = _setup(tmp_path)
    results = []
    barrier = threading.Barrier(8)

    def go():
        barrier.wait()
        results.append(_db.refund_song_credit_once(p, 1, "race"))
    threads = [threading.Thread(target=go) for _ in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert results.count(True) == 1
    assert _balance(p, u["id"]) == START + 1


# ── Every other refund path goes through the gate ────────────────────────────

def test_stuck_sweeper_refunds_a_stuck_retry_against_its_original_once(tmp_path, harness_factory):
    import zeus_ops_agent as ops
    p, u = _setup(tmp_path)
    h = harness_factory(p)
    h.fail(1)
    rid = h.retry_id(1)
    c = sqlite3.connect(str(p))
    c.execute("UPDATE song_variants SET created_at=datetime('now','-30 minutes') WHERE id=?", (rid,))
    c.commit()
    c.close()
    ops._fix_stuck_songs()
    ops._fix_stuck_songs()
    h.fail(rid)                     # the lost webhook turns up late
    assert _balance(p, u["id"]) == START + 1
    assert _variants(p)[rid]["status"] == "failed"


def test_admin_refund_failures_command_skips_already_refunded_songs(tmp_path, harness_factory):
    import telegram_admin
    p, u = _setup(tmp_path)
    h = harness_factory(p)
    h.fail(1, error=COPYRIGHT)
    assert _balance(p, u["id"]) == START + 1
    with patch.object(_db, "get_db_path", return_value=p):
        telegram_admin._cmd_refund_failures()
    assert _balance(p, u["id"]) == START + 1, "the manual command must not pay the same song twice"


def test_admin_refund_failures_command_never_pays_for_a_retry(tmp_path):
    import telegram_admin
    p, u = _setup(tmp_path)
    c = sqlite3.connect(str(p))
    c.execute("UPDATE song_variants SET status='failed', refunded_at=datetime('now') WHERE id=1")
    c.execute("INSERT INTO song_variants (id,lyric_id,user_id,style_prompt,genre_tag,status,take_number,retry_of,credit_charged) "
              "VALUES (2,1,?,'s','g','failed',1,1,0)", (u["id"],))
    c.commit()
    c.close()
    with patch.object(_db, "get_db_path", return_value=p):
        telegram_admin._cmd_refund_failures()
    assert _balance(p, u["id"]) == START


def test_every_new_variant_row_records_whether_it_was_charged():
    """NULL means 'from before this fix' and is treated as charged; new rows must say."""
    import re
    backend = pathlib.Path(__file__).resolve().parent.parent
    missing = []
    for name in ("main.py", "songs.py", "webhooks.py", "zeus_ops_agent.py"):
        src = (backend / name).read_text(encoding="utf-8")
        for m in re.finditer(r"INSERT INTO song_variants", src):
            stmt = src[m.start():m.start() + 600]
            if "credit_charged" not in stmt:
                missing.append(f"{name}:{src.count(chr(10), 0, m.start()) + 1}")
    assert missing == [], f"INSERT INTO song_variants without credit_charged: {missing}"


# ── Each layer on its own (mutation-tested: the layers above can mask each other) ─

def test_a_late_failure_notice_never_unfails_a_delivered_song(tmp_path, harness_factory):
    p, u = _setup(tmp_path)
    c = sqlite3.connect(str(p))
    c.execute("UPDATE song_variants SET status='complete' WHERE id=1")
    c.commit()
    c.close()
    h = harness_factory(p)
    h.fail(1)
    assert _variants(p)[1]["status"] == "complete"
    assert _balance(p, u["id"]) == START
    assert h.retry_posts == 0


def test_a_duplicate_failure_notice_alerts_once(tmp_path, harness_factory):
    import alerts
    p, u = _setup(tmp_path)
    h = harness_factory(p)
    h.fail(1)
    h.fail(1)
    assert alerts.alert_song_failed.call_count == 1


def test_the_failure_handler_retries_an_original_only_once(tmp_path, harness_factory):
    """Even if something bypasses the claim, a second call must not retry again."""
    import zeus_ops_agent as ops
    p, u = _setup(tmp_path)
    h = harness_factory(p)
    ops.on_song_failed(1, TRANSIENT)
    ops.on_song_failed(1, TRANSIENT)
    assert h.retry_posts == 1
    assert _balance(p, u["id"]) == START


def test_stuck_sweeper_never_refunds_an_uncharged_song(tmp_path, harness_factory):
    import zeus_ops_agent as ops
    p, u = _setup(tmp_path, credit_charged=0)
    harness_factory(p)
    c = sqlite3.connect(str(p))
    c.execute("UPDATE song_variants SET created_at=datetime('now','-30 minutes') WHERE id=1")
    c.commit()
    c.close()
    ops._fix_stuck_songs()
    assert _variants(p)[1]["status"] == "failed"
    assert _balance(p, u["id"]) == START
