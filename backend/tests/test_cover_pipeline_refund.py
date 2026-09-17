"""Cover pipeline: uses Apiframe's documented Suno Cover action, and refunds
the song credit on failure (2026-09-17).

Apiframe's own docs (apiframe.ai/docs/actions/suno/cover, verified live)
describe a single-call action:

    POST https://api.apiframe.ai/v2/music/suno/action
    {"parentJobId": <original suno job id>, "action": "cover",
     "index": <1 or 2>, "prompt": <lyrics>, "style": <style tags>,
     "webhookUrl": ..., "webhookEvents": [...]}

parentJobId is "ID of the completed suno job to act on" -- exactly what we
already store as song_variants.provider_job_id, with take_number matching
"index". This replaces the old approach (download the source mp3, POST it to
/v2/music/upload, then /v2/music/extend) which relied on an upload endpoint
that no longer exists (404, confirmed live 2026-09-16) -- there was never a
need to re-upload audio Apiframe already has a job id for.

Credit-refund-on-failure (added 2026-09-16, when the crash this replaced a
different failure) must keep working regardless of which Apiframe call is
being made.
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


def _mock_action_ok():
    resp = MagicMock()
    resp.status_code = 200
    resp.text = '{"jobId": "new-job-123"}'
    resp.raise_for_status.return_value = None
    return resp


def _mock_action_failed(status_code=404, body='{"message":"Route POST:/v2/music/suno/action not found"}'):
    resp = MagicMock()
    resp.status_code = status_code
    resp.text = body
    resp.raise_for_status.side_effect = requests.HTTPError(f"{status_code} Client Error")
    return resp


def test_calls_the_documented_cover_action_endpoint_with_no_source_download(temp_db):
    """No requests.get at all -- the whole point of switching to this action
    is that Apiframe already has the source job, so nothing needs uploading."""
    user, variant_id = _make_cover_variant(temp_db)

    with patch.object(_webhooks_mod, "DB_PATH", str(temp_db)), \
         patch.object(_webhooks_mod.requests, "get") as mock_get, \
         patch.object(_webhooks_mod.requests, "post", return_value=_mock_action_ok()) as mock_post:
        _webhooks_mod._cover_pipeline(
            variant_id, parent_job_id="orig-job-abc", track_index=2,
            style="acoustic folk", lyrics_text="[Verse 1]\nEdited lyrics",
        )

    mock_get.assert_not_called()
    mock_post.assert_called_once()
    call_url = mock_post.call_args[0][0] if mock_post.call_args[0] else mock_post.call_args.kwargs.get("url")
    assert call_url == "https://api.apiframe.ai/v2/music/suno/action"


def test_cover_action_payload_matches_the_documented_shape(temp_db):
    user, variant_id = _make_cover_variant(temp_db)

    with patch.object(_webhooks_mod, "DB_PATH", str(temp_db)), \
         patch.object(_webhooks_mod.requests, "post", return_value=_mock_action_ok()) as mock_post:
        _webhooks_mod._cover_pipeline(
            variant_id, parent_job_id="orig-job-abc", track_index=2,
            style="acoustic folk", lyrics_text="[Verse 1]\nEdited lyrics",
        )

    payload = mock_post.call_args.kwargs["json"]
    assert payload["parentJobId"] == "orig-job-abc"
    assert payload["action"] == "cover"
    assert payload["index"] == 2
    assert payload["prompt"] == "[Verse 1]\nEdited lyrics"
    assert payload["style"] == "acoustic folk"
    assert payload["webhookEvents"] == ["completed", "failed"]
    assert str(variant_id) in payload["webhookUrl"]


def test_webhook_url_reads_from_song_webhook_url_not_a_different_name(temp_db):
    """Found live 2026-09-17: webhooks.py's WEBHOOK_URL constant read from
    os.environ.get("WEBHOOK_URL", "") -- a variable that has never existed
    in Railway (only SONG_WEBHOOK_URL does, which songs.py correctly reads).
    Always resolved to "", so every cover request's webhookUrl was just
    "?variant_id=N" -- confirmed live, Apiframe rejected it: "Invalid URL...
    must use https". Pin the constant to the source of truth directly."""
    assert _webhooks_mod.WEBHOOK_URL == os.environ["SONG_WEBHOOK_URL"].strip().rstrip("/")
    assert _webhooks_mod.WEBHOOK_URL.startswith("https://")


def test_cover_action_sends_a_real_https_webhook_url(temp_db):
    user, variant_id = _make_cover_variant(temp_db)

    with patch.object(_webhooks_mod, "DB_PATH", str(temp_db)), \
         patch.object(_webhooks_mod.requests, "post", return_value=_mock_action_ok()) as mock_post:
        _webhooks_mod._cover_pipeline(
            variant_id, parent_job_id="orig-job-abc", track_index=1,
            style="pop", lyrics_text="[Verse 1]\nEdited lyrics",
        )

    payload = mock_post.call_args.kwargs["json"]
    assert payload["webhookUrl"].startswith("https://")
    assert payload["webhookUrl"] == f"{os.environ['SONG_WEBHOOK_URL'].strip().rstrip('/')}?variant_id={variant_id}"


def test_pipeline_failure_refunds_the_credit(temp_db):
    user, variant_id = _make_cover_variant(temp_db, balance_after_charge=4)

    with patch.object(_webhooks_mod, "DB_PATH", str(temp_db)), \
         patch.object(_webhooks_mod.requests, "post", return_value=_mock_action_failed()):
        _webhooks_mod._cover_pipeline(
            variant_id, parent_job_id="orig-job-abc", track_index=1,
            style="some style", lyrics_text="[Verse 1]\nEdited lyrics",
        )

    credits = db.get_song_credits(temp_db, user["id"])
    assert credits["balance"] == 5  # refunded back to the pre-charge amount


def test_pipeline_failure_still_marks_the_variant_failed(temp_db):
    user, variant_id = _make_cover_variant(temp_db, balance_after_charge=4)

    with patch.object(_webhooks_mod, "DB_PATH", str(temp_db)), \
         patch.object(_webhooks_mod.requests, "post", return_value=_mock_action_failed()):
        _webhooks_mod._cover_pipeline(
            variant_id, parent_job_id="orig-job-abc", track_index=1,
            style="some style", lyrics_text="[Verse 1]\nEdited lyrics",
        )

    variant = db.get_song_variant_by_id(temp_db, variant_id)
    assert variant["status"] == "failed"


def test_pipeline_success_does_not_refund(temp_db):
    """A successful submission must not also refund -- the customer is
    meant to be charged for a real attempt."""
    user, variant_id = _make_cover_variant(temp_db, balance_after_charge=4)

    with patch.object(_webhooks_mod, "DB_PATH", str(temp_db)), \
         patch.object(_webhooks_mod.requests, "post", return_value=_mock_action_ok()):
        _webhooks_mod._cover_pipeline(
            variant_id, parent_job_id="orig-job-abc", track_index=1,
            style="some style", lyrics_text="[Verse 1]\nEdited lyrics",
        )

    credits = db.get_song_credits(temp_db, user["id"])
    assert credits["balance"] == 4  # unchanged -- charge already happened at request time
