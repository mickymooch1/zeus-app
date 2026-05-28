import { createContext, useContext, useState, useRef, useEffect, useCallback } from 'react';
import { audioManager } from '../utils/audioManager';

const NowPlayingContext = createContext(null);

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

  const audioRef            = useRef(null);
  const nextAudioRef        = useRef(null);   // scratch element used during crossfade
  const crossfadeActiveRef  = useRef(false);  // true from fade-start until new src is playing
  const fadeIntervalRef     = useRef(null);
  const shuffleRef          = useRef(false);
  const repeatRef           = useRef('none');
  const queueRef            = useRef([]);
  const indexRef            = useRef(-1);
  const crossfadeRef        = useRef(crossfade);
  const crossfadeDurationRef = useRef(crossfadeDuration);

  useEffect(() => { shuffleRef.current        = shuffle;          }, [shuffle]);
  useEffect(() => { repeatRef.current         = repeat;           }, [repeat]);
  useEffect(() => { queueRef.current          = queue;            }, [queue]);
  useEffect(() => { indexRef.current          = queueIndex;       }, [queueIndex]);
  useEffect(() => { crossfadeRef.current      = crossfade;        }, [crossfade]);
  useEffect(() => { crossfadeDurationRef.current = crossfadeDuration; }, [crossfadeDuration]);

  const setCrossfade = useCallback((val) => {
    setCrossfadeState(val);
    try { localStorage.setItem('zeus_crossfade', String(val)); } catch {}
  }, []);

  const setCrossfadeDuration = useCallback((val) => {
    setCrossfadeDurationState(val);
    try { localStorage.setItem('zeus_crossfade_duration', String(val)); } catch {}
  }, []);

  const getAudio = useCallback(() => {
    if (!audioRef.current) audioRef.current = new Audio();
    return audioRef.current;
  }, []);

  // Cancel any in-progress crossfade and restore primary audio to full volume.
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
    if (audioRef.current) audioRef.current.volume = 1;
    crossfadeActiveRef.current = false;
  }, []);

  const playAtIndex = useCallback((idx) => {
    cancelCrossfade();
    const q    = queueRef.current;
    const song = q[idx];
    if (!song?.mp3_url) return;
    const audio = getAudio();
    audio.volume = 1;
    audio.src = song.mp3_url;
    audioManager.play(audio, song.variant_id);
    setQueueIndex(idx);
    indexRef.current = idx;
    setIsPlaying(true);
    setCurrentTime(0);
    setDuration(0);
  }, [getAudio, cancelCrossfade]);

  // Begin a crossfade from the current song into the song at nextIdx.
  // The primary audioRef element fades out while a scratch element (nextAudio) fades in.
  // When the fade is complete, nextAudio's playback position is synced into the primary
  // element so all existing event listeners remain attached.
  const startCrossfade = useCallback((nextIdx) => {
    if (crossfadeActiveRef.current) return;
    const q        = queueRef.current;
    const nextSong = q[nextIdx];
    if (!nextSong?.mp3_url) return;

    crossfadeActiveRef.current = true;
    audioManager.stopWaveSurfer(); // ensure no WaveSurfer is competing

    const primary      = getAudio();
    const fadeDuration = crossfadeDurationRef.current;
    const step         = 1 / (fadeDuration * 10); // 100 ms tick → N seconds total

    const nextAudio = new Audio();
    nextAudio.src    = nextSong.mp3_url;
    nextAudio.volume = 0;
    nextAudioRef.current = nextAudio;
    nextAudio.play().catch(() => {});

    fadeIntervalRef.current = setInterval(() => {
      const newPrimaryVol = Math.max(0, primary.volume - step);
      const newNextVol    = Math.min(1, nextAudio.volume + step);
      primary.volume   = newPrimaryVol;
      nextAudio.volume = newNextVol;

      if (newPrimaryVol <= 0) {
        clearInterval(fadeIntervalRef.current);
        fadeIntervalRef.current = null;

        // Capture playback position reached by the scratch element
        const savedTime = nextAudio.currentTime;

        // Tear down scratch element
        nextAudio.pause();
        nextAudio.src = '';
        nextAudioRef.current = null;

        // Hand off to primary element (event listeners stay intact)
        setQueueIndex(nextIdx);
        indexRef.current = nextIdx;
        setDuration(0);
        primary.volume = 1;
        primary.src    = nextSong.mp3_url;

        // Seek to where the scratch element was, then play
        const doSeek = () => {
          if (savedTime > 0.1) primary.currentTime = savedTime;
          primary.play().catch(() => {});
          audioManager.updateVariantId(nextSong.variant_id);
          crossfadeActiveRef.current = false;
        };
        primary.addEventListener('canplay', doSeek, { once: true });
        // Safety: clear the flag even if canplay never fires (e.g. network error)
        setTimeout(() => { crossfadeActiveRef.current = false; }, 5000);
      }
    }, 100);
  }, [getAudio]);

  useEffect(() => {
    const audio = getAudio();

    const onTime = () => {
      const ct = audio.currentTime;
      setCurrentTime(ct);

      // Trigger crossfade when the song has N seconds remaining
      if (crossfadeRef.current && !crossfadeActiveRef.current) {
        const dur = audio.duration;
        if (isFinite(dur) && dur > 0) {
          const timeLeft = dur - ct;
          const fadeSecs = crossfadeDurationRef.current;
          if (timeLeft <= fadeSecs && timeLeft > 0) {
            const q   = queueRef.current;
            const idx = indexRef.current;
            if (repeatRef.current === 'one') return; // repeat-one: no crossfade
            let nextIdx;
            if (shuffleRef.current) {
              nextIdx = Math.floor(Math.random() * q.length);
            } else {
              nextIdx = idx + 1;
            }
            if (nextIdx < q.length) {
              startCrossfade(nextIdx);
            } else if (repeatRef.current === 'all' && q.length > 1) {
              startCrossfade(0);
            }
          }
        }
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
      if (repeatRef.current === 'one') {
        audio.currentTime = 0;
        audio.play().catch(() => {});
        return;
      }
      let next;
      if (shuffleRef.current) {
        next = Math.floor(Math.random() * q.length);
      } else {
        next = idx + 1;
      }
      if (next < q.length) {
        playAtIndex(next);
      } else if (repeatRef.current === 'all') {
        playAtIndex(0);
      } else {
        setIsPlaying(false);
      }
    };

    audio.addEventListener('timeupdate',    onTime);
    audio.addEventListener('loadedmetadata', onMeta);
    audio.addEventListener('play',           onPlay);
    audio.addEventListener('pause',          onPause);
    audio.addEventListener('ended',          onEnded);
    return () => {
      audio.removeEventListener('timeupdate',    onTime);
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

  const currentSong = queue[queueIndex] ?? null;

  return (
    <NowPlayingContext.Provider value={{
      currentSong, queue, queueIndex, isPlaying,
      shuffle, repeat, currentTime, duration,
      crossfade, crossfadeDuration,
      play, playOne, pause, resume, togglePlay,
      next, prev, seek, rewind, forward, toggleShuffle, cycleRepeat,
      setCrossfade, setCrossfadeDuration,
    }}>
      {children}
    </NowPlayingContext.Provider>
  );
}

export const useNowPlaying = () => useContext(NowPlayingContext);
