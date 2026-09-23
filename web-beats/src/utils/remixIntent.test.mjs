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
