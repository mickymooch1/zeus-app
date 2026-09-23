"""Zeus Clips remix: the source song's genre_tag must reach generation the same way a
normal blended-genre request would — as separate genre/genre_b parameters, never the
raw "{genre}__{genre_b}" string. Found via a real production remix attempt on a
blended-genre clip (2026-09-23): passing the joined tag straight through as a single
genre made generate_multiple_variants raise ValueError("No valid genres provided"),
surfacing as a 502. See clips.get_remix_prefill's genre/genre_b split (test_clips_db.py)
for the other half of this fix.
"""
import importlib
import os
import pathlib
import sqlite3
import sys
from datetime import datetime, timezone
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))
os.environ.setdefault("ANTHROPIC_API_KEY", "test-key")
os.environ.setdefault("APIFRAME_API_KEY", "test-key")
os.environ.setdefault("SONG_STORAGE_PATH", "/tmp/test_songs")
os.environ.setdefault("SONG_PUBLIC_BASE_URL", "https://example.com/files/songs")
os.environ.setdefault("SONG_WEBHOOK_URL", "https://zeusaidesign.com/webhooks/apiframe")
os.environ.setdefault("JWT_SECRET", "test-secret-for-remix-genre-tests")

import auth

NOW = datetime(2026, 9, 23, 12, 0, 0, tzinfo=timezone.utc)


@pytest.fixture
def app_client(tmp_path, monkeypatch):
    monkeypatch.setenv("ZEUS_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("SONG_STORAGE_PATH", str(tmp_path / "songs"))
    monkeypatch.setenv("CLIP_STORAGE_PATH", str(tmp_path / "clips"))
    monkeypatch.setenv("CLIPS_ENABLED", "true")
    import db as _db
    importlib.reload(_db)
    import clips as _clips
    importlib.reload(_clips)
    import main as _main
    importlib.reload(_main)
    _main.limiter.enabled = False

    db_path = _db.get_db_path()
    owner = _db.create_user(db_path, "owner@example.com", "x", "Owner", "now")
    viewer = _db.create_user(db_path, "viewer@example.com", "x", "Viewer", "now")
    conn = sqlite3.connect(db_path)
    conn.execute("UPDATE users SET email_verified = 1 WHERE id IN (?, ?)", (owner["id"], viewer["id"]))
    conn.execute("INSERT INTO song_credits (user_id, balance) VALUES (?, 5)", (viewer["id"],))

    def _seed_song(variant_id, genre_tag):
        conn.execute(
            "INSERT INTO lyrics (id, user_id, brief, lyrics_text, title) VALUES (?, ?, 'a song about summer', "
            "'la la la real lyrics here', ?)",
            (variant_id, owner["id"], f"Song {variant_id}"),
        )
        conn.execute(
            "INSERT INTO song_variants (id, lyric_id, user_id, style_prompt, genre_tag, status, "
            "mp3_url, is_public, created_at) VALUES (?, ?, ?, 'catchy melody', ?, 'complete', "
            "?, 1, ?)",
            (variant_id, variant_id, owner["id"], genre_tag, f"/files/songs/{variant_id}.mp3", NOW.isoformat()),
        )

    _seed_song(1, "pop")             # single genre
    _seed_song(2, "pop__rock")       # valid blend
    _seed_song(3, "totallyfakegenre")               # malformed: primary unknown
    _seed_song(4, "pop__totallyfakegenre")           # malformed: secondary unknown
    conn.commit()
    conn.close()

    owner_token = _main.auth.create_token(owner["id"], owner["email"])
    viewer_token = _main.auth.create_token(viewer["id"], viewer["email"])
    with TestClient(_main.app) as client:
        yield client, _db, _clips, db_path, owner, viewer, owner_token, viewer_token


def auth_hdr(token):
    return {"Authorization": f"Bearer {token}"}


def _publish(client, token, song_id):
    return client.post("/api/clips", json={
        "song_id": song_id, "caption": "", "media_type": "cover",
        "clip_start_time": 0, "clip_duration": 15,
    }, headers=auth_hdr(token))


def _mock_generation(db_path, user_id, lyric_id=555, title="Remixed"):
    """Same mocking boundary as test_clips_api.py's _mock_generation — mocks the Claude
    lyrics call and the Apiframe network submission, letting the real credit check,
    song_variants INSERT and genre validation run for real."""
    def fake_generate_lyrics(**kwargs):
        conn = sqlite3.connect(db_path)
        conn.execute("INSERT INTO lyrics (id, user_id, brief, lyrics_text, title) VALUES (?, ?, '', ?, ?)",
                     (lyric_id, user_id, "brand new remix lyrics", title))
        conn.commit(); conn.close()
        return {"lyric_id": lyric_id, "lyrics": "brand new remix lyrics", "title": title}

    return (
        patch("lyrics.generate_lyrics", side_effect=fake_generate_lyrics),
        patch("songs._submit_to_apiframe", return_value="job-abc123"),
    )


def test_remixing_a_single_genre_clip_succeeds(app_client):
    client, db_mod, clips_mod, db_path, owner, viewer, owner_token, viewer_token = app_client
    clip_id = _publish(client, owner_token, song_id=1).json()["id"]
    p1, p2 = _mock_generation(db_path, viewer["id"])
    with p1, p2:
        r = client.post(f"/api/clips/{clip_id}/remix", headers=auth_hdr(viewer_token))
    assert r.status_code == 202, r.text


def test_remixing_a_blended_genre_clip_succeeds_and_passes_genre_b_through(app_client):
    """The regression this whole file exists for: a blended genre_tag must reach BOTH
    generate_lyrics and generate_multiple_variants as genre='pop', genre_b='rock' —
    not as a single unrecognised genres=['pop__rock']."""
    client, db_mod, clips_mod, db_path, owner, viewer, owner_token, viewer_token = app_client
    clip_id = _publish(client, owner_token, song_id=2).json()["id"]
    p1, p2 = _mock_generation(db_path, viewer["id"])
    with p1 as gen_lyrics, p2 as submit:
        r = client.post(f"/api/clips/{clip_id}/remix", headers=auth_hdr(viewer_token))
    assert r.status_code == 202, r.text
    assert submit.called, "must have reached real Apiframe submission — proves generate_multiple_variants accepted the genres"

    _args, lyrics_kwargs = gen_lyrics.call_args
    assert lyrics_kwargs.get("genres") == ["pop"]
    assert lyrics_kwargs.get("genre_b") == "rock"


def test_remixing_a_clip_with_an_unknown_primary_genre_is_a_clean_400_not_a_502(app_client):
    client, db_mod, clips_mod, db_path, owner, viewer, owner_token, viewer_token = app_client
    clip_id = _publish(client, owner_token, song_id=3).json()["id"]
    p1, p2 = _mock_generation(db_path, viewer["id"])
    with p1 as gen_lyrics, p2 as submit:
        r = client.post(f"/api/clips/{clip_id}/remix", headers=auth_hdr(viewer_token))
    assert r.status_code == 400, r.text
    assert not gen_lyrics.called, "must be refused before spending a Claude lyrics call"
    assert not submit.called


def test_remixing_a_clip_with_an_unknown_secondary_genre_falls_back_to_the_primary_alone(app_client):
    """The primary genre is real (pop); only the blend partner is garbage. That should
    degrade gracefully to a plain single-genre remix, not fail the whole request."""
    client, db_mod, clips_mod, db_path, owner, viewer, owner_token, viewer_token = app_client
    clip_id = _publish(client, owner_token, song_id=4).json()["id"]
    p1, p2 = _mock_generation(db_path, viewer["id"])
    with p1 as gen_lyrics, p2 as submit:
        r = client.post(f"/api/clips/{clip_id}/remix", headers=auth_hdr(viewer_token))
    assert r.status_code == 202, r.text
    assert submit.called
    _args, lyrics_kwargs = gen_lyrics.call_args
    assert lyrics_kwargs.get("genres") == ["pop"]
    assert lyrics_kwargs.get("genre_b") is None


def test_unknown_primary_genre_does_not_deduct_a_credit(app_client):
    client, db_mod, clips_mod, db_path, owner, viewer, owner_token, viewer_token = app_client
    clip_id = _publish(client, owner_token, song_id=3).json()["id"]
    p1, p2 = _mock_generation(db_path, viewer["id"])
    with p1, p2:
        client.post(f"/api/clips/{clip_id}/remix", headers=auth_hdr(viewer_token))
    conn = sqlite3.connect(db_path)
    balance = conn.execute("SELECT balance FROM song_credits WHERE user_id = ?", (viewer["id"],)).fetchone()[0]
    conn.close()
    assert balance == 5, "refused before any credit work — balance must be untouched"
