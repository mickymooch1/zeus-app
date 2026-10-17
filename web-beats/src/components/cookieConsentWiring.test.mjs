// Wiring for Google Ads consent (see utils/adsConsent.js for the behaviour
// itself): where the module is called from, the banner's two equal choices,
// a way back to the choice later, and copy that matches what the site does.
import { test } from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const src = path.join(path.dirname(fileURLToPath(import.meta.url)), '..');
const read = (p) => fs.readFileSync(path.join(src, p), 'utf8');

test('main.jsx sets the Consent Mode defaults before the app renders, blocked in the iOS app', () => {
  const main = read('main.jsx');
  const init = main.indexOf('initConsentMode({ blocked: isIOSWebView })');
  assert.ok(init > -1, 'initConsentMode({ blocked: isIOSWebView }) missing');
  assert.ok(init < main.indexOf('createRoot('), 'must run before createRoot');
});

test('RegisterPage fires the conversion only after register() succeeds, with the new user id', () => {
  const page = read('pages/RegisterPage.jsx');
  const reg = page.indexOf('const data = await register(');
  const conv = page.indexOf('trackSignupConversion(data?.user?.id)');
  assert.ok(reg > -1 && conv > reg, 'conversion must follow the awaited register()');
  assert.ok(conv < page.indexOf('} catch (err)', reg), 'conversion must be inside the success path');
  assert.equal(page.match(/trackSignupConversion\(/g).length, 1);
});

test('the conversion is not fired from login, verification or anywhere else', () => {
  const hits = [];
  const walk = (dir) => {
    for (const e of fs.readdirSync(dir, { withFileTypes: true })) {
      const p = path.join(dir, e.name);
      if (e.isDirectory()) walk(p);
      else if (/\.jsx?$/.test(e.name) && fs.readFileSync(p, 'utf8').includes('trackSignupConversion(')) {
        hits.push(path.relative(src, p).replace(/\\/g, '/'));
      }
    }
  };
  walk(src);
  assert.deepEqual(hits.sort(), ['pages/RegisterPage.jsx', 'utils/adsConsent.js']);
});

test('banner: Accept and Reject are both buttons with the same style, and the old implied-consent flag is gone', () => {
  const banner = read('components/CookieBanner.jsx');
  assert.match(banner, /onClick=\{\(\) => choose\('granted'\)\}/);
  assert.match(banner, /onClick=\{\(\) => choose\('denied'\)\}/);
  const styles = [...banner.matchAll(/<button type="button" onClick=\{\(\) => choose\('\w+'\)\} style=\{(\w+)\}>/g)]
    .map((m) => m[1]);
  assert.equal(styles.length, 2);
  assert.equal(styles[0], styles[1], 'Accept and Reject must look the same');
  assert.doesNotMatch(banner, /zeus_cookie_accepted/);
  assert.match(banner, /COOKIE_SETTINGS_EVENT/, 'banner must reopen from Cookie settings');
});

test('there is a Cookie settings control in the footer, the sidebar and the privacy policy', () => {
  for (const p of ['pages/LandingPage.jsx', 'components/NeonSidebar.jsx', 'pages/PrivacyPage.jsx']) {
    assert.match(read(p), /onClick=\{openCookieSettings\}/, p);
  }
});

test('every locale has the new banner copy — no more "by using … you agree"', () => {
  const dir = path.join(src, 'locales');
  for (const f of fs.readdirSync(dir).filter((n) => n.endsWith('.json'))) {
    const c = JSON.parse(fs.readFileSync(path.join(dir, f), 'utf8')).cookies;
    for (const k of ['message', 'accept', 'reject', 'settings', 'learnMore']) assert.ok(c?.[k], `${f}: cookies.${k}`);
    assert.match(c.message, /<privacy>.+<\/privacy>/, `${f}: privacy link`);
    assert.match(c.message, /Google/, `${f}: names Google`);
  }
  assert.doesNotMatch(JSON.parse(read('locales/en.json')).cookies.message, /By using/);
});

test('privacy policy describes Google Ads honestly', () => {
  const privacy = read('pages/PrivacyPage.jsx');
  assert.doesNotMatch(privacy, /We do not use tracking cookies, advertising cookies/);
  for (const s of ['Google Ads', '_gcl_', 'Reject', 'Cookie settings']) assert.ok(privacy.includes(s), s);
});
