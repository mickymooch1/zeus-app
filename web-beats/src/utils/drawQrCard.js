// Draws the themed QR greeting card straight onto a 2D canvas context. The
// on-screen preview IS this canvas, so the downloaded PNG always matches what
// the user saw (no html2canvas DOM-to-image guesswork with gradients/emoji).
import { PERSONAL_MESSAGE_MAX } from './qrCardThemes.js';

export const CARD_WIDTH = 1080;
export const CARD_HEIGHT = 1440;
// Cards only grow past CARD_HEIGHT when the content needs it (long title +
// message + photo); 1920 is the phone "story" size, so it still shares well.
export const CARD_MAX_HEIGHT = 1920;

const EMOJI = "'Apple Color Emoji', 'Segoe UI Emoji', 'Noto Color Emoji'";
const SERIF = `Georgia, 'Iowan Old Style', 'Palatino Linotype', serif, ${EMOJI}`;
const SANS = `-apple-system, BlinkMacSystemFont, 'Segoe UI', Helvetica, Arial, sans-serif, ${EMOJI}`;
const TEXT_WIDTH = 900;
const CX = CARD_WIDTH / 2;
// Space kept under the QR panel for the theme message + footer.
const BOTTOM_RESERVE = 250;
const PANEL_MIN = 460;
const PANEL_MAX = 640;
const PANEL_PAD = 20;
// Space actually used under a minimum-size QR panel: theme message + footer.
const FOOTER_SPACE = 256;
const PORTRAIT = 200;
const PHOTO_PANEL_W = 800;
const PHOTO_PANEL_H = 400;

// object-fit: cover — the source rectangle to crop so the photo fills the
// target box without stretching.
export function coverCrop(sw, sh, dw, dh) {
  const scale = Math.max(dw / sw, dh / sh);
  const cw = dw / scale;
  const ch = dh / scale;
  return { sx: (sw - cw) / 2, sy: (sh - ch) / 2, sw: cw, sh: ch };
}

function drawPhoto(ctx, photo, x, y, w, h) {
  const c = coverCrop(photo.width, photo.height, w, h);
  ctx.drawImage(photo, c.sx, c.sy, c.sw, c.sh, x, y, w, h);
}

// Greedy word wrap; a single word wider than the line is broken by characters.
function wrapLines(ctx, text, maxWidth) {
  const lines = [];
  let line = '';
  for (const word of text.split(/\s+/).filter(Boolean)) {
    const candidate = line ? `${line} ${word}` : word;
    if (ctx.measureText(candidate).width <= maxWidth) { line = candidate; continue; }
    if (line) lines.push(line);
    line = '';
    let chunk = '';
    for (const ch of Array.from(word)) {
      if (ctx.measureText(chunk + ch).width > maxWidth && chunk) { lines.push(chunk); chunk = ''; }
      chunk += ch;
    }
    line = chunk;
  }
  if (line) lines.push(line);
  return lines;
}

function clampLines(ctx, lines, maxLines, maxWidth) {
  if (lines.length <= maxLines) return lines;
  const kept = lines.slice(0, maxLines);
  let last = kept[maxLines - 1];
  while (last && ctx.measureText(`${last}…`).width > maxWidth) last = last.slice(0, -1);
  kept[maxLines - 1] = `${last.trimEnd()}…`;
  return kept;
}

// Biggest title size that fits in 2 lines, else a smaller size in up to 3.
function layoutTitle(ctx, title) {
  for (const [size, maxLines] of [[84, 2], [68, 3]]) {
    ctx.font = `bold ${size}px ${SERIF}`;
    const lines = wrapLines(ctx, title, TEXT_WIDTH);
    if (lines.length <= maxLines || size === 68) {
      return { size, lines: clampLines(ctx, lines, maxLines, TEXT_WIDTH) };
    }
  }
  return null; // unreachable
}

function rng(seed) {
  let a = seed >>> 0;
  return () => {
    a = (a + 0x6d2b79f5) >>> 0;
    let t = a;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

// Keeps decorations mostly to the edges so the text and QR stay clean.
function inCentre(x, y, h) {
  return x > 130 && x < CARD_WIDTH - 130 && y > 200 && y < h - 120;
}

function roundRect(ctx, x, y, w, h, r) {
  ctx.beginPath();
  ctx.moveTo(x + r, y);
  ctx.lineTo(x + w - r, y);
  ctx.quadraticCurveTo(x + w, y, x + w, y + r);
  ctx.lineTo(x + w, y + h - r);
  ctx.quadraticCurveTo(x + w, y + h, x + w - r, y + h);
  ctx.lineTo(x + r, y + h);
  ctx.quadraticCurveTo(x, y + h, x, y + h - r);
  ctx.lineTo(x, y + r);
  ctx.quadraticCurveTo(x, y, x + r, y);
  ctx.closePath();
}

function heart(ctx, x, y, s) {
  ctx.beginPath();
  ctx.moveTo(x, y + s * 0.3);
  ctx.bezierCurveTo(x, y, x - s * 0.5, y, x - s * 0.5, y + s * 0.3);
  ctx.bezierCurveTo(x - s * 0.5, y + s * 0.6, x, y + s * 0.8, x, y + s);
  ctx.bezierCurveTo(x, y + s * 0.8, x + s * 0.5, y + s * 0.6, x + s * 0.5, y + s * 0.3);
  ctx.bezierCurveTo(x + s * 0.5, y, x, y, x, y + s * 0.3);
  ctx.closePath();
  ctx.fill();
}

function snowflake(ctx, x, y, r) {
  ctx.beginPath();
  for (let i = 0; i < 6; i++) {
    const a = (Math.PI / 3) * i;
    const ex = x + Math.cos(a) * r;
    const ey = y + Math.sin(a) * r;
    ctx.moveTo(x, y);
    ctx.lineTo(ex, ey);
    // little side branches two-thirds of the way out
    const bx = x + Math.cos(a) * r * 0.62;
    const by = y + Math.sin(a) * r * 0.62;
    for (const d of [-0.6, 0.6]) {
      ctx.moveTo(bx, by);
      ctx.lineTo(bx + Math.cos(a + d) * r * 0.3, by + Math.sin(a + d) * r * 0.3);
    }
  }
  ctx.stroke();
}

function cloud(ctx, x, y, w, alpha) {
  ctx.save();
  ctx.globalAlpha = alpha;
  ctx.fillStyle = '#ffffff';
  for (const [dx, dy, rx, ry] of [[0, 0, 0.5, 0.16], [-0.28, 0.04, 0.3, 0.12], [0.3, 0.05, 0.32, 0.11], [0.05, -0.07, 0.26, 0.12]]) {
    ctx.beginPath();
    ctx.ellipse(x + dx * w, y + dy * w, rx * w, ry * w, 0, 0, Math.PI * 2);
    ctx.fill();
  }
  ctx.restore();
}

function flower(ctx, x, y, r, theme) {
  ctx.save();
  ctx.fillStyle = theme.petal;
  for (let i = 0; i < 5; i++) {
    const a = (Math.PI * 2 * i) / 5;
    ctx.beginPath();
    ctx.ellipse(x + Math.cos(a) * r * 0.55, y + Math.sin(a) * r * 0.55, r * 0.5, r * 0.32, a, 0, Math.PI * 2);
    ctx.fill();
  }
  ctx.fillStyle = theme.accent;
  ctx.beginPath();
  ctx.arc(x, y, r * 0.24, 0, Math.PI * 2);
  ctx.fill();
  ctx.restore();
}

function leaf(ctx, x, y, len, angle, colour) {
  ctx.save();
  ctx.fillStyle = colour;
  ctx.beginPath();
  ctx.ellipse(x + Math.cos(angle) * len * 0.5, y + Math.sin(angle) * len * 0.5, len * 0.5, len * 0.18, angle, 0, Math.PI * 2);
  ctx.fill();
  ctx.restore();
}

const MOTIFS = {
  confetti(ctx, theme, h) {
    const r = rng(11);
    for (let n = 0; n < 160; n++) {
      const x = r() * CARD_WIDTH;
      const y = r() * h;
      if (inCentre(x, y, h)) continue;
      ctx.save();
      ctx.globalAlpha = 0.65 + r() * 0.35;
      ctx.fillStyle = theme.confetti[n % theme.confetti.length];
      ctx.translate(x, y);
      ctx.rotate(r() * Math.PI);
      if (n % 3 === 0) {
        ctx.beginPath();
        ctx.arc(0, 0, 5 + r() * 6, 0, Math.PI * 2);
        ctx.fill();
      } else {
        ctx.fillRect(-12, -5, 24, 10);
      }
      ctx.restore();
    }
  },
  floral(ctx, theme, h) {
    ctx.save();
    ctx.strokeStyle = theme.accent;
    ctx.lineWidth = 4;
    roundRect(ctx, 34, 34, CARD_WIDTH - 68, h - 68, 18);
    ctx.stroke();
    ctx.lineWidth = 1.5;
    roundRect(ctx, 52, 52, CARD_WIDTH - 104, h - 104, 12);
    ctx.stroke();
    ctx.restore();
    const corners = [[70, 70, 0], [CARD_WIDTH - 70, 70, Math.PI / 2], [CARD_WIDTH - 70, h - 70, Math.PI], [70, h - 70, -Math.PI / 2]];
    for (const [x, y, rot] of corners) {
      for (let i = 0; i < 5; i++) {
        leaf(ctx, x, y, 70, rot + (i * Math.PI) / 10, i % 2 ? 'rgba(201,162,74,0.85)' : 'rgba(150,170,120,0.7)');
      }
      flower(ctx, x, y, 34, theme);
      flower(ctx, x + Math.cos(rot) * 96, y + Math.sin(rot) * 96, 20, theme);
      flower(ctx, x + Math.cos(rot + Math.PI / 2) * 96, y + Math.sin(rot + Math.PI / 2) * 96, 20, theme);
    }
  },
  snow(ctx, theme, h) {
    ctx.save();
    ctx.fillStyle = theme.band;
    ctx.fillRect(0, 0, CARD_WIDTH, 26);
    ctx.fillRect(0, h - 26, CARD_WIDTH, 26);
    ctx.fillStyle = theme.accent;
    ctx.fillRect(0, 26, CARD_WIDTH, 4);
    ctx.fillRect(0, h - 30, CARD_WIDTH, 4);
    ctx.restore();
    const r = rng(25);
    ctx.save();
    ctx.strokeStyle = '#ffffff';
    ctx.lineCap = 'round';
    for (let n = 0; n < 90; n++) {
      const x = r() * CARD_WIDTH;
      const y = 40 + r() * (h - 80);
      const centre = inCentre(x, y, h);
      if (centre && n % 4) continue;
      ctx.globalAlpha = centre ? 0.12 : 0.35 + r() * 0.5;
      ctx.lineWidth = 2 + r() * 2;
      snowflake(ctx, x, y, 10 + r() * 22);
    }
    ctx.restore();
  },
  clouds(ctx, theme, h) {
    const glow = ctx.createRadialGradient(CX, 0, 40, CX, 0, 900);
    glow.addColorStop(0, 'rgba(255,255,255,0.85)');
    glow.addColorStop(1, 'rgba(255,255,255,0)');
    ctx.save();
    ctx.fillStyle = glow;
    ctx.fillRect(0, 0, CARD_WIDTH, h);
    ctx.restore();
    for (const [x, y, w, a] of [[150, 120, 360, 0.55], [930, 210, 400, 0.45], [120, h - 170, 420, 0.4], [960, h - 110, 380, 0.45], [60, 720, 260, 0.3], [1030, 820, 280, 0.3]]) {
      cloud(ctx, x, y, w, a);
    }
  },
  hearts(ctx, theme, h) {
    const r = rng(14);
    ctx.save();
    ctx.fillStyle = theme.accent;
    for (let n = 0; n < 70; n++) {
      const x = r() * CARD_WIDTH;
      const y = r() * h;
      if (inCentre(x, y, h)) continue;
      ctx.globalAlpha = 0.12 + r() * 0.2;
      heart(ctx, x, y, 26 + r() * 46);
    }
    ctx.restore();
  },
  neon(ctx, theme, h) {
    for (const [x, y, rad, colour] of [[120, 160, 620, theme.glow], [CARD_WIDTH - 80, h - 160, 640, theme.accent]]) {
      const g = ctx.createRadialGradient(x, y, 0, x, y, rad);
      g.addColorStop(0, `${colour}55`);
      g.addColorStop(1, `${colour}00`);
      ctx.save();
      ctx.fillStyle = g;
      ctx.fillRect(0, 0, CARD_WIDTH, h);
      ctx.restore();
    }
    ctx.save();
    ctx.strokeStyle = theme.accent;
    ctx.lineWidth = 3;
    ctx.shadowColor = theme.accent;
    ctx.shadowBlur = 24;
    roundRect(ctx, 32, 32, CARD_WIDTH - 64, h - 64, 28);
    ctx.stroke();
    ctx.restore();
  },
};

function centredText(ctx, text, y, font, colour) {
  ctx.font = font;
  ctx.fillStyle = colour;
  ctx.fillText(text, CX, y);
}

/**
 * Draws the card and sizes the canvas to fit it.
 * @param ctx  2D context of a CARD_WIDTH-wide canvas (its height is set here)
 * @param opts.theme           one of CARD_THEMES
 * @param opts.title           song title
 * @param opts.qrCanvas        canvas holding the QR code (drawn scaled)
 * @param opts.logo            loaded Zeus logo image, or null if it failed
 * @param opts.personalMessage optional, blank = skipped
 * @param opts.photo           optional loaded image; null = card unchanged
 * @returns {{ height: number }}
 */
export function drawQrCard(ctx, { theme, title, qrCanvas, logo, personalMessage = '', photo = null }) {
  const portrait = photo && theme.photo === 'circle';
  const panelPhoto = photo && theme.photo === 'panel';

  // ── Layout pass: every position is worked out before anything is drawn, so
  // the card height (and therefore the background) is known up front.
  let y = portrait ? 300 : 240;
  const { size, lines } = layoutTitle(ctx, title || 'Your Song');
  const titleLh = size * 1.1;
  const titleYs = lines.map((_, i) => y + titleLh * i + titleLh / 2);
  y += titleLh * lines.length;

  const message = String(personalMessage || '').trim().slice(0, PERSONAL_MESSAGE_MAX);
  const msgFont = `italic 36px ${SERIF}`;
  let msgLines = [];
  if (message) {
    y += 20;
    ctx.font = msgFont;
    msgLines = clampLines(ctx, wrapLines(ctx, message, TEXT_WIDTH), 4, TEXT_WIDTH);
  }
  const msgYs = msgLines.map((_, i) => y + 46 * i + 23);
  y += 46 * msgLines.length;

  y += 24;
  const madeY = y + 18;
  y += 36;

  let photoTop = 0;
  if (panelPhoto) {
    photoTop = y + 30;
    y = photoTop + PHOTO_PANEL_H;
  }

  const qrTop = y + 36;
  const height = Math.min(CARD_MAX_HEIGHT, Math.max(CARD_HEIGHT, Math.ceil(qrTop + PANEL_MIN + FOOTER_SPACE)));
  const panel = Math.max(PANEL_MIN, Math.min(PANEL_MAX, height - BOTTOM_RESERVE - qrTop));

  // ── Draw pass
  if (ctx.canvas && ctx.canvas.height !== height) ctx.canvas.height = height; // resets ctx state
  ctx.textAlign = 'center';
  ctx.textBaseline = 'middle';

  const bg = ctx.createLinearGradient(0, 0, 0, height);
  bg.addColorStop(0, theme.bg[0]);
  bg.addColorStop(1, theme.bg[1]);
  ctx.fillStyle = bg;
  ctx.fillRect(0, 0, CARD_WIDTH, height);
  MOTIFS[theme.motif](ctx, theme, height);

  // Header: circular portrait (birthday/memorial with a photo) or the theme emoji
  if (portrait) {
    const r = PORTRAIT / 2;
    const top = 70;
    ctx.save();
    ctx.shadowColor = 'rgba(0,0,0,0.25)';
    ctx.shadowBlur = 24;
    ctx.fillStyle = '#ffffff';
    ctx.beginPath();
    ctx.arc(CX, top + r, r + 8, 0, Math.PI * 2);
    ctx.fill();
    ctx.restore();
    ctx.save();
    ctx.beginPath();
    ctx.arc(CX, top + r, r, 0, Math.PI * 2);
    ctx.clip();
    drawPhoto(ctx, photo, CX - r, top, PORTRAIT, PORTRAIT);
    ctx.restore();
    ctx.save();
    ctx.strokeStyle = '#ffffff';
    ctx.lineWidth = 10;
    ctx.beginPath();
    ctx.arc(CX, top + r, r + 3, 0, Math.PI * 2);
    ctx.stroke();
    ctx.restore();
  } else {
    centredText(ctx, theme.icon, 140, `120px ${SANS}`, theme.text);
  }

  // Title
  ctx.font = `bold ${size}px ${SERIF}`;
  ctx.fillStyle = theme.text;
  lines.forEach((line, i) => ctx.fillText(line, CX, titleYs[i]));

  // Personal message (optional)
  msgLines.forEach((line, i) => centredText(ctx, line, msgYs[i], msgFont, theme.text));

  // Subtitle
  centredText(ctx, 'Made with Zeus Beats', madeY, `600 34px ${SANS}`, theme.muted);

  // Photo panel (the other themes, when there's a photo)
  if (panelPhoto) {
    const x = CX - PHOTO_PANEL_W / 2;
    ctx.save();
    ctx.shadowColor = 'rgba(0,0,0,0.3)';
    ctx.shadowBlur = 26;
    ctx.shadowOffsetY = 8;
    ctx.fillStyle = '#ffffff';
    roundRect(ctx, x, photoTop, PHOTO_PANEL_W, PHOTO_PANEL_H, 24);
    ctx.fill();
    ctx.restore();
    ctx.save();
    roundRect(ctx, x, photoTop, PHOTO_PANEL_W, PHOTO_PANEL_H, 24);
    ctx.clip();
    drawPhoto(ctx, photo, x, photoTop, PHOTO_PANEL_W, PHOTO_PANEL_H);
    ctx.restore();
  }

  // QR panel — as big as the space allows, never below PANEL_MIN
  const px = CX - panel / 2;
  ctx.save();
  ctx.shadowColor = 'rgba(0,0,0,0.28)';
  ctx.shadowBlur = 30;
  ctx.shadowOffsetY = 8;
  ctx.fillStyle = '#ffffff';
  roundRect(ctx, px, qrTop, panel, panel, 28);
  ctx.fill();
  ctx.restore();
  ctx.imageSmoothingEnabled = false; // keep QR modules crisp when scaled
  const qrSize = panel - PANEL_PAD * 2;
  ctx.drawImage(qrCanvas, px + PANEL_PAD, qrTop + PANEL_PAD, qrSize, qrSize);
  ctx.imageSmoothingEnabled = true;

  // Theme message
  const panelBottom = qrTop + panel;
  centredText(ctx, theme.message, panelBottom + 58, `bold 44px ${SANS}`, theme.messageColor || theme.text);

  // Footer — subtle branding
  const siteY = Math.max(panelBottom + 200, height - 62);
  const brandY = siteY - 46;
  ctx.save();
  ctx.globalAlpha = 0.85;
  ctx.font = `bold 32px ${SANS}`;
  const brandW = ctx.measureText('Zeus Beats').width;
  const logoSize = 52;
  const rowW = (logo ? logoSize + 14 : 0) + brandW;
  const rowX = CX - rowW / 2;
  if (logo) {
    ctx.save();
    ctx.beginPath();
    ctx.arc(rowX + logoSize / 2, brandY, logoSize / 2, 0, Math.PI * 2);
    ctx.clip();
    ctx.drawImage(logo, rowX, brandY - logoSize / 2, logoSize, logoSize);
    ctx.restore();
  }
  ctx.textAlign = 'left';
  ctx.fillStyle = theme.text;
  ctx.fillText('Zeus Beats', rowX + (logo ? logoSize + 14 : 0), brandY);
  ctx.textAlign = 'center';
  centredText(ctx, 'zeusbeats.com', siteY, `26px ${SANS}`, theme.muted);
  ctx.restore();

  return { height };
}
