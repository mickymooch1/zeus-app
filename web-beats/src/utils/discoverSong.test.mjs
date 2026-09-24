// Run: node --test src/utils/discoverSong.test.mjs
// Create Clip from Discover: the clip creator takes the same song shape the
// library gives it; a Discover song (GET /api/discover, /api/discover/:id) is mapped onto it.
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { discoverSongToClipSong } from './discoverSong.js';

test('maps a Discover song onto the creator\'s library shape', () => {
  const s = discoverSongToClipSong({
    variant_id: 7, title: 'Night Drive', cover_url: 'n.jpg', mp3_url: 'n.mp3',
    duration_seconds: 184, genre_tag: 'synthwave', artist_name: 'Nyxra', like_count: 3,
  });
  assert.deepEqual(s, {
    variant_id: 7, title: 'Night Drive', image_url: 'n.jpg', mp3_url: 'n.mp3',
    duration_seconds: 184, genre_tag: 'synthwave', artist_name: 'Nyxra', is_public: 1,
  });
});

test('everything on Discover is public, so no "will make public" notice', () => {
  assert.equal(discoverSongToClipSong({ variant_id: 1 }).is_public, 1);
});

test('null in, null out', () => {
  assert.equal(discoverSongToClipSong(null), null);
});
