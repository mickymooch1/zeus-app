import os
import pathlib
import sys
import tempfile

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))

os.environ.setdefault("ANTHROPIC_API_KEY", "test-key-for-tests")
os.environ.setdefault("APIFRAME_API_KEY", "test-apiframe-key")
os.environ.setdefault("SONG_WEBHOOK_URL", "https://zeusaidesign.com/webhooks/apiframe")
os.environ.setdefault("SONG_STORAGE_PATH", "/tmp/test_your_sound_storage")
os.environ.setdefault("SONG_PUBLIC_BASE_URL", "https://example.com/songs")
os.environ.setdefault("COMETAPI_API_KEY", "test-comet-key")
os.environ.setdefault("COMETAPI_WEBHOOK_URL", "https://zeusaidesign.com/webhooks/cometapi")


def _make_db():
    import db
    tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    db_path = pathlib.Path(tmp.name)
    tmp.close()
    db.init_user_tables(db_path)
    return db_path


def _make_user(db_path):
    import db, uuid
    from datetime import datetime, timezone
    uid = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()
    import sqlite3
    conn = sqlite3.connect(str(db_path))
    conn.execute(
        "INSERT INTO users (id, email, password_hash, subscription_status, subscription_plan, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (uid, f"{uid}@test.com", "hash", "active", "music_starter", now, now),
    )
    conn.commit()
    conn.close()
    return uid


def test_set_and_clear_sound_persona():
    import db
    db_path = _make_db()
    uid = _make_user(db_path)
    db.set_sound_persona(db_path, uid, persona_id="uuid-test-123", variant_id=42, title="Midnight Drift")
    user = db.get_user_by_id(db_path, uid)
    assert user["sound_persona_id"] == "uuid-test-123"
    assert user["sound_persona_variant_id"] == 42
    assert user["sound_persona_title"] == "Midnight Drift"
    db.clear_sound_persona(db_path, uid)
    user = db.get_user_by_id(db_path, uid)
    assert user["sound_persona_id"] is None
    assert user["sound_persona_variant_id"] is None
    assert user["sound_persona_title"] is None
