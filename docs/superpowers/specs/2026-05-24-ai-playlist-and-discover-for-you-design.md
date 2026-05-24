# Design: AI Playlist Builder + Discover "For You" Tab

**Date:** 2026-05-24  
**Project:** Zeus Beats (`web-beats/` + `backend/`)  
**Scope:** Two independent features; implemented and shipped separately.

---

## Feature 1 — AI Playlist Builder

### Overview

Users can generate a playlist by describing a vibe. Claude Haiku reads their song library and selects 10–15 songs that match the description, then auto-creates a named playlist.

### Backend

**Endpoint:** `POST /api/playlists/ai-generate`  
**Auth:** Required (`Depends(auth.get_current_user)`)  
**Request body:**
```json
{ "prompt": "Songs for my Sunday morning" }
```

**Logic:**
1. Fetch all the user's song variants: `variant_id`, `title`, `genre_tag`, `style_prompt` (via existing `GET /api/lyrics` + variants, or a dedicated DB query)
2. If the user has fewer than 3 songs, return `400` with `"Not enough songs to generate a playlist"`
3. Build a numbered list of songs and call Claude Haiku:
   - System: "You are a music curator. Select songs from a library that match a mood or vibe."
   - User: numbered song list + the user's prompt + instruction to return a JSON array of variant_ids (10–15, or fewer if library is small)
   - Claude must return only a valid JSON array of integers, nothing else
4. Parse Claude's response; filter to valid variant_ids the user actually owns
5. Create a playlist via `db.create_playlist()` — name is the prompt, truncated to 60 chars
6. Bulk-insert selected songs via `db.add_song_to_playlist()`
7. Return `{"playlist": {...}, "song_count": N}`

**No credits deducted.** AI playlist generation is a free discovery feature.

**Error handling:**
- Claude returns empty array or invalid JSON → `400` with `"No matching songs found for that vibe"`
- User has < 3 songs → `400` with `"Add more songs to use AI Playlist"`
- Claude API failure → `500`

### Frontend (`web-beats/src/pages/PlaylistPage.jsx`)

**Entry point:** "✨ AI Playlist" button placed alongside the existing "New Playlist" form at the top of the page.

**Modal UI:**
- Overlay modal with heading "AI Playlist Builder"
- 6 clickable suggestion chips above the input:
  - "Sunday morning chill", "Hype workout", "Late night drive", "Friday night out", "Focus mode", "Heartbreak vibes"
  - Clicking a chip pre-fills the text input (user can then edit)
- Text input: placeholder `"Describe your mood or vibe..."`
- "Generate Playlist" button (disabled while loading)
- Loading state: spinner + "Claude is curating your playlist…"
- On success: close modal, re-fetch playlists, new playlist appears at top
- Error state: inline message below input ("No matching songs found — try a different vibe")
- Close button (×) in corner; clicking outside modal closes it

**Styling:** Matches existing PlaylistPage dark theme — cyan accents, `#12121e` card background, gradient heading text.

---

## Feature 3 — Discover "For You" Tab

### Overview

A personalised recommendation tab on the Discover feed. Uses the user's like history to infer preferred genres and surfaces public songs in those genres, ordered by popularity.

### New Database Table

```sql
CREATE TABLE IF NOT EXISTS song_play_events (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    variant_id INTEGER NOT NULL,
    user_id    TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_play_events_user ON song_play_events(user_id);
```

`user_id` is nullable — unauthenticated plays are still logged (for future analytics), but only authenticated plays count toward recommendations.

### Backend Endpoints

**`POST /api/discover/play`**  
Auth: optional. Body: `{"variant_id": 123}`.  
Inserts a row into `song_play_events`. Returns `204 No Content`.  
Fire-and-forget from frontend — errors silently swallowed on client.

**`GET /api/discover/for-you`**  
Auth: required.  
Algorithm:
1. Get the user's liked `genre_tag` values (via `song_variant_likes JOIN song_variants`)
2. Deduplicate genres; if none → fall back to most-liked public songs (same as Trending, limit 20)
3. Return public songs (`is_public=1`, `status='complete'`, `mp3_url IS NOT NULL`) in those genres, **excluding songs the user has already liked**, ordered by `like_count DESC`, limit 20
4. Response shape identical to `GET /api/discover` response: `{"songs": [...], "page": 0, "count": N}`

No pagination on For You (fixed 20-song curated set; refreshes on next visit).

### Frontend (`web-beats/src/pages/DiscoverPage.jsx`)

**Tab bar:** Slim two-tab bar pinned at top of the discover view:
- **🔥 Trending** — existing `/api/discover` feed (infinite scroll, unchanged)
- **✨ For You** — calls `/api/discover/for-you`; fixed 20-song list (no infinite scroll)

**State:** Each tab maintains its own song list. Switching tabs does not re-fetch if data is already loaded.

**Unauthenticated users:** "For You" tab is visible but shows a login nudge card instead of songs: "Sign in to get personalised recommendations".

**Play event logging:** The existing IntersectionObserver callback (fires when a slide enters the viewport) also calls `POST /api/discover/play` for the active song. Auth token included if present; omitted if not logged in.

**Styling:** Tab bar uses existing cyan/pink colour scheme. Active tab underlined in cyan. Inactive tab dimmed.

---

## Implementation Order

1. Feature 1 (AI Playlist) — backend endpoint + PlaylistPage modal. Commit + push.
2. Feature 3 (For You) — DB migration + two backend endpoints + DiscoverPage tab bar. Commit + push.

---

## Out of Scope

- Feature 2 (Stems Separator) — deferred pending Apiframe endpoint verification.
- Playlist sharing or collaborative playlists.
- For You pagination or "refresh" button.
- Play count display on song cards.
