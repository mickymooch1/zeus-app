import { useRef, useState, useEffect } from 'react';
import { Audio } from 'expo-av';

export function useAudioPlayer() {
  const soundRef    = useRef<Audio.Sound | null>(null);
  const [playingUrl, setPlayingUrl] = useState<string | null>(null);
  const [isPlaying,  setIsPlaying]  = useState(false);

  useEffect(() => () => {
    soundRef.current?.unloadAsync();
  }, []);

  async function stop() {
    await soundRef.current?.unloadAsync();
    soundRef.current = null;
    setPlayingUrl(null);
    setIsPlaying(false);
  }

  async function togglePlay(url: string) {
    if (url === playingUrl) {
      if (isPlaying) {
        await soundRef.current?.pauseAsync();
        setIsPlaying(false);
      } else {
        await soundRef.current?.playAsync();
        setIsPlaying(true);
      }
      return;
    }
    // Different track — unload previous, load new
    await soundRef.current?.unloadAsync();
    soundRef.current = null;
    await Audio.setAudioModeAsync({ playsInSilentModeIOS: true });
    const { sound } = await Audio.Sound.createAsync(
      { uri: url },
      { shouldPlay: true },
      (status) => { if (status.isLoaded && status.didJustFinish) setIsPlaying(false); },
    );
    soundRef.current = sound;
    setPlayingUrl(url);
    setIsPlaying(true);
  }

  return { playingUrl, isPlaying, togglePlay, stop };
}
