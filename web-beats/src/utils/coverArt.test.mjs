// Run: node --test src/utils/coverArt.test.mjs
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { COVER_ART_STYLE_OPTIONS, coverArtPayload } from './genres.js';

test('8 cover styles with spec emoji + labels, in order', () => {
  assert.deepEqual(COVER_ART_STYLE_OPTIONS.map(o => `${o.emoji} ${o.label}`), [
    '🎬 Cinematic', '🖼️ Painterly', '🌈 Vibrant', '🖤 Dark & Moody',
    '✨ Dreamy', '🎭 Vintage / Retro', '📸 Photorealistic', '🎨 Illustrated / Cartoon',
  ]);
  assert.deepEqual(COVER_ART_STYLE_OPTIONS.map(o => o.key), [
    'cinematic', 'painterly', 'vibrant', 'dark_moody', 'dreamy', 'vintage', 'photorealistic', 'illustrated',
  ]);
});

test('coverArtPayload drops empty values and trims the description', () => {
  assert.deepEqual(coverArtPayload('', ''), {});
  assert.deepEqual(coverArtPayload('', '   '), {});
  assert.deepEqual(coverArtPayload('dreamy', ''), { cover_art_style: 'dreamy' });
  assert.deepEqual(coverArtPayload('', '  a fox  '), { cover_art_description: 'a fox' });
  assert.deepEqual(coverArtPayload('vintage', 'a jukebox'),
    { cover_art_style: 'vintage', cover_art_description: 'a jukebox' });
});

import { readFileSync } from 'node:fs';
const SONGS_PAGE = readFileSync(new URL('../pages/SongsPage.jsx', import.meta.url), 'utf8');

test('Create page shows both cover fields after Singer\'s Accent, hidden in Kids', () => {
  const accent = SONGS_PAGE.indexOf("t('songs.accentLabel')");
  const style = SONGS_PAGE.indexOf('🎨 Cover Art Style (optional)');
  const desc = SONGS_PAGE.indexOf('✏️ Describe your cover art (optional)');
  assert.ok(accent > 0 && style > accent && desc > style, 'order: accent → style → description');
  assert.ok(SONGS_PAGE.includes('placeholder="e.g. Manchester skyline at night, a dog at a piano, stormy ocean..."'));
  assert.match(SONGS_PAGE, /maxLength=\{150\}[\s\S]{0,400}value=\{coverDesc\}|value=\{coverDesc\}[\s\S]{0,400}maxLength=\{150\}/);
  const block = SONGS_PAGE.slice(SONGS_PAGE.lastIndexOf('{!isKidsMode && (', style), style);
  assert.ok(block.length > 0 && block.length < 400, 'cover block must be wrapped in !isKidsMode');
});

test('style chips are single-select and deselectable', () => {
  assert.match(SONGS_PAGE, /COVER_ART_STYLE_OPTIONS\.map/);
  assert.match(SONGS_PAGE, /setCoverStyle\(coverStyle === o\.key \? '' : o\.key\)/);
});

test('standard and roast requests send the cover fields; Kids request does not', () => {
  assert.equal((SONGS_PAGE.match(/\.\.\.coverArtPayload\(coverStyle, coverDesc\)/g) || []).length, 2);
  const kids = SONGS_PAGE.slice(SONGS_PAGE.indexOf('if (isKidsMode) {'), SONGS_PAGE.indexOf('} else if (isRoastMode) {'));
  assert.ok(kids.length > 0 && !/cover_?[aA]rt|coverArtPayload/.test(kids));
});
