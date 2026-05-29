import { createContext, useContext, useState, useRef, useEffect, useCallback } from 'react';
import { audioManager } from '../utils/audioManager';

const NowPlayingContext = createContext(null);

const PRELOAD_AHEAD = 20; // seconds before end — start buffering next song

export function NowPlayingProvider({ children }) {
  const [queue, setQueue]           = useState([]);
  const [queueIndex, setQueueIndex] = useState(-1);
  const [isPlaying, setIsPlaying]   = useState(false);
  const [shuffle, setShuffle]       = useState(false);
  const [repeat, setRepeat]         = useState('none'); // 'none' | 'all' | 'one'
  const [currentTime, setCurrentTime] = useState(0);
  const [duration, setDuration]     = useState(0);

  const [crossfade, setCrossfadeState] = useState(() => {
    try { return localStorage.getItem('zeus_crossfade') === 'true'; } catch { return false; }
  });
  const [crossfadeDuration, setCrossfadeDurationState] = useState(() => {
    try { return Number(localStorage.getItem('zeus_crossfade_duration')) || 5; } catch { return 5; }
  });

  const audioRef             = useRef(null);
  const nextAudioRef         = useRef(null);  // active scratch element during fade
  const preloadRef           = useRef(null);  // { audio: Audio, idx: number } — loaded 10s early
  const crossfadeActiveRef   = useRef(false);
  const fadeIntervalRef      = useRef(null);
  const shuffleRef           = useRef(false);
  const repeatRef            = useRef('none');
  const queueRef             = useRef([]);
  const indexRef             = useRef(-1);
  const crossfadeRef         = useRef(crossfade);
  const crossfadeDurationRef = useRef(crossfadeDuration);
  // Tracks the variant_id that is currently loaded in the audio element.
  // Used by playAtIndex to resume instead of resetting src when the same song is re-clicked.
  const loadedVariantRef     = useRef(null);

  useEffect(() => { shuffleRef.current          = shuffle;          }, [shuffle]);
  useEffect(() => { repeatRef.current           = repeat;           }, [repeat]);
  useEffect(() => { queueRef.current            = queue;            }, [queue]);
  useEffect(() => { indexRef.current            = queueIndex;       }, [queueIndex]);
  useEffect(() => { crossfadeRef.current        = crossfade;        }, [crossfade]);
  useEffect(() => { crossfadeDurationRef.current = crossfadeDuration; }, [crossfadeDuration]);

  // Log crossfade config on mount so we can verify localStorage is read correctly
  useEffect(() => {
    console.log(
      '[Zeus CF] Init — crossfade:', crossfadeRef.current,
      '| duration:', crossfadeDurationRef.current, 's',
      '| localStorage zeus_crossfade:', localStorage.getItem('zeus_crossfade'),
      '| zeus_crossfade_duration:', localStorage.getItem('zeus_crossfade_duration'),
    );
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const setCrossfade = useCallback((val) => {
    console.log('[Zeus CF] Toggle crossfade →', val);
    setCrossfadeState(val);
    try { localStorage.setItem('zeus_crossfade', String(val)); } catch {}
  }, []);

  const setCrossfadeDuration = useCallback((val) => {
    console.log('[Zeus CF] Set duration →', val, 's');
    setCrossfadeDurationState(val);
    try { localStorage.setItem('zeus_crossfade_duration', String(val)); } catch {}
  }, []);

  const getAudio = useCallback(() => {
    if (!audioRef.current) audioRef.current = new Audio();
    return audioRef.current;
  }, []);

  // Tear down any in-progress crossfade AND any pending preload.
  const cancelCrossfade = useCallback(() => {
    if (fadeIntervalRef.current) {
      clearInterval(fadeIntervalRef.current);
      fadeIntervalRef.current = null;
    }
    if (nextAudioRef.current) {
      nextAudioRef.current.pause();
      nextAudioRef.current.src = '';
      nextAudioRef.current = null;
    }
    if (preloadRef.current) {
      preloadRef.current.audio.src = '';
      preloadRef.current = null;
    }
    if (audioRef.current) audioRef.current.volume = 1;
    crossfadeActiveRef.current = false;
  }, []);

  const playAtIndex = useCallback((idx) => {
    cancelCrossfade();
    const q    = queueRef.current;
    const song = q[idx];
    if (!song?.mp3_url) return;
    const audio = getAudio();

    // Bug 2 fix: if this exact variant is already loaded and not ended, just resume.
    // This prevents src reassignment (which resets currentTime) when the user clicks a
    // paused song's row again or the NowPlayingBar re-mounts after being hidden.
    if (
      loadedVariantRef.current === song.variant_id &&
      audio.readyState >= 2 &&   // HAVE_CURRENT_DATA or better — audio is usable
      !audio.ended
    ) {
      console.log('[Zeus] playAtIndex: resuming variant', song.variant_id, 'at', audio.currentTime.toFixed(2));
      audio.volume = 1;
      audio.play().catch(() => {});
      audioManager.updateVariantId(song.variant_id);
      setQueueIndex(idx);
      indexRef.current = idx;
      setIsPlaying(true);
      return;
    }

    console.log('[Zeus] playAtIndex: loading variant', song.variant_id, '(was', loadedVariantRef.current, ')');
    loadedVariantRef.current = song.variant_id;
    audio.volume = 1;
    audio.src = song.mp3_url;
    audioManager.play(audio, song.variant_id);
    setQueueIndex(idx);
    indexRef.current = idx;
    setIsPlaying(true);
    setCurrentTime(0);
    setDuration(0);
  }, [getAudio, cancelCrossfade]);

  // Start the volume fade. Reuses preloadRef.current if it matches nextIdx so the
  // audio has already been buffering for up to PRELOAD_AHEAD seconds.
  const startCrossfade = useCallback((nextIdx) => {
    if (crossfadeActiveRef.current) return;

    const q        = queueRef.current;
    const nextSong = q[nextIdx];
    if (!nextSong?.mp3_url) {
      console.warn('[Zeus CF] startCrossfade: no mp3_url for nextIdx', nextIdx);
      return;
    }

    crossfadeActiveRef.current = true;
    audioManager.stopWaveSurfer();

    const primary      = getAudio();
    const fadeDuration = crossfadeDurationRef.current;
    const step         = 1 / (fadeDuration * 20); // 50 ms interval → N second fade

    console.log(
      '[Zeus CF] Crossfade starting — current time:', primary.currentTime.toFixed(2),
      '| duration:', isFinite(primary.duration) ? primary.duration.toFixed(2) : 'NaN',
      '| step:', step.toFixed(4), '| fadeDuration:', fadeDuration, 's',
    );
    console.log('[Zeus CF] Loading next song:', nextSong.title, '(idx', nextIdx + ')');

    // Use pre-buffered element if available, otherwise create a cold one
    let nextAudio;
    if (preloadRef.current?.idx === nextIdx && preloadRef.current?.audio) {
      nextAudio = preloadRef.current.audio;
      console.log('[Zeus CF] Using preloaded audio element — readyState:', nextAudio.readyState);
      preloadRef.current = null;
    } else {
      console.warn('[Zeus CF] No preloaded element — creating cold Audio (may buffer during fade)');
      nextAudio = new Audio();
      nextAudio.src = nextSong.mp3_url;
      nextAudio.preload = 'auto';
    }

    nextAudio.volume = 0;
    nextAudioRef.current = nextAudio;

    console.log('[Zeus CF] Fading out current, fading in next');
    nextAudio.play().catch(err => console.warn('[Zeus CF] nextAudio.play() rejected:', err));

    let tick = 0;
    fadeIntervalRef.current = setInterval(() => {
      const newPrimaryVol = Math.max(0, primary.volume - step);
      const newNextVol    = Math.min(1, nextAudio.volume + step);
      primary.volume   = newPrimaryVol;
      nextAudio.volume = newNextVol;
      tick++;

      // Log every ~1 s (every 20 ticks at 50 ms)
      if (tick % 20 === 0) {
        console.log(
          '[Zeus CF] Fade tick', tick,
          '— primary vol:', newPrimaryVol.toFixed(2),
          '| next vol:', newNextVol.toFixed(2),
          '| next readyState:', nextAudio.readyState,
        );
      }

      if (newPrimaryVol <= 0) {
        clearInterval(fadeIntervalRef.current);
        fadeIntervalRef.current = null;
        console.log('[Zeus CF] Fade complete — handing off to primary element');

        const savedTime = nextAudio.currentTime;
        nextAudio.pause();
        nextAudio.src = '';
        nextAudioRef.current = null;

        setQueueIndex(nextIdx);
        indexRef.current = nextIdx;
        setDuration(0);
        primary.volume = 1;
        primary.src    = nextSong.mp3_url;

        const doSeek = () => {
          console.log('[Zeus CF] canplay fired — seeking primary to', savedTime.toFixed(2));
          if (savedTime > 0.1) primary.currentTime = savedTime;
          primary.play().catch(err => console.warn('[Zeus CF] primary.play() after fade rejected:', err));
          audioManager.updateVariantId(nextSong.variant_id);
          loadedVariantRef.current = nextSong.variant_id; // keep resume check in sync
          crossfadeActiveRef.current = false;
        };
        primary.addEventListener('canplay', doSeek, { once: true });

        // Safety: release the lock if canplay never fires (network failure etc.)
        setTimeout(() => {
          if (crossfadeActiveRef.current) {
            console.warn('[Zeus CF] Safety timeout: canplay never fired — releasing lock');
            crossfadeActiveRef.current = false;
          }
        }, 5000);
      }
    }, 50);
  }, [getAudio]);

  useEffect(() => {
    const audio = getAudio();

    const onTime = () => {
      const ct = audio.currentTime;
      setCurrentTime(ct);

      if (!crossfadeRef.current || crossfadeActiveRef.current) return;

      const dur = audio.duration;
      if (!isFinite(dur) || dur <= 0) return;

      const timeLeft = dur - ct;
      const fadeSecs = crossfadeDurationRef.current;

      // Clear stale preload if user seeked away from the danger zone
      if (timeLeft > PRELOAD_AHEAD && preloadRef.current) {
        console.log('[Zeus CF] Seek cleared preload');
        preloadRef.current.audio.src = '';
        preloadRef.current = null;
      }

      if (timeLeft > PRELOAD_AHEAD) return;

      const q   = queueRef.current;
      const idx = indexRef.current;
      if (repeatRef.current === 'one') return;

      // Determine next index. For shuffle we lock it in at preload time so we don't
      // pick a new random target every 250 ms in the danger zone.
      let nextIdx;
      if (preloadRef.current) {
        nextIdx = preloadRef.current.idx; // already locked
      } else if (shuffleRef.current) {
        nextIdx = Math.floor(Math.random() * q.length);
      } else {
        nextIdx = idx + 1;
      }

      if (nextIdx >= q.length) {
        if (repeatRef.current === 'all' && q.length > 1) {
          nextIdx = 0;
        } else {
          return; // no next song
        }
      }

      const nextSong = q[nextIdx];
      if (!nextSong?.mp3_url) return;

      // Preload phase — buffer the next song silently
      if (!preloadRef.current) {
        console.log(
          '[Zeus CF] Preloading next song:', nextSong.title,
          '— timeLeft:', timeLeft.toFixed(2), 's',
          '| crossfade triggers at:', fadeSecs, 's',
        );
        const preload = new Audio();
        preload.src     = nextSong.mp3_url;
        preload.preload = 'auto';
        preload.volume  = 0;
        preload.load();
        preloadRef.current = { audio: preload, idx: nextIdx };
      }

      // Crossfade phase
      if (timeLeft <= fadeSecs) {
        console.log(
          '[Zeus CF] Triggering crossfade — timeLeft:', timeLeft.toFixed(2), 's',
          '| enabled:', crossfadeRef.current,
          '| nextIdx:', nextIdx,
        );
        startCrossfade(nextIdx);
      }
    };

    const onMeta  = () => setDuration(isFinite(audio.duration) ? audio.duration : 0);
    const onPlay  = () => setIsPlaying(true);
    // Suppress the spurious pause that fires when crossfade swaps the src attribute
    const onPause = () => { if (!crossfadeActiveRef.current) setIsPlaying(false); };
    const onEnded = () => {
      if (crossfadeActiveRef.current) return; // crossfade is handling the transition
      const q   = queueRef.current;
      const idx = indexRef.current;
      console.log(
        '[Zeus] onEnded — idx:', idx, '| qLen:', q.length,
        '| shuffle:', shuffleRef.current, '| repeat:', repeatRef.current,
      );
      if (repeatRef.current === 'one') {
        audio.currentTime = 0;
        audio.play().catch(() => {});
        return;
      }
      let next;
      if (shuffleRef.current) {
        next = Math.floor(Math.random() * q.length);
        console.log('[Zeus] onEnded: shuffle → next idx', next);
      } else {
        next = idx + 1;
        console.log('[Zeus] onEnded: in-order → next idx', next);
      }
      if (next < q.length) {
        playAtIndex(next);
      } else if (repeatRef.current === 'all') {
        console.log('[Zeus] onEnded: repeat all → wrapping to 0');
        playAtIndex(0);
      } else {
        console.log('[Zeus] onEnded: end of queue, stopping');
        setIsPlaying(false);
      }
    };

    audio.addEventListener('timeupdate',     onTime);
    audio.addEventListener('loadedmetadata', onMeta);
    audio.addEventListener('play',           onPlay);
    audio.addEventListener('pause',          onPause);
    audio.addEventListener('ended',          onEnded);
    return () => {
      audio.removeEventListener('timeupdate',     onTime);
      audio.removeEventListener('loadedmetadata', onMeta);
      audio.removeEventListener('play',           onPlay);
      audio.removeEventListener('pause',          onPause);
      audio.removeEventListener('ended',          onEnded);
    };
  }, [getAudio, playAtIndex, startCrossfade]);

  const play = useCallback((variants, startIndex = 0) => {
    setQueue(variants);
    queueRef.current = variants;
    playAtIndex(startIndex);
  }, [playAtIndex]);

  const playOne = useCallback((variant) => {
    setQueue([variant]);
    queueRef.current = [variant];
    playAtIndex(0);
  }, [playAtIndex]);

  const pause = useCallback(() => {
    cancelCrossfade();
    getAudio().pause();
    setIsPlaying(false);
  }, [cancelCrossfade, getAudio]);

  const resume = useCallback(() => {
    getAudio().play().catch(() => {});
    setIsPlaying(true);
  }, [getAudio]);

  const togglePlay = useCallback(() => {
    if (isPlaying) { cancelCrossfade(); getAudio().pause(); setIsPlaying(false); }
    else           { getAudio().play().catch(() => {}); setIsPlaying(true); }
  }, [isPlaying, cancelCrossfade, getAudio]);

  const next = useCallback(() => {
    const q   = queueRef.current;
    const idx = indexRef.current;
    if (shuffleRef.current) {
      playAtIndex(Math.floor(Math.random() * q.length));
    } else if (idx < q.length - 1) {
      playAtIndex(idx + 1);
    } else if (repeatRef.current === 'all') {
      playAtIndex(0);
    }
  }, [playAtIndex]);

  const prev = useCallback(() => {
    const idx = indexRef.current;
    if (getAudio().currentTime > 3) {
      cancelCrossfade();
      getAudio().currentTime = 0;
      setCurrentTime(0);
    } else if (idx > 0) {
      playAtIndex(idx - 1);
    }
  }, [getAudio, cancelCrossfade, playAtIndex]);

  const seek = useCallback((time) => {
    cancelCrossfade();
    const a = getAudio();
    a.currentTime = time;
    setCurrentTime(time);
  }, [cancelCrossfade, getAudio]);

  const rewind = useCallback(() => {
    cancelCrossfade();
    const a = getAudio();
    const t = Math.max(0, a.currentTime - 10);
    a.currentTime = t;
    setCurrentTime(t);
  }, [cancelCrossfade, getAudio]);

  const forward = useCallback(() => {
    cancelCrossfade();
    const a = getAudio();
    const t = Math.min(isFinite(a.duration) ? a.duration : 0, a.currentTime + 10);
    a.currentTime = t;
    setCurrentTime(t);
  }, [cancelCrossfade, getAudio]);

  const toggleShuffle = useCallback(() => setShuffle(s => !s), []);
  const cycleRepeat   = useCallback(() =>
    setRepeat(r => r === 'none' ? 'all' : r === 'all' ? 'one' : 'none'),
  []);

  const dismiss = useCallback(() => {
    cancelCrossfade();
    const audio = getAudio();
    audio.pause();
    audio.src = '';
    audioManager.stop();
    loadedVariantRef.current = null;
    setQueue([]);
    setQueueIndex(-1);
    setIsPlaying(false);
    setCurrentTime(0);
    setDuration(0);
  }, [cancelCrossfade, getAudio]);

  const currentSong = queue[queueIndex] ?? null;

  return (
    <NowPlayingContext.Provider value={{
      currentSong, queue, queueIndex, isPlaying,
      shuffle, repeat, currentTime, duration,
      crossfade, crossfadeDuration,
      play, playOne, pause, resume, togglePlay,
      next, prev, seek, rewind, forward, toggleShuffle, cycleRepeat,
      setCrossfade, setCrossfadeDuration,
      dismiss,
    }}>
      {children}
    </NowPlayingContext.Provider>
  );
}

export const useNowPlaying = () => useContext(NowPlayingContext);
