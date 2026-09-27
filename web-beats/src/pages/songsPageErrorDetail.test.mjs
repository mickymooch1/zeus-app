import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';

// The backend's `detail` can be an object (403 email_unverified) or a 422 list.
// Handing it straight to Error()/an error state renders "[object Object]"
// (2026-09-25 roast, 2026-09-27 iOS Create screen). Every error on the Create
// page must go through apiErrorMessage().
const src = readFileSync(new URL('./SongsPage.jsx', import.meta.url), 'utf8');

test('SongsPage never passes a raw .detail into an error message', () => {
  const raw = src.split('\n')
    .map((line, i) => [i + 1, line])
    .filter(([, line]) => /\.detail\s*\|\|/.test(line));
  assert.deepEqual(raw, [], `raw detail fallbacks:\n${raw.map(([n, l]) => `${n}: ${l.trim()}`).join('\n')}`);
});
