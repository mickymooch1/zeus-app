"""Cover pipeline must refund the song credit on failure (2026-09-17).

Live production testing (post the lyrics.brief fix, see test_cover_song.py)
found the Apiframe upload step Cover relies on is dead:

    Cover upload: status=404 body='{"message":"Route POST:/v2/music/upload
    not found", ...}'

Before the brief fix, that whole request rolled back atomically so nobody
was charged. Now that the DB writes commit successfully before the
background pipeline runs, a pipeline failure left the customer's credit
spent with nothing to show for it -- confirmed live, balance dropped 124
-> 123 on a single failed attempt.

This is a safety net independent of whatever happens with the Apiframe
endpoint: any failure in _cover_pipeline must refund the 1 credit it took,
using the same _refund_song_credit() helper every other generation pipeline
in this file already relies on for the same purpose.
"""
import os
import pathlib
import sys
from unittest.mock import MagicMock, patch

import pytest
import requests

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))
os.environ.setdefault("ANTHROPIC_API_KEY", "test-key")
os.environ.setdefault("APIFRAME_API_KEY", "test-key")
os.environ.setdefault("SONG_STORAGE_PATH", "/tmp/test_songs")
os.environ.setdefault("SONG_PUBLIC_BASE_URL", "https://example.com/files/songs")
os.environ.setdefault("SONG_WEBHOOK_URL", "https://zeusaidesign.com/webhooks/apiframe")
os.environ.setdefault("JWT_SECRET", "test-secret-for-cover-refund-tests")

import db
import webhooks as _webhooks_mod


@pytest.fixture
def temp_db(tmp_path):
    path = tmp_path / "test.db"
    db.init_user_tables(path)
    return path


def _make_cover_variant(temp_db, balance_after_charge=4):
    """balance_after_charge mirrors real sequencing: cover_song() already
    deducted 1 credit synchronously before the background pipeline (which
    is all this test drives) ever runs."""
    user = db.create_user(temp_db, email="singer@example.com", password_hash="x", name="Singer", tc_accepted_at="now")
    db.upsert_song_credits(temp_db, user["id"], balance=balance_after_charge, monthly_allowance=5)
    conn = db._conn(temp_db)
    try:
        lyric_cur = conn.execute(
            "INSERT INTO lyrics (user_id, brief, lyrics_text) VALUES (?, ?, ?)",
            (user["id"], "Cover of song #1", "[Verse 1]\nEdited lyrics"),
        )
        variant_cur = conn.execute(
            """INSERT INTO song_variants (lyric_id, user_id, style_prompt, genre_tag, status)
               VALUES (?, ?, ?, ?, 'pending')""",
            (lyric_cur.lastrowid, user["id"], "some style", "pop"),
        )
        conn.commit()
        return user, variant_cur.lastrowid
    finally:
        conn.close()


def _mock_download_ok():
    resp = MagicMock()
    resp.raise_for_status.return_value = None
    resp.content = b"fake mp3 bytes"
    return resp


def _mock_upload_404():
    resp = MagicMock()
    resp.status_code = 404
    resp.text = '{"message":"Route POST:/v2/music/upload not found"}'
    resp.raise_for_status.side_effect = requests.HTTPError("404 Client Error: Not Found")
    return resp


def test_pipeline_failure_refunds_the_credit(temp_db):
    user, variant_id = _make_cover_variant(temp_db, balance_after_charge=4)

    with patch.object(_webhooks_mod, "DB_PATH", str(temp_db)), \
         patch.object(_webhooks_mod.requests, "get", return_value=_mock_download_ok()), \
         patch.object(_webhooks_mod.requests, "post", return_value=_mock_upload_404()):
        _webhooks_mod._cover_pipeline(variant_id, "https://example.com/source.mp3", "[Verse 1]\nEdited lyrics")

    credits = db.get_song_credits(temp_db, user["id"])
    assert credits["balance"] == 5  # refunded back to the pre-charge amount


def test_pipeline_failure_still_marks_the_variant_failed(temp_db):
    user, variant_id = _make_cover_variant(temp_db, balance_after_charge=4)

    with patch.object(_webhooks_mod, "DB_PATH", str(temp_db)), \
         patch.object(_webhooks_mod.requests, "get", return_value=_mock_download_ok()), \
         patch.object(_webhooks_mod.requests, "post", return_value=_mock_upload_404()):
        _webhooks_mod._cover_pipeline(variant_id, "https://example.com/source.mp3", "[Verse 1]\nEdited lyrics")

    variant = db.get_song_variant_by_id(temp_db, variant_id)
    assert variant["status"] == "failed"


def test_pipeline_success_does_not_refund(temp_db):
    """A successful submission (upload + extend both accepted) must not
    also refund -- the customer is meant to be charged for a real attempt."""
    user, variant_id = _make_cover_variant(temp_db, balance_after_charge=4)
    upload_ok = MagicMock()
    upload_ok.raise_for_status.return_value = None
    upload_ok.json.return_value = {"task_id": "task_123"}
    extend_ok = MagicMock()
    extend_ok.raise_for_status.return_value = None
    extend_ok.text = "{}"
    extend_ok.status_code = 200

    with patch.object(_webhooks_mod, "DB_PATH", str(temp_db)), \
         patch.object(_webhooks_mod.requests, "get", return_value=_mock_download_ok()), \
         patch.object(_webhooks_mod.requests, "post", side_effect=[upload_ok, extend_ok]):
        _webhooks_mod._cover_pipeline(variant_id, "https://example.com/source.mp3", "[Verse 1]\nEdited lyrics")

    credits = db.get_song_credits(temp_db, user["id"])
    assert credits["balance"] == 4  # unchanged -- charge already happened at request time
