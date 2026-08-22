"""Discover → Porickbot alert.

Reads COALESCE(shared_at, created_at) — the same signal /api/discover/new-count
uses for the badge — so the alert and the badge can never disagree about what
counts as new. That shared signal is why shared_at was added rather than letting
each feature invent its own proxy.

The properties pinned here:
  * first run seeds and stays silent (otherwise it announces all 145 existing
    public songs at once)
  * each song alerts exactly once, across restarts
  * bursts batch into one message rather than N pings
  * an undelivered alert leaves the songs pending, so it retries
  * progress is per row, so two songs shared in the same second cannot collide
"""
import os
import pathlib
import sqlite3
import sys
import tempfile
import time
from unittest.mock import patch

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))
os.environ.setdefault("ANTHROPIC_API_KEY", "test-key")
os.environ.setdefault("APIFRAME_API_KEY", "test-key")
os.environ.setdefault("SONG_WEBHOOK_URL", "https://example.com/webhooks/apiframe")

import db as _db
import zeus_ops_agent as ops

def _env():
    p = pathlib.Path(tempfile.mkdtemp()) / "disc.db"
    _db.init_user_tables(p)
    c = sqlite3.connect(str(p))
    c.execute("""INSERT INTO users (id,email,password_hash,name,artist_name,tc_accepted_at,created_at,updated_at)
                 VALUES ('u','a@b.c','x','Ada','bassline rowles','t','t','t')""")
    c.commit()
    return p, c


def _share(c, n, title="Song"):
    c.execute("INSERT INTO lyrics (id,user_id,brief,lyrics_text,title) VALUES (?,'u','b','l',?)", (n, title))
    c.execute("""INSERT INTO song_variants (id,lyric_id,user_id,style_prompt,genre_tag,status,mp3_url,is_public)
                 VALUES (?,?,'u','s','jungle','complete','m.mp3',0)""", (n, n))
    c.execute("UPDATE song_variants SET is_public = 1 WHERE id = ?", (n,))   # trigger stamps shared_at
    c.commit()


def _run(p, delivered=True):
    sent = []
    with patch.object(_db, "get_db_path", return_value=p), \
         patch("alerts.send_admin_alert", side_effect=lambda m: (sent.append(m), delivered)[1]):
        ops.discover_monitor()
    return sent


def test_first_run_seeds_and_stays_silent():
    """Otherwise the very first run announces every song already on Discover."""
    p, c = _env()
    _share(c, 10, "Already Shared")
    assert _run(p) == []
    assert _db.discover_alerts_initialised(p), "existing songs must be marked as seen"


def test_nothing_new_sends_nothing():
    p, c = _env()
    _share(c, 10)
    _run(p)
    assert _run(p) == []


def test_newly_shared_songs_alert_once_and_batch():
    p, c = _env()
    _share(c, 10)
    _run(p)                                   # seed
    time.sleep(1.1)                           # CURRENT_TIMESTAMP is second-resolution
    _share(c, 11, "Selector Gamble")
    _share(c, 12, "Amen Break")

    sent = _run(p)
    assert len(sent) == 1, "a burst must batch into one message, not one per song"
    msg = sent[0]
    assert "2 new on Discover" in msg
    assert "Selector Gamble" in msg and "Amen Break" in msg
    assert "bassline rowles" in msg
    assert "/discover/11" in msg and "/discover/12" in msg


def test_a_song_never_alerts_twice():
    p, c = _env()
    _share(c, 10); _run(p)
    time.sleep(1.1); _share(c, 11, "New One")
    assert len(_run(p)) == 1
    assert _run(p) == [], "re-running must not re-announce the same song"


def test_undelivered_alert_leaves_songs_pending():
    """A repeat ping beats a silent miss."""
    p, c = _env()
    _share(c, 10); _run(p)
    time.sleep(1.1); _share(c, 11, "New One")

    _run(p, delivered=False)
    pending = _db.get_unalerted_discover_songs(p)
    assert [x["variant_id"] for x in pending] == [11], "failed send must leave the song pending"
    # ...and the next successful run still catches it
    assert len(_run(p)) == 1


def test_a_song_shared_mid_run_is_not_skipped():
    """A song shared while the alert is in flight must still be announced.

    This is what killed the timestamp-watermark design: shared_at has one-second
    resolution, so the mid-run song usually carries the SAME second as the one being
    announced, and a `> watermark` comparison then drops it forever. Per-row marking
    only ever stamps the rows actually listed, so the straggler stays pending.
    """
    p, c = _env()
    _share(c, 10); _run(p)                     # seed
    time.sleep(1.1)
    _share(c, 11, "First")

    def _alert_and_race(_msg):
        # A user shares another song while the alert is going out.
        _share(c, 12, "Slipped In")
        return True

    with patch.object(_db, "get_db_path", return_value=p), \
         patch("alerts.send_admin_alert", side_effect=_alert_and_race):
        ops.discover_monitor()

    later = _run(p)
    assert len(later) == 1, "the mid-run song must still be announced"
    assert "Slipped In" in later[0]


def test_progress_persists_across_a_restart():
    """ph_monitor keeps its equivalent state in a module global, which resets on every
    deploy. Deploys are frequent enough that in-memory state would drop alerts."""
    p, c = _env()
    _share(c, 10); _run(p)
    time.sleep(1.1); _share(c, 11); _run(p)
    import importlib
    importlib.reload(ops)                      # simulate a fresh process
    assert _db.get_unalerted_discover_songs(p) == []
    assert _run(p) == [], "state survived the restart, so nothing re-fires"


def test_private_songs_never_alert():
    p, c = _env()
    _share(c, 10); _run(p)
    time.sleep(1.1)
    c.execute("INSERT INTO lyrics (id,user_id,brief,lyrics_text,title) VALUES (99,'u','b','l','Private')")
    c.execute("""INSERT INTO song_variants (id,lyric_id,user_id,style_prompt,genre_tag,status,mp3_url,is_public)
                 VALUES (99,99,'u','s','jungle','complete','m.mp3',0)""")
    c.commit()
    assert _run(p) == []


def test_large_burst_is_capped_with_an_overflow_line():
    p, c = _env()
    _share(c, 10); _run(p)
    time.sleep(1.1)
    for n in range(20, 20 + ops._DISCOVER_MAX_LISTED + 3):
        _share(c, n, f"Song {n}")

    shared_ids = list(range(20, 20 + ops._DISCOVER_MAX_LISTED + 3))

    sent = _run(p)
    assert len(sent) == 1
    assert "more" in sent[0], "overflow must be stated, not silently truncated"
    assert len(sent[0]) < 4096, "Telegram would reject an over-long message"

    # Drain, then assert EVERY song was named exactly once somewhere. Only the LISTED
    # songs may be marked: the query fetches MAX_LISTED + 1, so marking the whole
    # fetched set silently swallows that one extra — it is counted in "…and N more"
    # and then never named in any run. Counting per-song is the only way to see it.
    for _ in range(5):
        more = _run(p)
        if not more:
            break
        sent.extend(more)

    combined = "\n".join(sent)
    named = [vid for vid in shared_ids if f"/discover/{vid}" in combined]
    assert named == shared_ids, (
        f"every shared song must be named exactly once; missing "
        f"{sorted(set(shared_ids) - set(named))}"
    )
    assert _db.get_unalerted_discover_songs(p) == [], "queue must drain fully"


def test_registered_on_the_scheduler():
    import inspect
    import scheduler
    src = inspect.getsource(scheduler.init_scheduler)
    assert "discover_monitor" in src, "the job must actually be scheduled to ever run"
