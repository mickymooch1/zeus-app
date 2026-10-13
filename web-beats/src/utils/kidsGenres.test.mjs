// Run: node --test src/utils/kidsGenres.test.mjs
// Genre picking in the Kids section of the main Create page (SongsPage.jsx).
// The standalone /kids app does not use any of this.
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { GENRES, GENRE_CATEGORIES, KIDS_HIDDEN_GENRES, KIDS_GENRE_CATEGORIES, kidsRequestGenres } from './genres.js';

const SONGS_PAGE = readFileSync(new URL('../pages/SongsPage.jsx', import.meta.url), 'utf8');
const GRID = readFileSync(new URL('../components/GenreTileGrid.jsx', import.meta.url), 'utf8');

test('the genres named as adult are hidden in Kids mode, and every hidden key is a real genre', () => {
  for (const g of ['ukdrill', 'darkcinematic', 'witchhouse', 'gothicrock']) {
    assert.ok(KIDS_HIDDEN_GENRES.has(g), `${g} should be hidden in Kids mode`);
  }
  // Kept on request (2026-10-13): grime, ragga and jungle stay available to Kids.
  for (const g of ['grime', 'ragga', 'jungle']) {
    assert.ok(!KIDS_HIDDEN_GENRES.has(g), `${g} should be shown in Kids mode`);
  }
  for (const g of KIDS_HIDDEN_GENRES) assert.ok(GENRES.includes(g), `${g} is not a genre key`);
});

test('Kids categories drop exactly the hidden genres, keep order, and drop empty categories', () => {
  const shown = KIDS_GENRE_CATEGORIES.flatMap(c => c.genres);
  assert.ok(shown.every(g => !KIDS_HIDDEN_GENRES.has(g)));
  assert.deepEqual(shown, GENRES.filter(g => !KIDS_HIDDEN_GENRES.has(g)));
  assert.ok(KIDS_GENRE_CATEGORIES.every(c => c.genres.length > 0));
  assert.ok(shown.includes('pop') && shown.includes('reggae') && shown.includes('spookypop'));
  // The adult grid itself is unchanged.
  assert.ok(GENRE_CATEGORIES.flatMap(c => c.genres).includes('grime'));
});

test('Kids request genre: a picked tile beats the Music Style, which beats pop', () => {
  assert.deepEqual(kidsRequestGenres(new Set(['afrobeats']), ['acoustic']), ['afrobeats']);
  assert.deepEqual(kidsRequestGenres(new Set(), ['acoustic']), ['acoustic']);
  assert.deepEqual(kidsRequestGenres(new Set(), undefined), ['pop']);
});

test('Kids request sends exactly one genre (1 credit) and never a hidden one', () => {
  // Several adult picks left over from adult mode → only the first allowed one.
  assert.deepEqual(kidsRequestGenres(new Set(['ukdrill', 'rock', 'afrobeats']), undefined), ['rock']);
  assert.deepEqual(kidsRequestGenres(new Set(['ukdrill', 'metal']), ['classical']), ['classical']);
  assert.deepEqual(kidsRequestGenres(new Set(['ukdrill']), undefined), ['pop']);
  assert.deepEqual(kidsRequestGenres(new Set(['grime']), ['acoustic']), ['grime']);
});

test('SongsPage Kids request uses kidsRequestGenres with the Music Style genre', () => {
  assert.match(SONGS_PAGE, /genres: kidsRequestGenres\(selGenres, KIDS_MUSIC_GENRES\[kidsMusicStyle\]\),/);
  assert.ok(!SONGS_PAGE.includes("KIDS_MUSIC_GENRES[kidsMusicStyle] || ['pop']"));
});

test('genre tiles are single-select in Kids mode, multi-select otherwise', () => {
  assert.match(SONGS_PAGE, /if \(isKidsMode\) return prev\.has\(g\) \? new Set\(\) : new Set\(\[g\]\);/);
  assert.match(SONGS_PAGE, /next\.has\(g\) \? next\.delete\(g\) : next\.add\(g\);/);
});

test('Kids mode shows the filtered grid and hides the "N genres = N songs" note', () => {
  assert.match(SONGS_PAGE, /<GenreTileGrid[^>]*categories=\{isKidsMode \? KIDS_GENRE_CATEGORIES : GENRE_CATEGORIES\}/);
  assert.match(SONGS_PAGE, /\{!isKidsMode && selGenres\.size > 1 && \(/);
  assert.match(GRID, /export default function GenreTileGrid\(\{[^}]*categories = GENRE_CATEGORIES/);
  assert.ok(!/GENRE_CATEGORIES\.(find|map)\(/.test(GRID), 'grid must render the categories prop');
});
