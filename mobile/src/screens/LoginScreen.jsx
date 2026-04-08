import React, { useState, useEffect } from 'react';
import {
  View, Text, TextInput, TouchableOpacity,
  StyleSheet, KeyboardAvoidingView, Platform,
  ActivityIndicator, ScrollView,
} from 'react-native';
import AsyncStorage from '@react-native-async-storage/async-storage';

const DEFAULT_URL = 'https://zeus-app-production.up.railway.app';

export function LoginScreen({ navigation }) {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [loading, setLoading] = useState(true); // true while checking stored token
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState(null);

  // Auto-navigate to Chat if a valid token is already stored
  useEffect(() => {
    AsyncStorage.getItem('zeus_token').then(token => {
      if (token) {
        navigation.reset({ index: 0, routes: [{ name: 'Chat' }] });
      } else {
        setLoading(false);
      }
    });
  }, [navigation]);

  const handleLogin = async () => {
    const trimmedEmail = email.trim();
    if (!trimmedEmail || !password) {
      setError('Please enter your email and password.');
      return;
    }
    setError(null);
    setSubmitting(true);

    try {
      const backendUrl = (await AsyncStorage.getItem('zeus_backend_url')) || DEFAULT_URL;
      const res = await fetch(`${backendUrl}/auth/login`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email: trimmedEmail, password }),
      });
      const data = await res.json();
      if (!res.ok) {
        setError(data.detail || 'Login failed. Please check your credentials.');
        return;
      }
      await AsyncStorage.setItem('zeus_token', data.token);
      navigation.reset({ index: 0, routes: [{ name: 'Chat' }] });
    } catch {
      setError('Could not connect to the server. Check your backend URL in Sessions.');
    } finally {
      setSubmitting(false);
    }
  };

  if (loading) {
    return (
      <View style={styles.loadingContainer}>
        <ActivityIndicator color="#a78bfa" size="large" />
      </View>
    );
  }

  return (
    <KeyboardAvoidingView
      style={styles.container}
      behavior={Platform.OS === 'ios' ? 'padding' : 'height'}
    >
      <ScrollView
        contentContainerStyle={styles.inner}
        keyboardShouldPersistTaps="handled"
      >
        <Text style={styles.logo}>⚡</Text>
        <Text style={styles.title}>Zeus AI Design</Text>
        <Text style={styles.subtitle}>Sign in to your account</Text>

        {error && <Text style={styles.error}>{error}</Text>}

        <TextInput
          style={styles.input}
          value={email}
          onChangeText={setEmail}
          placeholder="Email address"
          placeholderTextColor="#555"
          autoCapitalize="none"
          autoCorrect={false}
          keyboardType="email-address"
          textContentType="emailAddress"
          editable={!submitting}
        />
        <TextInput
          style={styles.input}
          value={password}
          onChangeText={setPassword}
          placeholder="Password"
          placeholderTextColor="#555"
          secureTextEntry
          textContentType="password"
          editable={!submitting}
          onSubmitEditing={handleLogin}
          returnKeyType="go"
        />

        <TouchableOpacity
          style={[styles.btn, submitting && styles.btnDisabled]}
          onPress={handleLogin}
          disabled={submitting}
          activeOpacity={0.8}
        >
          {submitting
            ? <ActivityIndicator color="#fff" size="small" />
            : <Text style={styles.btnText}>Sign In</Text>
          }
        </TouchableOpacity>
      </ScrollView>
    </KeyboardAvoidingView>
  );
}

const styles = StyleSheet.create({
  loadingContainer: {
    flex: 1, backgroundColor: '#0f0c29',
    alignItems: 'center', justifyContent: 'center',
  },
  container: { flex: 1, backgroundColor: '#0f0c29' },
  inner: {
    flexGrow: 1, alignItems: 'center', justifyContent: 'center',
    padding: 32,
  },
  logo: { fontSize: 52, marginBottom: 12 },
  title: {
    color: '#e2d9f3', fontSize: 24, fontWeight: '700',
    letterSpacing: 0.5, marginBottom: 6,
  },
  subtitle: { color: '#555', fontSize: 14, marginBottom: 32 },
  error: {
    color: '#fca5a5', fontSize: 13, textAlign: 'center',
    marginBottom: 16, backgroundColor: 'rgba(239,68,68,0.12)',
    borderRadius: 8, padding: 10, width: '100%',
  },
  input: {
    width: '100%', backgroundColor: 'rgba(0,0,0,0.3)',
    borderWidth: 1, borderColor: 'rgba(255,255,255,0.1)',
    borderRadius: 10, padding: 14,
    color: '#e2d9f3', fontSize: 15, marginBottom: 14,
  },
  btn: {
    width: '100%', backgroundColor: '#a78bfa',
    borderRadius: 10, padding: 15,
    alignItems: 'center', marginTop: 6,
  },
  btnDisabled: { opacity: 0.5 },
  btnText: { color: '#fff', fontSize: 16, fontWeight: '700' },
});
