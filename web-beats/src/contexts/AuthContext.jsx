import { createContext, useCallback, useContext, useEffect, useState } from 'react';
import { BACKEND_URL } from '../brand';

const TOKEN_KEY = 'zeus_token';
const USER_CACHE_KEY = 'zeus_user_cache';

function readCachedUser() {
  try {
    const raw = localStorage.getItem(USER_CACHE_KEY);
    return raw ? JSON.parse(raw) : null;
  } catch {
    return null;
  }
}

function writeCachedUser(user) {
  try {
    if (user) localStorage.setItem(USER_CACHE_KEY, JSON.stringify(user));
    else localStorage.removeItem(USER_CACHE_KEY);
  } catch {}
}

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(readCachedUser);
  const [token, setToken] = useState(() => localStorage.getItem(TOKEN_KEY));
  // Start loading=false if there's a cached user (no flash), true otherwise
  const [loading, setLoading] = useState(() => !readCachedUser() && !!localStorage.getItem(TOKEN_KEY));

  useEffect(() => {
    const storedToken = localStorage.getItem(TOKEN_KEY);
    if (!storedToken) {
      setLoading(false);
      return;
    }
    fetch(`${BACKEND_URL}/auth/me`, {
      headers: { Authorization: `Bearer ${storedToken}` },
    })
      .then(async (res) => {
        if (res.ok) {
          const data = await res.json();
          // Server may return a refreshed token — store it to slide the expiry forward
          const freshToken = data.token || storedToken;
          if (data.token) localStorage.setItem(TOKEN_KEY, freshToken);
          writeCachedUser(data);
          setToken(freshToken);
          setUser(data);
        } else {
          // Token rejected (expired or secret changed) — clear everything
          localStorage.removeItem(TOKEN_KEY);
          writeCachedUser(null);
          setToken(null);
          setUser(null);
        }
      })
      .catch(() => {
        // Network unavailable at startup (common on Android TWA launch) —
        // keep the stored token and show the cached user so the app feels logged in.
        // /auth/me will be retried next time the app opens with a network connection.
        setToken(storedToken);
        setUser(readCachedUser());
      })
      .finally(() => setLoading(false));
  }, []);

  const login = useCallback(async (email, password) => {
    const res = await fetch(`${BACKEND_URL}/auth/login`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email, password }),
    });

    const data = await res.json();
    if (!res.ok) {
      throw new Error(data.detail || 'Login failed');
    }

    localStorage.setItem(TOKEN_KEY, data.token);
    writeCachedUser(data.user);
    setToken(data.token);
    setUser(data.user);
    return data;
  }, []);

  const register = useCallback(async (email, password, name, tcAccepted, app = 'beats', referral = null, fingerprint = null) => {
    const res = await fetch(`${BACKEND_URL}/auth/register`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email, password, name, tc_accepted: tcAccepted, app, referral, fingerprint }),
    });

    const data = await res.json();
    if (!res.ok) {
      throw new Error(data.detail || 'Registration failed');
    }

    localStorage.setItem(TOKEN_KEY, data.token);
    writeCachedUser(data.user);
    setToken(data.token);
    setUser(data.user);
    return data;
  }, []);

  const logout = useCallback(() => {
    localStorage.removeItem(TOKEN_KEY);
    writeCachedUser(null);
    setToken(null);
    setUser(null);
  }, []);

  return (
    <AuthContext.Provider value={{ user, token, login, register, logout, loading }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth must be used within AuthProvider');
  return ctx;
}
