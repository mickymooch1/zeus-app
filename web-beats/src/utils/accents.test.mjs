// Run: node --test src/utils/accents.test.mjs
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { ACCENT_OPTIONS, ACCENT_GROUP_LABELS, accentOptionLabel, accentPayload } from './genres.js';

test('29 accents, unique keys, every group known', () => {
  assert.equal(ACCENT_OPTIONS.length, 29);
  assert.equal(new Set(ACCENT_OPTIONS.map(o => o.key)).size, 29);
  const groups = ACCENT_GROUP_LABELS.map(([id]) => id);
  assert.deepEqual(groups, ['british_isles', 'americas', 'africa', 'europe', 'asia', 'pacific']);
  for (const o of ACCENT_OPTIONS) assert.ok(groups.includes(o.group), o.key);
});

test('option label is flag-first', () => {
  const jam = ACCENT_OPTIONS.find(o => o.key === 'jamaican');
  assert.equal(accentOptionLabel(jam), '🇯🇲 Jamaican');
});

test('accentPayload routes accent keys, legacy values and blank', () => {
  assert.deepEqual(accentPayload('jamaican'), { vocal_accent: 'jamaican' });
  assert.deepEqual(accentPayload('German'), { accent: 'German' });
  const rapid = 'extremely fast rapid-fire rap delivery, machine gun flow';
  assert.deepEqual(accentPayload(rapid), { accent: rapid });
  assert.deepEqual(accentPayload(''), {});
  assert.deepEqual(accentPayload(undefined), {});
});

import { readFileSync } from 'node:fs';
const SONGS_PAGE = readFileSync(new URL('../pages/SongsPage.jsx', import.meta.url), 'utf8');
const EN = JSON.parse(readFileSync(new URL('../locales/en.json', import.meta.url), 'utf8'));

test('adult label text', () => {
  assert.equal(EN.songs.accentLabel, "🎤 Singer's Accent (optional)");
});

test('adult picker sits right after the genre grid, outside Advanced', () => {
  const grid = SONGS_PAGE.indexOf('<GenreTileGrid');
  const picker = SONGS_PAGE.indexOf("t('songs.accentLabel')");
  const adv = SONGS_PAGE.indexOf('{showAdvanced && (');
  assert.ok(grid > 0 && picker > grid && picker < adv, 'picker must be between grid and Advanced');
  assert.equal(SONGS_PAGE.split("t('songs.accentLabel')").length - 1, 1, 'exactly one adult picker');
});

test('three groups: accents, languages, vocal styles — nothing lost', () => {
  assert.match(SONGS_PAGE, /🌐 Sing in another language/);
  assert.match(SONGS_PAGE, /🎙 Vocal Style/);
  for (const kept of ['Rapid Fire Rap', 'Deep Bass Voice', 'Classic Rock', 'Vocoder / Talk Box',
                      'Cockney Grime', 'Bashment MC', 'UK Jungle MC', 'British MC Grime',
                      'American Soul', 'Caribbean', 'Punjabi', 'Brazilian Portuguese', 'Yoruba'])
    assert.ok(SONGS_PAGE.includes(kept), `lost option: ${kept}`);
  assert.ok(!SONGS_PAGE.includes('Auto (matches your genre)'));
});

test('standard and roast requests route the picker via accentPayload', () => {
  assert.equal(SONGS_PAGE.split('...accentPayload(accent)').length - 1, 2);
  assert.ok(!/\n\s*accent: accent \|\| undefined,/.test(SONGS_PAGE), 'raw accent send left behind');
});
