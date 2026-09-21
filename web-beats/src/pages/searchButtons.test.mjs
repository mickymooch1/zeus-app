// Run: node --test src/pages/searchButtons.test.mjs
//
// The three Search-page result buttons must read the same. They had drifted into
// three different labels for the same action (navigate to Create with the reference
// pre-filled): "Generate a song like this →" (Style), "Use as inspiration →" (YouTube)
// and "Write me something similar →" (Lyrics). Text-scans SearchPage.jsx, like
// genres.test.mjs, because the page cannot be imported outside a bundler.

import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { describe, it } from 'node:test';

const SRC = readFileSync(new URL('./SearchPage.jsx', import.meta.url), 'utf8');

describe('Search page result buttons', () => {
  it('reads the source (guards against an empty scan)', () => {
    assert.ok(SRC.includes('export default function SearchPage'));
  });

  it('every tab uses "Use as inspiration →" (Style, YouTube and Lyrics)', () => {
    const count = [...SRC.matchAll(/Use as inspiration →/g)].length;
    assert.equal(count, 3, `expected 3 buttons labelled "Use as inspiration →", found ${count}`);
  });

  it('no leftover divergent labels', () => {
    for (const old of ['Generate a song like this', 'Write me something similar']) {
      assert.ok(!SRC.includes(old), `stale label still present: ${old}`);
    }
  });

  it('the YouTube button keeps its loading state', () => {
    assert.ok(SRC.includes("'Reading the style…'"));
  });
});
