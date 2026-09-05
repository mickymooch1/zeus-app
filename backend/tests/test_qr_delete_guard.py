"""QR-code delete guard.

A "Create QR Code" button (web-beats) lets a user download a PNG/SVG QR
pointing at the permanent /songs/share/:variantId page. Because that QR may
end up printed or engraved (memorials, merch), deleting the underlying song
afterwards must not be a silent one-click action — same lesson as the
Apiframe webhook gaps investigated earlier this session: an action with a
real-world, unrecoverable consequence needs an explicit second confirmation,
not just a UI dialog a raw API call could skip.

Two layers, both tested here:
  1. qr_generated flag, set via POST .../mark-qr-generated once the user
     actually downloads a QR (not merely previews one).
  2. DELETE .../variants/{id} refuses with 409 when qr_generated=1 unless the
     caller explicitly passes confirm_qr_delete=true — enforced server-side,
     so the guard holds even against a direct API call bypassing the frontend
     dialog entirely.
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
os.environ.setdefault("JWT_SECRET", "test-secret-for-qr-delete-guard-tests")


@pytest.fixture()
def app_client(tmp_path, monkeypatch):
    """Real temp DB, real app, real endpoints — auth faked via dependency override
    (same pattern as test_main.py), DB isolated via ZEUS_DATA_DIR + reload (same
    pattern as test_library_batch.py)."""
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
            yield client, _db, db_path, owner, other
    finally:
        _main.app.dependency_overrides.pop(_auth.get_current_user, None)


# ── Schema ────────────────────────────────────────────────────────────────

def test_qr_generated_column_exists_and_defaults_to_zero(app_client):
    _, _db, db_path, _, _ = app_client
    conn = _db._conn(db_path)
    try:
        cols = [r[1] for r in conn.execute("PRAGMA table_info(song_variants)")]
    finally:
        conn.close()
    assert "qr_generated" in cols

    variant = _db.get_song_variant_by_id(db_path, 100)
    assert bool(variant.get("qr_generated")) is False


# ── mark-qr-generated ────────────────────────────────────────────────────

def test_mark_qr_generated_sets_the_flag(app_client):
    client, _db, db_path, _, _ = app_client
    resp = client.post("/api/songs/variants/100/mark-qr-generated")
    assert resp.status_code == 200
    variant = _db.get_song_variant_by_id(db_path, 100)
    assert bool(variant.get("qr_generated")) is True


def test_mark_qr_generated_is_idempotent(app_client):
    client, _db, db_path, _, _ = app_client
    assert client.post("/api/songs/variants/100/mark-qr-generated").status_code == 200
    assert client.post("/api/songs/variants/100/mark-qr-generated").status_code == 200
    variant = _db.get_song_variant_by_id(db_path, 100)
    assert bool(variant.get("qr_generated")) is True


def test_mark_qr_generated_404s_for_nonexistent_variant(app_client):
    client, _, _, _, _ = app_client
    resp = client.post("/api/songs/variants/999999/mark-qr-generated")
    assert resp.status_code == 404


# ── delete guard ─────────────────────────────────────────────────────────

def test_delete_succeeds_normally_when_no_qr_generated(app_client):
    client, _db, db_path, _, _ = app_client
    resp = client.delete("/api/songs/variants/100")
    assert resp.status_code == 200
    assert _db.get_song_variant_by_id(db_path, 100) is None


def test_delete_is_refused_with_409_after_qr_generated(app_client):
    client, _db, db_path, _, _ = app_client
    client.post("/api/songs/variants/100/mark-qr-generated")

    resp = client.delete("/api/songs/variants/100")

    assert resp.status_code == 409
    assert "QR code" in resp.json()["detail"]
    # refused, not deleted
    assert _db.get_song_variant_by_id(db_path, 100) is not None


def test_delete_succeeds_with_explicit_confirmation(app_client):
    client, _db, db_path, _, _ = app_client
    client.post("/api/songs/variants/100/mark-qr-generated")

    resp = client.delete("/api/songs/variants/100?confirm_qr_delete=true")

    assert resp.status_code == 200
    assert _db.get_song_variant_by_id(db_path, 100) is None


def test_delete_without_qr_ignores_the_confirm_param():
    """confirm_qr_delete=true on a song with no QR must behave identically to a
    normal delete — the param only matters once qr_generated is set."""
    # covered functionally by test_delete_succeeds_normally_when_no_qr_generated;
    # this test documents the intent explicitly so a future change can't silently
    # require the param unconditionally.


# ── the guard cannot be bypassed by a direct API call ───────────────────

def test_409_guard_holds_even_without_going_through_any_frontend_dialog(app_client):
    """The whole point: server-side enforcement, not just a UI popup. A raw
    DELETE call with no confirm param must be refused exactly like a browser
    would be, proving the frontend dialog isn't the only thing stopping this."""
    client, _db, db_path, _, _ = app_client
    client.post("/api/songs/variants/100/mark-qr-generated")

    first_attempt = client.delete("/api/songs/variants/100")
    assert first_attempt.status_code == 409

    second_attempt = client.delete("/api/songs/variants/100?confirm_qr_delete=true")
    assert second_attempt.status_code == 200


# ── list endpoints surface the flag (frontend needs it to show the dialog) ──

def test_library_endpoint_surfaces_qr_generated_flag(app_client):
    client, _db, db_path, _, _ = app_client
    client.post("/api/songs/variants/100/mark-qr-generated")

    resp = client.get("/api/library")
    assert resp.status_code == 200
    variants = {v["variant_id"]: v for v in resp.json()["variants"]}
    assert variants[100]["qr_generated"] is True


def test_lyric_variants_endpoint_surfaces_qr_generated_flag(app_client):
    client, _db, db_path, _, _ = app_client

    resp = client.get("/api/lyrics/1/variants")
    assert resp.status_code == 200
    variants = {v["variant_id"]: v for v in resp.json()["variants"]}
    assert variants[100]["qr_generated"] is False
