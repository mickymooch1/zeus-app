import { test } from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { isStandalonePublicPage } from './standalonePages.js';

test('share and memorial pages are standalone (no cookie banner)', () => {
  assert.equal(isStandalonePublicPage('/songs/share/123'), true);
  assert.equal(isStandalonePublicPage('/songs/share/_T8fZe0RiqOq'), true);
  assert.equal(isStandalonePublicPage('/memorial/_T8fZe0RiqOqcbJW'), true);
});

test('ordinary app pages are not — including the memorialS landing and wizard', () => {
  for (const p of ['/', '/songs', '/memorials', '/memorials/create', '/discover/7', '/pricing', '', undefined]) {
    assert.equal(isStandalonePublicPage(p), false, String(p));
  }
});

// Regression: the banner used to be suppressed only for /songs/share/, so it
// sat over every memorial page. App.jsx must route the decision through the
// helper, not a hand-written path check.
test('App.jsx gates the cookie banner with isStandalonePublicPage', () => {
  const here = path.dirname(fileURLToPath(import.meta.url));
  const app = fs.readFileSync(path.join(here, '..', 'App.jsx'), 'utf8');
  assert.match(app, /isStandalonePublicPage\(location\.pathname\)/);
  assert.doesNotMatch(app, /pathname\.startsWith\('\/songs\/share\/'\)/);
});
