import { createContext, useContext, useState, useRef, useEffect, useCallback } from 'react';

const NowPlayingContext = createContext(null);

export function NowPlayingProvider({ children }) {
  const [queue, setQueue]           = useState([]);
  const [queueIndex, setQueueIndex] = useState(-1);
  const [isPlaying, setIsPlaying]   = useState(false);
  const [shuffle, setShuffle]       = useState(false);
  const [repeat, setRepeat]         = useState('none'); // 'none' | 'all' | 'one'
  const [currentTime, setCurrentTime] = useState(0);
  const [duration, setDuration]     = useState(0);

  const audioRef     = useRef(null);
  const shuffleRef   = useRef(false);
  const repeatRef    = useRef('none');
  const queueRef     = useRef([]);
  const indexRef     = useRef(-1);

  useEffect(() => { shuffleRef.current = shuffle; }, [shuffle]);
  useEffect(() => { repeatRef.current  = repeat;  }, [repeat]);
  useEffect(() => { queueRef.current   = queue;   }, [queue]);
  useEffect(() => { indexRef.current   = queueIndex; }, [queueIndex]);

  const getAudio = useCallback(() => {
    if (!audioRef.current) audioRef.current = new Audio();
    return audioRef.current;
  }, []);

  const playAtIndex = useCallback((idx) => {
    const q   = queueRef.current;
    const song = q[idx];
    if (!song?.mp3_url) return;
    const audio = getAudio();
    audio.src = song.mp3_url;
    audio.play().catch(() => {});
    setQueueIndex(idx);
    indexRef.current = idx;
    setIsPlaying(true);
    setCurrentTime(0);
    setDuration(0);
  }, [getAudio]);

  useEffect(() => {
    const audio = getAudio();

    const onTime = () => setCurrentTime(audio.currentTime);
    const onMeta = () => setDuration(isFinite(audio.duration) ? audio.duration : 0);
    const onEnded = () => {
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

    audio.addEventListener('timeupdate', onTime);
    audio.addEventListener('loadedmetadata', onMeta);
    audio.addEventListener('ended', onEnded);
    return () => {
      audio.removeEventListener('timeupdate', onTime);
      audio.removeEventListener('loadedmetadata', onMeta);
      audio.removeEventListener('ended', onEnded);
    };
  }, [getAudio, playAtIndex]);

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
    getAudio().pause();
    setIsPlaying(false);
  }, [getAudio]);

  const resume = useCallback(() => {
    getAudio().play().catch(() => {});
    setIsPlaying(true);
  }, [getAudio]);

  const togglePlay = useCallback(() => {
    if (isPlaying) { getAudio().pause(); setIsPlaying(false); }
    else           { getAudio().play().catch(() => {}); setIsPlaying(true); }
  }, [isPlaying, getAudio]);

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
      getAudio().currentTime = 0;
      setCurrentTime(0);
    } else if (idx > 0) {
      playAtIndex(idx - 1);
    }
  }, [getAudio, playAtIndex]);

  const seek = useCallback((time) => {
    const a = getAudio();
    a.currentTime = time;
    setCurrentTime(time);
  }, [getAudio]);

  const toggleShuffle = useCallback(() => setShuffle(s => !s), []);
  const cycleRepeat   = useCallback(() =>
    setRepeat(r => r === 'none' ? 'all' : r === 'all' ? 'one' : 'none'),
  []);

  const currentSong = queue[queueIndex] ?? null;

  return (
    <NowPlayingContext.Provider value={{
      currentSong, queue, queueIndex, isPlaying,
      shuffle, repeat, currentTime, duration,
      play, playOne, pause, resume, togglePlay,
      next, prev, seek, toggleShuffle, cycleRepeat,
    }}>
      {children}
    </NowPlayingContext.Provider>
  );
}

export const useNowPlaying = () => useContext(NowPlayingContext);
