// Remix in a different genre (2026-09-24) — shared by the clip remix and the
// Discover song remix (both on ClipRemixPage). A selection is null (keep the
// original genre — the default) or { genre, genreB? }.
import { gLabel } from './genres.js';

// Popular, clearly-different-sounding genres offered as one-tap chips. The first
// QUICK_PICK_COUNT that aren't part of the original are shown.
const QUICK_PICK_POOL = ['ukdrill', 'trap', 'rnb', 'edm', 'kpop', 'dancehall', 'drumandbass', 'lofi', 'afroswing', 'metal'];
const QUICK_PICK_COUNT = 7;

export function quickPickGenres(originalTag) {
  const original = new Set((originalTag || '').split('__').filter(Boolean));
  return QUICK_PICK_POOL.filter(g => !original.has(g)).slice(0, QUICK_PICK_COUNT);
}

export function selectionTag(sel) {
  if (!sel?.genre) return null;
  return sel.genreB ? `${sel.genre}__${sel.genreB}` : sel.genre;
}

// undefined → RemixButton's own default label ("Remix This Sound").
export function remixButtonLabel(sel) {
  const tag = selectionTag(sel);
  return tag ? `⚡ Remix as ${gLabel(tag)}` : undefined;
}

// Genre fields for POST /api/clips/:id/remix or /api/songs/:id/remix — sent only
// when the choice differs from the original (the server treats a re-picked
// original the same way, but there's no reason to send it).
export function remixGenreBody(sel, originalTag) {
  const tag = selectionTag(sel);
  if (!tag || tag === originalTag) return {};
  return sel.genreB ? { genre: sel.genre, genre_b: sel.genreB } : { genre: sel.genre };
}
