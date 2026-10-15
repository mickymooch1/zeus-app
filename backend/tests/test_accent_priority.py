"""The picked singer's accent must reach the provider's style text.

Found 2026-10-15: on two-genre blends the DJ-transition core fills the ~1000-char
style limit, so the accent (an ordinary suffix descriptor) was dropped in ~19,000 of
20,880 possible blends; a long Sound Control notes box could squeeze it out too (live
logs 2026-10-12: Southern American and Jamaican Rasta dropped). Fix: the accent goes
first and its space is reserved; the genre / blend core and the notes are what get
trimmed, and both genres stay present in a blend.

Also: the "lyrics in that language" French and Spanish entries gave English lyrics
(they shared the accent-only French/Spanish values). They now have their own values.
"""
import itertools
import os
import pathlib
import sys
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))
os.environ.setdefault("ANTHROPIC_API_KEY", "test-key")
os.environ.setdefault("APIFRAME_API_KEY", "test-key")
os.environ.setdefault("SONG_STORAGE_PATH", "/tmp/test_songs")
os.environ.setdefault("SONG_PUBLIC_BASE_URL", "https://example.com/files/songs")
os.environ.setdefault("SONG_WEBHOOK_URL", "https://zeusaidesign.com/webhooks/apiframe")
os.environ.setdefault("JWT_SECRET", "test-secret-for-accent-priority-tests")

from song_genres import GENRE_PRESETS  # noqa: E402

BRITISH = ("strong unmistakable British RP brogue, thick received pronunciation, clipped precise "
           "consonants, pronounce words with heavy Queen's English inflection, distinctly posh "
           "British delivery that cuts through any genre")
# The longest real dropdown descriptor (Cockney Grime, 298 chars + " accent vocals").
COCKNEY = ("thick East London Cockney grime delivery, working class London accent mixed with grime "
           "flow, Cockney rhyming slang inflection, hard London vowels, street grime MC style with "
           "Cockney twist, authentic East End London road man delivery, sharp clipped Cockney "
           "consonants with grime energy accent vocals")
LONG_NOTES = ("Upbeat Southern soul line-dance anthem, 112 BPM, powerful playful African-American "
              "female Southern vocals, funky deep bass guitar, bouncy country soul groove, ") * 6


def _first(genre):
    """A genre's leading descriptor — the part that must survive any trim."""
    return GENRE_PRESETS[genre].split(",")[0].strip()


def _styles(genres, **kw):
    import songs
    captured = {}

    def fake_variant(**k):
        captured[k["genre_tag"]] = k["style_prompt"]
        return {"variant_id": len(captured)}

    with patch.object(songs, "generate_song_variant", side_effect=fake_variant):
        songs.generate_multiple_variants(user_id="u", lyric_id=1, genres=genres,
                                         db_path="unused.db", is_admin=True, **kw)
    return captured


# ── assembly unit ────────────────────────────────────────────────────────────

def test_accent_goes_first_and_is_never_dropped():
    from style_assembly import assemble_variant_style
    core = "g" * 900
    out = assemble_variant_style(core, ["slow tempo", "n" * 800], "", hard_cap=990, genre="x", accent=BRITISH)
    assert out.startswith(BRITISH + ", ")
    assert "ggg" in out
    assert len(out) <= 990


def test_without_an_accent_assembly_is_unchanged():
    from style_assembly import assemble_variant_style
    core = "east coast hip hop, boom bap drums"
    assert assemble_variant_style(core, ["slow tempo"], "") == "slow tempo, " + core
    assert assemble_variant_style(core, ["slow tempo"], "", accent=None) == "slow tempo, " + core


def test_core_too_long_for_the_reserved_space_is_trimmed_at_a_descriptor_boundary():
    from style_assembly import assemble_variant_style
    core = ", ".join(f"descriptor number {i}" for i in range(60))
    out = assemble_variant_style(core, [], "", hard_cap=400, genre="x", accent="accent text")
    assert out.startswith("accent text, descriptor number 0, ")
    assert len(out) <= 400
    assert not out.endswith(",") and not out.rstrip().endswith("descriptor number")


# ── blends ───────────────────────────────────────────────────────────────────

BLEND_SAMPLE = [(a, b) for a, b in itertools.permutations(
    ["grime", "pop", "bluegrass", "ukdrill", "country", "soul", "folk", "britpop"], 2)]


@pytest.mark.parametrize("accent", [BRITISH, COCKNEY])
def test_accent_survives_a_sample_of_blends_with_both_genres_present(accent):
    lost = []
    for a, b in BLEND_SAMPLE:
        style = _styles([a], genre_b=b, suffix_parts=[], accent_part=accent)[f"{a}__{b}"]
        if not (style.startswith(accent) and _first(a) in style and _first(b) in style and len(style) <= 990):
            lost.append(f"{a}x{b}")
    assert lost == [], f"{len(lost)} blends lost the accent or a genre, e.g. {lost[:5]}"


def test_accent_survives_every_blend_of_a_long_genre():
    """Blends whose DJ core alone is already at the 1000-char limit."""
    lost = [b for b in GENRE_PRESETS if b != "bluegrass" and BRITISH not in
            _styles(["bluegrass"], genre_b=b, suffix_parts=[], accent_part=BRITISH)[f"bluegrass__{b}"]]
    assert lost == []


def test_blend_keeps_all_six_dj_sections():
    style = _styles(["bluegrass"], genre_b="folk", suffix_parts=[], accent_part=COCKNEY)["bluegrass__folk"]
    for tag in ("[intro:", "[verse:", "[chorus:", "[bridge:", "[outro:"):
        assert tag in style


def test_blend_without_an_accent_is_unchanged():
    import songs
    a, b = GENRE_PRESETS["pop"], GENRE_PRESETS["grime"]
    style = _styles(["pop"], genre_b="grime", suffix_parts=[])["pop__grime"]
    assert style == songs._dj_transition_style(a, b)[:990]


def test_intermittent_blend_keeps_accent_and_both_genres():
    style = _styles(["bluegrass"], genre_b="folk", suffix_parts=[], accent_part=COCKNEY,
                    intermittent_vocals=True)["bluegrass__folk"]
    assert style.startswith(COCKNEY)
    assert "mostly instrumental" in style


# ── long custom sound description (Sound Control notes) ──────────────────────

@pytest.mark.parametrize("genre", [g for g in ("pop", "soul", "ragga", "southemsoul", "ukdrill") if g in GENRE_PRESETS])
def test_accent_survives_a_long_custom_description(genre):
    style = _styles([genre], suffix_parts=["fast tempo", LONG_NOTES[:1000]], accent_part=COCKNEY)[genre]
    assert style.startswith(COCKNEY)
    assert _first(genre) in style
    assert len(style) <= 990


def test_blend_plus_long_description_keeps_accent_and_both_genres():
    style = _styles(["ragga"], genre_b="country", suffix_parts=[LONG_NOTES[:1000]],
                    accent_part=BRITISH)["ragga__country"]
    assert style.startswith(BRITISH) and _first("ragga") in style and _first("country") in style


# ── endpoint routes the accent separately ────────────────────────────────────

def _user():
    return {"id": "acc-user", "email": "a@example.com", "subscription_status": "active",
            "subscription_plan": "free", "password_hash": "x", "name": "A",
            "is_admin": 0, "email_verified": 1}


def _post(body):
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
                client.post("/api/songs/generate", json=body, headers={"Authorization": "Bearer fake"})
        return gmv.call_args.kwargs, lyr.call_args.kwargs
    finally:
        _main.app.dependency_overrides.pop(auth.get_current_user, None)


def test_endpoint_passes_dropdown_accent_separately_from_the_notes():
    kw, _ = _post({"brief": "x", "genres": ["pop"], "accent": "British",
                   "sound_control": {"notes": LONG_NOTES[:1000]}})
    assert kw["accent_part"] == BRITISH
    assert BRITISH not in kw["suffix_parts"]
    assert LONG_NOTES[:1000].strip() in kw["suffix_parts"]


def test_endpoint_passes_catalog_accent_separately():
    kw, _ = _post({"brief": "x", "genres": ["pop"], "vocal_accent": "jamaican"})
    assert kw["accent_part"] == "Jamaican patois vocals, dancehall delivery, island lilt"


def test_endpoint_without_an_accent_passes_none():
    kw, _ = _post({"brief": "x", "genres": ["pop"]})
    assert kw["accent_part"] is None


def test_an_absurdly_long_free_text_accent_cannot_crowd_out_the_genre():
    kw, _ = _post({"brief": "x", "genres": ["pop"], "accent": "very long accent words, " * 100})
    assert 0 < len(kw["accent_part"]) <= 320


# ── French / Spanish "lyrics in that language" ───────────────────────────────

@pytest.mark.parametrize("value,language", [("French language", "French"), ("Spanish language", "Spanish")])
def test_language_entries_produce_lyrics_in_that_language(value, language):
    import lyrics
    assert lyrics.lyric_language_for(value) == language
    kw, lkw = _post({"brief": "x", "genres": ["pop"], "accent": value})
    assert f"singing in {language}" in kw["accent_part"]
    assert lkw["accent"] == value


@pytest.mark.parametrize("value", ["French", "Spanish"])
def test_accent_only_french_and_spanish_still_sing_in_english(value):
    import lyrics
    assert lyrics.lyric_language_for(value) is None
    kw, _ = _post({"brief": "x", "genres": ["pop"], "accent": value})
    assert "singing in English" in kw["accent_part"]


def test_genre_language_still_wins_over_the_picker():
    import lyrics
    assert lyrics.lyric_language_for("French language", lyrics_language="Spanish") == "Spanish"


@pytest.mark.parametrize("value,language", [("French language", "French"), ("Spanish language", "Spanish")])
def test_lyric_writer_is_told_to_write_in_that_language(value, language, tmp_path, monkeypatch):
    import db
    import lyrics
    monkeypatch.setenv("ZEUS_DATA_DIR", str(tmp_path))
    db_path = tmp_path / "zeus.db"
    db.init_user_tables(db_path)
    sent = []
    fake = MagicMock()

    def create(**k):
        sent.append(k["messages"][0]["content"])
        resp = MagicMock()
        resp.content = [MagicMock(text='{"title": "T", "lyrics": "[Verse 1]\\nla la"}')]
        resp.stop_reason = "end_turn"
        return resp
    fake.messages.create.side_effect = create
    with patch.object(lyrics, "Anthropic", return_value=fake):
        try:
            lyrics.generate_lyrics(user_id="u", brief="a song about summer", db_path=db_path,
                                   genres=["pop"], accent=value)
        except Exception:
            pass  # only the prompt sent to the model matters here
    assert any(f"Write the lyrics ENTIRELY in {language}" in m for m in sent), sent


def test_every_lyrics_in_that_language_option_writes_lyrics_in_a_language():
    """Guard: each option under a '(lyrics in that language)' group on the Create page
    must map to a lyric language — the French/Spanish gap must not come back."""
    import re
    import lyrics
    page = (pathlib.Path(__file__).parent.parent.parent / "web-beats/src/pages/SongsPage.jsx").read_text(encoding="utf-8")
    groups = re.findall(r'<optgroup label="[^"]*\(lyrics in that language\)">(.*?)</optgroup>', page, re.S)
    values = [v for g in groups for v in re.findall(r'<option value="([^"]+)">', g)]
    assert len(values) >= 30
    missing = [v for v in values if not lyrics.lyric_language_for(v)]
    assert missing == []
