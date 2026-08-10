"""The cloned-voice narrator option must exist in BOTH story flows (2026-08-10).

There are two separate story UIs and they had drifted:

  /kids/story        pages/kids/KidsStoryMode.jsx   had "My Voice"
  main app Kids>Story pages/SongsPage.jsx           did NOT — a hardcoded list
                                                    of 7 accents, no clone check

So a user who cloned their voice and used the main app (the one reachable
without the kids PIN gate) had no way to select it, and the backend support at
main.py `accent == 'my_voice'` was unreachable from there.

No backend change was needed: that picker already sends `accent: kidsNarratorVoice`.
"""
import pathlib
import re

WEB = pathlib.Path(__file__).parent.parent.parent / "web-beats" / "src"
SONGS = (WEB / "pages" / "SongsPage.jsx").read_text(encoding="utf-8")
KIDS = (WEB / "pages" / "kids" / "KidsStoryMode.jsx").read_text(encoding="utf-8")


def test_both_story_pickers_offer_my_voice():
    for name, src in (("SongsPage", SONGS), ("KidsStoryMode", KIDS)):
        assert "'my_voice'" in src, f"{name} lost the My Voice option"
        assert "My Voice" in src, f"{name} lost the My Voice label"


def test_both_gate_it_on_the_user_actually_having_a_clone():
    """It must never show to someone without a clone — selecting it would fall
    back to a default voice with no explanation."""
    for name, src in (("SongsPage", SONGS), ("KidsStoryMode", KIDS)):
        assert "user?.custom_voice_id" in src, f"{name} does not check for a clone"


def test_songspage_sends_the_narrator_value_as_accent():
    """The backend keys on `accent == 'my_voice'`, so the picker's value has to
    travel in that field or the option silently does nothing."""
    assert re.search(r"accent:\s*kidsSubMode === 'story' \?\s*\(kidsNarratorVoice", SONGS)


def test_no_preview_button_for_the_cloned_voice():
    """There is no pre-rendered sample for a user's own clone — offering preview
    would just fail."""
    for name, src in (("SongsPage", SONGS), ("KidsStoryMode", KIDS)):
        assert "val !== 'my_voice'" in src, f"{name} would show a broken preview button"


def test_the_narrator_list_is_a_single_named_constant():
    """It was an inline literal, which is how the two pickers drifted apart."""
    assert "const STORY_NARRATOR_VOICES" in SONGS
    assert "STORY_NARRATOR_VOICES" in SONGS.split("const STORY_NARRATOR_VOICES")[1]
