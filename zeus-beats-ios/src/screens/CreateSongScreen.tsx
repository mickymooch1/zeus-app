import React, { useState, useEffect, useRef } from 'react';
import {
  View, Text, TextInput, TouchableOpacity, Switch,
  ScrollView, ActivityIndicator, Image, StyleSheet, Alert,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Audio } from 'expo-av';
import * as SecureStore from 'expo-secure-store';
import { COLORS, RADIUS } from '../constants/theme';
import { BACKEND_URL, API, TOKEN_KEY } from '../constants/api';

const GENRES = ['Pop', 'Hip Hop', 'Rock', 'R&B', 'Electronic', 'Afrobeats', 'Drill', 'House', 'Country', 'Jazz'];
const POLL_MS = 5_000;
const TIMEOUT_MS = 5 * 60 * 1_000;

type Phase = 'idle' | 'generating' | 'polling' | 'complete' | 'error' | 'timeout';

interface SongResult {
  title: string;
  mp3_url: string;
  image_url: string | null;
}

function absoluteUrl(path: string | null): string | null {
  if (!path) return null;
  return path.startsWith('http') ? path : `${BACKEND_URL}${path}`;
}

export function CreateSongScreen() {
  const [brief, setBrief]             = useState('');
  const [genre, setGenre]             = useState<string | null>(null);
  const [instrumental, setInstrumental] = useState(false);
  const [phase, setPhase]             = useState<Phase>('idle');
  const [errorMsg, setErrorMsg]       = useState('');
  const [result, setResult]           = useState<SongResult | null>(null);
  const [isPlaying, setIsPlaying]     = useState(false);

  const soundRef     = useRef<Audio.Sound | null>(null);
  const pollTimer    = useRef<ReturnType<typeof setInterval> | null>(null);
  const pollStart    = useRef(0);
  const lyricIdRef   = useRef<number | null>(null);
  const titleRef     = useRef('Your Song');

  useEffect(() => () => {
    clearPoll();
    soundRef.current?.unloadAsync();
  }, []);

  function clearPoll() {
    if (pollTimer.current) {
      clearInterval(pollTimer.current);
      pollTimer.current = null;
    }
  }

  async function token(): Promise<string> {
    const t = await SecureStore.getItemAsync(TOKEN_KEY);
    if (!t) throw new Error('Not signed in');
    return t;
  }

  async function handleCreate() {
    if (!genre) return;
    try {
      setPhase('generating');
      setErrorMsg('');
      setResult(null);
      setIsPlaying(false);
      soundRef.current?.unloadAsync();
      soundRef.current = null;

      const res = await fetch(API.generate, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${await token()}` },
        body: JSON.stringify({ brief: brief.trim(), genres: [genre], instrumental }),
      });

      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        throw new Error(body.detail || `Error ${res.status}`);
      }

      const data = await res.json();
      lyricIdRef.current = data.lyric_id;
      titleRef.current   = data.title || 'Your Song';
      pollStart.current  = Date.now();
      setPhase('polling');
      beginPolling();
    } catch (e: any) {
      setErrorMsg(e.message || 'Something went wrong.');
      setPhase('error');
    }
  }

  function beginPolling() {
    pollTimer.current = setInterval(async () => {
      if (Date.now() - pollStart.current > TIMEOUT_MS) {
        clearPoll();
        setPhase('timeout');
        return;
      }
      try {
        const res = await fetch(API.variants(lyricIdRef.current!), {
          headers: { Authorization: `Bearer ${await token()}` },
        });
        if (!res.ok) return;
        const data  = await res.json();
        const v     = data.variants?.[0];
        if (!v) return;

        if (v.status === 'complete') {
          clearPoll();
          setResult({
            title:     titleRef.current,
            mp3_url:   absoluteUrl(v.mp3_url)!,
            image_url: absoluteUrl(v.image_url),
          });
          setPhase('complete');
        } else if (v.status === 'failed') {
          clearPoll();
          setErrorMsg('Song generation failed. Please try again.');
          setPhase('error');
        }
      } catch {
        // transient network error — keep polling
      }
    }, POLL_MS);
  }

  async function handlePlay() {
    if (!result) return;
    try {
      if (isPlaying) {
        await soundRef.current?.pauseAsync();
        setIsPlaying(false);
        return;
      }
      if (!soundRef.current) {
        await Audio.setAudioModeAsync({ playsInSilentModeIOS: true });
        const { sound } = await Audio.Sound.createAsync(
          { uri: result.mp3_url },
          { shouldPlay: true },
          (status) => { if (status.isLoaded && status.didJustFinish) setIsPlaying(false); },
        );
        soundRef.current = sound;
      } else {
        await soundRef.current.playAsync();
      }
      setIsPlaying(true);
    } catch (e: any) {
      Alert.alert('Playback error', e.message);
    }
  }

  function reset() {
    clearPoll();
    soundRef.current?.unloadAsync();
    soundRef.current = null;
    setPhase('idle');
    setResult(null);
    setErrorMsg('');
    setIsPlaying(false);
  }

  // ── Generating / polling ──────────────────────────────────────────────────
  if (phase === 'generating' || phase === 'polling') {
    return (
      <SafeAreaView style={s.center}>
        <ActivityIndicator size="large" color={COLORS.cyan} style={{ marginBottom: 20 }} />
        <Text style={s.statusText}>
          {phase === 'generating'
            ? 'Submitting your song…'
            : 'Generating your song…\nThis usually takes about a minute.'}
        </Text>
      </SafeAreaView>
    );
  }

  // ── Complete ──────────────────────────────────────────────────────────────
  if (phase === 'complete' && result) {
    return (
      <SafeAreaView style={s.center}>
        {result.image_url
          ? <Image source={{ uri: result.image_url }} style={s.cover} />
          : <View style={[s.cover, s.coverFallback]}><Text style={{ fontSize: 48 }}>⚡</Text></View>}
        <Text style={s.songTitle} numberOfLines={2}>{result.title}</Text>
        <TouchableOpacity style={s.playBtn} onPress={handlePlay}>
          <Text style={s.playBtnText}>{isPlaying ? '⏸  Pause' : '▶  Play'}</Text>
        </TouchableOpacity>
        <TouchableOpacity style={s.secondaryBtn} onPress={reset}>
          <Text style={s.secondaryBtnText}>Create another</Text>
        </TouchableOpacity>
      </SafeAreaView>
    );
  }

  // ── Error / timeout ───────────────────────────────────────────────────────
  if (phase === 'error' || phase === 'timeout') {
    return (
      <SafeAreaView style={s.center}>
        <Text style={s.errorText}>
          {phase === 'timeout'
            ? 'This is taking longer than expected.\nCheck your library soon.'
            : errorMsg || 'Something went wrong.'}
        </Text>
        <TouchableOpacity style={s.secondaryBtn} onPress={reset}>
          <Text style={s.secondaryBtnText}>Try again</Text>
        </TouchableOpacity>
      </SafeAreaView>
    );
  }

  // ── Idle form ─────────────────────────────────────────────────────────────
  return (
    <SafeAreaView style={s.safeArea}>
      <ScrollView contentContainerStyle={s.scroll} keyboardShouldPersistTaps="handled">
        <Text style={s.heading}>⚡ Create</Text>

        <Text style={s.label}>Describe your song</Text>
        <TextInput
          style={s.briefInput}
          placeholder="A summer anthem about chasing dreams…"
          placeholderTextColor={COLORS.textMuted}
          multiline
          maxLength={2000}
          value={brief}
          onChangeText={setBrief}
          textAlignVertical="top"
        />

        <Text style={s.label}>
          Genre <Text style={s.required}>*</Text>
        </Text>
        <View style={s.genreGrid}>
          {GENRES.map(g => (
            <TouchableOpacity
              key={g}
              style={[s.chip, genre === g && s.chipActive]}
              onPress={() => setGenre(g)}
            >
              <Text style={[s.chipText, genre === g && s.chipTextActive]}>{g}</Text>
            </TouchableOpacity>
          ))}
        </View>

        <View style={s.toggleRow}>
          <Text style={s.label}>Instrumental</Text>
          <Switch
            value={instrumental}
            onValueChange={setInstrumental}
            trackColor={{ false: COLORS.textMuted, true: COLORS.purple }}
            thumbColor={instrumental ? COLORS.cyan : COLORS.white}
          />
        </View>

        <TouchableOpacity
          style={[s.createBtn, !genre && s.createBtnDisabled]}
          onPress={handleCreate}
          disabled={!genre}
        >
          <Text style={s.createBtnText}>Create</Text>
        </TouchableOpacity>
      </ScrollView>
    </SafeAreaView>
  );
}

const s = StyleSheet.create({
  safeArea:  { flex: 1, backgroundColor: COLORS.bg },
  center:    { flex: 1, backgroundColor: COLORS.bg, alignItems: 'center', justifyContent: 'center', padding: 24 },
  scroll:    { padding: 20, paddingBottom: 48 },

  heading:   { fontSize: 26, fontWeight: '700', color: COLORS.white, marginBottom: 24 },
  label:     { fontSize: 13, fontWeight: '600', color: COLORS.textPrimary, marginBottom: 8, marginTop: 20 },
  required:  { color: COLORS.cyan },

  briefInput: {
    backgroundColor: COLORS.inputBg,
    borderWidth: 1,
    borderColor: COLORS.borderDim,
    borderRadius: RADIUS.md,
    color: COLORS.white,
    padding: 14,
    fontSize: 15,
    minHeight: 100,
    marginTop: 0,
  },

  genreGrid: { flexDirection: 'row', flexWrap: 'wrap', gap: 8, marginBottom: 4 },
  chip: {
    paddingHorizontal: 14,
    paddingVertical: 8,
    borderRadius: 20,
    borderWidth: 1,
    borderColor: COLORS.borderDim,
    backgroundColor: COLORS.inputBg,
  },
  chipActive:    { borderColor: COLORS.cyan, backgroundColor: 'rgba(0,240,255,0.1)' },
  chipText:      { color: COLORS.textMuted, fontSize: 13, fontWeight: '500' },
  chipTextActive:{ color: COLORS.cyan },

  toggleRow: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    marginTop: 20,
    marginBottom: 4,
  },

  createBtn: {
    marginTop: 32,
    backgroundColor: COLORS.purple,
    borderRadius: RADIUS.md,
    paddingVertical: 16,
    alignItems: 'center',
  },
  createBtnDisabled: { opacity: 0.4 },
  createBtnText:     { color: COLORS.white, fontSize: 16, fontWeight: '700', letterSpacing: 0.5 },

  statusText: { color: COLORS.textPrimary, fontSize: 15, textAlign: 'center', lineHeight: 24 },
  errorText:  { color: COLORS.errorText, fontSize: 15, textAlign: 'center', lineHeight: 24, marginBottom: 24 },

  cover: { width: 220, height: 220, borderRadius: RADIUS.lg, marginBottom: 20 },
  coverFallback: { backgroundColor: COLORS.bgCard, alignItems: 'center', justifyContent: 'center' },
  songTitle: {
    color: COLORS.white, fontSize: 20, fontWeight: '700',
    textAlign: 'center', marginBottom: 28, paddingHorizontal: 16,
  },

  playBtn: {
    backgroundColor: COLORS.purple,
    borderRadius: RADIUS.md,
    paddingVertical: 14,
    paddingHorizontal: 48,
    marginBottom: 14,
  },
  playBtnText: { color: COLORS.white, fontSize: 16, fontWeight: '700' },

  secondaryBtn: {
    borderWidth: 1,
    borderColor: COLORS.borderDim,
    borderRadius: RADIUS.md,
    paddingVertical: 12,
    paddingHorizontal: 32,
  },
  secondaryBtnText: { color: COLORS.textMuted, fontSize: 14 },
});
