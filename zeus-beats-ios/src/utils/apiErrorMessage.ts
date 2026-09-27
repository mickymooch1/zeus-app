// Turns a backend error `detail` into a sentence a person can read.
//
// The backend sends three shapes: a string (plain HTTPException), an object
// with a `message` (structured errors such as the 403 email_unverified gate),
// or — on a 422 — a LIST of validation errors ({loc, type, msg, ctx}). Passing
// the raw value to `new Error()` turned the object into "[object Object]"
// (2026-09-27). Mirrors web-beats/src/utils/apiErrorMessage.js.

const FIELD_LABELS: Record<string, [string, boolean]> = {
  brief:    ['Song description', false],
  genres:   ['Genres', true],
  platform: ['Platform', false],
};

function describe(err: any): string {
  if (!err || typeof err !== 'object') return '';
  const loc: unknown[] = Array.isArray(err.loc) ? err.loc : [];
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
  return label ? `${label}: ${err.msg}` : String(err.msg);
}

export function apiErrorMessage(detail: unknown, status: number): string {
  const fallback = `Something went wrong (error ${status}). Please try again.`;
  if (typeof detail === 'string') return detail || fallback;
  if (Array.isArray(detail)) {
    const parts = detail.map(describe).filter(Boolean);
    return parts.length ? parts.join(' ') : fallback;
  }
  if (detail && typeof detail === 'object') {
    const message = (detail as { message?: unknown }).message;
    if (typeof message === 'string' && message) return message;
  }
  return fallback;
}
