"""Singer's accent picker — spec docs/superpowers/specs/2026-10-13-vocal-accent-picker-design.md."""
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
os.environ.setdefault("JWT_SECRET", "test-secret-for-vocal-accent-tests")

EXPECTED_ACCENTS = {
    "english_london": "authentic London British vocals, Cockney or South London accent",
    "english_northern": "Northern English vocals, Manchester or Leeds accent, gritty and warm",
    "scottish": "Scottish accent vocals, Edinburgh or Glasgow lilt",
    "welsh": "Welsh accent vocals, melodic lilting tone",
    "irish": "Irish accent vocals, lilting Dublin or Cork delivery",
    "american_southern": "Southern American accent, country twang, warm drawl",
    "american_newyork": "New York accent vocals, sharp and urban",
    "american_westcoast": "West Coast American vocals, laid back California delivery",
    "jamaican": "Jamaican patois vocals, dancehall delivery, island lilt",
    "brazilian": "Brazilian Portuguese vocals, warm samba inflection",
    "mexican": "Mexican Spanish vocals, warm ranchera delivery",
    "colombian": "Colombian Spanish vocals, coastal Caribbean lilt",
    "nigerian": "Nigerian vocal style, Afrobeats inflection, Lagos energy",
    "ghanaian": "Ghanaian vocals, highlife warmth, Accra tone",
    "south_african": "South African vocals, township energy, Joburg delivery",
    "kenyan": "Kenyan vocals, East African lilt, Nairobi style",
    "senegalese": "Senegalese vocals, West African griot warmth",
    "french": "French accent vocals, Parisian delivery, romantic tone",
    "spanish": "Spanish accent vocals, Castilian delivery",
    "italian": "Italian accent vocals, operatic warmth, Mediterranean tone",
    "german": "German accent vocals, precise and powerful delivery",
    "portuguese": "Portuguese vocals, Lisbon fado-tinged delivery",
    "indian": "Indian accent vocals, Bollywood warmth, Hindi film style",
    "pakistani": "Pakistani vocals, Lahori delivery, qawwali warmth",
    "arabic": "Arabic accent vocals, Middle Eastern melodic delivery",
    "japanese": "Japanese accent vocals, precise and melodic J-pop delivery",
    "korean": "Korean accent vocals, K-pop clean and precise delivery",
    "australian": "Australian accent vocals, laid back Aussie delivery",
    "newzealand": "New Zealand accent vocals, warm Kiwi tone",
}

EXPECTED_DEFAULTS = {
    "grime": "authentic London British MC vocals, South London accent",
    "ukdrill": "London drill vocals, South London accent",
    "irishrebel": "Irish accent vocals, Dublin delivery",
    "irishballad": "Irish accent vocals, lilting emotional delivery",
    "irishtradtechno": "Irish accent gang vocals",
    "ragga": "Jamaican patois vocals, dancehall delivery",
    "rootsreggae": "Jamaican vocals, roots delivery",
    "country": "Southern American accent, country twang",
    "countrysoul": "Southern American vocals, warm soul drawl",
    "outlawcountry": "Southern American accent, dark and gritty drawl",
    "countryrap": "Southern American accent, country rap drawl",
    "countryballad": "Southern American accent, emotional country delivery",
}


# ── Task 1: catalog ──────────────────────────────────────────────────────────

def test_accent_map_has_exactly_the_29_spec_accents():
    from song_genres import ACCENT_STYLE_MAP
    assert len(EXPECTED_ACCENTS) == 29
    assert set(ACCENT_STYLE_MAP) == set(EXPECTED_ACCENTS)


@pytest.mark.parametrize("key,snippet", sorted(EXPECTED_ACCENTS.items()))
def test_each_accent_snippet_is_verbatim(key, snippet):
    from song_genres import ACCENT_STYLE_MAP
    assert ACCENT_STYLE_MAP[key] == snippet


def test_every_accent_is_in_exactly_one_group_in_spec_order():
    from song_genres import ACCENT_GROUPS, ACCENT_STYLE_MAP
    assert [g for g, _ in ACCENT_GROUPS] == [
        "british_isles", "americas", "africa", "europe", "asia", "pacific"]
    keys = [k for _, ks in ACCENT_GROUPS for k in ks]
    assert sorted(keys) == sorted(ACCENT_STYLE_MAP)
    assert len(keys) == len(set(keys))


def test_genre_defaults_are_the_12_spec_entries_on_real_genres():
    from song_genres import GENRE_DEFAULT_ACCENT, GENRE_PRESETS
    assert GENRE_DEFAULT_ACCENT == EXPECTED_DEFAULTS
    assert set(GENRE_DEFAULT_ACCENT) <= set(GENRE_PRESETS)
    assert "outlawcountryrap" not in GENRE_DEFAULT_ACCENT


def test_presets_were_not_edited_to_bake_in_defaults():
    from song_genres import GENRE_DEFAULT_ACCENT, GENRE_PRESETS
    for g, snippet in GENRE_DEFAULT_ACCENT.items():
        assert snippet not in GENRE_PRESETS[g], g


@pytest.mark.parametrize("raw,expected", [
    ("jamaican", "jamaican"), (" Jamaican ", "jamaican"), ("JAMAICAN", "jamaican"),
    ("", None), (None, None), ("klingon", None), ("Jamaican Dancehall", None),
])
def test_resolve_vocal_accent_normalises(raw, expected):
    from song_genres import resolve_vocal_accent
    assert resolve_vocal_accent(raw) == expected


@pytest.mark.parametrize("kw,expected", [
    ({}, True),
    ({"vocal_accent_key": "scottish"}, False),
    ({"legacy_accent": "German"}, False),
    ({"instrumental": True}, False),
    ({"intermittent": True}, False),
    ({"is_story": True}, False),
])
def test_should_use_genre_default_accent(kw, expected):
    from song_genres import should_use_genre_default_accent
    args = dict(vocal_accent_key=None, legacy_accent=None, instrumental=False,
                intermittent=False, is_story=False)
    args.update(kw)
    assert should_use_genre_default_accent(**args) is expected
