import { Link } from 'react-router-dom';

// Zeus Beats' own electric-blue → purple pair (RemixButton.jsx and everywhere
// else in Clips already use this exact gradient — not a new colour).
const CYAN = '#00f0ff';
const PURPLE = '#7c3aed';

/**
 * The "ZEUS CLIPS" wordmark — ZEUS bold white, CLIPS in the brand gradient,
 * per the approved mockups. Shared across the feed, clip page and creator
 * (the three pages the restyle brief names) so all three read as one
 * product, not three slightly different headers.
 */
export function ZeusClipsWordmark({ size = 19, to = '/clips' }) {
  const mark = (
    <span style={{
      fontFamily: "'Orbitron', sans-serif", fontWeight: 900, fontSize: size,
      letterSpacing: '0.01em', whiteSpace: 'nowrap', display: 'inline-flex', gap: 6,
      textShadow: `0 1px 4px rgba(0,0,0,0.9), 0 0 16px ${CYAN}77`,
    }}>
      <span style={{ color: '#fff' }}>ZEUS</span>
      <span style={{
        background: `linear-gradient(90deg, ${CYAN}, ${PURPLE})`,
        WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent', backgroundClip: 'text',
      }}>
        CLIPS
      </span>
    </span>
  );
  if (!to) return mark;
  return <Link to={to} style={{ textDecoration: 'none', display: 'inline-block' }}>{mark}</Link>;
}

/** The small "⚡ AI MADE HUMAN FELT" badge, top-right on every Clips page per the mockups. */
export function ClipsAiBadge() {
  return (
    <div style={{
      display: 'inline-flex', alignItems: 'center', gap: 5, padding: '6px 10px', borderRadius: 8,
      background: 'rgba(10,10,20,0.55)', backdropFilter: 'blur(8px)', WebkitBackdropFilter: 'blur(8px)',
      border: `1px solid ${CYAN}55`, boxShadow: `0 0 14px ${CYAN}22`,
    }}>
      <span style={{ color: CYAN, fontSize: 12, lineHeight: 1 }}>⚡</span>
      <span style={{
        fontSize: 9, fontWeight: 800, letterSpacing: '0.05em', textTransform: 'uppercase',
        color: 'rgba(255,255,255,0.85)', lineHeight: 1.25,
      }}>
        AI MADE<br />HUMAN FELT
      </span>
    </div>
  );
}

/**
 * Pill tab — the "New / Trending" tabs, styled like the mockups' "Following /
 * For You": a dark/transparent fill with a glowing gradient border when
 * active (never a solid gradient fill), plain gray outline when inactive.
 */
export function ClipsPillTab({ active, onClick, children }) {
  return (
    <button
      onClick={onClick}
      style={{
        padding: '7px 22px', borderRadius: 999, fontSize: 13, fontWeight: 700, cursor: 'pointer',
        color: active ? '#fff' : 'rgba(255,255,255,0.55)',
        background: active
          ? `linear-gradient(#0a0a14,#0a0a14) padding-box, linear-gradient(90deg, ${CYAN}, ${PURPLE}) border-box`
          : 'rgba(10,10,20,0.5)',
        border: active ? '1.5px solid transparent' : '1px solid rgba(255,255,255,0.15)',
        boxShadow: active ? `0 0 16px ${CYAN}55` : 'none',
        backdropFilter: 'blur(8px)', WebkitBackdropFilter: 'blur(8px)',
      }}
    >
      {children}
    </button>
  );
}
