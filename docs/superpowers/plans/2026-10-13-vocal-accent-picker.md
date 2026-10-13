# Vocal Accent Picker Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** One grouped "Singer's Accent" picker (29 accents + kept languages + kept vocal styles) in the Zeus Beats Create flow on web and iOS, plus per-genre default accents that an explicit choice overrides.

**Architecture:** The backend catalog (`ACCENT_STYLE_MAP`, `ACCENT_GROUPS`, `GENRE_DEFAULT_ACCENT`) lives in `song_genres.py`. A new optional request field `vocal_accent` adds its snippet to the existing accent prefix (`style_suffix_parts`); genre defaults are appended per variant in `songs.generate_multiple_variants` behind one boolean that `main.py` computes. Clients carry a mirrored catalog guarded by a 3-way text-scan test.

**Tech Stack:** FastAPI + pytest (backend), React/Vite + `node --test` (web-beats), Expo React Native + TypeScript (zeus-beats-ios).

**Spec:** `docs/superpowers/specs/2026-10-13-vocal-accent-picker-design.md`

## Global Constraints

- Work on branch `feature/vocal-accent-picker` in the worktree `scratchpad/accent-wt`. Never commit to master; no deploy until the user says so.
- Exactly 29 accent keys, snippets verbatim from the spec table. 12 genre defaults verbatim from the spec table.
- Do NOT edit `GENRE_PRESETS` strings, nor the body of `_ACCENT_DESCRIPTORS` / the legacy accent block in main.py (only its guard condition).
- Legacy `accent` field keeps working unchanged for languages, vocal styles, kids Story narration and old app builds.
- Unknown `vocal_accent` → ignored + logged, never a 4xx.
- Labels verbatim: adult "🎤 Singer's Accent (optional)", kids "🎤 Singer's Voice", adult first option "None", kids first option "🌟 Default".
- iOS: no new npm dependencies; no pricing/upgrade copy (App Store rule).
- No paid generations at any point.
- Backend tests: `cd backend && ANTHROPIC_API_KEY=x APIFRAME_API_KEY=x SONG_STORAGE_PATH=<tmp>/songs JWT_SECRET=x ZEUS_DATA_DIR=<tmp> py -m pytest ...` (use `py`, never set `SONG_PUBLIC_BASE_URL`/`SONG_WEBHOOK_URL`).
- Files are CRLF + UTF-8 (emoji). Edit with the Edit tool or byte-safe Python; never PowerShell `Set-Content`.
- Every commit ends with `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.

## Review Focus

1. **Old app builds sending removed legacy values** (`accent: "Jamaican"`, `"Irish"`) must still get the old descriptor AND suppress the genre default — pinned in Task 3 (`test_legacy_accent_still_works_and_suppresses_default`).
2. **Multi-genre request mixing a default genre with a plain one** (grime + pop) must put the default only on the grime variant — pinned in Task 2 (`test_default_only_on_matching_variant`).
3. **Blend grime × pop** must carry grime's default exactly once on the grime variant — pinned in Task 2 (`test_blend_variant_gets_own_genre_default_once`).
4. **Messy keys from clients** (`" Jamaican "`, `"JAMAICAN"`) must resolve, not silently drop — pinned in Task 1 (`test_resolve_vocal_accent_normalises`) and Task 3 (`test_vocal_accent_key_is_normalised`).
5. **Long suffix + default near the 990-char cap**: the default is part of the genre core and must survive the suffix trim — pinned in Task 2 (`test_default_survives_suffix_trim`).

---

## File Structure

| File | Responsibility |
|---|---|
| `backend/song_genres.py` (modify) | Catalog: `ACCENT_STYLE_MAP`, `ACCENT_GROUPS`, `GENRE_DEFAULT_ACCENT`, `resolve_vocal_accent()`, `should_use_genre_default_accent()` |
| `backend/songs.py` (modify) | `apply_genre_default_accent()` + `use_genre_default_accent` param on `generate_multiple_variants` |
| `backend/main.py` (modify) | `vocal_accent` field; suffix; legacy-block guard; pass the flag |
| `backend/tests/test_vocal_accent.py` (create) | Catalog, songs-level, endpoint-level tests |
| `backend/tests/test_accent_catalog_sync.py` (create) | 3-way guard: backend ↔ genres.js ↔ iOS |
| `web-beats/src/utils/genres.js` (modify) | `ACCENT_OPTIONS`, `ACCENT_GROUP_LABELS`, `accentOptionLabel()`, `accentPayload()` |
| `web-beats/src/utils/accents.test.mjs` (create) | Pure-function tests + source scans of pickers |
| `web-beats/src/components/KidsVoicePicker.jsx` (create) | Shared kids accent select |
| `web-beats/src/pages/SongsPage.jsx` (modify) | Adult picker moved + regrouped; payload routing; kids picker swap |
| `web-beats/src/pages/kids/KidsSongMode.jsx` (modify) | Use `KidsVoicePicker`, send `vocal_accent` |
| `web-beats/src/locales/*.json` (modify) | `songs.accentLabel` text |
| `zeus-beats-ios/src/screens/CreateSongScreen.tsx` (modify) | Accent catalog + expandable grouped chip picker + `vocal_accent` in request |

---

### Task 1: Backend accent catalog

**Files:**
- Modify: `backend/song_genres.py` (append at end of file)
- Test: `backend/tests/test_vocal_accent.py` (create)

**Interfaces:**
- Produces: `ACCENT_STYLE_MAP: dict[str, str]`, `ACCENT_GROUPS: list[tuple[str, list[str]]]` (group ids `british_isles, americas, africa, europe, asia, pacific`), `GENRE_DEFAULT_ACCENT: dict[str, str]`, `resolve_vocal_accent(key: str | None) -> str | None`, `should_use_genre_default_accent(*, vocal_accent_key: str | None, legacy_accent: str | None, instrumental: bool, intermittent: bool, is_story: bool) -> bool`.

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/test_vocal_accent.py`:

```python
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
```

- [ ] **Step 2: Run to verify failure**

Run: `cd backend && <env> py -m pytest tests/test_vocal_accent.py -q`
Expected: FAIL — `ImportError: cannot import name 'ACCENT_STYLE_MAP'`.

- [ ] **Step 3: Implement — append to `backend/song_genres.py`**

```python


# ── Singer's accent picker ───────────────────────────────────────────────────
# Spec: docs/superpowers/specs/2026-10-13-vocal-accent-picker-design.md.
# Mirrored (keys + groups) in web-beats/src/utils/genres.js ACCENT_OPTIONS and
# zeus-beats-ios CreateSongScreen.tsx; tests/test_accent_catalog_sync.py guards it.
ACCENT_STYLE_MAP: dict[str, str] = {
    # British Isles & Ireland
    "english_london":     "authentic London British vocals, Cockney or South London accent",
    "english_northern":   "Northern English vocals, Manchester or Leeds accent, gritty and warm",
    "scottish":           "Scottish accent vocals, Edinburgh or Glasgow lilt",
    "welsh":              "Welsh accent vocals, melodic lilting tone",
    "irish":              "Irish accent vocals, lilting Dublin or Cork delivery",
    # Americas
    "american_southern":  "Southern American accent, country twang, warm drawl",
    "american_newyork":   "New York accent vocals, sharp and urban",
    "american_westcoast": "West Coast American vocals, laid back California delivery",
    "jamaican":           "Jamaican patois vocals, dancehall delivery, island lilt",
    "brazilian":          "Brazilian Portuguese vocals, warm samba inflection",
    "mexican":            "Mexican Spanish vocals, warm ranchera delivery",
    "colombian":          "Colombian Spanish vocals, coastal Caribbean lilt",
    # Africa
    "nigerian":           "Nigerian vocal style, Afrobeats inflection, Lagos energy",
    "ghanaian":           "Ghanaian vocals, highlife warmth, Accra tone",
    "south_african":      "South African vocals, township energy, Joburg delivery",
    "kenyan":             "Kenyan vocals, East African lilt, Nairobi style",
    "senegalese":         "Senegalese vocals, West African griot warmth",
    # Europe
    "french":             "French accent vocals, Parisian delivery, romantic tone",
    "spanish":            "Spanish accent vocals, Castilian delivery",
    "italian":            "Italian accent vocals, operatic warmth, Mediterranean tone",
    "german":             "German accent vocals, precise and powerful delivery",
    "portuguese":         "Portuguese vocals, Lisbon fado-tinged delivery",
    # Middle East & Asia
    "indian":             "Indian accent vocals, Bollywood warmth, Hindi film style",
    "pakistani":          "Pakistani vocals, Lahori delivery, qawwali warmth",
    "arabic":             "Arabic accent vocals, Middle Eastern melodic delivery",
    "japanese":           "Japanese accent vocals, precise and melodic J-pop delivery",
    "korean":             "Korean accent vocals, K-pop clean and precise delivery",
    # Pacific
    "australian":         "Australian accent vocals, laid back Aussie delivery",
    "newzealand":         "New Zealand accent vocals, warm Kiwi tone",
}

ACCENT_GROUPS: list[tuple[str, list[str]]] = [
    ("british_isles", ["english_london", "english_northern", "scottish", "welsh", "irish"]),
    ("americas", ["american_southern", "american_newyork", "american_westcoast", "jamaican",
                  "brazilian", "mexican", "colombian"]),
    ("africa", ["nigerian", "ghanaian", "south_african", "kenyan", "senegalese"]),
    ("europe", ["french", "spanish", "italian", "german", "portuguese"]),
    ("asia", ["indian", "pakistani", "arabic", "japanese", "korean"]),
    ("pacific", ["australian", "newzealand"]),
]

# The accent a genre sings in when the user picks none. Kept OUT of GENRE_PRESETS so an
# explicit choice can replace it cleanly; songs.apply_genre_default_accent appends it.
GENRE_DEFAULT_ACCENT: dict[str, str] = {
    "grime":           "authentic London British MC vocals, South London accent",
    "ukdrill":         "London drill vocals, South London accent",
    "irishrebel":      "Irish accent vocals, Dublin delivery",
    "irishballad":     "Irish accent vocals, lilting emotional delivery",
    "irishtradtechno": "Irish accent gang vocals",
    "ragga":           "Jamaican patois vocals, dancehall delivery",
    "rootsreggae":     "Jamaican vocals, roots delivery",
    "country":         "Southern American accent, country twang",
    "countrysoul":     "Southern American vocals, warm soul drawl",
    "outlawcountry":   "Southern American accent, dark and gritty drawl",
    "countryrap":      "Southern American accent, country rap drawl",
    "countryballad":   "Southern American accent, emotional country delivery",
}


def resolve_vocal_accent(key: str | None) -> str | None:
    """The ACCENT_STYLE_MAP key for a client value, or None when blank/unknown."""
    k = (key or "").strip().lower()
    return k if k in ACCENT_STYLE_MAP else None


def should_use_genre_default_accent(*, vocal_accent_key: str | None, legacy_accent: str | None,
                                    instrumental: bool, intermittent: bool, is_story: bool) -> bool:
    """Genre defaults apply only to sung songs where the user chose no accent at all —
    any explicit choice (incl. a legacy language/vocal-style accent) replaces them."""
    return not (vocal_accent_key or legacy_accent or instrumental or intermittent or is_story)
```

- [ ] **Step 4: Run to verify pass**

Run: `cd backend && <env> py -m pytest tests/test_vocal_accent.py -q` → all pass.

- [ ] **Step 5: Commit**

```bash
git add backend/song_genres.py backend/tests/test_vocal_accent.py
git commit -m "feat(accent): backend accent catalog and genre defaults"
```

---

### Task 2: Genre defaults in the variant builder

**Files:**
- Modify: `backend/songs.py` — `generate_multiple_variants` (def at ~617; loop body ~661-705)
- Test: `backend/tests/test_vocal_accent.py` (append)

**Interfaces:**
- Consumes: `GENRE_DEFAULT_ACCENT` (Task 1).
- Produces: `songs.apply_genre_default_accent(genre_style: str, genre: str, enabled: bool) -> str`; new kwarg `generate_multiple_variants(..., use_genre_default_accent: bool = False)`.

- [ ] **Step 1: Write failing tests** (append to `test_vocal_accent.py`)

```python
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
```

- [ ] **Step 2: Run to verify failure**

Run: `<env> py -m pytest tests/test_vocal_accent.py -q -k "default or apply or byte or blend or variant or callers"`
Expected: FAIL — `ImportError: apply_genre_default_accent` / `unexpected keyword argument 'use_genre_default_accent'`.

- [ ] **Step 3: Implement in `backend/songs.py`**

Add above `def generate_multiple_variants(`:

```python
def apply_genre_default_accent(genre_style: str, genre: str, enabled: bool) -> str:
    """Append the genre's default singer accent (song_genres.GENRE_DEFAULT_ACCENT) to the
    genre core. Part of the core on purpose: assemble_variant_style trims the suffix,
    never the core, so the default survives a long Sound Control/accent suffix."""
    from song_genres import GENRE_DEFAULT_ACCENT
    default = GENRE_DEFAULT_ACCENT.get(genre) if enabled else None
    return f"{genre_style}, {default}" if default else genre_style
```

Add the parameter to the signature, after `platform: str | None = None,`:

```python
    use_genre_default_accent: bool = False,
```

In the loop, immediately before the line `genre_style = style` (inside `for genre in valid_genres:`), insert:

```python
        style = apply_genre_default_accent(style, genre, use_genre_default_accent)
```

- [ ] **Step 4: Run to verify pass** — same command → all pass.

- [ ] **Step 5: Commit**

```bash
git add backend/songs.py backend/tests/test_vocal_accent.py
git commit -m "feat(accent): append genre default accent per variant"
```

---

### Task 3: `vocal_accent` on the generate endpoint

**Files:**
- Modify: `backend/main.py` — `SongsGenerateRequest` (~2498), accent block guard (~3292), after legacy block (~3434), `generate_multiple_variants` call (~3574)
- Test: `backend/tests/test_vocal_accent.py` (append)

**Interfaces:**
- Consumes: `resolve_vocal_accent`, `should_use_genre_default_accent`, `ACCENT_STYLE_MAP` (Task 1); `use_genre_default_accent` kwarg (Task 2).
- Produces: request field `vocal_accent: str | None` (max 40 chars).

- [ ] **Step 1: Write failing tests** (append)

```python
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
```

- [ ] **Step 2: Run to verify failure**

Run: `<env> py -m pytest tests/test_vocal_accent.py -q -k "vocal_accent or legacy or instrumental or intermittent or kids or both or no_accent or explicit"`
Expected: FAIL — `KeyError: 'use_genre_default_accent'` and missing snippets.

- [ ] **Step 3: Implement in `backend/main.py`**

(a) In `SongsGenerateRequest`, directly under the `accent:` line:

```python
    vocal_accent: str | None = Field(default=None, max_length=40)  # song_genres.ACCENT_STYLE_MAP key → style prefix; overrides genre default
```

(b) Immediately before the line `    if body.accent and not _is_story:` (~3292), insert:

```python
    from song_genres import ACCENT_STYLE_MAP as _ACCENT_STYLE_MAP, resolve_vocal_accent as _resolve_vocal_accent
    _vocal_accent_key = _resolve_vocal_accent(body.vocal_accent)
    if body.vocal_accent and not _vocal_accent_key:
        log.info("accent: unknown vocal_accent=%r ignored", body.vocal_accent)
```

and change that line to:

```python
    if body.accent and not _is_story and not _vocal_accent_key:
```

(c) Directly after the legacy block ends — i.e. before the comment line `    # Rapid Fire Rap: the concise style descriptor is added via _accent_desc above` — insert:

```python
    if _vocal_accent_key and not _is_story:
        style_suffix_parts.append(_ACCENT_STYLE_MAP[_vocal_accent_key])
        log.info("accent: vocal_accent=%r applied", _vocal_accent_key)
```

(d) In the `_songs_mod.generate_multiple_variants(` call inside `songs_generate` (the one passing `suffix_parts=style_suffix_parts`), add after `platform=...`:

```python
            use_genre_default_accent=_song_genres_mod.should_use_genre_default_accent(
                vocal_accent_key=_vocal_accent_key, legacy_accent=body.accent or None,
                instrumental=_effective_instrumental,
                intermittent=bool(body.intermittent_vocals), is_story=_is_story),
```

and add `import song_genres as _song_genres_mod` next to the import inserted in (b).

- [ ] **Step 4: Run to verify pass** — `<env> py -m pytest tests/test_vocal_accent.py -q` → all pass. Then the neighbours: `<env> py -m pytest tests/test_style_assembly.py tests/test_my_voice_option.py tests/test_story_mode_kill_switch.py tests/test_credit_precheck.py -q` → all pass.

- [ ] **Step 5: Commit**

```bash
git add backend/main.py backend/tests/test_vocal_accent.py
git commit -m "feat(accent): vocal_accent request field with genre-default override"
```

---

### Task 4: Web accent catalog + payload routing

**Files:**
- Modify: `web-beats/src/utils/genres.js` (append)
- Test: `web-beats/src/utils/accents.test.mjs` (create)

**Interfaces:**
- Produces: `ACCENT_OPTIONS: {key, label, flag, group}[]` (29, spec order), `ACCENT_GROUP_LABELS: [groupId, heading][]`, `accentOptionLabel(opt) => "🇯🇲 Jamaican"`, `accentPayload(value) => {vocal_accent} | {accent} | {}`.

- [ ] **Step 1: Write failing tests** — create `web-beats/src/utils/accents.test.mjs`:

```js
// Run: node --test src/utils/accents.test.mjs
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { ACCENT_OPTIONS, ACCENT_GROUP_LABELS, accentOptionLabel, accentPayload } from './genres.js';

test('29 accents, unique keys, every group known', () => {
  assert.equal(ACCENT_OPTIONS.length, 29);
  assert.equal(new Set(ACCENT_OPTIONS.map(o => o.key)).size, 29);
  const groups = ACCENT_GROUP_LABELS.map(([id]) => id);
  assert.deepEqual(groups, ['british_isles', 'americas', 'africa', 'europe', 'asia', 'pacific']);
  for (const o of ACCENT_OPTIONS) assert.ok(groups.includes(o.group), o.key);
});

test('option label is flag-first', () => {
  const jam = ACCENT_OPTIONS.find(o => o.key === 'jamaican');
  assert.equal(accentOptionLabel(jam), '🇯🇲 Jamaican');
});

test('accentPayload routes accent keys, legacy values and blank', () => {
  assert.deepEqual(accentPayload('jamaican'), { vocal_accent: 'jamaican' });
  assert.deepEqual(accentPayload('German'), { accent: 'German' });
  const rapid = 'extremely fast rapid-fire rap delivery, machine gun flow';
  assert.deepEqual(accentPayload(rapid), { accent: rapid });
  assert.deepEqual(accentPayload(''), {});
  assert.deepEqual(accentPayload(undefined), {});
});
```

- [ ] **Step 2: Run to verify failure** — `cd web-beats && node --test src/utils/accents.test.mjs` → FAIL (exports missing).

- [ ] **Step 3: Implement — append to `web-beats/src/utils/genres.js`**

```js

// ── Singer's accent picker ──────────────────────────────────────────────────
// Keys/groups mirror backend/song_genres.py ACCENT_STYLE_MAP + ACCENT_GROUPS and
// zeus-beats-ios CreateSongScreen.tsx; backend/tests/test_accent_catalog_sync.py
// fails the build if any of the three drift.
export const ACCENT_GROUP_LABELS = [
  ['british_isles', '🇬🇧🇮🇪 British Isles & Ireland'],
  ['americas',      '🌎 Americas'],
  ['africa',        '🌍 Africa'],
  ['europe',        '🇪🇺 Europe'],
  ['asia',          '🌏 Middle East & Asia'],
  ['pacific',       '🌊 Pacific'],
];
export const ACCENT_OPTIONS = [
  { key: 'english_london',     label: 'London',               flag: '🇬🇧', group: 'british_isles' },
  { key: 'english_northern',   label: 'Northern English',     flag: '🇬🇧', group: 'british_isles' },
  { key: 'scottish',           label: 'Scottish',             flag: '🏴󠁧󠁢󠁳󠁣󠁴󠁿', group: 'british_isles' },
  { key: 'welsh',              label: 'Welsh',                flag: '🏴󠁧󠁢󠁷󠁬󠁳󠁿', group: 'british_isles' },
  { key: 'irish',              label: 'Irish',                flag: '🇮🇪', group: 'british_isles' },
  { key: 'american_southern',  label: 'Southern American',    flag: '🇺🇸', group: 'americas' },
  { key: 'american_newyork',   label: 'New York',             flag: '🇺🇸', group: 'americas' },
  { key: 'american_westcoast', label: 'West Coast American',  flag: '🇺🇸', group: 'americas' },
  { key: 'jamaican',           label: 'Jamaican',             flag: '🇯🇲', group: 'americas' },
  { key: 'brazilian',          label: 'Brazilian',            flag: '🇧🇷', group: 'americas' },
  { key: 'mexican',            label: 'Mexican',              flag: '🇲🇽', group: 'americas' },
  { key: 'colombian',          label: 'Colombian',            flag: '🇨🇴', group: 'americas' },
  { key: 'nigerian',           label: 'Nigerian',             flag: '🇳🇬', group: 'africa' },
  { key: 'ghanaian',           label: 'Ghanaian',             flag: '🇬🇭', group: 'africa' },
  { key: 'south_african',      label: 'South African',        flag: '🇿🇦', group: 'africa' },
  { key: 'kenyan',             label: 'Kenyan',               flag: '🇰🇪', group: 'africa' },
  { key: 'senegalese',         label: 'Senegalese',           flag: '🇸🇳', group: 'africa' },
  { key: 'french',             label: 'French',               flag: '🇫🇷', group: 'europe' },
  { key: 'spanish',            label: 'Spanish',              flag: '🇪🇸', group: 'europe' },
  { key: 'italian',            label: 'Italian',              flag: '🇮🇹', group: 'europe' },
  { key: 'german',             label: 'German',               flag: '🇩🇪', group: 'europe' },
  { key: 'portuguese',         label: 'Portuguese',           flag: '🇵🇹', group: 'europe' },
  { key: 'indian',             label: 'Indian',               flag: '🇮🇳', group: 'asia' },
  { key: 'pakistani',          label: 'Pakistani',            flag: '🇵🇰', group: 'asia' },
  { key: 'arabic',             label: 'Arabic',               flag: '🇸🇦', group: 'asia' },
  { key: 'japanese',           label: 'Japanese',             flag: '🇯🇵', group: 'asia' },
  { key: 'korean',             label: 'Korean',               flag: '🇰🇷', group: 'asia' },
  { key: 'australian',         label: 'Australian',           flag: '🇦🇺', group: 'pacific' },
  { key: 'newzealand',         label: 'New Zealand',          flag: '🇳🇿', group: 'pacific' },
];
const _ACCENT_KEYS = new Set(ACCENT_OPTIONS.map(o => o.key));

export const accentOptionLabel = (opt) => `${opt.flag} ${opt.label}`;

// One picker holds two kinds of value: an ACCENT_OPTIONS key (→ vocal_accent) or a
// legacy language / vocal-style value (→ accent, which lyrics.py also reads).
export function accentPayload(value) {
  if (!value) return {};
  return _ACCENT_KEYS.has(value) ? { vocal_accent: value } : { accent: value };
}
```

Note: the accent keys deliberately never collide with legacy values (legacy values are capitalised words like `German` or long descriptors), which the test pins.

- [ ] **Step 4: Run to verify pass** — `node --test src/utils/accents.test.mjs` → pass; then `npm test` → all pass.

- [ ] **Step 5: Commit**

```bash
git add web-beats/src/utils/genres.js web-beats/src/utils/accents.test.mjs
git commit -m "feat(accent): web accent catalog and payload routing"
```

---

### Task 5: Web adult picker (SongsPage)

**Files:**
- Modify: `web-beats/src/pages/SongsPage.jsx` — import (line 27), standard + roast request bodies (~1085-1117), new picker after `<GenreTileGrid …/>` (~2220), remove old picker from the Advanced panel (~2298-2378)
- Modify: `web-beats/src/locales/*.json` — `songs.accentLabel`
- Test: `web-beats/src/utils/accents.test.mjs` (append source scans)

**Interfaces:**
- Consumes: `ACCENT_OPTIONS`, `ACCENT_GROUP_LABELS`, `accentOptionLabel`, `accentPayload` (Task 4).

- [ ] **Step 1: Write failing tests** (append to `accents.test.mjs`)

```js
import { readFileSync } from 'node:fs';
const SONGS_PAGE = readFileSync(new URL('../pages/SongsPage.jsx', import.meta.url), 'utf8');
const EN = JSON.parse(readFileSync(new URL('../locales/en.json', import.meta.url), 'utf8'));

test('adult label text', () => {
  assert.equal(EN.songs.accentLabel, "🎤 Singer's Accent (optional)");
});

test('adult picker sits right after the genre grid, outside Advanced', () => {
  const grid = SONGS_PAGE.indexOf('<GenreTileGrid');
  const picker = SONGS_PAGE.indexOf("t('songs.accentLabel')");
  const adv = SONGS_PAGE.indexOf('{showAdvanced && (');
  assert.ok(grid > 0 && picker > grid && picker < adv, 'picker must be between grid and Advanced');
  assert.equal(SONGS_PAGE.split("t('songs.accentLabel')").length - 1, 1, 'exactly one adult picker');
});

test('three groups: accents, languages, vocal styles — nothing lost', () => {
  assert.match(SONGS_PAGE, /🌐 Sing in another language/);
  assert.match(SONGS_PAGE, /🎙 Vocal Style/);
  for (const kept of ['Rapid Fire Rap', 'Deep Bass Voice', 'Classic Rock', 'Vocoder / Talk Box',
                      'Cockney Grime', 'Bashment MC', 'UK Jungle MC', 'British MC Grime',
                      'American Soul', 'Caribbean', 'Punjabi', 'Brazilian Portuguese', 'Yoruba'])
    assert.ok(SONGS_PAGE.includes(kept), `lost option: ${kept}`);
  assert.ok(!SONGS_PAGE.includes('Auto (matches your genre)'));
});

test('standard and roast requests route the picker via accentPayload', () => {
  assert.equal(SONGS_PAGE.split('...accentPayload(accent)').length - 1, 2);
  assert.ok(!/\n\s*accent: accent \|\| undefined,/.test(SONGS_PAGE), 'raw accent send left behind');
});
```

- [ ] **Step 2: Run to verify failure** — `node --test src/utils/accents.test.mjs` → the four new tests FAIL.

- [ ] **Step 3: Implement**

(a) Line 27 import becomes:

```js
import { GENRE_CATEGORIES, genreColor, gLabel, GENRES, ACCENT_OPTIONS, ACCENT_GROUP_LABELS, accentOptionLabel, accentPayload } from '../utils/genres';
```

(b) In BOTH the roast `requestBody` and the standard `requestBody`, replace the line `accent: accent || undefined,` with `...accentPayload(accent),` (keep the comment above the roast one).

(c) Cut the whole old picker block from the Advanced panel — from `{!['meditation','healingfrequency'].some(g => selGenres.has(g)) && <div>` through its closing `</div>}` (the block containing `t('songs.accentLabel')` and ending after the "Leave on Auto…" `<p>`). Keep the cut text open: the language and vocal-style `<option>`s are reused verbatim below.

(d) Directly after `<GenreTileGrid selGenres={selGenres} toggleGenre={toggleGenre} gLabel={gLabel} />` insert:

```jsx
            {!['meditation','healingfrequency'].some(g => selGenres.has(g)) && (
              <div style={{ marginBottom: 18 }}>
                <p className="zb-mini-label">{t('songs.accentLabel')}</p>
                <select
                  value={accent}
                  onChange={(e) => setAccent(e.target.value)}
                  style={/* the old select's style object, unchanged */}
                >
                  <option value="">None</option>
                  {ACCENT_GROUP_LABELS.map(([groupId, heading]) => (
                    <optgroup key={groupId} label={heading}>
                      {ACCENT_OPTIONS.filter(o => o.group === groupId).map(o => (
                        <option key={o.key} value={o.key}>{accentOptionLabel(o)}</option>
                      ))}
                    </optgroup>
                  ))}
                  <optgroup label="🌐 Sing in another language (lyrics in that language)">
                    {/* every <option> from the four old language optgroups (European, Asian,
                        African & Caribbean, Americas), in their existing order, values unchanged */}
                  </optgroup>
                  <optgroup label="🎙 Vocal Style">
                    {/* in this order, values unchanged:
                        the old "🎸 Rock & Blues" options (Classic Rock, Southern Rock, Blues Rock, Punk Rock),
                        the old "🎵 Vocal Style" options (Deep Bass Voice, Rapid Fire Rap),
                        the descriptor-array options (UK D&B MC, UK Jungle MC, Bashment MC, Jamaican Dancehall,
                          Vocoder / Talk Box, Cyborg / Synthesised, Punjabi, Spanish Latin, Puerto Rican, Cockney Grime),
                        then from the old name array: D&B MC, UK Rave MC, British MC Grime, Jazz Vocal,
                          American Hip-Hop, K-Pop, West African, American Phonk, New Jersey / Newark,
                          British African, Jamaican Rasta, West Coast G-Funk, British Street Soul,
                          Caribbean, American Soul */}
                  </optgroup>
                </select>
                <p style={{ fontSize: 11, color: '#cccccc', marginTop: 5 }}>Leave blank and Zeus uses the genre's natural accent.</p>
              </div>
            )}
```

The two `{/* … */}` blocks are filled by moving the existing JSX from (c) — not retyped. Dropped from the old lists (do not move): British, American (Southern), Southern American, Irish, Scottish, Australian, French (accent), Spanish (accent), Jamaican, Colombian, South African. For the old name array, render the kept names as `<option key={a} value={a}>{a}</option>` from a filtered array literal containing only the kept names.

(e) Locales — set `songs.accentLabel`: en `"🎤 Singer's Accent (optional)"`; every other locale: prefix its existing value with `"🎤 "` (e.g. de `"🎤 Akzent"`). Edit as UTF-8.

- [ ] **Step 4: Run to verify pass** — `node --test src/utils/accents.test.mjs` and `npm test` → all pass. Also run `npm run lint` on SongsPage: `npx eslint src/pages/SongsPage.jsx` → no new errors.

- [ ] **Step 5: Commit**

```bash
git add web-beats/src/pages/SongsPage.jsx web-beats/src/locales web-beats/src/utils/accents.test.mjs
git commit -m "feat(accent): grouped Singer's Accent picker after the genre grid"
```

---

### Task 6: Kids "Singer's Voice" picker

**Files:**
- Create: `web-beats/src/components/KidsVoicePicker.jsx`
- Modify: `web-beats/src/pages/SongsPage.jsx` (kids song section ~2836-2846; kids requestBody ~1074)
- Modify: `web-beats/src/pages/kids/KidsSongMode.jsx` (`ACCENTS` const ~30, picker ~144-152, request ~78)
- Test: `web-beats/src/utils/accents.test.mjs` (append)

**Interfaces:**
- Consumes: `ACCENT_OPTIONS`, `accentOptionLabel` (Task 4).
- Produces: `<KidsVoicePicker value onChange labelStyle selectProps />` — `onChange(key: string)`.

- [ ] **Step 1: Write failing tests** (append)

```js
const KIDS_PICKER = readFileSync(new URL('../components/KidsVoicePicker.jsx', import.meta.url), 'utf8');
const KIDS_SONG_MODE = readFileSync(new URL('../pages/kids/KidsSongMode.jsx', import.meta.url), 'utf8');

test('kids picker label and flag-first options', () => {
  assert.ok(KIDS_PICKER.includes("🎤 Singer's Voice"));
  assert.ok(KIDS_PICKER.includes('🌟 Default'));
  assert.match(KIDS_PICKER, /ACCENT_OPTIONS\.map/);
  assert.match(KIDS_PICKER, /accentOptionLabel\(/);
});

test('both kids song pickers use the shared component and send vocal_accent', () => {
  for (const [name, src] of [['SongsPage', SONGS_PAGE], ['KidsSongMode', KIDS_SONG_MODE]]) {
    assert.match(src, /<KidsVoicePicker/, `${name} must render KidsVoicePicker`);
    assert.ok(!src.includes('🎤 Singing Accent'), `${name} still has the old kids label`);
  }
  assert.match(KIDS_SONG_MODE, /vocal_accent: accent \|\| undefined/);
  assert.match(SONGS_PAGE, /vocal_accent: kidsSubMode === 'song' \? \(kidsAccent \|\| undefined\) : undefined/);
  // Story narrator still rides on `accent`.
  assert.match(SONGS_PAGE, /accent: kidsSubMode === 'story' \? \(kidsNarratorVoice \|\| undefined\) : undefined/);
});
```

- [ ] **Step 2: Run to verify failure** — FAIL (component file missing → readFileSync throws).

- [ ] **Step 3: Implement**

Create `web-beats/src/components/KidsVoicePicker.jsx`:

```jsx
import { ACCENT_OPTIONS, accentOptionLabel } from '../utils/genres';

// Kids song mode accent picker — shared by SongsPage's kids section and the /kids/song
// page so the two can't drift. Value is an ACCENT_OPTIONS key, sent as `vocal_accent`.
export default function KidsVoicePicker({ value, onChange, labelStyle, selectProps = {} }) {
  return (
    <>
      <p style={labelStyle}>🎤 Singer's Voice</p>
      <select value={value} onChange={(e) => onChange(e.target.value)} {...selectProps}>
        <option value="">🌟 Default</option>
        {ACCENT_OPTIONS.map((o) => (
          <option key={o.key} value={o.key}>{accentOptionLabel(o)}</option>
        ))}
      </select>
    </>
  );
}
```

SongsPage: add `import KidsVoicePicker from '../components/KidsVoicePicker';`. Replace the kids `<p …>🎤 Singing Accent</p>` + `<select value={kidsAccent} …>…</select>` with:

```jsx
                  <KidsVoicePicker
                    value={kidsAccent}
                    onChange={setKidsAccent}
                    labelStyle={/* the old <p>'s style object, unchanged */}
                    selectProps={{ style: /* the old <select>'s style object, unchanged */ }}
                  />
```

In the kids `requestBody`, replace the `accent:` line with:

```js
          accent: kidsSubMode === 'story' ? (kidsNarratorVoice || undefined) : undefined,
          vocal_accent: kidsSubMode === 'song' ? (kidsAccent || undefined) : undefined,
```

KidsSongMode.jsx: delete the `const ACCENTS = [...]` block; add `import KidsVoicePicker from '../../components/KidsVoicePicker';`; replace the `{/* Accent */}` `<p>` + `<select>` with:

```jsx
      <KidsVoicePicker
        value={accent}
        onChange={setAccent}
        labelStyle={{ fontWeight: 800, fontSize: 13, color: 'rgba(255,255,255,0.9)', textTransform: 'uppercase', letterSpacing: '0.5px', margin: '0 0 8px' }}
        selectProps={{ className: 'kids-select', style: { marginBottom: 22 } }}
      />
```

and in its request body change `accent: accent || undefined,` to `vocal_accent: accent || undefined,`.

- [ ] **Step 4: Run to verify pass** — `npm test` → all pass; `npx eslint src/components/KidsVoicePicker.jsx src/pages/kids/KidsSongMode.jsx src/pages/SongsPage.jsx` → no new errors.

- [ ] **Step 5: Commit**

```bash
git add web-beats/src/components/KidsVoicePicker.jsx web-beats/src/pages/SongsPage.jsx web-beats/src/pages/kids/KidsSongMode.jsx web-beats/src/utils/accents.test.mjs
git commit -m "feat(accent): shared kids Singer's Voice picker sending vocal_accent"
```

---

### Task 7: iOS picker + 3-way catalog guard

**Files:**
- Modify: `zeus-beats-ios/src/screens/CreateSongScreen.tsx` — constants after `GENRE_LABEL` (~60-110), state (~117), request body (~166), UI between genre categories and `{/* ── Vocal mode */}` (~443), styles
- Create: `backend/tests/test_accent_catalog_sync.py`

**Interfaces:**
- Consumes: backend `ACCENT_STYLE_MAP`/`ACCENT_GROUPS` (Task 1), web `ACCENT_OPTIONS` (Task 4).

- [ ] **Step 1: Write failing guard test** — create `backend/tests/test_accent_catalog_sync.py`:

```python
"""3-way guard: backend ACCENT_STYLE_MAP/ACCENT_GROUPS == web ACCENT_OPTIONS == iOS
ACCENT_OPTIONS (keys AND groups). Text-scan, like the genre catalog guards."""
import pathlib
import re
import sys

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))
ROOT = pathlib.Path(__file__).resolve().parents[2]
_ENTRY = re.compile(r"\{\s*key:\s*'([a-z_]+)'[^}]*?group:\s*'([a-z_]+)'")


def _client(rel):
    src = (ROOT / rel).read_text(encoding="utf-8")
    m = re.search(r"ACCENT_OPTIONS[^=]*=\s*\[([\s\S]*?)\n\];", src)
    assert m, f"ACCENT_OPTIONS not found in {rel}"
    pairs = _ENTRY.findall(m.group(1))
    assert len(pairs) >= 20, f"parser matched too few entries in {rel}"
    return pairs


def _backend():
    from song_genres import ACCENT_GROUPS
    return [(k, g) for g, ks in ACCENT_GROUPS for k in ks]


def test_web_matches_backend():
    assert _client("web-beats/src/utils/genres.js") == _backend()


def test_ios_matches_backend():
    assert _client("zeus-beats-ios/src/screens/CreateSongScreen.tsx") == _backend()


def test_ios_sends_vocal_accent():
    src = (ROOT / "zeus-beats-ios/src/screens/CreateSongScreen.tsx").read_text(encoding="utf-8")
    assert re.search(r"vocal_accent:\s+accent \|\| undefined", src)
    assert "🎤 Singer's Accent (optional)" in src
```

- [ ] **Step 2: Run to verify failure** — `<env> py -m pytest tests/test_accent_catalog_sync.py -q` → web passes, iOS tests FAIL (`ACCENT_OPTIONS not found`).

- [ ] **Step 3: Implement in `CreateSongScreen.tsx`**

After the `GENRE_LABEL` object, add (same 29 entries as web, TS-typed):

```tsx
// ─── Singer's accent (mirrors backend ACCENT_STYLE_MAP + web genres.js; guarded by
// backend/tests/test_accent_catalog_sync.py) ─────────────────────────────────

interface AccentOption { key: string; label: string; flag: string; group: string }

const ACCENT_GROUP_LABELS: [string, string][] = [
  ['british_isles', '🇬🇧🇮🇪 British Isles & Ireland'],
  ['americas',      '🌎 Americas'],
  ['africa',        '🌍 Africa'],
  ['europe',        '🇪🇺 Europe'],
  ['asia',          '🌏 Middle East & Asia'],
  ['pacific',       '🌊 Pacific'],
];

const ACCENT_OPTIONS: AccentOption[] = [
  { key: 'english_london',     label: 'London',               flag: '🇬🇧', group: 'british_isles' },
  { key: 'english_northern',   label: 'Northern English',     flag: '🇬🇧', group: 'british_isles' },
  { key: 'scottish',           label: 'Scottish',             flag: '🏴󠁧󠁢󠁳󠁣󠁴󠁿', group: 'british_isles' },
  { key: 'welsh',              label: 'Welsh',                flag: '🏴󠁧󠁢󠁷󠁬󠁳󠁿', group: 'british_isles' },
  { key: 'irish',              label: 'Irish',                flag: '🇮🇪', group: 'british_isles' },
  { key: 'american_southern',  label: 'Southern American',    flag: '🇺🇸', group: 'americas' },
  { key: 'american_newyork',   label: 'New York',             flag: '🇺🇸', group: 'americas' },
  { key: 'american_westcoast', label: 'West Coast American',  flag: '🇺🇸', group: 'americas' },
  { key: 'jamaican',           label: 'Jamaican',             flag: '🇯🇲', group: 'americas' },
  { key: 'brazilian',          label: 'Brazilian',            flag: '🇧🇷', group: 'americas' },
  { key: 'mexican',            label: 'Mexican',              flag: '🇲🇽', group: 'americas' },
  { key: 'colombian',          label: 'Colombian',            flag: '🇨🇴', group: 'americas' },
  { key: 'nigerian',           label: 'Nigerian',             flag: '🇳🇬', group: 'africa' },
  { key: 'ghanaian',           label: 'Ghanaian',             flag: '🇬🇭', group: 'africa' },
  { key: 'south_african',      label: 'South African',        flag: '🇿🇦', group: 'africa' },
  { key: 'kenyan',             label: 'Kenyan',               flag: '🇰🇪', group: 'africa' },
  { key: 'senegalese',         label: 'Senegalese',           flag: '🇸🇳', group: 'africa' },
  { key: 'french',             label: 'French',               flag: '🇫🇷', group: 'europe' },
  { key: 'spanish',            label: 'Spanish',              flag: '🇪🇸', group: 'europe' },
  { key: 'italian',            label: 'Italian',              flag: '🇮🇹', group: 'europe' },
  { key: 'german',             label: 'German',               flag: '🇩🇪', group: 'europe' },
  { key: 'portuguese',         label: 'Portuguese',           flag: '🇵🇹', group: 'europe' },
  { key: 'indian',             label: 'Indian',               flag: '🇮🇳', group: 'asia' },
  { key: 'pakistani',          label: 'Pakistani',            flag: '🇵🇰', group: 'asia' },
  { key: 'arabic',             label: 'Arabic',               flag: '🇸🇦', group: 'asia' },
  { key: 'japanese',           label: 'Japanese',             flag: '🇯🇵', group: 'asia' },
  { key: 'korean',             label: 'Korean',               flag: '🇰🇷', group: 'asia' },
  { key: 'australian',         label: 'Australian',           flag: '🇦🇺', group: 'pacific' },
  { key: 'newzealand',         label: 'New Zealand',          flag: '🇳🇿', group: 'pacific' },
];
```

State, next to `vocalMode`:

```tsx
  const [accent,       setAccent]       = useState<string>('');
  const [accentOpen,   setAccentOpen]   = useState(false);
```

Request body, after `genres: [genre],`:

```tsx
          vocal_accent:        accent || undefined,
```

UI, directly before `{/* ── Vocal mode ── */}` — a collapsible row (no new dependency; same TouchableOpacity/chip idiom as the vocal-mode chips):

```tsx
              {/* ── Singer's accent ─────────────────────────────────────── */}
              <Text style={[s.sectionLabel, { marginTop: 24 }]}>🎤 Singer's Accent (optional)</Text>
              <TouchableOpacity style={s.accentRow} onPress={() => setAccentOpen(o => !o)}>
                <Text style={s.accentRowText}>
                  {accent
                    ? (() => { const o = ACCENT_OPTIONS.find(x => x.key === accent); return o ? `${o.flag} ${o.label}` : 'None'; })()
                    : 'None'}
                </Text>
                <Text style={s.accentRowText}>{accentOpen ? '▲' : '▼'}</Text>
              </TouchableOpacity>
              {accentOpen && (
                <View style={s.accentPanel}>
                  <TouchableOpacity
                    style={[s.vocalChip, !accent && s.vocalChipActive, { alignSelf: 'flex-start', marginBottom: 8 }]}
                    onPress={() => { setAccent(''); setAccentOpen(false); }}
                  >
                    <Text style={[s.vocalChipText, !accent && s.vocalChipTextActive]}>None</Text>
                  </TouchableOpacity>
                  {ACCENT_GROUP_LABELS.map(([groupId, heading]) => (
                    <View key={groupId} style={{ marginBottom: 10 }}>
                      <Text style={s.accentGroupHeading}>{heading}</Text>
                      <View style={s.accentChipWrap}>
                        {ACCENT_OPTIONS.filter(o => o.group === groupId).map(o => {
                          const active = accent === o.key;
                          return (
                            <TouchableOpacity
                              key={o.key}
                              style={[s.vocalChip, active && s.vocalChipActive]}
                              onPress={() => { setAccent(o.key); setAccentOpen(false); }}
                            >
                              <Text style={[s.vocalChipText, active && s.vocalChipTextActive]}>{`${o.flag} ${o.label}`}</Text>
                            </TouchableOpacity>
                          );
                        })}
                      </View>
                    </View>
                  ))}
                </View>
              )}
```

Styles — add to the `StyleSheet.create` object (reuse existing colours from `vocalChip`):

```tsx
  accentRow:          { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center',
                        borderWidth: 1, borderColor: 'rgba(255,255,255,0.15)', borderRadius: 10,
                        paddingVertical: 12, paddingHorizontal: 14 },
  accentRowText:      { color: '#fff', fontSize: 14 },
  accentPanel:        { marginTop: 10 },
  accentGroupHeading: { color: 'rgba(255,255,255,0.6)', fontSize: 12, fontWeight: '700', marginBottom: 6 },
  accentChipWrap:     { flexDirection: 'row', flexWrap: 'wrap', gap: 8 },
```

- [ ] **Step 4: Run to verify pass**

- `<env> py -m pytest tests/test_accent_catalog_sync.py -q` → 3 passed.
- Type-check: junction the main checkout's `node_modules` into the worktree (`cmd //c mklink /J zeus-beats-ios\node_modules C:\Users\Student\zeus-app\zeus-beats-ios\node_modules`), run `cd zeus-beats-ios && npx tsc --noEmit`, compare error count to the same command on unmodified master (pre-existing errors allowed; zero NEW errors in CreateSongScreen.tsx). Remove the junction with `cmd //c rmdir zeus-beats-ios\node_modules` (rmdir on a junction does not touch the target).

- [ ] **Step 5: Commit**

```bash
git add zeus-beats-ios/src/screens/CreateSongScreen.tsx backend/tests/test_accent_catalog_sync.py
git commit -m "feat(accent): iOS Singer's Accent picker + 3-way catalog guard"
```

---

### Task 8: Whole-branch verification

**Files:** none modified (fixes found here go back to the owning task's files).

- [ ] **Step 1:** Full backend suite: `cd backend && <env> py -m pytest tests -q` → 0 failed (baseline is fully green; any failure is a regression).
- [ ] **Step 2:** `cd web-beats && npm test` → 0 failed.
- [ ] **Step 3:** Production build: junction `web-beats/node_modules` as in Task 7, `npm run build` → exit 0; remove junction.
- [ ] **Step 4:** Visual check: `npm run dev` with the junction, open the Create page in the browser at phone width (390px) and desktop; confirm the picker sits under the genre grid, the three sections render, the hint text shows, and choosing meditation hides it. Open kids mode → "🎤 Singer's Voice" with flags. Screenshot both. Do NOT press Create (no paid generation).
- [ ] **Step 5:** Report results to the user; wait for their go before merging to master / deploying. iOS reaches users only via the next App Store build.
