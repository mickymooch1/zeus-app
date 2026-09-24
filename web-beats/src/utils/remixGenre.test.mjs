// Run: node --test src/utils/remixGenre.test.mjs
// Remix in a different genre (2026-09-24): the confirm page defaults to the
// original genre; "Remix in a different genre" offers quick-pick chips (not the
// original) and a full picker. A selection is null (= original) or { genre, genreB }.
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { quickPickGenres, remixButtonLabel, remixGenreBody, selectionTag } from './remixGenre.js';

test('quick picks: 7 popular genres, never the original', () => {
  const picks = quickPickGenres('trap');
  assert.equal(picks.length, 7);
  assert.ok(!picks.includes('trap'));
});

test('quick picks exclude both halves of a blended original', () => {
  const picks = quickPickGenres('ukdrill__rnb');
  assert.ok(!picks.includes('ukdrill') && !picks.includes('rnb'));
  assert.equal(picks.length, 7);
});

test('selectionTag: null for the original, "a" or "a__b" otherwise', () => {
  assert.equal(selectionTag(null), null);
  assert.equal(selectionTag({ genre: 'trap' }), 'trap');
  assert.equal(selectionTag({ genre: 'trap', genreB: 'rnb' }), 'trap__rnb');
});

test('button: default label for the original, "⚡ Remix as <friendly name>" otherwise', () => {
  assert.equal(remixButtonLabel(null), undefined);
  assert.equal(remixButtonLabel({ genre: 'ukdrill' }), '⚡ Remix as UK Drill');
  assert.equal(remixButtonLabel({ genre: 'trap', genreB: 'rnb' }), '⚡ Remix as Trap × R&B');
});

test('request body: nothing for the original (or re-picking it), genre fields otherwise', () => {
  assert.deepEqual(remixGenreBody(null, 'pop'), {});
  assert.deepEqual(remixGenreBody({ genre: 'pop' }, 'pop'), {});
  assert.deepEqual(remixGenreBody({ genre: 'trap' }, 'pop'), { genre: 'trap' });
  assert.deepEqual(remixGenreBody({ genre: 'trap', genreB: 'rnb' }, 'pop'), { genre: 'trap', genre_b: 'rnb' });
});
