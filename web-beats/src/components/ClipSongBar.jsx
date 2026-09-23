// The "sound" attribution strip at the bottom of a clip — cover art + song title,
// dark glass with a glow border, per the approved feed mockup.
const CYAN = '#00f0ff';

export default function ClipSongBar({ coverUrl, title }) {
  return (
    <div style={{
      display: 'flex', alignItems: 'center', gap: 10,
      padding: '7px 14px 7px 7px',
      borderRadius: 999,
      background: 'rgba(10,10,20,0.55)',
      backdropFilter: 'blur(10px)',
      WebkitBackdropFilter: 'blur(10px)',
      border: `1px solid ${CYAN}33`,
      maxWidth: 'fit-content',
    }}>
      <div style={{
        width: 30, height: 30, borderRadius: '50%', flexShrink: 0, overflow: 'hidden',
        background: '#1a0a2e', border: `1px solid ${CYAN}55`,
        display: 'flex', alignItems: 'center', justifyContent: 'center',
      }}>
        {coverUrl ? (
          <img src={coverUrl} alt="" style={{ width: '100%', height: '100%', objectFit: 'cover' }} />
        ) : (
          <span style={{ fontSize: 13 }}>🎵</span>
        )}
      </div>
      <span style={{
        fontSize: 12, fontWeight: 600, color: 'rgba(255,255,255,0.85)',
        maxWidth: 180, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
      }}>
        {title || 'Untitled'}
      </span>
    </div>
  );
}
