// Draws the themed QR greeting card straight onto a 2D canvas context. The
// on-screen preview IS this canvas, so the downloaded PNG always matches what
// the user saw (no html2canvas DOM-to-image guesswork with gradients/emoji).
import { PERSONAL_MESSAGE_MAX } from './qrCardThemes.js';

export const CARD_WIDTH = 1080;
export const CARD_HEIGHT = 1440;

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
function inCentre(x, y) {
  return x > 130 && x < CARD_WIDTH - 130 && y > 200 && y < CARD_HEIGHT - 120;
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
  confetti(ctx, theme) {
    const r = rng(11);
    for (let n = 0; n < 160; n++) {
      const x = r() * CARD_WIDTH;
      const y = r() * CARD_HEIGHT;
      if (inCentre(x, y)) continue;
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
  floral(ctx, theme) {
    ctx.save();
    ctx.strokeStyle = theme.accent;
    ctx.lineWidth = 4;
    roundRect(ctx, 34, 34, CARD_WIDTH - 68, CARD_HEIGHT - 68, 18);
    ctx.stroke();
    ctx.lineWidth = 1.5;
    roundRect(ctx, 52, 52, CARD_WIDTH - 104, CARD_HEIGHT - 104, 12);
    ctx.stroke();
    ctx.restore();
    const corners = [[70, 70, 0], [CARD_WIDTH - 70, 70, Math.PI / 2], [CARD_WIDTH - 70, CARD_HEIGHT - 70, Math.PI], [70, CARD_HEIGHT - 70, -Math.PI / 2]];
    for (const [x, y, rot] of corners) {
      for (let i = 0; i < 5; i++) {
        leaf(ctx, x, y, 70, rot + (i * Math.PI) / 10, i % 2 ? 'rgba(201,162,74,0.85)' : 'rgba(150,170,120,0.7)');
      }
      flower(ctx, x, y, 34, theme);
      flower(ctx, x + Math.cos(rot) * 96, y + Math.sin(rot) * 96, 20, theme);
      flower(ctx, x + Math.cos(rot + Math.PI / 2) * 96, y + Math.sin(rot + Math.PI / 2) * 96, 20, theme);
    }
  },
  snow(ctx, theme) {
    ctx.save();
    ctx.fillStyle = theme.band;
    ctx.fillRect(0, 0, CARD_WIDTH, 26);
    ctx.fillRect(0, CARD_HEIGHT - 26, CARD_WIDTH, 26);
    ctx.fillStyle = theme.accent;
    ctx.fillRect(0, 26, CARD_WIDTH, 4);
    ctx.fillRect(0, CARD_HEIGHT - 30, CARD_WIDTH, 4);
    ctx.restore();
    const r = rng(25);
    ctx.save();
    ctx.strokeStyle = '#ffffff';
    ctx.lineCap = 'round';
    for (let n = 0; n < 90; n++) {
      const x = r() * CARD_WIDTH;
      const y = 40 + r() * (CARD_HEIGHT - 80);
      const centre = inCentre(x, y);
      if (centre && n % 4) continue;
      ctx.globalAlpha = centre ? 0.12 : 0.35 + r() * 0.5;
      ctx.lineWidth = 2 + r() * 2;
      snowflake(ctx, x, y, 10 + r() * 22);
    }
    ctx.restore();
  },
  clouds(ctx) {
    const glow = ctx.createRadialGradient(CX, 0, 40, CX, 0, 900);
    glow.addColorStop(0, 'rgba(255,255,255,0.85)');
    glow.addColorStop(1, 'rgba(255,255,255,0)');
    ctx.save();
    ctx.fillStyle = glow;
    ctx.fillRect(0, 0, CARD_WIDTH, CARD_HEIGHT);
    ctx.restore();
    for (const [x, y, w, a] of [[150, 120, 360, 0.55], [930, 210, 400, 0.45], [120, 1270, 420, 0.4], [960, 1330, 380, 0.45], [60, 720, 260, 0.3], [1030, 820, 280, 0.3]]) {
      cloud(ctx, x, y, w, a);
    }
  },
  hearts(ctx, theme) {
    const r = rng(14);
    ctx.save();
    ctx.fillStyle = theme.accent;
    for (let n = 0; n < 70; n++) {
      const x = r() * CARD_WIDTH;
      const y = r() * CARD_HEIGHT;
      if (inCentre(x, y)) continue;
      ctx.globalAlpha = 0.12 + r() * 0.2;
      heart(ctx, x, y, 26 + r() * 46);
    }
    ctx.restore();
  },
  neon(ctx, theme) {
    for (const [x, y, rad, colour] of [[120, 160, 620, theme.glow], [CARD_WIDTH - 80, CARD_HEIGHT - 160, 640, theme.accent]]) {
      const g = ctx.createRadialGradient(x, y, 0, x, y, rad);
      g.addColorStop(0, `${colour}55`);
      g.addColorStop(1, `${colour}00`);
      ctx.save();
      ctx.fillStyle = g;
      ctx.fillRect(0, 0, CARD_WIDTH, CARD_HEIGHT);
      ctx.restore();
    }
    ctx.save();
    ctx.strokeStyle = theme.accent;
    ctx.lineWidth = 3;
    ctx.shadowColor = theme.accent;
    ctx.shadowBlur = 24;
    roundRect(ctx, 32, 32, CARD_WIDTH - 64, CARD_HEIGHT - 64, 28);
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
 * @param ctx  2D context of a CARD_WIDTH × CARD_HEIGHT canvas
 * @param opts.theme           one of CARD_THEMES
 * @param opts.title           song title
 * @param opts.qrCanvas        canvas holding the QR code (drawn scaled)
 * @param opts.logo            loaded Zeus logo image, or null if it failed
 * @param opts.personalMessage optional, blank = skipped
 */
export function drawQrCard(ctx, { theme, title, qrCanvas, logo, personalMessage = '' }) {
  ctx.textAlign = 'center';
  ctx.textBaseline = 'middle';

  const bg = ctx.createLinearGradient(0, 0, 0, CARD_HEIGHT);
  bg.addColorStop(0, theme.bg[0]);
  bg.addColorStop(1, theme.bg[1]);
  ctx.fillStyle = bg;
  ctx.fillRect(0, 0, CARD_WIDTH, CARD_HEIGHT);
  MOTIFS[theme.motif](ctx, theme);

  // Header
  centredText(ctx, theme.icon, 140, `120px ${SANS}`, theme.text);

  // Title
  let y = 240;
  const { size, lines } = layoutTitle(ctx, title || 'Your Song');
  const titleLh = size * 1.1;
  ctx.font = `bold ${size}px ${SERIF}`;
  ctx.fillStyle = theme.text;
  for (const line of lines) {
    ctx.fillText(line, CX, y + titleLh / 2);
    y += titleLh;
  }

  // Personal message (optional)
  const message = String(personalMessage || '').trim().slice(0, PERSONAL_MESSAGE_MAX);
  if (message) {
    y += 20;
    const font = `italic 36px ${SERIF}`;
    ctx.font = font;
    const msgLines = clampLines(ctx, wrapLines(ctx, message, TEXT_WIDTH), 4, TEXT_WIDTH);
    for (const line of msgLines) {
      centredText(ctx, line, y + 23, font, theme.text);
      y += 46;
    }
  }

  // Subtitle
  y += 24;
  centredText(ctx, 'Made with Zeus Beats', y + 18, `600 34px ${SANS}`, theme.muted);
  y += 36;

  // QR panel — as big as the space allows, never below PANEL_MIN
  const qrTop = y + 36;
  const panel = Math.max(PANEL_MIN, Math.min(PANEL_MAX, CARD_HEIGHT - BOTTOM_RESERVE - qrTop));
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
  const siteY = Math.max(panelBottom + 160, CARD_HEIGHT - 62);
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
}
