# Lyrics View — Design Spec

**Date:** 2026-07-17
**Scope:** web-beats frontend only. No backend changes.

## Goal

Surface the lyrics already stored with each song, viewable from the Now Playing
bar. Static display — deliberately NOT synced/karaoke highlighting, because Suno
provides no word-level timing (the same drift problem hit with kids-story
subtitles).

## Data path (verified, already exists)

- `lyrics` table stores `lyrics_text` per lyric; each `song_variants` row has a
  `lyric_id` FK.
- Endpoint: `GET /api/lyrics/{lyric_id}` → `{ lyric_id, title, lyrics_text }`,
  auth via `Authorization: Bearer <token>`.
- Frontend already tags every song object with `lyric_id` (`SongsPage.jsx:1381`),
  and the player exposes the playing song as `currentSong` (`useNowPlaying()`).
- Instrumental songs store the literal string `"[Instrumental]"` as their lyrics
  (`lyrics.py:518`) — the detection sentinel.

So: `currentSong.lyric_id` → fetch endpoint → render. No new generation, no new
endpoint, no backend edit.

## Components

### `LyricsModal.jsx` (new)
- Props: `lyricId`, `title`, `onClose`.
- On mount (and when `lyricId` changes) fetch `GET /api/lyrics/{lyricId}`.
- Module-level cache keyed by `lyricId` so reopening is instant and re-fetches
  are avoided across the session.
- States: loading (spinner) → loaded (parsed lyrics) / instrumental / error
  ("Couldn't load lyrics" with the raw close still available).
- Instrumental when `lyrics_text.trim() === "[Instrumental]"` or empty → centred
  `🎵 Instrumental`.

### Lyrics parser (pure helper, unit-testable)
Splits `lyrics_text` into an ordered list of blocks:
- A line matching `^\s*\[([^\]]+)\]\s*$` → `{ type: 'header', text }` (the tag
  text, e.g. "Verse 1", rendered as a styled section header).
- Any other non-empty line → `{ type: 'line', text }`.
- Blank lines → paragraph spacing between blocks (not their own block).
- Parenthetical ad-libs like `(oohs and ahs)` are ordinary lines — left as-is.

Kept as a standalone exported function so it can be tested without React.

### `NowPlayingBar.jsx` (edit)
- Add a 📜 button:
  - Desktop: in the right-hand cluster beside shuffle/repeat (`dBtn` style).
  - Mobile: in the row-1 control cluster at 44px (`mBtn` style).
- Button opens the modal for `currentSong.lyric_id`. Disabled/hidden if the
  current song has no `lyric_id` (shouldn't happen, but guard).

## Visual / behaviour

- Neon theme: dark backdrop (`rgba(6,6,12,0.92)`), panel `#0a0a14` with a
  `rgba(0,240,255,0.18)` top accent, matching the bar.
- Body text `#e2e8f0`, line-height ~1.7, generous block spacing.
- Section headers: uppercase, letter-spaced, ~12px, neon purple `#c084fc`,
  margin above to separate from the previous block.
- Mobile: full-screen panel. Desktop: centred modal, `max-width: 560px`,
  `max-height: 80vh`, scrollable body.
- Close: 44px ✕ target (top-right), tap-outside on backdrop, and Escape key.
- Title shown at the top of the panel.

## Testing

1. Unit-test the parser: headers detected, lines preserved, instrumental
   sentinel, empty input, parentheticals left intact.
2. Browser verification (the acceptance gate):
   - A real vocal song → lyrics display with styled section headers.
   - An instrumental song → `🎵 Instrumental`, not an empty panel.
   - Close works; mobile full-screen at 44px.

## Out of scope

- Synced/karaoke line highlighting (no timing data — explicitly excluded).
- Editing lyrics. Downloading lyrics. Translating lyrics.
- Any backend change.
