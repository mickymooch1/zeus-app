import { Link } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import { gLabel } from '../utils/genres';
import { beatsHomePath } from '../utils/clipsChrome';

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
// `to` omitted: the logo leads back to Zeus Beats (song library, or home for a
// visitor) — Clips' way out of itself. `to={null}` renders it unlinked.
export function ZeusClipsWordmark({ size = 19, to }) {
  const { user } = useAuth();
  const dest = to === undefined ? beatsHomePath(user) : to;
  const mark = (
    <span style={{
      fontFamily: "'Orbitron', sans-serif", fontWeight: 900, fontSize: size,
      letterSpacing: '0.01em', whiteSpace: 'nowrap', display: 'inline-flex', gap: 6,
    }}>
      <span style={{ color: '#fff', textShadow: `0 1px 4px rgba(0,0,0,0.9), 0 0 16px ${CYAN}77` }}>ZEUS</span>
      {/* No text-shadow here: with a transparent text fill the shadow shows
          THROUGH the letters and darkens the gradient. The glow comes from
          drop-shadow instead, which sits behind the painted gradient. Colours
          are lighter tints of the brand pair so CLIPS reads on pure black. */}
      <span style={{
        background: 'linear-gradient(90deg, #5ee7ff, #8b9dff 50%, #c77dff)',
        WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent', backgroundClip: 'text',
        filter: `drop-shadow(0 0 6px ${CYAN}99) drop-shadow(0 0 12px ${PURPLE}aa)`,
      }}>
        CLIPS
      </span>
    </span>
  );
  if (!dest) return mark;
  return (
    <Link to={dest} aria-label="Zeus Beats" style={{ textDecoration: 'none', display: 'inline-block' }}>{mark}</Link>
  );
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

/**
 * Genre pill shown above the @username. Near-solid dark fill (not a
 * translucent tint) so it stays readable over light cover images. Takes the
 * raw genre_tag and shows its display name ("soulrnb" → "Soul R&B", blends as
 * "Synth Funk × Soul R&B").
 */
export function ClipGenrePill({ genre, style }) {
  if (!genre) return null;
  return (
    <span style={{
      display: 'inline-block', padding: '3px 11px', borderRadius: 20, fontSize: 11,
      fontWeight: 700, letterSpacing: '0.02em',
      background: 'rgba(8,8,18,0.85)', border: `1px solid ${CYAN}88`,
      boxShadow: `0 0 10px ${CYAN}33`, color: '#7ff6ff',
      backdropFilter: 'blur(6px)', WebkitBackdropFilter: 'blur(6px)',
      ...style,
    }}>
      {gLabel(genre)}
    </span>
  );
}

/** Small "← Zeus Beats" link, top-left on Clips pages — the way back to the main app. */
export function BackToBeatsLink({ style }) {
  const { user } = useAuth();
  return (
    <Link
      to={beatsHomePath(user)}
      style={{
        color: 'rgba(255,255,255,0.7)', textDecoration: 'none', fontSize: 12, fontWeight: 700,
        whiteSpace: 'nowrap', textShadow: '0 1px 3px rgba(0,0,0,0.85)', ...style,
      }}
    >
      ← Zeus Beats
    </Link>
  );
}
