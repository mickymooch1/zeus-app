// Carries a "⚡ Remix This Sound" click on a clip page through login/register/email
// verification, so the user lands back at the remix create flow without re-finding
// the clip. Mirrors utils/roastDraft.js's savePostVerifyDraft pattern:
//   - The clip page ALSO appends `?remix=<clipId>` to wherever it sends a logged-out
//     visitor (register/login) — that query param survives a same-tab register/login
//     redirect on its own and is threaded through by those pages.
//   - localStorage is the one that survives the email-verification hop, since the
//     verification link opens in a brand NEW tab with no query param of ours on it.
// Both are written here so the caller only has to call saveRemixIntent once.
const REMIX_INTENT_KEY = 'zeus_remix_intent';
const MAX_AGE_MS = 60 * 60 * 1000; // 1 hour — matches roastDraft's post-verify draft TTL

function isFresh(ts) {
  return typeof ts === 'number' && Date.now() - ts <= MAX_AGE_MS;
}

// clipId is trusted only as a positive integer — anything else means the caller
// passed something unexpected, and this is a storage key, not a place to validate
// user input, so it simply declines to write rather than storing garbage.
function toValidClipId(clipId) {
  const n = Number(clipId);
  return Number.isInteger(n) && n > 0 ? n : null;
}

export function saveRemixIntent(clipId) {
  const id = toValidClipId(clipId);
  if (id === null) return;
  try {
    localStorage.setItem(REMIX_INTENT_KEY, JSON.stringify({ clipId: id, ts: Date.now() }));
  } catch {
    // localStorage unavailable (private browsing, storage disabled) — the remix
    // hand-off just loses its cross-tab safety net; navigation must never be
    // blocked by this the same way roastDraft's save never blocks navigation.
  }
}

// Returns { clipId } or null — null covers every "nothing to restore" case alike
// (missing, expired, malformed, invalid id), matching readPostVerifyDraft's contract.
export function readRemixIntent() {
  try {
    const raw = localStorage.getItem(REMIX_INTENT_KEY);
    if (!raw) return null;
    const data = JSON.parse(raw);
    if (!data || typeof data !== 'object') return null;
    if (!isFresh(data.ts)) return null;
    const id = toValidClipId(data.clipId);
    if (id === null) return null;
    return { clipId: id };
  } catch {
    return null;
  }
}

export function clearRemixIntent() {
  try { localStorage.removeItem(REMIX_INTENT_KEY); } catch { /* no-op */ }
}

// True when this /songs visit is part of a remix hand-off — either on the way
// in (?remix= / stored intent, about to redirect to the remix confirm page) or
// landing after the remix was started (navigation state). Used to skip the
// first-visit "explore first" welcome, which makes no sense mid-remix.
export function arrivedViaRemix({ state, search, hasStoredIntent = false }) {
  if (state?.remixStarted) return true;
  if (hasStoredIntent) return true;
  return Number(new URLSearchParams(search || '').get('remix')) > 0;
}
