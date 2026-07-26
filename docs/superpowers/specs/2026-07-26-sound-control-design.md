# Sound Control — Design Spec

**Date:** 2026-07-26
**Scope:** web-beats song creator (`zeusbeats.com`) only. `web/` (Zeus AI Design) is **not** touched.
**Status:** For review.

## 1. Summary

Add a collapsible **🎛️ Sound Control** block to the Advanced area of the web-beats song
creator. It offers descriptive control over Bass, Drums, Vocals, and Production via
preset dropdowns (each with a "Custom…" free-text option) plus a general
"Custom sound notes" box. Selected values are turned into Suno-optimised descriptor
phrases and appended to the style string as the **lowest-priority** additions, so they
never crowd out the genre core or the functionally-important accent/vocal-mode cues.

Bundled with it: a **surgical upgrade** to the existing style-suffix trimming so that,
when the assembled style exceeds budget, it drops **whole descriptors lowest-priority-first**
and **logs exactly which descriptors were dropped** — replacing today's crude character-level
cut. This improves truncation observability for rapid-fire, intermittent vocals, **and**
sound-control alike.

## 2. Context — how style assembly works today

- Endpoint: `POST /api/songs/generate` (`backend/main.py:2202`).
- The endpoint accumulates advanced descriptors into an ordered list `style_suffix_parts`
  (accent → explicit → instrumental → intermittent → healing), then joins them into
  `tempo_suffix` (`main.py:2822`).
- **Apiframe (primary) path:** `main.py` passes `tempo_suffix` into
  `songs.generate_multiple_variants` (`songs.py:541`), which combines it with the genre
  core **per variant** at `songs.py:614–648`. That code already:
  - Uses a **990-char** budget (`hard_cap = 990`) — deliberately *not* 500. The comment at
    `songs.py:617–620` records that the old 500 caused the rapid-fire and intermittent
    truncation bugs; 990 (under Apiframe's ~1000 field limit) fixed them.
  - Treats the **genre core as sacred** — prepends the suffix (Suno weights front text
    first) and, when over budget, trims the **suffix**, never the genre identity.
  - Char-trims the suffix (`suffix[:budget].rstrip(" ,")`) and logs a warning that does
    **not** name what was lost.
  - Applies a final hard-truncate safety net (`songs.py:642–647`).
- **Persona path (CometAPI):** a separate branch (`main.py:2833–2900`) builds
  `_p_style = f"{_p_style}, {tempo_suffix}"` and submits via `cometapi` (`tags[:200]`).
  This path does **not** use `generate_multiple_variants`.

**Key correction vs. the initial idea:** there is no "naive join" to replace. The
effective live limit is **~990 (Apiframe)**, not 500. The 500 (`_submit_to_goapi`,
`songs.py:362`) and 200 (CometAPI) are downstream provider submit caps on secondary
paths. Rapid-fire and intermittent are already protected by the existing 990 logic; this
spec **must not regress** that.

## 3. Frontend design (`web-beats/src/pages/SongsPage.jsx`)

### 3.1 Placement & collapse behaviour
- A nested collapsible **🎛️ Sound Control** section inside the existing Advanced panel
  (`showAdvanced`, state around `SongsPage.jsx:1217`).
- Own toggle `showSoundControl`, **collapsed by default** — even when Advanced is open,
  Sound Control stays closed until deliberately expanded. Casual users never see it;
  power users opt in. Toggle is a full-width 44px row with a chevron.

### 3.2 Controls
Four rows + one textarea, each row full-width and stacking cleanly at 375px:

| Control | Widget |
|---|---|
| Bass | native `<select>` (8 presets + "Custom…") → selecting Custom reveals a text `<input>` |
| Drums | same pattern (8 presets + Custom) |
| Vocals | same pattern (8 presets + Custom) |
| Production | same pattern (6 presets + Custom) |
| Custom sound notes | always-visible `<textarea>` |

- Native `<select>`/`<input>` give free 44px+ tap targets and native mobile pickers.
- All label/option/input text forced white, reusing the Advanced-panel `!important`
  text-legibility fix (`SongsPage.jsx:117`). No `#555` greys.
- Each section is **optional** — default is unset (no dropdown selection, empty custom).

### 3.3 State & request shape
- State object:
  `soundControl = { bass, bassCustom, drums, drumsCustom, vocals, vocalsCustom, production, productionCustom, notes }`.
- Per section, the **resolved value** = custom text if the dropdown is set to "Custom",
  else the selected preset label (or "" if unset).
- Included in the generate request body **only when `showAdvanced`** (consistent with the
  other advanced fields), as:
  ```js
  sound_control: {
    bass:       <resolved or "">,
    drums:      <resolved or "">,
    vocals:     <resolved or "">,
    production: <resolved or "">,
    notes:      <notes text or "">,
  }
  ```
  Omitted entirely if every field is empty.

## 4. Backend — phrase map & wiring

### 4.1 `SOUND_CONTROL_PHRASES` (new, in `backend/song_genres.py`)
Server-side so Suno phrasing can be tuned without a frontend rebuild — same rationale as
`GENRE_PRESETS`. Keyed by section, then by the exact frontend label. **Full 30-preset map:**

```python
SOUND_CONTROL_PHRASES = {
    "bass": {
        "Sub Bass":         "deep sub bass",
        "808":              "heavy 808 bass",
        "Reese Bass":       "growling reese bass",
        "Slap Bass":        "funky slap bass",
        "Upright/Acoustic": "warm upright acoustic bass",
        "Wobble Bass":      "wobbling dubstep bass",
        "Deep Bass":        "deep resonant bass",
        "Distorted Bass":   "gritty distorted bass",
    },
    "drums": {
        "Punchy":            "punchy hard-hitting drums",
        "Lo-fi":             "lo-fi dusty drums",
        "Trap Hi-hats":      "rapid rolling trap hi-hats",
        "Acoustic Kit":      "live acoustic drum kit",
        "Four-to-the-floor": "steady four-on-the-floor kick drums",
        "Breakbeat":         "chopped breakbeat drums",
        "Minimal":           "sparse minimal percussion",
        "Hard-hitting":      "hard-hitting punchy drums",
    },
    "vocals": {
        "Soft":               "soft gentle vocals",
        "Powerful":           "powerful belting vocals",
        "Layered":            "lush layered vocal harmonies",
        "Choppy/Chopped":     "chopped stuttering vocals",
        "Breathy":            "soft breathy vocals",
        "Aggressive":         "aggressive intense vocals",
        "Auto-tuned":         "melodic auto-tune vocals",
        "None/Instrumental":  "instrumental, no lead vocals",  # SPECIAL — see §4.4: sets the real instrumental=True param instead of appending this text
    },
    "production": {
        "Polished":      "polished radio-ready production",
        "Lo-fi":         "lo-fi vintage production",
        "Vintage":       "warm vintage analog production",
        "Cinematic":     "cinematic layered production",
        "Stripped-back": "stripped-back minimal production",
        "Wall-of-sound": "dense wall-of-sound production",
    },
}
```
- Frontend labels must match these keys exactly (single source list documented alongside).
- **Custom text & notes are appended verbatim** — resolution rule per section:
  `phrase = SOUND_CONTROL_PHRASES[section].get(value, value.strip())`. A known label maps
  to its curated phrase; anything else (a custom entry) passes through unchanged.
- `notes` is always verbatim (never mapped).
- **No artist/place names** in any preset phrase — pure descriptive production language,
  same principle as `GENRE_PRESETS`.

### 4.2 Request model (`main.py`, the `/api/songs/generate` body model ~`main.py:2050–2080`)
Add:
```python
sound_control: dict | None = None
```
Validation: each of `bass/drums/vocals/production/notes` is coerced to a stripped string;
each capped at **200 chars** (`notes` at **300**) to bound abuse; empty values ignored.

### 4.3 Appending sound-control to the suffix (`main.py`, after healing block ~`2821`)
```python
if body.sound_control:
    for section in ("bass", "drums", "vocals", "production"):
        val = (body.sound_control.get(section) or "").strip()[:200]
        if section == "vocals" and val == "None/Instrumental":
            continue  # handled as the instrumental flag in §4.4; INSTRUMENTAL_SUFFIX supplies the text
        if val:
            style_suffix_parts.append(SOUND_CONTROL_PHRASES.get(section, {}).get(val, val))
    notes = (body.sound_control.get("notes") or "").strip()[:300]
    if notes:
        style_suffix_parts.append(notes)
```
Because these are appended **last**, they sit at the **end** of the prepended suffix
(adjacent to the sacred genre core) and are the **first** parts dropped under budget.
Existing parts are **not reordered** — relative priority of accent/explicit/instrumental/
intermittent/healing is preserved exactly.

`tempo_suffix = ", ".join(style_suffix_parts)` is still computed unchanged for the persona
path and logging.

### 4.4 Vocals "None/Instrumental" → real instrumental param
A text descriptor alone is weaker than the actual Suno `instrumental` flag (the instrument
genres taught us the flag is what reliably works). So Vocals = "None/Instrumental" drives
the **real** param, with a single source of truth to prevent conflicting submit state.

**Backend is authoritative.** Near the top of the handler, **before** the existing
instrumental block (`main.py:2796`) and intermittent block (`2801`):
```python
_sc = body.sound_control or {}
if (_sc.get("vocals") or "").strip() == "None/Instrumental":
    body.instrumental = True   # OR-in: never turns instrumental OFF, only ON
```
Consequences, all via **existing** logic (no new conflict handling needed):
- `INSTRUMENTAL_SUFFIX` is appended (`main.py:2799-2800`) — that supplies the instrumental
  text, so §4.3 skips re-appending the vocals descriptor (no duplication).
- `instrumental` reaches `extra_suno_params` (`main.py`) and the Suno param is set.
- Intermittent is auto-disabled by the pre-existing guards
  (`if body.intermittent_vocals and not body.instrumental` at `2801`, and
  `intermittent_vocals=bool(body.intermittent_vocals and not body.instrumental)` at `2925`).
  **Instrumental wins over intermittent** — the correct resolution when a user asks for no
  vocals.

**Frontend** sends the raw `"None/Instrumental"` label as-is; it does **not** mutate the
Vocal-mode toggle state (avoids fragile two-way binding). Because the backend OR-in is the
sole authority for the submitted flag, the displayed Vocal-mode toggle and this selection
**cannot produce a conflicting submit**. A short hint — *"(makes the track instrumental)"* —
is shown next to the option so the effect is obvious.

## 5. Trim upgrade (surgical) — `songs.py:614–648`

### 5.1 Goal
Replace the character-level suffix cut with **whole-descriptor, lowest-priority-first**
dropping, and a warning that **names the dropped descriptors**. Preserve **byte-identical
output for the common (<990) case**, which is nearly all real requests.

### 5.2 Interface change
- `generate_multiple_variants` gains `suffix_parts: list[str] | None = None`.
- `main.py` passes `suffix_parts=style_suffix_parts` (the ordered list) alongside the
  existing `tempo_suffix` string.
- When `suffix_parts` is provided, the new whole-descriptor path is used. When it is
  `None` (any other caller), behaviour falls back to today's exact code using
  `tempo_suffix`. This keeps non-endpoint callers unchanged.

### 5.3 Algorithm (applied per variant, after genre core `style` and `tail` are built)
```
budget = hard_cap - len(genre_core) - len(tail) - 2      # same budget math as today
joined = ", ".join(suffix_parts)

if not suffix_parts:
    style = f"{genre_core}{tail}"                          # unchanged
elif len(joined) <= max(0, budget):
    style = f"{joined}, {genre_core}{tail}"                # COMMON CASE: identical to today
else:
    kept = list(suffix_parts)
    dropped = []
    while kept and len(", ".join(kept)) > max(0, budget):
        dropped.append(kept.pop())                         # drop from END = lowest priority
    logger.warning(
        "style: over budget for genre=%r — dropped %d suffix descriptor(s) "
        "lowest-priority-first: %r (genre core protected)",
        genre, len(dropped), list(reversed(dropped)),
    )
    style = f'{", ".join(kept)}, {genre_core}{tail}' if kept else f"{genre_core}{tail}"

# Final safety net (genre core + tail alone exceeding cap) — UNCHANGED (songs.py:642-647)
if len(style) > hard_cap:
    logger.warning("style string hard-truncated from %d to %d chars for genre=%r blend=%s", ...)
    style = style[:hard_cap]
```

### 5.4 Invariants (must hold)
- **Genre core is never trimmed by the suffix logic** — only the final safety net can cut
  it, and only when genre core + tail alone exceed the cap (exactly as today).
- **`hard_cap` stays 990** — no regression to 500 on the Apiframe path.
- **Common case is byte-identical** to today's output (`", ".join(parts)` == old
  `tempo_suffix`; same budget math; trim only triggers when over budget).
- **Existing part order unchanged** — accent stays highest, sound-control lowest.

## 6. Testing (`backend/tests/test_style_assembly.py`, new)

The trim logic will be factored into a small pure helper (e.g.
`_assemble_variant_style(genre_core, suffix_parts, tail, hard_cap=990)`) so it is unit-testable
without HTTP or DB.

1. **Common case identical:** parts that fit → output equals `", ".join(parts) + ", " +
   genre_core + tail`; **no** warning emitted.
2. **Genre core sacred:** a genre core that alone approaches/exceeds 990 is never shortened
   by the suffix path; suffix is fully dropped first; only the final safety net may cut a
   genre-core-only overflow (matching current behaviour).
3. **Lowest-priority-first drop:** with an over-budget mix `[accent, …, sound1, sound2]`,
   `sound2` then `sound1` drop **before** `accent`; kept parts stay in original order.
4. **Warning names descriptors:** the emitted warning lists exactly the dropped phrases,
   in priority order.
5. **Rapid-fire not regressed:** concise rapid-fire accent (~75 chars, `main.py:2784`) +
   typical genre core assembles unchanged; accent survives; no warning.
6. **Intermittent not regressed:** `INTERMITTENT_VOCALS_SUFFIX` present in `suffix_parts`
   under budget → appears in output unchanged; over budget → sound-control drops before
   the intermittent cue (intermittent is higher priority).
7. **Empty sound_control:** output identical to pre-feature (no trailing parts, no warning).
8. **Phrase mapping:** known labels map to curated phrases; custom/notes pass through
   verbatim; unknown label falls through to verbatim.
9. **"None/Instrumental" wiring:** vocals = "None/Instrumental" sets `instrumental=True`;
   does **not** append a duplicate vocals descriptor (INSTRUMENTAL_SUFFIX supplies text);
   disables intermittent when both are requested (instrumental wins); OR-in never turns an
   already-instrumental request OFF.

Manual: 375px visual pass of the collapsed/expanded panel (white text, 44px targets),
per the "verify by pixels" note.

## 7. Out of scope / known limitations

- **Persona (CometAPI) path:** sound-control is appended via the unchanged `tempo_suffix`
  and remains subject to CometAPI's existing `tags[:200]` submit truncation — it is **not**
  priority-trimmed there. Acceptable: persona is a minor path and the whole-descriptor
  upgrade is scoped to the Apiframe assembly in `generate_multiple_variants`.
- **GoAPI fallback:** its `tags[:500]` submit cap (`songs.py:362`) is a pre-existing
  downstream cut, unchanged by this work.
- **Vocals "None/Instrumental"** sets the real Suno `instrumental` param (§4.4), not just a
  descriptor. Backend OR-in is the single source of truth, so it cannot conflict with the
  existing Vocal-mode toggle; instrumental wins over intermittent.
- `web/` frontend: not modified.

## 8. Files touched

| File | Change |
|---|---|
| `web-beats/src/pages/SongsPage.jsx` | Sound Control collapsible UI, state, request field |
| `backend/song_genres.py` | `SOUND_CONTROL_PHRASES` map |
| `backend/main.py` | request-model field, validation, append sound-control to `style_suffix_parts`, pass `suffix_parts` to `generate_multiple_variants` |
| `backend/songs.py` | `suffix_parts` param + whole-descriptor trim upgrade (behind the fallback) |
| `backend/tests/test_style_assembly.py` | new unit tests |
