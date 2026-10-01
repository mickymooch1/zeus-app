import { test } from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

// The Create page hero tagline ("Say it in a song") must exist in every language.
test('songs.heroTag is translated in every locale', () => {
  const dir = path.join(path.dirname(fileURLToPath(import.meta.url)), '..', 'locales');
  for (const f of fs.readdirSync(dir).filter((n) => n.endsWith('.json'))) {
    const tag = JSON.parse(fs.readFileSync(path.join(dir, f), 'utf8')).songs?.heroTag;
    assert.ok(typeof tag === 'string' && tag.trim().length > 0, f);
  }
});
