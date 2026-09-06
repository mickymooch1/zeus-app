"""Vocal-forward genre registration: Scat Jazz (2026-08-02), Opera (2026-08-05).

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
# webhooks.py reads these at import time — needed for the cover-prompt checks.
os.environ.setdefault("SONG_STORAGE_PATH", "/tmp/test_songs")
os.environ.setdefault("SONG_PUBLIC_BASE_URL", "https://example.com/files/songs")

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


# ── Opera (2026-08-05) ───────────────────────────────────────────────────────
# Descriptors only. Composer and singer names are barred for the same reason
# place names were stripped from the bassline family: anything named in a style
# string can end up sung, and it invites impersonation of real performers.

_OPERA_NAMES = ["pavarotti", "callas", "verdi", "puccini", "mozart", "domingo",
                "bocelli", "wagner", "rossini", "bizet", "sutherland"]


def test_opera_preset_exists():
    assert "opera" in GENRE_PRESETS
    assert len(GENRE_PRESETS["opera"]) > 80


def test_opera_style_has_no_composer_or_singer_names():
    style = GENRE_PRESETS["opera"].lower()
    for name in _OPERA_NAMES:
        assert name not in style, f"opera style names {name!r}"


def test_opera_style_describes_the_voice_and_the_orchestra():
    style = GENRE_PRESETS["opera"].lower()
    for token in ["operatic vocals", "soprano", "orchestral", "vibrato", "bel canto"]:
        assert token in style, token


def test_opera_registered_in_web_app():
    s = (_ROOT / "web-beats" / "src" / "pages" / "SongsPage.jsx").read_text(encoding="utf-8")
    assert "'opera'" in s, "missing from the GENRES list"
    assert "opera:'Opera'" in s, "missing its label"
    assert "'classical','opera'" in s, "missing from the classical category group"
    assert s.count("opera:'Opera'") == 1, "duplicate object key"


def test_opera_registered_in_ios_app():
    s = (_ROOT / "zeus-beats-ios" / "src" / "screens" / "CreateSongScreen.tsx").read_text(encoding="utf-8")
    assert "opera:'Opera'" in s
    assert "'classical','opera'" in s
    assert s.count("opera:'Opera'") == 1, "duplicate object key"


def test_opera_label_present_in_display_maps():
    for rel in ["web-beats/src/components/NowPlayingBar.jsx",
                "web-beats/src/pages/PlaylistPage.jsx",
                "web-beats/src/pages/SongSharePage.jsx"]:
        s = (_ROOT / rel).read_text(encoding="utf-8")
        assert "opera:'Opera'" in s, rel
        assert s.count("opera:'Opera'") == 1, f"duplicate key in {rel}"


def test_searching_opera_maps_to_the_genre():
    """The Search page's fuzzy text->genre matcher should resolve "opera"."""
    s = (_ROOT / "web-beats" / "src" / "pages" / "SongsPage.jsx").read_text(encoding="utf-8")
    assert "['opera', 'opera']" in s


# ── Dancehall (2026-08-06) ───────────────────────────────────────────────────

def test_dancehall_preset_exists_and_is_name_free():
    assert "dancehall" in GENRE_PRESETS
    style = GENRE_PRESETS["dancehall"].lower()
    for name in ["vybz", "kartel", "sean paul", "shabba", "beenie", "popcaan", "kingston"]:
        assert name not in style, f"dancehall style names {name!r}"


def test_dancehall_is_distinct_from_ragga():
    """ragga's style string already says "ragga dancehall ... dancehall beat", so
    these two are adjacent by nature. They must not be interchangeable: ragga is
    the older 90 BPM bashment sound, dancehall is modern at 100 BPM."""
    dancehall = GENRE_PRESETS["dancehall"].lower()
    ragga = GENRE_PRESETS["ragga"].lower()
    assert dancehall != ragga
    assert "100 bpm" in dancehall and "90 bpm" in ragga


def test_dancehall_describes_the_sound():
    style = GENRE_PRESETS["dancehall"].lower()
    for token in ["riddim", "offbeat", "sub bass", "dancehall"]:
        assert token in style, token


def test_dancehall_has_its_own_cover_prompt():
    """The gap opera and scat shipped with — a genre falling back to the generic
    default gets untailored artwork, which is what Flux is paid to avoid."""
    import webhooks
    assert "dancehall" in webhooks.GENRE_COVER_PROMPTS
    assert webhooks.GENRE_COVER_PROMPTS["dancehall"] != webhooks._DEFAULT_COVER_PROMPT
    assert webhooks.GENRE_COVER_PROMPTS["dancehall"] != webhooks.GENRE_COVER_PROMPTS["ragga"]


def test_dancehall_registered_in_both_apps():
    web = (_ROOT / "web-beats" / "src" / "pages" / "SongsPage.jsx").read_text(encoding="utf-8")
    assert "'dancehall'" in web
    assert web.count("dancehall:'Dancehall'") == 1, "duplicate object key"
    assert "'ragga','dancehall'" in web, "should sit with the reggae family"
    ios = (_ROOT / "zeus-beats-ios" / "src" / "screens" / "CreateSongScreen.tsx").read_text(encoding="utf-8")
    assert ios.count("dancehall:'Dancehall'") == 1
    assert "'ragga','dancehall'" in ios


def test_dancehall_label_in_display_maps():
    for rel in ["web-beats/src/components/NowPlayingBar.jsx",
                "web-beats/src/pages/PlaylistPage.jsx",
                "web-beats/src/pages/SongSharePage.jsx"]:
        s = (_ROOT / rel).read_text(encoding="utf-8")
        assert s.count("dancehall:'Dancehall'") == 1, rel


# ── Celtic Punk (2026-08-08) ─────────────────────────────────────────────────

def test_celticpunk_exists_and_is_name_free():
    assert "celticpunk" in GENRE_PRESETS
    style = GENRE_PRESETS["celticpunk"].lower()
    for name in ["pogues", "dropkick", "murphys", "flogging", "molly",
                 "macgowan", "boston", "dublin", "ireland"]:
        assert name not in style, f"celticpunk style names {name!r}"


def test_celticpunk_is_distinct_from_the_other_celtic_genres():
    """irishfolk is acoustic and slow-moderate; irishjig is instrumental dance at
    160 BPM. Celtic punk is the electric, shouted one — it must not collapse into
    either."""
    cp = GENRE_PRESETS["celticpunk"].lower()
    assert cp != GENRE_PRESETS["irishfolk"].lower()
    assert cp != GENRE_PRESETS["irishjig"].lower()
    assert "punk" in cp and "electric guitar" in cp
    assert "punk" not in GENRE_PRESETS["irishfolk"].lower()


def test_celticpunk_keeps_the_traditional_instrumentation():
    """The whole point of the genre — punk tempo over trad instruments."""
    cp = GENRE_PRESETS["celticpunk"].lower()
    for token in ["tin whistle", "fiddle", "accordion", "bodhran"]:
        assert token in cp, token


def test_celticpunk_has_its_own_cover_prompt():
    import webhooks
    assert "celticpunk" in webhooks.GENRE_COVER_PROMPTS
    assert webhooks.GENRE_COVER_PROMPTS["celticpunk"] != webhooks._DEFAULT_COVER_PROMPT


def test_celticpunk_registered_in_both_apps():
    web = (_ROOT / "web-beats" / "src" / "pages" / "SongsPage.jsx").read_text(encoding="utf-8")
    assert "'celticpunk'" in web
    assert web.count("celticpunk:'Celtic Punk'") == 1, "duplicate object key"
    assert "'acousticblues','celticpunk'" in web, "should sit in Country & Folk"
    ios = (_ROOT / "zeus-beats-ios" / "src" / "screens" / "CreateSongScreen.tsx").read_text(encoding="utf-8")
    assert ios.count("celticpunk:'Celtic Punk'") == 1
    assert "'acousticblues','celticpunk'" in ios


def test_celticpunk_label_in_display_maps():
    for rel in ["web-beats/src/components/NowPlayingBar.jsx",
                "web-beats/src/pages/PlaylistPage.jsx",
                "web-beats/src/pages/SongSharePage.jsx"]:
        s = (_ROOT / rel).read_text(encoding="utf-8")
        assert s.count("celticpunk:'Celtic Punk'") == 1, rel


def test_irishfolk_carries_the_traditional_instrumentation():
    """Enriched 2026-08-08 instead of adding a third overlapping "traditionalfolk"
    genre. Tin whistle, bodhran and lilting melodies are Irish folk markers, so
    they belong on this genre rather than a near-duplicate of it and "folk"."""
    style = GENRE_PRESETS["irishfolk"].lower()
    for token in ["tin whistle", "bodhran", "mandolin", "lilting", "bpm"]:
        assert token in style, f"irishfolk lost {token!r}"


def test_irishfolk_stays_distinct_from_its_neighbours():
    """It sits between folk and the other Celtic genres — it must not become
    interchangeable with any of them."""
    irish = GENRE_PRESETS["irishfolk"].lower()
    for other in ("folk", "irishjig", "celticpunk", "acoustic", "roots"):
        assert irish != GENRE_PRESETS[other].lower(), f"irishfolk collapsed into {other}"
    # the things that make it Irish folk rather than generic folk
    assert "tin whistle" not in GENRE_PRESETS["folk"].lower()
    # and not the punk one
    assert "punk" not in irish and "electric guitar" not in irish


def test_no_traditionalfolk_genre_was_added():
    """Deliberately not added — it duplicated folk, and its distinguishing
    markers were Celtic ones now folded into irishfolk."""
    assert "traditionalfolk" not in GENRE_PRESETS


# ── Country Ballad (2026-09-06) ──────────────────────────────────────────────

def test_countryballad_preset_exists():
    assert "countryballad" in GENRE_PRESETS
    assert len(GENRE_PRESETS["countryballad"]) > 80


def test_countryballad_describes_the_sound():
    style = GENRE_PRESETS["countryballad"].lower()
    for token in ["steel pedal guitar", "fingerpicking", "60-70 bpm", "heartbreak"]:
        assert token in style, token


def test_countryballad_is_distinct_from_its_neighbours():
    """country/traditionalcountry are upbeat/twangy; acousticballad is genre-
    agnostic. countryballad must not collapse into any of them."""
    cb = GENRE_PRESETS["countryballad"].lower()
    for other in ("country", "traditionalcountry", "acousticballad"):
        assert cb != GENRE_PRESETS[other].lower(), f"countryballad collapsed into {other}"


def test_countryballad_has_its_own_cover_prompt():
    import webhooks
    assert "countryballad" in webhooks.GENRE_COVER_PROMPTS
    assert webhooks.GENRE_COVER_PROMPTS["countryballad"] != webhooks._DEFAULT_COVER_PROMPT
    assert webhooks.GENRE_COVER_PROMPTS["countryballad"] != webhooks.GENRE_COVER_PROMPTS["country"]


def test_countryballad_registered_in_both_apps():
    web = (_ROOT / "web-beats" / "src" / "pages" / "SongsPage.jsx").read_text(encoding="utf-8")
    assert "'countryballad'" in web
    assert web.count("countryballad:'Country Ballad'") == 1, "duplicate object key"
    assert "'countrypop','countryballad'" in web, "should sit in Country & Folk"
    ios = (_ROOT / "zeus-beats-ios" / "src" / "screens" / "CreateSongScreen.tsx").read_text(encoding="utf-8")
    assert ios.count("countryballad:'Country Ballad'") == 1
    assert "'countrypop','countryballad'" in ios


def test_countryballad_label_in_display_maps():
    for rel in ["web-beats/src/components/NowPlayingBar.jsx",
                "web-beats/src/pages/PlaylistPage.jsx",
                "web-beats/src/pages/SongSharePage.jsx"]:
        s = (_ROOT / rel).read_text(encoding="utf-8")
        assert s.count("countryballad:'Country Ballad'") == 1, rel
