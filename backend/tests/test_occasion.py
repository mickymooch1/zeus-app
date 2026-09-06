"""Occasion types for the song share page (memorial/birthday/anniversary/
celebration/none) and the Open Graph image-priority rule for them.

Two things covered:
  1. POST /api/songs/variants/{id}/occasion — owner-only, validates the
     occasion enum, editable any time (same as photos/QR).
  2. _get_public_song_for_share_og — the OG-tag helper used by serve_spa.
     Image priority mirrors the existing photo privacy split: a numeric
     identifier must NEVER surface a photo (it may be printed/engraved from
     before photos existed), so it always gets cover art regardless of
     whether photos exist. Only the token identifier, when photos exist,
     prefers the first uploaded one.
"""
import importlib
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
os.environ.setdefault("JWT_SECRET", "test-secret-for-occasion-tests")


@pytest.fixture()
def app_client(tmp_path, monkeypatch):
    monkeypatch.setenv("ZEUS_DATA_DIR", str(tmp_path))
    import db as _db
    importlib.reload(_db)

    db_path = _db.get_db_path()
    owner = _db.create_user(db_path, email="owner@example.com", password_hash="x",
                             name="Owner", tc_accepted_at="now")
    other = _db.create_user(db_path, email="other@example.com", password_hash="x",
                             name="Other", tc_accepted_at="now")

    conn = _db._conn(db_path)
    try:
        conn.execute(
            "INSERT INTO lyrics (id, user_id, title, brief, lyrics_text, created_at) "
            "VALUES (1, ?, 'Test Song', 'a brief', 'la la la', datetime('now'))",
            (owner["id"],),
        )
        conn.execute(
            """INSERT INTO song_variants
               (id, lyric_id, user_id, genre_tag, style_prompt, take_number, status,
                mp3_url, image_url, duration_seconds, created_at)
               VALUES (100, 1, ?, 'pop', 'a pop track', 1, 'complete',
                       'http://a.mp3', 'http://cover.png', 180, datetime('now'))""",
            (owner["id"],),
        )
        conn.commit()
    finally:
        conn.close()

    import main as _main
    importlib.reload(_main)
    import auth as _auth

    def _owner_user():
        return {"id": owner["id"], "email": owner["email"]}

    _main.app.dependency_overrides[_auth.get_current_user] = _owner_user
    try:
        with TestClient(_main.app) as client:
            yield client, _db, _main, db_path, owner, other
    finally:
        _main.app.dependency_overrides.pop(_auth.get_current_user, None)


# ── Schema ────────────────────────────────────────────────────────────────

def test_occasion_columns_exist_and_default_to_null(app_client):
    _, _db, _main, db_path, _, _ = app_client
    conn = _db._conn(db_path)
    try:
        cols = [r[1] for r in conn.execute("PRAGMA table_info(song_variants)")]
    finally:
        conn.close()
    assert "occasion" in cols
    assert "occasion_name" in cols

    variant = _db.get_song_variant_by_id(db_path, 100)
    assert variant.get("occasion") is None
    assert variant.get("occasion_name") is None


# ── POST .../occasion ────────────────────────────────────────────────────

@pytest.mark.parametrize("occasion", ["memorial", "birthday", "anniversary", "celebration"])
def test_set_occasion_accepts_each_allowed_value(app_client, occasion):
    client, _db, _main, db_path, _, _ = app_client
    resp = client.post("/api/songs/variants/100/occasion",
                        json={"occasion": occasion, "occasion_name": "Alex"})
    assert resp.status_code == 200
    assert resp.json() == {"variant_id": 100, "occasion": occasion, "occasion_name": "Alex"}
    variant = _db.get_song_variant_by_id(db_path, 100)
    assert variant["occasion"] == occasion
    assert variant["occasion_name"] == "Alex"


def test_set_occasion_rejects_invalid_value(app_client):
    client, _db, _main, db_path, _, _ = app_client
    resp = client.post("/api/songs/variants/100/occasion",
                        json={"occasion": "not-a-real-occasion", "occasion_name": "Alex"})
    assert resp.status_code == 400
    variant = _db.get_song_variant_by_id(db_path, 100)
    assert variant["occasion"] is None


def test_set_occasion_can_clear_back_to_none(app_client):
    client, _db, _main, db_path, _, _ = app_client
    client.post("/api/songs/variants/100/occasion", json={"occasion": "birthday", "occasion_name": "Sam"})
    resp = client.post("/api/songs/variants/100/occasion", json={"occasion": None, "occasion_name": None})
    assert resp.status_code == 200
    variant = _db.get_song_variant_by_id(db_path, 100)
    assert variant["occasion"] is None
    assert variant["occasion_name"] is None


def test_set_occasion_404s_for_nonexistent_variant(app_client):
    client, _, _main, _, _, _ = app_client
    resp = client.post("/api/songs/variants/999999/occasion", json={"occasion": "birthday"})
    assert resp.status_code == 404


def test_set_occasion_404s_for_non_owner(app_client):
    client, _db, _main, db_path, _, other = app_client

    def _other_user():
        return {"id": other["id"], "email": other["email"]}

    _main.app.dependency_overrides[__import__("auth").get_current_user] = _other_user
    resp = client.post("/api/songs/variants/100/occasion", json={"occasion": "birthday"})
    assert resp.status_code == 404


# ── occasion surfaced on public/library/lyric-variants endpoints ────────

def test_public_endpoint_surfaces_occasion_for_numeric_identifier(app_client):
    client, _db, _main, db_path, _, _ = app_client
    client.post("/api/songs/variants/100/occasion", json={"occasion": "memorial", "occasion_name": "Mary & Mike"})

    resp = client.get("/api/songs/variants/100/public")
    assert resp.status_code == 200
    body = resp.json()
    assert body["occasion"] == "memorial"
    assert body["occasion_name"] == "Mary & Mike"


def test_public_endpoint_surfaces_occasion_for_token_identifier(app_client):
    client, _db, _main, db_path, _, _ = app_client
    client.post("/api/songs/variants/100/occasion", json={"occasion": "birthday", "occasion_name": "Sam"})
    token = _db.get_or_create_share_token(db_path, 100)

    resp = client.get(f"/api/songs/variants/{token}/public")
    assert resp.status_code == 200
    body = resp.json()
    assert body["occasion"] == "birthday"
    assert body["occasion_name"] == "Sam"


def test_library_endpoint_surfaces_occasion(app_client):
    client, _db, _main, db_path, _, _ = app_client
    client.post("/api/songs/variants/100/occasion", json={"occasion": "anniversary", "occasion_name": "Pat & Jo"})

    resp = client.get("/api/library")
    variants = {v["variant_id"]: v for v in resp.json()["variants"]}
    assert variants[100]["occasion"] == "anniversary"
    assert variants[100]["occasion_name"] == "Pat & Jo"


def test_lyric_variants_endpoint_surfaces_occasion_default_none(app_client):
    client, _db, _main, db_path, _, _ = app_client
    resp = client.get("/api/lyrics/1/variants")
    variants = {v["variant_id"]: v for v in resp.json()["variants"]}
    assert variants[100]["occasion"] is None
    assert variants[100]["occasion_name"] is None


# ── _get_public_song_for_share_og image-priority + description ──────────

def test_og_helper_numeric_identifier_always_uses_cover_art_even_with_photos(app_client):
    client, _db, _main, db_path, _, _ = app_client
    _db.add_song_variant_photo(db_path, 100, "100_photo_first.jpg")
    _db.add_song_variant_photo(db_path, 100, "100_photo_second.jpg")

    song = _main._get_public_song_for_share_og("100")
    assert song["image_url"] == "http://cover.png"


def test_og_helper_token_identifier_prefers_first_uploaded_photo(app_client):
    client, _db, _main, db_path, _, _ = app_client
    _db.add_song_variant_photo(db_path, 100, "100_photo_first.jpg")
    _db.add_song_variant_photo(db_path, 100, "100_photo_second.jpg")
    token = _db.get_or_create_share_token(db_path, 100)

    song = _main._get_public_song_for_share_og(token)
    assert song["image_url"] == "https://example.com/files/songs/100_photo_first.jpg"


def test_og_helper_token_identifier_falls_back_to_cover_art_with_no_photos(app_client):
    client, _db, _main, db_path, _, _ = app_client
    token = _db.get_or_create_share_token(db_path, 100)

    song = _main._get_public_song_for_share_og(token)
    assert song["image_url"] == "http://cover.png"


@pytest.mark.parametrize("occasion,expected_substring", [
    ("memorial", "loving memory"),
    ("birthday", "birthday"),
    ("anniversary", "anniversary"),
    ("celebration", "celebrate"),
    (None, "Listen to this song"),
])
def test_og_helper_description_matches_occasion(app_client, occasion, expected_substring):
    client, _db, _main, db_path, _, _ = app_client
    if occasion:
        client.post("/api/songs/variants/100/occasion", json={"occasion": occasion, "occasion_name": "Alex"})

    song = _main._get_public_song_for_share_og("100")
    assert expected_substring in song["description"]


def test_og_helper_returns_none_for_incomplete_variant(app_client):
    client, _db, _main, db_path, owner, _ = app_client
    conn = _db._conn(db_path)
    try:
        conn.execute(
            """INSERT INTO song_variants
               (id, lyric_id, user_id, genre_tag, style_prompt, take_number, status, created_at)
               VALUES (101, 1, ?, 'pop', 'a pop track', 1, 'pending', datetime('now'))""",
            (owner["id"],),
        )
        conn.commit()
    finally:
        conn.close()
    assert _main._get_public_song_for_share_og("101") is None


def test_og_helper_returns_none_for_unknown_identifier(app_client):
    client, _db, _main, db_path, _, _ = app_client
    assert _main._get_public_song_for_share_og("999999") is None
    assert _main._get_public_song_for_share_og("not-a-real-token") is None


# ── serve_spa OG injection — the actual HTML a real crawler receives ────
#
# Regression: WhatsApp's real crawler UA is "WhatsApp/2.23.20.0" (confirmed
# from a live production request, not a spoofed test UA), and it IS matched
# by SOCIAL_CRAWLERS. But the injected <title>+og:*+twitter:* block was only
# ever replacing the static <title> tag in web-beats-dist/index.html — the
# static og:*/twitter:* tags baked into that file's <head> were left in
# place right after it, so the response shipped BOTH the correct song tags
# and the generic homepage tags for the same og:property. WhatsApp's parser
# resolved the duplicate by using the last-seen value, i.e. the generic one
# — showing the homepage promo card instead of the song, even though the
# correct tags were present (and first) in the HTML.
#
# The prior _get_public_song_for_share_og unit tests above never caught this
# because they call the helper directly and never render through serve_spa,
# so they never see the final HTML a crawler actually parses.

def test_whatsapp_crawler_gets_song_og_tags_without_duplicates(app_client):
    client, _db, _main, db_path, _, _ = app_client
    client.post("/api/songs/variants/100/occasion", json={"occasion": "memorial", "occasion_name": "Alex"})
    token = _db.get_or_create_share_token(db_path, 100)

    resp = client.get(
        f"/songs/share/{token}",
        headers={"User-Agent": "WhatsApp/2.23.20.0", "Host": "zeusbeats.com"},
    )
    assert resp.status_code == 200
    html = resp.text

    assert html.count('property="og:title"') == 1, "duplicate og:title tag — generic static tag not removed"
    assert html.count('property="og:image"') == 1, "duplicate og:image tag — generic static tag not removed"
    assert html.count('name="twitter:image"') == 1, "duplicate twitter:image tag — generic static tag not removed"
    assert 'content="Test Song"' in html
    assert "Zeus Beats — Create AI Music in Seconds" not in html
