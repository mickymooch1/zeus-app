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
  CARD_PHOTO_TYPES, CARD_PHOTO_MAX_BYTES, validateCardPhoto,
} from './qrCardThemes.js';
import { drawQrCard, coverCrop, CARD_WIDTH, CARD_HEIGHT, CARD_MAX_HEIGHT } from './drawQrCard.js';
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
  const { height } = drawQrCard(ctx, {
    theme: CARD_THEMES.wedding,
    title: 'A Very Long Wedding Song Title For The Happy Couple On Their Big Day',
    personalMessage: 'w'.repeat(5) + ' word'.repeat(29),
    qrCanvas: QR, logo: LOGO,
  });
  assert.ok(height >= CARD_HEIGHT && height <= CARD_MAX_HEIGHT);
  const qr = ctx.calls.find((c) => c.fn === 'drawImage' && c.args[0].tag === 'qr');
  const [, x, y, w, h] = qr.args;
  assert.ok(w >= 420 && w === h, `QR too small: ${w}`);
  assert.ok(x >= 0 && x + w <= CARD_WIDTH && y >= 0 && y + h <= height);
  const msgY = textCall(ctx, CARD_THEMES.wedding.message).args[2];
  const siteY = textCall(ctx, 'zeusbeats.com').args[2];
  assert.ok(msgY > y + h && siteY > msgY && siteY < height, 'bottom text overlaps QR or runs off the card');
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

// ── Optional photo ──────────────────────────────────────────────────────
const PHOTO = { width: 1600, height: 1200, tag: 'photo' };
const photoDraw = (ctx) => ctx.calls.find((c) => c.fn === 'drawImage' && c.args[0].tag === 'photo');
const qrDraw = (ctx) => ctx.calls.find((c) => c.fn === 'drawImage' && c.args[0].tag === 'qr');

test('birthday and memorial use a circular portrait; the rest use a panel', () => {
  for (const id of ['birthday', 'memorial']) assert.equal(CARD_THEMES[id].photo, 'circle', id);
  for (const id of ['wedding', 'christmas', 'love', 'general']) assert.equal(CARD_THEMES[id].photo, 'panel', id);
});

for (const id of ['birthday', 'memorial']) {
  test(`${id}: photo is a 200px circle centred at the top, above the title, with a white ring`, () => {
    const ctx = fakeCtx();
    drawQrCard(ctx, { theme: CARD_THEMES[id], title: 'Nan', qrCanvas: QR, logo: LOGO, photo: PHOTO });
    const d = photoDraw(ctx);
    assert.ok(d, 'photo not drawn');
    const [, , , , , dx, dy, dw, dh] = d.args;
    assert.deepEqual([dx + dw / 2, dw, dh], [CARD_WIDTH / 2, 200, 200]);
    assert.ok(dy + dh < textCall(ctx, 'Nan').args[2], 'portrait not above the title');
    const idx = ctx.calls.indexOf(d);
    const before = ctx.calls.slice(0, idx);
    const clipIdx = before.map((c) => c.fn).lastIndexOf('clip');
    assert.ok(clipIdx >= 0, 'photo not clipped');
    const arc = before.slice(0, clipIdx).reverse().find((c) => c.fn === 'arc');
    assert.deepEqual(arc.args.slice(0, 3), [CARD_WIDTH / 2, dy + 100, 100], 'not clipped to the circle');
    const ring = ctx.calls.slice(idx).find((c) => c.fn === 'stroke');
    assert.ok(ring, 'no white ring stroke after the photo');
    // the header emoji is replaced by the portrait
    assert.ok(!texts(ctx).includes(CARD_THEMES[id].icon));
  });
}

for (const id of ['wedding', 'christmas', 'love', 'general']) {
  test(`${id}: photo is an 800x400 panel between the title and the QR`, () => {
    const ctx = fakeCtx();
    drawQrCard(ctx, { theme: CARD_THEMES[id], title: 'Us', qrCanvas: QR, logo: LOGO, photo: PHOTO });
    const [, , , , , dx, dy, dw, dh] = photoDraw(ctx).args;
    assert.deepEqual([dx, dw, dh], [(CARD_WIDTH - 800) / 2, 800, 400]);
    assert.ok(dy > textCall(ctx, 'Made with Zeus Beats').args[2], 'panel not below the title block');
    assert.ok(dy + dh < qrDraw(ctx).args[2], 'panel overlaps the QR');
    assert.ok(texts(ctx).includes(CARD_THEMES[id].icon), 'header emoji should stay');
  });
}

test('no photo: nothing drawn, no gap — identical calls to a card drawn without the option', () => {
  for (const theme of Object.values(CARD_THEMES)) {
    const a = fakeCtx();
    const b = fakeCtx();
    drawQrCard(a, { theme, title: 'Song', qrCanvas: QR, logo: LOGO });
    drawQrCard(b, { theme, title: 'Song', qrCanvas: QR, logo: LOGO, photo: null });
    assert.equal(photoDraw(b), undefined);
    const sig = (ctx) => ctx.calls.map((c) => [c.fn, ...c.args.map((v) => (typeof v === 'object' ? v?.tag : v))]);
    assert.deepEqual(sig(b), sig(a));
  }
});

test('no photo: QR sits exactly where it did before photos existed', () => {
  // 1-line title, no message → same position the photo-less card has always used
  const ctx = fakeCtx();
  drawQrCard(ctx, { theme: CARD_THEMES.general, title: 'Song', qrCanvas: QR, logo: LOGO });
  const [, x, y, w] = qrDraw(ctx).args;
  assert.deepEqual([x, w], [CARD_WIDTH / 2 - 320 + 20, 600]);
  assert.ok(y < 460, `QR pushed down to ${y}`);
});

test('photo-less card keeps its 1080x1440 size', () => {
  const r = drawQrCard(fakeCtx(), { theme: CARD_THEMES.general, title: 'Song', qrCanvas: QR, logo: LOGO });
  assert.equal(r.height, CARD_HEIGHT);
});

test('worst case (long title, full message, panel photo) grows the card but keeps everything on it', () => {
  const ctx = fakeCtx();
  const r = drawQrCard(ctx, {
    theme: CARD_THEMES.wedding,
    title: 'A Very Long Wedding Song Title For The Happy Couple On Their Big Day',
    personalMessage: 'w'.repeat(5) + ' word'.repeat(29),
    qrCanvas: QR, logo: LOGO, photo: PHOTO,
  });
  assert.ok(r.height > CARD_HEIGHT && r.height <= CARD_MAX_HEIGHT, `height ${r.height}`);
  const [, x, y, w, h] = qrDraw(ctx).args;
  assert.ok(w >= 420 && x + w <= CARD_WIDTH && y + h < r.height);
  const siteY = textCall(ctx, 'zeusbeats.com').args[2];
  assert.ok(siteY > y + h && siteY < r.height - 30, 'footer off the card');
  const bg = ctx.calls.find((c) => c.fn === 'fillRect');
  assert.equal(bg.args[3], r.height, 'background does not cover the taller card');
});

test('cover crop fills the target without stretching', () => {
  // wide photo into a 2:1 panel → crop the sides
  assert.deepEqual(coverCrop(3000, 1000, 800, 400), { sx: 500, sy: 0, sw: 2000, sh: 1000 });
  // tall photo into a circle (1:1) → crop top and bottom
  assert.deepEqual(coverCrop(1000, 3000, 200, 200), { sx: 0, sy: 1000, sw: 1000, sh: 1000 });
  const ctx = fakeCtx();
  drawQrCard(ctx, { theme: CARD_THEMES.love, title: 'Us', qrCanvas: QR, logo: LOGO, photo: PHOTO });
  const [, sx, sy, sw, sh, , , dw, dh] = photoDraw(ctx).args;
  assert.equal(sw / sh, dw / dh, 'aspect ratio not preserved');
  assert.deepEqual([sx, sy], [0, 200]);
});

test('photo validation: JPG/PNG/WEBP up to 5MB', () => {
  assert.deepEqual(CARD_PHOTO_TYPES, ['image/jpeg', 'image/png', 'image/webp']);
  assert.equal(CARD_PHOTO_MAX_BYTES, 5 * 1024 * 1024);
  for (const type of CARD_PHOTO_TYPES) assert.equal(validateCardPhoto({ type, size: 1000 }), null);
  assert.equal(validateCardPhoto({ type: 'image/png', size: 5 * 1024 * 1024 }), null);
});

test('photo over 5MB is rejected with a clear error', () => {
  assert.equal(validateCardPhoto({ type: 'image/jpeg', size: 5 * 1024 * 1024 + 1 }), 'That photo is over 5MB — please choose a smaller one.');
});

test('non-image (or unsupported image) file is rejected', () => {
  for (const type of ['application/pdf', 'video/mp4', 'image/gif', 'image/heic', '']) {
    assert.equal(validateCardPhoto({ type, size: 1000 }), 'Please choose a JPG, PNG or WEBP image.', type);
  }
});

test('SongCard: photo button, picker limits, validation and remove are wired', () => {
  assert.ok(SONG_CARD.includes('📷 Add a photo (optional)'));
  assert.match(SONG_CARD, /type="file"[\s\S]{0,200}accept=\{CARD_PHOTO_TYPES\.join\(','\)\}/);
  assert.match(SONG_CARD, /validateCardPhoto\(file\)/);
  assert.match(SONG_CARD, /photo: cardPhoto/);
  assert.match(SONG_CARD, /onClick=\{removeCardPhoto\}/);
  assert.match(SONG_CARD, /const removeCardPhoto = \(\) => \{[\s\S]*?setCardPhoto\(null\)/, 'remove does not clear the photo');
  // the effect that redraws the canvas must re-run when the photo changes
  assert.match(SONG_CARD, /\[qrOpen, shareUrlForQr, title, cardTheme, cardMessage, cardPhoto\]/);
});

test('the photo never leaves the browser', () => {
  const handler = /const handleCardPhoto = [\s\S]*?\n  };/.exec(SONG_CARD)?.[0];
  assert.ok(handler, 'handleCardPhoto not found');
  assert.doesNotMatch(handler, /fetch\(|BACKEND_URL|FormData|XMLHttpRequest/);
});

test('footer branding never crowds the theme message, however tall the card', () => {
  const variants = [
    { title: 'Song' },
    { title: 'A Very Long Wedding Song Title For The Happy Couple On Their Big Day', personalMessage: 'word '.repeat(30) },
    { title: 'Song', photo: PHOTO },
    { title: 'A Very Long Wedding Song Title For The Happy Couple On Their Big Day', personalMessage: 'word '.repeat(30), photo: PHOTO },
  ];
  for (const theme of Object.values(CARD_THEMES)) {
    for (const v of variants) {
      const ctx = fakeCtx();
      const { height } = drawQrCard(ctx, { theme, qrCanvas: QR, logo: LOGO, ...v });
      const msgY = textCall(ctx, theme.message).args[2];
      const brandY = textCall(ctx, 'Zeus Beats').args[2];
      const siteY = textCall(ctx, 'zeusbeats.com').args[2];
      assert.ok(brandY - msgY >= 90, `${theme.id}: brand row ${brandY - msgY}px under the message`);
      assert.ok(siteY <= height - 50, `${theme.id}: site line too close to the bottom edge`);
    }
  }
});
