// Carries the /roast landing page's inputs through two different handoffs:
//   - saveRoastDraft/readRoastDraft (sessionStorage): /roast -> /register or
//     /login -> /songs, all within one continuous tab session.
//   - savePostVerifyDraft/readPostVerifyDraft (localStorage): a fresh signup
//     that gets gated by email_unverified at Generate, then opens their
//     verification link — which opens a NEW tab, where sessionStorage's
//     per-tab draft is already gone. localStorage is shared across tabs for
//     the same browser, so it survives that hop.
// Neither ever puts personal roast text in a URL — no query param, nothing
// sent anywhere except back into this same browser's own storage.
const ROAST_DRAFT_KEY = 'zeus_roast_draft';
const POST_VERIFY_DRAFT_KEY = 'zeus_roast_post_verify';
const MAX_AGE_MS = 60 * 60 * 1000; // 1 hour
const MAX_NAME_LEN = 80;
const MAX_DETAILS_LEN = 500;
const MAX_GENRES = 12;
const MAX_GENRE_LEN = 40;
// Must match the vibe picker's values on both SongsPage and RoastLandingPage.
export const ROAST_VIBES = ['gentle', 'roast', 'birthday', 'staghen'];
const DEFAULT_VIBE = 'gentle';

// Shared sanitizers — both drafts apply the same caps/validation, so the rule
// lives once here rather than twice at each storage's save/read pair.
function sanitizeName(name) {
  return (name || '').slice(0, MAX_NAME_LEN);
}
function sanitizeDetails(details) {
  return (details || '').slice(0, MAX_DETAILS_LEN);
}
function sanitizeVibe(vibe) {
  return ROAST_VIBES.includes(vibe) ? vibe : DEFAULT_VIBE;
}
function sanitizeGenres(genres) {
  if (!Array.isArray(genres)) return [];
  return genres
    .filter((g) => typeof g === 'string' && g)
    .slice(0, MAX_GENRES)
    .map((g) => g.slice(0, MAX_GENRE_LEN));
}
function isFresh(ts) {
  return typeof ts === 'number' && Date.now() - ts <= MAX_AGE_MS;
}

export function saveRoastDraft(roastName, roastDetails, roastVibe) {
  try {
    sessionStorage.setItem(ROAST_DRAFT_KEY, JSON.stringify({
      roastName: sanitizeName(roastName),
      roastDetails: sanitizeDetails(roastDetails),
      roastVibe: sanitizeVibe(roastVibe),
      ts: Date.now(),
    }));
  } catch {
    // sessionStorage unavailable (private browsing, storage disabled) — the
    // handoff just loses its prefill; navigation must never be blocked by this.
  }
}

// Returns { roastName, roastDetails, roastVibe } or null. Null covers every
// "nothing to restore" case alike (missing, expired, malformed) — the caller's
// job is only ever "prefill if present", never to distinguish why it wasn't.
export function readRoastDraft() {
  try {
    const raw = sessionStorage.getItem(ROAST_DRAFT_KEY);
    if (!raw) return null;
    const data = JSON.parse(raw);
    if (!data || typeof data !== 'object') return null;
    if (!isFresh(data.ts)) return null;
    if (typeof data.roastName !== 'string' || typeof data.roastDetails !== 'string') return null;
    return {
      roastName: sanitizeName(data.roastName),
      roastDetails: sanitizeDetails(data.roastDetails),
      roastVibe: sanitizeVibe(data.roastVibe),
    };
  } catch {
    return null;
  }
}

export function clearRoastDraft() {
  try { sessionStorage.removeItem(ROAST_DRAFT_KEY); } catch { /* no-op */ }
}

// genres: an array of genre slugs (e.g. Array.from(selGenres)) — stored as
// plain strings, not validated against the live genre list, so a future
// rename/removal degrades to "that one slug just doesn't highlight anything"
// rather than losing the whole draft.
export function savePostVerifyDraft(roastName, roastDetails, roastVibe, genres) {
  try {
    localStorage.setItem(POST_VERIFY_DRAFT_KEY, JSON.stringify({
      roastName: sanitizeName(roastName),
      roastDetails: sanitizeDetails(roastDetails),
      roastVibe: sanitizeVibe(roastVibe),
      genres: sanitizeGenres(genres),
      ts: Date.now(),
    }));
  } catch {
    // localStorage unavailable — same non-blocking stance as saveRoastDraft;
    // losing the safety net must never block the generate-attempt flow.
  }
}

// Returns { roastName, roastDetails, roastVibe, genres } or null — same
// "why" is never distinguished from the caller's side as readRoastDraft.
export function readPostVerifyDraft() {
  try {
    const raw = localStorage.getItem(POST_VERIFY_DRAFT_KEY);
    if (!raw) return null;
    const data = JSON.parse(raw);
    if (!data || typeof data !== 'object') return null;
    if (!isFresh(data.ts)) return null;
    if (typeof data.roastName !== 'string' || typeof data.roastDetails !== 'string') return null;
    return {
      roastName: sanitizeName(data.roastName),
      roastDetails: sanitizeDetails(data.roastDetails),
      roastVibe: sanitizeVibe(data.roastVibe),
      genres: sanitizeGenres(data.genres),
    };
  } catch {
    return null;
  }
}

export function clearPostVerifyDraft() {
  try { localStorage.removeItem(POST_VERIFY_DRAFT_KEY); } catch { /* no-op */ }
}
