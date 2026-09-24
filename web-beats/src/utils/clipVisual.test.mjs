// Run: node --test src/utils/clipVisual.test.mjs
// Cover-art clips "feel like video": framed square cover over a blurred copy,
// slow Ken Burns while playing. Photos/videos keep the full-screen crop.
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { clipVisualMode, kenBurnsStyle, pickableSongs } from './clipVisual.js';

test('visual mode by media type', () => {
  assert.equal(clipVisualMode('cover', 'x.jpg'), 'cover');
  assert.equal(clipVisualMode('image', 'x.jpg'), 'photo');
  assert.equal(clipVisualMode('video', 'x.mp4'), 'video');
  assert.equal(clipVisualMode('cover', null), 'none');
  assert.equal(clipVisualMode('image', ''), 'none');
});

test('Ken Burns runs over the clip duration and pauses when not playing', () => {
  assert.deepEqual(kenBurnsStyle(15, true), { animationDuration: '15s', animationPlayState: 'running' });
  assert.deepEqual(kenBurnsStyle(30, false), { animationDuration: '30s', animationPlayState: 'paused' });
});

test('Ken Burns falls back to 15s for a missing/bad duration', () => {
  assert.equal(kenBurnsStyle(undefined, true).animationDuration, '15s');
  assert.equal(kenBurnsStyle(0, true).animationDuration, '15s');
});

test('pick-a-song lists only finished songs (have audio), order kept', () => {
  const lib = [
    { variant_id: 3, mp3_url: 'c.mp3' },
    { variant_id: 2, mp3_url: null, status: 'generating' },
    { variant_id: 1, mp3_url: 'a.mp3' },
  ];
  assert.deepEqual(pickableSongs(lib).map(s => s.variant_id), [3, 1]);
  assert.deepEqual(pickableSongs(undefined), []);
});
