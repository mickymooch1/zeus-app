import os
import pathlib
import sys
import tempfile
from unittest.mock import patch, MagicMock

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


def test_generate_with_persona_builds_correct_payload():
    import cometapi
    mock_resp = MagicMock()
    mock_resp.json.return_value = {"code": 1, "data": "task-id-abc123"}
    mock_resp.raise_for_status = MagicMock()
    with patch("cometapi.requests.post", return_value=mock_resp) as mock_post:
        task_id = cometapi.generate_with_persona(
            variant_id=7,
            lyrics="verse 1 lyrics",
            style_prompt="uk grime, 140bpm",
            persona_id="uuid-persona-xyz",
            webhook_url="https://zeusaidesign.com/webhooks/cometapi?variant_id=7",
            extra_suno_params=None,
        )
    assert task_id == "task-id-abc123"
    call_json = mock_post.call_args.kwargs["json"]
    assert call_json["persona_id"] == "uuid-persona-xyz"
    assert call_json["task"] == "artist_consistency"
    assert "verse 1 lyrics" in call_json["prompt"]
    assert call_json["notify_hook"] == "https://zeusaidesign.com/webhooks/cometapi?variant_id=7"


def test_generate_with_persona_no_api_key_raises():
    import cometapi
    original = cometapi.COMETAPI_API_KEY
    cometapi.COMETAPI_API_KEY = ""
    try:
        try:
            cometapi.generate_with_persona(7, "lyrics", "style", "pid", "http://hook")
            assert False, "Should have raised"
        except RuntimeError as e:
            assert "COMETAPI_API_KEY" in str(e)
    finally:
        cometapi.COMETAPI_API_KEY = original


def test_create_persona_returns_persona_id_from_string_data():
    import cometapi
    mock_resp = MagicMock()
    mock_resp.json.return_value = {"code": 1, "data": "persona-uuid-str"}
    mock_resp.raise_for_status = MagicMock()
    with patch("cometapi.requests.post", return_value=mock_resp):
        pid = cometapi.create_persona("https://example.com/song.mp3", "Test Song")
    assert pid == "persona-uuid-str"


def test_create_persona_handles_dict_data_shape():
    import cometapi
    mock_resp = MagicMock()
    mock_resp.json.return_value = {"code": 1, "data": {"persona_id": "persona-uuid-dict"}}
    mock_resp.raise_for_status = MagicMock()
    with patch("cometapi.requests.post", return_value=mock_resp):
        pid = cometapi.create_persona("https://example.com/song.mp3", "Test Song")
    assert pid == "persona-uuid-dict"
