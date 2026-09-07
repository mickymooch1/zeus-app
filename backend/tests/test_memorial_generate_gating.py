import importlib, os, pathlib, sys
from unittest.mock import patch
import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))
os.environ.setdefault("ANTHROPIC_API_KEY", "test-key-for-tests")


@pytest.fixture()
def app_client(tmp_path, monkeypatch):
    monkeypatch.setenv("ZEUS_DATA_DIR", str(tmp_path))
    import db as _db
    importlib.reload(_db)
    db_path = _db.get_db_path()
    user = _db.create_user(db_path, email="buyer@example.com", password_hash="x", name="Buyer", tc_accepted_at="now")
    _db.update_user(db_path, user["id"], email_verified=1)
    import main as _main
    importlib.reload(_main)
    client = TestClient(_main.app)
    token = _main.auth.create_token(user["id"], user["email"], is_admin=False)
    return client, _db, _main, db_path, user, token


def _headers(token):
    return {"Authorization": f"Bearer {token}"}


# Requests use custom_lyrics + an explicit song_title so the handler never calls
# the real Anthropic API (custom_lyrics skips generate_lyrics entirely, and an
# explicit song_title skips the one Claude call inside store_custom_lyrics too —
# see lyrics.store_custom_lyrics). That lets generate_multiple_variants run for
# REAL below (not mocked out) so its actual per-genre credit deduction fires —
# only the outbound Apiframe HTTP call (songs._submit_to_apiframe) is stubbed.
# This is deliberately more end-to-end than the brief's sketch: a fully-mocked
# generate_multiple_variants never deducts anything, so a "net zero" assertion
# against it would be vacuous.
_BODY = {
    "genres": ["pop"],
    "brief": "a memorial song",
    "custom_lyrics": "La la la, this is a test verse.",
    "song_title": "Test Song",
}


def test_memorial_generate_without_credits_returns_402(app_client):
    client, _db, _main, db_path, user, token = app_client
    resp = client.post("/api/songs/generate", json={**_BODY, "is_memorial": True},
                        headers=_headers(token))
    assert resp.status_code == 402
    assert _db.get_user_by_id(db_path, user["id"])["memorial_credits_available"] == 0


def test_memorial_generate_consumes_memorial_credit_not_song_credit(app_client):
    client, _db, _main, db_path, user, token = app_client
    _db.increment_memorial_credits(db_path, user["id"], 1)
    _db.upsert_song_credits(db_path, user["id"], balance=0, monthly_allowance=0)

    with patch("songs._submit_to_apiframe", return_value="fake-job-id"):
        resp = client.post("/api/songs/generate", json={**_BODY, "is_memorial": True},
                            headers=_headers(token))

    assert resp.status_code == 200, resp.text
    assert _db.get_user_by_id(db_path, user["id"])["memorial_credits_available"] == 0
    assert _db.get_song_credits(db_path, user["id"])["balance"] == 0


def test_memorial_generate_failure_rolls_back_memorial_credit(app_client):
    """An invalid genre makes the real generate_multiple_variants raise ValueError
    ("No valid genres provided") before any credit is actually deducted inside it
    — the temp song credit granted by the memorial gate must be rolled back by the
    except block in songs_generate, not left dangling."""
    client, _db, _main, db_path, user, token = app_client
    _db.increment_memorial_credits(db_path, user["id"], 1)
    _db.upsert_song_credits(db_path, user["id"], balance=0, monthly_allowance=0)

    body = {**_BODY, "genres": ["not_a_real_genre"], "is_memorial": True}
    resp = client.post("/api/songs/generate", json=body, headers=_headers(token))

    assert resp.status_code == 400, resp.text
    assert _db.get_user_by_id(db_path, user["id"])["memorial_credits_available"] == 1
    assert _db.get_song_credits(db_path, user["id"])["balance"] == 0


def test_memorial_generate_lyrics_failure_rolls_back_memorial_credit(app_client):
    """The memorial grant happens BEFORE the lyrics call, not just before
    generate_multiple_variants — a lyrics-generation failure (e.g. the Claude
    API erroring) is a real, likely failure mode and must roll back the temp
    song credit / memorial debit exactly like a generate_multiple_variants
    failure does. Uses generate_lyrics (not custom_lyrics) so this exercises
    that earlier try/except block specifically."""
    client, _db, _main, db_path, user, token = app_client
    _db.increment_memorial_credits(db_path, user["id"], 1)
    _db.upsert_song_credits(db_path, user["id"], balance=0, monthly_allowance=0)

    body = {"genres": ["pop"], "brief": "a memorial song", "is_memorial": True}
    with patch("lyrics.generate_lyrics", side_effect=RuntimeError("claude boom")):
        resp = client.post("/api/songs/generate", json=body, headers=_headers(token))

    assert resp.status_code == 500, resp.text
    assert _db.get_user_by_id(db_path, user["id"])["memorial_credits_available"] == 1
    assert _db.get_song_credits(db_path, user["id"])["balance"] == 0


def test_non_memorial_generate_unaffected(app_client):
    client, _db, _main, db_path, user, token = app_client
    _db.upsert_song_credits(db_path, user["id"], balance=1, monthly_allowance=0)

    with patch("songs._submit_to_apiframe", return_value="fake-job-id"):
        resp = client.post("/api/songs/generate", json=_BODY, headers=_headers(token))

    assert resp.status_code == 200, resp.text
    assert _db.get_user_by_id(db_path, user["id"])["memorial_credits_available"] == 0
    assert _db.get_song_credits(db_path, user["id"])["balance"] == 0
