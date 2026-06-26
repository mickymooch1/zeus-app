"""Unit tests for intermittent-vocals helpers.

Intermittent mode must hand Suno almost nothing to sing: a tiny hook wrapped
in instrumental section tags, and a genre style string scrubbed of vocal cues.
"""
import os
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))

# Modules read these at import time — set before importing.
os.environ.setdefault("ANTHROPIC_API_KEY", "test-key-for-tests")
os.environ.setdefault("APIFRAME_API_KEY", "test-key-for-tests")
os.environ.setdefault("SONG_WEBHOOK_URL", "https://zeusaidesign.com/webhooks/apiframe")

import lyrics as lyrics_mod
import songs as songs_mod


class TestBuildIntermittentHook:
    def test_keeps_only_chorus_hook_and_wraps_in_instrumental_structure(self):
        full = (
            "[Verse 1]\n"
            "Walking down the street tonight\n"
            "Feeling all the city lights\n"
            "[Chorus]\n"
            "We run the night we own the floor\n"
            "Turn it up and give me more\n"
            "[Verse 2]\n"
            "Another line goes here\n"
            "And another over there\n"
        )
        out = lyrics_mod.build_intermittent_hook(full)
        # Hook survives, verses do not
        assert "We run the night we own the floor" in out
        assert "Walking down the street tonight" not in out
        assert "Another line goes here" not in out
        # Full instrumental scaffolding present for song length
        assert "[Intro - Instrumental]" in out
        assert "[Instrumental verse]" in out
        assert "[Instrumental break]" in out
        assert "[Instrumental build]" in out
        assert "[Drop - Instrumental]" in out
        assert "[Outro - Instrumental]" in out
        assert "[Extended outro - Instrumental]" in out
        # Multiple instrumental verses give Suno room to fill 2.5-3 minutes
        assert out.count("[Instrumental verse]") >= 3
        # Hook is opened and closed
        assert "[Hook]" in out
        assert "[/Hook]" in out

    def test_repeats_hook_twice_for_standard_song_structure(self):
        full = "[Chorus]\nWe run the night we own the floor\nTurn it up and give me more\n"
        out = lyrics_mod.build_intermittent_hook(full)
        assert out.count("We run the night we own the floor") == 2
        assert out.count("[Hook]") == 2
        assert out.count("[/Hook]") == 2

    def test_caps_hook_to_two_lines(self):
        full = "[Chorus]\nline one\nline two\nline three\nline four\n"
        out = lyrics_mod.build_intermittent_hook(full)
        assert "line one" in out
        assert "line two" in out
        assert "line three" not in out

    def test_falls_back_to_first_content_lines_when_no_chorus(self):
        full = "[Verse 1]\nFirst memorable line\nSecond line\nThird line\n"
        out = lyrics_mod.build_intermittent_hook(full)
        assert "First memorable line" in out
        assert "Third line" not in out
        assert "[Hook]" in out

    def test_handles_empty_input(self):
        out = lyrics_mod.build_intermittent_hook("")
        assert "[Hook]" in out
        assert "[Instrumental break]" in out


class TestStripVocalCues:
    def _vocal_residue(self, text: str) -> str:
        # Ignore the intentional "brief vocal hook only" sentinel we append.
        return text.lower().replace("brief vocal hook only", "")

    def test_removes_pitched_male_vocals_from_bassline_preset(self):
        style = ("bassline house, heavy 4x4 kick, wobbling sub bassline, "
                 "pitched male vocals, 130 BPM, Sheffield underground sound, raw club energy")
        out = songs_mod.strip_vocal_cues(style)
        assert "pitched male vocals" not in out
        assert "vocal" not in self._vocal_residue(out)
        assert "bassline house" in out
        assert "130 BPM" in out
        assert "mostly instrumental, brief vocal hook only" in out
        # Full-length duration cue is appended so Suno renders 2.5-3 minutes
        assert "extended outro, full length track, 3 minute duration" in out

    def test_removes_chopped_female_vocal_samples(self):
        style = ("heavy sub bass, chopped pitched-up female vocal samples, "
                 "Roland organ stabs, 140 BPM")
        out = songs_mod.strip_vocal_cues(style)
        assert "vocal" not in self._vocal_residue(out)
        assert "Roland organ stabs" in out

    def test_removes_singing_and_vocalist_cues(self):
        style = "warm storytelling vocals, gentle singing, lead vocalist, acoustic guitar"
        out = songs_mod.strip_vocal_cues(style)
        residue = self._vocal_residue(out)
        assert "vocal" not in residue
        assert "singing" not in residue
        assert "acoustic guitar" in out

    _DURATION_CUE = "extended outro, full length track, 3 minute duration"

    def test_reinforces_female_vocal_hook_when_female_selected(self):
        out = songs_mod.strip_vocal_cues("bassline house, pitched male vocals, 130 BPM", "f")
        assert "mostly instrumental, female vocal hook only" in out
        assert out.endswith(self._DURATION_CUE)
        assert "pitched male vocals" not in out

    def test_reinforces_male_vocal_hook_when_male_selected(self):
        out = songs_mod.strip_vocal_cues("bassline house, 130 BPM", "m")
        assert "mostly instrumental, male vocal hook only" in out
        assert out.endswith(self._DURATION_CUE)

    def test_reinforces_duet_hook_when_duet_selected(self):
        out = songs_mod.strip_vocal_cues("bassline house, 130 BPM", "duet")
        assert "mostly instrumental, brief male and female vocal hook" in out
        assert out.endswith(self._DURATION_CUE)

    def test_defaults_to_neutral_hook_when_no_gender(self):
        out_none = songs_mod.strip_vocal_cues("bassline house, 130 BPM")
        out_empty = songs_mod.strip_vocal_cues("bassline house, 130 BPM", "")
        assert "mostly instrumental, brief vocal hook only" in out_none
        assert "mostly instrumental, brief vocal hook only" in out_empty
        assert out_none.endswith(self._DURATION_CUE)
        assert out_empty.endswith(self._DURATION_CUE)
