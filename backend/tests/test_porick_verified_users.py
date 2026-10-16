"""Porick `verified users` / `unverified users` commands (2026-10-16).

The users table only had an email_verified flag, never a time, so verifying now
also stamps users.verified_at (email link and Porick's verify_email both).
Users verified before that column existed have NULL there: they still count and
still list, just with "date not recorded", after everyone with a real date.
"""
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
os.environ.setdefault("JWT_SECRET", "test-secret-for-porick-tests")

NOW = datetime(2026, 10, 16, 12, 0, tzinfo=timezone.utc)


@pytest.fixture()
def env(tmp_path, monkeypatch):
    monkeypatch.setenv("ZEUS_DATA_DIR", str(tmp_path))
    import importlib
    import db as _db
    importlib.reload(_db)
    import telegram_admin as _T
    importlib.reload(_T)
    return _db, _T


def _add(db, email, *, created_days_ago, verified_days_ago=None, verified=None):
    """verified_days_ago=None + verified=True → a legacy verified user with no date."""
    p = db.get_db_path()
    u = db.create_user(p, email=email, password_hash="x", name="N", tc_accepted_at="n")
    is_verified = verified if verified is not None else verified_days_ago is not None
    v_at = (NOW - timedelta(days=verified_days_ago)).isoformat() if verified_days_ago is not None else None
    conn = db._conn(p)
    try:
        conn.execute("UPDATE users SET created_at=?, email_verified=?, verified_at=? WHERE id=?",
                     ((NOW - timedelta(days=created_days_ago)).isoformat(), int(is_verified), v_at, u["id"]))
        conn.commit()
    finally:
        conn.close()
    return u


def _lines_with(out, *emails):
    return [next(i for i, ln in enumerate(out.splitlines()) if e in ln) for e in emails]


# ── verified users ───────────────────────────────────────────────────────────

def test_verified_users_count_and_newest_verification_first(env):
    db, T = env
    _add(db, "old@example.com", created_days_ago=30, verified_days_ago=29)
    _add(db, "new@example.com", created_days_ago=40, verified_days_ago=1)
    _add(db, "mid@example.com", created_days_ago=10, verified_days_ago=9)
    _add(db, "nope@example.com", created_days_ago=0)
    out = T._cmd_verified_users()
    assert out.splitlines()[0] == "✅ 3 verified users"
    assert "nope@example.com" not in out
    a, b, c = _lines_with(out, "new@example.com", "mid@example.com", "old@example.com")
    assert a < b < c
    assert "2026-10-15 12:00" in out.splitlines()[a]


def test_verified_users_without_a_recorded_date_list_last(env):
    db, T = env
    _add(db, "legacy@example.com", created_days_ago=100, verified=True)
    _add(db, "recent@example.com", created_days_ago=50, verified_days_ago=5)
    out = T._cmd_verified_users()
    assert out.splitlines()[0] == "✅ 2 verified users"
    a, b = _lines_with(out, "recent@example.com", "legacy@example.com")
    assert a < b
    assert "date not recorded" in out.splitlines()[b]


def test_verified_users_singular_and_empty(env):
    db, T = env
    assert T._cmd_verified_users().splitlines()[0] == "✅ 0 verified users"
    _add(db, "solo@example.com", created_days_ago=3, verified_days_ago=2)
    assert T._cmd_verified_users().splitlines()[0] == "✅ 1 verified user"


# ── unverified users ─────────────────────────────────────────────────────────

def test_unverified_users_count_and_newest_signup_first(env):
    db, T = env
    _add(db, "a@example.com", created_days_ago=20)
    _add(db, "b@example.com", created_days_ago=2)
    _add(db, "done@example.com", created_days_ago=1, verified_days_ago=1)
    out = T._cmd_unverified_users()
    assert out.splitlines()[0] == "⏳ 2 unverified users"
    assert "done@example.com" not in out
    b, a = _lines_with(out, "b@example.com", "a@example.com")
    assert b < a
    assert "2026-10-14 12:00" in out.splitlines()[b]


def test_unverified_users_singular_and_empty(env):
    db, T = env
    assert T._cmd_unverified_users().splitlines()[0] == "⏳ 0 unverified users"
    _add(db, "solo@example.com", created_days_ago=3)
    assert T._cmd_unverified_users().splitlines()[0] == "⏳ 1 unverified user"


# ── pagination ───────────────────────────────────────────────────────────────

@pytest.mark.parametrize("cmd,verified,header", [("_cmd_verified_users", True, "✅ 25 verified users"),
                                                 ("_cmd_unverified_users", False, "⏳ 25 unverified users")])
def test_long_lists_show_20_then_page_2(env, cmd, verified, header):
    db, T = env
    for i in range(25):  # user00 is the newest
        _add(db, f"user{i:02d}@example.com", created_days_ago=i + 1,
             verified_days_ago=(i if verified else None))
    page1 = getattr(T, cmd)()
    assert page1.splitlines()[0] == header
    shown = [f"user{i:02d}@" for i in range(25) if f"user{i:02d}@" in page1]
    assert shown == [f"user{i:02d}@" for i in range(20)]
    assert "5 more" in page1
    word = "verified" if verified else "unverified"
    assert f"{word} users page 2" in page1

    page2 = getattr(T, cmd)(page=2)
    assert page2.splitlines()[0] == header
    assert [f"user{i:02d}@" for i in range(25) if f"user{i:02d}@" in page2] == \
           [f"user{i:02d}@" for i in range(20, 25)]
    assert "more" not in page2


def test_exactly_20_has_no_more_note(env):
    db, T = env
    for i in range(20):
        _add(db, f"u{i}@example.com", created_days_ago=i + 1)
    assert "more" not in T._cmd_unverified_users()


def test_page_past_the_end_says_so(env):
    db, T = env
    _add(db, "x@example.com", created_days_ago=1)
    out = T._cmd_unverified_users(page=3)
    assert out.splitlines()[0] == "⏳ 1 unverified user"
    assert "x@example.com" not in out
    assert "no page 3" in out.lower()


def test_emails_are_html_escaped(env):
    db, T = env
    _add(db, "a<b>@example.com", created_days_ago=1)
    out = T._cmd_unverified_users()
    assert "a&lt;b&gt;@example.com" in out and "<b>@" not in out


# ── routing: exact match, never the AI ───────────────────────────────────────

@pytest.mark.parametrize("text,fn,page", [
    ("verified users", "_cmd_verified_users", 1),
    ("Verified Users", "_cmd_verified_users", 1),
    ("porick verified users", "_cmd_verified_users", 1),
    ("verified users page 2", "_cmd_verified_users", 2),
    ("unverified users", "_cmd_unverified_users", 1),
    ("porick unverified users page 3", "_cmd_unverified_users", 3),
])
def test_parse_and_run_routes_exactly(env, monkeypatch, text, fn, page):
    _, T = env
    calls = []
    for name in ("_cmd_verified_users", "_cmd_unverified_users"):
        monkeypatch.setattr(T, name, lambda page=1, _n=name: calls.append((_n, page)) or "ok")
    monkeypatch.setattr(T, "_ai_parse", lambda *a, **k: pytest.fail("went to the AI"))
    assert T.parse_and_run(text) == "ok"
    assert calls == [(fn, page)]


def test_help_lists_both_commands(env):
    _, T = env
    assert "verified users" in T.HELP_TEXT and "unverified users" in T.HELP_TEXT


# ── verified_at is recorded ──────────────────────────────────────────────────

def _user(db, email):
    return db.get_user_by_email(db.get_db_path(), email)


def test_porick_verify_stamps_verified_at_and_unverify_clears_it(env):
    db, T = env
    _add(db, "p@example.com", created_days_ago=1)
    assert _user(db, "p@example.com")["verified_at"] is None
    assert T._cmd_db_verify_email("p@example.com").startswith("✅")
    stamped = _user(db, "p@example.com")["verified_at"]
    assert stamped and datetime.fromisoformat(stamped) > datetime.now(timezone.utc) - timedelta(minutes=1)
    assert T._cmd_db_unverify_email("p@example.com").startswith("✅")
    assert _user(db, "p@example.com")["verified_at"] is None


def test_porick_verify_keeps_the_original_date_if_already_verified(env):
    db, T = env
    _add(db, "v@example.com", created_days_ago=10, verified_days_ago=5)
    before = _user(db, "v@example.com")["verified_at"]
    T._cmd_db_verify_email("v@example.com")
    assert _user(db, "v@example.com")["verified_at"] == before


def test_email_link_stamps_verified_at(env):
    db, _ = env
    import importlib
    import main as _main
    importlib.reload(_main)
    from fastapi.testclient import TestClient
    p = db.get_db_path()
    u = _add(db, "link@example.com", created_days_ago=1)
    db.create_verification_token(p, u["id"], "tok123", (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat())
    _main.limiter.enabled = False
    with TestClient(_main.app) as client:
        r = client.post("/api/auth/verify-email", json={"token": "tok123"})
    assert r.status_code == 200
    row = _user(db, "link@example.com")
    assert row["email_verified"] == 1
    assert datetime.fromisoformat(row["verified_at"]) > datetime.now(timezone.utc) - timedelta(minutes=1)
