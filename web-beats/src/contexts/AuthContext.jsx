import { createContext, useCallback, useContext, useEffect, useState } from 'react';
import { BACKEND_URL } from '../brand';

const TOKEN_KEY = 'zeus_token';
const USER_CACHE_KEY = 'zeus_user_cache';

function readCachedUser() {
  try {
    const raw = localStorage.getItem(USER_CACHE_KEY);
    if (!raw) {
      console.log('[Auth] readCachedUser: nothing in localStorage');
      return null;
    }
    const parsed = JSON.parse(raw);
    console.log('[Auth] readCachedUser: found user id=', parsed?.id, 'email=', parsed?.email);
    return parsed;
  } catch (e) {
    console.warn('[Auth] readCachedUser: JSON.parse failed:', e);
    return null;
  }
}

function writeCachedUser(user) {
  try {
    if (user) {
      localStorage.setItem(USER_CACHE_KEY, JSON.stringify(user));
      console.log('[Auth] writeCachedUser: stored user id=', user?.id);
    } else {
      localStorage.removeItem(USER_CACHE_KEY);
      console.log('[Auth] writeCachedUser: cleared cache');
    }
  } catch (e) {
    console.warn('[Auth] writeCachedUser failed:', e);
  }
}

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(readCachedUser);
  const [token, setToken] = useState(() => localStorage.getItem(TOKEN_KEY));
  // loading=false immediately if we have a cached user — no flash, no spinner
  const [loading, setLoading] = useState(() => {
    const hasCache = !!readCachedUser();
    const hasToken = !!localStorage.getItem(TOKEN_KEY);
    const initial = !hasCache && hasToken;
    console.log('[Auth] initial loading state:', initial, '(hasCache:', hasCache, 'hasToken:', hasToken, ')');
    return initial;
  });

  // Log what the first render sees — runs once after mount
  useEffect(() => {
    console.log('[Auth] first render — user:', user?.id ?? 'null', 'token:', token ? 'present' : 'absent', 'loading:', loading);
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    const storedToken = localStorage.getItem(TOKEN_KEY);
    console.log('[Auth] useEffect: storedToken', storedToken ? 'present' : 'absent');

    if (!storedToken) {
      console.log('[Auth] no token — setting loading=false, staying logged out');
      setLoading(false);
      return;
    }

    console.log('[Auth] fetching /auth/me to validate token...');
    fetch(`${BACKEND_URL}/auth/me`, {
      headers: { Authorization: `Bearer ${storedToken}` },
    })
      .then(async (res) => {
        console.log('[Auth] /auth/me response status:', res.status, 'ok:', res.ok);
        if (res.ok) {
          const data = await res.json();
          const freshToken = data.token || storedToken;
          if (data.token) localStorage.setItem(TOKEN_KEY, freshToken);
          writeCachedUser(data);
          setToken(freshToken);
          setUser(data);
          console.log('[Auth] /auth/me success — user id:', data?.id);
        } else {
          const body = await res.text().catch(() => '');
          console.warn('[Auth] /auth/me REJECTED status:', res.status, 'body:', body, '— clearing session');
          localStorage.removeItem(TOKEN_KEY);
          writeCachedUser(null);
          setToken(null);
          setUser(null);
        }
      })
      .catch((err) => {
        console.warn('[Auth] /auth/me network error (keeping cached session):', err?.message);
        setToken(storedToken);
        setUser(readCachedUser());
      })
      .finally(() => {
        console.log('[Auth] /auth/me done — setting loading=false');
        setLoading(false);
      });
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
