/**
 * Bare /memorial (no token) used to match no route and showed a blank page.
 * It now redirects to the /memorials landing page; /memorial/:token is untouched.
 *
 * Routes are read from App.jsx and resolved with react-router's own matcher,
 * same structural approach as the other page tests (App needs a full browser
 * environment to mount).
 */
import { test } from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import { matchRoutes } from 'react-router';

const APP = fs.readFileSync(path.join(import.meta.dirname, '..', 'App.jsx'), 'utf8');

const routes = [...APP.matchAll(/<Route\s+path="([^"]+)"\s+element=\{([\s\S]*?)\}\s*\/>/g)]
  .map(([, p, element]) => ({ path: p, element }));

function resolve(url) {
  const m = matchRoutes(routes, url);
  return m && m[m.length - 1].route;
}

test('/memorial and /memorial/ redirect to /memorials (replace, so Back works)', () => {
  for (const url of ['/memorial', '/memorial/']) {
    const r = resolve(url);
    assert.ok(r, `${url} matches no route`);
    assert.match(r.element, /<Navigate to="\/memorials" replace \/>/);
  }
});

test('/memorial/:token still opens the memorial page', () => {
  assert.equal(resolve('/memorial/abc123').path, '/memorial/:token');
  assert.match(resolve('/memorial/abc123').element, /MemorialPage/);
});

test('/memorials is still the landing page', () => {
  assert.match(resolve('/memorials').element, /MemorialsLandingPage/);
});
