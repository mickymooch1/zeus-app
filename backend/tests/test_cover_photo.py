"""Let an uploaded photo replace the AI cover art as a song's primary image.

Storage: song_variants.cover_photo_id, a nullable pointer into
song_variant_photos. NULL (default) = AI cover art shows everywhere,
unchanged from before this feature existed. The AI art itself
(song_variants.image_url) is never touched — switching back to it is just
clearing cover_photo_id, not restoring anything.

Resolution differs by context:
  - Owner's own view (/api/library, /api/lyrics/{id}/variants): no privacy
    gate, cover_photo_id wins whenever set.
  - Public share page (/public): numeric identifier ALWAYS gets the AI art
    regardless of cover_photo_id (same rule as photos generally); token
    identifier prefers cover_photo_id.
  - OG social-preview helper: numeric always AI art; token prefers
    cover_photo_id, then falls back to the existing "first uploaded photo"
    heuristic, then AI art.

Deleting the photo currently set as cover clears cover_photo_id back to
NULL rather than leaving it pointing at nothing.
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
os.environ.setdefault("JWT_SECRET", "test-secret-for-cover-photo-tests")


@pytest.fixture()
def app_client(tmp_path, monkeypatch):
    monkeypatch.setenv("ZEUS_DATA_DIR", str(tmp_path))
    photo_storage = tmp_path / "songs"
    photo_storage.mkdir()
    monkeypatch.setenv("SONG_STORAGE_PATH", str(photo_storage))

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

    photo_a_id = _db.add_song_variant_photo(db_path, 100, "100_photo_a.jpg")
    photo_b_id = _db.add_song_variant_photo(db_path, 100, "100_photo_b.jpg")
    for fname in ("100_photo_a.jpg", "100_photo_b.jpg"):
        (photo_storage / fname).write_bytes(b"fake-jpeg-bytes")
    token = _db.get_or_create_share_token(db_path, 100)

    import main as _main
    importlib.reload(_main)
    import auth as _auth

    def _owner_user():
        return {"id": owner["id"], "email": owner["email"]}

    _main.app.dependency_overrides[_auth.get_current_user] = _owner_user
    try:
        with TestClient(_main.app) as client:
            yield client, _db, _main, db_path, owner, other, photo_a_id, photo_b_id, token
    finally:
        _main.app.dependency_overrides.pop(_auth.get_current_user, None)


# ── Schema ────────────────────────────────────────────────────────────────

def test_cover_photo_id_column_exists_and_defaults_to_null(app_client):
    _, _db, _main, db_path, *_ = app_client
    conn = _db._conn(db_path)
    try:
        cols = [r[1] for r in conn.execute("PRAGMA table_info(song_variants)")]
    finally:
        conn.close()
    assert "cover_photo_id" in cols
    variant = _db.get_song_variant_by_id(db_path, 100)
    assert variant.get("cover_photo_id") is None


# ── POST .../cover-photo ─────────────────────────────────────────────────

def test_set_cover_photo_to_a_valid_photo(app_client):
    client, _db, _main, db_path, _, _, photo_a_id, _, _ = app_client
    resp = client.post("/api/songs/variants/100/cover-photo", json={"photo_id": photo_a_id})
    assert resp.status_code == 200
    assert resp.json() == {
        "variant_id": 100, "cover_photo_id": photo_a_id,
        "image_url": "https://example.com/files/songs/100_photo_a.jpg",
    }
    variant = _db.get_song_variant_by_id(db_path, 100)
    assert variant["cover_photo_id"] == photo_a_id


def test_set_cover_photo_null_clears_it(app_client):
    client, _db, _main, db_path, _, _, photo_a_id, _, _ = app_client
    client.post("/api/songs/variants/100/cover-photo", json={"photo_id": photo_a_id})
    resp = client.post("/api/songs/variants/100/cover-photo", json={"photo_id": None})
    assert resp.status_code == 200
    variant = _db.get_song_variant_by_id(db_path, 100)
    assert variant["cover_photo_id"] is None


def test_set_cover_photo_rejects_a_photo_from_another_variant(app_client):
    client, _db, _main, db_path, owner, _, _, _, _ = app_client
    conn = _db._conn(db_path)
    try:
        conn.execute(
            """INSERT INTO song_variants
               (id, lyric_id, user_id, genre_tag, style_prompt, take_number, status, created_at)
               VALUES (200, 1, ?, 'pop', 'x', 1, 'complete', datetime('now'))""",
            (owner["id"],),
        )
        conn.commit()
    finally:
        conn.close()
    other_photo_id = _db.add_song_variant_photo(db_path, 200, "200_photo.jpg")

    resp = client.post("/api/songs/variants/100/cover-photo", json={"photo_id": other_photo_id})
    assert resp.status_code == 404
    variant = _db.get_song_variant_by_id(db_path, 100)
    assert variant["cover_photo_id"] is None


def test_set_cover_photo_rejects_nonexistent_photo_id(app_client):
    client, _db, _main, db_path, *_ = app_client
    resp = client.post("/api/songs/variants/100/cover-photo", json={"photo_id": 999999})
    assert resp.status_code == 404


def test_set_cover_photo_404s_for_nonexistent_variant(app_client):
    client, _, _main, _, _, _, photo_a_id, _, _ = app_client
    resp = client.post("/api/songs/variants/999999/cover-photo", json={"photo_id": photo_a_id})
    assert resp.status_code == 404


def test_set_cover_photo_404s_for_non_owner(app_client):
    client, _db, _main, db_path, _, other, photo_a_id, _, _ = app_client

    def _other_user():
        return {"id": other["id"], "email": other["email"]}

    _main.app.dependency_overrides[__import__("auth").get_current_user] = _other_user
    resp = client.post("/api/songs/variants/100/cover-photo", json={"photo_id": photo_a_id})
    assert resp.status_code == 404


# ── resolution: owner's own view (library / lyric-variants) ────────────

def test_library_shows_cover_photo_when_set(app_client):
    client, _db, _main, db_path, _, _, photo_a_id, _, _ = app_client
    client.post("/api/songs/variants/100/cover-photo", json={"photo_id": photo_a_id})

    resp = client.get("/api/library")
    variants = {v["variant_id"]: v for v in resp.json()["variants"]}
    assert variants[100]["image_url"] == "https://example.com/files/songs/100_photo_a.jpg"
    assert variants[100]["cover_photo_id"] == photo_a_id


def test_library_shows_ai_art_when_no_cover_set(app_client):
    client, _db, _main, db_path, *_ = app_client
    resp = client.get("/api/library")
    variants = {v["variant_id"]: v for v in resp.json()["variants"]}
    assert variants[100]["image_url"] == "http://cover.png"
    assert variants[100]["cover_photo_id"] is None


def test_lyric_variants_shows_cover_photo_when_set(app_client):
    client, _db, _main, db_path, _, _, photo_a_id, _, _ = app_client
    client.post("/api/songs/variants/100/cover-photo", json={"photo_id": photo_a_id})

    resp = client.get("/api/lyrics/1/variants")
    variants = {v["variant_id"]: v for v in resp.json()["variants"]}
    assert variants[100]["image_url"] == "https://example.com/files/songs/100_photo_a.jpg"


# ── resolution: /public endpoint (numeric vs token) ─────────────────────

def test_public_numeric_identifier_always_shows_ai_art_even_with_cover_set(app_client):
    client, _db, _main, db_path, _, _, photo_a_id, _, _ = app_client
    client.post("/api/songs/variants/100/cover-photo", json={"photo_id": photo_a_id})

    resp = client.get("/api/songs/variants/100/public")
    assert resp.json()["image_url"] == "http://cover.png"


def test_public_token_identifier_shows_cover_photo_when_set(app_client):
    client, _db, _main, db_path, _, _, photo_a_id, _, token = app_client
    client.post("/api/songs/variants/100/cover-photo", json={"photo_id": photo_a_id})

    resp = client.get(f"/api/songs/variants/{token}/public")
    assert resp.json()["image_url"] == "https://example.com/files/songs/100_photo_a.jpg"


def test_public_token_identifier_shows_ai_art_when_no_cover_set(app_client):
    client, _db, _main, db_path, _, _, _, _, token = app_client
    resp = client.get(f"/api/songs/variants/{token}/public")
    assert resp.json()["image_url"] == "http://cover.png"


# ── resolution: OG helper ────────────────────────────────────────────────

def test_og_helper_numeric_always_ai_art_even_with_cover_set(app_client):
    client, _db, _main, db_path, _, _, photo_a_id, _, _ = app_client
    client.post("/api/songs/variants/100/cover-photo", json={"photo_id": photo_a_id})

    song = _main._get_public_song_for_share_og("100")
    assert song["image_url"] == "http://cover.png"


def test_og_helper_token_prefers_explicit_cover_over_first_photo_heuristic(app_client):
    client, _db, _main, db_path, _, _, photo_a_id, photo_b_id, token = app_client
    # photo_a was uploaded first (the "first photo" heuristic would pick it by
    # default), but explicitly choosing photo_b as cover must win instead.
    client.post("/api/songs/variants/100/cover-photo", json={"photo_id": photo_b_id})

    song = _main._get_public_song_for_share_og(token)
    assert song["image_url"] == "https://example.com/files/songs/100_photo_b.jpg"


def test_og_helper_token_falls_back_to_first_photo_when_no_cover_set(app_client):
    client, _db, _main, db_path, _, _, photo_a_id, photo_b_id, token = app_client
    song = _main._get_public_song_for_share_og(token)
    assert song["image_url"] == "https://example.com/files/songs/100_photo_a.jpg"


# ── delete-cascade ────────────────────────────────────────────────────────

def test_deleting_the_cover_photo_clears_cover_photo_id(app_client):
    client, _db, _main, db_path, _, _, photo_a_id, _, _ = app_client
    client.post("/api/songs/variants/100/cover-photo", json={"photo_id": photo_a_id})

    resp = client.delete(f"/api/songs/variants/100/photos/{photo_a_id}")
    assert resp.status_code == 200
    variant = _db.get_song_variant_by_id(db_path, 100)
    assert variant["cover_photo_id"] is None


def test_deleting_a_non_cover_photo_leaves_cover_photo_id_untouched(app_client):
    client, _db, _main, db_path, _, _, photo_a_id, photo_b_id, _ = app_client
    client.post("/api/songs/variants/100/cover-photo", json={"photo_id": photo_a_id})

    resp = client.delete(f"/api/songs/variants/100/photos/{photo_b_id}")
    assert resp.status_code == 200
    variant = _db.get_song_variant_by_id(db_path, 100)
    assert variant["cover_photo_id"] == photo_a_id


# ── switching back to AI art ─────────────────────────────────────────────

def test_switch_back_to_ai_art_after_choosing_a_cover(app_client):
    client, _db, _main, db_path, _, _, photo_a_id, _, token = app_client
    client.post("/api/songs/variants/100/cover-photo", json={"photo_id": photo_a_id})
    assert client.get(f"/api/songs/variants/{token}/public").json()["image_url"] != "http://cover.png"

    client.post("/api/songs/variants/100/cover-photo", json={"photo_id": None})
    resp = client.get(f"/api/songs/variants/{token}/public")
    assert resp.json()["image_url"] == "http://cover.png"
