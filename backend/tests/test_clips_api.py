"""Zeus Clips — HTTP endpoints (Phase 1 of the build brief). Full-app TestClient tests,
following the test_contact_form.py / test_porick_usage_commands.py convention: a real
temp SQLite DB via ZEUS_DATA_DIR + reload, real auth tokens, no mocking of the clips
layer itself.
"""
import importlib
import io
import os
import pathlib
import sqlite3
import sys
from datetime import datetime, timezone
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from PIL import Image

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))
os.environ.setdefault("ANTHROPIC_API_KEY", "test-key")
os.environ.setdefault("APIFRAME_API_KEY", "test-key")
os.environ.setdefault("SONG_STORAGE_PATH", "/tmp/test_songs")
os.environ.setdefault("SONG_PUBLIC_BASE_URL", "https://example.com/files/songs")
os.environ.setdefault("SONG_WEBHOOK_URL", "https://zeusaidesign.com/webhooks/apiframe")
os.environ.setdefault("JWT_SECRET", "test-secret-for-clips-api-tests")

import auth

NOW = datetime(2026, 9, 23, 12, 0, 0, tzinfo=timezone.utc)


@pytest.fixture
def app_client(tmp_path, monkeypatch):
    monkeypatch.setenv("ZEUS_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("SONG_STORAGE_PATH", str(tmp_path / "songs"))
    monkeypatch.setenv("CLIP_STORAGE_PATH", str(tmp_path / "clips"))
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
    # create_user() grants no starting credits (confirmed: no song_credits row at all) — give the
    # viewer a real balance so remix-happy-path tests aren't accidentally testing the 0-credit case.
    conn.execute("INSERT INTO song_credits (user_id, balance) VALUES (?, 5)", (viewer["id"],))
    conn.execute("INSERT INTO lyrics (id, user_id, brief, lyrics_text, title) VALUES "
                 "(1, ?, 'a song about summer love', 'la la la real lyrics here', 'Summer Song')", (owner["id"],))
    conn.execute("INSERT INTO song_variants (id, lyric_id, user_id, style_prompt, genre_tag, status, "
                 "mp3_url, is_public, created_at) VALUES "
                 "(1, 1, ?, 'modern pop, catchy synth melody', 'pop', 'complete', '/files/songs/1.mp3', 1, ?)",
                 (owner["id"], NOW.isoformat()))
    conn.execute("INSERT INTO lyrics (id, user_id, brief, lyrics_text, title) VALUES "
                 "(2, ?, 'a private song', 'la la', 'Private Song')", (owner["id"],))
    conn.execute("INSERT INTO song_variants (id, lyric_id, user_id, style_prompt, genre_tag, status, "
                 "mp3_url, is_public, created_at) VALUES "
                 "(2, 2, ?, 'rock anthem', 'rock', 'complete', '/files/songs/2.mp3', 0, ?)",
                 (owner["id"], NOW.isoformat()))
    conn.commit()
    conn.close()

    owner_token = _main.auth.create_token(owner["id"], owner["email"])
    viewer_token = _main.auth.create_token(viewer["id"], viewer["email"])
    with TestClient(_main.app) as client:
        yield client, _db, _clips, db_path, owner, viewer, owner_token, viewer_token


def _make_paid_user(db_mod, db_path, email="paid@example.com"):
    """Creates a paying, email-verified user ad-hoc within a test — mirrors the existing
    `broke` user pattern (test_remix_with_zero_song_credits_is_refused...) rather than
    growing the shared app_client tuple, so existing positional-unpack call sites can't
    silently bind the wrong variable when a new fixture user is added."""
    user = db_mod.create_user(db_path, email, "x", "Paid", "now")
    conn = sqlite3.connect(db_path)
    conn.execute(
        "UPDATE users SET email_verified = 1, subscription_status = 'active', subscription_plan = 'music_starter' "
        "WHERE id = ?",
        (user["id"],),
    )
    conn.commit()
    conn.close()
    return user, auth.create_token(user["id"], user["email"])


def auth_hdr(token):
    return {"Authorization": f"Bearer {token}"}


def _publish(client, token, song_id=1, **overrides):
    body = {"song_id": song_id, "caption": "check this out", "media_type": "cover",
            "clip_start_time": 2.0, "clip_duration": 15}
    body.update(overrides)
    return client.post("/api/clips", json=body, headers=auth_hdr(token))


def _event_names(db_path, clip_id):
    """All clip_events.event_name rows logged for a given clip_id, in insertion order —
    used to confirm the server actually writes analytics rows, not just returns 200s."""
    conn = sqlite3.connect(db_path)
    rows = conn.execute(
        "SELECT event_name FROM clip_events WHERE clip_id = ? ORDER BY id", (clip_id,)
    ).fetchall()
    conn.close()
    return [r[0] for r in rows]


# ── create ───────────────────────────────────────────────────────────────────

def test_publish_a_cover_clip(app_client):
    client, *_, owner_token, _ = app_client
    r = _publish(client, owner_token)
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["media_type"] == "cover" and body["caption"] == "check this out"
    assert body["like_count"] == 0 and body["view_count"] == 0 and body["remix_count"] == 0


def test_publish_requires_auth(app_client):
    client, *_ = app_client
    r = client.post("/api/clips", json={"song_id": 1, "media_type": "cover", "clip_start_time": 0, "clip_duration": 15})
    assert r.status_code == 401


def test_publish_from_a_private_song_without_make_public_is_rejected(app_client):
    client, *_ , owner_token, _ = app_client
    r = _publish(client, owner_token, song_id=2)
    assert r.status_code == 400
    assert "public" in r.json()["detail"].lower()


def test_publish_with_make_song_public_sets_is_public_and_succeeds(app_client):
    client, db_mod, _clips, db_path, owner, *_ , owner_token, _ = app_client
    r = _publish(client, owner_token, song_id=2, make_song_public=True)
    assert r.status_code == 201, r.text
    conn = sqlite3.connect(db_path)
    is_pub = conn.execute("SELECT is_public FROM song_variants WHERE id = 2").fetchone()[0]
    conn.close()
    assert is_pub == 1


def test_publish_someone_elses_song_is_rejected(app_client):
    client, *_ , viewer_token = app_client
    r = _publish(client, viewer_token, song_id=1)  # song 1 belongs to owner
    assert r.status_code == 404


@pytest.mark.parametrize("duration", [10, 45, 0, -5])
def test_publish_rejects_an_invalid_duration(app_client, duration):
    client, *_ , owner_token, _ = app_client
    r = _publish(client, owner_token, clip_duration=duration)
    assert r.status_code == 422 or r.status_code == 400


def test_publish_rejects_a_caption_over_150_chars(app_client):
    client, *_ , owner_token, _ = app_client
    r = _publish(client, owner_token, caption="x" * 151)
    assert r.status_code in (400, 422)


# ── upload-media ─────────────────────────────────────────────────────────────

def _real_jpeg():
    buf = io.BytesIO()
    Image.new("RGB", (8, 8), (10, 20, 30)).save(buf, format="JPEG")
    return buf.getvalue()


def test_upload_media_accepts_a_real_image_and_returns_a_usable_url(app_client):
    client, db_mod, _clips_unused, db_path, *_ = app_client
    _, paid_token = _make_paid_user(db_mod, db_path)
    r = client.post("/api/clips/upload-media", files={"file": ("photo.jpg", _real_jpeg(), "image/jpeg")},
                    data={"media_type": "image"}, headers=auth_hdr(paid_token))
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["media_type"] == "image"
    assert body["media_url"].startswith("/files/clips/")
    assert body["media_url"].endswith(".jpg")


def test_upload_media_rejects_non_paying_users(app_client):
    """Item 4 of the pre-Phase-2 review: upload-media (custom image/video) is a
    storage-cost feature gated to paying plans, same as scheduled tasks/websites
    elsewhere in this file — free users can still publish a 'cover' clip (no upload
    involved at all), just not upload a custom image or video."""
    client, *_ , owner_token, _ = app_client  # owner is free-tier by construction
    r = client.post("/api/clips/upload-media", files={"file": ("photo.jpg", _real_jpeg(), "image/jpeg")},
                    data={"media_type": "image"}, headers=auth_hdr(owner_token))
    assert r.status_code == 403


def test_upload_media_rejects_a_renamed_exe(app_client):
    client, db_mod, _clips_unused, db_path, *_ = app_client
    _, paid_token = _make_paid_user(db_mod, db_path)
    fake = b"MZ\x90\x00\x03\x00\x00\x00\x04\x00\x00\x00\xff\xff" + b"\x00" * 200
    r = client.post("/api/clips/upload-media", files={"file": ("photo.jpg", fake, "image/jpeg")},
                    data={"media_type": "image"}, headers=auth_hdr(paid_token))
    assert r.status_code == 400


def test_upload_media_rejects_an_oversized_file(app_client):
    client, db_mod, _clips_unused, db_path, *_ = app_client
    _, paid_token = _make_paid_user(db_mod, db_path)
    huge = _real_jpeg() + b"\x00" * (11 * 1024 * 1024)
    r = client.post("/api/clips/upload-media", files={"file": ("photo.jpg", huge, "image/jpeg")},
                    data={"media_type": "image"}, headers=auth_hdr(paid_token))
    assert r.status_code == 400


def test_upload_media_enforces_20_uploads_per_24h_per_user(app_client):
    """Hardening review item 2: a per-user cap, independent of the existing
    20/minute burst rate limiter (which the test fixture disables entirely —
    see app_client). Seeds 20 prior uploads directly rather than POSTing 20 real
    ones — this is a limit test, not a re-test of the upload path itself."""
    client, db_mod, _clips_unused, db_path, *_ = app_client
    paid_user, paid_token = _make_paid_user(db_mod, db_path)
    import clip_uploads
    for i in range(clip_uploads.UPLOAD_RATE_LIMIT):
        clip_uploads.record_upload(db_path, paid_user["id"], f"seed{i}.jpg", "image", 1024)
    r = client.post("/api/clips/upload-media", files={"file": ("photo.jpg", _real_jpeg(), "image/jpeg")},
                    data={"media_type": "image"}, headers=auth_hdr(paid_token))
    assert r.status_code == 429, r.text


def test_upload_media_rate_limit_is_scoped_per_user(app_client):
    client, db_mod, _clips_unused, db_path, *_ = app_client
    limited_user, _ = _make_paid_user(db_mod, db_path, email="limited@example.com")
    other_user, other_token = _make_paid_user(db_mod, db_path, email="other@example.com")
    import clip_uploads
    for i in range(clip_uploads.UPLOAD_RATE_LIMIT):
        clip_uploads.record_upload(db_path, limited_user["id"], f"seed{i}.jpg", "image", 1024)
    r = client.post("/api/clips/upload-media", files={"file": ("photo.jpg", _real_jpeg(), "image/jpeg")},
                    data={"media_type": "image"}, headers=auth_hdr(other_token))
    assert r.status_code == 200, r.text


def test_upload_media_rejects_a_body_over_50mb_via_content_length_before_parsing(app_client):
    """Hardening review item 1: a >50MB body sent directly to the API (not just
    an in-process oversized-file check) must be rejected. This one is caught by
    _MaxUploadSizeMiddleware's Content-Length pre-check — 413, not 400 — which
    fires before Starlette even starts parsing the multipart body, so the
    validators in clip_uploads.py never run at all for this request."""
    client, db_mod, _clips_unused, db_path, *_ = app_client
    _, paid_token = _make_paid_user(db_mod, db_path)
    way_too_big = b"\x00" * (55 * 1024 * 1024)  # over both the 50MB video cap and the 52MB middleware ceiling
    r = client.post("/api/clips/upload-media", files={"file": ("video.mp4", way_too_big, "video/mp4")},
                    data={"media_type": "video"}, headers=auth_hdr(paid_token))
    assert r.status_code == 413, r.text


def test_upload_media_requires_auth(app_client):
    client, *_ = app_client
    r = client.post("/api/clips/upload-media", files={"file": ("photo.jpg", _real_jpeg(), "image/jpeg")},
                    data={"media_type": "image"})
    assert r.status_code == 401


def test_uploaded_image_can_then_be_used_to_publish_a_clip(app_client):
    client, db_mod, _clips_unused, db_path, owner, viewer, owner_token, viewer_token = app_client
    paid_user, paid_token = _make_paid_user(db_mod, db_path)
    up = client.post("/api/clips/upload-media", files={"file": ("photo.jpg", _real_jpeg(), "image/jpeg")},
                     data={"media_type": "image"}, headers=auth_hdr(paid_token))
    url = up.json()["media_url"]
    # publishing itself isn't plan-gated — only the upload step was — so this can publish
    # against the paid user's own song... but there's no song owned by paid_user in the
    # fixture, so publish as the owner using a URL the paid user's upload produced (the
    # media_url itself carries no per-uploader restriction, matching how media_url is
    # just an opaque path once it exists).
    r = _publish(client, owner_token, media_type="image", media_url=url)
    assert r.status_code == 201, r.text
    assert r.json()["media_url"] == url


def test_publishing_an_uploaded_clip_marks_the_upload_attached(app_client):
    """Hardening review item 3: publishing must take the upload out of
    sweep_orphaned_uploads' candidate set — see clip_uploads.mark_upload_attached."""
    client, db_mod, _clips_unused, db_path, owner, viewer, owner_token, viewer_token = app_client
    paid_user, paid_token = _make_paid_user(db_mod, db_path)
    up = client.post("/api/clips/upload-media", files={"file": ("photo.jpg", _real_jpeg(), "image/jpeg")},
                     data={"media_type": "image"}, headers=auth_hdr(paid_token))
    url = up.json()["media_url"]
    filename = url.rsplit("/", 1)[-1]
    r = _publish(client, owner_token, media_type="image", media_url=url)
    assert r.status_code == 201, r.text
    conn = sqlite3.connect(db_path)
    row = conn.execute("SELECT attached_clip_id FROM clip_media_uploads WHERE filename = ?", (filename,)).fetchone()
    conn.close()
    assert row is not None and row[0] == r.json()["id"]


def test_publishing_an_image_clip_without_a_prior_upload_url_is_rejected(app_client):
    client, *_ , owner_token, _ = app_client
    r = _publish(client, owner_token, media_type="image", media_url=None)
    assert r.status_code in (400, 422)


# ── detail / feed ────────────────────────────────────────────────────────────

def test_get_clip_detail_includes_song_and_remix_prefill_fields_never_raw_lyrics(app_client):
    client, *_ , owner_token, _ = app_client
    clip_id = _publish(client, owner_token).json()["id"]
    r = client.get(f"/api/clips/{clip_id}")
    assert r.status_code == 200
    body = r.json()
    assert body["song_title"] == "Summer Song"
    assert "pop" in body["remix_style_descriptors"].lower()
    assert "summer" in body["remix_theme"].lower()
    assert "la la la real lyrics here" not in str(body)


def test_get_clip_detail_is_public_no_auth_needed(app_client):
    client, *_ , owner_token, _ = app_client
    clip_id = _publish(client, owner_token).json()["id"]
    r = client.get(f"/api/clips/{clip_id}")  # no Authorization header
    assert r.status_code == 200


def test_get_clip_404s_for_a_hidden_clip(app_client):
    client, db_mod, clips_mod, db_path, *_ , owner_token, _ = app_client
    clip_id = _publish(client, owner_token).json()["id"]
    clips_mod.set_clip_status(db_path, clip_id, "hidden")
    assert client.get(f"/api/clips/{clip_id}").status_code == 404


def test_get_clip_404s_for_a_deleted_clip(app_client):
    client, db_mod, clips_mod, db_path, *_ , owner_token, _ = app_client
    clip_id = _publish(client, owner_token).json()["id"]
    clips_mod.set_clip_status(db_path, clip_id, "deleted")
    assert client.get(f"/api/clips/{clip_id}").status_code == 404


def test_feed_lists_only_published_clips_new_first(app_client):
    client, *_ , owner_token, _ = app_client
    a = _publish(client, owner_token).json()["id"]
    b = _publish(client, owner_token, song_id=1).json()["id"]
    r = client.get("/api/clips?sort=new")
    assert r.status_code == 200
    ids = [c["id"] for c in r.json()["clips"]]
    assert ids[:2] == [b, a]


def test_feed_and_trending_exclude_hidden_and_deleted_clips(app_client):
    client, db_mod, clips_mod, db_path, *_ , owner_token, _ = app_client
    visible = _publish(client, owner_token).json()["id"]
    hidden = _publish(client, owner_token, song_id=1).json()["id"]
    deleted = _publish(client, owner_token, song_id=1).json()["id"]
    clips_mod.set_clip_status(db_path, hidden, "hidden")
    clips_mod.set_clip_status(db_path, deleted, "deleted")
    for sort in ("new", "trending"):
        ids = [c["id"] for c in client.get(f"/api/clips?sort={sort}").json()["clips"]]
        assert ids == [visible], f"sort={sort} must only list the published clip"


def test_feed_trending_sort_is_accepted(app_client):
    client, *_ = app_client
    r = client.get("/api/clips?sort=trending")
    assert r.status_code == 200 and r.json()["clips"] == []


def test_feed_rejects_an_unknown_sort(app_client):
    client, *_ = app_client
    assert client.get("/api/clips?sort=bogus").status_code in (400, 422)


# ── likes ────────────────────────────────────────────────────────────────────

def test_like_and_unlike_round_trip(app_client):
    client, *_ , owner_token, viewer_token = app_client
    clip_id = _publish(client, owner_token).json()["id"]
    r = client.post(f"/api/clips/{clip_id}/like", headers=auth_hdr(viewer_token))
    assert r.status_code == 200 and r.json()["like_count"] == 1
    r = client.delete(f"/api/clips/{clip_id}/like", headers=auth_hdr(viewer_token))
    assert r.status_code == 200 and r.json()["like_count"] == 0


def test_like_requires_auth(app_client):
    client, *_ , owner_token, _ = app_client
    clip_id = _publish(client, owner_token).json()["id"]
    assert client.post(f"/api/clips/{clip_id}/like").status_code == 401


def test_liking_a_clip_logs_a_clip_liked_event(app_client):
    client, db_mod, clips_mod, db_path, *_ , owner_token, viewer_token = app_client
    clip_id = _publish(client, owner_token).json()["id"]
    client.post(f"/api/clips/{clip_id}/like", headers=auth_hdr(viewer_token))
    assert "clip_liked" in _event_names(db_path, clip_id)


# ── views (auth optional; anon_id fallback) ──────────────────────────────────

def test_view_by_logged_in_user_counts_once(app_client):
    client, *_ , owner_token, viewer_token = app_client
    clip_id = _publish(client, owner_token).json()["id"]
    r1 = client.post(f"/api/clips/{clip_id}/view", headers=auth_hdr(viewer_token))
    r2 = client.post(f"/api/clips/{clip_id}/view", headers=auth_hdr(viewer_token))
    assert r1.json()["view_count"] == 1
    assert r2.json()["view_count"] == 1


def test_view_by_anonymous_visitor_uses_anon_id(app_client):
    client, *_ , owner_token, _ = app_client
    clip_id = _publish(client, owner_token).json()["id"]
    r1 = client.post(f"/api/clips/{clip_id}/view", json={"anon_id": "anon-abc"})
    r2 = client.post(f"/api/clips/{clip_id}/view", json={"anon_id": "anon-abc"})
    assert r1.status_code == 200 and r1.json()["view_count"] == 1
    assert r2.json()["view_count"] == 1


def test_view_with_neither_auth_nor_anon_id_is_rejected(app_client):
    client, *_ , owner_token, _ = app_client
    clip_id = _publish(client, owner_token).json()["id"]
    assert client.post(f"/api/clips/{clip_id}/view", json={}).status_code == 400


# ── report ───────────────────────────────────────────────────────────────────

def test_report_a_clip(app_client):
    client, *_ , owner_token, viewer_token = app_client
    clip_id = _publish(client, owner_token).json()["id"]
    r = client.post(f"/api/clips/{clip_id}/report", json={"reason": "spam"}, headers=auth_hdr(viewer_token))
    assert r.status_code == 200


def test_report_requires_auth(app_client):
    client, *_ , owner_token, _ = app_client
    clip_id = _publish(client, owner_token).json()["id"]
    assert client.post(f"/api/clips/{clip_id}/report", json={"reason": "spam"}).status_code == 401


def test_report_rejects_an_unknown_reason(app_client):
    client, *_ , owner_token, viewer_token = app_client
    clip_id = _publish(client, owner_token).json()["id"]
    r = client.post(f"/api/clips/{clip_id}/report", json={"reason": "nonsense"}, headers=auth_hdr(viewer_token))
    assert r.status_code in (400, 422)


# ── delete (owner) ───────────────────────────────────────────────────────────

def test_owner_can_delete_their_own_clip(app_client):
    client, *_ , owner_token, _ = app_client
    clip_id = _publish(client, owner_token).json()["id"]
    r = client.delete(f"/api/clips/{clip_id}", headers=auth_hdr(owner_token))
    assert r.status_code == 200
    assert client.get(f"/api/clips/{clip_id}").status_code == 404


def test_non_owner_cannot_delete_a_clip(app_client):
    client, *_ , owner_token, viewer_token = app_client
    clip_id = _publish(client, owner_token).json()["id"]
    r = client.delete(f"/api/clips/{clip_id}", headers=auth_hdr(viewer_token))
    assert r.status_code in (403, 404)
    assert client.get(f"/api/clips/{clip_id}").status_code == 200


def test_deleting_a_clip_is_a_soft_delete_and_does_not_touch_the_songs_is_public(app_client):
    """Approved decision: DELETE is a SOFT delete (status='deleted') — the row is kept
    for analytics/remix links, and the source song's is_public is left exactly as it was."""
    client, db_mod, clips_mod, db_path, *_ , owner_token, _ = app_client
    r = _publish(client, owner_token, make_song_public=True)  # song 1 starts public anyway
    clip_id = r.json()["id"]
    conn = sqlite3.connect(db_path)
    before = conn.execute("SELECT is_public FROM song_variants WHERE id = 1").fetchone()[0]
    conn.close()
    client.delete(f"/api/clips/{clip_id}", headers=auth_hdr(owner_token))
    conn = sqlite3.connect(db_path)
    after = conn.execute("SELECT is_public FROM song_variants WHERE id = 1").fetchone()[0]
    row_still_exists = conn.execute("SELECT status FROM clips WHERE id = ?", (clip_id,)).fetchone()
    conn.close()
    assert after == before
    assert row_still_exists is not None and row_still_exists[0] == "deleted"


# ── remix ────────────────────────────────────────────────────────────────────

def test_remix_requires_auth(app_client):
    client, *_ , owner_token, _ = app_client
    clip_id = _publish(client, owner_token).json()["id"]
    assert client.post(f"/api/clips/{clip_id}/remix").status_code == 401


def test_remix_is_blocked_for_an_unverified_email_same_as_normal_generation(app_client):
    client, db_mod, _clips, db_path, owner, *_ , owner_token, _ = app_client
    clip_id = _publish(client, owner_token).json()["id"]
    unverified = db_mod.create_user(db_path, "new@example.com", "x", "New", "now")
    token = auth.create_token(unverified["id"], unverified["email"])
    r = client.post(f"/api/clips/{clip_id}/remix", headers=auth_hdr(token))
    assert r.status_code == 403
    assert r.json()["detail"]["code"] == "email_unverified"


def _mock_generation(db_path, user_id, lyric_id=555, title="Remixed"):
    """Mocks the SAME two boundaries songs_generate itself hits: the Claude lyrics call
    (lyrics.generate_lyrics) and the actual Apiframe network submission
    (songs._submit_to_apiframe). Everything BETWEEN them — the real credit check/deduct,
    the real song_variants INSERT, the real ownership check inside generate_song_variant —
    runs for real, so these tests exercise the real wiring, not a fabricated shortcut.

    The mocked generate_lyrics still does a REAL minimal lyrics INSERT (matching what the
    unmocked function would do): generate_song_variant looks the row up by
    (lyric_id, user_id) right afterward, so a mock that only returns a dict without ever
    writing the row would fail that real, unmocked lookup."""
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


def test_starting_a_remix_creates_a_pending_row_and_does_not_yet_increment_remix_count(app_client):
    client, db_mod, clips_mod, db_path, owner, viewer, owner_token, viewer_token = app_client
    clip_id = _publish(client, owner_token).json()["id"]
    p1, p2 = _mock_generation(db_path, viewer["id"], lyric_id=555)
    with p1, p2:
        r = client.post(f"/api/clips/{clip_id}/remix", headers=auth_hdr(viewer_token))
    assert r.status_code == 202, r.text
    body = r.json()
    assert body["lyric_id"] == 555 and isinstance(body["variant_id"], int)
    assert client.get(f"/api/clips/{clip_id}").json()["remix_count"] == 0
    remix = clips_mod.get_remix(db_path, body["remix_id"])
    assert remix["lyric_id"] == 555 and remix["remix_song_id"] is None
    assert "remix_started" in _event_names(db_path, clip_id)


def test_publishing_and_viewing_a_clip_log_their_own_events(app_client):
    """Confirms item 4's clip_published / clip_viewed rows land server-side — the
    endpoints that already call clips.log_event, checked at the DB row level rather
    than just trusting the 200."""
    client, db_mod, clips_mod, db_path, *_ , owner_token, viewer_token = app_client
    clip_id = _publish(client, owner_token).json()["id"]
    assert _event_names(db_path, clip_id) == ["clip_published"]
    client.post(f"/api/clips/{clip_id}/view", headers=auth_hdr(viewer_token))
    assert _event_names(db_path, clip_id) == ["clip_published", "clip_viewed"]


def test_remixing_sends_the_theme_and_style_but_never_the_source_songs_raw_lyrics(app_client):
    client, db_mod, clips_mod, db_path, owner, viewer, owner_token, viewer_token = app_client
    clip_id = _publish(client, owner_token).json()["id"]
    p1, p2 = _mock_generation(db_path, viewer["id"])
    with p1 as gen_lyrics, p2:
        client.post(f"/api/clips/{clip_id}/remix", headers=auth_hdr(viewer_token))
    assert gen_lyrics.called
    _args, kwargs = gen_lyrics.call_args
    assert "la la la real lyrics here" not in str(kwargs)  # the source clip's raw lyrics_text
    assert "summer" in str(kwargs.get("inspired_by_theme", "")).lower()


def test_remix_costs_a_credit_and_is_actually_deducted(app_client):
    client, db_mod, _clips, db_path, owner, viewer, owner_token, viewer_token = app_client
    clip_id = _publish(client, owner_token).json()["id"]
    p1, p2 = _mock_generation(db_path, viewer["id"])
    with p1, p2:
        r = client.post(f"/api/clips/{clip_id}/remix", headers=auth_hdr(viewer_token))
    assert r.status_code == 202, r.text
    conn = sqlite3.connect(db_path)
    balance = conn.execute("SELECT balance FROM song_credits WHERE user_id = ?", (viewer["id"],)).fetchone()[0]
    conn.close()
    assert balance == 4, "started at 5, one remix (one genre) must deduct exactly one credit"


def test_remix_with_zero_song_credits_is_refused_same_as_normal_generation(app_client):
    client, db_mod, _clips, db_path, owner, *_ , owner_token, _ = app_client
    broke = db_mod.create_user(db_path, "broke@example.com", "x", "Broke", "now")
    conn = sqlite3.connect(db_path)
    conn.execute("UPDATE users SET email_verified = 1 WHERE id = ?", (broke["id"],))
    conn.commit(); conn.close()
    broke_token = auth.create_token(broke["id"], broke["email"])  # no song_credits row at all
    clip_id = _publish(client, owner_token).json()["id"]
    p1, p2 = _mock_generation(db_path, broke["id"])
    with p1, p2 as submit:
        r = client.post(f"/api/clips/{clip_id}/remix", headers=auth_hdr(broke_token))
    assert r.status_code == 402
    assert not submit.called, "must be refused before ever reaching the Apiframe submission"


def test_a_failed_apiframe_submission_refunds_the_credit_and_does_not_leave_a_dangling_remix(app_client):
    client, db_mod, clips_mod, db_path, owner, viewer, owner_token, viewer_token = app_client
    clip_id = _publish(client, owner_token).json()["id"]
    with patch("lyrics.generate_lyrics", return_value={"lyric_id": 999, "lyrics": "x", "title": "x"}), \
         patch("songs._submit_to_apiframe", side_effect=RuntimeError("network down")):
        r = client.post(f"/api/clips/{clip_id}/remix", headers=auth_hdr(viewer_token))
    assert r.status_code >= 500
    conn = sqlite3.connect(db_path)
    balance = conn.execute("SELECT balance FROM song_credits WHERE user_id = ?", (viewer["id"],)).fetchone()[0]
    conn.close()
    assert balance == 5, "the credit must be refunded (generate_song_variant already does this on submit failure)"


# ── static media serving (point 2 of the approved additions) ────────────────

def test_uploaded_clip_media_is_served_with_cache_control_and_supports_range(app_client, tmp_path):
    """Unlike /files/songs (see test_song_file_cache_control.py), clip upload filenames
    are random and never rewritten, so these stay long/immutable."""
    client, *_ = app_client
    clip_dir = pathlib.Path(os.environ["CLIP_STORAGE_PATH"])
    clip_dir.mkdir(parents=True, exist_ok=True)
    (clip_dir / "abc123.jpg").write_bytes(_real_jpeg())
    r = client.get("/files/clips/abc123.jpg")
    assert r.status_code == 200
    assert r.headers.get("cache-control", "") == "public, max-age=31536000, immutable"
    r2 = client.get("/files/clips/abc123.jpg", headers={"Range": "bytes=0-3"})
    assert r2.status_code == 206
    assert r2.headers.get("content-range", "").startswith("bytes 0-3/")


# ── webhook completion hook (source-inspection — see test_clips_db.py for the
# actual linking logic; this only pins that all three provider webhooks call it) ──

def test_maybe_complete_remix_two_variants_one_lyric_increments_remix_count_once(app_client):
    """Exercises webhooks._maybe_complete_remix itself (the actual function every provider
    webhook calls), not just clips.complete_remix_for_lyric in isolation — confirms the
    DB_PATH lookup + clip_remixes linking wiring works end to end, and that calling it for
    BOTH variants of a standard 2-variant generation only counts the remix once and logs
    remix_completed exactly once (never per-variant)."""
    client, db_mod, clips_mod, db_path, owner, viewer, owner_token, viewer_token = app_client
    clip_id = _publish(client, owner_token).json()["id"]

    import webhooks
    with patch.object(webhooks, "DB_PATH", str(db_path)):
        conn = sqlite3.connect(db_path)
        conn.execute("INSERT INTO lyrics (id, user_id, brief, lyrics_text, title) VALUES "
                     "(777, ?, '', 'x', 'Remix')", (viewer["id"],))
        conn.execute("INSERT INTO song_variants (id, lyric_id, user_id, style_prompt, status, take_number) "
                     "VALUES (301, 777, ?, 's', 'complete', 1)", (viewer["id"],))
        conn.execute("INSERT INTO song_variants (id, lyric_id, user_id, style_prompt, status, take_number) "
                     "VALUES (302, 777, ?, 's', 'complete', 2)", (viewer["id"],))
        conn.commit(); conn.close()
        remix_id = clips_mod.start_remix(db_path, original_clip_id=clip_id, original_song_id=1,
                                         user_id=viewer["id"], lyric_id=777)

        webhooks._maybe_complete_remix(301)
        webhooks._maybe_complete_remix(302)  # second variant of the same generation — must be a no-op

    assert clips_mod.get_remix(db_path, remix_id)["remix_song_id"] == 301
    assert client.get(f"/api/clips/{clip_id}").json()["remix_count"] == 1
    assert _event_names(db_path, clip_id).count("remix_completed") == 1


def test_every_provider_webhook_completion_site_hooks_the_remix_completer():
    import inspect
    import webhooks
    src = inspect.getsource(webhooks)
    assert src.count("_maybe_complete_remix(") >= 3, (
        "clips.complete_remix_for_lyric must be reachable from every provider's "
        "own completion path (apiframe/cometapi/goapi), not just the primary one"
    )
