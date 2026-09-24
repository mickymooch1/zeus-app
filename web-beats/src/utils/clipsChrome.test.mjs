// Run: node --test src/utils/clipsChrome.test.mjs
// The full-screen clip viewers (/clips feed and /clips/:id) get a compact
// cookie banner that never covers the Remix button. Other Clips routes
// (creator, remix confirm, profile) are normal scrolling pages.
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { isClipViewerPath } from './clipsChrome.js';

test('feed and single-clip pages are viewer paths', () => {
  assert.equal(isClipViewerPath('/clips'), true);
  assert.equal(isClipViewerPath('/clips/'), true);
  assert.equal(isClipViewerPath('/clips/42'), true);
});

test('creator, remix, profile and unrelated pages are not', () => {
  assert.equal(isClipViewerPath('/clips/new'), false);
  assert.equal(isClipViewerPath('/clips/42/remix'), false);
  assert.equal(isClipViewerPath('/clips/u/nyxra'), false);
  assert.equal(isClipViewerPath('/songs'), false);
  assert.equal(isClipViewerPath('/clipsfoo'), false);
});
