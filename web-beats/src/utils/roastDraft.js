// Carries the /roast landing page's inputs through signup (or straight to /songs
// for an already logged-in visitor) without ever putting personal roast text in a
// URL. sessionStorage only — never a query param, never sent anywhere.
const ROAST_DRAFT_KEY = 'zeus_roast_draft';
const MAX_AGE_MS = 60 * 60 * 1000; // 1 hour
const MAX_NAME_LEN = 80;
const MAX_DETAILS_LEN = 500;

export function saveRoastDraft(roastName, roastDetails) {
  try {
    sessionStorage.setItem(ROAST_DRAFT_KEY, JSON.stringify({
      roastName: (roastName || '').slice(0, MAX_NAME_LEN),
      roastDetails: (roastDetails || '').slice(0, MAX_DETAILS_LEN),
      ts: Date.now(),
    }));
  } catch {
    // sessionStorage unavailable (private browsing, storage disabled) — the
    // handoff just loses its prefill; navigation must never be blocked by this.
  }
}

// Returns { roastName, roastDetails } or null. Null covers every "nothing to
// restore" case alike (missing, expired, malformed) — the caller's job is only
// ever "prefill if present", never to distinguish why it wasn't.
export function readRoastDraft() {
  try {
    const raw = sessionStorage.getItem(ROAST_DRAFT_KEY);
    if (!raw) return null;
    const data = JSON.parse(raw);
    if (!data || typeof data !== 'object') return null;
    if (typeof data.ts !== 'number' || Date.now() - data.ts > MAX_AGE_MS) return null;
    if (typeof data.roastName !== 'string' || typeof data.roastDetails !== 'string') return null;
    return {
      roastName: data.roastName.slice(0, MAX_NAME_LEN),
      roastDetails: data.roastDetails.slice(0, MAX_DETAILS_LEN),
    };
  } catch {
    return null;
  }
}

export function clearRoastDraft() {
  try { sessionStorage.removeItem(ROAST_DRAFT_KEY); } catch { /* no-op */ }
}
