// public/ads-frame.js — the only place Google's tag ever runs (see
// utils/adsConsent.js). Run in a vm with a fake browser.
import { test } from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import vm from 'node:vm';
import { fileURLToPath } from 'node:url';

const here = path.dirname(fileURLToPath(import.meta.url));
const SOURCE = fs.readFileSync(path.join(here, '..', '..', 'public', 'ads-frame.js'), 'utf8');
const ORIGIN = 'https://zeusbeats.com';

function runFrame({ hash = '#tid=42', search = '?gclid=G1', framed = true, parentOrigin = ORIGIN } = {}) {
  const messages = [];
  const scripts = [];
  const win = {
    location: { origin: ORIGIN, hash, search },
    URLSearchParams,
  };
  win.parent = framed ? {
    get location() {
      if (parentOrigin !== ORIGIN) throw new Error('SecurityError: cross-origin');
      return { origin: parentOrigin };
    },
    postMessage: (data, targetOrigin) => messages.push({ data, targetOrigin }),
  } : win;
  win.window = win;
  const document = {
    createElement: () => ({}),
    head: { appendChild: (el) => { scripts.push(el); return el; } },
  };
  vm.runInNewContext(SOURCE, { window: win, document, URLSearchParams, Date });
  // JSON round-trip: objects made inside the vm have another realm's prototypes
  const plain = (x) => JSON.parse(JSON.stringify(x));
  const calls = () => (win.dataLayer || []).map((a) => Array.from(a));
  const plainCalls = () => calls().map((c) => c.map((v) => (typeof v === 'function' ? v : plain(v))));
  return { win, messages, scripts, calls, plainCalls, plainMessages: () => plain(messages) };
}

test('framed by zeusbeats.com: Consent Mode default denied first, then only ad_storage + ad_user_data granted, no config', () => {
  const f = runFrame();
  const c = f.plainCalls();
  assert.deepEqual(c[0], ['consent', 'default', {
    ad_storage: 'denied', ad_user_data: 'denied', ad_personalization: 'denied', analytics_storage: 'denied',
  }]);
  assert.deepEqual(c[1], ['consent', 'update', {
    ad_storage: 'granted', ad_user_data: 'granted', ad_personalization: 'denied', analytics_storage: 'denied',
  }]);
  assert.equal(c.filter((x) => x[0] === 'config').length, 0, 'config would add page_view pings');
  assert.equal(f.scripts.length, 1);
  assert.equal(f.scripts[0].src, 'https://www.googletagmanager.com/gtag/js?id=AW-18517714190');
});

test('the conversion is pushed only after gtag.js has loaded, with the user id as transaction_id', () => {
  const f = runFrame({ hash: '#tid=987654' });
  assert.equal(f.calls().filter((x) => x[0] === 'event').length, 0, 'nothing before the tag loads');
  f.scripts[0].onload();
  const events = f.calls().filter((x) => x[0] === 'event');
  assert.equal(events.length, 1);
  assert.equal(events[0][1], 'conversion');
  assert.equal(events[0][2].send_to, 'AW-18517714190/o7SdCLShsZ8dEI7K9_1E');
  assert.equal(events[0][2].transaction_id, '987654');
});

test("reports 'handed-off' to the parent only when the tag's event_callback fires", () => {
  const f = runFrame();
  f.scripts[0].onload();
  assert.equal(f.messages.length, 0);
  f.calls().find((x) => x[0] === 'event')[2].event_callback();
  assert.deepEqual(f.plainMessages(), [{ data: { type: 'zeus-ads-frame', tid: '42', status: 'handed-off' }, targetOrigin: ORIGIN }]);
});

test("reports 'failed' when gtag.js can't load", () => {
  const f = runFrame();
  f.scripts[0].onerror();
  assert.deepEqual(f.messages.map((m) => m.data.status), ['failed']);
  assert.equal(f.calls().filter((x) => x[0] === 'event').length, 0);
});

test('opened directly (not in a frame): does nothing at all', () => {
  const f = runFrame({ framed: false });
  assert.equal(f.scripts.length, 0);
  assert.equal(f.win.dataLayer, undefined);
});

test('framed by another site: does nothing at all', () => {
  const f = runFrame({ parentOrigin: 'https://evil.example' });
  assert.equal(f.scripts.length, 0);
  assert.equal(f.messages.length, 0);
});

test('no transaction id: loads nothing and reports failed', () => {
  const f = runFrame({ hash: '' });
  assert.equal(f.scripts.length, 0);
  assert.deepEqual(f.messages.map((m) => m.data.status), ['failed']);
});

test('the frame page loads only this script and is kept out of search results', () => {
  const html = fs.readFileSync(path.join(here, '..', '..', 'public', 'ads-frame.html'), 'utf8');
  assert.match(html, /<meta name="robots" content="noindex, nofollow">/);
  assert.deepEqual([...html.matchAll(/<script[^>]*>/g)].map((m) => m[0]), ['<script src="/ads-frame.js">']);
});
