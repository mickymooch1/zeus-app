import { test } from 'node:test';
import assert from 'node:assert/strict';
import { canConfirmDelete, showDeleteButton, formatBytes } from './adminDelete.js';

const clean = { email: 'Target@Example.com', blockers: [], warnings: [] };

test('canConfirmDelete: only when the typed email matches (case-insensitive, trimmed)', () => {
  assert.equal(canConfirmDelete({ preview: clean, typedEmail: '', acknowledged: false, busy: false }), false);
  assert.equal(canConfirmDelete({ preview: clean, typedEmail: 'target@example.co', acknowledged: false, busy: false }), false);
  assert.equal(canConfirmDelete({ preview: clean, typedEmail: '  target@example.com ', acknowledged: false, busy: false }), true);
});

test('canConfirmDelete: blockers always disable', () => {
  const p = { ...clean, blockers: ['Subscription is active'] };
  assert.equal(canConfirmDelete({ preview: p, typedEmail: 'target@example.com', acknowledged: true, busy: false }), false);
});

test('canConfirmDelete: warnings need the "I understand" tick', () => {
  const p = { ...clean, warnings: ['Has 1 past Stripe purchase(s)'] };
  assert.equal(canConfirmDelete({ preview: p, typedEmail: 'target@example.com', acknowledged: false, busy: false }), false);
  assert.equal(canConfirmDelete({ preview: p, typedEmail: 'target@example.com', acknowledged: true, busy: false }), true);
});

test('canConfirmDelete: disabled while loading or deleting', () => {
  assert.equal(canConfirmDelete({ preview: null, typedEmail: 'x', acknowledged: true, busy: false }), false);
  assert.equal(canConfirmDelete({ preview: clean, typedEmail: 'target@example.com', acknowledged: false, busy: true }), false);
});

test('showDeleteButton: never for admins or yourself', () => {
  assert.equal(showDeleteButton({ id: 'u1', is_admin: 0 }, { id: 'a1' }), true);
  assert.equal(showDeleteButton({ id: 'u2', is_admin: 1 }, { id: 'a1' }), false);
  assert.equal(showDeleteButton({ id: 'a1', is_admin: 0 }, { id: 'a1' }), false);
});

test('formatBytes', () => {
  assert.equal(formatBytes(0), '0 KB');
  assert.equal(formatBytes(50), '1 KB');
  assert.equal(formatBytes(5 * 1024 * 1024), '5.0 MB');
});
