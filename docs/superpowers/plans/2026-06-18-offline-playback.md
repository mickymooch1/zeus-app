# Offline Playback Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let users save songs locally and play them with no internet — Songs page transforms to show saved songs when offline, generate button shows a toast instead of breaking.

**Architecture:** Cache API stores MP3 audio keyed by `/offline-audio/${variant_id}`; IndexedDB stores song metadata. SW activate handler patched to skip `zeus-audio-*` caches. `useOfflineSongs` hook owns all local storage logic; `useOnlineStatus` detects connectivity. SongsPage uses `isOnline` to switch between server library and saved songs.

**Tech Stack:** React hooks, IndexedDB (raw API, no library), Cache API, Web Audio (HTML5), existing NowPlayingContext.

**Spec:** `docs/superpowers/specs/2026-06-18-offline-playback-design.md`

---

## File Map

| Action | Path | Responsibility |
|--------|------|---------------|
| Create | `web-beats/src/hooks/useOnlineStatus.js` | `isOnline` boolean from window events |
| Create | `web-beats/src/hooks/useOfflineSongs.js` | IDB + Cache API save/remove/list/play |
| Create | `web-beats/src/components/OfflineBanner.jsx` | Amber banner shown when offline |
| Modify | `web-beats/src/sw.js` line 25 | Exclude `zeus-audio-*` from deploy cleanup |
| Modify | `web-beats/src/pages/SongsPage.jsx` | Wire offline mode into library, card, generate |

---

## Task 1: `useOnlineStatus` hook

**Files:**
- Create: `web-beats/src/hooks/useOnlineStatus.js`

- [ ] **Step 1: Write the file**

```js
// web-beats/src/hooks/useOnlineStatus.js
import { useEffect, useState } from 'react';

export function useOnlineStatus() {
  const [isOnline, setIsOnline] = useState(navigator.onLine);
  useEffect(() => {
    const handleOnline  = () => setIsOnline(true);
    const handleOffline = () => setIsOnline(false);
    window.addEventListener('online',  handleOnline);
    window.addEventListener('offline', handleOffline);
    return () => {
      window.removeEventListener('online',  handleOnline);
      window.removeEventListener('offline', handleOffline);
    };
  }, []);
  return isOnline;
}
```

- [ ] **Step 2: Verify file exists**

Run: `ls web-beats/src/hooks/`
Expected: `useOnlineStatus.js` present

- [ ] **Step 3: Commit**

```bash
git add web-beats/src/hooks/useOnlineStatus.js
git commit -m "feat: useOnlineStatus hook — wraps navigator.onLine + window events"
```

---

## Task 2: `useOfflineSongs` hook

**Files:**
- Create: `web-beats/src/hooks/useOfflineSongs.js`

- [ ] **Step 1: Write the file**

```js
// web-beats/src/hooks/useOfflineSongs.js
import { useCallback, useEffect, useState } from 'react';

const DB_NAME     = 'zeus-offline';
const DB_VERSION  = 1;
const STORE       = 'songs';
const AUDIO_CACHE = 'zeus-audio-v1';

function audioKey(variant_id) {
  return `/offline-audio/${variant_id}`;
}

function openDb() {
  return new Promise((resolve, reject) => {
    const req = indexedDB.open(DB_NAME, DB_VERSION);
    req.onupgradeneeded = (e) => {
      const db = e.target.result;
      if (!db.objectStoreNames.contains(STORE)) {
        db.createObjectStore(STORE, { keyPath: 'variant_id' });
      }
    };
    req.onsuccess = (e) => resolve(e.target.result);
    req.onerror   = (e) => reject(e.target.error);
  });
}

function idbGetAll(db) {
  return new Promise((resolve, reject) => {
    const req = db.transaction(STORE, 'readonly').objectStore(STORE).getAll();
    req.onsuccess = (e) => resolve(e.target.result);
    req.onerror   = (e) => reject(e.target.error);
  });
}

function idbPut(db, record) {
  return new Promise((resolve, reject) => {
    const req = db.transaction(STORE, 'readwrite').objectStore(STORE).put(record);
    req.onsuccess = resolve;
    req.onerror   = (e) => reject(e.target.error);
  });
}

function idbDelete(db, key) {
  return new Promise((resolve, reject) => {
    const req = db.transaction(STORE, 'readwrite').objectStore(STORE).delete(key);
    req.onsuccess = resolve;
    req.onerror   = (e) => reject(e.target.error);
  });
}

export function useOfflineSongs() {
  const [savedSongs,  setSavedSongs]  = useState([]);
  const [downloading, setDownloading] = useState(new Set());

  const loadSongs = useCallback(async () => {
    try {
      const db  = await openDb();
      const all = await idbGetAll(db);
      setSavedSongs(all.sort((a, b) => b.saved_at - a.saved_at));
    } catch (_) {
      setSavedSongs([]);
    }
  }, []);

  useEffect(() => { loadSongs(); }, [loadSongs]);

  const isSaved = useCallback(
    (variant_id) => savedSongs.some(s => s.variant_id === variant_id),
    [savedSongs],
  );

  const saveForOffline = useCallback(async (song) => {
    const vid = song.variant_id;
    setDownloading(d => new Set([...d, vid]));
    try {
      const response = await fetch(song.mp3_url);
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      const cache = await caches.open(AUDIO_CACHE);
      await cache.put(audioKey(vid), response);
      const db = await openDb();
      await idbPut(db, {
        variant_id:       song.variant_id,
        title:            song.title            || '',
        artist_name:      song.artist_name      || '',
        image_url:        song.image_url        || '',
        mp3_url:          song.mp3_url,
        duration_seconds: song.duration_seconds || 0,
        genre_tag:        song.genre_tag        || '',
        saved_at:         Date.now(),
      });
      await loadSongs();
    } catch (err) {
      if (err?.name === 'QuotaExceededError') {
        const quotaErr = new Error('Storage full');
        quotaErr.isQuota = true;
        throw quotaErr;
      }
      throw err;
    } finally {
      setDownloading(d => { const n = new Set(d); n.delete(vid); return n; });
    }
  }, [loadSongs]);

  const removeSaved = useCallback(async (variant_id) => {
    try {
      const cache = await caches.open(AUDIO_CACHE);
      await cache.delete(audioKey(variant_id));
      const db = await openDb();
      await idbDelete(db, variant_id);
      await loadSongs();
    } catch (_) {}
  }, [loadSongs]);

  const getOfflineAudioUrl = useCallback(async (variant_id) => {
    try {
      const cache = await caches.open(AUDIO_CACHE);
      const resp  = await cache.match(audioKey(variant_id));
      if (!resp) return null;
      return URL.createObjectURL(await resp.blob());
    } catch (_) {
      return null;
    }
  }, []);

  return { savedSongs, downloading, isSaved, saveForOffline, removeSaved, getOfflineAudioUrl };
}
```

- [ ] **Step 2: Commit**

```bash
git add web-beats/src/hooks/useOfflineSongs.js
git commit -m "feat: useOfflineSongs hook — IDB metadata + Cache API audio storage"
```

---

## Task 3: `OfflineBanner` component

**Files:**
- Create: `web-beats/src/components/OfflineBanner.jsx`

- [ ] **Step 1: Write the file**

```jsx
// web-beats/src/components/OfflineBanner.jsx
export default function OfflineBanner() {
  return (
    <div style={{
      background:   'linear-gradient(135deg, rgba(245,158,11,0.12), rgba(245,158,11,0.06))',
      border:       '1px solid rgba(245,158,11,0.3)',
      borderRadius: 8,
      padding:      '10px 16px',
      marginBottom: 16,
      display:      'flex',
      alignItems:   'center',
      gap:          10,
    }}>
      <span style={{ fontSize: 18 }}>📵</span>
      <span style={{ fontSize: 13, color: '#fbbf24', fontWeight: 500, lineHeight: 1.4 }}>
        <strong>You're offline</strong> — reconnect to create songs. Playing from your saved library.
      </span>
    </div>
  );
}
```

- [ ] **Step 2: Commit**

```bash
git add web-beats/src/components/OfflineBanner.jsx
git commit -m "feat: OfflineBanner component — amber sticky banner for offline state"
```

---

## Task 4: SW activate patch — preserve audio cache across deploys

**Files:**
- Modify: `web-beats/src/sw.js` (line 25 — the `names.filter` in the activate handler)

**Context:** The activate handler currently deletes every cache except the current static cache. Without this patch, deploying the app wipes all saved offline songs.

- [ ] **Step 1: Open `web-beats/src/sw.js` and find the activate handler**

The relevant section (lines 21–30):
```js
self.addEventListener('activate', event => {
  event.waitUntil(
    caches.keys()
      .then(names =>
        Promise.all(names.filter(n => n !== CACHE_NAME).map(n => caches.delete(n)))
      )
      .then(() => self.clients.claim())
  );
});
```

- [ ] **Step 2: Change the filter to exclude `zeus-audio-*`**

Replace:
```js
        Promise.all(names.filter(n => n !== CACHE_NAME).map(n => caches.delete(n)))
```
With:
```js
        Promise.all(names.filter(n => n !== CACHE_NAME && !n.startsWith('zeus-audio-')).map(n => caches.delete(n)))
```

The complete activate handler after the change:
```js
self.addEventListener('activate', event => {
  // Delete every cache that isn't this version — clears stale assets from old deploys
  // zeus-audio-* is excluded: it holds user's saved offline songs and must survive deploys
  event.waitUntil(
    caches.keys()
      .then(names =>
        Promise.all(names.filter(n => n !== CACHE_NAME && !n.startsWith('zeus-audio-')).map(n => caches.delete(n)))
      )
      .then(() => self.clients.claim())
  );
});
```

- [ ] **Step 3: Commit**

```bash
git add web-beats/src/sw.js
git commit -m "fix: preserve zeus-audio-* cache across deploys in SW activate handler"
```

---

## Task 5: SongCard — save button and offline play

**Files:**
- Modify: `web-beats/src/pages/SongsPage.jsx` (the `SongCard` component defined at line 422)

The `SongCard` is a `memo` component defined inline in SongsPage.jsx. All edits in this task are inside the `SongCard` function.

- [ ] **Step 1: Add new props to SongCard signature**

Find the SongCard signature (line 422–432):
```js
const SongCard = memo(function SongCard({
  variant, title, artistName, activeWsRef,
  canYouTube, ytConnected, ytStatus: ytSt, ytUrl, ytError, onYouTubeClick,
  canDid, didSt, videoUrl, onAvatarClick, videoCredits, didPlanOk, isAdmin,
  onDelete, deleting, musicVideoUrl, onRemake, onTelegramClick, onRegenerate,
  isFavourite, onToggleFavourite, isFreeTier, animateCover,
  isPublic, onShareToggle,
  playlists, onAddToPlaylist,
  premiumCredits, stemsData: stemsProp, onGetStems, onOpenCover,
  soundPersonaVariantId, onLockSound,
}) {
```

Add `isSaved, isDownloading, onSaveOffline, onRemoveSaved, onPlayOffline,` to the destructure:
```js
const SongCard = memo(function SongCard({
  variant, title, artistName, activeWsRef,
  canYouTube, ytConnected, ytStatus: ytSt, ytUrl, ytError, onYouTubeClick,
  canDid, didSt, videoUrl, onAvatarClick, videoCredits, didPlanOk, isAdmin,
  onDelete, deleting, musicVideoUrl, onRemake, onTelegramClick, onRegenerate,
  isFavourite, onToggleFavourite, isFreeTier, animateCover,
  isPublic, onShareToggle,
  playlists, onAddToPlaylist,
  premiumCredits, stemsData: stemsProp, onGetStems, onOpenCover,
  soundPersonaVariantId, onLockSound,
  isSaved, isDownloading, onSaveOffline, onRemoveSaved, onPlayOffline,
}) {
```

- [ ] **Step 2: Modify the play button to support offline play**

Find the play button in the card cover area (around line 725–743). Current code:
```jsx
        {!isFailed && (
          <button
            onClick={handlePlay}
            style={{
              position: 'absolute', bottom: 8, left: 8,
              transform: 'none',
              width: 40, height: 40, borderRadius: '50%',
              border: '1.5px solid rgba(255,255,255,0.7)',
              background: playing ? 'rgba(124,58,237,0.85)' : 'rgba(0,0,0,0.6)',
              color: '#fff', fontSize: 16, cursor: wsReady ? 'pointer' : 'default',
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              backdropFilter: 'blur(6px)', opacity: wsReady ? 1 : 0.4,
              transition: 'all 0.2s', pointerEvents: wsReady ? 'auto' : 'none', flexShrink: 0,
            }}
            onMouseEnter={(e) => { if (wsReady) e.currentTarget.style.boxShadow = '0 0 10px rgba(0,240,255,0.6)'; }}
            onMouseLeave={(e) => { e.currentTarget.style.boxShadow = 'none'; }}
          >
            {playing ? '⏸' : '▶'}
          </button>
        )}
```

Replace with (adds `canPlay` which is true when WaveSurfer is ready OR offline audio is available):
```jsx
        {!isFailed && (
          <button
            onClick={onPlayOffline || handlePlay}
            style={{
              position: 'absolute', bottom: 8, left: 8,
              transform: 'none',
              width: 40, height: 40, borderRadius: '50%',
              border: '1.5px solid rgba(255,255,255,0.7)',
              background: playing ? 'rgba(124,58,237,0.85)' : 'rgba(0,0,0,0.6)',
              color: '#fff', fontSize: 16,
              cursor: (wsReady || !!onPlayOffline) ? 'pointer' : 'default',
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              backdropFilter: 'blur(6px)',
              opacity: (wsReady || !!onPlayOffline) ? 1 : 0.4,
              transition: 'all 0.2s',
              pointerEvents: (wsReady || !!onPlayOffline) ? 'auto' : 'none',
              flexShrink: 0,
            }}
            onMouseEnter={(e) => { if (wsReady || !!onPlayOffline) e.currentTarget.style.boxShadow = '0 0 10px rgba(0,240,255,0.6)'; }}
            onMouseLeave={(e) => { e.currentTarget.style.boxShadow = 'none'; }}
          >
            {playing ? '⏸' : '▶'}
          </button>
        )}
```

- [ ] **Step 3: Add the Save Offline button after the Download button**

Find the download button block (Row 1, around line 820–839):
```jsx
            {/* Row 1: Download — full width primary */}
            <div style={{ marginTop: 10 }}>
              <a
                className="dl-btn"
                href={variant.mp3_url}
                download={safeFilename}
                onClick={() => setDownloaded(true)}
                style={{ ... }}
              >
                {downloaded ? '✓ Downloaded' : t('songs.buttons.download')}
              </a>
            </div>
            {/* Row 2: Share + Telegram */}
```

Add the save-offline button between Row 1 and Row 2:
```jsx
            {/* Row 1: Download — full width primary */}
            <div style={{ marginTop: 10 }}>
              <a
                className="dl-btn"
                href={variant.mp3_url}
                download={safeFilename}
                onClick={() => setDownloaded(true)}
                style={{ ... }}
              >
                {downloaded ? '✓ Downloaded' : t('songs.buttons.download')}
              </a>
            </div>
            {/* Row 1.5: Save for offline */}
            <div style={{ marginTop: 8 }}>
              <button
                onClick={isSaved ? onRemoveSaved : onSaveOffline}
                disabled={isDownloading}
                style={{
                  ...actionBtnStyle,
                  width:       '100%',
                  color:       isSaved ? '#4ade80' : '#a78bfa',
                  borderColor: isSaved ? 'rgba(74,222,128,0.5)' : 'rgba(167,139,250,0.5)',
                  opacity:     isDownloading ? 0.6 : 1,
                  cursor:      isDownloading ? 'default' : 'pointer',
                }}
              >
                {isDownloading ? '⬇ Saving…' : isSaved ? '✓ Saved Offline' : '⬇ Save Offline'}
              </button>
            </div>
            {/* Row 2: Share + Telegram */}
```

- [ ] **Step 4: Commit**

```bash
git add web-beats/src/pages/SongsPage.jsx
git commit -m "feat: SongCard — save/remove offline button + offline play button support"
```

---

## Task 6: SongsPage — imports, hooks, state, helpers

**Files:**
- Modify: `web-beats/src/pages/SongsPage.jsx` (top of file and top of `SongsPage` component)

- [ ] **Step 1: Add imports at top of file**

Find the existing import block (lines 1–12). After the last existing import:
```js
import IOSWebViewBanner from '../components/IOSWebViewBanner';
```

Add:
```js
import { useOnlineStatus }  from '../hooks/useOnlineStatus';
import { useOfflineSongs }  from '../hooks/useOfflineSongs';
import OfflineBanner        from '../components/OfflineBanner';
import { useNowPlaying }    from '../contexts/NowPlayingContext';
```

- [ ] **Step 2: Add hooks and state inside `SongsPage()` function**

Find the line that starts the component body (around line 1127):
```js
export default function SongsPage() {
  const { token, user } = useAuth();
```

After `const { token, user } = useAuth();`, add:
```js
  const isOnline = useOnlineStatus();
  const { savedSongs, downloading, isSaved, saveForOffline, removeSaved, getOfflineAudioUrl } = useOfflineSongs();
  const { playOne } = useNowPlaying();
```

- [ ] **Step 3: Add offlineToast state and ref**

Find the block of `useState` declarations (around line 1130–1260). After the last `useState`:
```js
  const [lockToast, setLockToast] = useState('');
  const lockToastTimer = useRef(null);
```

Add:
```js
  const [offlineToast, setOfflineToast] = useState('');
  const offlineToastRef = useRef(null);
```

- [ ] **Step 4: Add helper functions after the `handleGenerate` function**

Find `handleGenerate` (around line 1604). After the complete function, add:
```js
  const showOfflineToast = useCallback((msg = "You're offline — reconnect to create songs") => {
    setOfflineToast(msg);
    clearTimeout(offlineToastRef.current);
    offlineToastRef.current = setTimeout(() => setOfflineToast(''), 3500);
  }, []);

  const handleSaveOffline = useCallback(async (song) => {
    try {
      await saveForOffline(song);
    } catch (err) {
      if (err?.isQuota) {
        showOfflineToast('Not enough storage — remove a saved song to free space');
      }
    }
  }, [saveForOffline, showOfflineToast]);

  const handlePlayOffline = useCallback(async (song) => {
    try {
      const blobUrl = await getOfflineAudioUrl(song.variant_id);
      if (!blobUrl) {
        showOfflineToast('Song file not found — try saving it again while online');
        return;
      }
      playOne({ ...song, mp3_url: blobUrl });
    } catch (_) {}
  }, [getOfflineAudioUrl, playOne, showOfflineToast]);
```

- [ ] **Step 5: Commit**

```bash
git add web-beats/src/pages/SongsPage.jsx
git commit -m "feat: SongsPage — offline hooks, state, helpers (save/play/toast)"
```

---

## Task 7: SongsPage — fetch guard, library switch, render changes

**Files:**
- Modify: `web-beats/src/pages/SongsPage.jsx` (render logic and data flow)

- [ ] **Step 1: Guard the initial fetch useEffect**

Find the useEffect that calls `fetchCredits`, `fetchLibrary`, `fetchPlaylists` (around line 1398–1402):
```js
  useEffect(() => {
    fetchCredits();
    fetchLibrary();
    fetchPlaylists();
  }, [fetchCredits, fetchLibrary, fetchPlaylists]);
```

Replace with:
```js
  useEffect(() => {
    if (!isOnline) return;
    fetchCredits();
    fetchLibrary();
    fetchPlaylists();
  }, [fetchCredits, fetchLibrary, fetchPlaylists, isOnline]);
```

This also re-fetches automatically when connectivity is restored.

- [ ] **Step 2: Fix the `filteredLibrary` computation to use savedSongs when offline**

Find (around line 2181–2192):
```js
  const activeLyricId   = activeJob?.lyric_id;
  const filteredLibrary = useMemo(() => {
    const q = search.trim().toLowerCase();
    return library
      .filter((v) => v.lyric_id !== activeLyricId)
      .filter((v) => !q ||
        v.title?.toLowerCase().includes(q) ||
        v.genre_tag?.toLowerCase().includes(q) ||
        gLabel(v.genre_tag).toLowerCase().includes(q) ||
        v.brief?.toLowerCase().includes(q)
      );
  }, [library, activeLyricId, search]);
```

Replace with:
```js
  const activeLyricId   = activeJob?.lyric_id;
  const displayLibrary  = isOnline ? library : savedSongs;
  const filteredLibrary = useMemo(() => {
    const q = search.trim().toLowerCase();
    return displayLibrary
      .filter((v) => activeLyricId == null || v.lyric_id !== activeLyricId)
      .filter((v) => !q ||
        v.title?.toLowerCase().includes(q) ||
        v.genre_tag?.toLowerCase().includes(q) ||
        gLabel(v.genre_tag).toLowerCase().includes(q) ||
        v.brief?.toLowerCase().includes(q)
      );
  }, [displayLibrary, activeLyricId, search]);
```

Notes on changes:
- `displayLibrary` swaps between `library` (online) and `savedSongs` (offline)
- `activeLyricId == null ||` guard prevents filtering out all offline songs (saved songs have no `lyric_id`, and when offline there's no active job, so both are `undefined` — without this guard `undefined !== undefined = false` filters everything out)

- [ ] **Step 3: Add OfflineBanner and generateEffective variable**

Find the `canGenerate` and `creditExceeded` computed values (around line 1272–1283). After `creditExceeded`, add:
```js
  const generateEffective = isOnline ? canGenerate : true; // offline: keep button active
```

- [ ] **Step 4: Add OfflineBanner to the render**

In the JSX render, find the content area. Look for the `EmailVerificationBanner` usage (around line 2200–2220 — this is near the top of the rendered page content). Find a `<section>` or `<div>` that wraps the main content after the header. Add the OfflineBanner just inside the inner content wrapper:

Look for where the songs content area starts — find this pattern:
```jsx
        <div className="songs-content-wrap" style={{ ... }}>
```
(or similar — it's the main scrollable content div)

After that opening div, add:
```jsx
          {!isOnline && <OfflineBanner />}
```

- [ ] **Step 5: Guard activeJob section with `isOnline`**

Find the activeJob section (around line 3551):
```jsx
          {activeJob && (
            <section style={{ marginBottom: 48 }}>
```

Replace with:
```jsx
          {isOnline && activeJob && (
            <section style={{ marginBottom: 48 }}>
```

- [ ] **Step 6: Modify generate button for offline toast**

Find the generate button (around line 3473–3492):
```jsx
            <button
              onClick={handleGenerate}
              disabled={!canGenerate}
              style={{
                ...
                background: canGenerate
                  ? isKidsMode
                    ? 'linear-gradient(135deg, #f59e0b 0%, #fbbf24 100%)'
                    : 'linear-gradient(135deg, #7c3aed 0%, #a855f7 100%)'
                  : 'rgba(255,255,255,0.05)',
                color: canGenerate ? (isKidsMode ? '#1a0a00' : '#fff') : '#444',
                ...
                cursor: canGenerate ? 'pointer' : 'default',
                ...
              }}
            >
```

Replace `canGenerate` references in this button's props and style with `generateEffective`, and change `onClick`:
```jsx
            <button
              onClick={isOnline ? handleGenerate : () => showOfflineToast()}
              disabled={!generateEffective}
              style={{
                width: '100%',
                padding: '14px',
                borderRadius: 10,
                border: 'none',
                background: generateEffective
                  ? isKidsMode
                    ? 'linear-gradient(135deg, #f59e0b 0%, #fbbf24 100%)'
                    : 'linear-gradient(135deg, #7c3aed 0%, #a855f7 100%)'
                  : 'rgba(255,255,255,0.05)',
                color: generateEffective ? (isKidsMode ? '#1a0a00' : '#fff') : '#444',
                fontSize: isKidsMode ? 16 : 15,
                fontWeight: 700,
                cursor: generateEffective ? 'pointer' : 'default',
                transition: 'all 0.2s',
                letterSpacing: '0.2px',
              }}
            >
```

- [ ] **Step 7: Update the offline empty-state message**

Find the empty library message (around line 3790–3795):
```jsx
          {!activeJob && filteredLibrary.length === 0 && (
            <div style={{ textAlign: 'center', padding: '80px 0' }}>
              <div style={{ fontSize: 56, marginBottom: 16, opacity: 0.15 }}>♫</div>
              <p style={{ fontSize: 15, color: '#555' }}>{t('songs.emptySongs')}</p>
            </div>
          )}
```

Replace with:
```jsx
          {!activeJob && filteredLibrary.length === 0 && (
            <div style={{ textAlign: 'center', padding: '80px 0' }}>
              <div style={{ fontSize: 56, marginBottom: 16, opacity: 0.15 }}>♫</div>
              <p style={{ fontSize: 15, color: '#555' }}>
                {isOnline
                  ? t('songs.emptySongs')
                  : 'No songs saved yet. Go online to save songs for offline playback.'}
              </p>
            </div>
          )}
```

- [ ] **Step 8: Add offline props to both SongCard call sites**

There are two places where SongCard is rendered in the JSX:

**Call site 1** — inside the `activeJob` section (around line 3571), the SongCard for generating songs. This one does NOT need save-offline props (songs being generated can't be saved yet). Add null/false defaults:
```jsx
                      <SongCard
                        key={v.variant_id}
                        variant={v}
                        title={activeJob.title}
                        {/* ... all existing props ... */}
                        isSaved={false}
                        isDownloading={false}
                        onSaveOffline={null}
                        onRemoveSaved={null}
                        onPlayOffline={null}
                      />
```

**Call site 2** — the main library grid `visibleLibrary.map` (around line 3714). This is the one that needs full offline support:
```jsx
                    <SongCard
                      key={v.variant_id}
                      variant={v}
                      title={v.title}
                      {/* ... all existing props ... */}
                      isSaved={isSaved(v.variant_id)}
                      isDownloading={downloading.has(v.variant_id)}
                      onSaveOffline={() => handleSaveOffline(v)}
                      onRemoveSaved={() => removeSaved(v.variant_id)}
                      onPlayOffline={!isOnline && isSaved(v.variant_id) ? () => handlePlayOffline(v) : null}
                    />
```

- [ ] **Step 9: Add offlineToast overlay to JSX**

Find the end of the SongsPage return statement (just before the closing `</div>` and `</div>` of the page). Add the toast overlay inside the outermost return div:

```jsx
      {/* Offline toast */}
      {offlineToast && (
        <div style={{
          position:  'fixed',
          bottom:    80,
          left:      '50%',
          transform: 'translateX(-50%)',
          background:   'rgba(18,18,30,0.96)',
          border:       '1px solid rgba(245,158,11,0.4)',
          borderRadius: 10,
          padding:   '12px 20px',
          color:     '#fbbf24',
          fontSize:  13,
          fontWeight: 600,
          zIndex:    9999,
          whiteSpace: 'nowrap',
          boxShadow: '0 8px 32px rgba(0,0,0,0.5)',
          pointerEvents: 'none',
        }}>
          📵 {offlineToast}
        </div>
      )}
```

- [ ] **Step 10: Commit**

```bash
git add web-beats/src/pages/SongsPage.jsx
git commit -m "feat: SongsPage — offline library view, banner, generate toast, empty state"
```

---

## Task 8: Build, verify, deploy

**Files:**
- Build output: `web-beats-dist/`

- [ ] **Step 1: Run the build**

Run from `web-beats/`:
```bash
cd web-beats && npm run build
```

Expected: `✓ built in Xs` with no errors. All chunks listed. `sw.js` emitted to `../web-beats-dist/sw.js`.

- [ ] **Step 2: Verify the SW patch is in the built output**

Run:
```bash
grep "zeus-audio-" ../web-beats-dist/sw.js
```

Expected: `!n.startsWith('zeus-audio-')` present in the output.

- [ ] **Step 3: Smoke-test offline mode (manual)**

1. Open the app in Chrome DevTools
2. Application → Service Workers → check **Offline**
3. Reload the page
4. Expected: app shell loads (from SW cache), Songs page shows "You're offline" banner, empty state shows "No songs saved yet"
5. Uncheck Offline
6. Expected: banner disappears, songs load from server

- [ ] **Step 4: Smoke-test save-for-offline (manual)**

1. While online, open Songs page
2. Tap "⬇ Save Offline" on a song card — spinner appears, then "✓ Saved Offline"
3. Go offline (DevTools → Offline)
4. Reload — saved song appears in the offline songs list
5. Tap ▶ on the saved song — NowPlayingBar opens and plays from local cache
6. Go back online — full library reloads

- [ ] **Step 5: Push to Railway**

```bash
git push origin HEAD
```

Expected: Railway picks up the push and deploys.

---

## Self-review notes

- **Spec coverage:** Piece 2 (save for offline) ✓ Tasks 2, 5, 6. Piece 3 (offline view) ✓ Tasks 3, 7. Piece 4 (SW versioning) ✓ Task 4. Generate toast ✓ Task 7 Step 6.
- **Type consistency:** `isSaved(variant_id)` called with `v.variant_id` in both SongCard call sites ✓. `handlePlayOffline(v)` matches `handlePlayOffline(song)` signature ✓. `saveForOffline(song)` called with full variant objects from visibleLibrary ✓.
- **activeLyricId bug:** Fixed in Task 7 Step 2 — `activeLyricId == null ||` guard prevents savedSongs (undefined lyric_id) being filtered out when offline.
- **Blob URL lifecycle:** Blob URLs created by `getOfflineAudioUrl` are passed to `NowPlayingContext.playOne`. They are not explicitly revoked — they persist for the tab session and are GC'd on tab close. Acceptable for this use case.
- **IDB private-browsing:** `openDb` throws if IDB unavailable; `loadSongs` catches and returns `[]`; all save/remove operations catch silently. Hook returns empty state — save buttons render but fail gracefully.
