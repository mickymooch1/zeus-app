// Google Ads "Sign-up" conversion behind explicit cookie consent (UK PECR /
// Google Consent Mode v2) — and nothing else.
//
// Google's tag NEVER runs on the app's own pages. For each consented sign-up,
// a hidden frame (/ads-frame.html + public/ads-frame.js) is added, loads the
// tag, sends that one conversion and is removed. Measured against the real
// gtag.js, this is what keeps tracking limited to sign-ups:
//   - a tag on the page sends page_view pings on every page and SPA
//     navigation whenever it is `config`ured (even with send_page_view: false);
//   - while loaded on a page it also watches every form submission there and
//     sends "form-data" pings (this account has automatic enhanced conversions);
//   - once loaded it can't be switched off — a 'denied' update and
//     window['ga-disable-AW-…'] don't stop it.
// In the empty frame it sees no pages, forms or navigation; the main page
// only ever pushes the all-denied Consent Mode default.
//
// Ad click: the gclid / gbraid / wbraid from the landing URL is held in memory
// and, once the visitor accepts, kept in localStorage for 90 days, then passed
// to the frame's URL where the tag reads it — so a sign-up is attributed to the
// ad even on a later visit.
//
// Delivery: a browser cannot see whether Google accepted a hit (the response is
// cross-origin and opaque). The tag's event_callback — which fires once it has
// processed the event, whether the hit then succeeds or fails — is the strongest
// local signal, so that is "handed off". Until then the sign-up stays pending
// in localStorage and is retried on later visits (while consent lasts, up to 5
// attempts within 30 days), always with the user id as transaction_id so
// Google drops duplicates.
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
export const PENDING_STORAGE_KEY = 'zeus_ads_pending_signups';
export const CLICK_STORAGE_KEY = 'zeus_ads_click';
export const COOKIE_SETTINGS_EVENT = 'zeus:cookie-settings';
export const FRAME_PATH = '/ads-frame.html';
export const FRAME_MESSAGE_TYPE = 'zeus-ads-frame';
const SENT_KEY_PREFIX = 'zeus_ads_signup_sent_';
const CLICK_ID_PARAMS = ['gclid', 'gbraid', 'wbraid'];
const CONSENT_COOKIE_MAX_AGE_S = 365 * 24 * 60 * 60;
const PENDING_MAX_AGE_MS = 30 * 24 * 60 * 60 * 1000;
const PENDING_MAX_ATTEMPTS = 5;
const CLICK_MAX_AGE_MS = 90 * 24 * 60 * 60 * 1000;
const DEFAULT_SEND_TIMEOUT_MS = 20000;

const DENIED = {
  ad_storage: 'denied', ad_user_data: 'denied', ad_personalization: 'denied', analytics_storage: 'denied',
};

// Per-page state — reset by initConsentMode, which runs once per page load.
let blocked = false;
let sendTimeoutMs = DEFAULT_SEND_TIMEOUT_MS;
let memoryChoice = null; // this page's choice; wins over storage
let landingClick = null; // ad click ids from this page's landing URL
const memoryPending = new Map(); // id -> record, in case storage writes fail
const memorySent = new Set();
const inFlight = new Set();
const liveFrames = new Map(); // id -> finish(status)

function gtag() {
  // gtag.js only processes real Arguments objects, so this must stay a
  // `function` using `arguments` (not rest params / an array).
  window.dataLayer = window.dataLayer || [];
  window.dataLayer.push(arguments);
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

// ── ad click ids ───────────────────────────────────────────────────────────

const CLICK_ID_RE = /^[\w-]{1,200}$/;

function pickClickIds(source) {
  const click = {};
  for (const k of CLICK_ID_PARAMS) {
    const v = source(k);
    if (typeof v === 'string' && CLICK_ID_RE.test(v)) click[k] = v;
  }
  return Object.keys(click).length ? click : null;
}
function clickFromUrl() {
  try {
    const params = new URLSearchParams(window.location?.search || '');
    return pickClickIds((k) => params.get(k));
  } catch {
    return null;
  }
}
function rememberClick() {
  if (landingClick) lsSet(CLICK_STORAGE_KEY, JSON.stringify({ ...landingClick, ts: Date.now() }));
}
function currentClick() {
  if (landingClick) return landingClick;
  try {
    const stored = JSON.parse(lsGet(CLICK_STORAGE_KEY));
    if (!stored || Date.now() - (Number(stored.ts) || 0) > CLICK_MAX_AGE_MS) return null;
    return pickClickIds((k) => stored[k]);
  } catch {
    return null;
  }
}

// ── pending conversions ────────────────────────────────────────────────────

function storedPending() {
  try {
    const list = JSON.parse(lsGet(PENDING_STORAGE_KEY) || '[]');
    return Array.isArray(list) ? list.filter((r) => r && typeof r.id === 'string') : [];
  } catch {
    return [];
  }
}
function livePending() {
  const byId = new Map(storedPending().map((r) => [r.id, r]));
  for (const [id, r] of memoryPending) byId.set(id, { ...byId.get(id), ...r });
  const now = Date.now();
  return [...byId.values()].filter((r) => now - (Number(r.ts) || 0) <= PENDING_MAX_AGE_MS
    && (Number(r.attempts) || 0) < PENDING_MAX_ATTEMPTS);
}
function savePending(list) {
  memoryPending.clear();
  for (const r of list) memoryPending.set(r.id, r);
  if (list.length === 0) lsRemove(PENDING_STORAGE_KEY);
  else lsSet(PENDING_STORAGE_KEY, JSON.stringify(list));
}
function updatePending(id, change) {
  savePending(livePending().map((r) => (r.id === id ? change(r) : r)).filter(Boolean));
}
function isSent(id) {
  return memorySent.has(id) || lsGet(`${SENT_KEY_PREFIX}${id}`) === '1';
}
function markHandedOff(id) {
  memorySent.add(id);
  lsSet(`${SENT_KEY_PREFIX}${id}`, '1');
  updatePending(id, () => null);
}

// ── the hidden frame ───────────────────────────────────────────────────────

function sendViaFrame(id) {
  return new Promise((resolve) => {
    let frame = null;
    let timer = null;
    const listener = (e) => {
      if (!frame || e.source !== frame.contentWindow || e.origin !== window.location.origin) return;
      const d = e.data;
      if (!d || d.type !== FRAME_MESSAGE_TYPE || d.tid !== id) return;
      finish(d.status === 'handed-off' ? 'handed-off' : 'failed');
    };
    function finish(status) {
      if (liveFrames.get(id) !== finish) return; // settled already, or not this send
      liveFrames.delete(id);
      clearTimeout(timer);
      try { window.removeEventListener('message', listener); } catch { /* no window */ }
      try { frame?.remove(); } catch { /* already gone */ }
      if (status === 'cancelled') { resolve('skipped'); return; }
      if (status === 'handed-off') { markHandedOff(id); resolve('handed-off'); return; }
      // 'failed': gtag.js couldn't load — free to retry. 'timeout': we can't
      // tell whether it went, so not again on this page (later visits retry,
      // and Google drops a duplicate transaction_id).
      if (status === 'failed') inFlight.delete(id);
      resolve('pending');
    }
    liveFrames.set(id, finish);
    try {
      frame = document.createElement('iframe');
      frame.setAttribute('aria-hidden', 'true');
      frame.setAttribute('tabindex', '-1');
      frame.title = 'Zeus Beats';
      frame.style.cssText = 'position:fixed;width:0;height:0;border:0;visibility:hidden;pointer-events:none';
      const click = currentClick();
      const qs = click ? new URLSearchParams(click).toString() : '';
      frame.src = `${FRAME_PATH}${qs ? `?${qs}` : ''}#tid=${encodeURIComponent(id)}`;
      window.addEventListener('message', listener);
      timer = setTimeout(() => finish('timeout'), sendTimeoutMs);
      (document.body || document.documentElement).appendChild(frame);
    } catch {
      finish('failed');
    }
  });
}

async function dispatch(id) {
  if (inFlight.has(id) || isSent(id) || !consentOk()) return 'skipped';
  inFlight.add(id);
  updatePending(id, (r) => ({ ...r, attempts: (Number(r.attempts) || 0) + 1 }));
  return sendViaFrame(id);
}

// Retries anything a previous page couldn't hand to the tag.
export function flushPendingConversions() {
  try {
    if (!consentOk()) return Promise.resolve([]);
    return Promise.all(livePending().filter((r) => !isSent(r.id)).map((r) => dispatch(r.id)));
  } catch {
    return Promise.resolve([]);
  }
}

// Google Ads' first-party cookies (_gcl_au, _gcl_aw, …) and the _gcl_ls entry
// gtag.js keeps in localStorage — the frame is same-origin, so they are ours to
// delete. Set on the registrable domain, so try each parent domain as well.
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
// the iOS app, where Apple's tracking rules apply — nothing is ever sent there.
export function initConsentMode({ blocked: isBlocked = false, sendTimeoutMs: timeout = DEFAULT_SEND_TIMEOUT_MS } = {}) {
  blocked = isBlocked;
  sendTimeoutMs = timeout;
  memoryChoice = null;
  memoryPending.clear();
  memorySent.clear();
  inFlight.clear();
  for (const finish of [...liveFrames.values()]) finish('cancelled'); // never leave a send unsettled
  landingClick = clickFromUrl();
  try {
    // The main page never grants anything to Google: if any Google tag were
    // ever added here, it would start (and stay) all-denied.
    gtag('consent', 'default', DENIED);
    savePending(livePending()); // drops expired / exhausted records
    if (consentOk()) {
      rememberClick();
      flushPendingConversions();
    }
  } catch {
    // tracking must never break the app
  }
}

// Returns { persisted } — whether the choice was saved for future visits (it
// always applies to the rest of this page).
export function setConsent(choice) {
  const value = choice === 'granted' ? 'granted' : 'denied';
  memoryChoice = value;
  if (!lsSet(CONSENT_STORAGE_KEY, JSON.stringify({ ads: value, v: 1, ts: Date.now() })) && value === 'denied') {
    lsRemove(CONSENT_STORAGE_KEY); // never leave an old "granted" behind
  }
  writeCookie(CONSENT_COOKIE, value);
  const persisted = storedChoice() === value;

  try {
    if (value === 'granted') {
      if (!blocked) {
        rememberClick();
        flushPendingConversions();
      }
    } else {
      // Withdrawal: stop any send in progress, forget unsent sign-ups and the
      // ad click, and delete what Google's tag stored on this site.
      for (const finish of [...liveFrames.values()]) finish('cancelled');
      savePending([]);
      lsRemove(CLICK_STORAGE_KEY);
      clearAdStorage();
    }
  } catch {
    // tracking must never break the app
  }
  return { persisted };
}

export function openCookieSettings() {
  try {
    window.dispatchEvent(new Event(COOKIE_SETTINGS_EVENT));
  } catch {
    // no window (tests / SSR)
  }
}

// Resolves to 'handed-off' (Google's tag took the event), 'pending' (kept for
// a retry on a later visit) or 'skipped' (no consent, no id, already done or
// withdrawn). Never rejects.
export function trackSignupConversion(userId) {
  try {
    if (userId === undefined || userId === null || userId === '') return Promise.resolve('skipped');
    if (!consentOk()) return Promise.resolve('skipped');
    const id = String(userId);
    if (isSent(id)) return Promise.resolve('skipped');
    if (!livePending().some((r) => r.id === id)) {
      savePending([...livePending(), { id, ts: Date.now(), attempts: 0 }]);
    }
    return dispatch(id).catch(() => 'pending');
  } catch {
    return Promise.resolve('skipped');
  }
}
