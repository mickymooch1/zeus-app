import React from 'react';
import { StyleSheet, Text, View } from 'react-native';
import { COLORS } from '../constants/theme';

export function LibraryScreen() {
  return (
    <View style={styles.container}>
      <Text style={styles.icon}>🎵</Text>
      <Text style={styles.title}>Library</Text>
      <Text style={styles.sub}>Coming soon — Stage 2</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: COLORS.bg,
    alignItems: 'center',
    justifyContent: 'center',
    gap: 8,
  },
  icon:  { fontSize: 48 },
  title: { fontSize: 20, fontWeight: '700', color: COLORS.textPrimary },
  sub:   { fontSize: 13, color: COLORS.textMuted },
});
