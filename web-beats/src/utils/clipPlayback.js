// A clip plays its SOURCE SONG's mp3 (arbitrary length) clamped to a
// clip_start_time..+clip_duration window — see clipPlayback.test.mjs for the full
// reasoning. Pure functions so the clamp logic can be tested without a real <audio>
// element or a DOM.

// Called on the <audio> element's `timeupdate` event. Returns the currentTime the
// player must be forced to, or null when no correction is needed this tick.
export function clipSeekTarget(currentTime, clipStartTime, clipDuration) {
  const end = clipStartTime + clipDuration;
  if (currentTime < clipStartTime) return clipStartTime;
  if (currentTime >= end) return clipStartTime; // loop back to the start of the window
  return null;
}

// Where playback should begin once the source file is ready to seek.
// eslint-disable-next-line no-unused-vars -- kept for call-site symmetry with clipSeekTarget
export function clipInitialTime(clipStartTime, clipDuration) {
  return clipStartTime;
}
