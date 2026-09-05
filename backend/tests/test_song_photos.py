"""Song photos: up to 5 photos per song, shown on the public share page.

Privacy model (memorial-page use case — a QR may be printed/engraved):
  - Photos are ONLY ever reachable via an unguessable share_token, generated
    lazily on first photo upload. The plain numeric /public route (used by
    QR codes generated before this feature existed) NEVER returns photos,
    regardless of whether any exist for that variant — closing the
    sequential-ID enumeration risk a stranger could otherwise use to find
    someone else's memorial photos.
  - HEIC uploads (the default on iPhone, the likely majority of uploaders)
    are converted to JPEG at upload time — HEIC doesn't render in an <img>
    tag on Chrome/Firefox/Android, only Safari decodes it natively.
  - Every limit (size, format, count) is enforced server-side, not just in
    the UI — a raw API call must be stopped exactly like the browser is.
"""
import importlib
import io
import os
import pathlib
import sys

import pytest
from fastapi.testclient import TestClient
from PIL import Image

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))
os.environ.setdefault("ANTHROPIC_API_KEY", "test-key")
os.environ.setdefault("APIFRAME_API_KEY", "test-key")
os.environ.setdefault("SONG_STORAGE_PATH", "/tmp/test_songs")
os.environ.setdefault("SONG_PUBLIC_BASE_URL", "https://example.com/files/songs")
os.environ.setdefault("SONG_WEBHOOK_URL", "https://zeusaidesign.com/webhooks/apiframe")
os.environ.setdefault("JWT_SECRET", "test-secret-for-song-photos-tests")


def _jpeg_bytes(size=(200, 200), color=(255, 0, 0)) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", size, color).save(buf, format="JPEG")
    return buf.getvalue()


def _heic_bytes(size=(200, 200), color=(0, 255, 0)) -> bytes:
    import pillow_heif
    pillow_heif.register_heif_opener()
    buf = io.BytesIO()
    Image.new("RGB", size, color).save(buf, format="HEIF")
    return buf.getvalue()


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
               VALUES (200, 1, ?, 'pop', 'a pop track', 1, 'complete',
                       'http://a.mp3', 'http://i.png', 180, datetime('now'))""",
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
            yield client, _db, db_path, owner, other, photo_storage
    finally:
        _main.app.dependency_overrides.pop(_auth.get_current_user, None)


# ── schema ────────────────────────────────────────────────────────────────

def test_photos_table_and_share_token_column_exist(app_client):
    _, _db, db_path, *_ = app_client
    conn = _db._conn(db_path)
    try:
        tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        assert "song_variant_photos" in tables
        cols = [r[1] for r in conn.execute("PRAGMA table_info(song_variants)")]
        assert "share_token" in cols
    finally:
        conn.close()


# ── upload happy path ────────────────────────────────────────────────────

def test_upload_jpeg_succeeds_and_writes_a_real_file(app_client):
    client, _db, db_path, _, _, photo_storage = app_client
    resp = client.post(
        "/api/songs/variants/200/photos",
        files={"file": ("photo.jpg", _jpeg_bytes(), "image/jpeg")},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["photo_id"]
    photos = _db.get_song_variant_photos(db_path, 200)
    assert len(photos) == 1
    stored = photo_storage / photos[0]["filename"]
    assert stored.exists()
    with Image.open(stored) as img:
        assert img.format == "JPEG"


def test_heic_upload_is_converted_to_a_real_displayable_jpeg(app_client):
    """The essential requirement: iPhone HEIC uploads must display in every
    browser, not just Safari — proven by actually opening the stored file
    and checking its real format, not trusting the extension."""
    client, _db, db_path, _, _, photo_storage = app_client
    resp = client.post(
        "/api/songs/variants/200/photos",
        files={"file": ("photo.heic", _heic_bytes(), "image/heic")},
    )
    assert resp.status_code == 200, resp.text
    photos = _db.get_song_variant_photos(db_path, 200)
    stored = photo_storage / photos[0]["filename"]
    assert stored.suffix == ".jpg"
    with Image.open(stored) as img:
        assert img.format == "JPEG"
        assert img.size == (200, 200)


def test_first_upload_generates_a_share_token(app_client):
    client, _db, db_path, *_ = app_client
    before = _db.get_song_variant_by_id(db_path, 200)
    assert not before.get("share_token")

    resp = client.post("/api/songs/variants/200/photos", files={"file": ("p.jpg", _jpeg_bytes(), "image/jpeg")})
    token = resp.json()["share_token"]
    assert token and len(token) > 20

    after = _db.get_song_variant_by_id(db_path, 200)
    assert after["share_token"] == token


def test_second_upload_does_not_regenerate_the_token(app_client):
    client, _db, db_path, *_ = app_client
    t1 = client.post("/api/songs/variants/200/photos", files={"file": ("p.jpg", _jpeg_bytes(), "image/jpeg")}).json()["share_token"]
    t2 = client.post("/api/songs/variants/200/photos", files={"file": ("p2.jpg", _jpeg_bytes(), "image/jpeg")}).json()["share_token"]
    assert t1 == t2


# ── server-side enforcement (never trust the client alone) ──────────────

def test_oversized_photo_is_rejected_with_413(app_client):
    """The size check must reject before any decode attempt — an oversized
    file should never even reach the conversion step."""
    client, _db, db_path, *_ = app_client
    oversized = _jpeg_bytes() + b"\x00" * (6 * 1024 * 1024)
    resp = client.post("/api/songs/variants/200/photos", files={"file": ("big.jpg", oversized, "image/jpeg")})
    assert resp.status_code == 413
    assert _db.count_song_variant_photos(db_path, 200) == 0


def test_wrong_format_is_rejected_with_400(app_client):
    client, _db, db_path, *_ = app_client
    resp = client.post(
        "/api/songs/variants/200/photos",
        files={"file": ("notes.txt", b"just some text", "text/plain")},
    )
    assert resp.status_code == 400
    assert _db.count_song_variant_photos(db_path, 200) == 0


def test_sixth_photo_is_rejected_server_side(app_client):
    client, _db, db_path, *_ = app_client
    for i in range(5):
        r = client.post("/api/songs/variants/200/photos", files={"file": (f"p{i}.jpg", _jpeg_bytes(), "image/jpeg")})
        assert r.status_code == 200, r.text
    sixth = client.post("/api/songs/variants/200/photos", files={"file": ("p6.jpg", _jpeg_bytes(), "image/jpeg")})
    assert sixth.status_code == 400
    assert "5" in sixth.json()["detail"]
    assert _db.count_song_variant_photos(db_path, 200) == 5


def test_upload_404s_for_a_variant_the_caller_does_not_own(app_client):
    client, _db, db_path, owner, other, _ = app_client
    conn = _db._conn(db_path)
    try:
        conn.execute(
            "INSERT INTO lyrics (id, user_id, title, brief, lyrics_text, created_at) VALUES (2, ?, 'Other', 'b', 'l', datetime('now'))",
            (other["id"],),
        )
        conn.execute(
            """INSERT INTO song_variants (id, lyric_id, user_id, genre_tag, style_prompt, take_number, status, mp3_url, duration_seconds, created_at)
               VALUES (201, 2, ?, 'pop', 'x', 1, 'complete', 'http://a.mp3', 100, datetime('now'))""",
            (other["id"],),
        )
        conn.commit()
    finally:
        conn.close()
    resp = client.post("/api/songs/variants/201/photos", files={"file": ("p.jpg", _jpeg_bytes(), "image/jpeg")})
    assert resp.status_code == 404


# ── public endpoint: numeric route never exposes photos ─────────────────

def test_numeric_public_route_never_returns_photos(app_client):
    client, _db, db_path, *_ = app_client
    client.post("/api/songs/variants/200/photos", files={"file": ("p.jpg", _jpeg_bytes(), "image/jpeg")})

    resp = client.get("/api/songs/variants/200/public")
    assert resp.status_code == 200
    assert resp.json()["photos"] == []


def test_share_token_route_returns_the_photos(app_client):
    client, _db, db_path, *_ = app_client
    token = client.post("/api/songs/variants/200/photos", files={"file": ("p.jpg", _jpeg_bytes(), "image/jpeg")}).json()["share_token"]

    resp = client.get(f"/api/songs/variants/{token}/public")
    assert resp.status_code == 200
    body = resp.json()
    assert body["variant_id"] == 200
    assert len(body["photos"]) == 1
    assert body["photos"][0]["url"]


def test_unknown_share_token_404s(app_client):
    client, *_ = app_client
    resp = client.get("/api/songs/variants/not-a-real-token-at-all/public")
    assert resp.status_code == 404


# ── authenticated listing (for the owner's Add Photos panel) ─────────────

def test_owner_can_list_photos_for_their_own_song(app_client):
    client, *_ = app_client
    client.post("/api/songs/variants/200/photos", files={"file": ("p.jpg", _jpeg_bytes(), "image/jpeg")})
    resp = client.get("/api/songs/variants/200/photos")
    assert resp.status_code == 200
    photos = resp.json()["photos"]
    assert len(photos) == 1
    assert photos[0]["url"]


def test_listing_photos_404s_for_a_variant_the_caller_does_not_own(app_client):
    client, _db, db_path, owner, other, _ = app_client
    conn = _db._conn(db_path)
    try:
        conn.execute(
            "INSERT INTO lyrics (id, user_id, title, brief, lyrics_text, created_at) VALUES (4, ?, 'Other3', 'b', 'l', datetime('now'))",
            (other["id"],),
        )
        conn.execute(
            """INSERT INTO song_variants (id, lyric_id, user_id, genre_tag, style_prompt, take_number, status, mp3_url, duration_seconds, created_at)
               VALUES (203, 4, ?, 'pop', 'x', 1, 'complete', 'http://a.mp3', 100, datetime('now'))""",
            (other["id"],),
        )
        conn.commit()
    finally:
        conn.close()
    resp = client.get("/api/songs/variants/203/photos")
    assert resp.status_code == 404


# ── deletion ─────────────────────────────────────────────────────────────

def test_delete_photo_removes_row_and_file(app_client):
    client, _db, db_path, _, _, photo_storage = app_client
    photo_id = client.post("/api/songs/variants/200/photos", files={"file": ("p.jpg", _jpeg_bytes(), "image/jpeg")}).json()["photo_id"]
    filename = _db.get_song_variant_photos(db_path, 200)[0]["filename"]
    assert (photo_storage / filename).exists()

    resp = client.delete(f"/api/songs/variants/200/photos/{photo_id}")
    assert resp.status_code == 200
    assert _db.count_song_variant_photos(db_path, 200) == 0
    assert not (photo_storage / filename).exists()


def test_delete_photo_404s_for_a_photo_on_someone_elses_song(app_client):
    client, _db, db_path, owner, other, _ = app_client
    conn = _db._conn(db_path)
    try:
        conn.execute(
            "INSERT INTO lyrics (id, user_id, title, brief, lyrics_text, created_at) VALUES (3, ?, 'Other2', 'b', 'l', datetime('now'))",
            (other["id"],),
        )
        conn.execute(
            """INSERT INTO song_variants (id, lyric_id, user_id, genre_tag, style_prompt, take_number, status, mp3_url, duration_seconds, created_at)
               VALUES (202, 3, ?, 'pop', 'x', 1, 'complete', 'http://a.mp3', 100, datetime('now'))""",
            (other["id"],),
        )
        conn.commit()
    finally:
        conn.close()
    other_photo_id = _db.add_song_variant_photo(db_path, 202, "someone-elses-photo.jpg")

    resp = client.delete(f"/api/songs/variants/200/photos/{other_photo_id}")
    assert resp.status_code == 404
    assert _db.get_song_variant_photo_by_id(db_path, other_photo_id) is not None


def test_deleting_the_whole_variant_deletes_its_photo_rows_too(app_client):
    client, _db, db_path, *_ = app_client
    client.post("/api/songs/variants/200/photos", files={"file": ("p.jpg", _jpeg_bytes(), "image/jpeg")})
    assert _db.count_song_variant_photos(db_path, 200) == 1

    resp = client.delete("/api/songs/variants/200")
    assert resp.status_code == 200
    assert _db.count_song_variant_photos(db_path, 200) == 0


# ── share_token surfaced on the owner's own list endpoints ───────────────

def test_library_endpoint_surfaces_share_token(app_client):
    client, *_ = app_client
    token = client.post("/api/songs/variants/200/photos", files={"file": ("p.jpg", _jpeg_bytes(), "image/jpeg")}).json()["share_token"]
    resp = client.get("/api/library")
    variants = {v["variant_id"]: v for v in resp.json()["variants"]}
    assert variants[200]["share_token"] == token


def test_lyric_variants_endpoint_surfaces_share_token_as_null_when_no_photos(app_client):
    client, *_ = app_client
    resp = client.get("/api/lyrics/1/variants")
    variants = {v["variant_id"]: v for v in resp.json()["variants"]}
    assert variants[200]["share_token"] is None
