"""Step 3 of the alerting build: page when an external provider (Apiframe, fal.ai,
ElevenLabs) returns an auth/quota-class error, so a dead API key or an exhausted
balance gets caught immediately instead of silently degrading every request that
hits it. Also confirms the duplicate GoAPI-fallback Telegram sender (its own
TELEGRAM_CHANNEL_ID POST) is gone, replaced by the shared, deduped alerts.py path.
"""
import os
import pathlib
import sys
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))
os.environ.setdefault("ANTHROPIC_API_KEY", "test-key")
os.environ.setdefault("APIFRAME_API_KEY", "test-key")
os.environ.setdefault("SONG_STORAGE_PATH", "/tmp/test_songs")
os.environ.setdefault("SONG_PUBLIC_BASE_URL", "https://example.com/files/songs")
os.environ.setdefault("SONG_WEBHOOK_URL", "https://zeusaidesign.com/webhooks/apiframe")
os.environ.setdefault("JWT_SECRET", "test-secret")

import alerts  # noqa: E402


@pytest.fixture()
def fresh_db(tmp_path, monkeypatch):
    monkeypatch.setenv("ZEUS_DATA_DIR", str(tmp_path))
    import importlib
    import db as _db
    importlib.reload(_db)
    return _db


def _make_lyric(fresh_db, db_path, credits=5):
    u = fresh_db.create_user(db_path, email="svc-err@test.co", password_hash="x", name="U", tc_accepted_at="n")
    fresh_db.ensure_free_song_credits(db_path, u["id"], balance=credits, monthly_allowance=0)
    conn = fresh_db._conn(db_path)
    try:
        conn.execute("INSERT INTO lyrics (id,user_id,title,brief,lyrics_text,created_at) "
                     "VALUES (1,?,'T','b','la',datetime('now'))", (u["id"],))
        conn.commit()
    finally:
        conn.close()
    return u


def _reset():
    alerts._ALERT_CATEGORY_STATE.clear()
    alerts._sent_alerts.clear()


# ── alerts.alert_service_error ────────────────────────────────────────────────

def test_alert_service_error_dedupes_per_service_and_status(monkeypatch):
    _reset()
    sent = []
    monkeypatch.setattr(alerts, "_send_telegram", lambda msg: sent.append(msg) or True)

    alerts.alert_service_error("apiframe", 401, "bad key #1")
    alerts.alert_service_error("apiframe", 401, "bad key #2")  # same service+status, suppressed
    alerts.alert_service_error("apiframe", 429, "rate limited")  # different status, own alert
    alerts.alert_service_error("elevenlabs", 401, "different service, own alert")

    assert len(sent) == 3, f"expected 3 distinct (service,status) alerts, got {len(sent)}: {sent}"


def test_alert_service_error_never_raises(monkeypatch):
    _reset()
    monkeypatch.setattr(alerts, "send_admin_alert_deduped", MagicMock(side_effect=RuntimeError("telegram down")))
    alerts.alert_service_error("apiframe", 401, "boom")  # must not raise


# ── songs.py: Apiframe 401/402/429 classification ──────────────────────────────
# End-to-end through generate_song_variant's real failure/fallback path, not a
# hand-written reproduction of its internals — same style as
# test_platform_attribution.py's real-insert-path test.

def test_apiframe_401_fires_service_error_alert_and_is_not_silently_swallowed(fresh_db, monkeypatch):
    import importlib
    import songs as _songs
    importlib.reload(_songs)

    err = Exception("apiframe rejected the request")
    err.response = MagicMock(status_code=401)
    monkeypatch.setattr(_songs, "_submit_to_apiframe", MagicMock(side_effect=err))
    monkeypatch.setattr(_songs, "GOAPI_API_KEY", "")  # no fallback configured — must re-raise

    p = fresh_db.get_db_path()
    u = _make_lyric(fresh_db, p)

    with patch("alerts.alert_service_error") as alert_fn:
        with pytest.raises(Exception):
            _songs.generate_song_variant(user_id=u["id"], lyric_id=1, style_prompt="s",
                                         genre_tag="pop", db_path=str(p))
        alert_fn.assert_called_once_with("apiframe", 401, str(err))


def test_apiframe_generic_500_does_not_fire_the_service_error_alert(fresh_db, monkeypatch):
    """A transient 500 isn't an auth/quota problem — don't page for it."""
    import importlib
    import songs as _songs
    importlib.reload(_songs)

    err = Exception("apiframe internal error")
    err.response = MagicMock(status_code=500)
    monkeypatch.setattr(_songs, "_submit_to_apiframe", MagicMock(side_effect=err))
    monkeypatch.setattr(_songs, "GOAPI_API_KEY", "")

    p = fresh_db.get_db_path()
    u = _make_lyric(fresh_db, p)

    with patch("alerts.alert_service_error") as alert_fn:
        with pytest.raises(Exception):
            _songs.generate_song_variant(user_id=u["id"], lyric_id=1, style_prompt="s",
                                         genre_tag="pop", db_path=str(p))
        alert_fn.assert_not_called()


def test_apiframe_credit_wording_fires_the_alert_even_without_an_http_status(fresh_db, monkeypatch):
    """Some Apiframe failures surface as a plain exception with 'credit'/'quota' in
    the message rather than a structured HTTP status — must still be caught."""
    import importlib
    import songs as _songs
    importlib.reload(_songs)

    err = RuntimeError("Apiframe: insufficient credit balance")
    monkeypatch.setattr(_songs, "_submit_to_apiframe", MagicMock(side_effect=err))
    monkeypatch.setattr(_songs, "GOAPI_API_KEY", "")

    p = fresh_db.get_db_path()
    u = _make_lyric(fresh_db, p)

    with patch("alerts.alert_service_error") as alert_fn:
        with pytest.raises(Exception):
            _songs.generate_song_variant(user_id=u["id"], lyric_id=1, style_prompt="s",
                                         genre_tag="pop", db_path=str(p))
        alert_fn.assert_called_once_with("apiframe", "unknown", str(err))


class _SyncThread:
    """_alert_fallback_to_goapi normally fires on a daemon thread — replace it with
    a synchronous stand-in so the test can assert on it without a race."""
    def __init__(self, target, args=(), kwargs=None, daemon=None):
        self._target, self._args, self._kwargs = target, args, kwargs or {}

    def start(self):
        self._target(*self._args, **self._kwargs)


def test_apiframe_failure_with_working_goapi_fallback_still_fires_the_alert(fresh_db, monkeypatch):
    """The alert must fire even when GoAPI fallback succeeds — Apiframe being down
    is worth knowing about even if the user's song still gets made another way."""
    import importlib
    import songs as _songs
    importlib.reload(_songs)

    err = Exception("apiframe unauthorized")
    err.response = MagicMock(status_code=401)
    monkeypatch.setattr(_songs, "_submit_to_apiframe", MagicMock(side_effect=err))
    monkeypatch.setattr(_songs, "_submit_to_goapi", MagicMock(return_value="goapi-task-1"))
    monkeypatch.setattr(_songs, "GOAPI_API_KEY", "fake-goapi-key")
    monkeypatch.setattr(_songs, "GOAPI_WEBHOOK_URL", "https://example.com/goapi-webhook")
    monkeypatch.setattr(_songs.threading, "Thread", _SyncThread)

    p = fresh_db.get_db_path()
    u = _make_lyric(fresh_db, p)

    with patch("alerts.alert_service_error") as alert_fn, \
         patch("alerts.send_admin_alert_deduped") as fallback_fn:
        result = _songs.generate_song_variant(user_id=u["id"], lyric_id=1, style_prompt="s",
                                               genre_tag="pop", db_path=str(p))
    assert result["variant_id"]
    alert_fn.assert_called_once_with("apiframe", 401, str(err))
    fallback_fn.assert_called_once()  # the GoAPI-fallback-triggered alert, folded into the shared sender


# ── image_generator.py: fal.ai 401 / 403-exhausted ─────────────────────────────

def test_falai_exhausted_balance_fires_service_error_alert():
    import image_generator

    fake_resp = MagicMock()
    fake_resp.ok = False
    fake_resp.status_code = 403
    fake_resp.text = "Exhausted balance for this account"

    with patch("image_generator.requests.post", return_value=fake_resp), \
         patch("image_generator.FAL_API_KEY", "fake-key"), \
         patch("alerts.alert_service_error") as alert_fn:
        try:
            image_generator.submit_image_generation("a cat", "1024x1024")
        except RuntimeError as exc:
            assert "balance is exhausted" in str(exc)
        alert_fn.assert_called_once()
        service, status, detail = alert_fn.call_args[0]
        assert (service, status) == ("fal.ai", 403)
        assert "balance exhausted" in detail


def test_falai_401_fires_service_error_alert():
    import image_generator

    fake_resp = MagicMock()
    fake_resp.ok = False
    fake_resp.status_code = 401
    fake_resp.text = "Unauthorized"

    with patch("image_generator.requests.post", return_value=fake_resp), \
         patch("image_generator.FAL_API_KEY", "fake-key"), \
         patch("alerts.alert_service_error") as alert_fn:
        try:
            image_generator.submit_image_generation("a dog", "1024x1024")
        except RuntimeError as exc:
            assert "API key is invalid" in str(exc)
        alert_fn.assert_called_once()
        service, status, detail = alert_fn.call_args[0]
        assert (service, status) == ("fal.ai", 401)
        assert "invalid API key" in detail


def test_falai_other_error_does_not_fire_the_alert():
    """A generic 500 from fal.ai isn't an auth/quota problem — don't page for it."""
    import image_generator

    fake_resp = MagicMock()
    fake_resp.ok = False
    fake_resp.status_code = 500
    fake_resp.text = "internal error"

    with patch("image_generator.requests.post", return_value=fake_resp), \
         patch("image_generator.FAL_API_KEY", "fake-key"), \
         patch("alerts.alert_service_error") as alert_fn:
        try:
            image_generator.submit_image_generation("a fox", "1024x1024")
        except RuntimeError:
            pass
        alert_fn.assert_not_called()


# ── songs.py: GoAPI fallback alert now routes through the shared sender ────────

def test_goapi_fallback_alert_uses_shared_deduped_sender_not_its_own_telegram_post():
    import songs

    with patch("alerts.send_admin_alert_deduped") as deduped_fn, \
         patch("songs.requests.post") as raw_post:
        songs._alert_fallback_to_goapi(42, "apiframe timed out")

    deduped_fn.assert_called_once()
    category, message = deduped_fn.call_args[0]
    assert category == "goapi_fallback"
    assert "variant_id=42" in message
    raw_post.assert_not_called(), "must not also fire its own separate Telegram POST"
