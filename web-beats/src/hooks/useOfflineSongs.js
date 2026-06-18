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
