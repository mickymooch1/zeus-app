// First-touch UTM attribution. Captures utm_source/utm_medium/utm_campaign from
// the URL on first landing (App.jsx calls captureUtmFromUrl once, on mount) and
// survives signup/login/email-verification the same way utils/remixIntent.js's
// saveRemixIntent does — plain localStorage, so it's there whichever page the
// user eventually lands back on, including a brand new tab opened from a
// verification email.
//
// "First touch wins": once something is stored, a later visit — even with
// different utm params, even with none at all — never overwrites it. That's
// the entire point of first-touch attribution: it answers "what brought this
// person here the FIRST time", not "what's the most recent link they clicked".
const UTM_KEY = 'zeus_utm_attribution';
const MAX_AGE_MS = 30 * 24 * 60 * 60 * 1000; // 30 days — long enough to outlive a slow convert,
                                              // short enough that a stale capture doesn't attribute
                                              // a signup months later to an ad no one remembers.
const MAX_VALUE_LEN = 200; // matches the backend's Field(max_length=200)

function isFresh(ts) {
  return typeof ts === 'number' && Date.now() - ts <= MAX_AGE_MS;
}

function cap(value) {
  return typeof value === 'string' ? value.slice(0, MAX_VALUE_LEN) : null;
}

// Reads utm_source/utm_medium/utm_campaign from a query string (with or without
// the leading '?') and stores them — but ONLY if nothing fresh is already
// stored, and ONLY if at least one of the three is actually present. Safe to
// call on every page load unconditionally; it is a no-op on every call after
// the real first touch until MAX_AGE_MS has passed.
export function captureUtmFromUrl(search) {
  try {
    if (readUtmAttribution()) return; // first touch already recorded and still fresh
    const params = new URLSearchParams(search || '');
    const source = cap(params.get('utm_source'));
    const medium = cap(params.get('utm_medium'));
    const campaign = cap(params.get('utm_campaign'));
    if (!source && !medium && !campaign) return; // nothing to capture — leave storage untouched
    localStorage.setItem(UTM_KEY, JSON.stringify({
      utm_source: source, utm_medium: medium, utm_campaign: campaign, ts: Date.now(),
    }));
  } catch {
    // localStorage unavailable (private browsing, storage disabled) — attribution
    // is just lost for this visit; must never block navigation or throw.
  }
}

// Returns { utm_source, utm_medium, utm_campaign } or null — null covers every
// "nothing to attach" case alike (missing, expired, malformed), matching
// utils/remixIntent.js's readRemixIntent contract.
export function readUtmAttribution() {
  try {
    const raw = localStorage.getItem(UTM_KEY);
    if (!raw) return null;
    const data = JSON.parse(raw);
    if (!data || typeof data !== 'object') return null;
    if (!isFresh(data.ts)) return null;
    return {
      utm_source: cap(data.utm_source) || null,
      utm_medium: cap(data.utm_medium) || null,
      utm_campaign: cap(data.utm_campaign) || null,
    };
  } catch {
    return null;
  }
}
