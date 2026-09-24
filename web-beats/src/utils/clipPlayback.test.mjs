/**
 * A clip has no rendering of its own — it plays the SOURCE SONG's mp3 (which can be
 * minutes long) clamped to a clip_start_time..+clip_duration window. That clamp has
 * to hold regardless of the actual file length (build brief, Phase 2: "player
 * stops/loops at clip_duration regardless of file length"), so it's a pure function
 * over (currentTime, clipStart, clipDuration) rather than trusted to `<audio loop>`
 * (which loops the WHOLE file, not the window) or to the file happening to already
 * be clip_duration seconds long (uploads/generations are never guaranteed to be).
 */
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { clipSeekTarget, clipInitialTime } from './clipPlayback.js';

test('inside the window: no correction needed', () => {
  assert.equal(clipSeekTarget(12, 10, 15), null);
});

test('exactly at the window start: no correction needed', () => {
  assert.equal(clipSeekTarget(10, 10, 15), null);
});

test('at or past the window end: loops back to clip_start_time', () => {
  assert.equal(clipSeekTarget(25, 10, 15), 10);   // exactly at the end
  assert.equal(clipSeekTarget(30, 10, 15), 10);   // well past the end — long source file
});

test('before the window start (e.g. a manual seek): snaps forward to clip_start_time', () => {
  assert.equal(clipSeekTarget(3, 10, 15), 10);
});

test('a short source file that ends mid-window does not need a special case here — '
   + 'the <audio> element itself fires "ended", handled separately from timeupdate', () => {
  // Documents the split of responsibility: this function only ever answers the
  // timeupdate question. A source file shorter than clip_start+clip_duration is the
  // caller's "ended" handler's job (restart at clip_start_time), not this one's.
  assert.equal(clipSeekTarget(10, 10, 15), null);
});

test('clipInitialTime is just clip_start_time — where playback should begin on load', () => {
  assert.equal(clipInitialTime(10, 15), 10);
  assert.equal(clipInitialTime(0, 30), 0);
});

// Tap-to-pause (2026-09-24): resuming continues from where it paused — but only
// inside the clip's window; anywhere else (never started, or drifted out) it
// starts from the clip's start point.
import { clipResumeTime } from './clipPlayback.js';

test('clipResumeTime: continues from a paused point inside the window', () => {
  assert.equal(clipResumeTime(17.5, 10, 15), 17.5);
});

test('clipResumeTime: starts from the clip start when outside the window', () => {
  assert.equal(clipResumeTime(0, 10, 15), 10);     // never played yet
  assert.equal(clipResumeTime(25, 10, 15), 10);    // at/after the end
  assert.equal(clipResumeTime(3, 10, 15), 10);     // before the start
});
