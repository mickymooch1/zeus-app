import React, { useState } from 'react';
import {
  ActivityIndicator,
  KeyboardAvoidingView,
  Platform,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  TouchableOpacity,
  View,
} from 'react-native';
import { LinearGradient } from 'expo-linear-gradient';
import { useAuth } from '../context/AuthContext';
import { COLORS, RADIUS } from '../constants/theme';

export function LoginScreen() {
  const { login } = useAuth();
  const [email,      setEmail]      = useState('');
  const [password,   setPassword]   = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [error,      setError]      = useState<string | null>(null);

  const handleLogin = async () => {
    if (!email.trim() || !password) {
      setError('Please enter your email and password.');
      return;
    }
    setError(null);
    setSubmitting(true);
    try {
      await login(email, password);
      // Navigation happens automatically via RootNavigator watching auth state
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Login failed. Please try again.');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <KeyboardAvoidingView
      style={styles.root}
      behavior={Platform.OS === 'ios' ? 'padding' : 'height'}
    >
      <ScrollView
        contentContainerStyle={styles.inner}
        keyboardShouldPersistTaps="handled"
        showsVerticalScrollIndicator={false}
      >
        {/* Logo */}
        <View style={styles.logoRow}>
          <Text style={styles.bolt}>⚡</Text>
          <Text style={styles.logoText}>Zeus Beats</Text>
        </View>
        <Text style={styles.tagline}>AI music creation. No limits.</Text>

        {/* Card */}
        <View style={styles.card}>
          <Text style={styles.heading}>Sign in</Text>

          {error && (
            <View style={styles.errorBanner}>
              <Text style={styles.errorText}>{error}</Text>
            </View>
          )}

          <TextInput
            style={styles.input}
            value={email}
            onChangeText={setEmail}
            placeholder="Email address"
            placeholderTextColor={COLORS.textMuted}
            autoCapitalize="none"
            autoCorrect={false}
            keyboardType="email-address"
            textContentType="emailAddress"
            editable={!submitting}
            returnKeyType="next"
          />

          <TextInput
            style={styles.input}
            value={password}
            onChangeText={setPassword}
            placeholder="Password"
            placeholderTextColor={COLORS.textMuted}
            secureTextEntry
            textContentType="password"
            editable={!submitting}
            returnKeyType="go"
            onSubmitEditing={handleLogin}
          />

          <TouchableOpacity
            onPress={handleLogin}
            disabled={submitting}
            activeOpacity={0.85}
            style={styles.btnWrapper}
          >
            <LinearGradient
              colors={['#7c3aed', '#a855f7']}
              start={{ x: 0, y: 0 }}
              end={{ x: 1, y: 0 }}
              style={[styles.btn, submitting && styles.btnDisabled]}
            >
              {submitting
                ? <ActivityIndicator color="#fff" size="small" />
                : <Text style={styles.btnText}>Sign In</Text>
              }
            </LinearGradient>
          </TouchableOpacity>
        </View>
      </ScrollView>
    </KeyboardAvoidingView>
  );
}

const styles = StyleSheet.create({
  root: {
    flex: 1,
    backgroundColor: COLORS.bg,
  },
  inner: {
    flexGrow: 1,
    alignItems: 'center',
    justifyContent: 'center',
    paddingHorizontal: 24,
    paddingVertical: 48,
  },
  logoRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 10,
    marginBottom: 8,
  },
  bolt: {
    fontSize: 40,
  },
  logoText: {
    fontSize: 28,
    fontWeight: '900',
    color: COLORS.white,
    letterSpacing: 0.5,
  },
  tagline: {
    fontSize: 13,
    color: COLORS.textMuted,
    marginBottom: 40,
    letterSpacing: 0.3,
  },
  card: {
    width: '100%',
    backgroundColor: COLORS.bgCard,
    borderWidth: 1,
    borderColor: COLORS.borderDim,
    borderRadius: RADIUS.lg,
    padding: 24,
  },
  heading: {
    fontSize: 20,
    fontWeight: '700',
    color: COLORS.textPrimary,
    marginBottom: 20,
  },
  errorBanner: {
    backgroundColor: COLORS.errorBg,
    borderRadius: RADIUS.sm,
    padding: 12,
    marginBottom: 16,
  },
  errorText: {
    color: COLORS.errorText,
    fontSize: 13,
    textAlign: 'center',
  },
  input: {
    width: '100%',
    backgroundColor: COLORS.inputBg,
    borderWidth: 1,
    borderColor: COLORS.borderDim,
    borderRadius: RADIUS.md,
    paddingHorizontal: 16,
    paddingVertical: 14,
    color: COLORS.textPrimary,
    fontSize: 15,
    marginBottom: 14,
  },
  btnWrapper: {
    width: '100%',
    marginTop: 4,
    borderRadius: RADIUS.md,
    overflow: 'hidden',
  },
  btn: {
    paddingVertical: 15,
    alignItems: 'center',
    justifyContent: 'center',
  },
  btnDisabled: {
    opacity: 0.55,
  },
  btnText: {
    color: '#fff',
    fontSize: 16,
    fontWeight: '700',
    letterSpacing: 0.3,
  },
});
