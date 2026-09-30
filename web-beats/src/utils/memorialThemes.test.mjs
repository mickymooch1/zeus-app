import { test } from 'node:test';
import assert from 'node:assert/strict';
import { PAGE_THEMES, normalizeTheme, waveColors, stairSteps } from './memorialThemes.js';

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

test('stairSteps: rise from the bottom and narrow toward the light, with no gaps', () => {
  const steps = stairSteps();
  assert.equal(steps.length, 14);
  steps.forEach((s, i) => {
    assert.ok(s.yTop < s.yBottom, 'each step goes up');
    assert.ok(s.halfTop < s.halfBottom, 'each step narrows');
    if (i > 0) {
      assert.equal(s.yBottom, steps[i - 1].yTop);
      assert.equal(s.halfBottom, steps[i - 1].halfTop);
    }
  });
  assert.ok(steps[0].halfBottom > 200 && steps.at(-1).halfTop < 70);
  assert.ok(steps[0].yBottom < 800, 'the whole stairway sits in the top half of the scene');
});
