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

test('adult picker is in Advanced, in its original slot: Vocal gender → accent → Model', () => {
  const adv = SONGS_PAGE.indexOf('{showAdvanced && (');
  const gender = SONGS_PAGE.indexOf("t('songs.vocalGenderLabel')");
  const picker = SONGS_PAGE.indexOf("t('songs.accentLabel')");
  const model = SONGS_PAGE.indexOf("t('songs.modelLabel')");
  assert.ok(adv > 0 && gender > adv && picker > gender && model > picker, 'order: Advanced → Vocal gender → accent → Model');
  assert.equal(SONGS_PAGE.split("t('songs.accentLabel')").length - 1, 1, 'exactly one adult picker');
});

test('adult picker is the original dropdown: Auto first, then British at the top of the list', () => {
  const at = SONGS_PAGE.indexOf("t('songs.accentLabel')");
  const block = SONGS_PAGE.slice(at, SONGS_PAGE.indexOf('</select>', at));
  const options = [...block.matchAll(/<option[^>]*>([^<]+)<\/option>/g)].map(m => m[1]);
  assert.equal(options[0], '🎤 Auto (matches your genre)');
  assert.match(block, /\{\['British','American \(Southern\)','Irish','Scottish','Australian',/);
  for (const kept of ['Rapid Fire Rap', 'Deep Bass Voice', 'Classic Rock', 'Vocoder / Talk Box',
                      'Cockney Grime', 'UK Jungle MC', 'British MC Grime',
                      'American Soul', 'Caribbean', 'Punjabi'])
    assert.ok(block.includes(kept), `lost option: ${kept}`);
  assert.ok(!block.includes('ACCENT_GROUP_LABELS'), 'grouped catalog picker should be gone');
  assert.match(SONGS_PAGE, /Leave on Auto to let Zeus match the accent to your genre/);
});

test('standard and roast requests send the picker on the original accent field', () => {
  assert.equal(SONGS_PAGE.split(/\n\s*accent: accent \|\| undefined,/).length - 1, 2);
  assert.ok(!SONGS_PAGE.includes('accentPayload(accent)'));
});

const readOrEmpty = (rel) => { try { return readFileSync(new URL(rel, import.meta.url), 'utf8'); } catch { return ''; } };
const KIDS_PICKER = readOrEmpty('../components/KidsVoicePicker.jsx');
const KIDS_SONG_MODE = readFileSync(new URL('../pages/kids/KidsSongMode.jsx', import.meta.url), 'utf8');

test('kids picker label and flag-first options', () => {
  assert.ok(KIDS_PICKER.includes("🎤 Singer's Voice"));
  assert.ok(KIDS_PICKER.includes('🌟 Default'));
  assert.match(KIDS_PICKER, /ACCENT_OPTIONS\.map/);
  assert.match(KIDS_PICKER, /accentOptionLabel\(/);
});

test('both kids song pickers use the shared component and send vocal_accent', () => {
  for (const [name, src] of [['SongsPage', SONGS_PAGE], ['KidsSongMode', KIDS_SONG_MODE]]) {
    assert.match(src, /<KidsVoicePicker/, `${name} must render KidsVoicePicker`);
    assert.ok(!src.includes('🎤 Singing Accent'), `${name} still has the old kids label`);
  }
  assert.match(KIDS_SONG_MODE, /vocal_accent: accent \|\| undefined/);
  assert.match(SONGS_PAGE, /vocal_accent: kidsSubMode === 'song' \? \(kidsAccent \|\| undefined\) : undefined/);
  // Story narrator still rides on `accent`.
  assert.match(SONGS_PAGE, /accent: kidsSubMode === 'story' \? \(kidsNarratorVoice \|\| undefined\) : undefined/);
});

test('adult accent picker is hidden in Kids mode (kids has its own Singer\'s Voice picker)', () => {
  const src = readFileSync(new URL('../pages/SongsPage.jsx', import.meta.url), 'utf8');
  const at = src.indexOf("t('songs.accentLabel')");
  const cond = src.slice(src.lastIndexOf('{!', at), at);
  assert.match(cond, /^\{!isKidsMode && /, `adult picker condition is: ${cond}`);
});
