export const BACKEND_URL = 'https://zeus-app-production.up.railway.app';

export const API = {
  login:        `${BACKEND_URL}/auth/login`,
  me:           `${BACKEND_URL}/auth/me`,
  logout:       `${BACKEND_URL}/auth/logout`,
  generate:     `${BACKEND_URL}/api/songs/generate`,
  variants:     (lyricId: number) => `${BACKEND_URL}/api/lyrics/${lyricId}/variants`,
};

export const TOKEN_KEY = 'zeus_beats_token';
