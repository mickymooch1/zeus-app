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

test('clipsReturnPath keeps the query string (Discover Create Clip → /clips/new?song=)', () => {
  assert.equal(clipsReturnPath('/clips/new?song=7'), '/clips/new?song=7');
});

// ── Way back to Zeus Beats (2026-09-24) ──────────────────────────────────────
import { beatsHomePath, mediaUploadAllowed } from './clipsChrome.js';

test('"← Zeus Beats" / logo: song library when signed in, home page when not', () => {
  assert.equal(beatsHomePath({ id: 'u1' }), '/songs');
  assert.equal(beatsHomePath(null), '/');
});

// Photo/Video uploads mirror the backend gate (upload_clip_media): an active paid
// plan, or an admin. Unknown (still loading / fetch failed) is not locked — the
// backend still enforces it, and a paying user should never see a false lock.
test('uploads allowed for an active plan or an admin', () => {
  assert.equal(mediaUploadAllowed({ is_active: true, is_admin: false }), true);
  assert.equal(mediaUploadAllowed({ is_active: false, is_admin: true }), true);
  assert.equal(mediaUploadAllowed({ is_active: false, is_admin: false }), false);
});

test('unknown status does not show a lock', () => {
  assert.equal(mediaUploadAllowed(null), true);
});
