// Run: node --test src/utils/remixSource.test.mjs
// The remix confirm page serves both a clip (/clips/:id/remix, GET /api/clips/:id)
// and a Discover song (/discover/:id/remix, GET /api/discover/:id). This maps
// either response onto the one shape the page renders.
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { toRemixSource } from './remixSource.js';

const B = 'https://api.example';

test('clip with cover media uses the song cover', () => {
  const s = toRemixSource({ song_title: 'Sky', media_type: 'cover', song_cover_url: 'c.jpg', genre_tag: 'soulrnb',
    remix_style_descriptors: 'soul', remix_theme: 'love' }, { isSong: false, backendUrl: B });
  assert.deepEqual(s, { title: 'Sky', visualUrl: 'c.jpg', genreTag: 'soulrnb', style: 'soul', theme: 'love' });
});

test('clip with uploaded media uses the upload, on the backend origin', () => {
  const s = toRemixSource({ song_title: 'Sky', media_type: 'image', media_url: '/files/clips/a.jpg' }, { isSong: false, backendUrl: B });
  assert.equal(s.visualUrl, `${B}/files/clips/a.jpg`);
});

test('Discover song uses its title and cover_url', () => {
  const s = toRemixSource({ title: 'Night Drive', cover_url: 'n.jpg', genre_tag: 'synthwave',
    remix_style_descriptors: 'synths', remix_theme: 'roads' }, { isSong: true, backendUrl: B });
  assert.deepEqual(s, { title: 'Night Drive', visualUrl: 'n.jpg', genreTag: 'synthwave', style: 'synths', theme: 'roads' });
});

test('missing bits come back empty, never undefined', () => {
  const s = toRemixSource({}, { isSong: true, backendUrl: B });
  assert.deepEqual(s, { title: '', visualUrl: null, genreTag: '', style: '', theme: '' });
});
