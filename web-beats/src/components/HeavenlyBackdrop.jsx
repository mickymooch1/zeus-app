import { stairSteps } from '../utils/memorialThemes';

/**
 * "Heavenly" memorial-page background (2026-09-30): a stairway rising through
 * clouds into warm golden light, with small floral touches. Original artwork
 * drawn entirely in SVG — no image file, no stock or third-party asset — so
 * there is nothing to license and nothing to load.
 *
 * Composition: the light and the stairway sit in the TOP of the scene and the
 * SVG is anchored to the top of the viewport (xMidYMin slice), so on any
 * screen shape they show above the memorial card, which starts lower down
 * (see .zb-theme-heavenly .zb-share-content in MemorialPage) — the stairs
 * appear to rise from the card into the light. The corner bouquets are
 * separate so they stay in the bottom corners at any aspect ratio; on narrow
 * screens the card covers those corners, so FloralDivider carries the floral
 * touch inside the card instead.
 *
 * Fixed behind the page content (the page sets `isolation: isolate`, so
 * z-index -1 sits above the page's own background colour but below its
 * children). Purely decorative: aria-hidden, no pointer events. The slow
 * cloud drift and glow pulse stop under prefers-reduced-motion.
 */

const CX = 800;
const LIGHT_Y = 190;

const CSS = `
.zb-heavenly { position: fixed; inset: 0; z-index: -1; pointer-events: none; overflow: hidden; }
.zb-heavenly > svg.scene { width: 100%; height: 100%; display: block; }
.zb-heavenly .bouquet { position: absolute; bottom: 0; width: min(24vw, 250px); height: auto; display: none; }
.zb-heavenly .bouquet.left { left: 0; }
.zb-heavenly .bouquet.right { right: 0; transform: scaleX(-1); }
@media (min-width: 760px) { .zb-heavenly .bouquet { display: block; } }
@keyframes zbCloudDriftA { from { transform: translateX(-16px); } to { transform: translateX(16px); } }
@keyframes zbCloudDriftB { from { transform: translateX(14px); } to { transform: translateX(-14px); } }
@keyframes zbGlowPulse { from { opacity: 0.84; } to { opacity: 1; } }
.zb-heavenly .drift-a { animation: zbCloudDriftA 46s ease-in-out infinite alternate; }
.zb-heavenly .drift-b { animation: zbCloudDriftB 58s ease-in-out infinite alternate; }
.zb-heavenly .glow { animation: zbGlowPulse 9s ease-in-out infinite alternate; }
@media (prefers-reduced-motion: reduce) {
  .zb-heavenly .drift-a, .zb-heavenly .drift-b, .zb-heavenly .glow { animation: none; }
}
`;

// A cloud bank: overlapping soft ellipses. [cx, cy, rx, ry]
function Cloud({ puffs, opacity = 0.9 }) {
  return (
    <g opacity={opacity} fill="#ffffff">
      {puffs.map(([cx, cy, rx, ry], i) => <ellipse key={i} cx={cx} cy={cy} rx={rx} ry={ry} />)}
    </g>
  );
}

// A small five-petal flower with a golden centre.
function Flower({ x, y, r = 16, petal = '#f7cfd6', rotate = 0 }) {
  return (
    <g transform={`translate(${x} ${y}) rotate(${rotate})`}>
      {[0, 72, 144, 216, 288].map((a) => (
        <ellipse key={a} cx="0" cy={-r * 0.78} rx={r * 0.46} ry={r * 0.78} fill={petal} stroke="rgba(190,140,120,0.35)" strokeWidth="0.8" transform={`rotate(${a})`} />
      ))}
      <circle r={r * 0.3} fill="#e2a93c" />
    </g>
  );
}

function Leaf({ x, y, rotate, len = 46, fill = '#a9c79b' }) {
  return (
    <path
      transform={`translate(${x} ${y}) rotate(${rotate})`}
      d={`M0 0 C ${len * 0.3} ${-len * 0.34}, ${len * 0.72} ${-len * 0.3}, ${len} 0 C ${len * 0.72} ${len * 0.3}, ${len * 0.3} ${len * 0.34}, 0 0 Z`}
      fill={fill}
    />
  );
}

// Bottom-left corner bouquet (mirrored with CSS for the right corner).
function Bouquet({ side }) {
  return (
    <svg className={`bouquet ${side}`} viewBox="0 0 260 220" xmlns="http://www.w3.org/2000/svg">
      <Leaf x={20} y={200} rotate={-62} len={86} />
      <Leaf x={40} y={210} rotate={-34} len={104} fill="#b9d3ac" />
      <Leaf x={70} y={214} rotate={-14} len={92} />
      <Leaf x={10} y={170} rotate={-84} len={70} fill="#b9d3ac" />
      <Flower x={62} y={128} r={30} />
      <Flower x={128} y={168} r={24} petal="#fff1dc" rotate={18} />
      <Flower x={30} y={84} r={20} petal="#fbdcc2" rotate={36} />
      <Flower x={104} y={92} r={17} rotate={10} />
      <Flower x={180} y={196} r={16} petal="#fff1dc" rotate={-12} />
      <Flower x={18} y={184} r={18} petal="#fbdcc2" rotate={50} />
    </svg>
  );
}

/** A small sprig–flower–sprig divider, shown inside the card on the Heavenly theme. */
export function FloralDivider() {
  return (
    <svg aria-hidden="true" viewBox="0 0 220 36" width="176" height="29" style={{ display: 'block', margin: '2px auto 14px' }} xmlns="http://www.w3.org/2000/svg">
      <path d="M8 18 H84 M136 18 H212" stroke="#c9a662" strokeWidth="1.2" strokeLinecap="round" />
      <Leaf x={86} y={18} rotate={200} len={26} />
      <Leaf x={86} y={18} rotate={160} len={26} fill="#b9d3ac" />
      <Leaf x={134} y={18} rotate={-20} len={26} />
      <Leaf x={134} y={18} rotate={20} len={26} fill="#b9d3ac" />
      <Flower x={110} y={18} r={13} />
      <Flower x={58} y={18} r={6} petal="#fff1dc" />
      <Flower x={162} y={18} r={6} petal="#fff1dc" />
    </svg>
  );
}

export default function HeavenlyBackdrop() {
  const steps = stairSteps();
  const rays = [-42, -28, -14, 0, 14, 28, 42];

  return (
    <div className="zb-heavenly" aria-hidden="true">
      <style>{CSS}</style>
      <svg className="scene" viewBox="0 0 1600 1600" preserveAspectRatio="xMidYMin slice" xmlns="http://www.w3.org/2000/svg">
        <defs>
          <linearGradient id="zbhSky" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0" stopColor="#fff4d2" />
            <stop offset="0.13" stopColor="#ffdf9a" />
            <stop offset="0.30" stopColor="#f9cfae" />
            <stop offset="0.50" stopColor="#c9d8f2" />
            <stop offset="1" stopColor="#a9bde4" />
          </linearGradient>
          <radialGradient id="zbhGlow" cx="0.5" cy="0.5" r="0.5">
            <stop offset="0" stopColor="#ffffff" stopOpacity="1" />
            <stop offset="0.22" stopColor="#fff6cf" stopOpacity="0.96" />
            <stop offset="0.55" stopColor="#ffd884" stopOpacity="0.45" />
            <stop offset="1" stopColor="#ffd884" stopOpacity="0" />
          </radialGradient>
          <linearGradient id="zbhRay" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0" stopColor="#fffdf0" stopOpacity="0.6" />
            <stop offset="1" stopColor="#fffdf0" stopOpacity="0" />
          </linearGradient>
          <linearGradient id="zbhTread" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0" stopColor="#fffdf4" />
            <stop offset="1" stopColor="#ffefc6" />
          </linearGradient>
          <filter id="zbhSoft" x="-20%" y="-20%" width="140%" height="140%"><feGaussianBlur stdDeviation="11" /></filter>
          <filter id="zbhSofter" x="-20%" y="-20%" width="140%" height="140%"><feGaussianBlur stdDeviation="20" /></filter>
          <filter id="zbhHaze" x="-20%" y="-20%" width="140%" height="140%"><feGaussianBlur stdDeviation="6" /></filter>
        </defs>

        <rect width="1600" height="1600" fill="url(#zbhSky)" />

        {/* The light the stairway leads to, and its rays. */}
        <g className="glow">
          <circle cx={CX} cy={LIGHT_Y} r="640" fill="url(#zbhGlow)" />
          <g filter="url(#zbhHaze)">
            {rays.map((deg) => (
              <polygon key={deg} points={`${CX - 12},${LIGHT_Y} ${CX + 12},${LIGHT_Y} ${CX + 78},930 ${CX - 78},930`}
                       fill="url(#zbhRay)" transform={`rotate(${deg} ${CX} ${LIGHT_Y})`} />
            ))}
          </g>
        </g>

        {/* Far clouds, behind the stairway. */}
        <g filter="url(#zbhSofter)" className="drift-b">
          <Cloud opacity={0.8} puffs={[[380, 330, 250, 66], [560, 300, 150, 52], [200, 380, 200, 60]]} />
          <Cloud opacity={0.8} puffs={[[1220, 320, 250, 66], [1040, 295, 150, 52], [1400, 375, 200, 60]]} />
        </g>

        {/* A soft arch of light at the top of the stairs. */}
        <path d={`M ${CX - 58} 262 L ${CX - 58} 170 A 58 58 0 0 1 ${CX + 58} 170 L ${CX + 58} 262 Z`}
              fill="#ffffff" opacity="0.9" filter="url(#zbhHaze)" />

        {/* The stairway: far steps drawn first, each a lit tread over a shaded riser. */}
        <g>
          {[...steps].reverse().map((s, i) => {
            const rise = (s.yBottom - s.yTop) * 0.46;
            return (
              <g key={i} opacity={1 - s.depth * 0.4}>
                <polygon
                  points={`${CX - s.halfBottom},${s.yBottom} ${CX + s.halfBottom},${s.yBottom} ${CX + s.halfBottom},${s.yBottom - rise} ${CX - s.halfBottom},${s.yBottom - rise}`}
                  fill="#e6c887"
                />
                <polygon
                  points={`${CX - s.halfBottom},${s.yBottom - rise} ${CX + s.halfBottom},${s.yBottom - rise} ${CX + s.halfTop},${s.yTop} ${CX - s.halfTop},${s.yTop}`}
                  fill="url(#zbhTread)"
                />
              </g>
            );
          })}
        </g>

        {/* Clouds the stairway rises through — they soften its edges. */}
        <g filter="url(#zbhSoft)" className="drift-a">
          {/* The foot of the stairway dissolves into cloud, so no hard step edge
              ever shows beside the card, whatever the screen width. */}
          <Cloud opacity={1} puffs={[[800, 690, 470, 62], [560, 660, 190, 56], [1040, 660, 190, 56]]} />
          <Cloud opacity={0.95} puffs={[[470, 560, 190, 62], [330, 600, 200, 70], [600, 610, 110, 44]]} />
          <Cloud opacity={0.95} puffs={[[1130, 550, 190, 62], [1270, 595, 200, 70], [1000, 605, 110, 44]]} />
          <Cloud opacity={0.85} puffs={[[620, 430, 110, 36], [540, 455, 110, 36]]} />
          <Cloud opacity={0.85} puffs={[[980, 425, 110, 36], [1060, 450, 110, 36]]} />
        </g>
        <g filter="url(#zbhSoft)" className="drift-b">
          <Cloud opacity={0.97} puffs={[[260, 800, 330, 96], [560, 850, 260, 84], [60, 880, 260, 100]]} />
          <Cloud opacity={0.97} puffs={[[1340, 790, 330, 96], [1040, 850, 260, 84], [1540, 880, 260, 100]]} />
          <Cloud opacity={0.9} puffs={[[800, 760, 330, 70]]} />
        </g>
        <g filter="url(#zbhSofter)" className="drift-a">
          <Cloud opacity={0.7} puffs={[[240, 1150, 300, 80], [520, 1200, 220, 66]]} />
          <Cloud opacity={0.7} puffs={[[1380, 1130, 300, 80], [1090, 1190, 220, 66]]} />
          <Cloud opacity={0.75} puffs={[[420, 1480, 380, 90], [1180, 1500, 380, 90], [800, 1560, 420, 80]]} />
        </g>
      </svg>

      <Bouquet side="left" />
      <Bouquet side="right" />
    </div>
  );
}
