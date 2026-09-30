// Background presets for the memorial page (2026-09-30). The backend stores
// only the id (song_variants.page_theme; NULL = "classic") and validates it
// against the same two ids — what each preset looks like lives here and in
// MemorialPage.jsx / HeavenlyBackdrop.jsx.

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

// The stairway's steps, bottom (wide, near) to top (narrow, far), in the
// backdrop's 1600×1600 viewBox, centred on x=800. They sit in the top of the
// scene so they show above the memorial card. Pure geometry, unit-tested.
export function stairSteps(count = 14) {
  const steps = [];
  for (let i = 0; i < count; i++) {
    const t0 = i / count;
    const t1 = (i + 1) / count;
    const y = (t) => 680 - 418 * (1 - Math.pow(1 - t, 1.55)); // rises fast near, slow far
    const half = (t) => 280 - 222 * Math.pow(t, 0.82);        // narrows toward the light
    steps.push({ yBottom: y(t0), yTop: y(t1), halfBottom: half(t0), halfTop: half(t1), depth: t0 });
  }
  return steps;
}
