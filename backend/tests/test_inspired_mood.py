"""Lyric mood must follow the Search-Inspiration theme, not a dice roll.

Found 2026-09-21 in the production logs: a Search -> "Use as inspiration" run on a
song about a destructive relationship reached generate_lyrics with the right theme
("...their relationship became destructive, built on mutual dependency and harmful
patterns...") but `mood='euphoric'`, because lyrics.py did `mood = random.choice(_MOODS)`
unconditionally. The song's subject was carried through; its emotional register was
random and could flatly contradict it.

Fix: when a reference theme is present, infer the mood from the theme text
(lyrics.infer_mood_from_theme). No theme, or a theme with no emotional signal, keeps
the old random pick — and the genre "IMPORTANT MOOD" directives still win.
"""
import os
import pathlib
import random
import sys

import pytest

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))
os.environ.setdefault("ANTHROPIC_API_KEY", "test-key")
os.environ.setdefault("APIFRAME_API_KEY", "test-key")
os.environ.setdefault("SONG_STORAGE_PATH", "/tmp/test_songs")
os.environ.setdefault("SONG_PUBLIC_BASE_URL", "https://example.com/files/songs")
os.environ.setdefault("SONG_WEBHOOK_URL", "https://zeusaidesign.com/webhooks/apiframe")
os.environ.setdefault("JWT_SECRET", "test-secret-for-inspired-mood-tests")

import lyrics

# The two real themes from the production logs (2026-09-21), verbatim.
DESTRUCTIVE = ("A person confronts how their relationship became destructive, built on mutual "
               "dependency and harmful patterns, as they struggle to break free from cycles they "
               "can no longer control")
LONELY = ("A person sits alone by the water, grappling with uncertainty and loneliness after "
          "personal upheaval and lost love, finding momentary peace in solitude while wrestling "
          "with questions about direction and meaning")
JOYFUL = "A crowd celebrating a hard-won victory, dancing all night with pure joy and freedom"
ROMANTIC = ("Two people falling deeply in love, sharing an intimate, passionate evening of "
            "desire and devotion")
NOSTALGIC = "An old friend remembering childhood summers and the good old days in the hometown"
ANGRY = "Someone furious at being silenced, rising up in defiance and refusing to back down"

DARK_MOODS = {"dark and gritty", "raw and emotional", "melancholic and reflective"}
SAD_MOODS = {"melancholic", "melancholic and reflective", "bittersweet", "raw and emotional"}
UPBEAT_MOODS = {"euphoric", "euphoric and uplifting", "uplifting", "energetic and hype", "playful"}


def infer_many(theme, n=80):
    return {lyrics.infer_mood_from_theme(theme) for _ in range(n)}


# ── inference ────────────────────────────────────────────────────────────────

def test_the_reported_destructive_relationship_gets_a_dark_mood_never_euphoric():
    moods = infer_many(DESTRUCTIVE)
    assert moods <= DARK_MOODS, f"got {moods - DARK_MOODS}"
    assert not (moods & UPBEAT_MOODS)


def test_the_lonely_reflective_theme_gets_a_sad_mood():
    assert infer_many(LONELY) <= SAD_MOODS


@pytest.mark.parametrize("theme,allowed", [
    (JOYFUL, {"euphoric and uplifting", "uplifting", "energetic and hype", "euphoric"}),
    (ROMANTIC, {"romantic", "smooth and sensual"}),
    (NOSTALGIC, {"nostalgic", "bittersweet"}),
    (ANGRY, {"defiant", "aggressive and intense", "raw and emotional", "aggressive"}),
])
def test_other_emotional_registers_map_to_matching_moods(theme, allowed):
    assert infer_many(theme) <= allowed


@pytest.mark.parametrize("theme", [
    # From test_inspired_by_theme.py — remorse, NOT hope: "second chance" must not win.
    "a man begging for a second chance after ruining everything",
    "someone consumed by guilt and shame, apologising to a friend they betrayed... too late",
])
def test_remorse_reads_as_sad_or_dark_never_uplifting(theme):
    assert infer_many(theme) <= (SAD_MOODS | DARK_MOODS)


def test_mixed_joy_and_grief_is_bittersweet():
    assert infer_many("A person celebrating with joy while grieving the loss of a friend") == {"bittersweet"}


def test_more_evidence_beats_less():
    # One cheerful word inside a clearly sad theme must not flip it.
    theme = LONELY + ", and even a little joy"
    assert infer_many(theme) <= SAD_MOODS


@pytest.mark.parametrize("theme", [None, "", "   ", "a man walking to the shop and buying some bread"])
def test_no_emotional_signal_means_no_inference(theme):
    assert lyrics.infer_mood_from_theme(theme) is None


def test_matching_is_case_insensitive_and_whole_word():
    assert infer_many("HEARTBREAK and LONELINESS") <= SAD_MOODS
    # "belonging" / "prolonged" must not trip the "longing" stem.
    assert lyrics.infer_mood_from_theme("The prolonged belonging of a long walk") is None
    # "harmony" must not trip a "harm..." stem.
    assert lyrics.infer_mood_from_theme("Voices in perfect harmony") is None


def test_every_inferable_mood_is_a_real_mood():
    """The result is dropped straight into the lyric prompt beside the random ones."""
    for name, _stems, moods in lyrics._MOOD_LEXICON:
        assert moods, name
        assert set(moods) <= set(lyrics._MOODS), f"{name}: {set(moods) - set(lyrics._MOODS)}"
    assert "bittersweet" in lyrics._MOODS


# ── what actually reaches the model ──────────────────────────────────────────

class _Stop(Exception):
    pass


def _prompt(monkeypatch, tmp_path, **kw):
    """Run generate_lyrics up to the model call and return what it would have sent."""
    seen = {}

    class Messages:
        @staticmethod
        def create(**kwargs):
            seen.update(kwargs)
            raise _Stop()

    class FakeClient:
        messages = Messages

    monkeypatch.setattr(lyrics, "Anthropic", lambda *a, **k: FakeClient())
    with pytest.raises(_Stop):
        lyrics.generate_lyrics("u1", "", tmp_path / "x.db", **kw)
    return seen["system"], seen["messages"][0]["content"]


def _mood_in(text, marker):
    line = next(p for p in text.replace("\n", " ").split(marker)[1:2])
    return line.split(".")[0].split(" — ")[0].strip()


def test_the_model_gets_the_inferred_mood_in_both_the_system_and_user_prompt(monkeypatch, tmp_path):
    for _ in range(15):
        system, user = _prompt(monkeypatch, tmp_path, genres=["rnb"], inspired_by_theme=DESTRUCTIVE)
        m_user = _mood_in(user, "Mood: ")
        m_sys = _mood_in(system, "Emotional angle: ")
        assert m_user in DARK_MOODS, m_user
        assert m_sys == m_user, "system and user prompts must agree on the mood"


def test_without_a_theme_the_mood_is_still_the_random_pick(monkeypatch, tmp_path):
    monkeypatch.setattr(lyrics.random, "choice", lambda seq: seq[0])
    _system, user = _prompt(monkeypatch, tmp_path, genres=["rnb"])
    assert "Mood: uplifting" in user           # _MOODS[0]: random path untouched


def test_a_theme_with_no_emotional_signal_falls_back_to_random(monkeypatch, tmp_path):
    monkeypatch.setattr(lyrics.random, "choice", lambda seq: seq[0])
    _system, user = _prompt(monkeypatch, tmp_path, genres=["rnb"],
                            inspired_by_theme="a man walking to the shop and buying some bread")
    assert "Mood: uplifting" in user


def test_genre_mood_directives_still_apply_on_top(monkeypatch, tmp_path):
    _system, user = _prompt(monkeypatch, tmp_path, genres=["christmas"], inspired_by_theme=DESTRUCTIVE)
    assert "IMPORTANT MOOD" in user            # Christmas stays joyful, as before
    assert "Mood: " in user


def test_the_theme_and_subject_directive_are_unchanged(monkeypatch, tmp_path):
    _system, user = _prompt(monkeypatch, tmp_path, genres=["rnb"], inspired_by_theme=DESTRUCTIVE)
    assert f"Theme: {DESTRUCTIVE}" in user
    assert "SUBJECT MATTER" in user
