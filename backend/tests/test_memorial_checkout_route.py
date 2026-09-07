"""POST /api/memorials/checkout — creates a Stripe checkout session for a
memorial pack, mirroring the existing POST /api/songs/payg route.
"""
import importlib
import os
import pathlib
import sys
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))
os.environ.setdefault("ANTHROPIC_API_KEY", "test-key")
os.environ.setdefault("APIFRAME_API_KEY", "test-key")
os.environ.setdefault("SONG_STORAGE_PATH", "/tmp/test_songs")
os.environ.setdefault("SONG_PUBLIC_BASE_URL", "https://example.com/files/songs")
os.environ.setdefault("SONG_WEBHOOK_URL", "https://zeusaidesign.com/webhooks/apiframe")
os.environ.setdefault("JWT_SECRET", "test-secret-for-memorial-checkout-tests")


@pytest.fixture()
def app_client(tmp_path, monkeypatch):
    monkeypatch.setenv("ZEUS_DATA_DIR", str(tmp_path))
    import db as _db
    importlib.reload(_db)

    db_path = _db.get_db_path()
    user = _db.create_user(db_path, email="buyer@example.com", password_hash="x",
                            name="Buyer", tc_accepted_at="now")

    import main as _main
    importlib.reload(_main)
    import auth as _auth

    def _current_user():
        return {"id": user["id"], "email": user["email"]}

    _main.app.dependency_overrides[_auth.get_current_user] = _current_user
    try:
        with TestClient(_main.app) as client:
            yield client, _db, _main, db_path, user
    finally:
        _main.app.dependency_overrides.pop(_auth.get_current_user, None)


def test_memorial_checkout_requires_auth(app_client):
    client, _db, _main, db_path, user = app_client
    # Remove the auth override for this test only, so the real dependency
    # (which 401s with no Authorization header/token) is exercised.
    import auth as _auth
    _main.app.dependency_overrides.pop(_auth.get_current_user, None)
    try:
        resp = client.post("/api/memorials/checkout")
        assert resp.status_code in (401, 403)
    finally:
        _main.app.dependency_overrides[_auth.get_current_user] = lambda: {
            "id": user["id"], "email": user["email"]
        }


def test_memorial_checkout_returns_url(app_client):
    client, _db, _main, db_path, user = app_client
    _main.billing._STRIPE_SECRET_KEY = "sk_test_dummy"  # billing.stripe_enabled() gate
    with patch.object(_main.billing, "create_memorial_checkout_session",
                       return_value="https://checkout.stripe.com/xyz"):
        resp = client.post("/api/memorials/checkout")
    assert resp.status_code == 200, resp.text
    assert resp.json()["url"] == "https://checkout.stripe.com/xyz"
