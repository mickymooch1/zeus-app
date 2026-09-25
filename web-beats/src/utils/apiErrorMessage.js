// Turns a backend error `detail` into something a person can read.
//
// FastAPI sends three shapes: a string (HTTPException), an object with a
// `message` (our structured errors), or — on a 422 validation failure — a LIST
// of Pydantic errors ({loc, type, msg, ctx}). The list used to be ignored, so
// an over-long roast showed only "Generation failed" (2026-09-25).

// Must match SongsGenerateRequest.roast_details max_length in backend/main.py.
export const ROAST_DETAILS_MAX = 800;

// [label, plural?] — plural picks "are"/"is" in the too-long sentence.
const FIELD_LABELS = {
  roast_details: ['Roast details', true],
  roast_name:    ['Name', false],
  roast_vibe:    ['Roast vibe', false],
  brief:         ['Song description', false],
  genres:        ['Genres', true],
  platform:      ['Platform', false],
};

function describe(err) {
  if (!err || typeof err !== 'object') return '';
  const loc = Array.isArray(err.loc) ? err.loc : [];
  const field = String(loc.filter((p) => p !== 'body').pop() ?? '');
  const [label, plural] = FIELD_LABELS[field] || [field, false];
  const max = err.ctx?.max_length;

  if (field === 'genres' && err.type === 'too_long' && max != null) {
    return `Too many genres — pick up to ${max}.`;
  }
  if (err.type === 'string_too_long' && max != null && label) {
    return `${label} ${plural ? 'are' : 'is'} too long — max ${max} characters.`;
  }
  if (!err.msg) return '';
  return label ? `${label}: ${err.msg}` : err.msg;
}

export function apiErrorMessage(detail, fallback) {
  if (typeof detail === 'string') return detail || fallback;
  if (Array.isArray(detail)) {
    const parts = detail.map(describe).filter(Boolean);
    return parts.length ? parts.join(' ') : fallback;
  }
  if (detail && typeof detail === 'object' && typeof detail.message === 'string' && detail.message) {
    return detail.message;
  }
  return fallback;
}
