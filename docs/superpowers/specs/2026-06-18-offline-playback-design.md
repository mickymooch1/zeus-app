# Offline Playback — Design Spec

## Goal

Let users save songs to their device and play them with no internet connection. When offline, the Songs page transforms to show the local saved library. Online behaviour is unchanged.

## Scope

- **Piece 1 (app shell offline)** — already shipped. This spec covers Pieces 2–4.
- **Piece 2** — save-for-offline action + audio/metadata storage
- **Piece 3** — offline Songs page view + graceful degradation
- **Piece 4** — SW activate patch to preserve the audio cache across deploys

---

## Architecture

### New files

| File | Responsibility |
|------|---------------|
| `src/hooks/useOnlineStatus.js` | `isOnline: boolean` — wraps `navigator.onLine` + window events |
| `src/hooks/useOfflineSongs.js` | All offline data: save, remove, list, get blob URL |
| `src/components/OfflineBanner.jsx` | Thin sticky banner shown at top of Songs page when offline |

### Modified files

| File | Change |
|------|--------|
| `src/sw.js` | Activate handler: exclude `zeus-audio-*` caches from deletion |
| `src/pages/SongsPage.jsx` | Integrate offline mode: banner, filtered list, skipped fetch |
| Song card component | Add save/remove offline icon button |
| Generate-song / lyrics trigger points | Show "You're offline" toast on tap when offline |

---

## Storage

**Two-store model:**

| Store | What | Key | Technology |
|-------|------|-----|------------|
| `zeus-audio-v1` | MP3 audio (full Response) | `/offline-audio/${variant_id}` | Cache API |
| IDB `zeus-offline` / `songs` | Song metadata | `variant_id` | IndexedDB |

**Why Cache API for audio:** designed for HTTP responses, `cache.put(url, response)` is idiomatic, integrates with blob URL playback cleanly.

**Why IDB for metadata:** localStorage is too small (5 MB) once several songs are saved; IDB persists better under storage pressure than Cache API and is easy to query as a list.

**Audio cache versioning:** `zeus-audio-v1` is intentionally unversioned — it accumulates across app deploys and is only cleared when the user explicitly removes a song. The SW activate handler must exclude it from the deploy-time cache cleanup (see SW section).

---

## `useOnlineStatus` hook

```js
// src/hooks/useOnlineStatus.js
import { useEffect, useState } from 'react';

export function useOnlineStatus() {
  const [isOnline, setIsOnline] = useState(navigator.onLine);
  useEffect(() => {
    const on  = () => setIsOnline(true);
    const off = () => setIsOnline(false);
    window.addEventListener('online',  on);
    window.addEventListener('offline', off);
    return () => { window.removeEventListener('online', on); window.removeEventListener('offline', off); };
  }, []);
  return isOnline;
}
```

Simple hook, no context needed — components each call it; event listeners are cheap.

---

## `useOfflineSongs` hook

```js
// src/hooks/useOfflineSongs.js
export function useOfflineSongs() {
  // State
  savedSongs: Song[]          // live list from IDB, refreshed after save/remove
  downloading: Set<string>    // variant_ids mid-download

  // API
  isSaved(variant_id)         // boolean
  saveForOffline(song)        // Promise<void> — fetch + Cache API + IDB
  removeSaved(variant_id)     // Promise<void> — Cache API + IDB
  getOfflineAudioUrl(variant_id) // Promise<string|null> — blob URL; caller revokes after use
}
```

**IDB schema** (auto-created on first open):

```
db: zeus-offline  version: 1
  store: songs  keyPath: variant_id
    fields: variant_id, title, artist_name, image_url, mp3_url, duration_seconds, saved_at
```

**`saveForOffline` flow:**
1. Add `variant_id` to `downloading`
2. `const response = await fetch(song.mp3_url)`
3. `const cache = await caches.open('zeus-audio-v1')`
4. `await cache.put('/offline-audio/' + variant_id, response.clone())`
5. Write metadata to IDB
6. Remove from `downloading`, refresh `savedSongs`
7. On `QuotaExceededError` → show toast "Not enough storage — remove a saved song to free space"

**`getOfflineAudioUrl` flow:**
1. `const cache = await caches.open('zeus-audio-v1')`
2. `const resp = await cache.match('/offline-audio/' + variant_id)`
3. `if (!resp) return null`
4. `return URL.createObjectURL(await resp.blob())`
5. Caller must call `URL.revokeObjectURL(url)` after playback ends. The component that calls `getOfflineAudioUrl` owns the blob URL lifetime — it revokes when the song changes or the component unmounts.

---

## Service Worker patch

**Problem:** The existing activate handler deletes every cache except the current `zeus-static-*` cache. Without a fix, `zeus-audio-v1` is wiped on every deploy, silently erasing all saved offline songs.

**Fix** (one line change in `sw.js`):

```js
// Before
names.filter(n => n !== CACHE_NAME)

// After
names.filter(n => n !== CACHE_NAME && !n.startsWith('zeus-audio-'))
```

**SW versioning (Piece 4):** The existing mechanism already satisfies the requirement — `v${Date.now()}` stamped at build time by the Vite plugin, `skipWaiting` on install, `clients.claim` on activate, old `zeus-static-*` caches deleted. No further changes needed beyond the audio-exclusion patch above.

---

## Songs page — offline behaviour

When `!isOnline`:

1. **Skip the server fetch** — no `GET /api/users/me/song_credits` call (would fail anyway)
2. **Show `OfflineBanner`** — thin sticky bar: "You're offline — reconnect to create songs. Playing from your saved library."
3. **Filter list to `savedSongs`** — from IDB, not the server
4. **Play action** — `getOfflineAudioUrl(variant_id)` → blob URL → `NowPlayingContext.playSong({ ...song, mp3_url: blobUrl })`; revoke blob URL when song ends or changes
5. **Generate-song button** — stays active; on tap shows toast "You're offline — reconnect to create songs"
6. **Lyrics generation** — same: button stays active, toast on tap when offline

When `isOnline`: zero change to existing behaviour.

---

## Song card — save button

Added to the existing song card action row (same row as other action icons):

| State | Icon | Behaviour |
|-------|------|-----------|
| Not saved | Cloud-download icon | Tap → `saveForOffline(song)` |
| Downloading | Spinner | Not tappable |
| Saved | Checkmark / cloud-check | Tap → `removeSaved(variant_id)` (no confirm, reversible) |

`QuotaExceededError` → toast only; spinner returns to cloud-download icon.

---

## Offline banner

```
┌─────────────────────────────────────────────────────────────┐
│  ⚡ You're offline — reconnect to create songs.              │
│     Playing from your saved library.                        │
└─────────────────────────────────────────────────────────────┘
```

- Sticky at the top of the Songs page content area (below navbar)
- Not a modal, not full-screen
- Disappears automatically when `isOnline` returns true
- Styled to match the Zeus dark theme (amber/yellow accent for warning)

---

## Error handling

| Error | Handling |
|-------|---------|
| `QuotaExceededError` on save | Toast: "Not enough storage — remove a saved song to free space" |
| Cache evicted (song saved but audio missing) | `getOfflineAudioUrl` returns `null`; card shows broken state; user can re-save |
| IDB unavailable (private browsing) | `useOfflineSongs` catches and returns empty state; save buttons hidden |
| Offline + no saved songs | Banner + empty state: "No songs saved yet. Go online to save songs for offline playback." |

---

## Platform notes

- **Android TWA** — primary target. Cache API and IDB work fully in Chrome WebView (TWA). Audio blob URLs work with the HTML5 audio element.
- **Web (Chrome/Firefox)** — full support.
- **iOS Safari / WebView** — Cache API supported since iOS 11.1; IDB supported. Blob URL playback works. Storage limits are tighter (~50 MB per origin) — quota error handling is the mitigation.

---

## Out of scope

- Stem files, music video — only the main `mp3_url` is cached offline
- Background pre-caching — user initiates each save explicitly
- Cross-device sync of saved songs
- Offline-capable song generation
