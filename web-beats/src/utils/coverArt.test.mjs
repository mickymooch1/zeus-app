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
