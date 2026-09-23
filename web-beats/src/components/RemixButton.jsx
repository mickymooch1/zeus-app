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

export default function RemixButton({ onClick, count, size = 'large', label, disabled, style }) {
  const large = size === 'large';
  return (
    <button
      onClick={onClick}
      disabled={disabled}
      style={{
        display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 8,
        width: large ? '100%' : 'auto',
        padding: large ? '17px 24px' : '10px 18px',
        borderRadius: 999, // pill
        border: 'none',
        background: `linear-gradient(90deg, ${CYAN}, ${PURPLE})`,
        color: '#000',
        fontWeight: 900,
        fontSize: large ? 16 : 13,
        fontFamily: "'Orbitron', sans-serif",
        cursor: disabled ? 'default' : 'pointer',
        opacity: disabled ? 0.7 : 1,
        letterSpacing: '0.01em',
        boxShadow: `0 0 ${large ? 28 : 16}px ${CYAN}88, 0 0 ${large ? 46 : 26}px ${PURPLE}55`,
        ...style,
      }}
    >
      <WaveformIcon size={large ? 16 : 13} />
      <span>{label || `⚡ Remix This Sound${count > 0 ? ` · ${count}` : ''}`}</span>
    </button>
  );
}
