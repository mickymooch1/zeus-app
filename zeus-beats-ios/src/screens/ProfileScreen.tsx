import React from 'react';
import {
  View, Text, StyleSheet, Linking, Alert,
} from 'react-native';
import { TouchableOpacity } from 'react-native-gesture-handler';
import { SafeAreaView } from 'react-native-safe-area-context';
import { LinearGradient } from 'expo-linear-gradient';
import { useFonts, Orbitron_700Bold } from '@expo-google-fonts/orbitron';
import { useAuth } from '../context/AuthContext';
import { COLORS, RADIUS } from '../constants/theme';

const BG: [string, string] = [COLORS.gradientTop, COLORS.gradientBot];
const UPGRADE_URL = 'https://zeusbeats.com';

function initialOf(name: string | undefined, email: string): string {
  const source = (name && name.trim()) || email;
  return source.charAt(0).toUpperCase() || '⚡';
}

function displayName(name: string | undefined, email: string): string {
  if (name && name.trim()) return name.trim();
  // Fall back to the local part of the email so there's always a friendly label
  return email.split('@')[0];
}

export function ProfileScreen() {
  const [fontsLoaded] = useFonts({ Orbitron_700Bold });
  const orbitron = fontsLoaded ? 'Orbitron_700Bold' : undefined;

  const { user, logout } = useAuth();
  const email = user?.email ?? '';
  const name  = user?.name;

  async function handleUpgrade() {
    try {
      await Linking.openURL(UPGRADE_URL);
    } catch {
      Alert.alert('Could not open link', 'Visit zeusbeats.com in your browser to upgrade.');
    }
  }

  function handleSignOut() {
    Alert.alert(
      'Sign out',
      'Are you sure you want to sign out?',
      [
        { text: 'Cancel', style: 'cancel' },
        { text: 'Sign out', style: 'destructive', onPress: () => { logout(); } },
      ],
    );
  }

  return (
    <LinearGradient colors={BG} style={{ flex: 1 }}>
      <SafeAreaView style={s.safeArea} edges={['top', 'left', 'right']}>
        <Text style={[s.heading, { fontFamily: orbitron }]}>PROFILE</Text>

        {/* ── Identity card ─────────────────────────────────────────── */}
        <View style={s.card}>
          <View style={s.avatar}>
            <Text style={[s.avatarText, { fontFamily: orbitron }]}>
              {initialOf(name, email)}
            </Text>
          </View>
          <Text style={s.name} numberOfLines={1}>{displayName(name, email)}</Text>
          <Text style={s.email} numberOfLines={1}>{email}</Text>
        </View>

        {/* ── Upgrade link (no pricing / no in-app purchase) ────────── */}
        <TouchableOpacity style={s.linkRow} onPress={handleUpgrade} activeOpacity={0.7}>
          <Text style={s.linkText}>
            To upgrade your plan, visit{' '}
            <Text style={s.linkAccent}>zeusbeats.com</Text>
          </Text>
          <Text style={s.linkChevron}>›</Text>
        </TouchableOpacity>

        <View style={{ flex: 1 }} />

        {/* ── Sign out ──────────────────────────────────────────────── */}
        <TouchableOpacity style={s.signOutBtn} onPress={handleSignOut} activeOpacity={0.8}>
          <Text style={s.signOutText}>Sign out</Text>
        </TouchableOpacity>

        <Text style={s.footer}>Zeus Beats · AI music creation</Text>
      </SafeAreaView>
    </LinearGradient>
  );
}

const s = StyleSheet.create({
  safeArea: { flex: 1, paddingHorizontal: 20, paddingBottom: 20 },

  heading: {
    fontSize: 28, fontWeight: '900', color: COLORS.cyan,
    marginTop: 8, marginBottom: 28, letterSpacing: 2,
    textShadowColor: COLORS.cyan,
    textShadowOffset: { width: 0, height: 0 },
    textShadowRadius: 16,
  },

  // ── Identity card
  card: {
    alignItems: 'center',
    backgroundColor: COLORS.bgCard,
    borderWidth: 1, borderColor: COLORS.borderDim,
    borderRadius: RADIUS.lg,
    paddingVertical: 28, paddingHorizontal: 20,
  },
  avatar: {
    width: 84, height: 84, borderRadius: 42,
    backgroundColor: 'rgba(124,58,237,0.18)',
    borderWidth: 2, borderColor: COLORS.cyan,
    alignItems: 'center', justifyContent: 'center',
    marginBottom: 16,
    shadowColor: COLORS.cyan,
    shadowOffset: { width: 0, height: 0 },
    shadowOpacity: 0.6, shadowRadius: 14,
    elevation: 8,
  },
  avatarText: { fontSize: 34, fontWeight: '900', color: COLORS.cyan },
  name:  { fontSize: 20, fontWeight: '700', color: COLORS.white, marginBottom: 4 },
  email: { fontSize: 14, color: COLORS.cyan, fontWeight: '500' },

  // ── Upgrade link row
  linkRow: {
    flexDirection: 'row', alignItems: 'center',
    backgroundColor: 'rgba(255,255,255,0.03)',
    borderWidth: 1, borderColor: 'rgba(0,240,255,0.15)',
    borderRadius: RADIUS.md,
    paddingVertical: 16, paddingHorizontal: 16,
    marginTop: 20,
  },
  linkText:    { flex: 1, fontSize: 14, color: COLORS.textPrimary, lineHeight: 20 },
  linkAccent:  { color: COLORS.cyan, fontWeight: '700' },
  linkChevron: { fontSize: 22, color: COLORS.textMuted, marginLeft: 8 },

  // ── Sign out
  signOutBtn: {
    borderWidth: 1, borderColor: 'rgba(239,68,68,0.5)',
    backgroundColor: 'rgba(239,68,68,0.10)',
    borderRadius: RADIUS.md,
    paddingVertical: 16, alignItems: 'center',
  },
  signOutText: { color: '#fca5a5', fontSize: 15, fontWeight: '700', letterSpacing: 0.5 },

  footer: {
    textAlign: 'center', color: COLORS.textMuted,
    fontSize: 11, marginTop: 16, letterSpacing: 0.5,
  },
});
