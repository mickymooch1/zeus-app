"""Static mounts must serve .webp as image/webp (2026-09-30).

Found right after the memorial "Heavenly" backgrounds shipped: production
(Python 3.12) served them as application/octet-stream, because `.webp` is only
in mimetypes' non-strict table there and Starlette's StaticFiles/FileResponse
guess with strict=True. Newer Pythons know the type, so this test removes it
first to reproduce the 3.12 behaviour on any interpreter.
"""
import mimetypes
import os
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))
os.environ.setdefault("ANTHROPIC_API_KEY", "test-key")
os.environ.setdefault("APIFRAME_API_KEY", "test-key")
os.environ.setdefault("SONG_STORAGE_PATH", "/tmp/test_songs")
os.environ.setdefault("SONG_PUBLIC_BASE_URL", "https://example.com/files/songs")
os.environ.setdefault("SONG_WEBHOOK_URL", "https://zeusaidesign.com/webhooks/apiframe")
os.environ.setdefault("JWT_SECRET", "test-secret-for-webp-content-type-tests")


def _forget_webp(monkeypatch):
    """Put mimetypes in the state Python 3.12 has: no strict entry for .webp."""
    mimetypes.init()
    db = mimetypes._db
    strict = dict(db.types_map[True])
    strict.pop(".webp", None)
    monkeypatch.setattr(db, "types_map", (db.types_map[False], strict))
    assert mimetypes.guess_type("bg.webp")[0] is None        # the production bug, reproduced


def test_register_static_mime_types_teaches_strict_guess_webp(monkeypatch):
    import main
    _forget_webp(monkeypatch)
    main._register_static_mime_types()
    assert mimetypes.guess_type("heavenly-portrait-CI1xqrgo.webp")[0] == "image/webp"


def test_static_mount_serves_webp_with_image_content_type(tmp_path, monkeypatch):
    import main
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    _forget_webp(monkeypatch)
    main._register_static_mime_types()
    (tmp_path / "bg.webp").write_bytes(b"RIFF\x00\x00\x00\x00WEBP")
    app = FastAPI()
    app.mount("/assets-beats", main._LongCacheStaticFiles(directory=str(tmp_path)), name="a")
    resp = TestClient(app).get("/assets-beats/bg.webp")
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "image/webp"
    assert "immutable" in resp.headers["cache-control"]          # existing caching behaviour kept
