/**
 * Remix-intent handoff — mirrors utils/roastDraft.js's savePostVerifyDraft pattern
 * (same file has the full reasoning): a clip's "⚡ Remix This Sound" click while
 * logged out must survive register/login (same tab, `?remix=` query param) AND
 * email verification (a NEW tab, where the query param is gone — only localStorage
 * crosses that hop).
 *
 * Node's test runner has no real `localStorage` global, so these tests install a
 * minimal in-memory stand-in before each test — this mirrors how the browser API
 * behaves (get/set/removeItem, JSON strings only) without pulling in a DOM library.
 */
import { test, beforeEach } from 'node:test';
import assert from 'node:assert/strict';

function installFakeLocalStorage() {
  const store = new Map();
  globalThis.localStorage = {
    getItem: (k) => (store.has(k) ? store.get(k) : null),
    setItem: (k, v) => store.set(k, String(v)),
    removeItem: (k) => store.delete(k),
  };
}

beforeEach(() => {
  installFakeLocalStorage();
});

const { saveRemixIntent, readRemixIntent, clearRemixIntent } =
  await import('./remixIntent.js');

test('a saved intent round-trips through read', () => {
  saveRemixIntent(42);
  assert.deepEqual(readRemixIntent(), { clipId: 42 });
});

test('nothing saved reads as null', () => {
  assert.equal(readRemixIntent(), null);
});

test('clearing removes it', () => {
  saveRemixIntent(42);
  clearRemixIntent();
  assert.equal(readRemixIntent(), null);
});

test('a non-numeric clip id is rejected at save time — never written', () => {
  saveRemixIntent('drop table clips');
  assert.equal(readRemixIntent(), null);
});

test('an intent older than the TTL is treated as absent', () => {
  const OLD = Date.now() - (2 * 60 * 60 * 1000); // 2h ago
  localStorage.setItem('zeus_remix_intent', JSON.stringify({ clipId: 42, ts: OLD }));
  assert.equal(readRemixIntent(), null);
});

test('malformed JSON is treated as absent, not thrown', () => {
  localStorage.setItem('zeus_remix_intent', '{not json');
  assert.equal(readRemixIntent(), null);
});

test('localStorage throwing (private browsing) never throws out of save/read/clear', () => {
  globalThis.localStorage = {
    getItem() { throw new Error('blocked'); },
    setItem() { throw new Error('blocked'); },
    removeItem() { throw new Error('blocked'); },
  };
  assert.doesNotThrow(() => saveRemixIntent(42));
  assert.equal(readRemixIntent(), null);
  assert.doesNotThrow(() => clearRemixIntent());
});

// ── Onboarding suppression (2026-09-24) ──────────────────────────────────────
// Someone who arrived via a remix must not get the "explore first" welcome
// modal — neither on the /songs?remix= bounce nor on landing after the remix
// was started.
import { arrivedViaRemix } from './remixIntent.js';

test('arrivedViaRemix: remix just started (navigation state)', () => {
  assert.equal(arrivedViaRemix({ state: { remixStarted: true }, search: '' }), true);
});

test('arrivedViaRemix: ?remix= on the URL', () => {
  assert.equal(arrivedViaRemix({ state: null, search: '?remix=7' }), true);
});

test('arrivedViaRemix: stored intent from the email-verification tab', () => {
  assert.equal(arrivedViaRemix({ state: null, search: '', hasStoredIntent: true }), true);
});

test('arrivedViaRemix: ordinary visit', () => {
  assert.equal(arrivedViaRemix({ state: null, search: '' }), false);
  assert.equal(arrivedViaRemix({ state: { prefillGenre: 'jazz' }, search: '?tab=all' }), false);
  assert.equal(arrivedViaRemix({ state: null, search: '?remix=abc' }), false);
});

// ── Song remix hand-off (2026-09-24, Discover "Remix") ───────────────────────
// Same hand-off as a clip remix, keyed by song: ?remixSong=<id> in the URL +
// {songId} in localStorage, landing on /discover/<id>/remix.
import {
  saveSongRemixIntent, remixTargetFromSearch, remixQuery, remixDestination,
} from './remixIntent.js';

test('song intent round-trips through localStorage', () => {
  saveSongRemixIntent(42);
  assert.deepEqual(readRemixIntent(), { songId: 42 });
  clearRemixIntent();
  assert.equal(readRemixIntent(), null);
});

test('saving a song intent replaces a clip intent (latest click wins)', () => {
  saveRemixIntent(5);
  saveSongRemixIntent(9);
  assert.deepEqual(readRemixIntent(), { songId: 9 });
  clearRemixIntent();
});

test('invalid song ids are not stored', () => {
  saveSongRemixIntent('abc');
  saveSongRemixIntent(-1);
  assert.equal(readRemixIntent(), null);
});

test('remixTargetFromSearch reads either param', () => {
  assert.deepEqual(remixTargetFromSearch('?remix=5'), { clipId: 5 });
  assert.deepEqual(remixTargetFromSearch('?remixSong=7'), { songId: 7 });
  assert.equal(remixTargetFromSearch('?remixSong=x'), null);
  assert.equal(remixTargetFromSearch(''), null);
});

test('remixQuery builds the param to carry through login/register', () => {
  assert.equal(remixQuery({ clipId: 5 }), '?remix=5');
  assert.equal(remixQuery({ songId: 7 }), '?remixSong=7');
  assert.equal(remixQuery(null), '');
});

test('remixDestination: clip → clip confirm page, song → Discover confirm page', () => {
  assert.equal(remixDestination({ clipId: 5 }), '/clips/5/remix');
  assert.equal(remixDestination({ songId: 7 }), '/discover/7/remix');
  assert.equal(remixDestination(null), null);
});

test('arrivedViaRemix also recognises ?remixSong=', () => {
  assert.equal(arrivedViaRemix({ state: null, search: '?remixSong=7' }), true);
});
