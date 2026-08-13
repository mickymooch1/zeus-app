// Run: node --test src/pages/genres.test.mjs
//
// The requirement under test, in the user's words:
//   "Two lists that must agree, don't — that's exactly how this drifted."
//
// Two separate drifts have already happened here:
//
//   1. SongsPage kept a hand-written GENRES array alongside GENRE_CATEGORIES.
//      It fell to 71 of the 107 pickable genres, which silently cut 36 of them
//      (trance, folk, salsa, ambient, bluegrass, every instrumental-solo entry)
//      out of the Genre B blend dropdown. GENRES is now derived from the grid,
//      so that particular pair cannot disagree again.
//
//   2. The pair this file guards: the genres the UI can select vs the genres
//      the backend has a style preset for. Those live in different languages in
//      different directories and nothing links them. generate_multiple_variants
//      does `valid_genres = [g for g in genres if g in GENRE_PRESETS]` — a
//      SILENT filter with no fallback. A genre added to the grid without a
//      matching preset would therefore vanish at generation time while the UI
//      still charged for it (cost = selGenres.size), producing fewer variants
//      than the user paid for, with no error anywhere.
//
// Parsing the sources as text is deliberate: SongsPage.jsx is a React module
// that cannot be imported outside a bundler, and song_genres.py is Python. The
// counts are asserted non-zero first so a parser that silently matches nothing
// fails loudly instead of comparing two empty sets and passing.

import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { describe, it } from 'node:test';

const SONGS_PAGE = new URL('./SongsPage.jsx', import.meta.url);
const SONG_GENRES_PY = new URL('../../../backend/song_genres.py', import.meta.url);

function read(url, label) {
  try {
    return readFileSync(url, 'utf8');
  } catch (err) {
    assert.fail(`could not read ${label} at ${url.pathname}: ${err.message}`);
  }
}

/** Every genre slug selectable from the category grid, in grid order. */
function pickableGenres() {
  const src = read(SONGS_PAGE, 'SongsPage.jsx');
  const block = src.match(/const GENRE_CATEGORIES = \[([\s\S]*?)\n\];/);
  assert.ok(block, 'could not locate GENRE_CATEGORIES in SongsPage.jsx');
  return [...block[1].matchAll(/genres:\s*\[([^\]]*)\]/g)]
    .flatMap(m => [...m[1].matchAll(/'([^']+)'/g)].map(x => x[1]));
}

/** Every genre slug the backend has a style preset for. */
function presetGenres() {
  const src = read(SONG_GENRES_PY, 'backend/song_genres.py');
  const block = src.match(/^GENRE_PRESETS = \{([\s\S]*?)^\}/m);
  assert.ok(block, 'could not locate GENRE_PRESETS in backend/song_genres.py');
  // Case-insensitive on purpose: a preset keyed with a stray capital is a typo
  // that must still be reported, not quietly skipped by the parser.
  return [...block[1].matchAll(/^\s*"([A-Za-z0-9_]+)"\s*:/gm)].map(m => m[1]);
}

describe('genre catalog', () => {
  it('parses both sources (guards against a silently-empty comparison)', () => {
    assert.ok(pickableGenres().length > 50, 'suspiciously few genres parsed from the grid');
    assert.ok(presetGenres().length > 50, 'suspiciously few presets parsed from the backend');
  });

  it('lists no genre twice across categories', () => {
    const flat = pickableGenres();
    const dupes = flat.filter((g, i) => flat.indexOf(g) !== i);
    assert.deepEqual(dupes, [], `genre(s) appear in more than one category: ${dupes.join(', ')}`);
  });

  it('every pickable genre has a backend style preset', () => {
    const presets = new Set(presetGenres());
    const orphans = [...new Set(pickableGenres())].filter(g => !presets.has(g));
    assert.deepEqual(
      orphans, [],
      `pickable in the UI but no GENRE_PRESETS entry — these would be silently ` +
      `dropped by generate_multiple_variants while still being charged for: ${orphans.join(', ')}`,
    );
  });

  it('every backend style preset is reachable from the grid', () => {
    const pickable = new Set(pickableGenres());
    const unreachable = presetGenres().filter(g => !pickable.has(g));
    assert.deepEqual(
      unreachable, [],
      `has a GENRE_PRESETS entry but cannot be selected anywhere in the UI: ${unreachable.join(', ')}`,
    );
  });

  it('the two catalogs match exactly', () => {
    const a = [...new Set(pickableGenres())].sort();
    const b = [...new Set(presetGenres())].sort();
    assert.deepEqual(a, b);
  });
});
