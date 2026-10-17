/**
 * Google Ads + Consent Mode v2 (UK PECR: advertising cookies need opt-in).
 *
 * The rules these tests pin down:
 *   - Consent Mode defaults are pushed FIRST, all four signals 'denied'.
 *   - gtag.js is not even requested until the visitor clicks Accept
 *     (basic Consent Mode — no cookieless pings before consent).
 *   - The old "By using Zeus Beats you agree" banner flag is NOT consent.
 *   - The sign-up conversion is only pushed once gtag.js has really loaded,
 *     only marked sent when the tag hands it back via event_callback, and
 *     retried on later visits (same transaction_id) if the tag never loaded.
 *   - Storage failures fail safe: "denied" anywhere wins; unknown = no tracking.
 *   - Withdrawing consent stops everything, clears _gcl cookies/storage and
 *     reloads the page if Google's tag was already running in it.
 */
import { test, beforeEach } from 'node:test';
import assert from 'node:assert/strict';

function fakeStorage() {
  const store = new Map();
  return {
    store,
    getItem: (k) => (store.has(k) ? store.get(k) : null),
    setItem: (k, v) => store.set(k, String(v)),
    removeItem: (k) => store.delete(k),
    key: (i) => [...store.keys()][i] ?? null,
    get length() { return store.size; },
  };
}

// A fresh "page": new window/document/dataLayer. Storage + cookies survive
// between pages unless `fresh` is set, exactly like a real reload.
let jar = new Map();
let page;
function newPage({ fresh = false, cookies = {} } = {}) {
  if (fresh) {
    globalThis.localStorage = fakeStorage();
    globalThis.sessionStorage = fakeStorage();
    jar = new Map(Object.entries(cookies));
  }
  const scripts = [];
  const events = [];
  let reloads = 0;
  globalThis.window = {
    location: { hostname: 'zeusbeats.com', reload: () => { reloads += 1; } },
    dispatchEvent: (e) => { events.push(e.type); return true; },
  };
  globalThis.document = {
    createElement: (tag) => {
      const el = { tagName: tag.toUpperCase() };
      el.remove = () => { const i = scripts.indexOf(el); if (i >= 0) scripts.splice(i, 1); };
      return el;
    },
    getElementById: (id) => scripts.find((s) => s.id === id) || null,
    head: { appendChild: (el) => { scripts.push(el); return el; } },
    get cookie() { return [...jar].map(([k, v]) => `${k}=${v}`).join('; '); },
    set cookie(str) {
      const [pair, ...attrs] = str.split(';').map((s) => s.trim());
      const [name, value] = pair.split('=');
      if (attrs.some((a) => /^max-age=0$/i.test(a))) jar.delete(name); else jar.set(name, value);
    },
  };
  page = { scripts, events, get reloads() { return reloads; } };
  return page;
}

beforeEach(() => { newPage({ fresh: true, cookies: { _gcl_aw: 'GCL.1.abc', _gcl_au: '1.1.2', zeus_x: 'keep' } }); });

const ads = await import('./adsConsent.js');

const calls = () => window.dataLayer.map((args) => Array.from(args));
const isArgumentsObject = (x) => Object.prototype.toString.call(x) === '[object Arguments]';
const conversions = () => calls().filter((c) => c[0] === 'event' && c[1] === 'conversion');
const tick = () => new Promise((r) => setImmediate(r));
const tagLoads = () => { page.scripts[0].onload(); return tick(); };
const tagFails = () => { page.scripts[0].onerror(); return tick(); };
// gtag.js calls event_callback once it has processed the event.
const tagHandsOff = async () => { for (const c of conversions()) c[2].event_callback?.(); await tick(); };
const grantedPage = (opts) => { ads.initConsentMode(opts); ads.setConsent('granted'); };
const pending = () => JSON.parse(localStorage.getItem(ads.PENDING_STORAGE_KEY) || '[]');

// ── basics ──────────────────────────────────────────────────────────────────

test('IDs match the Google Ads snippet', () => {
  assert.equal(ads.GOOGLE_ADS_ID, 'AW-18517714190');
  assert.equal(ads.SIGNUP_CONVERSION_LABEL, 'o7SdCLShsZ8dEI7K9_1E');
});

test('first thing pushed is the Consent Mode v2 default: all four signals denied', () => {
  ads.initConsentMode();
  const [first] = calls();
  assert.deepEqual(first.slice(0, 2), ['consent', 'default']);
  for (const k of ['ad_storage', 'ad_user_data', 'ad_personalization', 'analytics_storage']) {
    assert.equal(first[2][k], 'denied', k);
  }
});

test('gtag pushes real Arguments objects (gtag.js ignores plain arrays)', () => {
  grantedPage();
  assert.ok(window.dataLayer.length > 2);
  assert.ok(window.dataLayer.every(isArgumentsObject));
});

test('no choice yet: gtag.js is not loaded and nothing is granted', () => {
  ads.initConsentMode();
  assert.equal(ads.readConsent(), null);
  assert.equal(page.scripts.length, 0);
  assert.ok(!calls().some((c) => c[0] === 'consent' && c[1] === 'update'));
  assert.ok(!calls().some((c) => c[0] === 'config'));
});

test('the old implied-consent banner flag does not count as consent', () => {
  localStorage.setItem('zeus_cookie_accepted', '1');
  ads.initConsentMode();
  assert.equal(ads.readConsent(), null);
  assert.equal(page.scripts.length, 0);
});

test('Accept: grants ad storage + ad user data only, loads gtag.js once, configures the tag once', () => {
  ads.initConsentMode();
  ads.setConsent('granted');
  ads.setConsent('granted');
  assert.equal(ads.readConsent(), 'granted');
  assert.equal(page.scripts.length, 1);
  assert.equal(page.scripts[0].src, 'https://www.googletagmanager.com/gtag/js?id=AW-18517714190');
  assert.equal(page.scripts[0].async, true);
  const update = calls().find((c) => c[0] === 'consent' && c[1] === 'update');
  assert.deepEqual(update[2], {
    ad_storage: 'granted', ad_user_data: 'granted',
    ad_personalization: 'denied', // the banner asks about measuring sign-ups, not remarketing
    analytics_storage: 'denied', // no analytics product is used — nothing to consent to
  });
  assert.equal(calls().filter((c) => c[0] === 'config' && c[1] === 'AW-18517714190').length, 1);
  const i = calls().findIndex((c) => c[0] === 'consent' && c[1] === 'update');
  assert.ok(i < calls().findIndex((c) => c[0] === 'config'), 'consent update before config');
});

test('a returning visitor who accepted earlier gets the tag on page load', () => {
  grantedPage();
  newPage();
  ads.initConsentMode();
  assert.equal(page.scripts.length, 1);
});

test('Reject: nothing loads, denied is recorded and existing Google Ads cookies are cleared', () => {
  ads.initConsentMode();
  ads.setConsent('denied');
  assert.equal(ads.readConsent(), 'denied');
  assert.equal(page.scripts.length, 0);
  assert.ok(!jar.has('_gcl_aw') && !jar.has('_gcl_au'));
  assert.equal(jar.get('zeus_x'), 'keep');
  assert.equal(page.reloads, 0, 'no reload needed — the tag never ran on this page');
});

test('garbage in storage is treated as no choice', () => {
  ads.initConsentMode();
  localStorage.setItem(ads.CONSENT_STORAGE_KEY, '{nope');
  assert.equal(ads.readConsent(), null);
  localStorage.setItem(ads.CONSENT_STORAGE_KEY, JSON.stringify({ ads: 'maybe' }));
  assert.equal(ads.readConsent(), null);
});

test('inside the iOS app the tag never loads, even with consent', async () => {
  localStorage.setItem(ads.CONSENT_STORAGE_KEY, JSON.stringify({ ads: 'granted', v: 1, ts: 1 }));
  ads.initConsentMode({ blocked: true });
  ads.setConsent('granted');
  assert.equal(page.scripts.length, 0);
  assert.equal(await ads.trackSignupConversion(42), 'skipped');
});

test('openCookieSettings asks the banner to reappear', () => {
  ads.openCookieSettings();
  assert.deepEqual(page.events, [ads.COOKIE_SETTINGS_EVENT]);
});

// ── sign-up conversion: happy path and de-duplication ──────────────────────

test('without consent no conversion is sent or stored', async () => {
  ads.initConsentMode();
  assert.equal(await ads.trackSignupConversion(42), 'skipped');
  ads.setConsent('denied');
  assert.equal(await ads.trackSignupConversion(42), 'skipped');
  assert.equal(conversions().length, 0);
  assert.deepEqual(pending(), []);
});

test('with consent: one labelled conversion, user id as transaction_id, handed off via the tag', async () => {
  grantedPage();
  const p = ads.trackSignupConversion(42);
  await tagLoads();
  assert.equal(conversions().length, 1);
  const [[, , params]] = conversions();
  assert.equal(params.send_to, 'AW-18517714190/o7SdCLShsZ8dEI7K9_1E');
  assert.equal(params.transaction_id, '42');
  assert.equal(typeof params.event_callback, 'function');
  await tagHandsOff();
  assert.equal(await p, 'handed-off');
  assert.deepEqual(pending(), []);
});

test('the same user id never converts twice (refresh, back button, double submit)', async () => {
  grantedPage();
  const a = ads.trackSignupConversion(42);
  const b = ads.trackSignupConversion(42); // double submit while the tag is still loading
  await tagLoads();
  await tagHandsOff();
  assert.equal(await a, 'handed-off');
  assert.equal(await b, 'skipped');
  assert.equal(await ads.trackSignupConversion('42'), 'skipped');
  assert.equal(conversions().length, 1);
  newPage(); // reload
  ads.initConsentMode();
  await tagLoads();
  assert.equal(conversions().length, 0, 'nothing re-sent after a confirmed hand-off');
});

test('a missing user id sends nothing', async () => {
  grantedPage();
  for (const id of [undefined, null, '']) assert.equal(await ads.trackSignupConversion(id), 'skipped');
  assert.equal(conversions().length, 0);
});

// ── BLOCKER 1: lost conversions ─────────────────────────────────────────────

test('B1: nothing is pushed or marked sent before gtag.js has loaded', async () => {
  grantedPage();
  ads.trackSignupConversion(42);
  await tick();
  assert.equal(conversions().length, 0, 'event must wait for the tag');
  assert.deepEqual(pending().map((r) => r.id), ['42'], 'kept as pending until handed off');
});

test('B1: loaded but not yet handed off is still pending (not marked sent)', async () => {
  grantedPage();
  ads.trackSignupConversion(42);
  await tagLoads();
  assert.equal(conversions().length, 1);
  assert.deepEqual(pending().map((r) => r.id), ['42']);
  newPage();
  ads.initConsentMode();
  await tagLoads();
  assert.equal(conversions().length, 1, 'retried on the next visit');
  assert.equal(conversions()[0][2].transaction_id, '42', 'same transaction_id — Google drops duplicates');
});

test('B1: tag fails to load → conversion stays pending, nothing marked sent', async () => {
  grantedPage();
  const p = ads.trackSignupConversion(42);
  await tagFails();
  assert.equal(await p, 'pending');
  assert.equal(conversions().length, 0);
  assert.deepEqual(pending().map((r) => r.id), ['42']);
  assert.equal(page.scripts.length, 0, 'failed script removed so a retry can load it again');
});

test('B1: after a failed load the next visit retries with the same transaction_id and then stops', async () => {
  grantedPage();
  ads.trackSignupConversion(42);
  await tagFails();
  newPage();
  ads.initConsentMode();
  await tagLoads();
  assert.equal(conversions().length, 1);
  assert.equal(conversions()[0][2].transaction_id, '42');
  await tagHandsOff();
  assert.deepEqual(pending(), []);
  newPage();
  ads.initConsentMode();
  await tagLoads();
  assert.equal(conversions().length, 0, 'not sent again once handed off');
});

test('B1: a failed load can be retried in the same page (script re-added)', async () => {
  grantedPage();
  ads.trackSignupConversion(42);
  await tagFails();
  const p = ads.trackSignupConversion(43);
  assert.equal(page.scripts.length, 1);
  await tagLoads();
  await tagHandsOff();
  assert.equal(await p, 'handed-off');
});

test('B1: a tag that never loads times out and stays pending', async () => {
  grantedPage({ tagTimeoutMs: 5 });
  const status = await ads.trackSignupConversion(42);
  assert.equal(status, 'pending');
  assert.equal(conversions().length, 0);
  assert.deepEqual(pending().map((r) => r.id), ['42']);
});

test('B1: retries give up after 5 attempts or 30 days', async () => {
  grantedPage();
  ads.trackSignupConversion(42);
  await tagFails();
  for (let i = 0; i < 6; i++) { newPage(); ads.initConsentMode(); if (page.scripts[0]) await tagFails(); }
  assert.deepEqual(pending(), [], 'dropped after 5 attempts');
  localStorage.setItem(ads.PENDING_STORAGE_KEY, JSON.stringify([{ id: '7', ts: Date.now() - 31 * 864e5, attempts: 0 }]));
  newPage();
  ads.initConsentMode();
  assert.deepEqual(pending(), [], 'dropped after 30 days');
});

// ── BLOCKER 2: browser storage failures ─────────────────────────────────────

function breakStorage({ reads = false, writes = true } = {}) {
  const s = globalThis.localStorage;
  globalThis.localStorage = {
    getItem: (k) => { if (reads) throw new Error('blocked'); return s.getItem(k); },
    setItem: (k, v) => { if (writes) throw new Error('QuotaExceededError'); return s.setItem(k, v); },
    removeItem: (k) => s.removeItem(k),
    key: (i) => s.key(i),
    get length() { return s.length; },
  };
  return s;
}

test('B2: Reject whose localStorage write fails over an old Accept is still Reject — now and after reload', () => {
  grantedPage();
  breakStorage(); // writes throw; the old {ads:'granted'} is still in there
  ads.setConsent('denied');
  assert.equal(ads.readConsent(), 'denied');
  newPage();
  ads.initConsentMode();
  assert.equal(ads.readConsent(), 'denied');
  assert.equal(page.scripts.length, 0, 'rejected consent must never load the tag');
});

test('B2: Reject with failing writes AND cookies refused: the old Accept is removed, next page is not tracked', () => {
  grantedPage();
  jar.delete(ads.CONSENT_COOKIE);
  breakStorage(); // setItem throws, removeItem still works
  const cookie = Object.getOwnPropertyDescriptor(document, 'cookie');
  Object.defineProperty(document, 'cookie', { get: cookie.get, set() {} });
  ads.setConsent('denied');
  newPage();
  ads.initConsentMode();
  assert.notEqual(ads.readConsent(), 'granted');
  assert.equal(page.scripts.length, 0);
});

test('B2: storage that cannot be read at all means no tracking', async () => {
  grantedPage();
  breakStorage({ reads: true });
  jar.delete(ads.CONSENT_COOKIE);
  newPage();
  ads.initConsentMode();
  assert.equal(ads.readConsent(), null);
  assert.equal(page.scripts.length, 0);
  assert.equal(await ads.trackSignupConversion(42), 'skipped');
});

test('B2: conflicting records (one says granted, one says denied) mean denied', () => {
  localStorage.setItem(ads.CONSENT_STORAGE_KEY, JSON.stringify({ ads: 'granted', v: 1, ts: 1 }));
  jar.set(ads.CONSENT_COOKIE, 'denied');
  ads.initConsentMode();
  assert.equal(ads.readConsent(), 'denied');
  assert.equal(page.scripts.length, 0);
});

test('B2: Accept that cannot be saved anywhere still applies to this page only, then asks again', async () => {
  ads.initConsentMode();
  breakStorage();
  const cookieSet = Object.getOwnPropertyDescriptor(document, 'cookie');
  Object.defineProperty(document, 'cookie', { get: cookieSet.get, set() {} }); // cookies refused too
  ads.setConsent('granted');
  assert.equal(ads.readConsent(), 'granted');
  const p = ads.trackSignupConversion(42);
  await tagLoads();
  assert.equal(conversions().length, 1, 'eligible conversion not lost to a storage failure');
  await tagHandsOff();
  assert.equal(await p, 'handed-off');
  newPage();
  ads.initConsentMode();
  assert.equal(ads.readConsent(), null, 'uncertain → ask again, no tracking');
  assert.equal(page.scripts.length, 0);
});

test('B2: a failed "sent" write never throws and is retried later under the same transaction_id', async () => {
  grantedPage();
  const p = ads.trackSignupConversion(42);
  const real = breakStorage(); // pending already written; the "sent" write will fail
  await tagLoads();
  await tagHandsOff();
  assert.equal(await p, 'handed-off');
  globalThis.localStorage = real;
  newPage();
  ads.initConsentMode();
  await tagLoads();
  const re = conversions();
  assert.ok(re.length <= 1);
  if (re.length) assert.equal(re[0][2].transaction_id, '42', 'any retry reuses the transaction_id');
});

test('B2: nothing in this module throws when storage and cookies are unavailable', async () => {
  globalThis.localStorage = { getItem() { throw new Error('x'); }, setItem() { throw new Error('x'); }, removeItem() { throw new Error('x'); }, key() { throw new Error('x'); }, get length() { throw new Error('x'); } };
  globalThis.sessionStorage = globalThis.localStorage;
  Object.defineProperty(document, 'cookie', { get() { throw new Error('x'); }, set() { throw new Error('x'); } });
  assert.doesNotThrow(() => ads.initConsentMode());
  assert.doesNotThrow(() => ads.setConsent('granted'));
  assert.doesNotThrow(() => ads.setConsent('denied'));
  assert.equal(await ads.trackSignupConversion(7), 'skipped');
});

// ── BLOCKER 3: consent withdrawal ───────────────────────────────────────────

test('B3: withdrawing after Accept pushes denied, deletes _gcl cookies AND _gcl storage, reloads to remove the tag', async () => {
  grantedPage();
  await tagLoads();
  jar.set('_gcl_au', '1.1.9');
  localStorage.setItem('_gcl_ls', '{"x":1}');
  sessionStorage.setItem('_gcl_tmp', '1');
  const result = ads.setConsent('denied');
  const last = calls().filter((c) => c[0] === 'consent' && c[1] === 'update').at(-1)[2];
  for (const k of ['ad_storage', 'ad_user_data', 'ad_personalization', 'analytics_storage']) assert.equal(last[k], 'denied', k);
  assert.ok(![...jar.keys()].some((k) => k.startsWith('_gcl')));
  assert.equal(localStorage.getItem('_gcl_ls'), null);
  assert.equal(sessionStorage.getItem('_gcl_tmp'), null);
  assert.deepEqual(result, { persisted: true, reloading: true });
  assert.equal(page.reloads, 1, 'reload: the running Google tag cannot be switched off any other way');
  newPage();
  ads.initConsentMode();
  assert.equal(page.scripts.length, 0, 'tag not loaded after the reload');
});

test('B3: withdrawal cancels any conversion not yet handed to Google', async () => {
  grantedPage();
  ads.trackSignupConversion(42);
  await tagFails();
  assert.deepEqual(pending().map((r) => r.id), ['42']);
  ads.setConsent('denied');
  assert.deepEqual(pending(), []);
  ads.setConsent('granted'); // even accepting again later must not send it
  newPage();
  ads.initConsentMode();
  await tagLoads();
  assert.equal(conversions().length, 0);
});

test('B3: withdrawing while the tag is still loading — the conversion is never pushed', async () => {
  grantedPage();
  const p = ads.trackSignupConversion(42);
  ads.setConsent('denied');
  await tagLoads();
  assert.equal(await p, 'skipped');
  assert.equal(conversions().length, 0);
});

test('B3: after withdrawal no further conversions are sent', async () => {
  grantedPage();
  await tagLoads();
  ads.setConsent('denied');
  assert.equal(await ads.trackSignupConversion(43), 'skipped');
  assert.equal(conversions().length, 0);
});

test('B3: if the withdrawal cannot be saved, do not reload (it would bring the old Accept back)', async () => {
  grantedPage();
  await tagLoads();
  const real = globalThis.localStorage;
  globalThis.localStorage = {
    getItem: (k) => real.getItem(k), // the old {ads:'granted'} is still readable
    setItem() { throw new Error('QuotaExceededError'); },
    removeItem() { throw new Error('x'); },
    key: (i) => real.key(i),
    get length() { return real.length; },
  };
  Object.defineProperty(document, 'cookie', { get: () => '', set() {} });
  const result = ads.setConsent('denied');
  assert.deepEqual(result, { persisted: false, reloading: false });
  assert.equal(page.reloads, 0);
  assert.equal(ads.readConsent(), 'denied', 'still denied for the rest of this page');
  assert.equal(await ads.trackSignupConversion(44), 'skipped');
  globalThis.localStorage = real;
});
