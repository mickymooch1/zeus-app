import React, { useState, useEffect } from 'react';
import {
  View, Text, TextInput, TouchableOpacity,
  StyleSheet, Alert, ScrollView, Share, Platform,
} from 'react-native';
import AsyncStorage from '@react-native-async-storage/async-storage';

const DEFAULT_URL = 'https://zeus-app-production.up.railway.app';

export function SettingsScreen({ navigation }: any) {
  const [editingUrl, setEditingUrl] = useState(DEFAULT_URL);
  const [savedUrl, setSavedUrl] = useState(DEFAULT_URL);

  useEffect(() => {
    AsyncStorage.getItem('zeus_backend_url').then(url => {
      const u = url || DEFAULT_URL;
      setEditingUrl(u);
      setSavedUrl(u);
    });
  }, []);

  const saveUrl = async () => {
    const trimmed = editingUrl.trim();
    if (!trimmed.startsWith('http')) {
      Alert.alert('Invalid URL', 'URL must start with http:// or https://');
      return;
    }
    await AsyncStorage.setItem('zeus_backend_url', trimmed);
    setSavedUrl(trimmed);
    Alert.alert('Saved', 'Backend URL updated. Restart the app to reconnect.');
  };

  const handleNotifications = () => {
    if (Platform.OS === 'ios') {
      Alert.alert(
        'Push Notifications',
        'To manage Zeus Beats notifications, go to iOS Settings → Zeus Beats → Notifications.',
        [{ text: 'OK' }],
      );
    } else {
      Alert.alert('Notifications', 'Push notifications are configured in device settings.');
    }
  };

  const handleShare = async () => {
    try {
      await Share.share({
        message: 'Creating music with Zeus Beats — AI-powered music creation! ⚡',
        title: 'Zeus Beats',
      });
    } catch {
      // user cancelled — do nothing
    }
  };

  const handleLogout = async () => {
    Alert.alert('Sign Out', 'Are you sure you want to sign out?', [
      { text: 'Cancel', style: 'cancel' },
      {
        text: 'Sign Out', style: 'destructive',
        onPress: async () => {
          await AsyncStorage.removeItem('zeus_token');
          navigation.reset({ index: 0, routes: [{ name: 'Login' }] });
        },
      },
    ]);
  };

  return (
    <ScrollView style={styles.container} contentContainerStyle={styles.inner}>
      <Text style={styles.sectionLabel}>NOTIFICATIONS</Text>
      <TouchableOpacity style={styles.row} onPress={handleNotifications} activeOpacity={0.7}>
        <Text style={styles.rowIcon}>🔔</Text>
        <Text style={styles.rowText}>Push Notifications</Text>
        <Text style={styles.rowArrow}>›</Text>
      </TouchableOpacity>

      <Text style={styles.sectionLabel}>SHARE</Text>
      <TouchableOpacity style={styles.row} onPress={handleShare} activeOpacity={0.7}>
        <Text style={styles.rowIcon}>📤</Text>
        <Text style={styles.rowText}>Share Zeus Beats</Text>
        <Text style={styles.rowArrow}>›</Text>
      </TouchableOpacity>

      <Text style={styles.sectionLabel}>SERVER CONNECTION</Text>
      <View style={styles.urlCard}>
        <Text style={styles.urlHint}>
          Railway URL (default) or your own server / Cloudflare tunnel for self-hosting.
        </Text>
        <TextInput
          style={styles.urlInput}
          value={editingUrl}
          onChangeText={setEditingUrl}
          placeholder="https://..."
          placeholderTextColor="#555"
          autoCapitalize="none"
          autoCorrect={false}
          keyboardType="url"
        />
        <TouchableOpacity style={styles.saveBtn} onPress={saveUrl} activeOpacity={0.8}>
          <Text style={styles.saveBtnText}>Save & Reconnect</Text>
        </TouchableOpacity>
        {savedUrl !== DEFAULT_URL && (
          <Text style={styles.customUrlNote}>Using: {savedUrl}</Text>
        )}
      </View>

      <Text style={styles.sectionLabel}>ACCOUNT</Text>
      <TouchableOpacity style={[styles.row, styles.logoutRow]} onPress={handleLogout} activeOpacity={0.7}>
        <Text style={styles.rowIcon}>⏻</Text>
        <Text style={[styles.rowText, styles.logoutText]}>Sign Out</Text>
      </TouchableOpacity>

      <Text style={styles.version}>Zeus Beats · AI Music Creation</Text>
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#0f0c29' },
  inner: { paddingBottom: 48 },
  sectionLabel: {
    color: '#555', fontSize: 10, fontWeight: '700',
    letterSpacing: 1.2, padding: 16, paddingBottom: 6, marginTop: 8,
    textTransform: 'uppercase',
  },
  row: {
    flexDirection: 'row', alignItems: 'center',
    backgroundColor: 'rgba(255,255,255,0.04)',
    marginHorizontal: 16, borderRadius: 10, padding: 14,
    marginBottom: 4,
  },
  rowIcon: { fontSize: 18, marginRight: 12, width: 26, textAlign: 'center' },
  rowText: { color: '#e2d9f3', fontSize: 15, flex: 1 },
  rowArrow: { color: '#555', fontSize: 20, fontWeight: '300' },
  logoutRow: { backgroundColor: 'rgba(239,68,68,0.08)' },
  logoutText: { color: '#fca5a5' },
  urlCard: {
    marginHorizontal: 16,
    backgroundColor: 'rgba(255,255,255,0.04)',
    borderRadius: 10, padding: 14,
  },
  urlHint: { color: '#555', fontSize: 11, marginBottom: 10, lineHeight: 16 },
  urlInput: {
    backgroundColor: 'rgba(0,0,0,0.3)',
    borderWidth: 1, borderColor: 'rgba(255,255,255,0.1)',
    borderRadius: 8, padding: 10,
    color: '#e2d9f3', fontSize: 13, marginBottom: 10,
  },
  saveBtn: {
    backgroundColor: 'rgba(167,139,250,0.2)',
    borderRadius: 8, padding: 10, alignItems: 'center',
  },
  saveBtnText: { color: '#a78bfa', fontWeight: '600', fontSize: 14 },
  customUrlNote: { color: '#555', fontSize: 10, marginTop: 8, textAlign: 'center' },
  version: {
    color: '#2a2a4a', fontSize: 12, textAlign: 'center',
    marginTop: 40, letterSpacing: 0.5,
  },
});
