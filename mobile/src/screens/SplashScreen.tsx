import React, { useEffect, useRef } from 'react';
import { View, Text, Animated, StyleSheet } from 'react-native';

interface Props {
  onDone: () => void;
}

export function SplashScreen({ onDone }: Props) {
  const opacity = useRef(new Animated.Value(0)).current;
  const scale = useRef(new Animated.Value(0.6)).current;

  useEffect(() => {
    Animated.sequence([
      Animated.parallel([
        Animated.timing(opacity, { toValue: 1, duration: 500, useNativeDriver: true }),
        Animated.spring(scale, { toValue: 1, friction: 5, tension: 80, useNativeDriver: true }),
      ]),
      Animated.delay(1000),
      Animated.timing(opacity, { toValue: 0, duration: 400, useNativeDriver: true }),
    ]).start(onDone);
  }, []);

  return (
    <View style={styles.container}>
      <Animated.View style={{ opacity, transform: [{ scale }], alignItems: 'center' }}>
        <Text style={styles.bolt}>⚡</Text>
        <Text style={styles.name}>Zeus Beats</Text>
        <Text style={styles.tagline}>AI Music Creation</Text>
      </Animated.View>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1, backgroundColor: '#0f0c29',
    alignItems: 'center', justifyContent: 'center',
  },
  bolt: { fontSize: 80, marginBottom: 16 },
  name: {
    color: '#e2d9f3', fontSize: 34, fontWeight: '800',
    letterSpacing: 1,
  },
  tagline: { color: '#a78bfa', fontSize: 15, fontWeight: '600', marginTop: 10 },
});
