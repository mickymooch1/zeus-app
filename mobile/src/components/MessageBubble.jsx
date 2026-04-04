import React from 'react';
import { View, Text, StyleSheet, Platform } from 'react-native';

export function MessageBubble({ message, isStreaming }) {
  if (message.role === 'user') {
    return (
      <View style={styles.userContainer}>
        <View style={styles.userBubble}>
          <Text style={styles.userText}>{message.text}</Text>
        </View>
      </View>
    );
  }

  const showCursor = isStreaming && !message.error;

  return (
    <View style={styles.zeusContainer}>
      <View style={styles.avatar}>
        <Text style={styles.avatarText}>⚡</Text>
      </View>
      <View style={styles.zeusBubble}>
        <Text style={styles.zeusLabel}>ZEUS</Text>

        {(message.text || showCursor) ? (
          <Text style={styles.zeusText}>
            {message.text}{showCursor ? '▍' : ''}
          </Text>
        ) : null}

        {message.tools?.length > 0 && (
          <View style={styles.toolLog}>
            {message.tools.map((t, i) => (
              <Text
                key={i}
                style={[styles.toolItem, t.status === 'done' ? styles.toolDone : styles.toolRunning]}
              >
                {t.status === 'done' ? '✓' : '⟳'} {t.name}{t.path ? `: ${t.path}` : ''}
              </Text>
            ))}
          </View>
        )}

        {message.error ? (
          <Text style={styles.errorText}>{message.error}</Text>
        ) : null}
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  userContainer: { alignItems: 'flex-end', marginBottom: 12 },
  userBubble: {
    backgroundColor: 'rgba(167,139,250,0.25)',
    borderWidth: 1,
    borderColor: 'rgba(167,139,250,0.3)',
    borderRadius: 12,
    borderBottomRightRadius: 2,
    padding: 10,
    maxWidth: '75%',
  },
  userText: { color: '#e2d9f3', fontSize: 14, lineHeight: 20 },

  zeusContainer: { flexDirection: 'row', marginBottom: 12, maxWidth: '92%' },
  avatar: {
    width: 28, height: 28, borderRadius: 14,
    backgroundColor: '#a78bfa',
    alignItems: 'center', justifyContent: 'center',
    marginRight: 8, marginTop: 2,
  },
  avatarText: { fontSize: 12, color: '#fff' },
  zeusBubble: {
    backgroundColor: 'rgba(255,255,255,0.06)',
    borderWidth: 1,
    borderColor: 'rgba(255,255,255,0.1)',
    borderRadius: 12,
    borderTopLeftRadius: 2,
    padding: 12,
    flex: 1,
  },
  zeusLabel: {
    color: '#a78bfa', fontSize: 9, fontWeight: '700',
    letterSpacing: 0.8, marginBottom: 4,
  },
  zeusText: { color: '#e2d9f3', fontSize: 14, lineHeight: 20 },

  toolLog: {
    marginTop: 8,
    backgroundColor: 'rgba(0,0,0,0.3)',
    borderRadius: 6, padding: 6,
  },
  toolItem: { fontSize: 11, fontFamily: Platform.select({ android: 'monospace', ios: 'Courier New' }), paddingVertical: 1 },
  toolDone: { color: '#34d399' },
  toolRunning: { color: '#60a5fa' },

  errorText: { color: '#fca5a5', fontSize: 12, marginTop: 6 },
});
