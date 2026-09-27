import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync, readdirSync, statSync } from 'node:fs';
import { join, relative } from 'node:path';
import { fileURLToPath } from 'node:url';

// The backend's `detail` can be an object (403 email_unverified) or a 422 list.
// Handing it straight to Error()/an error state renders "[object Object]"
// (2026-09-25 roast, 2026-09-27 iOS Create screen). Every error message in the
// app must go through apiErrorMessage(); this fails if a raw `x.detail ||`
// fallback comes back anywhere under src/.
const SRC = fileURLToPath(new URL('..', import.meta.url));

function* sourceFiles(dir) {
  for (const name of readdirSync(dir)) {
    const p = join(dir, name);
    if (statSync(p).isDirectory()) yield* sourceFiles(p);
    else if (/\.(jsx?|mjs)$/.test(name) && !/\.test\./.test(name)) yield p;
  }
}

test('no file passes a raw .detail into an error message', () => {
  const raw = [];
  for (const file of sourceFiles(SRC)) {
    readFileSync(file, 'utf8').split('\n').forEach((line, i) => {
      if (/\.detail\s*\|\|/.test(line)) raw.push(`${relative(SRC, file)}:${i + 1}: ${line.trim()}`);
    });
  }
  assert.deepEqual(raw, [], `raw detail fallbacks:\n${raw.join('\n')}`);
});

// The older hand-rolled "string or .message" check is safe from [object Object]
// but silently drops a 422 list, so the user sees a generic message instead of
// which field was wrong. apiErrorMessage() handles all three shapes.
test('no file hand-rolls the string-or-message detail check', () => {
  const handRolled = [];
  for (const file of sourceFiles(SRC)) {
    if (file.endsWith('apiErrorMessage.js')) continue;
    readFileSync(file, 'utf8').split('\n').forEach((line, i) => {
      if (/typeof\s+[\w.?]*\b(detail|det)\s*===\s*'string'/.test(line)) {
        handRolled.push(`${relative(SRC, file)}:${i + 1}: ${line.trim()}`);
      }
    });
  }
  assert.deepEqual(handRolled, [], `hand-rolled detail checks:\n${handRolled.join('\n')}`);
});
