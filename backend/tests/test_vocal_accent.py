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


# ── Task 2: songs-level defaults ─────────────────────────────────────────────

def _styles(genres, **kw):
    """Run the real generate_multiple_variants (admin: no credit DB) and capture
    the style_prompt each variant would send to the provider."""
    import songs
    captured = {}

    def fake_variant(**k):
        captured[k["genre_tag"]] = k["style_prompt"]
        return {"variant_id": len(captured)}

    with patch.object(songs, "generate_song_variant", side_effect=fake_variant):
        songs.generate_multiple_variants(user_id="u", lyric_id=1, genres=genres,
                                         db_path="unused.db", is_admin=True, **kw)
    return captured


def test_apply_genre_default_accent_unit():
    from songs import apply_genre_default_accent
    assert apply_genre_default_accent("core", "grime", True) == \
        "core, authentic London British MC vocals, South London accent"
    assert apply_genre_default_accent("core", "grime", False) == "core"
    assert apply_genre_default_accent("core", "pop", True) == "core"


@pytest.mark.parametrize("genre,snippet", sorted(EXPECTED_DEFAULTS.items()))
def test_each_default_genre_gets_its_accent(genre, snippet):
    style = _styles([genre], suffix_parts=[], use_genre_default_accent=True)[genre]
    assert snippet in style


@pytest.mark.parametrize("genre", sorted(EXPECTED_DEFAULTS))
def test_flag_off_means_no_default(genre):
    style = _styles([genre], suffix_parts=[], use_genre_default_accent=False)[genre]
    assert EXPECTED_DEFAULTS[genre] not in style


def test_genres_without_a_default_are_byte_identical():
    """No accent = no change: the flag must not touch any other genre's style."""
    from song_genres import GENRE_PRESETS
    plain = [g for g in GENRE_PRESETS if g not in EXPECTED_DEFAULTS]
    for g in plain:
        on = _styles([g], suffix_parts=["slow tempo"], use_genre_default_accent=True)[g]
        off = _styles([g], suffix_parts=["slow tempo"], use_genre_default_accent=False)[g]
        assert on == off, g


def test_default_only_on_matching_variant():
    s = _styles(["grime", "pop"], suffix_parts=[], use_genre_default_accent=True)
    assert EXPECTED_DEFAULTS["grime"] in s["grime"]
    assert "South London accent" not in s["pop"]


def test_blend_variant_gets_own_genre_default_once():
    s = _styles(["grime"], genre_b="pop", suffix_parts=[], use_genre_default_accent=True)
    style = s["grime__pop"]
    assert style.count(EXPECTED_DEFAULTS["grime"]) == 1


def test_default_survives_suffix_trim():
    huge = ["x" * 400, "y" * 400, "z" * 400]
    style = _styles(["grime"], suffix_parts=huge, use_genre_default_accent=True)["grime"]
    assert EXPECTED_DEFAULTS["grime"] in style
    assert len(style) <= 990


def test_existing_callers_unchanged_by_default():
    """Callers that don't pass the flag (remix, zeus_agent) get no default."""
    style = _styles(["grime"], suffix_parts=[])["grime"]
    assert EXPECTED_DEFAULTS["grime"] not in style


# ── Task 3: endpoint ─────────────────────────────────────────────────────────

def _user():
    return {"id": "accent-user", "email": "a@example.com", "subscription_status": "active",
            "subscription_plan": "free", "password_hash": "x", "name": "A",
            "is_admin": 0, "email_verified": 1}


def _post(body):
    """Drive /api/songs/generate; capture variant-builder and lyrics kwargs."""
    import auth
    import main as _main
    from fastapi.testclient import TestClient

    _main.app.dependency_overrides[auth.get_current_user] = _user
    _main.limiter.enabled = False
    try:
        with patch("db.get_song_credits", return_value={"balance": 10, "monthly_allowance": 0}), \
             patch("db.upsert_song_credits"), \
             patch("lyrics.generate_lyrics",
                   return_value={"lyric_id": 1, "lyrics": "[Verse 1]\nfake", "title": "Fake"}) as lyr, \
             patch("songs.generate_multiple_variants",
                   return_value={"variants": [{"variant_id": 1, "genre": "pop"}]}) as gmv:
            with TestClient(_main.app) as client:
                resp = client.post("/api/songs/generate", json=body,
                                   headers={"Authorization": "Bearer fake"})
        return resp, gmv, lyr
    finally:
        _main.app.dependency_overrides.pop(auth.get_current_user, None)


def _kw(gmv):
    assert gmv.called, "generate_multiple_variants was never reached"
    return gmv.call_args.kwargs


def test_vocal_accent_appends_snippet_and_disables_default():
    resp, gmv, _ = _post({"brief": "x", "genres": ["pop"], "vocal_accent": "jamaican"})
    assert resp.status_code == 200
    kw = _kw(gmv)
    assert EXPECTED_ACCENTS["jamaican"] in kw["suffix_parts"]
    assert kw["use_genre_default_accent"] is False


def test_no_accent_enables_default_and_adds_nothing():
    resp, gmv, _ = _post({"brief": "x", "genres": ["grime"]})
    kw = _kw(gmv)
    assert kw["use_genre_default_accent"] is True
    assert not any(s in kw["suffix_parts"] for s in EXPECTED_ACCENTS.values())


def test_explicit_accent_overrides_grime_default():
    _, gmv, _ = _post({"brief": "x", "genres": ["grime"], "vocal_accent": "scottish"})
    kw = _kw(gmv)
    assert EXPECTED_ACCENTS["scottish"] in kw["suffix_parts"]
    assert kw["use_genre_default_accent"] is False


def test_legacy_accent_still_works_and_suppresses_default():
    """Old app builds still send accent="Irish"; it must keep its descriptor."""
    _, gmv, _ = _post({"brief": "x", "genres": ["grime"], "accent": "Irish"})
    kw = _kw(gmv)
    assert any("Irish brogue" in s for s in kw["suffix_parts"])
    assert kw["use_genre_default_accent"] is False


def test_legacy_language_accent_overrides_default():
    _, gmv, _ = _post({"brief": "x", "genres": ["grime"], "accent": "German"})
    assert _kw(gmv)["use_genre_default_accent"] is False


def test_instrumental_skips_default():
    _, gmv, _ = _post({"brief": "x", "genres": ["grime"], "instrumental": True})
    assert _kw(gmv)["use_genre_default_accent"] is False


def test_intermittent_skips_default():
    _, gmv, _ = _post({"brief": "x", "genres": ["grime"], "intermittent_vocals": True})
    assert _kw(gmv)["use_genre_default_accent"] is False


def test_unknown_vocal_accent_is_ignored_not_rejected():
    resp, gmv, _ = _post({"brief": "x", "genres": ["grime"], "vocal_accent": "klingon"})
    assert resp.status_code == 200
    kw = _kw(gmv)
    assert kw["use_genre_default_accent"] is True
    assert not any("klingon" in s for s in kw["suffix_parts"])


def test_vocal_accent_key_is_normalised():
    _, gmv, _ = _post({"brief": "x", "genres": ["pop"], "vocal_accent": " Jamaican "})
    assert EXPECTED_ACCENTS["jamaican"] in _kw(gmv)["suffix_parts"]


def test_both_fields_vocal_accent_wins_style_accent_reaches_lyrics():
    _, gmv, lyr = _post({"brief": "x", "genres": ["pop"],
                         "vocal_accent": "jamaican", "accent": "German"})
    parts = _kw(gmv)["suffix_parts"]
    assert EXPECTED_ACCENTS["jamaican"] in parts
    assert not any("German" in s for s in parts)
    assert lyr.call_args.kwargs["accent"] == "German"


def test_kids_song_mode_applies_vocal_accent():
    _, gmv, _ = _post({"brief": "x", "genres": ["pop"], "kids_story": True,
                       "kids_mode": "song", "vocal_accent": "australian"})
    assert EXPECTED_ACCENTS["australian"] in _kw(gmv)["suffix_parts"]


# ── Final review fixes ───────────────────────────────────────────────────────

@pytest.mark.parametrize("genre_b", ["bluegrass", "folk", "britpop"])
def test_blend_default_survives_long_dj_transition_core(genre_b):
    """Review finding: _dj_transition_style cores often hit the 990 cap, so a default
    appended at the END was hard-truncated away (grime × bluegrass → no London accent)."""
    style = _styles(["grime"], genre_b=genre_b, suffix_parts=[],
                    use_genre_default_accent=True)[f"grime__{genre_b}"]
    assert EXPECTED_DEFAULTS["grime"] in style
    assert len(style) <= 990


def test_every_default_genre_blend_keeps_its_default():
    from song_genres import GENRE_PRESETS
    lost = []
    for g in EXPECTED_DEFAULTS:
        for b in GENRE_PRESETS:
            if b == g:
                continue
            style = _styles([g], genre_b=b, suffix_parts=[], use_genre_default_accent=True)[f"{g}__{b}"]
            if EXPECTED_DEFAULTS[g] not in style:
                lost.append(f"{g}x{b}")
    assert lost == [], f"{len(lost)} blends lost their default, e.g. {lost[:5]}"
