/**
 * Themed QR greeting card: the occasion → theme mapping, the download
 * filename, what actually gets drawn on the canvas (via a recording fake 2D
 * context — node has no canvas) and the share-sheet-vs-download decision.
 */
import { test } from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import {
  CARD_THEMES, themeForOccasion, cardFilename, PERSONAL_MESSAGE_MAX,
} from './qrCardThemes.js';
import { drawQrCard, CARD_WIDTH, CARD_HEIGHT } from './drawQrCard.js';
import { shareOrDownloadCard } from './qrCardDownload.js';

// ── Recording fake CanvasRenderingContext2D ─────────────────────────────
function fakeCtx() {
  const calls = [];
  const state = { font: '10px sans-serif' };
  const ctx = new Proxy(state, {
    get(target, prop) {
      if (prop === 'calls') return calls;
      if (prop === 'measureText') {
        return (text) => {
          const px = parseFloat(/(\d+(?:\.\d+)?)px/.exec(target.font)?.[1] || '10');
          return { width: String(text).length * px * 0.55 };
        };
      }
      if (prop === 'createLinearGradient' || prop === 'createRadialGradient') {
        return () => ({ addColorStop() {} });
      }
      if (prop in target) return target[prop];
      return (...args) => { calls.push({ fn: prop, args, font: target.font }); };
    },
    set(target, prop, value) { target[prop] = value; return true; },
  });
  return ctx;
}
const texts = (ctx) => ctx.calls.filter((c) => c.fn === 'fillText').map((c) => String(c.args[0]));
const textCall = (ctx, s) => ctx.calls.find((c) => c.fn === 'fillText' && String(c.args[0]) === s);
const QR = { width: 512, height: 512, tag: 'qr' };
const LOGO = { width: 192, height: 192, tag: 'logo' };

// ── Theme mapping ───────────────────────────────────────────────────────
test('each occasion maps to its theme', () => {
  assert.equal(themeForOccasion('birthday').id, 'birthday');
  assert.equal(themeForOccasion('anniversary').id, 'wedding');
  assert.equal(themeForOccasion('christmas').id, 'christmas');
  assert.equal(themeForOccasion('memorial').id, 'memorial');
  assert.equal(themeForOccasion('love').id, 'love');
});

test('no occasion, celebration, or an unknown value uses the General theme', () => {
  for (const o of [null, undefined, '', 'celebration', 'not-a-thing']) {
    assert.equal(themeForOccasion(o).id, 'general', `occasion=${o}`);
  }
});

test('every occasion the backend allows has a theme decision', () => {
  const main = fs.readFileSync(path.join(import.meta.dirname, '..', '..', '..', 'backend', 'main.py'), 'utf8');
  const allowed = [...(/_ALLOWED_OCCASIONS = \{([^}]*)\}/.exec(main)[1]).matchAll(/"([a-z]+)"/g)].map((m) => m[1]);
  assert.ok(allowed.length >= 6);
  // celebration deliberately uses General; every other one gets its own theme
  for (const o of allowed.filter((o) => o !== 'celebration')) {
    assert.notEqual(themeForOccasion(o).id, 'general', `${o} has no card theme`);
  }
});

test('theme messages match the brief', () => {
  assert.equal(CARD_THEMES.birthday.message, 'Scan to hear your song! 🎂');
  assert.equal(CARD_THEMES.wedding.message, 'Scan to hear your song 💍');
  assert.equal(CARD_THEMES.christmas.message, 'Scan to hear your song 🎄');
  assert.equal(CARD_THEMES.memorial.message, 'A song made in your memory 🕊️');
  assert.equal(CARD_THEMES.love.message, 'Scan to hear your song ❤️');
  assert.equal(CARD_THEMES.general.message, 'Scan to hear your song 🎵');
});

// ── Filename ────────────────────────────────────────────────────────────
test('filename is [song-title]-zeus-card.png', () => {
  assert.equal(cardFilename('Midnight Vibes'), 'midnight-vibes-zeus-card.png');
  assert.equal(cardFilename("Mum's 60th Birthday!!"), 'mum-s-60th-birthday-zeus-card.png');
  assert.equal(cardFilename('  Café — Song  '), 'caf-song-zeus-card.png');
});

test('filename falls back to song-<id> when the title has no usable characters', () => {
  assert.equal(cardFilename('', 42), 'song-42-zeus-card.png');
  assert.equal(cardFilename('🎵🎵', 7), 'song-7-zeus-card.png');
});

// ── Drawing ─────────────────────────────────────────────────────────────
for (const theme of Object.values(CARD_THEMES)) {
  test(`${theme.id}: title, QR, message and Zeus Beats branding are drawn`, () => {
    const ctx = fakeCtx();
    drawQrCard(ctx, { theme, title: 'Happy Days', qrCanvas: QR, logo: LOGO });
    const t = texts(ctx);
    assert.ok(t.includes('Happy Days'), 'title missing');
    assert.ok(t.includes('Made with Zeus Beats'), 'subtitle missing');
    assert.ok(t.includes('zeusbeats.com'), 'site missing');
    assert.ok(t.includes(theme.message), 'theme message missing');
    const images = ctx.calls.filter((c) => c.fn === 'drawImage').map((c) => c.args[0].tag);
    assert.ok(images.includes('qr'), 'QR not drawn');
    assert.ok(images.includes('logo'), 'logo not drawn');
  });
}

test('branding still drawn when the logo failed to load', () => {
  const ctx = fakeCtx();
  drawQrCard(ctx, { theme: CARD_THEMES.general, title: 'X', qrCanvas: QR, logo: null });
  assert.ok(texts(ctx).includes('zeusbeats.com'));
  assert.ok(texts(ctx).includes('Zeus Beats'));
});

test('a long title wraps onto several lines and stays inside the card', () => {
  const ctx = fakeCtx();
  const title = 'The Longest Song Title Anyone Has Ever Typed Into Zeus Beats For Their Nan';
  drawQrCard(ctx, { theme: CARD_THEMES.birthday, title, qrCanvas: QR, logo: LOGO });
  const lines = ctx.calls.filter((c) => c.fn === 'fillText' && c.font.includes('bold') && /Nan|Longest|Title|Anyone|Typed/.test(c.args[0]));
  assert.ok(lines.length >= 2, 'title did not wrap');
  assert.ok(lines.length <= 3, 'title used more than 3 lines');
  for (const l of lines) {
    const px = parseFloat(/(\d+)px/.exec(l.font)[1]);
    assert.ok(String(l.args[0]).length * px * 0.55 <= CARD_WIDTH - 120, `line too wide: ${l.args[0]}`);
  }
});

test('personal message is drawn between the title and "Made with Zeus Beats", wrapped', () => {
  const ctx = fakeCtx();
  const msg = 'Happy birthday Nan, we love you more than words can say and hope this makes you smile all day long!';
  drawQrCard(ctx, { theme: CARD_THEMES.birthday, title: 'Nan', qrCanvas: QR, logo: LOGO, personalMessage: msg });
  const msgLines = ctx.calls.filter((c) => c.fn === 'fillText' && c.font.includes('italic'));
  assert.ok(msgLines.length >= 2, 'message did not wrap');
  assert.equal(msgLines.map((c) => c.args[0]).join(' '), msg);
  const titleY = textCall(ctx, 'Nan').args[2];
  const madeY = textCall(ctx, 'Made with Zeus Beats').args[2];
  for (const l of msgLines) {
    assert.ok(l.args[2] > titleY && l.args[2] < madeY, 'message not between title and subtitle');
  }
});

test('blank personal message is skipped — layout identical to no message', () => {
  const a = fakeCtx();
  const b = fakeCtx();
  drawQrCard(a, { theme: CARD_THEMES.love, title: 'Us', qrCanvas: QR, logo: LOGO });
  drawQrCard(b, { theme: CARD_THEMES.love, title: 'Us', qrCanvas: QR, logo: LOGO, personalMessage: '   ' });
  assert.equal(b.calls.filter((c) => c.fn === 'fillText' && c.font.includes('italic')).length, 0);
  assert.equal(textCall(a, 'Made with Zeus Beats').args[2], textCall(b, 'Made with Zeus Beats').args[2]);
});

test('personal message is capped at 150 characters on the card', () => {
  assert.equal(PERSONAL_MESSAGE_MAX, 150);
  const ctx = fakeCtx();
  drawQrCard(ctx, { theme: CARD_THEMES.general, title: 'T', qrCanvas: QR, logo: LOGO, personalMessage: 'a'.repeat(400) });
  const drawn = ctx.calls.filter((c) => c.fn === 'fillText' && c.font.includes('italic')).map((c) => c.args[0]).join('');
  assert.ok(drawn.length <= 150);
});

test('QR stays large and fully on the card even with a long title and full message', () => {
  const ctx = fakeCtx();
  drawQrCard(ctx, {
    theme: CARD_THEMES.wedding,
    title: 'A Very Long Wedding Song Title For The Happy Couple On Their Big Day',
    personalMessage: 'w'.repeat(5) + ' word'.repeat(29),
    qrCanvas: QR, logo: LOGO,
  });
  const qr = ctx.calls.find((c) => c.fn === 'drawImage' && c.args[0].tag === 'qr');
  const [, x, y, w, h] = qr.args;
  assert.ok(w >= 420 && w === h, `QR too small: ${w}`);
  assert.ok(x >= 0 && x + w <= CARD_WIDTH && y >= 0 && y + h <= CARD_HEIGHT);
  const msgY = textCall(ctx, CARD_THEMES.wedding.message).args[2];
  const siteY = textCall(ctx, 'zeusbeats.com').args[2];
  assert.ok(msgY > y + h && siteY > msgY && siteY < CARD_HEIGHT, 'bottom text overlaps QR or runs off the card');
});

// ── Share sheet vs download ─────────────────────────────────────────────
function fakeDoc() {
  const clicked = [];
  return {
    clicked,
    body: { appendChild() {} },
    createElement: () => {
      const a = { click() { clicked.push({ href: a.href, download: a.download }); }, remove() {} };
      return a;
    },
  };
}
const fakeUrl = { createObjectURL: () => 'blob:x', revokeObjectURL() {} };
const blob = new Blob(['png'], { type: 'image/png' });

test('mobile with file sharing: opens the share sheet with the named PNG', async () => {
  const shared = [];
  const nav = { canShare: () => true, share: async (d) => { shared.push(d); } };
  const doc = fakeDoc();
  const r = await shareOrDownloadCard(blob, 'x-zeus-card.png', { preferShare: true, nav, doc, url: fakeUrl });
  assert.equal(r, 'shared');
  assert.equal(shared[0].files[0].name, 'x-zeus-card.png');
  assert.equal(shared[0].files[0].type, 'image/png');
  assert.equal(doc.clicked.length, 0);
});

test('desktop (preferShare false) downloads even if the browser can share', async () => {
  const nav = { canShare: () => true, share: async () => { throw new Error('should not share'); } };
  const doc = fakeDoc();
  const r = await shareOrDownloadCard(blob, 'x-zeus-card.png', { preferShare: false, nav, doc, url: fakeUrl });
  assert.equal(r, 'downloaded');
  assert.deepEqual(doc.clicked, [{ href: 'blob:x', download: 'x-zeus-card.png' }]);
});

test('no file-sharing support falls back to download', async () => {
  const doc = fakeDoc();
  const r = await shareOrDownloadCard(blob, 'x-zeus-card.png', { preferShare: true, nav: {}, doc, url: fakeUrl });
  assert.equal(r, 'downloaded');
  assert.equal(doc.clicked.length, 1);
});

test('user cancelling the share sheet does not trigger a surprise download', async () => {
  const nav = { canShare: () => true, share: async () => { const e = new Error('x'); e.name = 'AbortError'; throw e; } };
  const doc = fakeDoc();
  const r = await shareOrDownloadCard(blob, 'x-zeus-card.png', { preferShare: true, nav, doc, url: fakeUrl });
  assert.equal(r, 'cancelled');
  assert.equal(doc.clicked.length, 0);
});

test('a share failure (not a cancel) falls back to download', async () => {
  const nav = { canShare: () => true, share: async () => { const e = new Error('x'); e.name = 'NotAllowedError'; throw e; } };
  const doc = fakeDoc();
  const r = await shareOrDownloadCard(blob, 'x-zeus-card.png', { preferShare: true, nav, doc, url: fakeUrl });
  assert.equal(r, 'downloaded');
  assert.equal(doc.clicked.length, 1);
});

// ── SongCard wiring ─────────────────────────────────────────────────────
const SONG_CARD = fs.readFileSync(path.join(import.meta.dirname, '..', 'components', 'SongCard.jsx'), 'utf8');
const CARD_UTILS = ['qrCardThemes.js', 'drawQrCard.js', 'qrCardDownload.js']
  .map((f) => fs.readFileSync(path.join(import.meta.dirname, f), 'utf8')).join('\n');

test('the QR panel has the Download Card button and the personal message field', () => {
  assert.ok(SONG_CARD.includes('⬇️ Download Card'));
  assert.ok(SONG_CARD.includes('✍️ Add a personal message (optional)'));
  assert.match(SONG_CARD, /maxLength=\{PERSONAL_MESSAGE_MAX\}/);
  assert.match(SONG_CARD, /drawQrCard\(/);
  assert.match(SONG_CARD, /themeForOccasion\(variant\.occasion\)/);
});

test('the occasion picker offers Christmas and Love', () => {
  assert.match(SONG_CARD, /value: 'christmas'/);
  assert.match(SONG_CARD, /value: 'love'/);
});

test('making or downloading a card never calls the API (so no credits can be spent)', () => {
  assert.doesNotMatch(CARD_UTILS, /fetch\(|BACKEND_URL|credit/i);
  const handler = /const handleCardDownload = [\s\S]*?\n  };/.exec(SONG_CARD)?.[0];
  assert.ok(handler, 'handleCardDownload not found');
  assert.doesNotMatch(handler, /fetch\(|BACKEND_URL|credit/i);
});
