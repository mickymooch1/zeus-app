# Vocal Accent Picker — Design

Date: 2026-10-13 · Status: approved in brainstorming, awaiting spec review

## Goal

Let a Zeus Beats user pick the singer's accent from one clear, grouped list in
the Create flow (web + iOS), and make genres with an obvious home accent (grime,
ragga, country, the Irish genres…) sing in it by default — with the user's
explicit choice always winning.

## Context: what exists today

- `SongsGenerateRequest.accent` (main.py) is already sent by the web adult Create
  flow, roast mode, both web kids song pickers, and kids Story mode (as the
  narrator-voice key). In regular mode it becomes a descriptor from
  `_ACCENT_DESCRIPTORS` (main.py ~3292, marked "DO NOT MODIFY") added to
  `style_suffix_parts`, which `songs.py` places BEFORE each genre's preset
  (Suno weights the front; end-appended accents lose to preset cues).
- `lyrics.py` also reads `accent`: language options switch the lyric language
  (`_REGULAR_LANGUAGE_MAP`), and "rapid-fire rap" restructures the lyrics.
- The web adult dropdown (inside the collapsed Advanced panel) mixes ~70 options:
  plain accents, scene/MC voices, vocal styles, and "sing in language X".
  Its "Auto (matches your genre)" default has no logic behind it.
- iOS `CreateSongScreen.tsx` has no accent picker.

## Decisions (from brainstorming)

1. ONE adult picker, reorganised into three groups: **accents** (the new 29),
   **languages**, **vocal styles**. Not a second dropdown.
2. Languages and vocal styles are kept unchanged and keep sending legacy `accent`.
3. Both web kids song pickers switch to the 29 accents, labelled "🎤 Singer's Voice".
4. Genre defaults live in a separate dict (option A), not edited into presets.
5. `outlawcountry` ("Dark Outlaw Country") gets "dark and gritty drawl";
   `outlawcountryrap` gets no default.

## 1. Backend

### song_genres.py

`ACCENT_STYLE_MAP: dict[str, str]` — exactly these 29 keys and snippets:

| Group | key → snippet |
|---|---|
| British Isles & Ireland | `english_london` → "authentic London British vocals, Cockney or South London accent" · `english_northern` → "Northern English vocals, Manchester or Leeds accent, gritty and warm" · `scottish` → "Scottish accent vocals, Edinburgh or Glasgow lilt" · `welsh` → "Welsh accent vocals, melodic lilting tone" · `irish` → "Irish accent vocals, lilting Dublin or Cork delivery" |
| Americas | `american_southern` → "Southern American accent, country twang, warm drawl" · `american_newyork` → "New York accent vocals, sharp and urban" · `american_westcoast` → "West Coast American vocals, laid back California delivery" · `jamaican` → "Jamaican patois vocals, dancehall delivery, island lilt" · `brazilian` → "Brazilian Portuguese vocals, warm samba inflection" · `mexican` → "Mexican Spanish vocals, warm ranchera delivery" · `colombian` → "Colombian Spanish vocals, coastal Caribbean lilt" |
| Africa | `nigerian` → "Nigerian vocal style, Afrobeats inflection, Lagos energy" · `ghanaian` → "Ghanaian vocals, highlife warmth, Accra tone" · `south_african` → "South African vocals, township energy, Joburg delivery" · `kenyan` → "Kenyan vocals, East African lilt, Nairobi style" · `senegalese` → "Senegalese vocals, West African griot warmth" |
| Europe | `french` → "French accent vocals, Parisian delivery, romantic tone" · `spanish` → "Spanish accent vocals, Castilian delivery" · `italian` → "Italian accent vocals, operatic warmth, Mediterranean tone" · `german` → "German accent vocals, precise and powerful delivery" · `portuguese` → "Portuguese vocals, Lisbon fado-tinged delivery" |
| Middle East & Asia | `indian` → "Indian accent vocals, Bollywood warmth, Hindi film style" · `pakistani` → "Pakistani vocals, Lahori delivery, qawwali warmth" · `arabic` → "Arabic accent vocals, Middle Eastern melodic delivery" · `japanese` → "Japanese accent vocals, precise and melodic J-pop delivery" · `korean` → "Korean accent vocals, K-pop clean and precise delivery" |
| Pacific | `australian` → "Australian accent vocals, laid back Aussie delivery" · `newzealand` → "New Zealand accent vocals, warm Kiwi tone" |

The brief said 30; its list has 29. 29 is the spec.

`ACCENT_GROUPS: list[tuple[str, list[str]]]` — the six groups above, in that
order; every key appears in exactly one group.

`GENRE_DEFAULT_ACCENT: dict[str, str]` — 12 genres (the brief's 13 lines, with
two naming the same genre):

| genre | default snippet |
|---|---|
| grime | authentic London British MC vocals, South London accent |
| ukdrill | London drill vocals, South London accent |
| irishrebel | Irish accent vocals, Dublin delivery |
| irishballad | Irish accent vocals, lilting emotional delivery |
| irishtradtechno | Irish accent gang vocals |
| ragga | Jamaican patois vocals, dancehall delivery |
| rootsreggae | Jamaican vocals, roots delivery |
| country | Southern American accent, country twang |
| countrysoul | Southern American vocals, warm soul drawl |
| outlawcountry | Southern American accent, dark and gritty drawl |
| countryrap | Southern American accent, country rap drawl |
| countryballad | Southern American accent, emotional country delivery |

(The brief's `outlaw_country` and `darkoutlawcountry` are the same genre,
`outlawcountry`.) Every key must exist in `GENRE_PRESETS`. `GENRE_PRESETS`
strings are NOT edited.

### main.py — request

- `SongsGenerateRequest.vocal_accent: str | None = Field(default=None, max_length=40)`.
- Unknown key → ignored, logged (`accent: unknown vocal_accent=%r ignored`); never
  a 422 (an old/new app build mismatch must still produce a song).
- A valid `vocal_accent` appends `ACCENT_STYLE_MAP[key]` to `style_suffix_parts`
  (same position every accent uses today).
- If `vocal_accent` is valid, the legacy regular-mode accent STYLE block is
  skipped (guard condition only; the block's body is untouched). `accent` is
  still passed to `generate_lyrics`, so a language/rapid-fire choice keeps
  driving the lyrics. The UI never sends both; this only defines the API edge.
- Kids Story narrator handling of `accent` is unchanged.

### songs.py — genre defaults

The variant builder gets one new parameter, `use_genre_default_accent: bool`
(default False, so other callers such as zeus_agent are unchanged). main.py passes
True unless any of these hold:

- an explicit accent: valid `vocal_accent`, or any legacy `accent`
  (a language or vocal-style choice also overrides the default)
- `instrumental` or `intermittent_vocals`
- kids Story mode

When True, for each variant whose genre is in `GENRE_DEFAULT_ACCENT`, the default
snippet is appended to that variant's genre style (end of the genre core, so the
length-trim protects it like the rest of the genre identity). In a blend it is the
variant's own genre's default. Genres without a default: byte-identical output.

## 2. Frontend

### Shared catalog — 3-way guard

`web-beats/src/utils/genres.js` exports `ACCENT_OPTIONS` (29 × `{key, label, flag,
group}`) and `ACCENT_GROUP_LABELS`; `CreateSongScreen.tsx` carries the identical
list. The existing 3-way genre guard test is extended: backend `ACCENT_STYLE_MAP`
keys, genres.js keys, iOS keys, and per-key groups must all match.

Labels / flags: London 🇬🇧, Northern English 🇬🇧, Scottish 🏴󠁧󠁢󠁳󠁣󠁴󠁿, Welsh 🏴󠁧󠁢󠁷󠁬󠁳󠁿,
Irish 🇮🇪, Southern American 🇺🇸, New York 🇺🇸, West Coast American 🇺🇸,
Jamaican 🇯🇲, Brazilian 🇧🇷, Mexican 🇲🇽, Colombian 🇨🇴, Nigerian 🇳🇬, Ghanaian 🇬🇭,
South African 🇿🇦, Kenyan 🇰🇪, Senegalese 🇸🇳, French 🇫🇷, Spanish 🇪🇸, Italian 🇮🇹,
German 🇩🇪, Portuguese 🇵🇹, Indian 🇮🇳, Pakistani 🇵🇰, Arabic 🇸🇦, Japanese 🇯🇵,
Korean 🇰🇷, Australian 🇦🇺, New Zealand 🇳🇿. The Scotland/Wales subdivision flags
render as a plain black flag on Windows and many Android devices; the text label
always sits beside the flag, so the option stays readable.

Group headings: "🇬🇧🇮🇪 British Isles & Ireland" (not just 🇬🇧 — Irish lives here),
"🌎 Americas", "🌍 Africa", "🇪🇺 Europe", "🌏 Middle East & Asia", "🌊 Pacific".

### Web adult Create flow (SongsPage.jsx)

- The dropdown moves out of the collapsed Advanced panel to directly after the
  genre tile grid. Still hidden when meditation/healingfrequency is selected.
- Label "🎤 Singer's Accent (optional)"; first option "None" (blank).
- Options, three sections:
  1. **Accents** — the six region groups, 29 options, value = accent key.
  2. **🌐 Sing in another language** — the existing ~32 language options, values
     unchanged (French … Brazilian Portuguese).
  3. **🎙 Vocal Style** — every existing scene-voice / style option, values
     unchanged: Classic Rock, Southern Rock, Blues Rock, Punk Rock, Deep Bass
     Voice, Rapid Fire Rap, Vocoder / Talk Box, Cyborg / Synthesised, D&B MC,
     UK D&B MC, UK Rave MC, UK Jungle MC, British MC Grime, Cockney Grime,
     Bashment MC, Jamaican Dancehall, Jamaican Rasta, Caribbean, American Soul,
     Jazz Vocal, American Hip-Hop, American Phonk, West Coast G-Funk,
     New Jersey / Newark, K-Pop, West African, British African,
     British Street Soul, Punjabi, Spanish Latin, Puerto Rican.
- Removed (plain accents the 29 now cover): British, American (Southern),
  Southern American, Irish, Scottish, Australian, French (accent), Spanish
  (accent), Jamaican, Colombian, South African.
- One state value. On submit (standard AND roast branches): a key in
  `ACCENT_OPTIONS` → `vocal_accent`; anything else → `accent`; blank → neither.
  A small pure helper `accentPayload(value)` does this routing.
- Hint text: "Leave blank and Zeus uses the genre's natural accent."

### Web kids mode

A shared `KidsVoicePicker` component, used by SongsPage's kids song section and
`pages/kids/KidsSongMode.jsx`: label "🎤 Singer's Voice", first option
"🌟 Default", then the 29 accents flag-first (e.g. "🇯🇲 Jamaican"), sends
`vocal_accent`. The old 9-option kids list (incl. Caribbean, American Soul) is
replaced. Kids Story narrator picker untouched.

### iOS (CreateSongScreen.tsx)

Same adult picker after the genre categories: same label, the 29 accents in the
six groups, "None" first, sends `vocal_accent`. No language/vocal-style groups
(iOS never had them). Ships only with the next App Store build.

## 3. Testing

Backend (`tests/test_vocal_accent.py`):
- `ACCENT_STYLE_MAP` has exactly the 29 keys/snippets above (parametrised); each
  key in exactly one `ACCENT_GROUPS` group.
- `GENRE_DEFAULT_ACCENT`: all 12 keys exist in `GENRE_PRESETS`; parametrised —
  each genre with no accent gets its default in the final style.
- Explicit accent appends: pop + `vocal_accent="jamaican"` → snippet in style.
- Explicit overrides default: grime + `scottish` → Scottish in, "South London
  accent" out; grime + legacy `accent="German"` → default out.
- No accent = no change: genres without a default produce a style identical to
  pre-change master (golden strings captured from master before the change).
- Instrumental and intermittent grime → no default; unknown `vocal_accent` →
  ignored, no error, request succeeds.
- Both fields: `vocal_accent` decides style; `accent` still reaches lyrics.
- 3-way guard extended to accent keys + groups.

Frontend (node --test):
- `accentPayload`: accent key → `{vocal_accent}`, language/style value →
  `{accent}`, blank → `{}`.
- Kids picker renders "🎤 Singer's Voice" with flag-first options; adult label
  is "🎤 Singer's Accent (optional)".

Verification before shipping: full backend suite (0 failures), web-beats tests,
iOS `tsc --noEmit`, web-beats production build, one visual check of the Create
page. No paid generations.

## Rollout

Backend + web: one commit to master → Railway deploy, only on the user's go.
iOS: same commit, reaches users only via the next App Store build.

## Out of scope

Remix/Discover/Clips flows, kids Story narrator, editing `_ACCENT_DESCRIPTORS`,
a 30th accent, tile art.
