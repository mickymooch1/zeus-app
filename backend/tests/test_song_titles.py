"""Auto-generated song titles (2026-08-05).

Before this, titles were an afterthought. The lyric prompt carried 18 detailed
rules about lyrics and said nothing about the title beyond asking for a "title"
field, and two paths had no AI title at all: every instrumental was called
"Instrumental" and every custom-lyrics song "Custom Song".

Now a dedicated Haiku call names the song from its finished lyrics, genre and
brief. The rule these tests protect above all: a title is cosmetic, so no
failure in naming may ever cost someone the song they paid a credit for.
"""
import os
import pathlib
import sys
from unittest.mock import patch

import pytest

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))
os.environ.setdefault("ANTHROPIC_API_KEY", "test-key")
os.environ.setdefault("APIFRAME_API_KEY", "test-key")
os.environ.setdefault("SONG_STORAGE_PATH", "/tmp/test_songs")
os.environ.setdefault("SONG_PUBLIC_BASE_URL", "https://example.com/files/songs")
os.environ.setdefault("SONG_WEBHOOK_URL", "https://zeusaidesign.com/webhooks/apiframe")
os.environ.setdefault("JWT_SECRET", "test-secret-for-title-tests")

import lyrics as L


def _haiku(text):
    """Patch the Anthropic client so it returns `text` as the title."""
    class _Resp:
        content = [type("T", (), {"text": text})()]

    class _Client:
        def __init__(self, *a, **k):
            self.messages = type("M", (), {"create": lambda _s, **kw: _Resp()})()

    return patch.object(L, "Anthropic", _Client)


# ── it returns a usable title ────────────────────────────────────────────────

def test_returns_the_generated_title():
    with _haiku("Built From Nothing"):
        assert L.generate_song_title("[Verse]\nfrom the block", genres=["grime"]) == "Built From Nothing"


def test_strips_quotes_and_trailing_punctuation():
    """Haiku sometimes wraps the title or adds a full stop despite the rules."""
    for raw, expected in [('"The Silent Shore"', "The Silent Shore"),
                          ("'Back To The Porch Light'", "Back To The Porch Light"),
                          ("Moving On From Forever.", "Moving On From Forever"),
                          ("  Bassline Collapse  ", "Bassline Collapse")]:
        with _haiku(raw):
            assert L.generate_song_title("lyrics", genres=["pop"]) == expected


def test_takes_only_the_first_line_if_it_rambles():
    with _haiku("Silent Shore\n\nThis title evokes the loneliness of..."):
        assert L.generate_song_title("lyrics", genres=["opera"]) == "Silent Shore"


# ── failure must never cost the user their song ──────────────────────────────

def test_api_failure_returns_the_fallback_and_does_not_raise():
    class _Boom:
        def __init__(self, *a, **k):
            raise RuntimeError("API down")

    with patch.object(L, "Anthropic", _Boom):
        assert L.generate_song_title("lyrics", genres=["pop"], fallback="Custom Song") == "Custom Song"


def test_empty_response_returns_the_fallback():
    for junk in ["", "   ", '""']:
        with _haiku(junk):
            assert L.generate_song_title("lyrics", genres=["pop"], fallback="Untitled") == "Untitled"


def test_absurdly_long_title_is_rejected():
    """A 400-character 'title' would wreck every card it renders in."""
    with _haiku("A Very Long Title " * 20):
        assert L.generate_song_title("lyrics", genres=["pop"], fallback="Untitled") == "Untitled"


def test_no_lyrics_and_no_brief_skips_the_call_entirely():
    """Nothing to name it from — don't spend a request to learn that."""
    called = []

    class _Spy:
        def __init__(self, *a, **k):
            called.append(1)
            raise AssertionError("should not have called the API")

    with patch.object(L, "Anthropic", _Spy):
        assert L.generate_song_title(None, brief=None, genres=None, fallback="Untitled") == "Untitled"
    assert not called


# ── it is wired into the paths that had generic or unguided titles ───────────

def test_instrumental_path_no_longer_hardcodes_Instrumental():
    import inspect
    src = inspect.getsource(L.generate_lyrics)
    assert 'title = song_title or "Instrumental"' not in src, "the generic title is back"
    assert "generate_song_title" in src


def test_custom_lyrics_path_no_longer_hardcodes_Custom_Song():
    import inspect
    src = inspect.getsource(L.store_custom_lyrics)
    assert 'title = song_title or "Custom Song"' not in src, "the generic title is back"
    assert "generate_song_title" in src


def test_a_user_supplied_title_always_wins():
    """Never overwrite a title the user typed themselves."""
    import inspect
    for fn in (L.generate_lyrics, L.store_custom_lyrics):
        src = inspect.getsource(fn)
        assert "song_title or generate_song_title" in src, fn.__name__


def test_the_prompt_asks_for_what_was_requested():
    p = L._TITLE_SYSTEM
    assert "2 to 5 words" in p
    assert "genre" in p.lower()
    assert "real, existing song" in p, "must be told not to reuse real song titles"


def test_it_uses_haiku_not_an_expensive_model():
    assert "haiku" in L._TITLE_MODEL.lower()


# ── end to end through the real code path ────────────────────────────────────

def test_generated_title_reaches_the_stored_song(tmp_path, monkeypatch):
    monkeypatch.setenv("ZEUS_DATA_DIR", str(tmp_path))
    import importlib
    import db as _db
    importlib.reload(_db)
    importlib.reload(L)

    p = _db.get_db_path()
    u = _db.create_user(p, email="t@x.co", password_hash="x", name="T", tc_accepted_at="n")

    with _haiku("Breath Like Water"):
        out = L.store_custom_lyrics(
            user_id=u["id"], brief="calm music", lyrics_text="[Verse]\nbreathe",
            db_path=p, genre="meditation")
    assert out["title"] == "Breath Like Water"

    conn = _db._conn(p)
    try:
        row = conn.execute("SELECT title FROM lyrics WHERE id = ?", (out["lyric_id"],)).fetchone()
    finally:
        conn.close()
    assert row["title"] == "Breath Like Water", "the title must persist, not just be returned"
