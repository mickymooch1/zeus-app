# Cover Art Customisation — Design

Date: 2026-10-14
Status: approved in chat (all three parts), awaiting spec review

## Goal

Let adult Create-flow users optionally steer their song's cover art with a visual
style and/or a short description. With neither filled in, covers are generated
exactly as today.

## Decisions (from the user)

- Two optional fields: a **Cover Art Style** chip picker (8 options, single-select,
  tap again to clear) and a **Describe your cover art** text box (max 150 chars).
- Final Flux prompt = genre cover prompt + style descriptor (if picked) + cleaned
  description (if entered) + `no text`.
- **Both takes** use the customisation: when a song is customised, take 2 also gets
  a Flux cover (~$0.025 extra). Uncustomised songs keep today's split (take 1 Flux,
  take 2 the provider's art).
- **Placement:** after the Singer's Accent picker, on web and iOS
  (brief → genres → Singer's Accent → Cover Art Style → Describe your cover art).
  The brief sits above the genre picker on both clients, so "after genres, before
  brief" is not possible as written.
- Hidden in Kids mode; Kids covers use the existing Kids prompt only.
- 3-way guard: backend `song_genres.py` ↔ web `genres.js` ↔ iOS `CreateSongScreen.tsx`.

## Style catalog (verbatim)

| key | chip | descriptor |
|---|---|---|
| cinematic | 🎬 Cinematic | cinematic lighting, dramatic composition, film still quality, high contrast |
| painterly | 🖼️ Painterly | oil painting style, brushstroke texture, fine art, gallery quality |
| vibrant | 🌈 Vibrant | vibrant saturated colours, bold and energetic, vivid and striking |
| dark_moody | 🖤 Dark & Moody | dark and moody, deep shadows, low key lighting, atmospheric |
| dreamy | ✨ Dreamy | dreamy and ethereal, soft focus, pastel tones, otherworldly glow |
| vintage | 🎭 Vintage / Retro | vintage retro style, film grain, faded colours, nostalgic feel |
| photorealistic | 📸 Photorealistic | photorealistic, ultra detailed, sharp focus, professional photography |
| illustrated | 🎨 Illustrated / Cartoon | cartoon illustration style, clean lines, colourful, fun and playful |

Labels: `🎨 Cover Art Style (optional)`, `✏️ Describe your cover art (optional)`.
Placeholder: `e.g. Manchester skyline at night, a dog at a piano, stormy ocean...`

## Backend

### song_genres.py
- `COVER_ART_STYLE_MAP: dict[str, str]` — the 8 entries above.
- `resolve_cover_art_style(key) -> str | None` — trimmed, lower-cased; known key or `None`.
- `sanitize_cover_art_description(text) -> str | None`:
  - control characters and newlines → spaces; whitespace collapsed;
  - removes URLs, prompt-weight syntax `(word:1.5)` → `word`, `--flag value` parameters,
    `negative prompt…`, `ignore/disregard (all) previous/above…` instructions, and
    any `no text` / `without text` phrases (we add `no text` ourselves);
  - strips stray separators (`, ; :`) left at the ends; truncates to 150 chars;
  - returns `None` when nothing meaningful remains.
- `build_cover_prompt(genre_prompt, style_key, description) -> str`:
  - neither set → `genre_prompt` **unchanged**;
  - otherwise remove a trailing `no text` (with its comma) from the genre prompt, then
    join `[genre_prompt, descriptor, description, "no text"]` with `", "`.

### Request + storage
- `SongsGenerateRequest.cover_art_style: str | None = Field(None, max_length=40)`.
- `SongsGenerateRequest.cover_art_description: str | None = Field(None, max_length=150)`
  (over 150 → 422; clients cap input at 150).
- New nullable columns `lyrics.cover_art_style TEXT`, `lyrics.cover_art_description TEXT`
  via the existing `ALTER TABLE … ADD COLUMN` startup migration list in `db.py`.
- `songs_generate`, right after `lyric_id` is known (covers both AI and custom-lyrics
  paths): when not `kids_story` and at least one cleaned value exists, `UPDATE lyrics`
  with the resolved key and cleaned description. Unknown style keys are logged and ignored.

### Cover generation (webhooks.py)
- `_cover_customisation(variant_id) -> tuple[str | None, str | None]` — reads the two
  columns via `song_variants.lyric_id`; any error → `(None, None)` (fail-soft).
- `_generate_flux_cover`: the Kids branch is unchanged and takes precedence. Otherwise
  `prompt = build_cover_prompt(cover_prompt_for(genre_tag), style, desc)`.
  - Uncustomised: calls `submit_image_generation(prompt, "1:1")` exactly as today.
  - Customised: calls it with `safety_check=True`; on `UnsafeImageError` it retries
    once with the plain genre prompt (no safety flag); other failures behave as today.
- Every caller inherits this (take 1, take 2, legacy webhook paths, YouTube re-cover).
- **Take 2:** if the song is customised, take 2 calls Flux even when the provider sent
  art; if Flux fails it keeps the provider's art (already downloaded and overlaid).
  Uncustomised → unchanged (provider art; Flux only when none was sent).

### image_generator.py
- `submit_image_generation(..., safety_check: bool = False)`; when true the payload adds
  `"enable_safety_checker": True` and a response whose `has_nsfw_concepts` contains a
  true value raises the new `UnsafeImageError(RuntimeError)`. Default path unchanged.

## Clients

### web-beats
- `genres.js`: `COVER_ART_STYLE_OPTIONS` (`{ key, emoji, label }` × 8, table order) and
  `coverArtPayload(style, description)` → `{ cover_art_style?, cover_art_description? }`
  (omits empty/whitespace values; trims the description).
- `SongsPage.jsx`: state `coverStyle` (`''`) and `coverDesc` (`''`); the block sits right
  after the Singer's Accent picker, gated `{!isKidsMode && (…)}`; chips toggle
  (`coverStyle === key ? '' : key`); textarea `maxLength={150}` with an `n/150` counter.
  Standard and Roast request bodies spread `...coverArtPayload(coverStyle, coverDesc)`;
  the Kids body sends neither.

### iOS (zeus-beats-ios)
- `CreateSongScreen.tsx`: `COVER_ART_STYLE_OPTIONS` constant, state `coverStyle` /
  `coverDesc`, chips (reusing the vocal-chip styles) and a `TextInput` (`maxLength={150}`)
  after the Singer's Accent block; request adds
  `cover_art_style: coverStyle || undefined` and
  `cover_art_description: coverDesc.trim() || undefined`.
- Ships to users only with the next App Store build. No pricing/upgrade UI involved.

## Testing
- Catalog: 8 keys, non-empty descriptors; `resolve_cover_art_style` cases.
- `build_cover_prompt`: genre only (unchanged), + style, + description, all three, and
  single trailing `no text` (genre prompts with and without it).
- Sanitiser: each injection pattern stripped; empty-after-cleaning → `None`; ≤150 chars.
- Endpoint (TestClient): 150 accepted, 151 → 422; values persisted on the lyric row;
  Kids request persists nothing; unknown style key ignored.
- `_generate_flux_cover`: uses stored customisation; Kids ignores it; unsafe → retry
  with the plain genre prompt; uncustomised call has no safety kwarg.
- Take 2: Flux only when customised (source-level, matching `test_cover_art_cost.py`).
- 3-way guard: web and iOS option keys == `COVER_ART_STYLE_MAP` keys, same order.
- Web: labels, placement after Singer's Accent, hidden in Kids, Kids body sends neither,
  `coverArtPayload` drops empties; iOS sends both fields.
- Before deploy: full backend suite, web tests, iOS `tsc --noEmit`, production build.

## Out of scope
- Kids covers, the persona ("Your Sound") path and the standalone `/kids` app.
- Editing a cover after generation.
