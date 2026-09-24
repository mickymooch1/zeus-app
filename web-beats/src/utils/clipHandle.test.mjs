import { test } from 'node:test';
import assert from 'node:assert/strict';
import { deriveClipHandle } from './clipHandle.js';

// Must match backend/clips.py's _normalize_handle exactly — same derivation,
// used on both sides to compute the SAME @handle for a given display name.

test('lowercases and strips whitespace', () => {
  assert.equal(deriveClipHandle('Jo Smith'), 'josmith');
});

test('handles multiple internal spaces', () => {
  assert.equal(deriveClipHandle('Jo   Van   Smith'), 'jovansmith');
});

test('trims leading/trailing whitespace', () => {
  assert.equal(deriveClipHandle('  Nyxra  '), 'nyxra');
});

test('falls back to "zeusbeats" for empty/missing names', () => {
  assert.equal(deriveClipHandle(''), 'zeusbeats');
  assert.equal(deriveClipHandle(null), 'zeusbeats');
  assert.equal(deriveClipHandle(undefined), 'zeusbeats');
});

test('is idempotent', () => {
  const once = deriveClipHandle('Nyxra Beats');
  assert.equal(deriveClipHandle(once), once);
});
