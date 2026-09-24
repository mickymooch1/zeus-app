// The "⚡ Remix This Sound" pill — same style everywhere a clip can be remixed
// (feed, clip detail, remix confirm), per the approved mockups: glowing pill,
// electric-blue → purple gradient (Zeus Beats' own #00f0ff → #7c3aed, already
// used for the logo/NowPlayingBar/PlaylistPage — not a new colour), waveform icon.
const CYAN = '#00f0ff';
const PURPLE = '#7c3aed';

function WaveformIcon({ size = 16 }) {
  const bars = [0.4, 0.9, 0.55, 1, 0.7, 0.45];
  return (
    <svg width={size * 1.3} height={size} viewBox="0 0 26 20" fill="none" aria-hidden="true">
      {bars.map((h, i) => (
        <rect
          key={i}
          x={i * 4.4}
          y={(20 - 20 * h) / 2}
          width="2.6"
          height={20 * h}
          rx="1.3"
          fill="#000"
        />
      ))}
    </svg>
  );
}

// Deliberately never carries a count in its own label — the remix count is its
// own dedicated stat next to like/share (feed: the right-side action column;
// clip page: the pill row above this button), so this stays a clean, constant
// call to action.
export default function RemixButton({ onClick, size = 'large', label, disabled, style }) {
  const large = size === 'large';
  return (
    <button
      onClick={onClick}
      disabled={disabled}
      className="remix-btn"
      style={{
        display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 8,
        width: large ? '100%' : 'auto', minWidth: 0, flex: 'none',
        // Always one line: the label shrinks (clamp) and, at the very narrowest,
        // ellipsises — it never wraps (2026-09-24 iPhone large-text bug).
        padding: large ? 'clamp(11px, 2.4cqh, 17px) clamp(14px, 5cqw, 24px)' : '10px 18px',
        borderRadius: 999, // pill
        border: 'none',
        background: `linear-gradient(90deg, ${CYAN}, ${PURPLE})`,
        color: '#000',
        fontWeight: 900,
        fontSize: large ? 'clamp(12px, 4.3cqw, 16px)' : 13,
        fontFamily: "'Orbitron', sans-serif",
        cursor: disabled ? 'default' : 'pointer',
        opacity: disabled ? 0.7 : 1,
        letterSpacing: '0.01em',
        boxShadow: `0 0 ${large ? 28 : 16}px ${CYAN}88, 0 0 ${large ? 46 : 26}px ${PURPLE}55`,
        ...style,
      }}
    >
      <WaveformIcon size={large ? 16 : 13} />
      <span style={{ whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis', minWidth: 0 }}>
        {label || '⚡ Remix This Sound'}
      </span>
    </button>
  );
}
