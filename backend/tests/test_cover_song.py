"""POST /api/songs/variants/{id}/cover (2026-09-17).

Found broken via a live production test: every single call crashed with a
500 before ever reaching Apiframe --

    sqlite3.IntegrityError: NOT NULL constraint failed: lyrics.brief

cover_song()'s own INSERT INTO lyrics omits the `brief` column, which the
schema requires NOT NULL (every other lyrics-writing call site in the
codebase supplies one). Because the credit deduction and this INSERT share
one uncommitted sqlite3 connection, the whole transaction rolled back on the
crash -- confirmed live, the customer's credit balance was unaffected -- but
the feature could not produce a single cover, ever, for any customer.

This file pins the fix and the source-song attribute copying (style_prompt,
genre_tag) that already worked and must keep working.
"""
import os
import pathlib
import sys
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))
os.environ.setdefault("ANTHROPIC_API_KEY", "test-key")
os.environ.setdefault("APIFRAME_API_KEY", "test-key")
os.environ.setdefault("SONG_STORAGE_PATH", "/tmp/test_songs")
os.environ.setdefault("SONG_PUBLIC_BASE_URL", "https://example.com/files/songs")
os.environ.setdefault("SONG_WEBHOOK_URL", "https://zeusaidesign.com/webhooks/apiframe")
os.environ.setdefault("JWT_SECRET", "test-secret-for-cover-song-tests")

import auth
import db


@pytest.fixture
def temp_db(tmp_path, monkeypatch):
    path = tmp_path / "test.db"
    db.init_user_tables(path)
    monkeypatch.setattr(db, "get_db_path", lambda: path)
    return path


def _make_user_with_credits(temp_db, balance=5):
    user = db.create_user(temp_db, email="singer@example.com", password_hash="x", name="Singer", tc_accepted_at="now")
    db.upsert_song_credits(temp_db, user["id"], balance=balance, monthly_allowance=balance)
    return user


def _make_source_variant(temp_db, user_id, style_prompt="Chicago electric blues", genre_tag="chicagoblues",
                          provider_job_id="orig-job-abc", take_number=1):
    conn = db._conn(temp_db)
    try:
        cur = conn.execute(
            "INSERT INTO lyrics (user_id, brief, lyrics_text) VALUES (?, ?, ?)",
            (user_id, "Original song", "[Verse 1]\nOriginal lyrics here"),
        )
        lyric_id = cur.lastrowid
        cur = conn.execute(
            """INSERT INTO song_variants (lyric_id, user_id, style_prompt, genre_tag, status, mp3_url,
                                           provider_job_id, take_number)
               VALUES (?, ?, ?, ?, 'complete', 'https://example.com/files/songs/1.mp3', ?, ?)""",
            (lyric_id, user_id, style_prompt, genre_tag, provider_job_id, take_number),
        )
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()


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


@patch("main._webhooks_mod._cover_pipeline")
def test_cover_request_succeeds_instead_of_crashing_on_missing_brief(mock_pipeline, temp_db, app_client):
    user = _make_user_with_credits(temp_db)
    source_id = _make_source_variant(temp_db, user["id"])

    resp = app_client.post(
        f"/api/songs/variants/{source_id}/cover",
        json={"lyrics": "[Verse 1]\nMy edited lyrics"},
        headers=_auth_headers(user),
    )

    assert resp.status_code == 202
    assert resp.json()["status"] == "pending"


@patch("main._webhooks_mod._cover_pipeline")
def test_cover_writes_a_lyrics_row_with_a_non_null_brief(mock_pipeline, temp_db, app_client):
    user = _make_user_with_credits(temp_db)
    source_id = _make_source_variant(temp_db, user["id"])

    resp = app_client.post(
        f"/api/songs/variants/{source_id}/cover",
        json={"lyrics": "[Verse 1]\nMy edited lyrics"},
        headers=_auth_headers(user),
    )

    new_variant = db.get_song_variant_by_id(temp_db, resp.json()["variant_id"])
    lyric_row = db.get_lyric(temp_db, new_variant["lyric_id"], user["id"])
    assert lyric_row["brief"]
    assert lyric_row["lyrics_text"] == "[Verse 1]\nMy edited lyrics"


@patch("main._webhooks_mod._cover_pipeline")
def test_cover_copies_style_and_genre_from_the_source_song(mock_pipeline, temp_db, app_client):
    user = _make_user_with_credits(temp_db)
    source_id = _make_source_variant(temp_db, user["id"], style_prompt="Delta acoustic blues", genre_tag="deltablues")

    resp = app_client.post(
        f"/api/songs/variants/{source_id}/cover",
        json={"lyrics": "[Verse 1]\nMy edited lyrics"},
        headers=_auth_headers(user),
    )

    new_variant = db.get_song_variant_by_id(temp_db, resp.json()["variant_id"])
    assert new_variant["style_prompt"] == "Delta acoustic blues"
    assert new_variant["genre_tag"] == "deltablues"


@patch("main._webhooks_mod._cover_pipeline")
def test_cover_deducts_exactly_one_song_credit(mock_pipeline, temp_db, app_client):
    user = _make_user_with_credits(temp_db, balance=5)
    source_id = _make_source_variant(temp_db, user["id"])

    app_client.post(
        f"/api/songs/variants/{source_id}/cover",
        json={"lyrics": "[Verse 1]\nMy edited lyrics"},
        headers=_auth_headers(user),
    )

    credits = db.get_song_credits(temp_db, user["id"])
    assert credits["balance"] == 4


@patch("main._webhooks_mod._cover_pipeline")
def test_cover_submits_the_pipeline_with_the_sources_original_job_and_track(mock_pipeline, temp_db, app_client):
    """The pipeline no longer needs the source mp3 -- it needs the ORIGINAL
    Apiframe job id and which of its two tracks to cover, per Apiframe's
    documented Suno Cover action."""
    user = _make_user_with_credits(temp_db)
    source_id = _make_source_variant(
        temp_db, user["id"], style_prompt="Delta acoustic blues",
        provider_job_id="orig-job-xyz", take_number=2,
    )

    app_client.post(
        f"/api/songs/variants/{source_id}/cover",
        json={"lyrics": "[Verse 1]\nMy edited lyrics"},
        headers=_auth_headers(user),
    )

    mock_pipeline.assert_called_once()
    _, kwargs = mock_pipeline.call_args
    assert kwargs["parent_job_id"] == "orig-job-xyz"
    assert kwargs["track_index"] == 2
    assert kwargs["style"] == "Delta acoustic blues"
    assert kwargs["lyrics_text"] == "[Verse 1]\nMy edited lyrics"


def test_cover_rejects_a_source_song_with_no_original_job_id(temp_db, app_client):
    """A song with no provider_job_id on file (e.g. predates this column,
    or never actually completed a real generation) can't be covered via
    Apiframe's job-based Cover action."""
    user = _make_user_with_credits(temp_db)
    source_id = _make_source_variant(temp_db, user["id"], provider_job_id=None)

    resp = app_client.post(
        f"/api/songs/variants/{source_id}/cover",
        json={"lyrics": "[Verse 1]\nMy edited lyrics"},
        headers=_auth_headers(user),
    )

    assert resp.status_code == 400


def test_cover_rejects_a_source_song_that_isnt_ready(temp_db, app_client):
    user = _make_user_with_credits(temp_db)
    conn = db._conn(temp_db)
    lyric_cur = conn.execute(
        "INSERT INTO lyrics (user_id, brief, lyrics_text) VALUES (?, ?, ?)",
        (user["id"], "Original", "[Verse 1]\nOriginal"),
    )
    variant_cur = conn.execute(
        "INSERT INTO song_variants (lyric_id, user_id, style_prompt, status) VALUES (?, ?, ?, 'pending')",
        (lyric_cur.lastrowid, user["id"], "Some style"),
    )
    conn.commit()
    source_id = variant_cur.lastrowid
    conn.close()

    resp = app_client.post(
        f"/api/songs/variants/{source_id}/cover",
        json={"lyrics": "[Verse 1]\nMy edited lyrics"},
        headers=_auth_headers(user),
    )

    assert resp.status_code == 400


def test_cover_rejects_someone_elses_song(temp_db, app_client):
    owner = _make_user_with_credits(temp_db)
    other = db.create_user(temp_db, email="other@example.com", password_hash="x", name="Other", tc_accepted_at="now")
    db.upsert_song_credits(temp_db, other["id"], balance=5, monthly_allowance=5)
    source_id = _make_source_variant(temp_db, owner["id"])

    resp = app_client.post(
        f"/api/songs/variants/{source_id}/cover",
        json={"lyrics": "[Verse 1]\nMy edited lyrics"},
        headers=_auth_headers(other),
    )

    assert resp.status_code == 404
