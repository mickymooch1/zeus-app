import { useRef, useState, useEffect, useCallback } from 'react';
import { Audio, AVPlaybackStatus } from 'expo-av';

/**
 * Single-track audio player shared by the Create and Library screens.
 *
 * Correctness notes (previous bug: pause didn't stop playback):
 * - Branching pause-vs-play is decided by the player's LIVE status
 *   (`getStatusAsync`), never by React state read from a stale closure — so
 *   pressing pause always pauses.
 * - `isPlaying` is driven by `onPlaybackStatusUpdate`, so the button state
 *   always reflects what the player is actually doing.
 * - The current track's url is mirrored in a ref so the async toggle compares
 *   against the current value, not a captured one.
 * - `loadingRef` serialises loads so a new song fully tears down the previous
 *   sound before starting — no two tracks can play at once.
 */
export function useAudioPlayer() {
  const soundRef   = useRef<Audio.Sound | null>(null);
  const urlRef     = useRef<string | null>(null);  // current track url (ref = always current)
  const loadingRef = useRef(false);                // true while a track is being (un)loaded

  const [playingUrl, setPlayingUrl] = useState<string | null>(null);
  const [isPlaying,  setIsPlaying]  = useState(false);

  // Configure the audio session once; unload on unmount.
  useEffect(() => {
    Audio.setAudioModeAsync({ playsInSilentModeIOS: true }).catch(() => {});
    return () => { soundRef.current?.unloadAsync().catch(() => {}); };
  }, []);

  // Keep React state in lockstep with the real player.
  const onStatus = useCallback((status: AVPlaybackStatus) => {
    if (!status.isLoaded) return;
    setIsPlaying(status.isPlaying);
    if (status.didJustFinish) {
      setIsPlaying(false);
      soundRef.current?.setPositionAsync(0).catch(() => {}); // rewind so Play restarts it
    }
  }, []);

  // Fully tear down the current sound.
  const stop = useCallback(async () => {
    const s = soundRef.current;
    soundRef.current = null;
    urlRef.current   = null;
    setPlayingUrl(null);
    setIsPlaying(false);
    if (s) {
      try { await s.stopAsync(); }   catch { /* already stopped */ }
      try { await s.unloadAsync(); } catch { /* already unloaded */ }
    }
  }, []);

  const togglePlay = useCallback(async (url: string) => {
    if (loadingRef.current) return; // ignore taps while a load is in flight

    // Same track already loaded → pause/resume off the ACTUAL status.
    if (soundRef.current && urlRef.current === url) {
      const status = await soundRef.current.getStatusAsync();
      if (!status.isLoaded) return;
      if (status.isPlaying) {
        await soundRef.current.pauseAsync();
        setIsPlaying(false);
      } else {
        await soundRef.current.playAsync();
        setIsPlaying(true);
      }
      return;
    }

    // Different (or first) track → tear down the previous one FIRST, then load.
    loadingRef.current = true;
    try {
      const prev = soundRef.current;
      soundRef.current = null;
      urlRef.current   = null;
      if (prev) {
        try { await prev.stopAsync(); }   catch { /* noop */ }
        try { await prev.unloadAsync(); } catch { /* noop */ }
      }

      const { sound } = await Audio.Sound.createAsync(
        { uri: url },
        { shouldPlay: true },
        onStatus,
      );
      soundRef.current = sound;
      urlRef.current   = url;
      setPlayingUrl(url);
      setIsPlaying(true);
    } finally {
      loadingRef.current = false;
    }
  }, [onStatus]);

  return { playingUrl, isPlaying, togglePlay, stop };
}
