"""Unaffordable requests must be refused BEFORE generate_lyrics runs.

Every credit check in songs_generate used to sit after the lyrics call, so an
unaffordable request burned a Claude call, wrote a lyrics row, and only then 402'd
— leaving an orphaned lyrics row with no variants and no song. Three exist since
2026-08-01: lyric 602 (dominic.rowle@yahoo.com), 680 and 695
(kingshaza727@gmail.com). A normal request costs one credit per genre, so picking
several genres on a small balance hits it easily.

The pre-check MIRRORS the downstream rules rather than replacing them — those stay
in place as defence in depth. What these tests pin:

  * an unaffordable request never reaches generate_lyrics
  * the refusal is a 402 whose message matches the downstream one exactly
  * affordable requests are untouched
  * admins bypass it
  * kids_story / persona / sfx paths are costed at 1, not per-genre
  * an unrecognised genre still yields the 400, not a credit 402
"""
import os
import pathlib
import sys
from unittest.mock import patch

from fastapi.testclient import TestClient

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))
os.environ.setdefault("ANTHROPIC_API_KEY", "test-key")
os.environ.setdefault("APIFRAME_API_KEY", "test-key")
os.environ.setdefault("SONG_STORAGE_PATH", "/tmp/test_songs")
os.environ.setdefault("SONG_PUBLIC_BASE_URL", "https://example.com/files/songs")
os.environ.setdefault("SONG_WEBHOOK_URL", "https://zeusaidesign.com/webhooks/apiframe")
os.environ.setdefault("JWT_SECRET", "test-secret-for-precheck-tests")


def _user(is_admin=0, persona=None):
    u = {
        "id": "precheck-user", "email": "pre@example.com",
        "subscription_status": "active", "subscription_plan": "free",
        "password_hash": "x", "name": "Pre", "is_admin": is_admin,
        "email_verified": 1,
    }
    if persona:
        u["sound_persona_id"] = persona
    return u


def _post(body, balance=3, is_admin=0, persona=None):
    """POST /api/songs/generate with a known balance, capturing whether lyrics ran."""
    import auth
    import main as _main

    _main.app.dependency_overrides[auth.get_current_user] = lambda: _user(is_admin, persona)
    _main.limiter.enabled = False
    try:
        with patch("db.get_song_credits", return_value={"balance": balance, "monthly_allowance": 0}), \
             patch("db.upsert_song_credits"), \
             patch("lyrics.generate_lyrics") as lyr:
            lyr.side_effect = AssertionError("generate_lyrics must not run for a refused request")
            with TestClient(_main.app) as client:
                resp = client.post("/api/songs/generate", json=body,
                                   headers={"Authorization": "Bearer fake"})
            return resp, lyr
    finally:
        _main.app.dependency_overrides.pop(auth.get_current_user, None)


# ── The core guarantee ───────────────────────────────────────────────────────

def test_unaffordable_request_never_reaches_lyrics():
    """5 genres, 3 credits — the exact shape that orphaned lyrics 680 and 695."""
    resp, lyr = _post({"brief": "x", "genres": ["pop", "rock", "jazz", "blues", "soul"]},
                      balance=3)
    assert resp.status_code == 402, f"expected 402, got {resp.status_code}"
    lyr.assert_not_called()


def test_refusal_message_matches_the_downstream_one():
    """The client must not be able to tell which layer refused."""
    resp, _ = _post({"brief": "x", "genres": ["pop", "rock", "jazz", "blues", "soul"]},
                    balance=3)
    assert resp.json()["detail"] == "Need 5 credits, have 3"


def test_exactly_enough_credits_is_allowed_through():
    """Boundary: balance == cost must NOT be refused."""
    resp, lyr = _post({"brief": "x", "genres": ["pop", "rock", "jazz"]}, balance=3)
    assert resp.status_code != 402, "balance == cost must be affordable"
    lyr.assert_called_once()   # got past the gate; the AssertionError proves it ran


def test_zero_balance_with_one_genre_is_refused():
    resp, lyr = _post({"brief": "x", "genres": ["pop"]}, balance=0)
    assert resp.status_code == 402
    assert resp.json()["detail"] == "Need 1 credits, have 0"
    lyr.assert_not_called()


# ── Paths that must NOT be costed per-genre ──────────────────────────────────

def test_admin_bypasses_the_precheck():
    resp, lyr = _post({"brief": "x", "genres": ["pop", "rock", "jazz"]}, balance=0, is_admin=1)
    assert resp.status_code != 402
    lyr.assert_called_once()


def test_kids_story_costs_one_not_one_per_genre():
    """The precheck's flat-1-credit rule keys on kids_story alone, not kids_mode
    (kids_mode='song' here, deliberately not 'story' — story mode is currently
    disabled by the kill switch in test_story_mode_kill_switch.py, and this test
    has nothing to do with that; it would otherwise 503 before ever reaching the
    credit check this test exists to pin)."""
    resp, lyr = _post({"brief": "x", "genres": ["pop", "rock", "jazz"],
                       "kids_story": True, "kids_mode": "song"}, balance=1)
    assert resp.status_code != 402, "kids mode is flat-rate 1 credit"
    lyr.assert_called_once()


def test_persona_path_costs_one_not_one_per_genre():
    resp, lyr = _post({"brief": "x", "genres": ["pop", "rock", "jazz"]},
                      balance=1, persona="persona-123")
    assert resp.status_code != 402, "the persona path renders a single variant"
    lyr.assert_called_once()


# ── The 400 must not be masked by a 402 ──────────────────────────────────────

def test_unknown_genre_still_yields_the_bad_request_not_a_credit_error():
    """With no valid genres the cost is 0, so the existing 'No valid genres
    provided' 400 must still win — a 402 would hide the real problem."""
    resp, _ = _post({"brief": "x", "genres": ["not_a_real_genre"]}, balance=0)
    assert resp.status_code != 402, "a bogus genre is a bad request, not a billing one"


# ── The ordering itself ──────────────────────────────────────────────────────

def test_precheck_is_physically_before_the_lyrics_call():
    import inspect
    import main

    src = inspect.getsource(main.songs_generate)
    assert "refused before lyrics" in src, "the pre-check is gone"
    assert src.index("refused before lyrics") < src.index("generate_lyrics("), \
        "the credit pre-check must come BEFORE generate_lyrics, or it saves nothing"


def test_downstream_checks_are_still_present():
    """The pre-check is an addition, not a replacement — a race could still slip past."""
    import inspect
    import songs

    src = inspect.getsource(songs.generate_multiple_variants)
    assert "InsufficientCreditsError" in src, "downstream credit check must remain"
