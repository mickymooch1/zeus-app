/**
 * Google Ads sign-up conversion + Consent Mode v2 (UK PECR: opt-in only).
 *
 * The rules these tests pin down:
 *   - Google's tag never runs on the app's pages: the main page only pushes the
 *     all-denied Consent Mode default. Each consented sign-up gets a hidden
 *     /ads-frame.html frame that sends that one conversion and is removed.
 *   - The old "By using Zeus Beats you agree" banner flag is NOT consent.
 *   - A sign-up stays pending until the frame reports the tag took it, and is
 *     retried on later visits (same transaction_id) — max 5 tries, 30 days.
 *   - Storage failures fail safe: "denied" anywhere wins; unknown = no tracking.
 *   - Withdrawing consent stops sends in progress, cancels pending sign-ups,
 *     forgets the ad click and deletes Google's _gcl cookies/storage.
 */
import { test, beforeEach } from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const ORIGIN = 'https://zeusbeats.com';

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
function newPage({ fresh = false, cookies = {}, search = '' } = {}) {
  if (fresh) {
    globalThis.localStorage = fakeStorage();
    globalThis.sessionStorage = fakeStorage();
    jar = new Map(Object.entries(cookies));
  }
  const frames = [];
  const events = [];
  const listeners = new Set();
  globalThis.window = {
    location: { hostname: 'zeusbeats.com', origin: ORIGIN, search },
    dispatchEvent: (e) => { events.push(e.type); return true; },
    addEventListener: (type, fn) => { if (type === 'message') listeners.add(fn); },
    removeEventListener: (type, fn) => { if (type === 'message') listeners.delete(fn); },
  };
  const body = { appendChild: (el) => { frames.push(el); return el; } };
  globalThis.document = {
    body,
    createElement: (tag) => {
      const el = { tagName: tag.toUpperCase(), attrs: {}, style: {}, contentWindow: { name: 'frame-window' } };
      el.setAttribute = (k, v) => { el.attrs[k] = v; };
      el.remove = () => { const i = frames.indexOf(el); if (i >= 0) frames.splice(i, 1); el.removed = true; };
      return el;
    },
    get cookie() { return [...jar].map(([k, v]) => `${k}=${v}`).join('; '); },
    set cookie(str) {
      const [pair, ...attrs] = str.split(';').map((s) => s.trim());
      const [name, value] = pair.split('=');
      if (attrs.some((a) => /^max-age=0$/i.test(a))) jar.delete(name); else jar.set(name, value);
    },
  };
  page = { frames, events, listeners };
  return page;
}

beforeEach(() => { newPage({ fresh: true, cookies: { _gcl_au: '1.1.2', zeus_x: 'keep' }, search: '?gclid=TEST' }); });

const ads = await import('./adsConsent.js');

const calls = () => (window.dataLayer || []).map((args) => Array.from(args));
const isArgumentsObject = (x) => Object.prototype.toString.call(x) === '[object Arguments]';
const tick = () => new Promise((r) => setImmediate(r));
const tidOf = (frame) => decodeURIComponent(frame.src.split('#tid=')[1]);
// The frame posting back to the app (see public/ads-frame.js).
async function frameSays(status, { frame = page.frames[0], tid, origin = ORIGIN, source } = {}) {
  const e = { source: source ?? frame.contentWindow, origin, data: { type: 'zeus-ads-frame', tid: tid ?? tidOf(frame), status } };
  for (const fn of [...page.listeners]) fn(e);
  await tick();
}
const grantedPage = (opts) => { ads.initConsentMode(opts); ads.setConsent('granted'); };
const pending = () => JSON.parse(localStorage.getItem(ads.PENDING_STORAGE_KEY) || '[]');

// ── basics ──────────────────────────────────────────────────────────────────

test('IDs match the Google Ads snippet, and the frame script uses the same ones', () => {
  assert.equal(ads.GOOGLE_ADS_ID, 'AW-18517714190');
  assert.equal(ads.SIGNUP_CONVERSION_LABEL, 'o7SdCLShsZ8dEI7K9_1E');
  const here = path.dirname(fileURLToPath(import.meta.url));
  const frameJs = fs.readFileSync(path.join(here, '..', '..', 'public', 'ads-frame.js'), 'utf8');
  assert.match(frameJs, /var ADS_ID = 'AW-18517714190';/);
  assert.match(frameJs, /var LABEL = 'o7SdCLShsZ8dEI7K9_1E';/);
  assert.ok(frameJs.includes(`'${ads.FRAME_MESSAGE_TYPE}'`));
});

test('the main page only ever pushes the all-denied Consent Mode default — even after Accept and a sign-up', async () => {
  grantedPage();
  const p = ads.trackSignupConversion(42);
  await frameSays('handed-off');
  await p;
  const all = calls();
  assert.equal(all.length, 1);
  assert.deepEqual(all[0], ['consent', 'default', {
    ad_storage: 'denied', ad_user_data: 'denied', ad_personalization: 'denied', analytics_storage: 'denied',
  }]);
  assert.ok(window.dataLayer.every(isArgumentsObject));
});

test('no choice yet: no frame, nothing granted', () => {
  ads.initConsentMode();
  assert.equal(ads.readConsent(), null);
  assert.equal(page.frames.length, 0);
});

test('the old implied-consent banner flag does not count as consent', async () => {
  localStorage.setItem('zeus_cookie_accepted', '1');
  ads.initConsentMode();
  assert.equal(ads.readConsent(), null);
  assert.equal(await ads.trackSignupConversion(42), 'skipped');
  assert.equal(page.frames.length, 0);
});

test('Accept on its own sends nothing — not even from an ad click', () => {
  grantedPage();
  assert.equal(ads.readConsent(), 'granted');
  assert.equal(page.frames.length, 0);
  newPage({ search: '?gclid=AGAIN' });
  ads.initConsentMode();
  assert.equal(page.frames.length, 0, 'a returning visitor who accepted: nothing on page load');
});

test('Reject: nothing sent, denied recorded, existing Google Ads cookies cleared', async () => {
  ads.initConsentMode();
  ads.setConsent('denied');
  assert.equal(ads.readConsent(), 'denied');
  assert.equal(await ads.trackSignupConversion(42), 'skipped');
  assert.equal(page.frames.length, 0);
  assert.ok(!jar.has('_gcl_au'));
  assert.equal(jar.get('zeus_x'), 'keep');
});

test('garbage in storage is treated as no choice', () => {
  ads.initConsentMode();
  localStorage.setItem(ads.CONSENT_STORAGE_KEY, '{nope');
  assert.equal(ads.readConsent(), null);
  localStorage.setItem(ads.CONSENT_STORAGE_KEY, JSON.stringify({ ads: 'maybe' }));
  assert.equal(ads.readConsent(), null);
});

test('inside the iOS app nothing is ever sent, even with consent', async () => {
  localStorage.setItem(ads.CONSENT_STORAGE_KEY, JSON.stringify({ ads: 'granted', v: 1, ts: 1 }));
  ads.initConsentMode({ blocked: true });
  ads.setConsent('granted');
  assert.equal(await ads.trackSignupConversion(42), 'skipped');
  assert.equal(page.frames.length, 0);
});

test('openCookieSettings asks the banner to reappear', () => {
  ads.openCookieSettings();
  assert.deepEqual(page.events, [ads.COOKIE_SETTINGS_EVENT]);
});

// ── the sign-up conversion ─────────────────────────────────────────────────

test('without consent no conversion is sent or stored', async () => {
  ads.initConsentMode();
  assert.equal(await ads.trackSignupConversion(42), 'skipped');
  assert.deepEqual(pending(), []);
  assert.equal(page.frames.length, 0);
});

test('with consent: one hidden frame carrying the ad click and the user id; removed once handed off', async () => {
  grantedPage();
  const p = ads.trackSignupConversion(42);
  assert.equal(page.frames.length, 1);
  const [frame] = page.frames;
  assert.equal(frame.tagName, 'IFRAME');
  assert.equal(frame.src, '/ads-frame.html?gclid=TEST#tid=42');
  assert.equal(frame.attrs['aria-hidden'], 'true');
  assert.match(frame.style.cssText, /visibility:hidden/);
  await frameSays('handed-off');
  assert.equal(await p, 'handed-off');
  assert.equal(page.frames.length, 0, 'frame removed — the tag is gone');
  assert.equal(page.listeners.size, 0, 'message listener removed');
  assert.deepEqual(pending(), []);
});

test('the same user id never converts twice (double submit, refresh, back button)', async () => {
  grantedPage();
  const a = ads.trackSignupConversion(42);
  const b = ads.trackSignupConversion(42); // double submit while sending
  assert.equal(page.frames.length, 1);
  await frameSays('handed-off');
  assert.equal(await a, 'handed-off');
  assert.equal(await b, 'skipped');
  assert.equal(await ads.trackSignupConversion('42'), 'skipped');
  newPage();
  ads.initConsentMode();
  assert.equal(page.frames.length, 0, 'nothing re-sent after a confirmed hand-off');
});

test('a missing user id sends nothing', async () => {
  grantedPage();
  for (const id of [undefined, null, '']) assert.equal(await ads.trackSignupConversion(id), 'skipped');
  assert.equal(page.frames.length, 0);
});

test('messages from anything but this frame, this origin and this sign-up are ignored', async () => {
  grantedPage();
  const p = ads.trackSignupConversion(42);
  await frameSays('handed-off', { origin: 'https://evil.example' });
  await frameSays('handed-off', { source: { other: true } });
  await frameSays('handed-off', { tid: '99' });
  assert.equal(page.frames.length, 1, 'still waiting');
  await frameSays('handed-off');
  assert.equal(await p, 'handed-off');
});

test('ad click: remembered after Accept for a sign-up on a later visit (90 days), never without consent', async () => {
  newPage({ search: '?utm_source=ad&gbraid=GB-1&wbraid=bad%20value!' });
  ads.initConsentMode();
  assert.equal(localStorage.getItem(ads.CLICK_STORAGE_KEY), null, 'not stored before consent');
  ads.setConsent('granted');
  newPage({ search: '' }); // comes back later, no click in the URL
  ads.initConsentMode();
  ads.trackSignupConversion(7);
  assert.equal(page.frames[0].src, '/ads-frame.html?gbraid=GB-1#tid=7', 'malformed wbraid dropped');
  const stored = JSON.parse(localStorage.getItem(ads.CLICK_STORAGE_KEY));
  localStorage.setItem(ads.CLICK_STORAGE_KEY, JSON.stringify({ ...stored, ts: Date.now() - 91 * 864e5 }));
  newPage({ search: '' });
  ads.initConsentMode();
  ads.trackSignupConversion(8);
  // (sign-up 7 was never confirmed, so it is retried here too — also without the expired click)
  assert.deepEqual(page.frames.map((f) => f.src), ['/ads-frame.html#tid=7', '/ads-frame.html#tid=8'], 'older than 90 days: no click');
});

// ── BLOCKER 1: lost conversions ─────────────────────────────────────────────

test('B1: not marked sent until the frame says the tag took it', async () => {
  grantedPage();
  ads.trackSignupConversion(42);
  await tick();
  assert.deepEqual(pending().map((r) => r.id), ['42']);
  assert.equal(localStorage.getItem('zeus_ads_signup_sent_42'), null);
});

test('B1: tag fails to load in the frame → pending, frame removed, can retry on the same page', async () => {
  grantedPage();
  const p = ads.trackSignupConversion(42);
  await frameSays('failed');
  assert.equal(await p, 'pending');
  assert.equal(page.frames.length, 0);
  assert.deepEqual(pending().map((r) => r.id), ['42']);
  const again = ads.trackSignupConversion(42);
  assert.equal(page.frames.length, 1, 'retried');
  assert.equal(tidOf(page.frames[0]), '42');
  await frameSays('handed-off');
  assert.equal(await again, 'handed-off');
});

test('B1: no answer from the frame → times out, pending, not re-sent on this page', async () => {
  grantedPage({ sendTimeoutMs: 5 });
  const status = await ads.trackSignupConversion(42);
  assert.equal(status, 'pending');
  assert.equal(page.frames.length, 0, 'frame removed on timeout');
  assert.equal(await ads.trackSignupConversion(42), 'skipped', 'unknown outcome: not again on this page');
  assert.deepEqual(pending().map((r) => r.id), ['42']);
});

test('B1: a later visit retries with the same transaction id, then never again', async () => {
  grantedPage();
  ads.trackSignupConversion(42);
  await frameSays('failed');
  newPage();
  ads.initConsentMode();
  assert.equal(page.frames.length, 1);
  assert.equal(tidOf(page.frames[0]), '42');
  await frameSays('handed-off');
  assert.deepEqual(pending(), []);
  newPage();
  ads.initConsentMode();
  assert.equal(page.frames.length, 0);
});

test('B1: retries give up after 5 attempts or 30 days', async () => {
  grantedPage();
  ads.trackSignupConversion(42);
  await frameSays('failed');
  for (let i = 0; i < 6; i++) { newPage(); ads.initConsentMode(); if (page.frames[0]) await frameSays('failed'); }
  assert.deepEqual(pending(), [], 'dropped after 5 attempts');
  localStorage.setItem(ads.PENDING_STORAGE_KEY, JSON.stringify([{ id: '7', ts: Date.now() - 31 * 864e5, attempts: 0 }]));
  newPage();
  ads.initConsentMode();
  assert.deepEqual(pending(), [], 'dropped after 30 days');
  assert.equal(page.frames.length, 0);
});

test('B1: a stale send for the same user id can never swallow a newer one', async () => {
  grantedPage({ sendTimeoutMs: 30 });
  const old = ads.trackSignupConversion(42); // never answered
  newPage();
  ads.initConsentMode({ sendTimeoutMs: 60 }); // re-initialised while the old send is still out
  const fresh = ads.trackSignupConversion(42);
  assert.equal(await old, 'skipped', 're-initialising cancels the old send');
  await new Promise((r) => setTimeout(r, 100));
  const settled = await Promise.race([fresh, new Promise((r) => setTimeout(() => r('HUNG'), 200))]);
  assert.notEqual(settled, 'HUNG', 'the newer send must still settle on its own timeout');
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

test('B2: Reject whose localStorage write fails over an old Accept is still Reject — now and after reload', async () => {
  grantedPage();
  breakStorage(); // the old {ads:'granted'} is still in there
  ads.setConsent('denied');
  assert.equal(ads.readConsent(), 'denied');
  newPage();
  ads.initConsentMode();
  assert.equal(ads.readConsent(), 'denied');
  assert.equal(await ads.trackSignupConversion(42), 'skipped');
});

test('B2: Reject with failing writes AND cookies refused: the old Accept is removed, next page is not tracked', async () => {
  grantedPage();
  jar.delete(ads.CONSENT_COOKIE);
  breakStorage(); // setItem throws, removeItem still works
  refuseCookies();
  ads.setConsent('denied');
  newPage();
  ads.initConsentMode();
  assert.notEqual(ads.readConsent(), 'granted');
  assert.equal(await ads.trackSignupConversion(42), 'skipped');
});

test('B2: storage that cannot be read at all means no tracking', async () => {
  grantedPage();
  breakStorage({ reads: true });
  jar.delete(ads.CONSENT_COOKIE);
  newPage();
  ads.initConsentMode();
  assert.equal(ads.readConsent(), null);
  assert.equal(await ads.trackSignupConversion(42), 'skipped');
});

test('B2: conflicting records (one says granted, one says denied) mean denied', async () => {
  localStorage.setItem(ads.CONSENT_STORAGE_KEY, JSON.stringify({ ads: 'granted', v: 1, ts: 1 }));
  jar.set(ads.CONSENT_COOKIE, 'denied');
  ads.initConsentMode();
  assert.equal(ads.readConsent(), 'denied');
  assert.equal(await ads.trackSignupConversion(42), 'skipped');
});

test('B2: Accept that cannot be saved anywhere still applies to this page only, then asks again', async () => {
  ads.initConsentMode();
  breakStorage();
  refuseCookies();
  ads.setConsent('granted');
  assert.equal(ads.readConsent(), 'granted');
  const p = ads.trackSignupConversion(42);
  assert.equal(page.frames.length, 1, 'eligible conversion not lost to a storage failure');
  await frameSays('handed-off');
  assert.equal(await p, 'handed-off');
  newPage();
  ads.initConsentMode();
  assert.equal(ads.readConsent(), null, 'uncertain → ask again, no tracking');
});

test('B2: a failed "sent" write never throws and any retry reuses the transaction id', async () => {
  grantedPage();
  const p = ads.trackSignupConversion(42);
  const real = breakStorage(); // pending already written; the "sent" write will fail
  await frameSays('handed-off');
  assert.equal(await p, 'handed-off');
  globalThis.localStorage = real;
  newPage();
  ads.initConsentMode();
  assert.ok(page.frames.length <= 1);
  if (page.frames.length) assert.equal(tidOf(page.frames[0]), '42');
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

test('B3: withdrawal deletes _gcl cookies, _gcl storage and the remembered ad click', () => {
  grantedPage();
  assert.ok(localStorage.getItem(ads.CLICK_STORAGE_KEY));
  jar.set('_gcl_aw', 'GCL.1.x');
  localStorage.setItem('_gcl_ls', '{"x":1}');
  sessionStorage.setItem('_gcl_tmp', '1');
  const result = ads.setConsent('denied');
  assert.deepEqual(result, { persisted: true });
  assert.ok(![...jar.keys()].some((k) => k.startsWith('_gcl')));
  assert.equal(localStorage.getItem('_gcl_ls'), null);
  assert.equal(sessionStorage.getItem('_gcl_tmp'), null);
  assert.equal(localStorage.getItem(ads.CLICK_STORAGE_KEY), null);
});

test('B3: withdrawing while a sign-up is being sent removes the frame and cancels it', async () => {
  grantedPage();
  const p = ads.trackSignupConversion(42);
  assert.equal(page.frames.length, 1);
  ads.setConsent('denied');
  assert.equal(await p, 'skipped');
  assert.equal(page.frames.length, 0, 'tag removed with its frame');
  assert.deepEqual(pending(), []);
});

test('B3: withdrawal cancels pending sign-ups for good — accepting again does not send them', async () => {
  grantedPage();
  ads.trackSignupConversion(42);
  await frameSays('failed');
  ads.setConsent('denied');
  assert.deepEqual(pending(), []);
  ads.setConsent('granted');
  newPage();
  ads.initConsentMode();
  assert.equal(page.frames.length, 0);
});

test('B3: after withdrawal no further conversions are sent', async () => {
  grantedPage();
  ads.setConsent('denied');
  assert.equal(await ads.trackSignupConversion(43), 'skipped');
  assert.equal(page.frames.length, 0);
});

test('B3: a withdrawal that cannot be saved still holds for the rest of the page', async () => {
  grantedPage();
  globalThis.localStorage = {
    getItem: (k) => fakeStorage().getItem(k),
    setItem() { throw new Error('QuotaExceededError'); },
    removeItem() { throw new Error('x'); },
    key: () => null,
    get length() { return 0; },
  };
  refuseCookies();
  ads.setConsent('denied');
  assert.equal(ads.readConsent(), 'denied');
  assert.equal(await ads.trackSignupConversion(44), 'skipped');
});
