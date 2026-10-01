import { test } from 'node:test';
import assert from 'node:assert/strict';
import { showsAppSidebar } from './appNav.js';

test('sidebar on every logged-in app page', () => {
  for (const p of ['/songs', '/search', '/discover', '/discover/42', '/playlists', '/playlists/7', '/mixer',
    '/billing', '/settings', '/tutorial', '/contact', '/admin', '/admin/clips', '/memorials/create']) {
    assert.equal(showsAppSidebar(p), true, p);
  }
});

test('no sidebar on public, standalone, kids, clips or full-width flows', () => {
  for (const p of ['/', '/login', '/register', '/pricing', '/terms', '/privacy', '/roast', '/memorials',
    '/songs/share/abc', '/memorial/tok123', '/kids', '/kids/song', '/clips', '/clips/12', '/clips/new',
    '/discover/42/remix', '/songsX', '', undefined]) {
    assert.equal(showsAppSidebar(p), false, String(p));
  }
});
