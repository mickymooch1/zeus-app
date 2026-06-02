import React, { useEffect, useState, useRef } from 'react';
import { View, Text, StyleSheet, Animated, AppState } from 'react-native';
import AsyncStorage from '@react-native-async-storage/async-storage';

const DEFAULT_URL = 'https://zeus-app-production.up.railway.app';
const INTERVAL_MS = 20000;

export function OfflineBanner() {
  const [offline, setOffline] = useState(false);
  const anim = useRef(new Animated.Value(0)).current;

  const check = async () => {
    try {
      const url = (await AsyncStorage.getItem('zeus_backend_url')) || DEFAULT_URL;
      const res = await fetch(`${url}/health`, {
        method: 'HEAD',
        headers: { 'Cache-Control': 'no-cache' },
      });
      setOffline(!res.ok);
    } catch {
      setOffline(true);
    }
  };

  useEffect(() => {
    check();
    const timer = setInterval(check, INTERVAL_MS);
    const sub = AppState.addEventListener('change', state => {
      if (state === 'active') check();
    });
    return () => { clearInterval(timer); sub.remove(); };
  }, []);

  useEffect(() => {
    Animated.timing(anim, {
      toValue: offline ? 1 : 0,
      duration: 250,
      useNativeDriver: false,
    }).start();
  }, [offline]);

  const maxHeight = anim.interpolate({ inputRange: [0, 1], outputRange: [0, 40] });

  return (
    <Animated.View style={[styles.banner, { maxHeight }]}>
      <Text style={styles.text}>⚠ No connection to server — check network</Text>
    </Animated.View>
  );
}

const styles = StyleSheet.create({
  banner: {
    backgroundColor: '#7f1d1d', overflow: 'hidden',
    alignItems: 'center', justifyContent: 'center',
  },
  text: { color: '#fecaca', fontSize: 12, fontWeight: '600' },
});
