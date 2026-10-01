/**
 * The public homepage names no third-party AI provider (2026-09-29, owner
 * decision) — not in index.html (meta, JSON-LD, <noscript>), not in the
 * LandingPage demo copy, and not in any locale's `landing.*` strings.
 * Since 2026-10-01 that includes URLs (the old /suno-alternative slug now
 * 301s to /ai-music-generator-alternative) — no exceptions.
 */
import { test } from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const here = path.dirname(fileURLToPath(import.meta.url));
const root = path.resolve(here, '..', '..');
const PROVIDERS = /suno|claude|apiframe|anthropic|openai|cometapi|elevenlabs/i;

const withoutSlug = (s) => s;

test('index.html names no AI provider', () => {
  const html = withoutSlug(fs.readFileSync(path.join(root, 'index.html'), 'utf8'));
  assert.doesNotMatch(html, PROVIDERS);
});

test('LandingPage.jsx names no AI provider', () => {
  const src = withoutSlug(fs.readFileSync(path.join(here, 'LandingPage.jsx'), 'utf8'));
  assert.doesNotMatch(src, PROVIDERS);
});

test('no locale landing.* string names an AI provider', () => {
  const dir = path.join(here, '..', 'locales');
  const walk = (obj, prefix) => Object.entries(obj).flatMap(([k, v]) =>
    v && typeof v === 'object' ? walk(v, `${prefix}.${k}`) : [[`${prefix}.${k}`, v]]);
  for (const file of fs.readdirSync(dir).filter((f) => f.endsWith('.json'))) {
    const landing = JSON.parse(fs.readFileSync(path.join(dir, file), 'utf8')).landing || {};
    for (const [key, value] of walk(landing, 'landing')) {
      assert.ok(typeof value !== 'string' || !PROVIDERS.test(value), `${file} ${key}: ${value}`);
    }
  }
});

// 2026-10-01: the owner asked for "suno" to be gone from everything a user can
// see. Every UI string lives in the locale files, so none of them may name it.
test('no locale string anywhere names Suno', () => {
  const dir = path.join(here, '..', 'locales');
  const walk = (obj, prefix) => Object.entries(obj).flatMap(([k, v]) =>
    v && typeof v === 'object' ? walk(v, `${prefix}.${k}`) : [[`${prefix}.${k}`, v]]);
  for (const file of fs.readdirSync(dir).filter((f) => f.endsWith('.json'))) {
    for (const [key, value] of walk(JSON.parse(fs.readFileSync(path.join(dir, file), 'utf8')), '')) {
      assert.ok(typeof value !== 'string' || !/suno/i.test(value), `${file} ${key}: ${value}`);
    }
  }
});

test('privacy page names no model provider', () => {
  const src = fs.readFileSync(path.join(here, 'PrivacyPage.jsx'), 'utf8');
  assert.doesNotMatch(src, /suno/i);
});
