// How a clip's visual is drawn. Cover-art clips get the "framed" treatment —
// the whole square cover, uncropped, over a blurred copy of itself; uploaded
// photos and videos fill the screen (object-fit: cover) as before.
export function clipVisualMode(mediaType, url) {
  if (!url) return 'none';
  if (mediaType === 'video') return 'video';
  if (mediaType === 'cover') return 'cover';
  return 'photo';
}

// Slow zoom (1.0 → 1.12, see .clip-ken-burns in index.css) spread over the
// clip's own duration, frozen whenever the clip isn't playing.
export function kenBurnsStyle(durationSec, playing) {
  const d = Number(durationSec) > 0 ? Number(durationSec) : 15;
  return { animationDuration: `${d}s`, animationPlayState: playing ? 'running' : 'paused' };
}

// Songs that can become a clip: finished ones, i.e. with audio (same test as
// SongCard's "Create Clip" button). Library order (newest first) is kept.
export function pickableSongs(variants) {
  return (variants || []).filter(v => v && v.mp3_url);
}
