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
        # Default scaffolding present for song length
        assert "[Intro - Instrumental]" in out
        assert "[Instrumental verse]" in out
        assert "[Instrumental break]" in out
        assert "[Drop - Instrumental]" in out
        assert "[Outro - Instrumental]" in out
        assert "[Extended outro - Instrumental]" in out
        # Hook repeated 3x + sparse ad-libs give Suno spread vocal content to fill
        # 2.5-3 minutes rather than cutting short on near-empty sections.
        assert out.count("[Hook]") == 4
        assert out.count("[Instrumental verse]") >= 2
        assert "(oohs and ahs)" in out and "(sparse ad-libs fading)" in out
        # Hook is opened and closed
        assert "[Hook]" in out
        assert "[/Hook]" in out

    def test_repeats_hook_four_times_for_standard_song_structure(self):
        full = "[Chorus]\nWe run the night we own the floor\nTurn it up and give me more\n"
        out = lyrics_mod.build_intermittent_hook(full)
        # 4x since 2026-08-20 (was 3x, before that 2x). A 2-line hook repeated 3x is
        # ~520 chars of material for a 2.5-3 minute render; completed songs averaged
        # 114s against a 150s target, i.e. Suno ran out of sheet and stopped.
        assert out.count("We run the night we own the floor") == 4
        assert out.count("[Hook]") == 4
        assert out.count("[/Hook]") == 4
        # Sparse ad-libs give Suno light vocal moments under the instrumentals.
        assert "(oohs and ahs)" in out
        assert "(yeah, uh, come on)" in out

    def test_caps_hook_to_four_lines(self):
        """Raised 2 -> 4 on 2026-08-20: more sung material per block, because the sheet
        was too thin to fill a track. Still a cap — this is a hook, not a full lyric,
        or the mode stops being mostly-instrumental."""
        full = "[Chorus]\nline one\nline two\nline three\nline four\nline five\n"
        out = lyrics_mod.build_intermittent_hook(full)
        assert "line one" in out
        assert "line four" in out
        assert "line five" not in out

    def test_falls_back_to_first_content_lines_when_no_chorus(self):
        full = ("[Verse 1]\nFirst memorable line\nSecond line\nThird line\n"
                "Fourth line\nFifth line\n")
        out = lyrics_mod.build_intermittent_hook(full)
        assert "First memorable line" in out
        assert "Fourth line" in out       # 4-line cap
        assert "Fifth line" not in out    # still capped
        assert "[Hook]" in out

    def test_handles_empty_input(self):
        out = lyrics_mod.build_intermittent_hook("")
        assert "[Hook]" in out
        assert "[Instrumental break]" in out


class TestGenreAwareIntermittentStructure:
    _HOOK_FULL = "[Chorus]\nWe run the night we own the floor\nTurn it up and give me more\n"

    def test_unknown_genre_falls_back_to_default(self):
        out = lyrics_mod.build_intermittent_hook(self._HOOK_FULL, genre="reggaeton")
        # Compare against the EXTENDED default: _extend_structure adds the fourth hook
        # and extra instrumental material to every template on the way through.
        expected = lyrics_mod._extend_structure(
            lyrics_mod.INTERMITTENT_STRUCTURES["default"]
        ).replace("{hook}", "We run the night we own the floor\nTurn it up and give me more")
        assert out == expected

    def test_no_genre_uses_default(self):
        out = lyrics_mod.build_intermittent_hook(self._HOOK_FULL)
        assert "[Instrumental verse]" in out  # default-only tag

    def test_jungle_gets_amen_breaks(self):
        out = lyrics_mod.build_intermittent_hook(self._HOOK_FULL, genre="jungle")
        assert "[Amen break - Instrumental]" in out
        assert "[Reese bass drop - Instrumental]" in out
        assert "[Instrumental verse]" not in out  # not the default structure

    def test_deephouse_gets_grooves_and_breakdown(self):
        out = lyrics_mod.build_intermittent_hook(self._HOOK_FULL, genre="deephouse")
        assert "[Groove - Instrumental]" in out
        assert "[Breakdown - Instrumental]" in out
        assert "[Instrumental groove]" in out

    def test_techhouse_gets_drops_and_builds(self):
        out = lyrics_mod.build_intermittent_hook(self._HOOK_FULL, genre="techhouse")
        assert "[Build - Instrumental]" in out
        assert "[Drop - Instrumental]" in out
        assert "[Breakdown - Instrumental]" in out

    def test_bassline_uses_build_drop_structure(self):
        out = lyrics_mod.build_intermittent_hook(self._HOOK_FULL, genre="bassline")
        assert "[Build]" in out
        assert "[Drop - Instrumental]" in out
        assert "[Instrumental verse]" not in out

    def test_drumandbass_genre_key_aliases_to_drumnbass_structure(self):
        # The app passes the real GENRE_PRESETS key "drumandbass"; it must resolve.
        out = lyrics_mod.build_intermittent_hook(self._HOOK_FULL, genre="drumandbass")
        assert "[Amen break]" in out
        assert "[Jungle break - Instrumental]" in out

    def test_technhouse_genre_key_aliases_to_techhouse_structure(self):
        # GENRE_PRESETS stores tech house under the typo'd key "technhouse".
        out = lyrics_mod.build_intermittent_hook(self._HOOK_FULL, genre="technhouse")
        assert "[Build - Instrumental]" in out
        assert "[Breakdown - Instrumental]" in out

    def test_genre_match_is_case_insensitive(self):
        out = lyrics_mod.build_intermittent_hook(self._HOOK_FULL, genre="Jungle")
        assert "[Amen break - Instrumental]" in out

    def test_every_structure_repeats_hook_four_times_with_adlibs(self):
        for key in lyrics_mod.INTERMITTENT_STRUCTURES:
            out = lyrics_mod.build_intermittent_hook(self._HOOK_FULL, genre=None if key == "default" else key)
            assert out.count("[Hook]") == 4, key
            assert out.count("[/Hook]") == 4, key
            assert out.count("We run the night we own the floor") == 4, key
            assert "{hook}" not in out, key  # placeholder fully substituted
            assert "(oohs and ahs)" in out, key  # sparse ad-libs present


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
        # Full-length duration cue LEADS so Suno weights it first
        assert out.startswith("full length track, 3 minute duration, extended outro")

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

    # Cue LEADS now (2026-08-20), and in the blend path's word order. It used to
    # trail, which put it ~96% through the assembled style string — measured worth
    # ~3s across 68 songs (115.3s with vs 112.5s without, target 150s).
    _DURATION_CUE = "full length track, 3 minute duration, extended outro"

    def test_reinforces_female_vocal_hook_when_female_selected(self):
        out = songs_mod.strip_vocal_cues("bassline house, pitched male vocals, 130 BPM", "f")
        assert "mostly instrumental, female vocal hook only" in out
        assert out.startswith(self._DURATION_CUE)
        assert "pitched male vocals" not in out

    def test_reinforces_male_vocal_hook_when_male_selected(self):
        out = songs_mod.strip_vocal_cues("bassline house, 130 BPM", "m")
        assert "mostly instrumental, male vocal hook only" in out
        assert out.startswith(self._DURATION_CUE)

    def test_reinforces_duet_hook_when_duet_selected(self):
        out = songs_mod.strip_vocal_cues("bassline house, 130 BPM", "duet")
        assert "mostly instrumental, brief male and female vocal hook" in out
        assert out.startswith(self._DURATION_CUE)

    def test_defaults_to_neutral_hook_when_no_gender(self):
        out_none = songs_mod.strip_vocal_cues("bassline house, 130 BPM")
        out_empty = songs_mod.strip_vocal_cues("bassline house, 130 BPM", "")
        assert "mostly instrumental, brief vocal hook only" in out_none
        assert "mostly instrumental, brief vocal hook only" in out_empty
        assert out_none.startswith(self._DURATION_CUE)
        assert out_empty.startswith(self._DURATION_CUE)
