/**
 * Google Ads + Consent Mode v2 (UK PECR: advertising cookies need opt-in).
 *
 * The rules these tests pin down:
 *   - Consent Mode defaults are pushed FIRST, all four signals 'denied'.
 *   - gtag.js is not even requested until the visitor clicks Accept
 *     (basic Consent Mode — no cookieless pings before consent).
 *   - The old "By using Zeus Beats you agree" banner flag is NOT consent.
 *   - Reject / withdrawing consent pushes 'denied' and clears _gcl cookies.
 *   - The sign-up conversion fires once per new user id, only with consent.
 */
import { test, beforeEach } from 'node:test';
import assert from 'node:assert/strict';

function installFakeBrowser({ cookies = {} } = {}) {
  const store = new Map();
  globalThis.localStorage = {
    getItem: (k) => (store.has(k) ? store.get(k) : null),
    setItem: (k, v) => store.set(k, String(v)),
    removeItem: (k) => store.delete(k),
  };
  const jar = new Map(Object.entries(cookies));
  const scripts = [];
  const events = [];
  globalThis.window = {
    location: { hostname: 'zeusbeats.com' },
    dispatchEvent: (e) => { events.push(e.type); return true; },
  };
  globalThis.document = {
    createElement: (tag) => ({ tagName: tag.toUpperCase() }),
    getElementById: (id) => scripts.find((s) => s.id === id) || null,
    head: { appendChild: (el) => { scripts.push(el); return el; } },
    get cookie() { return [...jar].map(([k, v]) => `${k}=${v}`).join('; '); },
    set cookie(str) {
      const [pair, ...attrs] = str.split(';').map((s) => s.trim());
      const [name, value] = pair.split('=');
      const expired = attrs.some((a) => /^max-age=0$/i.test(a) || /^expires=Thu, 01 Jan 1970/i.test(a));
      if (expired) jar.delete(name); else jar.set(name, value);
    },
  };
  return { store, jar, scripts, events };
}

let env;
beforeEach(() => { env = installFakeBrowser({ cookies: { _gcl_aw: 'GCL.1.abc', _gcl_au: '1.1.2', zeus_x: 'keep' } }); });

const ads = await import('./adsConsent.js');

const calls = () => window.dataLayer.map((args) => Array.from(args));
const isArgumentsObject = (x) => Object.prototype.toString.call(x) === '[object Arguments]';

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
  ads.initConsentMode();
  assert.ok(window.dataLayer.length > 0);
  assert.ok(window.dataLayer.every(isArgumentsObject));
});

test('no choice yet: gtag.js is not loaded and nothing is granted', () => {
  ads.initConsentMode();
  assert.equal(ads.readConsent(), null);
  assert.equal(env.scripts.length, 0);
  assert.ok(!calls().some((c) => c[0] === 'consent' && c[1] === 'update'));
  assert.ok(!calls().some((c) => c[0] === 'config'));
});

test('the old implied-consent banner flag does not count as consent', () => {
  localStorage.setItem('zeus_cookie_accepted', '1');
  ads.initConsentMode();
  assert.equal(ads.readConsent(), null);
  assert.equal(env.scripts.length, 0);
});

test('Accept: grants ad storage + ad user data only, loads gtag.js once and configures the Ads tag', () => {
  ads.initConsentMode();
  ads.setConsent('granted');
  ads.setConsent('granted');
  assert.equal(ads.readConsent(), 'granted');
  assert.equal(env.scripts.length, 1);
  assert.equal(env.scripts[0].src, 'https://www.googletagmanager.com/gtag/js?id=AW-18517714190');
  assert.equal(env.scripts[0].async, true);
  const update = calls().find((c) => c[0] === 'consent' && c[1] === 'update');
  assert.deepEqual(update[2], {
    ad_storage: 'granted', ad_user_data: 'granted',
    ad_personalization: 'denied', // the banner asks about measuring sign-ups, not remarketing
    analytics_storage: 'denied', // no analytics product is used — nothing to consent to
  });
  assert.equal(calls().filter((c) => c[0] === 'config' && c[1] === 'AW-18517714190').length, 1);
  // consent update must come before the config that starts measurement
  const i = calls().findIndex((c) => c[0] === 'consent' && c[1] === 'update');
  const j = calls().findIndex((c) => c[0] === 'config');
  assert.ok(i < j);
});

test('a returning visitor who accepted earlier gets the tag on page load', () => {
  localStorage.setItem(ads.CONSENT_STORAGE_KEY, JSON.stringify({ ads: 'granted', v: 1, ts: 1 }));
  ads.initConsentMode();
  assert.equal(env.scripts.length, 1);
});

test('Reject: nothing loads, denied is recorded and existing Google Ads cookies are cleared', () => {
  ads.initConsentMode();
  ads.setConsent('denied');
  assert.equal(ads.readConsent(), 'denied');
  assert.equal(env.scripts.length, 0);
  assert.ok(!env.jar.has('_gcl_aw') && !env.jar.has('_gcl_au'));
  assert.equal(env.jar.get('zeus_x'), 'keep');
});

test('changing Accept → Reject later pushes denied and clears the cookies', () => {
  ads.initConsentMode();
  ads.setConsent('granted');
  env.jar.set('_gcl_au', '1.1.9');
  ads.setConsent('denied');
  const updates = calls().filter((c) => c[0] === 'consent' && c[1] === 'update');
  assert.equal(updates.at(-1)[2].ad_storage, 'denied');
  assert.equal(updates.at(-1)[2].ad_user_data, 'denied');
  assert.equal(updates.at(-1)[2].ad_personalization, 'denied');
  assert.ok(!env.jar.has('_gcl_au'));
});

test('garbage in storage is treated as no choice', () => {
  localStorage.setItem(ads.CONSENT_STORAGE_KEY, '{nope');
  assert.equal(ads.readConsent(), null);
  localStorage.setItem(ads.CONSENT_STORAGE_KEY, JSON.stringify({ ads: 'maybe' }));
  assert.equal(ads.readConsent(), null);
});

test('inside the iOS app the tag never loads, even with consent', () => {
  localStorage.setItem(ads.CONSENT_STORAGE_KEY, JSON.stringify({ ads: 'granted', v: 1, ts: 1 }));
  ads.initConsentMode({ blocked: true });
  ads.setConsent('granted');
  assert.equal(env.scripts.length, 0);
  assert.equal(ads.trackSignupConversion(42), false);
});

// ── sign-up conversion ──────────────────────────────────────────────────────

const conversions = () => calls().filter((c) => c[0] === 'event' && c[1] === 'conversion');

test('without consent no conversion is sent', () => {
  ads.initConsentMode();
  assert.equal(ads.trackSignupConversion(42), false);
  ads.setConsent('denied');
  assert.equal(ads.trackSignupConversion(42), false);
  assert.equal(conversions().length, 0);
});

test('with consent: one conversion, labelled, with the user id as transaction_id', () => {
  ads.initConsentMode();
  ads.setConsent('granted');
  assert.equal(ads.trackSignupConversion(42), true);
  assert.deepEqual(conversions(), [['event', 'conversion', {
    send_to: 'AW-18517714190/o7SdCLShsZ8dEI7K9_1E', transaction_id: '42',
  }]]);
});

test('the same user id never converts twice (refresh, back button, double submit)', () => {
  ads.initConsentMode();
  ads.setConsent('granted');
  ads.trackSignupConversion(42);
  assert.equal(ads.trackSignupConversion(42), false);
  assert.equal(ads.trackSignupConversion('42'), false);
  assert.equal(conversions().length, 1);
  assert.equal(ads.trackSignupConversion(43), true);
  assert.equal(conversions().length, 2);
});

test('a missing user id sends nothing', () => {
  ads.initConsentMode();
  ads.setConsent('granted');
  for (const id of [undefined, null, '']) assert.equal(ads.trackSignupConversion(id), false);
  assert.equal(conversions().length, 0);
});

test('never throws, even with storage unavailable', () => {
  ads.initConsentMode();
  globalThis.localStorage = { getItem() { throw new Error('blocked'); }, setItem() { throw new Error('blocked'); } };
  assert.doesNotThrow(() => ads.setConsent('granted'));
  assert.doesNotThrow(() => ads.trackSignupConversion(7));
  assert.equal(ads.readConsent(), null);
});

test('openCookieSettings asks the banner to reappear', () => {
  ads.openCookieSettings();
  assert.deepEqual(env.events, [ads.COOKIE_SETTINGS_EVENT]);
});
