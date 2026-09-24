"""Zeus Clips on PUBLIC songs + song-based remix (2026-09-24 Discover brief).

- Anyone may clip any PUBLIC song; private songs stay owner-only.
- A clip always credits the song's ORIGINAL artist (song_artist_name), separately
  from the clip's creator (artist_name → @handle / profile).
- clip_published analytics carry is_own_song.
- POST /api/songs/{variant_id}/remix: the Clips remix flow, keyed by song not clip.

Reuses test_clips_api's fixture and helpers (same real temp DB, real auth, only the
two network boundaries mocked for generation).
"""
import sqlite3

from tests.test_clips_api import app_client, _publish, auth_hdr, _mock_generation  # noqa: F401  (fixture import)


def _events(db_path, **where):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    clause = " AND ".join(f"{k} IS ?" for k in where) or "1"
    rows = conn.execute(f"SELECT * FROM clip_events WHERE {clause} ORDER BY id", tuple(where.values())).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def _is_public(db_path, song_id):
    conn = sqlite3.connect(db_path)
    v = conn.execute("SELECT is_public FROM song_variants WHERE id = ?", (song_id,)).fetchone()[0]
    conn.close()
    return v


# ── clipping someone else's song ─────────────────────────────────────────────

def test_anyone_can_clip_a_public_song(app_client):
    client, _db, _clips, db_path, owner, viewer, owner_token, viewer_token = app_client
    r = _publish(client, viewer_token, song_id=1)  # song 1: owner's, public
    assert r.status_code == 201, r.text
    clip = r.json()
    assert clip["user_id"] == viewer["id"]
    assert clip["song_id"] == 1


def test_someone_elses_private_song_cannot_be_clipped_even_asking_to_make_it_public(app_client):
    client, _db, _clips, db_path, owner, viewer, owner_token, viewer_token = app_client
    r = _publish(client, viewer_token, song_id=2, make_song_public=True)  # song 2: owner's, private
    assert r.status_code == 404
    assert _is_public(db_path, 2) == 0, "a non-owner must never be able to flip someone else's song public"


def test_owner_can_still_clip_their_own_private_song_by_making_it_public(app_client):
    client, _db, _clips, db_path, owner, viewer, owner_token, viewer_token = app_client
    r = _publish(client, owner_token, song_id=2, make_song_public=True)
    assert r.status_code == 201, r.text
    assert _is_public(db_path, 2) == 1


def test_clip_of_someone_elses_song_credits_the_original_artist(app_client):
    client, _db, _clips, db_path, owner, viewer, owner_token, viewer_token = app_client
    clip_id = _publish(client, viewer_token, song_id=1).json()["id"]
    detail = client.get(f"/api/clips/{clip_id}").json()
    assert detail["song_artist_name"] == "Owner", "song bar credits whoever made the song"
    assert detail["artist_name"] == "Viewer", "@handle is still the clip's creator"
    feed_item = next(c for c in client.get("/api/clips?sort=new").json()["clips"] if c["id"] == clip_id)
    assert feed_item["song_artist_name"] == "Owner"


def test_own_clip_credits_yourself_as_the_original_artist(app_client):
    client, _db, _clips, db_path, owner, viewer, owner_token, viewer_token = app_client
    clip_id = _publish(client, owner_token, song_id=1).json()["id"]
    detail = client.get(f"/api/clips/{clip_id}").json()
    assert detail["song_artist_name"] == detail["artist_name"] == "Owner"


def test_clip_published_event_records_is_own_song(app_client):
    client, _db, _clips, db_path, owner, viewer, owner_token, viewer_token = app_client
    own = _publish(client, owner_token, song_id=1).json()["id"]
    theirs = _publish(client, viewer_token, song_id=1).json()["id"]
    assert _events(db_path, clip_id=own, event_name="clip_published")[0]["is_own_song"] == 1
    assert _events(db_path, clip_id=theirs, event_name="clip_published")[0]["is_own_song"] == 0


def test_other_events_leave_is_own_song_null(app_client):
    client, _db, _clips, db_path, owner, viewer, owner_token, viewer_token = app_client
    clip_id = _publish(client, owner_token, song_id=1).json()["id"]
    client.post(f"/api/clips/{clip_id}/view", headers=auth_hdr(viewer_token))
    assert _events(db_path, clip_id=clip_id, event_name="clip_viewed")[0]["is_own_song"] is None


# ── song remix (Discover) ────────────────────────────────────────────────────

def test_song_remix_requires_auth(app_client):
    client, *_ = app_client
    assert client.post("/api/songs/1/remix").status_code == 401


def test_song_remix_is_blocked_for_an_unverified_email(app_client):
    client, db_mod, _clips, db_path, *_ = app_client
    import auth
    u = db_mod.create_user(db_path, "unverified@example.com", "x", "U", "now")
    r = client.post("/api/songs/1/remix", headers=auth_hdr(auth.create_token(u["id"], u["email"])))
    assert r.status_code == 403
    assert r.json()["detail"]["code"] == "email_unverified"


def test_song_remix_of_a_public_song_starts_generation_and_costs_one_credit(app_client):
    client, _db, _clips, db_path, owner, viewer, owner_token, viewer_token = app_client
    p1, p2 = _mock_generation(db_path, viewer["id"], lyric_id=777)
    with p1 as gen_lyrics, p2:
        r = client.post("/api/songs/1/remix", headers=auth_hdr(viewer_token))
    assert r.status_code == 202, r.text
    body = r.json()
    assert body["lyric_id"] == 777 and isinstance(body["variant_id"], int)
    _args, kwargs = gen_lyrics.call_args
    assert "la la la real lyrics here" not in str(kwargs), "never the source song's lyrics"
    assert "summer" in str(kwargs.get("inspired_by_theme", "")).lower()
    conn = sqlite3.connect(db_path)
    balance = conn.execute("SELECT balance FROM song_credits WHERE user_id = ?", (viewer["id"],)).fetchone()[0]
    remix_rows = conn.execute("SELECT COUNT(*) FROM clip_remixes").fetchone()[0]
    conn.close()
    assert balance == 4
    assert remix_rows == 0, "a song remix has no clip, so it must not create a clip_remixes row"
    ev = _events(db_path, event_name="song_remix_started")
    assert len(ev) == 1 and ev[0]["song_id"] == 1 and ev[0]["clip_id"] is None and ev[0]["user_id"] == viewer["id"]


def test_song_remix_of_someone_elses_private_song_is_404(app_client):
    client, _db, _clips, db_path, owner, viewer, owner_token, viewer_token = app_client
    p1, p2 = _mock_generation(db_path, viewer["id"])
    with p1 as gen_lyrics, p2:
        r = client.post("/api/songs/2/remix", headers=auth_hdr(viewer_token))
    assert r.status_code == 404
    assert not gen_lyrics.called


def test_song_remix_of_an_unknown_song_is_404(app_client):
    client, *_, viewer_token = app_client
    assert client.post("/api/songs/9999/remix", headers=auth_hdr(viewer_token)).status_code == 404


def test_song_remix_with_zero_credits_is_refused(app_client):
    client, db_mod, _clips, db_path, *_ = app_client
    import auth
    broke = db_mod.create_user(db_path, "broke2@example.com", "x", "Broke", "now")
    conn = sqlite3.connect(db_path)
    conn.execute("UPDATE users SET email_verified = 1 WHERE id = ?", (broke["id"],))
    conn.commit(); conn.close()
    p1, p2 = _mock_generation(db_path, broke["id"])
    with p1, p2:
        r = client.post("/api/songs/1/remix", headers=auth_hdr(auth.create_token(broke["id"], broke["email"])))
    assert r.status_code == 402


def test_discover_song_exposes_sanitised_remix_prefill_never_lyrics(app_client):
    client, *_ = app_client
    d = client.get("/api/discover/1").json()
    assert "synth" in d["remix_style_descriptors"].lower()
    assert "summer" in d["remix_theme"].lower()
    assert "la la la real lyrics here" not in str(d)
