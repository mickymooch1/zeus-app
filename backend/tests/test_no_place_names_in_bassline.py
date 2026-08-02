"""Place names must not reach the lyrics for the bassline-family genres.

Reported 2026-08-02: songs in Niche/Bassline kept singing the word "Sheffield".

There were TWO sources, and the second was the real one:

  1. song_genres.GENRE_PRESETS — the Suno style string said
     "Sheffield underground sound" / "Nottingham bassline sound", and the niche
     preset opened with "niche music" (Niche was a club, not a sound).

  2. lyrics.GENRE_VOCABULARY — injected verbatim into the lyric prompt as
     "Use authentic <genre> vocabulary and slang: ...". Both niche and bassline
     listed "Sheffield", so Claude was being told IN WORDS to use it. That is
     why it appeared so reliably in the sung lyrics.

Cover-art prompts (songs.py, webhooks.py) still mention Sheffield on purpose —
those generate images, never lyrics.
"""
import os
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))
os.environ.setdefault("ANTHROPIC_API_KEY", "test-key")
os.environ.setdefault("APIFRAME_API_KEY", "test-key")
os.environ.setdefault("SONG_WEBHOOK_URL", "https://zeusaidesign.com/webhooks/apiframe")

from song_genres import GENRE_PRESETS
from lyrics import GENRE_VOCABULARY

# Genres in the bassline family — the ones this bug affected.
BASSLINE_FAMILY = ["bassline", "niche", "deeprotbassline", "purebassline"]

# Places and venues that were, or could plausibly be, embedded in these presets.
BANNED = ["sheffield", "nottingham", "yorkshire", "leeds", "doncaster",
          "rotherham", "barnsley", "niche music"]


def test_bassline_family_style_strings_have_no_place_or_club_names():
    for genre in BASSLINE_FAMILY:
        style = GENRE_PRESETS[genre].lower()
        for banned in BANNED:
            assert banned not in style, f"{genre} style string still contains {banned!r}"


def test_bassline_family_lyric_vocabulary_has_no_place_names():
    """The real cause — this list is an instruction to Claude, verbatim."""
    for genre in BASSLINE_FAMILY:
        vocab = GENRE_VOCABULARY.get(genre, "").lower()
        for banned in BANNED:
            assert banned not in vocab, f"{genre} lyric vocabulary still contains {banned!r}"


def test_sheffield_is_gone_from_both_sources_entirely():
    for genre in BASSLINE_FAMILY:
        assert "sheffield" not in GENRE_PRESETS[genre].lower()
        assert "sheffield" not in GENRE_VOCABULARY.get(genre, "").lower()


def test_the_sound_is_still_described():
    """Removing the place must not gut the genre — these must still read as
    bassline/speed-garage, or the fix has broken the sound."""
    for genre in ["bassline", "niche", "deeprotbassline"]:
        style = GENRE_PRESETS[genre].lower()
        assert "bass" in style
        assert "bpm" in style
        # each keeps a distinctive sonic hook
        assert any(k in style for k in ["4x4", "wobbl", "sub bass", "organ", "garage"]), genre


def test_niche_and_bassline_are_distinct_genres_not_duplicates():
    """They are adjacent but deliberately different: different tempo and
    different vocal treatment. If they ever become identical, one is redundant."""
    niche = GENRE_PRESETS["niche"].lower()
    bassline = GENRE_PRESETS["bassline"].lower()
    assert niche != bassline
    assert "138 bpm" in niche and "130 bpm" in bassline
    assert "female" in niche and "male" in bassline


def test_bassline_family_presets_are_non_empty():
    for genre in BASSLINE_FAMILY:
        assert len(GENRE_PRESETS[genre]) > 40, genre
