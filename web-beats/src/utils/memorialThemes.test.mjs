import { test } from 'node:test';
import assert from 'node:assert/strict';
import { PAGE_THEMES, normalizeTheme, waveColors } from './memorialThemes.js';

test('presets: classic and heavenly, matching the ids the backend accepts', () => {
  assert.deepEqual(PAGE_THEMES.map((t) => t.id), ['classic', 'heavenly']);
  for (const t of PAGE_THEMES) assert.ok(t.label && t.hint && t.swatch);
});

test('normalizeTheme: unknown / missing values fall back to classic', () => {
  assert.equal(normalizeTheme('heavenly'), 'heavenly');
  assert.equal(normalizeTheme('classic'), 'classic');
  for (const v of [undefined, null, '', 'neon', 'HEAVENLY']) assert.equal(normalizeTheme(v), 'classic');
});

test('waveColors: heavenly is always the light palette; classic follows dark mode', () => {
  assert.deepEqual(waveColors('heavenly', true), waveColors('heavenly', false));
  assert.notDeepEqual(waveColors('classic', true), waveColors('classic', false));
  assert.deepEqual(waveColors(undefined, false), waveColors('classic', false));
});
