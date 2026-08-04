"""Porick usage-insight commands (2026-08-04).

Added so Michael can see what testers are actually doing: `active`, `activity`,
`prompts`, `user_songs <email>`, plus a widened `top_genres`.

Two things these tests exist to protect:

1. MIXED TIMESTAMP FORMATS. song_variants.created_at comes from the schema
   default CURRENT_TIMESTAMP ("2026-08-04 12:00:00") while users.created_at is
   written by Python .isoformat() ("2026-08-04T12:00:00.123456+00:00"). Comparing
   the ISO form straight against datetime('now', ...) misreads the boundary day,
   because 'T' sorts after ' '. The queries normalise with replace(...,'T',' ').

2. HTML ESCAPING. Prompts are free text written by users and are rendered into an
   HTML-parsed Telegram message. One unescaped '<' breaks the entire send.
"""
import os
import pathlib
import sys
import tempfile
from datetime import datetime, timedelta, timezone

import pytest

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))
os.environ.setdefault("ANTHROPIC_API_KEY", "test-key")
os.environ.setdefault("APIFRAME_API_KEY", "test-key")
os.environ.setdefault("SONG_STORAGE_PATH", "/tmp/test_songs")
os.environ.setdefault("SONG_PUBLIC_BASE_URL", "https://example.com/files/songs")
os.environ.setdefault("SONG_WEBHOOK_URL", "https://zeusaidesign.com/webhooks/apiframe")
os.environ.setdefault("JWT_SECRET", "test-secret-for-porick-tests")

_HOSTILE = 'a <script>alert(1)</script> "banger" & more'


@pytest.fixture()
def seeded(tmp_path, monkeypatch):
    """3 users: one active today, one active 5 and 20 days ago, one who never
    created anything."""
    monkeypatch.setenv("ZEUS_DATA_DIR", str(tmp_path))
    import importlib
    import db as _db
    importlib.reload(_db)
    import telegram_admin as _T
    importlib.reload(_T)

    p = _db.get_db_path()
    now = datetime.now(timezone.utc)
    alice = _db.create_user(p, email="alice@example.com", password_hash="x", name="A", tc_accepted_at="n")
    bob = _db.create_user(p, email="bob@example.com", password_hash="x", name="B", tc_accepted_at="n")
    _db.create_user(p, email="carol@example.com", password_hash="x", name="C", tc_accepted_at="n")

    conn = _db._conn(p)
    try:
        def add(uid, brief, genre, status, days_ago):
            ts = (now - timedelta(days=days_ago)).strftime("%Y-%m-%d %H:%M:%S")
            conn.execute(
                "INSERT INTO lyrics (user_id,title,brief,lyrics_text,created_at) VALUES (?,?,?,?,?)",
                (uid, "T", brief, "la", ts))
            lid = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
            conn.execute(
                """INSERT INTO song_variants (lyric_id,user_id,genre_tag,style_prompt,take_number,
                                              status,duration_seconds,created_at)
                   VALUES (?,?,?,'s',1,?,120,?)""", (lid, uid, genre, status, ts))

        add(alice["id"], _HOSTILE, "grime", "complete", 0)
        add(alice["id"], "sad piano ballad about my dog", "niche", "failed", 0)
        add(bob["id"], "uplifting gospel choir number", "gospel", "complete", 5)
        add(bob["id"], "old drill track", "ukdrill", "complete", 20)
        conn.commit()
    finally:
        conn.close()
    return _T


# ── active ───────────────────────────────────────────────────────────────────

def test_active_separates_signups_from_real_usage(seeded):
    out = seeded._cmd_active()
    assert "Signed up: <b>3</b>" in out
    assert "Ever made a song: <b>2</b>" in out
    assert "1 signed up but never made a song" in out


def test_active_windows_are_correct_across_timestamp_formats(seeded):
    """The regression this guards: alice is inside 24h, bob only inside 7d/30d."""
    out = seeded._cmd_active()
    assert "Last 24h: <b>1</b>" in out
    assert "Last 7 days: <b>2</b>" in out
    assert "Last 30 days: <b>2</b>" in out


def test_active_states_it_covers_every_platform(seeded):
    """There is no per-platform column; the totals are all clients combined and
    the message must say so, or the number reads as web-only."""
    assert "web + Android + iOS" in seeded._cmd_active()


def test_active_counts_attempts_not_just_completions(seeded):
    """alice's second song failed — she is still an active user."""
    out = seeded._cmd_active()
    assert "Total: <b>4</b>" in out and "3 completed" in out


# ── activity / prompts / user_songs ──────────────────────────────────────────

def test_activity_shows_who_what_and_when(seeded):
    out = seeded._cmd_activity(10)
    assert "alice" in out and "grime" in out
    assert "bob" in out and "gospel" in out


def test_activity_shows_failed_songs_too(seeded):
    assert "❌" in seeded._cmd_activity(10)


def test_prompts_surface_what_users_typed(seeded):
    out = seeded._cmd_prompts(10)
    assert "sad piano ballad about my dog" in out
    assert "uplifting gospel choir number" in out


def test_prompts_escape_hostile_user_text(seeded):
    """One unescaped '<' would break the whole Telegram send."""
    out = seeded._cmd_prompts(10)
    assert "<script>" not in out
    assert "&lt;script&gt;" in out


def test_user_songs_is_case_insensitive_and_summarises(seeded):
    out = seeded._cmd_user_songs("ALICE@EXAMPLE.COM")
    assert "alice@example.com" in out
    assert "Songs: <b>2</b>" in out
    assert "grime" in out


def test_user_songs_escapes_prompts_too(seeded):
    out = seeded._cmd_user_songs("alice@example.com")
    assert "<script>" not in out


def test_user_songs_handles_unknown_email(seeded):
    assert "No user found" in seeded._cmd_user_songs("nobody@example.com")


# ── top_genres ───────────────────────────────────────────────────────────────

def test_top_genres_defaults_to_all_time(seeded):
    """Previously 7-days-and-complete-only, which reads as no-data on a small
    tester group and hides the 20-day-old drill track entirely."""
    out = seeded._cmd_top_genres()
    assert "all time" in out
    assert "ukdrill" in out


def test_top_genres_can_still_narrow_to_a_window(seeded):
    out = seeded._cmd_top_genres(15, 7)
    assert "last 7 days" in out
    assert "ukdrill" not in out          # 20 days old, correctly excluded


def test_top_genres_includes_attempted_not_only_completed(seeded):
    """niche was attempted once and failed — it must still show."""
    assert "niche" in seeded._cmd_top_genres()


# ── wiring ───────────────────────────────────────────────────────────────────

def test_all_commands_are_dispatched_and_documented():
    import telegram_admin as T
    src = pathlib.Path(T.__file__).read_text(encoding="utf-8")
    for act in ["active", "activity", "prompts", "user_songs"]:
        assert f'if act == "{act}"' in src, f"{act} not dispatched"
        assert f'"action": "{act}"' in src, f"{act} missing from the agent prompt schema"
        assert f"- {act} —" in src, f"{act} missing from the capability list"


# ── real_users: adoption outside the founder's own circle ────────────────────

@pytest.fixture()
def circle_db(tmp_path, monkeypatch):
    """Founder + family + genuine outside users, spread over months."""
    monkeypatch.setenv("ZEUS_DATA_DIR", str(tmp_path))
    monkeypatch.delenv("INSIDER_EMAILS", raising=False)
    import importlib
    import db as _db
    importlib.reload(_db)
    import telegram_admin as _T
    importlib.reload(_T)

    p = _db.get_db_path()
    now = datetime.now(timezone.utc)
    for email, n, days_ago in [
        ("dominic.rowle@yahoo.com", 40, 120),   # founder
        ("dwrowle@gmail.com", 12, 100),         # family
        ("laky120@yahoo.com", 6, 90),           # family
        ("danielrowle@gmail.com", 4, 60),       # family
        ("sarah.jones@gmail.com", 9, 45),       # outside
        ("mike_t@hotmail.com", 2, 30),          # outside, light user
    ]:
        u = _db.create_user(p, email=email, password_hash="x", name="N", tc_accepted_at="n")
        c = _db._conn(p)
        c.execute("INSERT INTO lyrics (user_id,title,brief,lyrics_text,created_at) "
                  "VALUES (?,?,?,?,datetime('now'))", (u["id"], "T", "b", "la"))
        lid = c.execute("SELECT last_insert_rowid()").fetchone()[0]
        for i in range(n):
            ts = (now - timedelta(days=max(0, days_ago - i))).strftime("%Y-%m-%d %H:%M:%S")
            c.execute("""INSERT INTO song_variants
                         (lyric_id,user_id,genre_tag,style_prompt,take_number,status,
                          duration_seconds,created_at)
                         VALUES (?,?,'grime','s',1,'complete',120,?)""", (lid, u["id"], ts))
        c.commit()
        c.close()
    # Signed up, never created — must not be counted as a maker.
    _db.create_user(p, email="lurker@gmail.com", password_hash="x", name="L", tc_accepted_at="n")
    return _T


def test_real_users_separates_the_circle_from_genuine_adoption(circle_db):
    out = circle_db._cmd_real_users()
    assert "<b>2</b> outside" in out          # sarah + mike
    assert "4 yours" in out                   # founder + 3 family


def test_real_users_counts_songs_not_just_people(circle_db):
    """9 + 2 outside vs 40 + 12 + 6 + 4 = 62 inside."""
    out = circle_db._cmd_real_users()
    assert "<b>11</b> outside" in out
    assert "62 yours" in out


def test_real_users_covers_all_history_not_a_recent_window(circle_db):
    """The oldest outside song is 45 days old and must still be included."""
    out = circle_db._cmd_real_users()
    assert "sarah.jones" in out and "9" in out


def test_real_users_excludes_people_who_never_created(circle_db):
    assert "lurker" not in circle_db._cmd_real_users()


def test_real_users_names_who_it_excluded(circle_db):
    """The number is meaningless without knowing what was filtered out."""
    out = circle_db._cmd_real_users()
    assert "Excluding:" in out
    for tag in ["dwrowle", "laky120", "danielrowle", "dominic.rowle"]:
        assert tag in out


def test_insider_list_is_overridable_without_a_deploy(circle_db, monkeypatch):
    """Porick: var set INSIDER_EMAILS=... — family then counts as outside."""
    monkeypatch.setenv("INSIDER_EMAILS", "dominic.rowle")
    out = circle_db._cmd_real_users()
    assert "<b>5</b> outside" in out
    assert "1 yours" in out


def test_real_users_matching_is_case_insensitive(circle_db, monkeypatch):
    monkeypatch.setenv("INSIDER_EMAILS", "DOMINIC.ROWLE")
    assert "1 yours" in circle_db._cmd_real_users()


def test_real_users_is_wired_up():
    import telegram_admin as T
    src = pathlib.Path(T.__file__).read_text(encoding="utf-8")
    assert 'if act == "real_users"' in src
    assert '"action": "real_users"' in src
    assert "- real_users —" in src
