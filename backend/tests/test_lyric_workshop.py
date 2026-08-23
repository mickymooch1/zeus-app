"""Lyric Workshop — conversational lyric writing before generation.

Users were leaving to write lyrics elsewhere and pasting them back into "Write my
own". This is the same Claude that already writes lyrics, reachable turn by turn.

Deliberately stateless: the client owns the transcript. There is no table and no
session id, so a redeploy cannot strand a draft and an abandoned workshop leaves
nothing behind. Everything the server must still guarantee is pinned here:

  * the trailing-window cap is enforced SERVER-side, so a hand-rolled client
    cannot grow the prompt without bound
  * a follow-up carries the earlier turns, or "make the hook harder" has no hook
  * the current sheet reaches the model, or edits are written blind
  * output passes through the generator's slur filter — otherwise the workshop
    can approve text the generator would strip, and the song differs from the
    sheet the user signed off on
  * unverified accounts are blocked, matching generation
  * a malformed model response fails loudly rather than returning empty lyrics
"""
import json
import os
import pathlib
import sys
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))
os.environ.setdefault("ANTHROPIC_API_KEY", "test-key")
os.environ.setdefault("APIFRAME_API_KEY", "test-key")
os.environ.setdefault("SONG_STORAGE_PATH", "/tmp/test_songs")
os.environ.setdefault("SONG_PUBLIC_BASE_URL", "https://example.com/files/songs")
os.environ.setdefault("SONG_WEBHOOK_URL", "https://example.com/webhooks/apiframe")
os.environ.setdefault("JWT_SECRET", "test-secret-for-workshop-tests")

import main as _main


def _user(verified=1):
    return {
        "id": "workshop-user-1",
        "email": "writer@example.com",
        "subscription_status": "active",
        "subscription_plan": "free",
        "password_hash": "x",
        "name": "Writer",
        "is_admin": 0,
        "email_verified": verified,
    }


class _Block:
    def __init__(self, text):
        self.text = text


class _Resp:
    def __init__(self, text):
        self.content = [_Block(text)]


def _ok(lyrics="[Verse 1]\nup from nothing\n\n[Chorus]\nwe run it now",
        reply="Wrote your drill track.", title="Up From Nothing"):
    return json.dumps({"reply": reply, "lyrics": lyrics, "title": title})


def _call(messages, current_lyrics=None, raw=None, verified=1):
    """POST the workshop; returns (response, captured create kwargs)."""
    import auth

    captured = {}

    async def _create(**kwargs):
        captured.update(kwargs)
        return _Resp(raw if raw is not None else _ok())

    _main.app.dependency_overrides[auth.get_current_user] = lambda: _user(verified)
    try:
        with patch.object(_main, "get_anthropic_client") as gc:
            gc.return_value.messages.create = AsyncMock(side_effect=_create)
            with TestClient(_main.app) as client:
                r = client.post("/api/lyrics/workshop", json={
                    "messages": messages,
                    "current_lyrics": current_lyrics,
                })
    finally:
        _main.app.dependency_overrides.clear()
    return r, captured


def _u(text):
    return {"role": "user", "content": text}


# ── The happy path ───────────────────────────────────────────────────────────

def test_writes_lyrics_from_a_plain_request():
    r, sent = _call([_u("write me a drill song about coming up from nothing")])
    assert r.status_code == 200, r.text
    body = r.json()
    assert "[Verse 1]" in body["lyrics"]
    assert body["reply"] == "Wrote your drill track."
    assert body["title"] == "Up From Nothing"
    assert sent["model"] == _main._WORKSHOP_HAIKU, "a short first request is Haiku work"


def test_full_sheet_is_returned_not_a_fragment():
    """The response REPLACES the panel, so a diff or a single verse would silently
    destroy the rest of the user's lyrics."""
    r, _ = _call([_u("write a pop song")])
    assert "[Chorus]" in r.json()["lyrics"] and "[Verse 1]" in r.json()["lyrics"]


# ── Conversation context ─────────────────────────────────────────────────────

def test_followups_carry_the_earlier_turns():
    """'make the hook harder' is meaningless without the turns that built the hook."""
    r, sent = _call([
        _u("write a drill song about coming up"),
        {"role": "assistant", "content": "Wrote it."},
        _u("make the hook harder"),
    ])
    assert r.status_code == 200
    texts = [m["content"] for m in sent["messages"]]
    assert any("coming up" in t for t in texts), "the original brief must survive"
    assert texts[-1] == "make the hook harder", "the live request must be last"


def test_the_current_sheet_is_given_to_the_model():
    """Without it the model edits blind and regenerates from scratch, losing the
    user's own manual tweaks."""
    r, sent = _call([_u("add a bridge")], current_lyrics="[Verse 1]\nmy own edit")
    assert r.status_code == 200
    joined = "\n".join(m["content"] for m in sent["messages"])
    assert "my own edit" in joined


def test_the_sheet_is_positioned_before_the_live_request():
    """Appended after the request, the model reads the sheet as the thing to react
    to rather than the thing to edit."""
    _, sent = _call([_u("add a bridge")], current_lyrics="[Verse 1]\nexisting")
    assert sent["messages"][-1]["content"] == "add a bridge"


def test_history_is_capped_server_side():
    """The cap cannot live only in the client — a stale or hand-rolled caller would
    grow the prompt (and the bill) without bound."""
    many = [_u(f"change {i}") for i in range(30)]
    r, sent = _call(many)
    assert r.status_code == 200
    assert len(sent["messages"]) <= _main._WORKSHOP_MAX_MESSAGES
    assert sent["messages"][-1]["content"] == "change 29", "must keep the NEWEST turns"


def test_a_long_sheet_is_truncated_into_the_prompt():
    """Two separate layers guard this, and they do different jobs. This is the inner
    one: a sheet far longer than any real song still produces a bounded prompt."""
    sheet = "[Verse 1]\n" + ("a line of lyrics\n" * 900)   # ~15k chars, under the body cap
    r, sent = _call([_u("tighten it")], current_lyrics=sheet)
    assert r.status_code == 200
    joined = "\n".join(m["content"] for m in sent["messages"])
    assert len(joined) < _main._WORKSHOP_MAX_LYRICS + 2000, "prompt must stay bounded"


def test_an_absurd_payload_is_rejected_at_the_edge():
    """The outer layer: the request body itself is capped, so a pathological caller
    cannot make the server hold 50KB in memory before truncation ever runs. A real
    song is ~2k chars, so nothing legitimate reaches this."""
    r, _ = _call([_u("tighten it")], current_lyrics="x" * 50_000)
    assert r.status_code == 422


# ── Model escalation ─────────────────────────────────────────────────────────

def test_long_briefs_escalate_to_sonnet():
    _, sent = _call([_u("write a song. " + "detail about the story, " * 20)])
    assert sent["model"] == _main._WORKSHOP_SONNET


def test_deep_conversations_escalate_to_sonnet():
    """Constraints accumulate across turns and Haiku starts dropping the earliest."""
    convo = [_u("a"), {"role": "assistant", "content": "ok"}, _u("b"), _u("c")]
    _, sent = _call(convo)
    assert sent["model"] == _main._WORKSHOP_SONNET


def test_structural_rewrites_escalate_to_sonnet():
    _, sent = _call([_u("start over, completely different vibe")])
    assert sent["model"] == _main._WORKSHOP_SONNET


def test_a_named_language_escalates_to_sonnet():
    _, sent = _call([_u("write it in french")])
    assert sent["model"] == _main._WORKSHOP_SONNET


def test_short_simple_edits_stay_on_haiku():
    """Escalating everything would just be paying Sonnet prices for 'add a bridge'."""
    _, sent = _call([_u("add a bridge")])
    assert sent["model"] == _main._WORKSHOP_HAIKU


# ── Safety and failure ───────────────────────────────────────────────────────

def test_output_passes_through_the_slur_filter():
    """The generator strips these. If the workshop did not, the user would approve a
    sheet and get a different song back."""
    import lyrics as _lm

    pattern = getattr(_lm, "_SLUR_PATTERN", None)
    assert pattern is not None, "the generator's filter must exist to be reused"
    dirty = "[Verse 1]\nnigger on the block"
    r, _ = _call([_u("write something")], raw=_ok(lyrics=dirty))
    assert r.status_code == 200
    assert "****" in r.json()["lyrics"]
    assert "nigger" not in r.json()["lyrics"]


def test_unverified_users_are_blocked():
    """Matches generation. An unverified account cannot generate a song, so an
    ungated workshop is spend with no possible payoff."""
    r, _ = _call([_u("write me a song")], verified=0)
    assert r.status_code == 403
    assert r.json()["detail"]["code"] == "email_unverified"


def test_verified_users_are_unaffected():
    r, _ = _call([_u("write me a song")], verified=1)
    assert r.status_code == 200


def test_unparseable_output_fails_loudly():
    """Returning empty lyrics would wipe the panel the user was working in."""
    r, _ = _call([_u("write something")], raw="I'm afraid I can't do that.")
    assert r.status_code == 502


def test_empty_lyrics_are_rejected():
    r, _ = _call([_u("write something")], raw=_ok(lyrics="   "))
    assert r.status_code == 502


def test_prose_wrapped_json_is_still_read():
    """A stray 'Here you go:' preamble should not cost the user their turn."""
    r, _ = _call([_u("write something")], raw="Here you go:\n" + _ok() + "\nHope that helps!")
    assert r.status_code == 200
    assert "[Verse 1]" in r.json()["lyrics"]


def test_an_upstream_failure_is_a_503_not_a_500():
    import auth

    _main.app.dependency_overrides[auth.get_current_user] = lambda: _user(1)
    try:
        with patch.object(_main, "get_anthropic_client") as gc:
            gc.return_value.messages.create = AsyncMock(side_effect=RuntimeError("boom"))
            with TestClient(_main.app) as client:
                r = client.post("/api/lyrics/workshop",
                                json={"messages": [_u("hi")], "current_lyrics": None})
    finally:
        _main.app.dependency_overrides.clear()
    assert r.status_code == 503


# ── Wiring ───────────────────────────────────────────────────────────────────

def test_rate_limited_per_user_not_per_ip():
    """get_remote_address is defeated by Railway's rotating proxy IPs, so an
    IP-keyed limit on a paid-per-call endpoint is no limit at all."""
    import inspect

    src = inspect.getsource(_main.lyrics_workshop)
    assert "_user_key" in src or "20/minute" in src
    outer = inspect.getsource(_main)
    idx = outer.find("async def lyrics_workshop")
    head = outer[max(0, idx - 400):idx]
    assert "key_func=_user_key" in head, "must be keyed by user, not IP"
    assert "20/minute" in head


def test_literal_route_precedes_the_typed_one():
    """/api/lyrics/{lyric_id} would otherwise try to parse 'workshop' as an id — the
    same ordering bug that made /api/discover/for-you 422 since inception."""
    paths = [r.path for r in _main.app.routes if getattr(r, "path", "").startswith("/api/lyrics")]
    assert paths.index("/api/lyrics/workshop") < paths.index("/api/lyrics/{lyric_id}")
