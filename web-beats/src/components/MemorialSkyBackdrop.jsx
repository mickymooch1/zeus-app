import sky from '../assets/memorial/memorial-sky-portrait-v6.webp';

/**
 * Photographic sky background for the memorial landing page (/memorials) and
 * the create wizard (/memorials/create) only — a stairway of glowing steps
 * rising into golden light (Flux-generated, 2026-10-16). The public
 * /memorial/:token page keeps its own owner-selectable HeavenlyBackdrop.
 *
 * Fixed and covering the viewport, it sits over the app-wide starfield
 * (SpaceBackground: same z-index -1, but rendered earlier in the DOM) without
 * touching it, so every other page keeps the starfield. A position: fixed
 * layer is used rather than background-attachment: fixed, which iOS Safari
 * ignores.
 *
 * The overlay is darkest in a centre column, because the bright stairway runs
 * straight up the middle exactly where the heading, form and buttons sit, and
 * lighter at the edges so the clouds and light still show through.
 */

const CSS = `
.zb-memorial-sky, .zb-memorial-sky-shade {
  position: fixed; inset: 0; z-index: -1; pointer-events: none;
}
.zb-memorial-sky {
  background-color: #1a1408;
  background-image: url(${sky});
  background-size: cover; background-position: center; background-repeat: no-repeat;
}
.zb-memorial-sky-shade {
  background:
    radial-gradient(ellipse 45% 40% at 50% 22%, rgba(0,0,0,0.30) 0%, rgba(0,0,0,0) 100%),
    linear-gradient(to right, rgba(0,0,0,0) 0%, rgba(0,0,0,0.38) 32%, rgba(0,0,0,0.38) 68%, rgba(0,0,0,0) 100%),
    linear-gradient(to bottom, rgba(0,0,0,0.15) 0%, rgba(0,0,0,0) 35%, rgba(0,0,0,0.20) 100%);
}
@media (max-width: 640px) {
  /* On a phone the content spans the full width, so shade it evenly. */
  .zb-memorial-sky-shade {
    background:
      radial-gradient(ellipse 90% 45% at 50% 38%, rgba(0,0,0,0.38) 0%, rgba(0,0,0,0) 100%),
      linear-gradient(to bottom, rgba(0,0,0,0.40) 0%, rgba(0,0,0,0.42) 50%, rgba(0,0,0,0.55) 100%);
  }
}
`;

export default function MemorialSkyBackdrop() {
  return (
    <>
      <style>{CSS}</style>
      <div className="zb-memorial-sky" aria-hidden="true" />
      <div className="zb-memorial-sky-shade" aria-hidden="true" />
    </>
  );
}
