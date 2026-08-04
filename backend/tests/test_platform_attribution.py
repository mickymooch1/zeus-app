"""Platform attribution (2026-08-04).

Records which client a signup and each song came from, so web vs Play Store vs
App Store can be compared going forward.

Why the client has to tell us: an Android TWA is backed by Chrome and sends an
ordinary Chrome User-Agent, indistinguishable from the mobile site. The reliable
signals are client-side (document.referrer "android-app://" for a TWA; the
?platform=ios-app param / window.webkit for the iOS shell), so the client sends
the value and the server only sanitises it. The User-Agent path is a weak
fallback for older builds — anything unrecognised must stay "unknown" rather
than being guessed into a real bucket, or the numbers become fiction.

This cannot be backfilled: rows created before it shipped stay NULL.
"""
import os
import pathlib
import sys

import pytest

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))
os.environ.setdefault("ANTHROPIC_API_KEY", "test-key")
os.environ.setdefault("APIFRAME_API_KEY", "test-key")
os.environ.setdefault("SONG_STORAGE_PATH", "/tmp/test_songs")
os.environ.setdefault("SONG_PUBLIC_BASE_URL", "https://example.com/files/songs")
os.environ.setdefault("SONG_WEBHOOK_URL", "https://zeusaidesign.com/webhooks/apiframe")
os.environ.setdefault("JWT_SECRET", "test-secret-for-platform-tests")


class _Req:
    """Minimal stand-in for a FastAPI Request."""
    def __init__(self, headers=None):
        self.headers = headers or {}


# ── detection ────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("value,expected", [
    ("web", "web"), ("android", "android"), ("ios", "ios"),
    ("ANDROID", "android"), ("  iOS  ", "ios"),
    ("android-twa", "android"), ("twa", "android"),
    ("ios-app", "ios"), ("ios-native", "ios"), ("ios-webview", "ios"),
    ("browser", "web"), ("pwa", "web"),
])
def test_known_platform_values_normalise(value, expected):
    import main
    assert main._detect_platform(_Req(), value) == expected


def test_header_is_used_when_no_explicit_value():
    import main
    assert main._detect_platform(_Req({"x-zeus-platform": "android"})) == "android"


def test_explicit_value_wins_over_header():
    import main
    assert main._detect_platform(_Req({"x-zeus-platform": "web"}), "ios") == "ios"


def test_unknown_input_is_never_guessed_into_a_real_bucket():
    """A wrong attribution is worse than an honest 'unknown'."""
    import main
    for junk in [None, "", "   ", "windows-phone", "curl/8.1", "<script>"]:
        assert main._detect_platform(_Req(), junk) == "unknown"


def test_a_plain_chrome_on_android_ua_is_not_called_android():
    """This is exactly the TWA-vs-mobile-web ambiguity — the mobile SITE in
    Chrome on a phone must NOT be attributed to the Play Store."""
    import main
    ua = ("Mozilla/5.0 (Linux; Android 14; Pixel 8) AppleWebKit/537.36 "
          "(KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36")
    assert main._detect_platform(_Req({"user-agent": ua})) == "unknown"


def test_ua_fallback_only_fires_for_a_branded_client():
    import main
    assert main._detect_platform(_Req({"user-agent": "ZeusBeats/1.3 (Android 14)"})) == "android"
    assert main._detect_platform(_Req({"user-agent": "ZeusBeats/1.0 (iPhone; iOS 17)"})) == "ios"


# ── storage ──────────────────────────────────────────────────────────────────

@pytest.fixture()
def fresh_db(tmp_path, monkeypatch):
    monkeypatch.setenv("ZEUS_DATA_DIR", str(tmp_path))
    import importlib
    import db as _db
    importlib.reload(_db)
    return _db


def test_columns_exist(fresh_db):
    conn = fresh_db._conn(fresh_db.get_db_path())
    try:
        assert "signup_platform" in {r[1] for r in conn.execute("PRAGMA table_info(users)")}
        assert "platform" in {r[1] for r in conn.execute("PRAGMA table_info(song_variants)")}
    finally:
        conn.close()


def test_signup_platform_is_stored_and_readable(fresh_db):
    p = fresh_db.get_db_path()
    u = fresh_db.create_user(p, email="a@b.co", password_hash="x", name="A", tc_accepted_at="n")
    fresh_db.update_user(p, u["id"], signup_platform="android")
    assert fresh_db.get_user_by_id(p, u["id"])["signup_platform"] == "android"


def test_pre_existing_rows_stay_null_not_mislabelled(fresh_db):
    """Backfill is impossible; old rows must read as unknown, never as 'web'."""
    p = fresh_db.get_db_path()
    u = fresh_db.create_user(p, email="old@b.co", password_hash="x", name="O", tc_accepted_at="n")
    assert fresh_db.get_user_by_id(p, u["id"])["signup_platform"] is None


def test_generate_song_variant_stamps_the_platform(fresh_db, monkeypatch):
    """End-to-end through the real insert path, not a hand-written INSERT."""
    import importlib
    import songs as _songs
    importlib.reload(_songs)
    monkeypatch.setattr(_songs, "_submit_to_apiframe", lambda *a, **k: "job-1")

    p = fresh_db.get_db_path()
    u = fresh_db.create_user(p, email="c@d.co", password_hash="x", name="C", tc_accepted_at="n")
    fresh_db.ensure_free_song_credits(p, u["id"], balance=5, monthly_allowance=0)
    conn = fresh_db._conn(p)
    try:
        conn.execute("INSERT INTO lyrics (id,user_id,title,brief,lyrics_text,created_at) "
                     "VALUES (1,?,'T','b','la',datetime('now'))", (u["id"],))
        conn.commit()
    finally:
        conn.close()

    _songs.generate_song_variant(
        user_id=u["id"], lyric_id=1, style_prompt="s", genre_tag="pop",
        db_path=str(p), platform="android")

    conn = fresh_db._conn(p)
    try:
        row = conn.execute("SELECT platform FROM song_variants ORDER BY id DESC LIMIT 1").fetchone()
    finally:
        conn.close()
    assert row["platform"] == "android"


# ── reporting ────────────────────────────────────────────────────────────────

def test_platforms_command_reports_each_bucket_and_the_gap(fresh_db):
    import importlib
    import telegram_admin as T
    importlib.reload(T)

    p = fresh_db.get_db_path()
    for email, plat in [("w@x.co", "web"), ("a@x.co", "android"), ("i@x.co", "ios")]:
        u = fresh_db.create_user(p, email=email, password_hash="x", name="N", tc_accepted_at="n")
        fresh_db.update_user(p, u["id"], signup_platform=plat)
    fresh_db.create_user(p, email="legacy@x.co", password_hash="x", name="L", tc_accepted_at="n")

    out = T._cmd_platforms()
    for expected in ["web", "android", "ios", "unknown"]:
        assert expected in out, expected
    assert "can't be backfilled" in out, "the caveat must be stated, not implied"


def test_platforms_command_is_wired_up():
    import telegram_admin as T
    src = pathlib.Path(T.__file__).read_text(encoding="utf-8")
    assert 'if act == "platforms"' in src
    assert '"action": "platforms"' in src
    assert "- platforms —" in src


def test_web_client_sends_a_platform_on_register_and_generate():
    root = pathlib.Path(__file__).parent.parent.parent / "web-beats" / "src"
    assert "PLATFORM" in (root / "contexts" / "AuthContext.jsx").read_text(encoding="utf-8")
    assert "platform: PLATFORM" in (root / "pages" / "SongsPage.jsx").read_text(encoding="utf-8")
    util = (root / "utils" / "platform.js").read_text(encoding="utf-8")
    assert "android-app://" in util, "TWA detection must use the documented referrer signal"


def test_ios_app_identifies_itself():
    ios = (pathlib.Path(__file__).parent.parent.parent / "zeus-beats-ios" / "src"
           / "screens" / "CreateSongScreen.tsx").read_text(encoding="utf-8")
    assert "platform:" in ios and "'ios'" in ios
