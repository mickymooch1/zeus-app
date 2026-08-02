"""Scat Jazz genre registration (2026-08-02).

Two things make this genre work, and the second is easy to forget: the style
string tells Suno how it should SOUND, and the lyric directive makes the sung
content vocables rather than words. Without the directive the lyric writer
produces ordinary lyrics and Suno sings them straight — that is vocal jazz,
not scat.
"""
import os
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))
os.environ.setdefault("ANTHROPIC_API_KEY", "test-key")
os.environ.setdefault("APIFRAME_API_KEY", "test-key")
os.environ.setdefault("SONG_WEBHOOK_URL", "https://zeusaidesign.com/webhooks/apiframe")

from song_genres import GENRE_PRESETS
from lyrics import GENRE_MOOD_DIRECTIVES

_ROOT = pathlib.Path(__file__).parent.parent.parent
# Singers most likely to be reached for when describing scat.
_ARTISTS = ["louis", "armstrong", "ella", "fitzgerald", "cab calloway",
            "sarah vaughan", "mel torme", "scatman", "satchmo"]


def test_scat_preset_exists():
    assert "scat" in GENRE_PRESETS
    assert len(GENRE_PRESETS["scat"]) > 60


def test_scat_style_has_no_artist_names():
    style = GENRE_PRESETS["scat"].lower()
    for name in _ARTISTS:
        assert name not in style, f"style string names {name!r}"


def test_scat_style_describes_the_sound():
    style = GENRE_PRESETS["scat"].lower()
    for token in ["scat singing", "swing", "upright bass", "vocables"]:
        assert token in style, token


def test_scat_lyric_directive_forces_vocables():
    """The bit that actually makes it scat rather than jazz with words."""
    d = GENRE_MOOD_DIRECTIVES.get("scat", "")
    assert d, "scat needs a lyric directive or the vocals will be ordinary words"
    low = d.lower()
    assert "vocable" in low or "wordless" in low
    assert "doo" in low and "bop" in low


def test_scat_registered_in_web_app():
    p = _ROOT / "web-beats" / "src" / "pages" / "SongsPage.jsx"
    s = p.read_text(encoding="utf-8")
    assert "'scat'" in s, "missing from the GENRES list"
    assert "scat:'Scat Jazz'" in s, "missing its label"
    assert "'vocaljazz','scat','swing'" in s, "missing from a category group"


def test_scat_registered_in_ios_app():
    p = _ROOT / "zeus-beats-ios" / "src" / "screens" / "CreateSongScreen.tsx"
    s = p.read_text(encoding="utf-8")
    assert "scat:'Scat Jazz'" in s or "scat: 'Scat Jazz'" in s
    assert "'vocaljazz','scat','swing'" in s


def test_scat_label_present_in_display_maps():
    """Otherwise the player/playlist/share pages render a raw genre key."""
    for rel in ["web-beats/src/components/NowPlayingBar.jsx",
                "web-beats/src/pages/PlaylistPage.jsx",
                "web-beats/src/pages/SongSharePage.jsx"]:
        s = (_ROOT / rel).read_text(encoding="utf-8")
        assert "scat:" in s, rel
