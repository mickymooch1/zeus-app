// Run: node --test src/utils/accents.test.mjs
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { ACCENT_OPTIONS, ACCENT_GROUP_LABELS, accentOptionLabel, accentPayload } from './genres.js';

test('29 accents, unique keys, every group known', () => {
  assert.equal(ACCENT_OPTIONS.length, 29);
  assert.equal(new Set(ACCENT_OPTIONS.map(o => o.key)).size, 29);
  const groups = ACCENT_GROUP_LABELS.map(([id]) => id);
  assert.deepEqual(groups, ['british_isles', 'americas', 'africa', 'europe', 'asia', 'pacific']);
  for (const o of ACCENT_OPTIONS) assert.ok(groups.includes(o.group), o.key);
});

test('option label is flag-first', () => {
  const jam = ACCENT_OPTIONS.find(o => o.key === 'jamaican');
  assert.equal(accentOptionLabel(jam), '🇯🇲 Jamaican');
});

test('accentPayload routes accent keys, legacy values and blank', () => {
  assert.deepEqual(accentPayload('jamaican'), { vocal_accent: 'jamaican' });
  assert.deepEqual(accentPayload('German'), { accent: 'German' });
  const rapid = 'extremely fast rapid-fire rap delivery, machine gun flow';
  assert.deepEqual(accentPayload(rapid), { accent: rapid });
  assert.deepEqual(accentPayload(''), {});
  assert.deepEqual(accentPayload(undefined), {});
});
