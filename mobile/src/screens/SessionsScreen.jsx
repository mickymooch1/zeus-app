import React, { useState, useEffect, useCallback } from 'react';
import {
  View, FlatList, Text, TouchableOpacity, StyleSheet,
} from 'react-native';
import AsyncStorage from '@react-native-async-storage/async-storage';

const DEFAULT_URL = 'https://zeus-app-production.up.railway.app';

export function SessionsScreen({ navigation }) {
  const [sessions, setSessions] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const loadSessions = useCallback((url, signal) => {
    setLoading(true);
    setError(null);
    fetch(`${url}/sessions`, signal ? { signal } : undefined)
      .then(r => {
        if (!r.ok) throw new Error(`Server error ${r.status}`);
        return r.json();
      })
      .then(data => { setSessions(data); setLoading(false); })
      .catch(err => {
        if (err.name === 'AbortError') return;
        setError('Could not load sessions — check your connection.');
        setLoading(false);
      });
  }, []);

  useEffect(() => {
    const controller = new AbortController();
    AsyncStorage.getItem('zeus_backend_url').then(url => {
      const u = url || DEFAULT_URL;
      loadSessions(u, controller.signal);
    });
    return () => controller.abort();
  }, [loadSessions]);

  return (
    <View style={styles.container}>
      {error ? <Text style={styles.errorText}>{error}</Text> : null}

      <Text style={styles.sectionLabel}>RECENT SESSIONS</Text>

      <FlatList
        data={sessions}
        keyExtractor={item => String(item.id)}
        renderItem={({ item }) => (
          <TouchableOpacity
            style={styles.sessionItem}
            onPress={() => navigation.navigate('Chat', { sessionId: item.id })}
            activeOpacity={0.7}
          >
            <Text style={styles.preview}>{item.preview || 'Session'}</Text>
            <Text style={styles.meta}>
              {item.turns} turn{item.turns !== 1 ? 's' : ''} ·{' '}
              {item.started ? new Date(item.started).toLocaleDateString() : '—'}
            </Text>
          </TouchableOpacity>
        )}
        ListEmptyComponent={
          <Text style={styles.empty}>
            {loading ? 'Loading…' : 'No sessions yet.'}
          </Text>
        }
      />
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#0f0c29' },
  sectionLabel: {
    color: '#555', fontSize: 9, fontWeight: '700',
    letterSpacing: 0.8, padding: 12, paddingBottom: 4,
    textTransform: 'uppercase',
  },
  sessionItem: {
    padding: 16, borderBottomWidth: 1,
    borderBottomColor: 'rgba(255,255,255,0.05)',
  },
  preview: { color: '#e2d9f3', fontSize: 14 },
  meta: { color: '#555', fontSize: 11, marginTop: 3 },
  empty: { color: '#555', textAlign: 'center', padding: 24, fontSize: 13 },
  errorText: { color: '#fca5a5', fontSize: 12, textAlign: 'center', padding: 12 },
});
