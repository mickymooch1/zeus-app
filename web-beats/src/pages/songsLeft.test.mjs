import { test } from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import i18next from 'i18next';

// The /songs credit counter reads "4 songs left", not "4 / 3 songs": the old
// "balance / plan allowance" looked wrong whenever a refund, top-up, referral or
// admin grant took the balance above the plan's number. Run real i18next over
// every locale so each plural form the language needs actually resolves.
const here = path.dirname(fileURLToPath(import.meta.url));
const dir = path.join(here, '..', 'locales');
const locales = fs.readdirSync(dir).filter((n) => n.endsWith('.json')).map((n) => n.slice(0, -5));
// Covers zero/one/two/few/many/other across en, ru (1/2-4/5+/21) and ar (0/1/2/3-10/11-99/100+).
const COUNTS = [0, 1, 2, 4, 5, 11, 21, 101];

test('songs.songsLeft resolves for every count in every locale', async () => {
  assert.equal(locales.length, 13);
  const resources = Object.fromEntries(locales.map((l) => [
    l, { translation: JSON.parse(fs.readFileSync(path.join(dir, `${l}.json`), 'utf8')) },
  ]));
  const i18n = i18next.createInstance();
  await i18n.init({ resources, lng: 'en', fallbackLng: false, interpolation: { escapeValue: false } });
  for (const l of locales) {
    const t = i18n.getFixedT(l);
    for (const count of COUNTS) {
      assert.ok(i18n.exists('songs.songsLeft', { lng: l, count }), `${l} count=${count}: no plural form`);
      const s = t('songs.songsLeft', { count });
      assert.ok(!s.includes('songsLeft') && !s.includes('{{'), `${l} count=${count}: ${s}`);
      // Arabic spells out 0/1/2 ("no song", "one song", "two songs"); every other form shows the number.
      if (!(l === 'ar' && count <= 2)) assert.ok(s.includes(String(count)), `${l} count=${count}: ${s}`);
    }
  }
  const en = i18n.getFixedT('en');
  assert.equal(en('songs.songsLeft', { count: 1 }), '1 song left');
  assert.equal(en('songs.songsLeft', { count: 4 }), '4 songs left');
});

test('the /songs counter uses songsLeft, not the old balance / allowance', () => {
  const src = fs.readFileSync(path.join(here, 'SongsPage.jsx'), 'utf8');
  assert.ok(src.includes("t('songs.songsLeft', { count: balance })"));
  assert.ok(!src.includes('songsBalance'));
});
