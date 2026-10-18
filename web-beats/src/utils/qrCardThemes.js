// Themes for the downloadable QR greeting card (SongCard's QR panel). Picked
// automatically from the song's Occasion tag; drawQrCard.js does the drawing.
// `celebration` deliberately shares the General (Zeus-branded) look.

export const PERSONAL_MESSAGE_MAX = 150;

// Optional photo drawn onto the card (client-side only, never uploaded).
export const CARD_PHOTO_TYPES = ['image/jpeg', 'image/png', 'image/webp'];
export const CARD_PHOTO_MAX_BYTES = 5 * 1024 * 1024;

export function validateCardPhoto(file) {
  if (!CARD_PHOTO_TYPES.includes(file?.type)) return 'Please choose a JPG, PNG or WEBP image.';
  if (file.size > CARD_PHOTO_MAX_BYTES) return 'That photo is over 5MB — please choose a smaller one.';
  return null;
}

export const CARD_THEMES = {
  birthday: {
    id: 'birthday',
    photo: 'circle',
    icon: '🎂',
    message: 'Scan to hear your song! 🎂',
    motif: 'confetti',
    bg: ['#ff5fa2', '#ffc94d'],
    text: '#4a0f2e',
    muted: 'rgba(74,15,46,0.75)',
    accent: '#ffffff',
    confetti: ['#ffffff', '#ffd700', '#ff2d7a', '#7a2bff', '#2bd9c9'],
  },
  wedding: {
    id: 'wedding',
    photo: 'panel',
    icon: '💍',
    message: 'Scan to hear your song 💍',
    motif: 'floral',
    bg: ['#fffaf0', '#f1e3c6'],
    text: '#4f3d26',
    muted: 'rgba(79,61,38,0.7)',
    accent: '#c9a24a',
    petal: '#e9c6c0',
  },
  christmas: {
    id: 'christmas',
    photo: 'panel',
    icon: '🎄',
    message: 'Scan to hear your song 🎄',
    motif: 'snow',
    bg: ['#11573a', '#072a1b'],
    text: '#ffffff',
    muted: 'rgba(255,255,255,0.75)',
    accent: '#f2d27a',
    band: '#b3202a',
    messageColor: '#f2d27a',
  },
  memorial: {
    id: 'memorial',
    photo: 'circle',
    icon: '🕊️',
    message: 'A song made in your memory 🕊️',
    motif: 'clouds',
    bg: ['#eef3f8', '#9fb4ca'],
    text: '#2f4054',
    muted: 'rgba(47,64,84,0.72)',
    accent: '#ffffff',
  },
  love: {
    id: 'love',
    photo: 'panel',
    icon: '❤️',
    message: 'Scan to hear your song ❤️',
    motif: 'hearts',
    bg: ['#b3304f', '#4f0919'],
    text: '#ffffff',
    muted: 'rgba(255,255,255,0.78)',
    accent: '#ffd1dc',
  },
  general: {
    id: 'general',
    photo: 'panel',
    icon: '🎵',
    message: 'Scan to hear your song 🎵',
    motif: 'neon',
    bg: ['#2a1050', '#050308'],
    text: '#ffffff',
    muted: 'rgba(255,255,255,0.72)',
    accent: '#16c8ff',
    glow: '#b44cff',
  },
};

const OCCASION_TO_THEME = {
  birthday: 'birthday',
  anniversary: 'wedding',
  christmas: 'christmas',
  memorial: 'memorial',
  love: 'love',
};

export function themeForOccasion(occasion) {
  return CARD_THEMES[OCCASION_TO_THEME[occasion]] || CARD_THEMES.general;
}

export function cardFilename(title, variantId) {
  const slug = String(title || '').toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-+|-+$/g, '');
  return `${slug || `song-${variantId}`}-zeus-card.png`;
}
