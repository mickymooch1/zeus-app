// Run: node --test src/utils/freeSongs.test.mjs
// The /songs welcome card used to hard-code "You have 3 free songs" — wrong for
// anyone who had already spent one (e.g. on a Zeus Clips remix). It now reads
// the real balance.
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { freeSongsLine } from './freeSongs.js';

test('uses the real balance', () => {
  assert.equal(freeSongsLine(2), 'You have 2 free songs to get started.');
  assert.equal(freeSongsLine(3), 'You have 3 free songs to get started.');
});

test('singular for one', () => {
  assert.equal(freeSongsLine(1), 'You have 1 free song to get started.');
});

test('nothing to say at zero or unknown', () => {
  assert.equal(freeSongsLine(0), null);
  assert.equal(freeSongsLine(undefined), null);
});
