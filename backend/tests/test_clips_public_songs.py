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


# ── a song going private / deleted hides OTHER people's clips of it ──────────
# (2026-09-24) Clips of someone else's song are hidden with hidden_reason
# 'song_private' when that song stops being public, and come back automatically
# if it's made public again. The owner's own clips follow the existing rules
# (untouched). Enforced by DB triggers, so every writer is covered — the share
# toggle, a clip publish that makes the song public, and raw admin SQL alike.

def _clip_row(db_path, clip_id):
    conn = sqlite3.connect(db_path)
    row = conn.execute("SELECT status, hidden_reason FROM clips WHERE id = ?", (clip_id,)).fetchone()
    conn.close()
    return row


def _two_clips(client, owner_token, viewer_token):
    """Owner's own clip + viewer's clip, both of the owner's public song 1."""
    own = _publish(client, owner_token, song_id=1).json()["id"]
    theirs = _publish(client, viewer_token, song_id=1).json()["id"]
    return own, theirs


def _toggle_share(client, token, song_id=1):
    r = client.patch(f"/api/songs/variants/{song_id}/share", headers=auth_hdr(token))
    assert r.status_code == 200, r.text
    return r.json()["is_public"]


def test_making_a_song_private_hides_other_peoples_clips_of_it(app_client):
    client, _db, _clips, db_path, owner, viewer, owner_token, viewer_token = app_client
    own, theirs = _two_clips(client, owner_token, viewer_token)
    assert _toggle_share(client, owner_token) is False
    assert _clip_row(db_path, theirs) == ("hidden", "song_private")
    assert client.get(f"/api/clips/{theirs}").status_code == 404
    assert theirs not in [c["id"] for c in client.get("/api/clips?sort=new").json()["clips"]]
    assert _clip_row(db_path, own) == ("published", None), "the owner's own clip follows the existing rules"


def test_making_the_song_public_again_restores_them(app_client):
    client, _db, _clips, db_path, owner, viewer, owner_token, viewer_token = app_client
    own, theirs = _two_clips(client, owner_token, viewer_token)
    _toggle_share(client, owner_token)   # → private
    assert _toggle_share(client, owner_token) is True
    assert _clip_row(db_path, theirs) == ("published", None)
    assert client.get(f"/api/clips/{theirs}").status_code == 200


def test_a_clip_hidden_for_another_reason_is_left_alone_both_ways(app_client):
    client, _db, clips_mod, db_path, owner, viewer, owner_token, viewer_token = app_client
    own, theirs = _two_clips(client, owner_token, viewer_token)
    clips_mod.set_clip_status(db_path, theirs, "hidden", reason="admin_moderation")
    _toggle_share(client, owner_token)   # → private
    assert _clip_row(db_path, theirs) == ("hidden", "admin_moderation")
    _toggle_share(client, owner_token)   # → public
    assert _clip_row(db_path, theirs) == ("hidden", "admin_moderation"), "never un-moderates a clip"


def test_deleting_the_song_hides_other_peoples_clips_of_it(app_client):
    client, _db, _clips, db_path, owner, viewer, owner_token, viewer_token = app_client
    own, theirs = _two_clips(client, owner_token, viewer_token)
    r = client.delete("/api/songs/variants/1", headers=auth_hdr(owner_token))
    assert r.status_code == 200, r.text
    assert _clip_row(db_path, theirs) == ("hidden", "song_private")


def test_owner_republishing_via_a_clip_also_restores_them(app_client):
    """make_song_public on the owner's own clip publish flips the song public — the
    trigger restores other people's hidden clips on that path too."""
    client, _db, _clips, db_path, owner, viewer, owner_token, viewer_token = app_client
    own, theirs = _two_clips(client, owner_token, viewer_token)
    _toggle_share(client, owner_token)   # → private
    assert _publish(client, owner_token, song_id=1, make_song_public=True).status_code == 201
    assert _clip_row(db_path, theirs) == ("published", None)


def test_raw_sql_visibility_changes_are_covered_too(app_client):
    """Porick's `db exec` runs raw SQL no endpoint can intercept — the storage-level
    trigger still applies."""
    client, _db, _clips, db_path, owner, viewer, owner_token, viewer_token = app_client
    own, theirs = _two_clips(client, owner_token, viewer_token)
    conn = sqlite3.connect(db_path)
    conn.execute("UPDATE song_variants SET is_public = 0 WHERE id = 1"); conn.commit()
    assert _clip_row(db_path, theirs) == ("hidden", "song_private")
    conn.execute("UPDATE song_variants SET is_public = 1 WHERE id = 1"); conn.commit()
    conn.close()
    assert _clip_row(db_path, theirs) == ("published", None)


def test_a_blocked_creators_clip_is_not_revived_when_the_song_goes_public_again(app_client):
    client, _db, clips_mod, db_path, owner, viewer, owner_token, viewer_token = app_client
    own, theirs = _two_clips(client, owner_token, viewer_token)
    _toggle_share(client, owner_token)                           # → private: theirs hidden (song_private)
    clips_mod.hide_clips_for_blocked_user(db_path, viewer["id"])  # then the viewer is blocked
    assert _clip_row(db_path, theirs) == ("hidden", "blocked_user")
    _toggle_share(client, owner_token)                           # → public again
    assert _clip_row(db_path, theirs) == ("hidden", "blocked_user"), "the block must win"


def test_unblocking_while_the_song_is_still_private_keeps_the_clip_hidden_until_it_is_public(app_client):
    client, _db, clips_mod, db_path, owner, viewer, owner_token, viewer_token = app_client
    own, theirs = _two_clips(client, owner_token, viewer_token)
    clips_mod.hide_clips_for_blocked_user(db_path, viewer["id"])
    _toggle_share(client, owner_token)                           # → private while blocked
    clips_mod.restore_clips_hidden_for_reason(db_path, viewer["id"], "blocked_user")
    assert _clip_row(db_path, theirs) == ("hidden", "song_private")
    _toggle_share(client, owner_token)                           # → public
    assert _clip_row(db_path, theirs) == ("published", None)


def test_unblocking_restores_a_clip_of_the_creators_own_private_song(app_client):
    """The owner's own clips follow the existing rules: a private song never hid them,
    so unblocking publishes them as before."""
    client, _db, clips_mod, db_path, owner, viewer, owner_token, viewer_token = app_client
    own, theirs = _two_clips(client, owner_token, viewer_token)
    clips_mod.hide_clips_for_blocked_user(db_path, owner["id"])
    _toggle_share(client, owner_token)
    clips_mod.restore_clips_hidden_for_reason(db_path, owner["id"], "blocked_user")
    assert _clip_row(db_path, own) == ("published", None)
