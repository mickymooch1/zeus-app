"""Every Messages.create() call passing temperature/top_p/top_k crashed in
production — not a 400, a Python TypeError, because the deployed anthropic SDK
(1.3.0) dropped those kwargs from the method signature entirely.

Found via a real user's Kids Mode story failing with "Messages.create() got an
unexpected keyword argument 'temperature'". The story-song path looked like the
odd one out, but it wasn't: ALL SEVEN call sites passed temperature (six in
lyrics.py, one in alerts.py), including the main non-kids song path. Confirmed
directly on production, before any fix: calling lyrics.generate_lyrics() with
kids_story=False raised the identical TypeError at the identical line. This was
a full outage of song generation, not a kids-mode-only bug.

Root cause: requirements.txt pinned `anthropic>=0.40.0` — an unbounded floating
minimum. Production silently drifted to 1.3.0 on some redeploy; local dev still
had 0.89.0, which still accepts temperature — that's why this was invisible by
reading source or running tests locally. Same shape as the stripe>=15,<16
incident already pinned in requirements.txt.

WHY THIS TEST DOESN'T JUST RUN AGAINST THE INSTALLED SDK: local dev has 0.89.0,
which still accepts temperature — a test that simply calls the real SDK would
pass whether or not the bug is fixed, on this machine, which is exactly how the
bug went unnoticed locally in the first place. Instead this mocks
Anthropic().messages.create() to enforce production's ACTUAL signature (no
temperature/top_p/top_k) regardless of what's installed here, so the test means
the same thing in every environment.
"""
import os
import pathlib
import sys

import pytest

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))
os.environ.setdefault("ANTHROPIC_API_KEY", "test-key-for-tests")

import db  # noqa: E402
import lyrics  # noqa: E402
import alerts  # noqa: E402


class _FakeMessages:
    """Enforces the ACTUAL production Messages.create() signature — no
    temperature/top_p/top_k — independent of whatever anthropic version happens
    to be installed in whatever environment runs this test."""

    def create(self, *, model, max_tokens, messages, system=None, **kwargs):
        forbidden = {"temperature", "top_p", "top_k"} & kwargs.keys()
        if forbidden:
            raise TypeError(
                f"Messages.create() got an unexpected keyword argument {next(iter(forbidden))!r}"
            )
        text = '{"title": "Sunny Days", "lyrics": "[Verse 1]\\nfake lyrics\\n[Chorus]\\nfake hook"}'
        if system and "You name songs" in system:
            text = "Sunny Days"
        elif system and "roast" in system.lower():
            text = '{"title": "Roast Title", "lyrics": "[Verse 1]\\nroast bars"}'
        elif "segments" in messages[0]["content"]:
            text = '{"segments": [{"text": "Bonjour.", "english": "Hello."}]}'
        elif system and '"lines"' in system:
            # The bilingual story path parses a "lines" array, not a "lyrics" string.
            text = ('{"title": "Histoire", "lines": ['
                    '{"foreign": "Il etait une fois.", "english": "Once upon a time."}]}')
        block = type("Block", (), {"text": text})()
        return type("Resp", (), {"content": [block], "stop_reason": "end_turn"})()


class _FakeAnthropic:
    def __init__(self, *a, **k):
        self.messages = _FakeMessages()


@pytest.fixture
def db_path(tmp_path):
    p = tmp_path / "t.db"
    db.init_user_tables(p)
    return p


@pytest.fixture
def user(db_path):
    return db.create_user(db_path, "songwriter@test.com", "x", "Songwriter", "2026-01-01")


@pytest.fixture(autouse=True)
def fake_anthropic(monkeypatch):
    # lyrics.py does `from anthropic import Anthropic` at MODULE level, so its
    # reference was bound at import time — patch lyrics.Anthropic directly.
    monkeypatch.setattr(lyrics, "Anthropic", _FakeAnthropic)
    # alerts.py does the same import LOCALLY, inside suggest_contact_reply, which
    # re-executes on every call — patching alerts.Anthropic (no such module-level
    # attribute exists) would silently do nothing and let the real SDK through.
    # The import statement resolves against the anthropic package itself at call
    # time, so that's what has to be patched.
    monkeypatch.setattr("anthropic.Anthropic", _FakeAnthropic)


# ── The bug, reproduced exactly as it hit production ──────────────────────────

def test_main_song_path_does_not_crash(db_path, user):
    """This is the path the user was told "still works fine". It didn't —
    confirmed live on production before any fix, identical TypeError, identical
    line. This is that exact call shape: kids_story=False, genres only."""
    result = lyrics.generate_lyrics(
        user_id=user["id"], brief="a song about a sunny afternoon",
        db_path=db_path, genres=["pop"],
    )
    assert result["lyrics"]


def test_kids_story_path_does_not_crash(db_path, user):
    result = lyrics.generate_lyrics(
        user_id=user["id"], brief="a magical forest adventure",
        db_path=db_path, kids_story=True, kids_mode="story",
    )
    assert result["lyrics"]


def test_kids_song_path_does_not_crash(db_path, user):
    result = lyrics.generate_lyrics(
        user_id=user["id"], brief="", db_path=db_path,
        kids_story=True, kids_mode="song", genres=["pop"],
    )
    assert result["lyrics"]


def test_kids_bilingual_story_does_not_crash(db_path, user):
    result = lyrics.generate_lyrics(
        user_id=user["id"], brief="a French adventure", db_path=db_path,
        kids_story=True, kids_mode="story", story_language="french", bilingual_mode=True,
    )
    assert result["lyrics"]


def test_kids_story_translation_call_does_not_crash(db_path, user):
    """The second, translation-only call inside the foreign-language story path —
    the one at temperature=0.2, the odd one out among the temperature=1.0 calls."""
    result = lyrics.generate_lyrics(
        user_id=user["id"], brief="une histoire", db_path=db_path,
        kids_story=True, kids_mode="story", story_language="french", bilingual_mode=False,
    )
    assert result["lyrics"]
    assert result.get("segments"), "translation call must have produced subtitles"


def test_roast_mode_does_not_crash(db_path, user):
    result = lyrics.generate_lyrics(
        user_id=user["id"], brief="", db_path=db_path,
        roast_mode=True, roast_name="Dave", genres=["pop"],
    )
    assert result["lyrics"]


def test_title_generation_does_not_crash():
    """The quiet one: generate_song_title() swallows all exceptions and falls
    back silently, so this never crashed loudly — it just gave every song a
    generic fallback title instead of an AI one, with nothing in the logs to
    flag it. Confirm the real title comes back now, not the fallback."""
    title = lyrics.generate_song_title(
        "[Verse 1]\nfake lyrics", brief="a song about summer", genres=["pop"],
    )
    assert title == "Sunny Days", (
        f"got the fallback title {title!r} — generate_song_title() is still "
        "swallowing an exception, meaning it's still passing a forbidden kwarg"
    )


def test_contact_reply_suggestion_does_not_crash():
    result = alerts.suggest_contact_reply("Dave", "pricing question", "How much for 10 songs?")
    assert result is not None, (
        "suggest_contact_reply swallows exceptions too — a None here means it's "
        "still hitting the same TypeError silently"
    )


# ── Proof the mock itself enforces the real constraint ────────────────────────

def test_the_mock_actually_rejects_temperature():
    """A mock that can't fail isn't a mock — this is the exact shape of the bug,
    reproduced directly against the fake, independent of any real SDK."""
    with pytest.raises(TypeError, match="temperature"):
        _FakeAnthropic().messages.create(
            model="m", max_tokens=1, messages=[{"role": "user", "content": "hi"}],
            temperature=1.0,
        )
