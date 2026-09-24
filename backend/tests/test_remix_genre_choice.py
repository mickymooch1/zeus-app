"""Remix in a different genre (2026-09-24) — both the clip remix and the Discover
song remix accept an optional {genre, genre_b} in the body.

- Omitted, or the same as the original: current behaviour — the original genre
  AND the original song's (sanitized) style descriptors.
- A different genre: that genre's own preset (NO original style descriptors),
  but still the original song's theme for the new lyrics. Never the lyrics.
- Unknown genres are a clean 400 before any lyrics call or credit spend.
- Same credit cost as a normal remix.
- remix_started / song_remix_started carry original_genre, remix_genre,
  genre_changed.

Reuses test_clips_api's fixture: song 1 is the owner's public 'pop' song whose
brief is "a song about summer love" and style "modern pop, catchy synth melody".
"""
import sqlite3
from unittest.mock import patch

from tests.test_clips_api import app_client, _publish, auth_hdr, _mock_generation  # noqa: F401


def _last_event(db_path, name):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    row = conn.execute("SELECT * FROM clip_events WHERE event_name = ? ORDER BY id DESC LIMIT 1", (name,)).fetchone()
    conn.close()
    return dict(row) if row else None


def _balance(db_path, user_id):
    conn = sqlite3.connect(db_path)
    b = conn.execute("SELECT balance FROM song_credits WHERE user_id = ?", (user_id,)).fetchone()[0]
    conn.close()
    return b


def _remix(client, db_path, viewer, token, url, body=None):
    """POST a remix with generation mocked at its network edges, capturing what the
    REAL generate_multiple_variants was asked for and what generate_lyrics got."""
    import songs
    real = songs.generate_multiple_variants
    p1, p2 = _mock_generation(db_path, viewer["id"])
    with p1 as gen_lyrics, p2, patch("songs.generate_multiple_variants", side_effect=real) as gen_variants:
        r = client.post(url, json=body, headers=auth_hdr(token)) if body is not None \
            else client.post(url, headers=auth_hdr(token))
    return r, gen_lyrics, gen_variants


# ── default: unchanged behaviour ──────────────────────────────────────────────

def test_song_remix_default_keeps_the_original_genre_and_style(app_client):
    client, _db, _clips, db_path, owner, viewer, owner_token, viewer_token = app_client
    r, gen_lyrics, gen_variants = _remix(client, db_path, viewer, viewer_token, "/api/songs/1/remix")
    assert r.status_code == 202, r.text
    kw = gen_variants.call_args.kwargs
    assert kw["genres"] == ["pop"] and kw.get("genre_b") is None
    assert "synth melody" in (kw.get("inspired_by_descriptors") or "")
    ev = _last_event(db_path, "song_remix_started")
    assert (ev["original_genre"], ev["remix_genre"], ev["genre_changed"]) == ("pop", "pop", 0)


def test_choosing_the_original_genre_explicitly_is_the_same_as_default(app_client):
    client, _db, _clips, db_path, owner, viewer, owner_token, viewer_token = app_client
    r, _gl, gen_variants = _remix(client, db_path, viewer, viewer_token, "/api/songs/1/remix", {"genre": "pop"})
    assert r.status_code == 202, r.text
    assert "synth melody" in (gen_variants.call_args.kwargs.get("inspired_by_descriptors") or "")
    assert _last_event(db_path, "song_remix_started")["genre_changed"] == 0


# ── a different genre ─────────────────────────────────────────────────────────

def test_song_remix_in_a_different_genre_uses_its_preset_but_keeps_the_theme(app_client):
    client, _db, _clips, db_path, owner, viewer, owner_token, viewer_token = app_client
    r, gen_lyrics, gen_variants = _remix(client, db_path, viewer, viewer_token, "/api/songs/1/remix", {"genre": "ukdrill"})
    assert r.status_code == 202, r.text
    kw = gen_variants.call_args.kwargs
    assert kw["genres"] == ["ukdrill"] and kw.get("genre_b") is None
    assert not kw.get("inspired_by_descriptors"), "the original style prompt must not be used"
    lkw = gen_lyrics.call_args.kwargs
    assert lkw["genres"] == ["ukdrill"]
    assert "summer" in str(lkw.get("inspired_by_theme", "")).lower(), "the original theme is kept"
    assert "la la la real lyrics here" not in str(lkw), "never the original lyrics"
    ev = _last_event(db_path, "song_remix_started")
    assert (ev["original_genre"], ev["remix_genre"], ev["genre_changed"]) == ("pop", "ukdrill", 1)


def test_clip_remix_in_a_different_genre_works_the_same_way(app_client):
    client, _db, _clips, db_path, owner, viewer, owner_token, viewer_token = app_client
    clip_id = _publish(client, owner_token, song_id=1).json()["id"]
    r, _gl, gen_variants = _remix(client, db_path, viewer, viewer_token, f"/api/clips/{clip_id}/remix", {"genre": "trap"})
    assert r.status_code == 202, r.text
    kw = gen_variants.call_args.kwargs
    assert kw["genres"] == ["trap"] and not kw.get("inspired_by_descriptors")
    ev = _last_event(db_path, "remix_started")
    assert (ev["original_genre"], ev["remix_genre"], ev["genre_changed"]) == ("pop", "trap", 1)


def test_clip_remix_default_records_unchanged_genre(app_client):
    client, _db, _clips, db_path, owner, viewer, owner_token, viewer_token = app_client
    clip_id = _publish(client, owner_token, song_id=1).json()["id"]
    r, _gl, _gv = _remix(client, db_path, viewer, viewer_token, f"/api/clips/{clip_id}/remix")
    assert r.status_code == 202, r.text
    ev = _last_event(db_path, "remix_started")
    assert (ev["original_genre"], ev["remix_genre"], ev["genre_changed"]) == ("pop", "pop", 0)


def test_a_blend_can_be_chosen(app_client):
    client, _db, _clips, db_path, owner, viewer, owner_token, viewer_token = app_client
    r, _gl, gen_variants = _remix(client, db_path, viewer, viewer_token, "/api/songs/1/remix",
                                  {"genre": "trap", "genre_b": "rnb"})
    assert r.status_code == 202, r.text
    kw = gen_variants.call_args.kwargs
    assert kw["genres"] == ["trap"] and kw["genre_b"] == "rnb"
    assert _last_event(db_path, "song_remix_started")["remix_genre"] == "trap__rnb"


def test_a_changed_genre_costs_the_same_one_credit(app_client):
    client, _db, _clips, db_path, owner, viewer, owner_token, viewer_token = app_client
    before = _balance(db_path, viewer["id"])
    r, *_ = _remix(client, db_path, viewer, viewer_token, "/api/songs/1/remix", {"genre": "trap", "genre_b": "rnb"})
    assert r.status_code == 202, r.text
    assert _balance(db_path, viewer["id"]) == before - 1


# ── validation: refused before any lyrics call or credit spend ────────────────

def test_an_unknown_genre_is_refused_before_anything_is_spent(app_client):
    client, _db, _clips, db_path, owner, viewer, owner_token, viewer_token = app_client
    before = _balance(db_path, viewer["id"])
    r, gen_lyrics, _gv = _remix(client, db_path, viewer, viewer_token, "/api/songs/1/remix", {"genre": "not_a_genre"})
    assert r.status_code == 400
    assert not gen_lyrics.called and _balance(db_path, viewer["id"]) == before


def test_an_unknown_blend_partner_is_refused(app_client):
    client, _db, _clips, db_path, owner, viewer, owner_token, viewer_token = app_client
    r, gen_lyrics, _gv = _remix(client, db_path, viewer, viewer_token, "/api/songs/1/remix", {"genre": "trap", "genre_b": "nope"})
    assert r.status_code == 400 and not gen_lyrics.called


def test_a_blend_partner_without_a_genre_is_refused(app_client):
    client, _db, _clips, db_path, owner, viewer, owner_token, viewer_token = app_client
    r, gen_lyrics, _gv = _remix(client, db_path, viewer, viewer_token, "/api/songs/1/remix", {"genre_b": "rnb"})
    assert r.status_code == 400 and not gen_lyrics.called


def test_blending_a_genre_with_itself_is_refused(app_client):
    client, _db, _clips, db_path, owner, viewer, owner_token, viewer_token = app_client
    r, gen_lyrics, _gv = _remix(client, db_path, viewer, viewer_token, "/api/songs/1/remix", {"genre": "trap", "genre_b": "trap"})
    assert r.status_code == 400 and not gen_lyrics.called
