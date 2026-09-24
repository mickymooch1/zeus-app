// The full-width "sound" bar pinned at the bottom of a clip (feed + clip
// page) — spinning-disc cover art, title, "@artist · AI Original", and a
// "Use Sound" button that starts the same remix flow as the big Remix
// button. A thin progress bar tracks the clip's playback position underneath
// it, per the approved mockups. Every text in it stays on one line (ellipsis) at
// any text size; on short screens the subtitle and disc drop out (index.css).
const CYAN = '#00f0ff';
const PURPLE = '#7c3aed';

export default function ClipSongBar({ coverUrl, title, artistName, spinning, onUseSound, progressBarRef }) {
  return (
    <div className="clip-songbar" style={{ flex: 'none', minWidth: 0 }}>
      <div style={{
        display: 'flex', alignItems: 'center', gap: 'clamp(6px, 2.4cqw, 10px)', padding: 8, minWidth: 0,
        borderRadius: 14, background: 'rgba(10,10,20,0.62)',
        backdropFilter: 'blur(10px)', WebkitBackdropFilter: 'blur(10px)',
        border: `1px solid ${CYAN}33`, boxShadow: '0 4px 18px rgba(0,0,0,0.5)',
      }}>
        <div className="clip-songbar-disc" style={{
          width: 38, height: 38, borderRadius: '50%', flexShrink: 0, overflow: 'hidden',
          background: '#15121f', border: '2px solid rgba(255,255,255,0.18)',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          animation: 'clipDiscSpin 6s linear infinite',
          animationPlayState: spinning ? 'running' : 'paused',
        }}>
          {coverUrl ? (
            <img src={coverUrl} alt="" style={{ width: '100%', height: '100%', objectFit: 'cover' }} />
          ) : (
            <span style={{ fontSize: 14 }}>🎵</span>
          )}
        </div>

        <div style={{ flex: 1, minWidth: 0 }}>
          <p style={{
            margin: 0, fontSize: 'clamp(12px, 3.6cqw, 13px)', fontWeight: 700, color: '#fff',
            whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis',
          }}>
            {title || 'Untitled'}
          </p>
          <p className="clip-songbar-sub clip-oneline" style={{ margin: 0, fontSize: 11, color: 'rgba(255,255,255,0.55)' }}>
            {artistName || 'Zeus Beats'} · AI Original
          </p>
        </div>

        {/* Visualiser — moves only while the clip's audio is playing. */}
        <span className={`clip-viz${spinning ? '' : ' clip-viz--paused'}`} aria-hidden="true">
          <span /><span /><span /><span /><span />
        </span>

        <button
          onClick={onUseSound}
          className="clip-songbar-use"
          style={{
            flexShrink: 0, padding: '7px clamp(9px, 3.4cqw, 14px)', borderRadius: 999, fontSize: 'clamp(11px, 3.3cqw, 12px)', fontWeight: 700,
            whiteSpace: 'nowrap',
            cursor: onUseSound ? 'pointer' : 'default', color: '#fff',
            background: 'rgba(255,255,255,0.08)', border: '1px solid rgba(255,255,255,0.22)',
          }}
        >
          Use Sound ›
        </button>
      </div>

      {/* Playback progress — set imperatively (ref.style.width) by the parent's
          existing timeupdate handler, never via React state, so it updates
          smoothly without a re-render on every tick. */}
      <div style={{ height: 3, borderRadius: 2, background: 'rgba(255,255,255,0.15)', marginTop: 6, overflow: 'hidden' }}>
        <div
          ref={progressBarRef}
          style={{ height: '100%', width: '0%', background: `linear-gradient(90deg, ${CYAN}, ${PURPLE})` }}
        />
      </div>

      <style>{'@keyframes clipDiscSpin { to { transform: rotate(360deg); } }'}</style>
    </div>
  );
}
