import { test } from 'node:test';
import assert from 'node:assert/strict';
import { plainLabel, initialCategory } from './genreTiles.js';
import { GENRE_CATEGORIES } from './genres.js';

test('plainLabel strips the leading emoji from category labels', () => {
  assert.equal(plainLabel('🎤 UK Street & Hip Hop'), 'UK Street & Hip Hop');
  assert.equal(plainLabel('🌍 World & Urban'), 'World & Urban');
  assert.equal(plainLabel('Jazz'), 'Jazz');
  for (const c of GENRE_CATEGORIES) assert.match(plainLabel(c.label), /^[\p{L}\p{N}]/u, c.label);
});

test('initialCategory opens on the category holding a selected genre', () => {
  assert.equal(initialCategory(new Set()), GENRE_CATEGORIES[0].id);
  const country = GENRE_CATEGORIES.find((c) => c.genres.includes('countrypop'));
  assert.equal(initialCategory(new Set(['countrypop'])), country.id);
});
