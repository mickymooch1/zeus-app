// Remix in a different genre (2026-09-24) — shared by the clip remix and the
// Discover song remix (both on ClipRemixPage). A selection is null (keep the
// original genre — the default) or { genre, genreB? }.
import { gLabel } from './genres.js';

// One-tap chips: a broad, all-ages mix. Any that are part of the original are
// dropped and topped up from the fallbacks, in order, back to QUICK_PICK_COUNT.
const QUICK_PICKS = ['pop', 'rock', 'country', 'soul', 'rnb', 'ukdrill', 'edm', 'reggae'];
const QUICK_PICK_FALLBACKS = ['trap', 'dancehall'];
const QUICK_PICK_COUNT = 8;

export function quickPickGenres(originalTag) {
  const original = new Set((originalTag || '').split('__').filter(Boolean));
  return [...QUICK_PICKS, ...QUICK_PICK_FALLBACKS].filter(g => !original.has(g)).slice(0, QUICK_PICK_COUNT);
}

// "More genres": everything except non-vocal genres (a remix always writes new
// lyrics — the server's list, derived from its own genre metadata) and `exclude`.
export function remixableGenres(allGenres, nonVocal, exclude = []) {
  const hidden = new Set([...(nonVocal || []), ...exclude]);
  return allGenres.filter(g => !hidden.has(g));
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
