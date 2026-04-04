import React, { useState, useEffect } from 'react';
import {
  View, FlatList, Text, TouchableOpacity, StyleSheet,
  TextInput, Alert,
} from 'react-native';
import AsyncStorage from '@react-native-async-storage/async-storage';

const DEFAULT_URL = 'http://10.0.2.2:8000';

export function SessionsScreen({ navigation }) {
  const [sessions, setSessions] = useState([]);
  const [backendUrl, setBackendUrl] = useState(DEFAULT_URL);
  const [editingUrl, setEditingUrl] = useState(DEFAULT_URL);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    AsyncStorage.getItem('zeus_backend_url').then(url => {
      const u = url || DEFAULT_URL;
      setBackendUrl(u);
      setEditingUrl(u);
      loadSessions(u);
    });
  }, []);

  const loadSessions = (url) => {
    setLoading(true);
    fetch(`${url}/sessions`)
      .then(r => r.json())
      .then(data => { setSessions(data); setLoading(false); })
      .catch(() => { setLoading(false); });
  };

  const saveUrl = async () => {
    const trimmed = editingUrl.trim();
    await AsyncStorage.setItem('zeus_backend_url', trimmed);
    setBackendUrl(trimmed);
    loadSessions(trimmed);
  };

  return (
    <View style={styles.container}>
      <View style={styles.urlSection}>
        <Text style={styles.urlLabel}>Backend URL</Text>
        <Text style={styles.urlHint}>
          Use your Cloudflare tunnel URL when away from home.{'\n'}
          On emulator/home WiFi: {DEFAULT_URL}
        </Text>
        <TextInput
          style={styles.urlInput}
          value={editingUrl}
          onChangeText={setEditingUrl}
          placeholder="https://xxxx.trycloudflare.com"
          placeholderTextColor="#555"
          autoCapitalize="none"
          autoCorrect={false}
          keyboardType="url"
        />
        <TouchableOpacity style={styles.saveBtn} onPress={saveUrl}>
          <Text style={styles.saveBtnText}>Connect</Text>
        </TouchableOpacity>
      </View>

      <Text style={styles.sectionLabel}>RECENT SESSIONS</Text>

      <FlatList
        data={sessions}
        keyExtractor={item => item.id}
        renderItem={({ item }) => (
          <TouchableOpacity
            style={styles.sessionItem}
            onPress={() => navigation.navigate('Chat')}
          >
            <Text style={styles.preview}>{item.preview || 'Session'}</Text>
            <Text style={styles.meta}>
              {item.turns} turn{item.turns !== 1 ? 's' : ''} ·{' '}
              {new Date(item.started).toLocaleDateString()}
            </Text>
          </TouchableOpacity>
        )}
        ListEmptyComponent={
          <Text style={styles.empty}>
            {loading ? 'Loading...' : 'No sessions yet.'}
          </Text>
        }
      />
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#0f0c29' },
  urlSection: {
    padding: 16, borderBottomWidth: 1,
    borderBottomColor: 'rgba(255,255,255,0.07)',
  },
  urlLabel: { color: '#a78bfa', fontSize: 11, fontWeight: '700', letterSpacing: 0.8, marginBottom: 4 },
  urlHint: { color: '#555', fontSize: 10, lineHeight: 14, marginBottom: 8 },
  urlInput: {
    backgroundColor: 'rgba(0,0,0,0.3)',
    borderWidth: 1, borderColor: 'rgba(255,255,255,0.1)',
    borderRadius: 8, padding: 10,
    color: '#e2d9f3', fontSize: 13, marginBottom: 8,
  },
  saveBtn: {
    backgroundColor: 'rgba(167,139,250,0.2)',
    borderRadius: 8, padding: 10, alignItems: 'center',
  },
  saveBtnText: { color: '#a78bfa', fontWeight: '600' },
  sectionLabel: {
    color: '#555', fontSize: 9, fontWeight: '600',
    letterSpacing: 0.8, padding: 12, paddingBottom: 4,
  },
  sessionItem: {
    padding: 16, borderBottomWidth: 1,
    borderBottomColor: 'rgba(255,255,255,0.05)',
  },
  preview: { color: '#e2d9f3', fontSize: 14 },
  meta: { color: '#555', fontSize: 11, marginTop: 3 },
  empty: { color: '#555', textAlign: 'center', padding: 24, fontSize: 13 },
});
