"""Single-request library load (2026-08-02).

The songs page used to issue one request per song (~400 concurrent on a large
account, each opening three SQLite connections). That saturated the single
uvicorn worker, so requests timed out and — because the client used
Promise.all — one straggler discarded every other result and the page came up
blank. Users learned to "refresh loads of times until it loads".

These tests pin the cure: the whole library comes back in ONE request, with the
lyric title already attached, and scoped strictly to the calling user.
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
os.environ.setdefault("JWT_SECRET", "test-secret-for-library-batch-tests")


@pytest.fixture()
def seeded(tmp_path, monkeypatch):
    """A DB with two users, so cross-user leakage is detectable."""
    monkeypatch.setenv("ZEUS_DATA_DIR", str(tmp_path))
    import importlib
    import db as _db
    importlib.reload(_db)

    db_path = _db.get_db_path()
    owner = _db.create_user(db_path, email="owner@example.com", password_hash="x",
                            name="Owner", tc_accepted_at="now")
    other = _db.create_user(db_path, email="other@example.com", password_hash="x",
                            name="Other", tc_accepted_at="now")

    conn = _db._conn(db_path)
    try:
        # 3 lyrics for the owner, 5 variants total; 1 lyric for the other user.
        for lid, (uid, title) in enumerate(
            [(owner["id"], "Owner Song A"), (owner["id"], "Owner Song B"),
             (owner["id"], "Owner Song C"), (other["id"], "Other Song")], start=1
        ):
            conn.execute(
                "INSERT INTO lyrics (id, user_id, title, brief, lyrics_text, created_at) VALUES (?,?,?,?,?,datetime('now'))",
                (lid, uid, title, "a brief", "la la la"),
            )
        rows = [
            # (id, lyric_id, user_id, kling_request_id, music_video_url)
            (10, 1, owner["id"], None, None),
            (11, 1, owner["id"], None, None),
            (12, 2, owner["id"], "kling-abc", None),        # video genuinely rendering
            (13, 3, owner["id"], "kling-xyz", "http://v/1"),  # video finished
            (14, 3, owner["id"], None, None),
            (99, 4, other["id"], None, None),               # must never leak
        ]
        for vid, lyric_id, uid, kling, mv in rows:
            conn.execute(
                """INSERT INTO song_variants
                   (id, lyric_id, user_id, genre_tag, style_prompt, take_number, status,
                    mp3_url, image_url, duration_seconds, kling_request_id, music_video_url, created_at)
                   VALUES (?,?,?,'soul','a soulful track',1,'complete','http://a.mp3','http://i.png',120,?,?,datetime('now'))""",
                (vid, lyric_id, uid, kling, mv),
            )
        conn.commit()
    finally:
        conn.close()
    return _db, db_path, owner, other


def test_whole_library_returns_in_one_query(seeded):
    _db, db_path, owner, _ = seeded
    variants = _db.get_all_variants_for_user(db_path, owner["id"])
    # 5 variants across 3 lyrics — one call, not one call per lyric.
    assert len(variants) == 5


def test_lyric_title_is_joined_in(seeded):
    """The client no longer fetches lyrics separately to get titles."""
    _db, db_path, owner, _ = seeded
    by_id = {v["id"]: v for v in _db.get_all_variants_for_user(db_path, owner["id"])}
    assert by_id[10]["lyric_title"] == "Owner Song A"
    assert by_id[12]["lyric_title"] == "Owner Song B"
    assert by_id[14]["lyric_title"] == "Owner Song C"


def test_other_users_variants_never_leak(seeded):
    _db, db_path, owner, other = seeded
    ids = {v["id"] for v in _db.get_all_variants_for_user(db_path, owner["id"])}
    assert 99 not in ids
    assert ids == {10, 11, 12, 13, 14}
    # And the other user sees only their own.
    assert {v["id"] for v in _db.get_all_variants_for_user(db_path, other["id"])} == {99}


def test_newest_first_ordering(seeded):
    _db, db_path, owner, _ = seeded
    ids = [v["id"] for v in _db.get_all_variants_for_user(db_path, owner["id"])]
    assert ids == sorted(ids, reverse=True)


def test_music_video_pending_only_when_actually_rendering(seeded):
    """Item 4: the client polls on this flag. If it were true for ordinary songs
    the page would re-fetch the entire library every 30s forever — which is
    exactly the bug being fixed."""
    _db, db_path, owner, _ = seeded
    by_id = {v["id"]: v for v in _db.get_all_variants_for_user(db_path, owner["id"])}
    pending = lambda v: bool(v.get("kling_request_id") and not v.get("music_video_url"))

    assert pending(by_id[12]) is True          # requested, not finished → poll
    assert pending(by_id[13]) is False         # finished → stop polling
    assert pending(by_id[10]) is False         # never requested → never poll
    assert pending(by_id[14]) is False
    # Only ONE of five variants should ever trigger polling.
    assert sum(pending(v) for v in by_id.values()) == 1


def test_empty_library_is_not_an_error(seeded):
    _db, db_path, _, _ = seeded
    fresh = _db.create_user(db_path, email="empty@example.com", password_hash="x",
                            name="Empty", tc_accepted_at="now")
    assert _db.get_all_variants_for_user(db_path, fresh["id"]) == []


def test_library_endpoint_is_registered_and_not_shadowed():
    """/api/library must not sit under /api/lyrics/{lyric_id:int}, which would
    422 on a string segment instead of falling through."""
    import main
    paths = {r.path for r in main.app.routes}
    assert "/api/library" in paths
    assert not any(p.startswith("/api/lyrics/") and p.endswith("/library") for p in paths)
