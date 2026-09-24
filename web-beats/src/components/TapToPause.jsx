import { useState } from 'react';

const CYAN = '#00f0ff';

function Icon({ kind }) {
  return kind === 'pause' ? (
    <svg width="30" height="30" viewBox="0 0 24 24" fill="#fff" aria-hidden="true">
      <rect x="6" y="5" width="4" height="14" rx="1" /><rect x="14" y="5" width="4" height="14" rx="1" />
    </svg>
  ) : (
    <svg width="32" height="32" viewBox="0 0 24 24" fill="#fff" aria-hidden="true"><path d="M8 5.5v13l11-6.5z" /></svg>
  );
}

const circle = {
  position: 'absolute', width: 'clamp(52px, 18cqmin, 76px)', height: 'clamp(52px, 18cqmin, 76px)', borderRadius: '50%', pointerEvents: 'none',
  display: 'flex', alignItems: 'center', justifyContent: 'center',
  background: 'rgba(0,0,0,0.45)', border: `2px solid ${CYAN}aa`,
  boxShadow: `0 0 24px ${CYAN}55`, backdropFilter: 'blur(4px)', WebkitBackdropFilter: 'blur(4px)',
};

/**
 * Tap the picture/video to pause or play (Clips feed, clip page, Discover).
 * A layer over the picture box that sits ABOVE the visual but BELOW every control — the
 * action buttons, caption, song bar, tabs and nav all have a higher z-index, so
 * a tap on them never reaches this. Each tap flashes a big pause/play icon at
 * `center` that fades over ~0.8s; while paused a play icon stays up.
 */
// Centred in its box — it's placed inside the layout's picture box (.clip-picture).
const CENTER = { top: '50%', left: '50%' };

export default function TapToPause({ paused, onToggle, center = CENTER, zIndex = 5 }) {
  const [flash, setFlash] = useState(null); // { key, kind }
  const toggle = () => {
    setFlash({ key: Date.now(), kind: paused ? 'play' : 'pause' });
    onToggle();
  };
  return (
    <div
      role="button"
      tabIndex={0}
      aria-label={paused ? 'Play' : 'Pause'}
      aria-pressed={!paused}
      onClick={toggle}
      onKeyDown={e => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); toggle(); } }}
      style={{ position: 'absolute', inset: 0, zIndex, cursor: 'pointer', WebkitTapHighlightColor: 'transparent', outline: 'none' }}
    >
      {paused && !flash && (
        <div data-testid="paused-icon" style={{ ...circle, ...center, transform: 'translate(-50%, -50%)' }}>
          <Icon kind="play" />
        </div>
      )}
      {flash && (
        <div key={flash.key} className="tap-flash" onAnimationEnd={() => setFlash(null)} style={{ ...circle, ...center }}>
          <Icon kind={flash.kind} />
        </div>
      )}
    </div>
  );
}
