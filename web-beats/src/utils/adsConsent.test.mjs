/**
 * Google Ads: standard sitewide Google tag with basic Consent Mode v2
 * (UK PECR: advertising cookies need opt-in).
 *
 * The rules these tests pin down:
 *   - Nothing from Google before consent: only the all-denied Consent Mode
 *     default is pushed; gtag.js is not requested until the visitor accepts.
 *   - After Accept, the standard Google tag runs on every page (config, page
 *     views) with ad_storage + ad_user_data granted; ad_personalization and
 *     analytics_storage stay denied.
 *   - The old "By using Zeus Beats you agree" banner flag is NOT consent.
 *   - Only a successful registration fires a conversion. Its transaction_id is
 *     a random conversion id made once per sign-up — never the user id — and
 *     reused for every retry, so Google drops duplicates.
 *   - A sign-up stays pending until gtag.js has loaded and handed it back via
 *     event_callback; retried on later visits (max 5 tries, 30 days).
 *   - Storage failures fail safe: "denied" anywhere wins; unknown = no tracking.
 *   - Reject / withdrawal: denied pushed, pending cancelled, _gcl cookies and
 *     storage cleared, page reloaded if the tag was running.
 */
import { test, beforeEach } from 'node:test';
import assert from 'node:assert/strict';

const UUID_RE = /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/;

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

const calls = () => (window.dataLayer || []).map((args) => Array.from(args));
const isArgumentsObject = (x) => Object.prototype.toString.call(x) === '[object Arguments]';
const conversions = () => calls().filter((c) => c[0] === 'event' && c[1] === 'conversion');
const tick = () => new Promise((r) => setImmediate(r));
// (no-ops when the tag was never requested)
const tagLoads = () => { page.scripts[0]?.onload(); return tick(); };
const tagFails = () => { page.scripts[0]?.onerror(); return tick(); };
// gtag.js calls event_callback once it has processed the event.
const tagHandsOff = async () => { for (const c of conversions()) c[2].event_callback?.(); await tick(); };
const grantedPage = (opts) => { ads.initConsentMode(opts); ads.setConsent('granted'); };
const pending = () => JSON.parse(localStorage.getItem(ads.PENDING_STORAGE_KEY) || '[]');
const pendingUsers = () => pending().map((r) => r.user);

// ── consent and the sitewide tag ───────────────────────────────────────────

test('IDs match the Google Ads snippet', () => {
  assert.equal(ads.GOOGLE_ADS_ID, 'AW-18517714190');
  assert.equal(ads.SIGNUP_CONVERSION_LABEL, 'o7SdCLShsZ8dEI7K9_1E');
});

test('before consent: only the all-denied Consent Mode default — no tag, no js, no config', () => {
  ads.initConsentMode();
  assert.deepEqual(calls(), [['consent', 'default', {
    ad_storage: 'denied', ad_user_data: 'denied', ad_personalization: 'denied', analytics_storage: 'denied',
  }]]);
  assert.equal(page.scripts.length, 0, 'gtag.js not requested');
  assert.equal(ads.readConsent(), null);
});

test('gtag pushes real Arguments objects (gtag.js ignores plain arrays)', () => {
  grantedPage();
  assert.ok(window.dataLayer.length > 2);
  assert.ok(window.dataLayer.every(isArgumentsObject));
});

test('the old implied-consent banner flag does not count as consent', () => {
  localStorage.setItem('zeus_cookie_accepted', '1');
  ads.initConsentMode();
  assert.equal(ads.readConsent(), null);
  assert.equal(page.scripts.length, 0);
});

test('Accept: grants ad storage + ad user data only, then loads the standard Google tag once and configures it', () => {
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
    ad_personalization: 'denied', // no remarketing / personalised ads
    analytics_storage: 'denied', // no analytics product is used
  });
  const configs = calls().filter((c) => c[0] === 'config');
  assert.deepEqual(configs, [['config', 'AW-18517714190']], 'standard sitewide config (page views included)');
  const i = calls().findIndex((c) => c[0] === 'consent' && c[1] === 'update');
  assert.ok(i < calls().findIndex((c) => c[0] === 'config'), 'consent update before config');
});

test('sitewide: a visitor who accepted gets the tag on every later page load', () => {
  grantedPage();
  for (let i = 0; i < 3; i++) {
    newPage();
    ads.initConsentMode();
    assert.equal(page.scripts.length, 1);
    assert.equal(calls().filter((c) => c[0] === 'config').length, 1);
  }
});

test('Accept on its own sends no conversion', async () => {
  grantedPage();
  await tagLoads();
  assert.equal(conversions().length, 0);
});

test('Reject: nothing loads, denied is recorded and existing Google Ads cookies are cleared', () => {
  ads.initConsentMode();
  ads.setConsent('denied');
  assert.equal(ads.readConsent(), 'denied');
  assert.equal(page.scripts.length, 0);
  assert.ok(!jar.has('_gcl_aw') && !jar.has('_gcl_au'));
  assert.equal(jar.get('zeus_x'), 'keep');
  assert.equal(page.reloads, 0, 'no reload needed — the tag never ran on this page');
  newPage();
  ads.initConsentMode();
  assert.equal(page.scripts.length, 0, 'still nothing on later pages');
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

// ── the sign-up conversion ─────────────────────────────────────────────────

test('without consent no conversion is sent or stored', async () => {
  ads.initConsentMode();
  assert.equal(await ads.trackSignupConversion(42), 'skipped');
  ads.setConsent('denied');
  assert.equal(await ads.trackSignupConversion(42), 'skipped');
  assert.equal(conversions().length, 0);
  assert.deepEqual(pending(), []);
});

test('with consent: one labelled conversion with a random conversion id, handed off via the tag', async () => {
  grantedPage();
  const p = ads.trackSignupConversion(42);
  await tagLoads();
  assert.equal(conversions().length, 1);
  const [[, , params]] = conversions();
  assert.equal(params.send_to, 'AW-18517714190/o7SdCLShsZ8dEI7K9_1E');
  assert.match(params.transaction_id, UUID_RE, 'a random v4 UUID');
  assert.notEqual(params.transaction_id, '42');
  assert.deepEqual(Object.keys(params).sort(), ['event_callback', 'send_to', 'transaction_id'], 'nothing else about the user');
  await tagHandsOff();
  assert.equal(await p, 'handed-off');
  assert.deepEqual(pending(), []);
});

test('the conversion id is random, not derived from the user id', async () => {
  const ids = [];
  for (let i = 0; i < 3; i++) {
    newPage({ fresh: true });
    grantedPage();
    ads.trackSignupConversion(42); // same user id each time, fresh browser
    await tagLoads();
    ids.push(conversions()[0][2].transaction_id);
  }
  assert.equal(new Set(ids).size, 3, 'a new random id each time');
  for (const id of ids) assert.match(id, UUID_RE);
});

test('the same user id never converts twice (double submit, refresh, back button)', async () => {
  grantedPage();
  const a = ads.trackSignupConversion(42);
  const b = ads.trackSignupConversion(42); // double submit while the tag is loading
  await tagLoads();
  await tagHandsOff();
  assert.equal(await a, 'handed-off');
  assert.equal(await b, 'skipped');
  assert.equal(await ads.trackSignupConversion('42'), 'skipped');
  assert.equal(conversions().length, 1);
  newPage();
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
  assert.deepEqual(pendingUsers(), ['42'], 'kept as pending until handed off');
  assert.match(pending()[0].cid, UUID_RE);
});

test('B1: loaded but not yet handed off is still pending, and retried with the SAME conversion id', async () => {
  grantedPage();
  ads.trackSignupConversion(42);
  await tagLoads();
  const first = conversions()[0][2].transaction_id;
  assert.deepEqual(pendingUsers(), ['42']);
  newPage();
  ads.initConsentMode();
  await tagLoads();
  assert.equal(conversions().length, 1, 'retried on the next visit');
  assert.equal(conversions()[0][2].transaction_id, first, 'same conversion id — Google drops duplicates');
});

test('B1: tag fails to load → conversion stays pending, nothing marked sent', async () => {
  grantedPage();
  const p = ads.trackSignupConversion(42);
  await tagFails();
  assert.equal(await p, 'pending');
  assert.equal(conversions().length, 0);
  assert.deepEqual(pendingUsers(), ['42']);
  assert.equal(page.scripts.length, 0, 'failed script removed so a retry can load it again');
});

test('B1: after a failed load the next visit retries with the same conversion id and then stops', async () => {
  grantedPage();
  ads.trackSignupConversion(42);
  const cid = pending()[0].cid;
  await tagFails();
  newPage();
  ads.initConsentMode();
  await tagLoads();
  assert.equal(conversions().length, 1);
  assert.equal(conversions()[0][2].transaction_id, cid);
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
  assert.deepEqual(pendingUsers(), ['42']);
});

test('B1: retries give up after 5 attempts or 30 days', async () => {
  grantedPage();
  ads.trackSignupConversion(42);
  await tagFails();
  for (let i = 0; i < 6; i++) { newPage(); ads.initConsentMode(); await tagFails(); }
  assert.deepEqual(pending(), [], 'dropped after 5 attempts');
  localStorage.setItem(ads.PENDING_STORAGE_KEY, JSON.stringify([
    { user: '7', cid: '11111111-1111-4111-8111-111111111111', ts: Date.now() - 31 * 864e5, attempts: 0 },
  ]));
  newPage();
  ads.initConsentMode();
  assert.deepEqual(pending(), [], 'dropped after 30 days');
});

test('B1: a pending record without a valid conversion id is dropped, never sent with a made-up one', async () => {
  localStorage.setItem(ads.PENDING_STORAGE_KEY, JSON.stringify([{ user: '9', cid: '9', ts: Date.now(), attempts: 0 }]));
  grantedPage();
  await tagLoads();
  assert.equal(conversions().length, 0);
  assert.deepEqual(pending(), []);
});

// ── BLOCKER 2: browser storage failures ─────────────────────────────────────

function breakStorage({ reads = false } = {}) {
  const s = globalThis.localStorage;
  globalThis.localStorage = {
    getItem: (k) => { if (reads) throw new Error('blocked'); return s.getItem(k); },
    setItem: () => { throw new Error('QuotaExceededError'); },
    removeItem: (k) => s.removeItem(k),
    key: (i) => s.key(i),
    get length() { return s.length; },
  };
  return s;
}
const refuseCookies = () => {
  const d = Object.getOwnPropertyDescriptor(document, 'cookie');
  Object.defineProperty(document, 'cookie', { get: d.get, set() {} });
};

test('B2: Reject whose localStorage write fails over an old Accept is still Reject — now and after reload', () => {
  grantedPage();
  breakStorage(); // the old {ads:'granted'} is still in there
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
  refuseCookies();
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
  refuseCookies();
  ads.setConsent('granted');
  assert.equal(ads.readConsent(), 'granted');
  const p = ads.trackSignupConversion(42);
  await tagLoads();
  assert.equal(conversions().length, 1, 'eligible conversion not lost to a storage failure');
  assert.match(conversions()[0][2].transaction_id, UUID_RE);
  await tagHandsOff();
  assert.equal(await p, 'handed-off');
  newPage();
  ads.initConsentMode();
  assert.equal(ads.readConsent(), null, 'uncertain → ask again, no tracking');
  assert.equal(page.scripts.length, 0);
});

test('B2: a failed "sent" write never throws and any retry reuses the conversion id', async () => {
  grantedPage();
  const p = ads.trackSignupConversion(42);
  const cid = pending()[0].cid;
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
  if (re.length) assert.equal(re[0][2].transaction_id, cid, 'any retry reuses the conversion id');
});

test('B2: nothing in this module throws when storage and cookies are unavailable', async () => {
  const boom = () => { throw new Error('x'); };
  globalThis.localStorage = { getItem: boom, setItem: boom, removeItem: boom, key: boom, get length() { return boom(); } };
  globalThis.sessionStorage = globalThis.localStorage;
  Object.defineProperty(document, 'cookie', { get: boom, set: boom });
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

test('B3: withdrawal cancels any conversion not yet handed to Google — for good', async () => {
  grantedPage();
  ads.trackSignupConversion(42);
  await tagFails();
  assert.deepEqual(pendingUsers(), ['42']);
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
