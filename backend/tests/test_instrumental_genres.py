"""Instrumental genres must never sing.

Two registries have to agree or a genre silently gains vocals:
  1. songs.INSTRUMENTAL_GENRES  — forces sunoParams.instrumental per variant
  2. song_genres.GENRE_PRESETS  — the style string's "no vocals" tail
  3. the frontends' '🎷 Instrumental & Solo' category — what the user is promised

551a6d2 created that category with six genres but registered only five, so Blues
Guitar sat in the instrumental menu while Suno sang over it. These tests pin all
three together so the next genre added can't drift the same way.
"""
import os
import pathlib
import re
import sys

import pytest

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))

os.environ.setdefault("ANTHROPIC_API_KEY", "test-key-for-tests")
os.environ.setdefault("APIFRAME_API_KEY", "test-key-for-tests")
os.environ.setdefault("SONG_STORAGE_PATH", "/tmp/test_songs")
os.environ.setdefault("SONG_PUBLIC_BASE_URL", "https://example.com/files/songs")
os.environ.setdefault("SONG_WEBHOOK_URL", "https://zeusaidesign.com/webhooks/apiframe")

REPO_ROOT = pathlib.Path(__file__).parent.parent.parent

# Every frontend that renders the genre picker. Each must stay in sync with the backend.
FRONTEND_GENRE_PICKERS = [
    REPO_ROOT / "web-beats" / "src" / "pages" / "SongsPage.jsx",
    REPO_ROOT / "web" / "src" / "pages" / "SongsPage.jsx",
    REPO_ROOT / "zeus-beats-ios" / "src" / "screens" / "CreateSongScreen.tsx",
]


def _category_genres(source: str, category_id: str) -> list[str]:
    """Pull the genre keys out of one GENRE_CATEGORIES entry."""
    block = re.search(rf"id:\s*'{category_id}'.*?genres:\s*\[(.*?)\]", source, re.S)
    assert block, f"category {category_id!r} not found"
    return re.findall(r"'([a-z]+)'", block.group(1))


class TestInstrumentalRegistry:
    def test_blues_guitar_is_instrumental(self):
        from songs import INSTRUMENTAL_GENRES

        assert "electricbluesguitar" in INSTRUMENTAL_GENRES

    def test_psychedelic_guitar_is_instrumental(self):
        from songs import INSTRUMENTAL_GENRES

        assert "psychedelicguitar" in INSTRUMENTAL_GENRES

    @pytest.mark.parametrize(
        "picker", FRONTEND_GENRE_PICKERS, ids=lambda p: p.parent.parent.parent.name
    )
    def test_psychedelic_guitar_lives_in_instrumental_not_rock(self, picker):
        source = picker.read_text(encoding="utf-8")
        assert "psychedelicguitar" in _category_genres(source, "instrumental_solo")
        assert "psychedelicguitar" not in _category_genres(source, "rock")

    @pytest.mark.parametrize(
        "picker", FRONTEND_GENRE_PICKERS, ids=lambda p: p.parent.parent.parent.name
    )
    def test_ui_instrumental_category_is_forced_instrumental(self, picker):
        """The bug: a genre in the UI's instrumental menu but absent from the frozenset."""
        from songs import INSTRUMENTAL_GENRES

        ui_genres = _category_genres(picker.read_text(encoding="utf-8"), "instrumental_solo")
        assert ui_genres, "instrumental_solo category is empty"
        missing = [g for g in ui_genres if g not in INSTRUMENTAL_GENRES]
        assert missing == [], (
            f"{picker.name} offers {missing} as instrumental but the backend won't force it"
        )

    @pytest.mark.parametrize(
        "picker", FRONTEND_GENRE_PICKERS, ids=lambda p: p.parent.parent.parent.name
    )
    def test_ui_instrumental_category_suppresses_vocals_in_style(self, picker):
        from song_genres import GENRE_PRESETS

        ui_genres = _category_genres(picker.read_text(encoding="utf-8"), "instrumental_solo")
        missing = [g for g in ui_genres if "no vocals" not in GENRE_PRESETS[g]]
        assert missing == [], f"{missing} lack a 'no vocals' tail in their style string"


class TestLyricsSkippedForInstrumentalGenres:
    """One lyric row is shared by every variant, so lyrics may only be skipped
    when no variant could possibly sing them."""

    def test_all_instrumental_selection_skips_lyrics(self):
        from songs import all_genres_instrumental

        assert all_genres_instrumental(["saxophone", "psychedelicguitar"]) is True

    def test_mixed_selection_still_writes_lyrics(self):
        from songs import all_genres_instrumental

        # The rock variant shares this lyric row — skipping would leave it silent.
        assert all_genres_instrumental(["saxophone", "rock"]) is False

    def test_vocal_selection_writes_lyrics(self):
        from songs import all_genres_instrumental

        assert all_genres_instrumental(["rock"]) is False

    def test_empty_selection_writes_lyrics(self):
        from songs import all_genres_instrumental

        assert all_genres_instrumental([]) is False
        assert all_genres_instrumental(None) is False

    def test_unregistered_genres_are_ignored(self):
        from songs import all_genres_instrumental

        # generate_multiple_variants drops non-preset genres, so only a saxophone
        # variant is built — nothing can sing, lyrics are safe to skip.
        assert all_genres_instrumental(["saxophone", "notarealgenre"]) is True
