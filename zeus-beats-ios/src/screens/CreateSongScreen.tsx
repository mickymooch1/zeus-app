import React, { useState, useEffect, useRef } from 'react';
import {
  View, Text, TextInput,
  ScrollView, ActivityIndicator, Image, StyleSheet, Alert,
  KeyboardAvoidingView, TouchableWithoutFeedback, Keyboard, Platform,
} from 'react-native';
import { TouchableOpacity } from 'react-native-gesture-handler';
import { SafeAreaView } from 'react-native-safe-area-context';
import { LinearGradient } from 'expo-linear-gradient';
import { useFonts, Orbitron_700Bold } from '@expo-google-fonts/orbitron';
import * as SecureStore from 'expo-secure-store';
import { useAudioPlayer } from '../hooks/useAudioPlayer';
import { COLORS, RADIUS } from '../constants/theme';
import { BACKEND_URL, API, TOKEN_KEY } from '../constants/api';

// ─── Vibe presets ─────────────────────────────────────────────────────────────

const SONG_TEMPLATES = [
  { emoji: '🔥', label: 'Club Banger',    value: 'An energetic club banger with a massive drop, euphoric build up and a crowd going crazy' },
  { emoji: '😢', label: 'Emotional R&B',  value: 'A heartfelt emotional R&B song about losing someone you love and trying to move on' },
  { emoji: '🎤', label: 'Grime Bars',     value: 'Hard hitting grime bars about coming from nothing and making it against all odds, fast aggressive flow' },
  { emoji: '📱', label: 'TikTok Viral',   value: 'A catchy viral TikTok song with an irresistible hook that gets stuck in your head instantly' },
  { emoji: '💔', label: 'Sad Love Song',  value: 'A sad love song about heartbreak and missing someone who left, slow and emotional' },
  { emoji: '🌴', label: 'Afrobeats Vibe', value: 'A feel good afrobeats song about summer, good vibes and celebrating life' },
];

// ─── Genre categories (mirrors web-beats GENRE_CATEGORIES exactly) ────────────

interface GenreCategory { id: string; label: string; color: string; genres: string[] }

const GENRE_CATEGORIES: GenreCategory[] = [
  { id: 'uk_street',  label: 'UK STREET',          color: '#00f0ff',
    genres: ['grime','ukdrill','ukgarage','jungle','drumandbass','niche','deeprotbassline','bassline','purebassline','ukstreetsoul','eastcoasthiphop'] },
  { id: 'caribbean',  label: 'CARIBBEAN & AFRICAN', color: '#f472b6',
    genres: ['reggae','loversrock','rastadub','ragga','afrobeats','afroswing','amapiano','reggaeton','latintrap','rootsreggae','corridos'] },
  { id: 'soul',       label: 'SOUL & BLUES',        color: '#fb923c',
    genres: ['soul','rnb','soulrnb','blues','bluessoul','deepsoulblues','jazz','swing','vocaljazz','southemsoul','gospel'] },
  { id: 'electronic', label: 'ELECTRONIC & DANCE',  color: '#4ade80',
    genres: ['house','deephouse','technhouse','techno','edm','lofi','electronicfunk','dubstep','driftphonk','jerseyclub','hyperpop','syntheticpop','synthwave'] },
  { id: 'rock',       label: 'ROCK & METAL',        color: '#f87171',
    genres: ['rock','bluesrock','metal','indie','acoustic','country','rockney','countryamericana','rocknroll','traditionalpop'] },
  { id: 'world',      label: 'WORLD & URBAN',       color: '#fbbf24',
    genres: ['hiphop','kpop','bhangra','trap','poprap','trapsoul'] },
  { id: 'classic',    label: 'CLASSIC',             color: '#e2e8f0',
    genres: ['classical','irishjig','irishfolk','pop','meditation','christmas','healingfrequency'] },
];

const GENRE_LABEL: Record<string, string> = {
  hiphop:'Hip-Hop', lofi:'Lo-Fi', edm:'EDM', irishjig:'Irish Jig', irishfolk:'Irish Folk',
  rnb:'R&B', bluessoul:'Blues Soul', drumandbass:'D&B', grime:'Grime', ukgarage:'UK Garage',
  jungle:'Jungle', bassline:'Bassline House', house:'House', deephouse:'Deep House',
  loversrock:'Lovers Rock', ukdrill:'UK Drill', kpop:'K-Pop', deepsoulblues:'Deep Soul Blues',
  ukstreetsoul:'UK Street Soul', technhouse:'Tech House', driftphonk:'Drift Phonk',
  jerseyclub:'Jersey Club', afroswing:'Afroswing', rastadub:'Rasta Dub',
  deeprotbassline:'Deeprot Bassline', jazz:'Jazz', swing:'Swing', vocaljazz:'Vocal Jazz',
  electronicfunk:'Electronic Funk', syntheticpop:'Synthetic Pop', ragga:'Ragga',
  dubstep:'Dubstep', bhangra:'Bhangra', rockney:'Rockney', metal:'Metal', bluesrock:'Blues Rock',
  reggaeton:'Reggaeton', latintrap:'Latin Trap', rootsreggae:'Roots Reggae',
  countryamericana:'Country Americana', southemsoul:'Southern Soul', soulrnb:'Soul R&B',
  traditionalpop:'Traditional Pop', rocknroll:'Rock & Roll', trap:'Trap',
  eastcoasthiphop:'East Coast Hip-Hop', poprap:'Pop Rap', synthwave:'Synthwave',
  gospel:'Gospel', trapsoul:'Trap Soul', meditation:'Meditation', christmas:'Christmas',
  corridos:'Corridos', healingfrequency:'Healing Frequencies', purebassline:'Pure Bassline',
  niche:'Niche', amapiano:'Amapiano', hyperpop:'Hyperpop', techno:'Techno',
  indie:'Indie', acoustic:'Acoustic', country:'Country', classical:'Classical',
  blues:'Blues', soul:'Soul', reggae:'Reggae', pop:'Pop',
};

function glabel(key: string): string {
  return GENRE_LABEL[key] ?? key.charAt(0).toUpperCase() + key.slice(1);
}

function absoluteUrl(path: string | null): string | null {
  if (!path) return null;
  return path.startsWith('http') ? path : `${BACKEND_URL}${path}`;
}

// ─── Types ────────────────────────────────────────────────────────────────────

type Phase     = 'idle' | 'generating' | 'polling' | 'complete' | 'error' | 'timeout';
type VocalMode = 'full' | 'instrumental' | 'intermittent';
interface SongResult { title: string; mp3_url: string; image_url: string | null }

const POLL_MS    = 5_000;
const TIMEOUT_MS = 5 * 60 * 1_000;

const BG: [string, string] = [COLORS.gradientTop, COLORS.gradientBot];

// ─── Screen ───────────────────────────────────────────────────────────────────

export function CreateSongScreen() {
  const [fontsLoaded] = useFonts({ Orbitron_700Bold });
  const orbitron = fontsLoaded ? 'Orbitron_700Bold' : undefined;

  const [brief,        setBrief]        = useState('');
  const [briefFocused, setBriefFocused] = useState(false);
  const [activePreset, setActivePreset] = useState<string | null>(null);
  const [genre,        setGenre]        = useState<string | null>(null);
  const [expanded,     setExpanded]     = useState<Set<string>>(new Set(['uk_street']));
  const [vocalMode,    setVocalMode]    = useState<VocalMode>('full');
  const [phase,        setPhase]        = useState<Phase>('idle');
  const [errorMsg,     setErrorMsg]     = useState('');
  const [result,       setResult]       = useState<SongResult | null>(null);

  const { isPlaying, togglePlay, stop: stopAudio } = useAudioPlayer();
  const pollTimer  = useRef<ReturnType<typeof setInterval> | null>(null);
  const pollStart  = useRef(0);
  const lyricIdRef = useRef<number | null>(null);
  const titleRef   = useRef('Your Song');

  useEffect(() => () => { clearPoll(); }, []);

  function clearPoll() {
    if (pollTimer.current) { clearInterval(pollTimer.current); pollTimer.current = null; }
  }

  function toggleCategory(id: string) {
    setExpanded(prev => {
      const next = new Set(prev);
      next.has(id) ? next.delete(id) : next.add(id);
      return next;
    });
  }

  async function getToken(): Promise<string> {
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
      stopAudio();

      const res = await fetch(API.generate, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${await getToken()}` },
        body: JSON.stringify({
          brief:               brief.trim(),
          genres:              [genre],
          instrumental:        vocalMode === 'instrumental' || undefined,
          intermittent_vocals: vocalMode === 'intermittent' || undefined,
        }),
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
        clearPoll(); setPhase('timeout'); return;
      }
      try {
        const res = await fetch(API.variants(lyricIdRef.current!), {
          headers: { Authorization: `Bearer ${await getToken()}` },
        });
        if (!res.ok) return;
        const data = await res.json();
        const v    = data.variants?.[0];
        if (!v) return;
        if (v.status === 'complete') {
          clearPoll();
          setResult({ title: titleRef.current, mp3_url: absoluteUrl(v.mp3_url)!, image_url: absoluteUrl(v.image_url) });
          setPhase('complete');
        } else if (v.status === 'failed') {
          clearPoll(); setErrorMsg('Song generation failed. Please try again.'); setPhase('error');
        }
      } catch { /* transient — keep polling */ }
    }, POLL_MS);
  }

  async function handlePlay() {
    if (!result) return;
    try { await togglePlay(result.mp3_url); }
    catch (e: any) { Alert.alert('Playback error', e.message); }
  }

  function reset() {
    clearPoll(); stopAudio();
    setPhase('idle'); setResult(null); setErrorMsg('');
    setVocalMode('full');
  }

  // ── Generating / polling ───────────────────────────────────────────────────
  if (phase === 'generating' || phase === 'polling') {
    return (
      <LinearGradient colors={BG} style={{ flex: 1 }}>
        <SafeAreaView style={s.center}>
          <Text style={[s.boltLarge, { fontFamily: orbitron }]}>⚡</Text>
          <ActivityIndicator size="large" color={COLORS.cyan} style={{ marginBottom: 20 }} />
          <Text style={s.statusText}>
            {phase === 'generating'
              ? 'Submitting your song…'
              : 'Generating your song…\nThis usually takes about a minute.'}
          </Text>
        </SafeAreaView>
      </LinearGradient>
    );
  }

  // ── Complete ───────────────────────────────────────────────────────────────
  if (phase === 'complete' && result) {
    return (
      <LinearGradient colors={BG} style={{ flex: 1 }}>
        <SafeAreaView style={s.center}>
          {result.image_url
            ? <Image source={{ uri: result.image_url }} style={s.cover} />
            : <View style={[s.cover, s.coverFallback]}><Text style={{ fontSize: 48 }}>⚡</Text></View>}
          <Text style={[s.songTitle, { fontFamily: orbitron }]} numberOfLines={2}>{result.title}</Text>
          <TouchableOpacity
            style={[s.playBtn, isPlaying && s.playBtnActive]}
            onPress={handlePlay}
          >
            <Text style={s.playBtnText}>{isPlaying ? '⏸  Pause' : '▶  Play'}</Text>
          </TouchableOpacity>
          <TouchableOpacity style={s.secondaryBtn} onPress={reset}>
            <Text style={s.secondaryBtnText}>Create another</Text>
          </TouchableOpacity>
        </SafeAreaView>
      </LinearGradient>
    );
  }

  // ── Error / timeout ────────────────────────────────────────────────────────
  if (phase === 'error' || phase === 'timeout') {
    return (
      <LinearGradient colors={BG} style={{ flex: 1 }}>
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
      </LinearGradient>
    );
  }

  // ── Idle form ──────────────────────────────────────────────────────────────
  return (
    <LinearGradient colors={BG} style={{ flex: 1 }}>
      <SafeAreaView style={{ flex: 1, backgroundColor: 'transparent' }}>
        <KeyboardAvoidingView
          style={{ flex: 1 }}
          behavior={Platform.OS === 'ios' ? 'padding' : undefined}
        >
          <TouchableWithoutFeedback onPress={Keyboard.dismiss} accessible={false}>
            <ScrollView
              contentContainerStyle={s.scroll}
              keyboardShouldPersistTaps="handled"
              showsVerticalScrollIndicator={false}
            >

              {/* ── Heading ─────────────────────────────────────────────── */}
              <Text style={[s.heading, { fontFamily: orbitron }]}>⚡ CREATE</Text>

              {/* ── Vibe presets ─────────────────────────────────────────── */}
              <Text style={s.sectionLabel}>VIBE</Text>
              <ScrollView
                horizontal
                showsHorizontalScrollIndicator={false}
                contentContainerStyle={s.vibeRow}
              >
                {SONG_TEMPLATES.map(tpl => {
                  const active = activePreset === tpl.label;
                  return (
                    <TouchableOpacity
                      key={tpl.label}
                      style={[s.vibeChip, active && s.vibeChipActive]}
                      onPress={() => {
                        const next = active ? null : tpl.label;
                        setActivePreset(next);
                        setBrief(next ? tpl.value : '');
                      }}
                    >
                      <Text style={s.vibeEmoji}>{tpl.emoji}</Text>
                      <Text style={[s.vibeLabel, active && s.vibeLabelActive]}>{tpl.label}</Text>
                    </TouchableOpacity>
                  );
                })}
              </ScrollView>

              {/* ── Brief input ──────────────────────────────────────────── */}
              <Text style={s.sectionLabel}>DESCRIBE YOUR SONG</Text>
              <TextInput
                style={[s.briefInput, briefFocused && s.briefInputFocused]}
                placeholder="A summer anthem about chasing dreams…"
                placeholderTextColor={COLORS.textMuted}
                multiline
                blurOnSubmit
                returnKeyType="done"
                maxLength={2000}
                value={brief}
                onChangeText={t => { setBrief(t); if (activePreset) setActivePreset(null); }}
                onFocus={() => setBriefFocused(true)}
                onBlur={() => setBriefFocused(false)}
                textAlignVertical="top"
              />

              {/* ── Genre categories ─────────────────────────────────────── */}
              <Text style={s.sectionLabel}>
                GENRE <Text style={{ color: COLORS.cyan }}>*</Text>
              </Text>
              {GENRE_CATEGORIES.map(cat => {
                const isOpen = expanded.has(cat.id);
                return (
                  <View key={cat.id} style={s.categoryBlock}>
                    <TouchableOpacity
                      style={s.categoryHeader}
                      onPress={() => toggleCategory(cat.id)}
                    >
                      <View style={[s.categoryDot, { backgroundColor: cat.color }]} />
                      <Text style={[s.categoryLabel, { color: cat.color }]}>{cat.label}</Text>
                      <Text style={[s.categoryChevron, { color: cat.color }]}>
                        {isOpen ? '▾' : '▸'}
                      </Text>
                    </TouchableOpacity>
                    {isOpen && (
                      <View style={s.chipGrid}>
                        {cat.genres.map(key => {
                          const selected = genre === key;
                          return (
                            <TouchableOpacity
                              key={key}
                              style={[
                                s.chip,
                                selected && {
                                  borderColor:       cat.color,
                                  backgroundColor:   `${cat.color}1a`,
                                  shadowColor:       cat.color,
                                  shadowOffset:      { width: 0, height: 0 },
                                  shadowOpacity:     0.9,
                                  shadowRadius:      8,
                                  elevation:         6,
                                },
                              ]}
                              onPress={() => setGenre(selected ? null : key)}
                            >
                              <Text style={[s.chipText, selected && { color: cat.color, fontWeight: '700' }]}>
                                {glabel(key)}
                              </Text>
                            </TouchableOpacity>
                          );
                        })}
                      </View>
                    )}
                  </View>
                );
              })}

              {/* ── Vocal mode ──────────────────────────────────────────── */}
              <Text style={[s.sectionLabel, { marginTop: 24 }]}>VOCAL MODE</Text>
              <View style={s.vocalRow}>
                {([
                  { value: 'full',         label: '🎵 Full Vocals' },
                  { value: 'instrumental', label: '🎹 Instrumental' },
                  { value: 'intermittent', label: '🎤 Intermittent' },
                ] as { value: VocalMode; label: string }[]).map(({ value, label }) => {
                  const active = vocalMode === value;
                  return (
                    <TouchableOpacity
                      key={value}
                      style={[s.vocalChip, active && s.vocalChipActive]}
                      onPress={() => setVocalMode(value)}
                    >
                      <Text style={[s.vocalChipText, active && s.vocalChipTextActive]}>
                        {label}
                      </Text>
                    </TouchableOpacity>
                  );
                })}
              </View>

              {/* ── Create button ─────────────────────────────────────────── */}
              <TouchableOpacity
                style={[
                  s.createBtn,
                  !genre && s.createBtnDisabled,
                  genre != null && {
                    shadowColor:   COLORS.purple,
                    shadowOffset:  { width: 0, height: 0 },
                    shadowOpacity: 0.85,
                    shadowRadius:  18,
                    elevation:     10,
                  },
                ]}
                onPress={handleCreate}
                disabled={!genre}
              >
                <Text style={[s.createBtnText, { fontFamily: orbitron }]}>CREATE</Text>
              </TouchableOpacity>

            </ScrollView>
          </TouchableWithoutFeedback>
        </KeyboardAvoidingView>
      </SafeAreaView>
    </LinearGradient>
  );
}

// ─── Styles ───────────────────────────────────────────────────────────────────

const s = StyleSheet.create({
  center: {
    flex: 1, alignItems: 'center', justifyContent: 'center',
    padding: 24, backgroundColor: 'transparent',
  },
  scroll: { padding: 20, paddingBottom: 60 },

  // ── Heading
  heading: {
    fontSize: 28, fontWeight: '900', color: COLORS.cyan,
    marginBottom: 24, letterSpacing: 2,
    textShadowColor: COLORS.cyan,
    textShadowOffset: { width: 0, height: 0 },
    textShadowRadius: 16,
  },
  boltLarge: {
    fontSize: 52, marginBottom: 16, color: COLORS.cyan,
    textShadowColor: COLORS.cyan,
    textShadowOffset: { width: 0, height: 0 },
    textShadowRadius: 22,
  },

  // ── Section label
  sectionLabel: {
    fontSize: 10, fontWeight: '700', color: COLORS.textMuted,
    letterSpacing: 1.5, marginBottom: 10, marginTop: 20,
  },

  // ── Vibe presets
  vibeRow: { gap: 8, paddingBottom: 4, paddingRight: 20 },
  vibeChip: {
    paddingHorizontal: 14, paddingVertical: 10, borderRadius: 20,
    borderWidth: 1, borderColor: 'rgba(0,240,255,0.15)',
    backgroundColor: 'rgba(0,240,255,0.03)',
    alignItems: 'center',
  },
  vibeChipActive: {
    borderColor: COLORS.cyan,
    backgroundColor: 'rgba(0,240,255,0.12)',
    shadowColor: COLORS.cyan,
    shadowOffset: { width: 0, height: 0 },
    shadowOpacity: 0.7,
    shadowRadius: 6,
    elevation: 4,
  },
  vibeEmoji: { fontSize: 18, marginBottom: 3 },
  vibeLabel: { fontSize: 11, fontWeight: '600', color: COLORS.textMuted },
  vibeLabelActive: { color: COLORS.cyan },

  // ── Brief input
  briefInput: {
    backgroundColor: 'rgba(0,0,0,0.5)',
    borderWidth: 1, borderColor: 'rgba(0,240,255,0.15)',
    borderRadius: RADIUS.md,
    color: COLORS.white, padding: 14, fontSize: 15,
    minHeight: 100,
  },
  briefInputFocused: {
    borderColor: COLORS.cyan,
    shadowColor: COLORS.cyan,
    shadowOffset: { width: 0, height: 0 },
    shadowOpacity: 0.35,
    shadowRadius: 8,
  },

  // ── Genre categories
  categoryBlock: { marginBottom: 2 },
  categoryHeader: {
    flexDirection: 'row', alignItems: 'center', gap: 8,
    paddingVertical: 10, paddingHorizontal: 2,
  },
  categoryDot: { width: 6, height: 6, borderRadius: 3 },
  categoryLabel: { flex: 1, fontSize: 10, fontWeight: '700', letterSpacing: 1.5 },
  categoryChevron: { fontSize: 14, fontWeight: '700' },
  chipGrid: {
    flexDirection: 'row', flexWrap: 'wrap', gap: 8,
    paddingBottom: 10, paddingLeft: 14,
  },
  chip: {
    paddingHorizontal: 12, paddingVertical: 7, borderRadius: 16,
    borderWidth: 1, borderColor: 'rgba(255,255,255,0.08)',
    backgroundColor: 'rgba(255,255,255,0.04)',
  },
  chipText: { fontSize: 12, fontWeight: '500', color: COLORS.textMuted },

  // ── Vocal mode
  vocalRow: { flexDirection: 'row', flexWrap: 'wrap', gap: 8 },
  vocalChip: {
    paddingHorizontal: 14, paddingVertical: 8, borderRadius: 20,
    borderWidth: 1, borderColor: 'rgba(255,255,255,0.08)',
    backgroundColor: 'rgba(255,255,255,0.04)',
  },
  vocalChipActive: {
    borderColor: COLORS.purple,
    backgroundColor: 'rgba(124,58,237,0.15)',
    shadowColor: COLORS.purple,
    shadowOffset: { width: 0, height: 0 },
    shadowOpacity: 0.7,
    shadowRadius: 6,
    elevation: 4,
  },
  vocalChipText: { fontSize: 12, fontWeight: '500', color: COLORS.textMuted },
  vocalChipTextActive: { color: '#c4b5fd', fontWeight: '700' },

  // ── Create button
  createBtn: {
    marginTop: 32,
    backgroundColor: COLORS.purple,
    borderRadius: RADIUS.md,
    paddingVertical: 17,
    alignItems: 'center',
    borderWidth: 1,
    borderColor: 'rgba(0,240,255,0.25)',
  },
  createBtnDisabled: { opacity: 0.35 },
  createBtnText: {
    color: COLORS.white, fontSize: 15, fontWeight: '700', letterSpacing: 2,
  },

  // ── Status / error
  statusText: {
    color: COLORS.textPrimary, fontSize: 15, textAlign: 'center', lineHeight: 24,
  },
  errorText: {
    color: COLORS.errorText, fontSize: 15, textAlign: 'center',
    lineHeight: 24, marginBottom: 24,
  },

  // ── Complete screen
  cover: { width: 220, height: 220, borderRadius: RADIUS.lg, marginBottom: 20 },
  coverFallback: {
    backgroundColor: COLORS.bgCard, alignItems: 'center', justifyContent: 'center',
  },
  songTitle: {
    color: COLORS.white, fontSize: 20, fontWeight: '700',
    textAlign: 'center', marginBottom: 28, paddingHorizontal: 16,
  },
  playBtn: {
    backgroundColor: COLORS.purple,
    borderRadius: RADIUS.md,
    paddingVertical: 14, paddingHorizontal: 48,
    marginBottom: 14,
    shadowColor: COLORS.purple,
    shadowOffset: { width: 0, height: 0 },
    shadowOpacity: 0.7,
    shadowRadius: 14,
    elevation: 8,
  },
  playBtnActive: { backgroundColor: '#1e0060' },
  playBtnText: { color: COLORS.white, fontSize: 16, fontWeight: '700' },

  // ── Secondary (retry / create another)
  secondaryBtn: {
    borderWidth: 1, borderColor: 'rgba(0,240,255,0.2)',
    borderRadius: RADIUS.md,
    paddingVertical: 12, paddingHorizontal: 32,
  },
  secondaryBtnText: { color: COLORS.textMuted, fontSize: 14 },
});
