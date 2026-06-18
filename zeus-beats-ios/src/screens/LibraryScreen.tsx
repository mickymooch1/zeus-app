import React, { useState, useCallback } from 'react';
import {
  View, Text, Image, FlatList, StyleSheet,
  ActivityIndicator, RefreshControl, Alert,
} from 'react-native';
import { TouchableOpacity } from 'react-native-gesture-handler';
import { SafeAreaView } from 'react-native-safe-area-context';
import * as SecureStore from 'expo-secure-store';
import { useAudioPlayer } from '../hooks/useAudioPlayer';
import { COLORS, RADIUS } from '../constants/theme';
import { BACKEND_URL, TOKEN_KEY } from '../constants/api';
import { useFocusEffect } from '@react-navigation/native';

const GENRE_LABEL: Record<string, string> = {
  hiphop:'Hip-Hop', lofi:'Lo-Fi', edm:'EDM', rnb:'R&B', bluessoul:'Blues Soul',
  drumandbass:'D&B', ukgarage:'UK Garage', bassline:'Bassline House',
  loversrock:'Lovers Rock', ukdrill:'UK Drill', kpop:'K-Pop',
  deepsoulblues:'Deep Soul Blues', ukstreetsoul:'UK Street Soul',
  technhouse:'Tech House', driftphonk:'Drift Phonk', jerseyclub:'Jersey Club',
  afroswing:'Afroswing', rastadub:'Rasta Dub', deeprotbassline:'Deeprot Bassline',
  vocaljazz:'Vocal Jazz', electronicfunk:'Electronic Funk', syntheticpop:'Synthetic Pop',
  dubstep:'Dubstep', rockney:'Rockney', reggaeton:'Reggaeton', latintrap:'Latin Trap',
  rootsreggae:'Roots Reggae', countryamericana:'Country Americana',
  southemsoul:'Southern Soul', traditionalpop:'Traditional Pop',
  rocknroll:'Rock & Roll', eastcoasthiphop:'East Coast Hip-Hop', poprap:'Pop Rap',
  synthwave:'Synthwave', trapsoul:'Trap Soul', healingfrequency:'Healing Frequencies',
  purebassline:'Pure Bassline', deephouse:'Deep House', irishjig:'Irish Jig',
  irishfolk:'Irish Folk',
};

function genreLabel(tag: string): string {
  return GENRE_LABEL[tag] ?? tag.charAt(0).toUpperCase() + tag.slice(1);
}

function abs(path: string | null): string | null {
  if (!path) return null;
  return path.startsWith('http') ? path : `${BACKEND_URL}${path}`;
}

interface Song {
  lyricId:   number;
  variantId: number;
  title:     string;
  mp3Url:    string;
  imageUrl:  string | null;
  genreTag:  string;
}

async function fetchLibrary(): Promise<Song[]> {
  const token = await SecureStore.getItemAsync(TOKEN_KEY);
  if (!token) throw new Error('Not signed in');

  const headers = { Authorization: `Bearer ${token}` };

  const lyricsRes = await fetch(`${BACKEND_URL}/api/lyrics`, { headers });
  if (!lyricsRes.ok) throw new Error(`Failed to load library (${lyricsRes.status})`);
  const { lyrics } = await lyricsRes.json();
  if (!lyrics?.length) return [];

  const variantResults = await Promise.all(
    lyrics.map((l: { id: number; title: string }) =>
      fetch(`${BACKEND_URL}/api/lyrics/${l.id}/variants`, { headers })
        .then(r => r.ok ? r.json() : null)
        .catch(() => null)
    )
  );

  const songs: Song[] = [];
  variantResults.forEach((data, i) => {
    const v = data?.variants?.[0];
    if (!v || v.status !== 'complete' || !v.mp3_url) return;
    songs.push({
      lyricId:   lyrics[i].id,
      variantId: v.variant_id,
      title:     lyrics[i].title || 'Untitled',
      mp3Url:    abs(v.mp3_url)!,
      imageUrl:  abs(v.image_url),
      genreTag:  v.genre_tag || '',
    });
  });

  return songs;
}

function SongCard({
  song, isPlaying, onPress,
}: {
  song: Song;
  isPlaying: boolean;
  onPress: () => void;
}) {
  return (
    <TouchableOpacity style={s.card} onPress={onPress} activeOpacity={0.75}>
      {song.imageUrl
        ? <Image source={{ uri: song.imageUrl }} style={s.cover} />
        : <View style={[s.cover, s.coverFallback]}><Text style={s.fallbackIcon}>⚡</Text></View>}
      <View style={s.cardInfo}>
        <Text style={s.cardTitle} numberOfLines={2}>{song.title}</Text>
        <Text style={s.cardGenre}>{genreLabel(song.genreTag)}</Text>
      </View>
      <Text style={[s.playIcon, isPlaying && s.playIconActive]}>
        {isPlaying ? '⏸' : '▶'}
      </Text>
    </TouchableOpacity>
  );
}

export function LibraryScreen() {
  const [songs,      setSongs]      = useState<Song[]>([]);
  const [loading,    setLoading]    = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error,      setError]      = useState<string | null>(null);

  const { playingUrl, isPlaying, togglePlay } = useAudioPlayer();

  const load = useCallback(async (isRefresh = false) => {
    if (isRefresh) setRefreshing(true); else setLoading(true);
    setError(null);
    try {
      setSongs(await fetchLibrary());
    } catch (e: any) {
      setError(e.message || 'Failed to load library.');
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, []);

  // Reload whenever the tab comes into focus so new songs appear after Create
  useFocusEffect(useCallback(() => { load(); }, [load]));

  async function handlePress(song: Song) {
    try {
      await togglePlay(song.mp3Url);
    } catch (e: any) {
      Alert.alert('Playback error', e.message);
    }
  }

  if (loading) {
    return (
      <SafeAreaView style={s.center}>
        <ActivityIndicator size="large" color={COLORS.cyan} />
      </SafeAreaView>
    );
  }

  if (error) {
    return (
      <SafeAreaView style={s.center}>
        <Text style={s.errorText}>{error}</Text>
        <TouchableOpacity style={s.retryBtn} onPress={() => load()}>
          <Text style={s.retryBtnText}>Retry</Text>
        </TouchableOpacity>
      </SafeAreaView>
    );
  }

  return (
    <SafeAreaView style={s.safeArea}>
      <FlatList
        data={songs}
        keyExtractor={item => String(item.variantId)}
        renderItem={({ item }) => (
          <SongCard
            song={item}
            isPlaying={playingUrl === item.mp3Url && isPlaying}
            onPress={() => handlePress(item)}
          />
        )}
        contentContainerStyle={songs.length === 0 ? s.emptyContainer : s.list}
        refreshControl={
          <RefreshControl
            refreshing={refreshing}
            onRefresh={() => load(true)}
            tintColor={COLORS.cyan}
          />
        }
        ListEmptyComponent={
          <View style={s.emptyInner}>
            <Text style={s.emptyIcon}>🎵</Text>
            <Text style={s.emptyTitle}>No songs yet</Text>
            <Text style={s.emptyHint}>Create one in the ⚡ Create tab</Text>
          </View>
        }
      />
    </SafeAreaView>
  );
}

const s = StyleSheet.create({
  safeArea: { flex: 1, backgroundColor: COLORS.bg },
  center:   { flex: 1, backgroundColor: COLORS.bg, alignItems: 'center', justifyContent: 'center', padding: 24 },
  list:     { padding: 16, paddingBottom: 32 },

  emptyContainer: { flexGrow: 1, justifyContent: 'center', alignItems: 'center', padding: 24 },
  emptyInner:     { alignItems: 'center', gap: 8 },
  emptyIcon:      { fontSize: 48, marginBottom: 4 },
  emptyTitle:     { fontSize: 18, fontWeight: '700', color: COLORS.textPrimary },
  emptyHint:      { fontSize: 13, color: COLORS.textMuted, textAlign: 'center' },

  card: {
    flexDirection:  'row',
    alignItems:     'center',
    backgroundColor: COLORS.bgCard,
    borderWidth:    1,
    borderColor:    COLORS.borderDim,
    borderRadius:   RADIUS.md,
    padding:        12,
    marginBottom:   10,
    gap:            12,
  },
  cover: {
    width: 64, height: 64,
    borderRadius: RADIUS.sm,
    backgroundColor: COLORS.inputBg,
  },
  coverFallback: { alignItems: 'center', justifyContent: 'center' },
  fallbackIcon:  { fontSize: 28 },

  cardInfo:  { flex: 1, gap: 4 },
  cardTitle: { fontSize: 15, fontWeight: '700', color: COLORS.white },
  cardGenre: { fontSize: 12, color: COLORS.cyan, fontWeight: '500' },

  playIcon:       { fontSize: 22, color: COLORS.textMuted, paddingHorizontal: 4 },
  playIconActive: { color: COLORS.cyan },

  errorText: { color: COLORS.errorText, fontSize: 15, textAlign: 'center', marginBottom: 20 },
  retryBtn:  {
    borderWidth: 1, borderColor: COLORS.borderDim,
    borderRadius: RADIUS.md, paddingVertical: 12, paddingHorizontal: 32,
  },
  retryBtnText: { color: COLORS.textMuted, fontSize: 14 },
});
