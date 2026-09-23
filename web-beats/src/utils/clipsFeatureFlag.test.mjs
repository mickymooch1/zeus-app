import { test } from 'node:test';
import assert from 'node:assert/strict';
import { canCreateClips } from './clipsFeatureFlag.js';

// Pure decision logic behind the CLIPS_ENABLED flag: whether THIS user should
// see clip-creation UI (the SongCard "Create Clip" button, the /clips/new
// page). Combines the server's raw flag with the user's own is_admin. Never
// used to gate the public /clips feed or /clips/:id pages — those show
// regardless, per the build brief ("Public /clips and /clips/:id pages still
// work for anyone with a link").

test('flag off, no user: cannot create', () => {
  assert.equal(canCreateClips(false, null), false);
});

test('flag off, logged-in non-admin: cannot create', () => {
  assert.equal(canCreateClips(false, { id: 1, is_admin: false }), false);
});

test('flag off, admin: can create', () => {
  assert.equal(canCreateClips(false, { id: 1, is_admin: true }), true);
});

test('flag on, non-admin: can create', () => {
  assert.equal(canCreateClips(true, { id: 1, is_admin: false }), true);
});

test('flag on, no user at all (logged out): can still see the option since the flag is public', () => {
  assert.equal(canCreateClips(true, null), true);
});

test('flag on, admin: can create', () => {
  assert.equal(canCreateClips(true, { id: 1, is_admin: true }), true);
});
