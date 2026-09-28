// Run: node --test src/utils/clipMoreMenu.test.mjs
// The Clips "⋯" button opens a bottom sheet (2026-09-28 fix: the old popover
// opened upward from the button, so on /clips/:id — where ⋯ sits in the header —
// it rendered above the top of the screen and was clipped by .clip-box).
import { test } from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import { clipMenuItems, isOwnClip, clipLink } from './clipMoreMenu.js';

test("someone else's clip: Copy link + Report, no Delete", () => {
  assert.deepEqual(clipMenuItems({ isOwn: false }), ['copy', 'report']);
});

test('your own clip: Copy link + Delete, no Report', () => {
  assert.deepEqual(clipMenuItems({ isOwn: true }), ['copy', 'delete']);
});

test('ownership compares the signed-in user id with the clip creator', () => {
  const clip = { id: 7, user_id: 'abc-123' };
  assert.equal(isOwnClip({ id: 'abc-123' }, clip), true);
  assert.equal(isOwnClip({ id: 'someone-else' }, clip), false);
  assert.equal(isOwnClip(null, clip), false, 'logged out never owns');
  assert.equal(isOwnClip({ id: 'abc-123' }, null), false);
  assert.equal(isOwnClip({}, { id: 7 }), false, 'two missing ids are not a match');
});

test('copied link is the canonical public clip URL', () => {
  assert.equal(clipLink(42), 'https://zeusbeats.com/clips/42');
});

// Guard the fix itself: the sheet must stay portalled to <body> and stack above
// the cookie banner (9999) and Clips bottom nav (9000), or it gets clipped/covered again.
test('menu renders as a portal above every piece of page chrome', () => {
  const src = fs.readFileSync(new URL('../components/ClipMoreMenu.jsx', import.meta.url), 'utf8');
  assert.match(src, /createPortal\([\s\S]*document\.body\s*\)/, 'portalled to document.body');
  const z = [...src.matchAll(/zIndex:\s*(\d+)/g)].map(m => +m[1]);
  assert.ok(z.length && Math.min(...z) > 9999, `every zIndex above the cookie banner, got ${z}`);
  assert.doesNotMatch(src, /position:\s*'absolute',\s*bottom:\s*46/, 'no button-anchored popover');
});
