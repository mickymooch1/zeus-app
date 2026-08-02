"""Inspired By must capture THEME as well as sound (2026-08-02).

Before this change the reference lookup extracted only musical style
descriptors, which fed the Suno style string. generate_lyrics had no channel
for the reference at all, so the lyric prompt's "Theme:" slot was filled by
random.choice(_THEMES) — an inspired-by song matched the sound while its
subject matter was a random word from a list of 22.

(The lookup endpoint was also 500ing outright: get_anthropic_client() returns
AsyncAnthropic and the call was never awaited, so `.content` hit a coroutine.
The same bug was fixed in music_search in eee5753 but missed here.)
"""
import inspect
import os
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))
os.environ.setdefault("ANTHROPIC_API_KEY", "test-key")
os.environ.setdefault("APIFRAME_API_KEY", "test-key")
os.environ.setdefault("SONG_STORAGE_PATH", "/tmp/test_songs")
os.environ.setdefault("SONG_PUBLIC_BASE_URL", "https://example.com/files/songs")
os.environ.setdefault("SONG_WEBHOOK_URL", "https://zeusaidesign.com/webhooks/apiframe")
os.environ.setdefault("JWT_SECRET", "test-secret-for-inspired-by-tests")

from songs import sanitize_inspired_by_descriptors, sanitize_inspired_by_theme


# ── The theme must survive sanitisation ──────────────────────────────────────

def test_the_reported_example_survives():
    """The user's own example: a song about a woman taking a man for a fool.
    The subject must reach the lyrics, not be scrubbed away."""
    theme = sanitize_inspired_by_theme(
        "a woman who plays a man for a fool and leaves him humiliated — betrayal, "
        "wounded pride and being outsmarted"
    )
    assert theme
    low = theme.lower()
    for word in ["woman", "fool", "betrayal", "outsmarted"]:
        assert word in low, f"lost '{word}' from the theme: {theme!r}"


def test_theme_keeps_sentence_structure():
    """Unlike the style path, this is a brief for a writer — not a token list."""
    theme = sanitize_inspired_by_theme("a man begging for a second chance after ruining everything")
    assert theme and len(theme.split()) >= 6


# ── But identifying information must not ─────────────────────────────────────

def test_quoted_song_titles_are_removed():
    theme = sanitize_inspired_by_theme('the narrator mourns a lost love in "Cry Me a River" style')
    assert theme is None or "cry me a river" not in theme.lower()


def test_by_artist_attribution_is_removed():
    theme = sanitize_inspired_by_theme(
        "a story of betrayal and revenge by Bob Marley told from the woman's side"
    )
    assert theme
    assert "bob marley" not in theme.lower()
    assert "betrayal" in theme.lower()   # subject survives


def test_known_artist_names_are_removed():
    from songs import DIRECT_ARTIST_STYLE_MAP
    artist = next(iter(DIRECT_ARTIST_STYLE_MAP))
    theme = sanitize_inspired_by_theme(f"heartbreak and longing, the way {artist} would tell it")
    assert theme is None or artist.lower() not in theme.lower()


def test_unknown_theme_becomes_none():
    for junk in ["unknown", "  Unknown.  ", "n/a", "none", "", None, "short"]:
        assert sanitize_inspired_by_theme(junk) is None


def test_theme_is_length_capped():
    assert len(sanitize_inspired_by_theme("betrayal and revenge " * 100)) <= 400


# ── The theme must actually reach the lyric prompt ───────────────────────────

def test_generate_lyrics_accepts_inspired_by_theme():
    import lyrics
    sig = inspect.signature(lyrics.generate_lyrics)
    assert "inspired_by_theme" in sig.parameters
    assert sig.parameters["inspired_by_theme"].default is None


def test_inspired_theme_overrides_the_random_theme():
    """The core regression: with a reference, the lyric prompt's theme must be
    the reference's subject — NOT random.choice(_THEMES)."""
    import lyrics
    src = inspect.getsource(lyrics.generate_lyrics)
    assert 'theme = (inspired_by_theme or "").strip() or random.choice(_THEMES)' in src, (
        "the random theme must only be a fallback when no reference theme is present"
    )


def test_subject_matter_directive_is_added_to_the_prompt():
    import lyrics
    src = inspect.getsource(lyrics.generate_lyrics)
    assert "SUBJECT MATTER" in src
    assert "must be ABOUT" in src


def test_generate_endpoint_passes_theme_through():
    import main
    src = inspect.getsource(main.songs_generate)
    assert "inspired_by_theme" in src
    assert "sanitize_inspired_by_theme" in src


def test_request_model_has_theme_field():
    import main
    assert "inspired_by_theme" in main.SongsGenerateRequest.model_fields


# ── The style path keeps its existing guarantees ─────────────────────────────

def test_style_descriptors_still_strip_proper_nouns():
    """Suno must still never receive artist/song/place names."""
    out = sanitize_inspired_by_descriptors("reggae, Bob Marley, 80 BPM, warm bassline")
    assert out
    assert "bob marley" not in out.lower()
    assert "reggae" in out.lower()


def test_artist_style_endpoint_awaits_the_async_client():
    """Regression guard for the bug that made this endpoint 500 on every call."""
    import main
    src = inspect.getsource(main.artist_style)
    assert "await get_anthropic_client().messages.create" in src
    assert "haiku = get_anthropic_client().messages.create" not in src


def test_artist_style_returns_both_halves():
    import main
    src = inspect.getsource(main.artist_style)
    assert '"style_descriptors"' in src and '"theme"' in src
    # It must ask for the subject matter, not only the sound.
    assert "THEME:" in src and "STYLE:" in src
