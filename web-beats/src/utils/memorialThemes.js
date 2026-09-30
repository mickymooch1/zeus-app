// Background presets for the memorial page (2026-09-30). The backend stores
// only the id (song_variants.page_theme; NULL = "classic") and validates it
// against the same two ids — what each preset looks like lives here and in
// MemorialPage.jsx / HeavenlyBackdrop.jsx (artwork: scripts/generate_heavenly_bg.py).

export const PAGE_THEMES = [
  {
    id: 'classic',
    label: 'Classic',
    hint: 'Warm cream — dark on dark-mode devices',
    swatch: 'linear-gradient(135deg, #f7f2ea 0 50%, #211f1c 50% 100%)',
  },
  {
    id: 'heavenly',
    label: 'Heavenly',
    hint: 'A stairway through clouds into golden light',
    swatch: 'linear-gradient(180deg, #fff6d8 0%, #ffe3a6 38%, #f7d9c8 66%, #cfdcf2 100%)',
  },
];

const IDS = new Set(PAGE_THEMES.map((t) => t.id));

// Anything unknown (older API, a preset removed later) falls back to classic
// so a memorial page can never render unstyled.
export function normalizeTheme(value) {
  return IDS.has(value) ? value : 'classic';
}

// WaveSurfer colours. Heavenly is always a light scene, so it ignores the
// device's dark-mode setting; classic keeps following it, as before.
export function waveColors(theme, prefersDark) {
  if (normalizeTheme(theme) === 'heavenly') {
    return { waveColor: 'rgba(67,54,42,0.22)', progressColor: '#b8862f' };
  }
  return prefersDark
    ? { waveColor: 'rgba(237,231,222,0.25)', progressColor: '#d98a6f' }
    : { waveColor: 'rgba(43,38,34,0.18)', progressColor: '#a8593f' };
}
