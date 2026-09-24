// Run: node --test src/utils/genreLabel.test.mjs
// Zeus Clips showed raw genre keys ("SOULRNB", "SYNTHFUNK__SOULRNB"). Clips now
// uses the shared gLabel — these pin the friendly/blended/fallback behaviour.
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { gLabel } from './genres.js';

test('known key → its display name', () => {
  assert.equal(gLabel('soulrnb'), 'Soul R&B');
});

test('blended key → "A × B" using display names', () => {
  assert.equal(gLabel('synthfunk__soulrnb'), 'Synth Funk × Soul R&B');
});

test('blend of three keeps every part, not just the first two', () => {
  assert.equal(gLabel('synthfunk__soulrnb__jazz'), 'Synth Funk × Soul R&B × Jazz');
});

test('unknown key falls back to a tidied, title-cased version', () => {
  assert.equal(gLabel('dark_wave-pop'), 'Dark Wave Pop');
  assert.equal(gLabel('mysterygenre'), 'Mysterygenre');
});

test('unknown part inside a blend is tidied too', () => {
  assert.equal(gLabel('soulrnb__space_rock'), 'Soul R&B × Space Rock');
});

test('empty → empty string', () => {
  assert.equal(gLabel(''), '');
  assert.equal(gLabel(null), '');
});
