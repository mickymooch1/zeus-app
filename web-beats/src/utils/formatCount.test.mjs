import { test } from 'node:test';
import assert from 'node:assert/strict';
import { formatCount } from './formatCount.js';

// Matches the mockups' stat style (12.4K, 1.1M) — used on the feed/clip
// page's like/remix counts and the profile's clip/like totals.

test('numbers under 1000 are shown as-is', () => {
  assert.equal(formatCount(0), '0');
  assert.equal(formatCount(342), '342');
  assert.equal(formatCount(999), '999');
});

test('thousands get one decimal and a K suffix', () => {
  assert.equal(formatCount(1000), '1K');
  assert.equal(formatCount(1100), '1.1K');
  assert.equal(formatCount(12400), '12.4K');
  assert.equal(formatCount(45000), '45K');
});

test('millions get one decimal and an M suffix', () => {
  assert.equal(formatCount(1000000), '1M');
  assert.equal(formatCount(1200000), '1.2M');
  assert.equal(formatCount(12400000), '12.4M');
});

test('a trailing .0 is dropped, not shown as "45.0K"', () => {
  assert.equal(formatCount(45000), '45K');
  assert.equal(formatCount(2000000), '2M');
});
