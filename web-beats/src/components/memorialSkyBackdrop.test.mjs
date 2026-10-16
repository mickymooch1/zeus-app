/**
 * The photographic memorial sky is scoped to the /memorials landing page and the
 * /memorials/create wizard. The public /memorial/:token page keeps its own
 * HeavenlyBackdrop, and every other page keeps the app-wide starfield.
 */
import { test } from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';

const SRC = path.join(import.meta.dirname, '..');
const read = (p) => fs.readFileSync(path.join(SRC, p), 'utf8');

function sourceFiles(dir) {
  return fs.readdirSync(path.join(SRC, dir), { withFileTypes: true }).flatMap((e) => {
    const rel = path.join(dir, e.name);
    if (e.isDirectory()) return sourceFiles(rel);
    return /\.jsx?$/.test(e.name) && !e.name.includes('.test.') ? [rel] : [];
  });
}

test('only the landing page and the create wizard use the memorial sky', () => {
  const users = sourceFiles('.')
    .filter((f) => /<MemorialSkyBackdrop\s*\/>/.test(read(f)))
    .map((f) => path.basename(f))
    .sort();
  assert.deepEqual(users, ['MemorialWizardPage.jsx', 'MemorialsLandingPage.jsx']);
});

test('it is the first thing inside each page wrapper, before the navbar', () => {
  assert.match(read('pages/MemorialsLandingPage.jsx'),
    /<div className="memorials-landing-page">\s*<MemorialSkyBackdrop \/>\s*<BeatsNavbar \/>/);
  assert.match(read('pages/MemorialWizardPage.jsx'),
    /<div className="memorial-wizard-page">\s*<MemorialSkyBackdrop \/>\s*<BeatsNavbar \/>/);
});

test('the landing page has no magenta hero orb tinting the sky', () => {
  assert.doesNotMatch(read('pages/MemorialsLandingPage.jsx'), /hero-orbs|orb-2/);
});

test('the public memorial page keeps HeavenlyBackdrop and not the sky', () => {
  const page = read('pages/MemorialPage.jsx');
  assert.doesNotMatch(page, /MemorialSkyBackdrop/);
  assert.match(page, /theme === 'heavenly' && <HeavenlyBackdrop \/>/);
});

test('the starfield is still mounted app-wide and knows nothing of the sky', () => {
  assert.match(read('App.jsx'), /<SpaceBackground \/>/);
  assert.doesNotMatch(read('components/SpaceBackground.jsx'), /memorial/i);
});

test('the sky covers the viewport, fixed, with a shade layer above it', () => {
  const src = read('components/MemorialSkyBackdrop.jsx');
  assert.match(src, /memorial-sky-portrait-v6\.webp/);
  assert.match(src, /position: fixed; inset: 0;/);
  assert.match(src, /background-size: cover; background-position: center;/);
  assert.ok(src.indexOf('className="zb-memorial-sky"') < src.indexOf('className="zb-memorial-sky-shade"'));
  assert.ok(fs.existsSync(path.join(SRC, 'assets/memorial/memorial-sky-portrait-v6.webp')));
});
