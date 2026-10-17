// Google Ads: the standard sitewide Google tag behind explicit cookie consent
// (UK PECR), using Consent Mode v2 in its "basic" form.
//
// Basic Consent Mode, as Google documents it: the all-denied defaults are
// pushed on every page load, but gtag.js itself is not requested until the
// visitor clicks Accept — so without consent nothing at all reaches Google.
// After Accept the standard Google tag runs on every page (page views, the
// conversion linker that reads the ad click from the landing URL), with
// ad_storage + ad_user_data granted; ad_personalization (remarketing) and
// analytics_storage stay denied.
//
// The only conversion is "Sign-up", fired from RegisterPage after the backend
// has created the account. Its transaction_id is a random conversion id made
// once per sign-up (never the user id — Google asks that transaction ids not
// identify customers) and reused for every retry, so Google drops duplicates.
//
// Delivery: a browser cannot see whether Google accepted a hit (the response
// is cross-origin and opaque). Measured against the real gtag.js, its
// event_callback fires once it has processed the event, whether the hit then
// succeeds or fails — so that is "handed off". Until then the sign-up stays
// pending in localStorage and is retried on later visits (while consent lasts,
// up to 5 attempts within 30 days).
//
// Withdrawal: a loaded gtag.js can't be switched off (a 'denied' update and
// window['ga-disable-AW-…'] don't stop it — measured), so withdrawing consent
// on a page where it is running reloads the page after saving the choice.
//
// Fail safe: consent that can't be read counts as not given; "denied" in either
// place it is stored wins over "granted".
export const GOOGLE_ADS_ID = 'AW-18517714190';
export const SIGNUP_CONVERSION_LABEL = 'o7SdCLShsZ8dEI7K9_1E';

// { ads: 'granted' | 'denied', v: 1, ts } — the visitor's choice, also mirrored
// in a first-party cookie so one failed write can't lose it. The old
// 'zeus_cookie_accepted' flag came from an "OK, by using the site you agree"
// banner, which isn't valid consent for advertising cookies, so it is ignored:
// those visitors are simply asked again.
export const CONSENT_STORAGE_KEY = 'zeus_cookie_consent';
export const CONSENT_COOKIE = 'zeus_ads_consent';
// [{ user, cid, ts, attempts }] — `user` stays in this browser (local
// de-duplication); only the random `cid` is ever sent to Google.
export const PENDING_STORAGE_KEY = 'zeus_ads_pending_signups';
export const COOKIE_SETTINGS_EVENT = 'zeus:cookie-settings';
const SENT_KEY_PREFIX = 'zeus_ads_signup_sent_';
const SCRIPT_ID = 'zeus-gtag';
const CONSENT_COOKIE_MAX_AGE_S = 365 * 24 * 60 * 60;
const PENDING_MAX_AGE_MS = 30 * 24 * 60 * 60 * 1000;
const PENDING_MAX_ATTEMPTS = 5;
const DEFAULT_TAG_TIMEOUT_MS = 15000;
const HAND_OFF_WAIT_MS = 10000;
const CID_RE = /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/;

const DENIED = {
  ad_storage: 'denied', ad_user_data: 'denied', ad_personalization: 'denied', analytics_storage: 'denied',
};
const GRANTED = { ...DENIED, ad_storage: 'granted', ad_user_data: 'granted' };

// Per-page state — reset by initConsentMode, which runs once per page load.
let blocked = false;
let tagTimeoutMs = DEFAULT_TAG_TIMEOUT_MS;
let memoryChoice = null; // this page's choice; wins over storage
let tagPromise = null;
let configured = false;
const memoryPending = new Map(); // user -> record, in case storage writes fail
const memorySent = new Set();
const inFlight = new Set();
const cancelled = new Set(); // in flight when consent was withdrawn

function gtag() {
  // gtag.js only processes real Arguments objects, so this must stay a
  // `function` using `arguments` (not rest params / an array).
  window.dataLayer = window.dataLayer || [];
  window.dataLayer.push(arguments);
}

// A random v4 UUID, from the browser's cryptographic generator.
function newConversionId() {
  const c = globalThis.crypto;
  if (typeof c?.randomUUID === 'function') return c.randomUUID();
  const b = c.getRandomValues(new Uint8Array(16));
  b[6] = (b[6] & 0x0f) | 0x40;
  b[8] = (b[8] & 0x3f) | 0x80;
  const h = [...b].map((x) => x.toString(16).padStart(2, '0')).join('');
  return `${h.slice(0, 8)}-${h.slice(8, 12)}-${h.slice(12, 16)}-${h.slice(16, 20)}-${h.slice(20)}`;
}

// ── storage helpers: never throw; writes report whether they really stuck ──

function lsGet(key) {
  try { return localStorage.getItem(key); } catch { return null; }
}
function lsSet(key, value) {
  try { localStorage.setItem(key, value); return localStorage.getItem(key) === value; } catch { return false; }
}
function lsRemove(key) {
  try { localStorage.removeItem(key); } catch { /* nothing to do */ }
}
function readCookie(name) {
  try {
    const hit = document.cookie.split(';').map((c) => c.trim()).find((c) => c.startsWith(`${name}=`));
    return hit ? hit.slice(name.length + 1) : null;
  } catch {
    return null;
  }
}
function writeCookie(name, value) {
  try {
    document.cookie = `${name}=${value}; Max-Age=${CONSENT_COOKIE_MAX_AGE_S}; path=/; SameSite=Lax`;
  } catch { /* cookies blocked */ }
}

const asChoice = (v) => (v === 'granted' || v === 'denied' ? v : null);

function storedChoice() {
  let fromStorage = null;
  try { fromStorage = asChoice(JSON.parse(lsGet(CONSENT_STORAGE_KEY))?.ads); } catch { fromStorage = null; }
  const fromCookie = asChoice(readCookie(CONSENT_COOKIE));
  if (fromStorage === 'denied' || fromCookie === 'denied') return 'denied';
  if (fromStorage === 'granted' || fromCookie === 'granted') return 'granted';
  return null;
}

export function readConsent() {
  return memoryChoice || storedChoice();
}

const consentOk = () => !blocked && readConsent() === 'granted';

// ── pending conversions ────────────────────────────────────────────────────

const validRecord = (r) => r && typeof r.user === 'string' && typeof r.cid === 'string' && CID_RE.test(r.cid);

function storedPending() {
  try {
    const list = JSON.parse(lsGet(PENDING_STORAGE_KEY) || '[]');
    return Array.isArray(list) ? list.filter(validRecord) : [];
  } catch {
    return [];
  }
}
function livePending() {
  const byUser = new Map(storedPending().map((r) => [r.user, r]));
  for (const [user, r] of memoryPending) byUser.set(user, { ...byUser.get(user), ...r });
  const now = Date.now();
  return [...byUser.values()].filter((r) => now - (Number(r.ts) || 0) <= PENDING_MAX_AGE_MS
    && (Number(r.attempts) || 0) < PENDING_MAX_ATTEMPTS);
}
function savePending(list) {
  memoryPending.clear();
  for (const r of list) memoryPending.set(r.user, r);
  if (list.length === 0) lsRemove(PENDING_STORAGE_KEY);
  else lsSet(PENDING_STORAGE_KEY, JSON.stringify(list));
}
function updatePending(user, change) {
  savePending(livePending().map((r) => (r.user === user ? change(r) : r)).filter(Boolean));
}
function isSent(user) {
  return memorySent.has(user) || lsGet(`${SENT_KEY_PREFIX}${user}`) === '1';
}
function markHandedOff(user) {
  memorySent.add(user);
  lsSet(`${SENT_KEY_PREFIX}${user}`, '1');
  updatePending(user, () => null);
}

// ── the tag ────────────────────────────────────────────────────────────────

// Resolves once gtag.js has loaded; rejects on load error or timeout. A failed
// script element is removed so a later attempt can add it again.
function loadTag() {
  if (blocked) return Promise.reject(new Error('blocked'));
  if (tagPromise) return tagPromise;
  const existing = document.getElementById(SCRIPT_ID);
  if (existing) {
    // timed out earlier on this page and may still arrive — don't add a second copy
    return window.google_tag_data ? Promise.resolve() : Promise.reject(new Error('still loading'));
  }
  tagPromise = new Promise((resolve, reject) => {
    const s = document.createElement('script');
    s.id = SCRIPT_ID;
    s.async = true;
    s.src = `https://www.googletagmanager.com/gtag/js?id=${GOOGLE_ADS_ID}`;
    let settled = false;
    const fail = (why) => {
      if (settled) return;
      settled = true;
      tagPromise = null;
      reject(new Error(why));
    };
    const timer = setTimeout(() => fail('timeout'), tagTimeoutMs);
    s.onload = () => {
      if (settled) return;
      settled = true;
      clearTimeout(timer);
      resolve();
    };
    s.onerror = () => {
      clearTimeout(timer);
      try { s.remove(); } catch { /* already gone */ }
      fail('load failed');
    };
    document.head.appendChild(s);
    if (!configured) {
      configured = true;
      gtag('js', new Date());
      gtag('config', GOOGLE_ADS_ID); // the standard sitewide config
    }
  });
  tagPromise.catch(() => {});
  return tagPromise;
}

async function dispatch(user) {
  if (inFlight.has(user) || isSent(user) || !consentOk()) return 'skipped';
  const record = livePending().find((r) => r.user === user);
  if (!record) return 'skipped';
  inFlight.add(user);
  updatePending(user, (r) => ({ ...r, attempts: (Number(r.attempts) || 0) + 1 }));
  try {
    await loadTag();
  } catch {
    inFlight.delete(user);
    return 'pending';
  }
  // consent may have been withdrawn while the tag was loading
  if (!consentOk() || cancelled.has(user)) {
    inFlight.delete(user);
    return 'skipped';
  }
  return new Promise((resolve) => {
    const timer = setTimeout(() => resolve('pending'), HAND_OFF_WAIT_MS);
    timer?.unref?.();
    gtag('event', 'conversion', {
      send_to: `${GOOGLE_ADS_ID}/${SIGNUP_CONVERSION_LABEL}`,
      transaction_id: record.cid,
      event_callback: () => {
        clearTimeout(timer);
        markHandedOff(user);
        resolve('handed-off');
      },
    });
    // stays in inFlight for the rest of this page: never pushed twice per page
  });
}

// Retries anything a previous page couldn't hand to the tag.
export function flushPendingConversions() {
  try {
    if (!consentOk()) return Promise.resolve([]);
    return Promise.all(livePending().filter((r) => !isSent(r.user)).map((r) => dispatch(r.user)));
  } catch {
    return Promise.resolve([]);
  }
}

// Google Ads' first-party cookies (_gcl_aw, _gcl_au, …) and the _gcl_ls entry
// gtag.js keeps in localStorage. Set on the registrable domain, so try each
// parent domain as well as none.
function clearAdStorage() {
  try {
    const names = document.cookie.split(';').map((c) => c.split('=')[0].trim()).filter((n) => n.startsWith('_gcl'));
    const labels = (window.location?.hostname || '').split('.');
    const domains = [null];
    for (let i = 0; i < labels.length - 1; i += 1) domains.push(`.${labels.slice(i).join('.')}`);
    for (const name of names) {
      for (const d of domains) document.cookie = `${name}=; Max-Age=0; path=/${d ? `; domain=${d}` : ''}`;
    }
  } catch { /* cookies unavailable */ }
  for (const store of [globalThis.localStorage, globalThis.sessionStorage]) {
    try {
      const keys = [];
      for (let i = 0; i < store.length; i += 1) keys.push(store.key(i));
      keys.filter((k) => k && k.startsWith('_gcl')).forEach((k) => store.removeItem(k));
    } catch { /* storage unavailable */ }
  }
}

// ── public API ─────────────────────────────────────────────────────────────

// Call once per page load, before the app renders. `blocked` is true inside
// the iOS app, where Apple's tracking rules apply — the tag never loads there.
export function initConsentMode({ blocked: isBlocked = false, tagTimeoutMs: timeout = DEFAULT_TAG_TIMEOUT_MS } = {}) {
  blocked = isBlocked;
  tagTimeoutMs = timeout;
  memoryChoice = null;
  tagPromise = null;
  configured = false;
  memoryPending.clear();
  memorySent.clear();
  inFlight.clear();
  cancelled.clear();
  try {
    gtag('consent', 'default', DENIED);
    savePending(livePending()); // drops expired / exhausted / malformed records
    if (consentOk()) {
      gtag('consent', 'update', GRANTED);
      loadTag();
      flushPendingConversions();
    }
  } catch {
    // tracking must never break the app
  }
}

// Returns { persisted, reloading }. Withdrawing consent on a page where
// Google's tag already ran reloads the page — the only way to stop it. If the
// withdrawal couldn't be saved, it does NOT reload (the reload would bring the
// old Accept back); the denial holds in memory for the rest of the page.
export function setConsent(choice) {
  const value = choice === 'granted' ? 'granted' : 'denied';
  memoryChoice = value;
  let tagWasRunning = false;
  try { tagWasRunning = !!document.getElementById(SCRIPT_ID); } catch { /* no DOM */ }
  if (!lsSet(CONSENT_STORAGE_KEY, JSON.stringify({ ads: value, v: 1, ts: Date.now() })) && value === 'denied') {
    lsRemove(CONSENT_STORAGE_KEY); // never leave an old "granted" behind
  }
  writeCookie(CONSENT_COOKIE, value);
  const persisted = storedChoice() === value;

  try {
    if (value === 'granted') {
      if (!blocked) {
        gtag('consent', 'update', GRANTED);
        loadTag();
        flushPendingConversions();
      }
      return { persisted, reloading: false };
    }
    gtag('consent', 'update', DENIED);
    savePending([]); // anything not yet handed to Google is cancelled
    for (const user of inFlight) cancelled.add(user);
    clearAdStorage();
    const reloading = tagWasRunning && persisted;
    if (reloading) window.location.reload();
    return { persisted, reloading };
  } catch {
    return { persisted, reloading: false };
  }
}

export function openCookieSettings() {
  try {
    window.dispatchEvent(new Event(COOKIE_SETTINGS_EVENT));
  } catch {
    // no window (tests / SSR)
  }
}

// Resolves to 'handed-off' (gtag.js took the event), 'pending' (kept for a
// retry on a later visit) or 'skipped' (no consent, no id, already done or
// withdrawn). Never rejects.
export function trackSignupConversion(userId) {
  try {
    if (userId === undefined || userId === null || userId === '') return Promise.resolve('skipped');
    if (!consentOk()) return Promise.resolve('skipped');
    const user = String(userId);
    if (isSent(user)) return Promise.resolve('skipped');
    if (!livePending().some((r) => r.user === user)) {
      savePending([...livePending(), { user, cid: newConversionId(), ts: Date.now(), attempts: 0 }]);
    }
    return dispatch(user).catch(() => 'pending');
  } catch {
    return Promise.resolve('skipped');
  }
}
