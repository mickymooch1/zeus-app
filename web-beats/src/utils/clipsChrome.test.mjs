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

// ── Bottom nav (2026-09-24) ──────────────────────────────────────────────────
import { isClipsNavPath, aboveBottomChrome } from './clipsChrome.js';

test('bottom nav shows on feed, clip page, profiles and pick-a-song', () => {
  for (const p of ['/clips', '/clips/', '/clips/42', '/clips/u/nyxra', '/clips/pick']) {
    assert.equal(isClipsNavPath(p), true, p);
  }
});

test('bottom nav stays off the focused flows and non-clips pages', () => {
  for (const p of ['/clips/new', '/clips/42/remix', '/songs', '/discover', '/clipsfoo']) {
    assert.equal(isClipsNavPath(p), false, p);
  }
});

test('pinned offsets clear both the cookie banner and the bottom nav', () => {
  const v = aboveBottomChrome(96);
  assert.match(v, /^calc\(96px \+ var\(--cookie-banner-h, 0px\) \+ var\(--clips-nav-h, 0px\)\)$/);
});

// Logged-out Create / My Clips → login (or register) → back to where they were.
// Register only honours /clips destinations; every other signup still lands on /songs.
import { clipsReturnPath } from './clipsChrome.js';

test('clipsReturnPath keeps clips destinations', () => {
  assert.equal(clipsReturnPath('/clips/pick'), '/clips/pick');
  assert.equal(clipsReturnPath('/clips/me'), '/clips/me');
});

test('clipsReturnPath ignores everything else', () => {
  assert.equal(clipsReturnPath('/billing'), null);
  assert.equal(clipsReturnPath('/clipsfoo'), null);
  assert.equal(clipsReturnPath(undefined), null);
  assert.equal(clipsReturnPath('https://evil.example/clips/pick'), null);
});
