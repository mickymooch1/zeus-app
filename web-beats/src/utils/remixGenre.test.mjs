// Run: node --test src/utils/remixGenre.test.mjs
// Remix in a different genre (2026-09-24): the confirm page defaults to the
// original genre; "Remix in a different genre" offers quick-pick chips (not the
// original) and a full picker. A selection is null (= original) or { genre, genreB }.
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { quickPickGenres, remixButtonLabel, remixGenreBody, selectionTag, remixableGenres } from './remixGenre.js';

test('quick picks: the 8-genre all-ages mix, in order', () => {
  assert.deepEqual(quickPickGenres('synthfunk'), ['pop', 'rock', 'country', 'soul', 'rnb', 'ukdrill', 'edm', 'reggae']);
});

test('an excluded quick pick is replaced by Trap', () => {
  assert.deepEqual(quickPickGenres('country'), ['pop', 'rock', 'soul', 'rnb', 'ukdrill', 'edm', 'reggae', 'trap']);
});

test('two excluded (a blended original) → Trap then Dancehall', () => {
  const picks = quickPickGenres('pop__rnb');
  assert.deepEqual(picks, ['rock', 'country', 'soul', 'ukdrill', 'edm', 'reggae', 'trap', 'dancehall']);
});

test('a fallback that is itself the original is skipped too', () => {
  const picks = quickPickGenres('rock__trap');
  assert.equal(picks.length, 8);
  assert.ok(!picks.includes('rock') && !picks.includes('trap') && picks.includes('dancehall'));
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

// "More genres" hides non-vocal genres (a remix always writes lyrics) using the
// server's list (GET /api/clips/config non_vocal_genres), plus the original's.
test('remixableGenres drops non-vocal and excluded genres, keeps order', () => {
  assert.deepEqual(
    remixableGenres(['pop', 'oceanwaves', 'rock', 'pianosolo', 'trap'], ['oceanwaves', 'pianosolo'], ['trap']),
    ['pop', 'rock'],
  );
});

test('remixableGenres with no server list yet hides nothing but the excluded', () => {
  assert.deepEqual(remixableGenres(['pop', 'rock'], undefined, ['rock']), ['pop']);
});
