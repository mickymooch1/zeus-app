"""What's New announcement system (2026-09-17).

Backend pieces under test:
  1. db.py — announcements table, users.last_seen_announcement_id, and the
     helpers that read/write them.
  2. New users must start caught up: create_user() stamps
     last_seen_announcement_id to whatever the newest announcement id already
     is at signup time, so a new signup never sees a backlog of old
     announcements made before they existed.
  3. GET /announcements/unseen and POST /announcements/seen end to end,
     including the case where there are more unseen announcements than the
     3-item display cap — "seen" must catch the user up on ALL of them, not
     just the 3 that were shown, or the extras would never be dismissable.
  4. The Porickbot `announce Title | Body` precision command.
"""
import os
import pathlib
import sys

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))
os.environ.setdefault("ANTHROPIC_API_KEY", "test-key")
os.environ.setdefault("APIFRAME_API_KEY", "test-key")
os.environ.setdefault("SONG_STORAGE_PATH", "/tmp/test_songs")
os.environ.setdefault("SONG_PUBLIC_BASE_URL", "https://example.com/files/songs")
os.environ.setdefault("SONG_WEBHOOK_URL", "https://zeusaidesign.com/webhooks/apiframe")
os.environ.setdefault("JWT_SECRET", "test-secret-for-announcements-tests")

import auth
import db


@pytest.fixture
def temp_db(tmp_path, monkeypatch):
    path = tmp_path / "test.db"
    db.init_user_tables(path)
    monkeypatch.setattr(db, "get_db_path", lambda: path)
    return path


def _make_user(temp_db, email="alice@example.com"):
    return db.create_user(temp_db, email=email, password_hash="x", name="Alice", tc_accepted_at="now")


# ── db.py: announcements table primitives ───────────────────────────────────

def test_create_announcement_returns_the_new_row(temp_db):
    row = db.create_announcement(temp_db, "New genres!", "We added Brazilian Phonk.")
    assert row["title"] == "New genres!"
    assert row["body"] == "We added Brazilian Phonk."
    assert row["active"] == 1
    assert row["id"] > 0


def test_get_unseen_announcements_excludes_anything_at_or_before_last_seen(temp_db):
    first = db.create_announcement(temp_db, "First", "body 1")
    second = db.create_announcement(temp_db, "Second", "body 2")

    unseen = db.get_unseen_announcements(temp_db, last_seen_id=first["id"])

    assert [a["id"] for a in unseen] == [second["id"]]


def test_get_unseen_announcements_returns_newest_first(temp_db):
    a1 = db.create_announcement(temp_db, "One", "b1")
    a2 = db.create_announcement(temp_db, "Two", "b2")
    a3 = db.create_announcement(temp_db, "Three", "b3")

    unseen = db.get_unseen_announcements(temp_db, last_seen_id=0)

    assert [a["id"] for a in unseen] == [a3["id"], a2["id"], a1["id"]]


def test_get_unseen_announcements_caps_at_three_even_with_more_pending(temp_db):
    for i in range(5):
        db.create_announcement(temp_db, f"Announcement {i}", "body")

    unseen = db.get_unseen_announcements(temp_db, last_seen_id=0)

    assert len(unseen) == 3


def test_get_unseen_announcements_excludes_inactive(temp_db):
    active = db.create_announcement(temp_db, "Active", "body")
    inactive = db.create_announcement(temp_db, "Inactive", "body")
    db.update_announcement_active(temp_db, inactive["id"], active=False)

    unseen = db.get_unseen_announcements(temp_db, last_seen_id=0)

    assert [a["id"] for a in unseen] == [active["id"]]


def test_get_latest_announcement_id_is_zero_when_none_exist(temp_db):
    assert db.get_latest_announcement_id(temp_db) == 0


def test_get_latest_announcement_id_returns_the_newest_id(temp_db):
    db.create_announcement(temp_db, "One", "b1")
    second = db.create_announcement(temp_db, "Two", "b2")

    assert db.get_latest_announcement_id(temp_db) == second["id"]


# ── New users start caught up ────────────────────────────────────────────────

def test_new_user_last_seen_is_zero_when_no_announcements_exist(temp_db):
    user = _make_user(temp_db)
    assert user["last_seen_announcement_id"] == 0


def test_new_user_last_seen_starts_at_the_current_latest_announcement(temp_db):
    """A signup that happens after announcements already exist must not see
    that pre-existing backlog — last_seen starts caught up, not at zero."""
    db.create_announcement(temp_db, "Old news", "posted before this user signed up")
    latest_id = db.get_latest_announcement_id(temp_db)

    user = _make_user(temp_db)

    assert user["last_seen_announcement_id"] == latest_id
    unseen = db.get_unseen_announcements(temp_db, last_seen_id=user["last_seen_announcement_id"])
    assert unseen == []


# ── HTTP endpoints ────────────────────────────────────────────────────────────

def _client():
    import main as _main
    _main.limiter.enabled = False
    return _main.app


@pytest.fixture
def app_client(temp_db):
    with TestClient(_client()) as client:
        yield client


def _auth_headers(user):
    token = auth.create_token(user["id"], user["email"], is_admin=bool(user.get("is_admin", 0)))
    return {"Authorization": f"Bearer {token}"}


def test_unseen_endpoint_requires_auth(app_client):
    resp = app_client.get("/announcements/unseen")
    assert resp.status_code == 401


def test_unseen_endpoint_returns_new_announcements_for_the_user(temp_db, app_client):
    user = _make_user(temp_db)
    ann = db.create_announcement(temp_db, "Hello", "World")

    resp = app_client.get("/announcements/unseen", headers=_auth_headers(user))

    assert resp.status_code == 200
    body = resp.json()
    assert [a["id"] for a in body["announcements"]] == [ann["id"]]
    assert body["announcements"][0]["title"] == "Hello"


def test_unseen_endpoint_is_empty_once_caught_up(temp_db, app_client):
    user = _make_user(temp_db)
    db.create_announcement(temp_db, "Hello", "World")
    headers = _auth_headers(user)

    app_client.post("/announcements/seen", headers=headers)
    resp = app_client.get("/announcements/unseen", headers=headers)

    assert resp.json()["announcements"] == []


def test_seen_endpoint_catches_up_past_announcements_beyond_the_display_cap(temp_db, app_client):
    """5 unseen exist, only 3 are ever shown — /seen must still mark all 5 as
    seen, or the other 2 would be permanently stuck as unseen-but-never-shown."""
    user = _make_user(temp_db)
    for i in range(5):
        db.create_announcement(temp_db, f"Announcement {i}", "body")
    headers = _auth_headers(user)

    shown = app_client.get("/announcements/unseen", headers=headers).json()["announcements"]
    assert len(shown) == 3

    app_client.post("/announcements/seen", headers=headers)

    resp = app_client.get("/announcements/unseen", headers=headers)
    assert resp.json()["announcements"] == []


# ── Porickbot `announce Title | Body` command ────────────────────────────────

def test_announce_command_creates_an_active_announcement(temp_db):
    import telegram_admin

    result = telegram_admin.parse_and_run("announce New Genres | We added Brazilian Phonk.", chat_id="1")

    assert "✅" in result
    unseen = db.get_unseen_announcements(temp_db, last_seen_id=0)
    assert len(unseen) == 1
    assert unseen[0]["title"] == "New Genres"
    assert unseen[0]["body"] == "We added Brazilian Phonk."
