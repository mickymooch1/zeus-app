// One round glass button in the right-side action column (like, remix count,
// share, ⋯) — shared between the feed and the single-clip page so both read
// as the same product. onClick omitted renders a plain (non-interactive)
// stat — used for the remix count, which has nothing to do when tapped here.
export default function ClipActionBtn({ onClick, icon, label, active, activeColor }) {
  const Tag = onClick ? 'button' : 'div';
  return (
    <Tag
      onClick={onClick}
      className="clip-action-btn"
      style={{
        background: 'none', border: 'none', cursor: onClick ? 'pointer' : 'default',
        display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 4, padding: 0,
      }}
    >
      <div style={{
        // Scales down on narrow / zoomed screens (--clip-action-size, index.css).
        width: 'var(--clip-action-size, 44px)', height: 'var(--clip-action-size, 44px)', borderRadius: '50%',
        background: active ? `${activeColor}28` : 'rgba(10,10,20,0.55)',
        backdropFilter: 'blur(8px)', WebkitBackdropFilter: 'blur(8px)',
        border: `1.5px solid ${active ? activeColor : 'rgba(255,255,255,0.22)'}`,
        display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 'clamp(15px, 4.4cqw, 18px)',
        boxShadow: active ? `0 0 20px ${activeColor}66` : 'none',
      }}>
        {icon}
      </div>
      {label && (
        <span className="clip-action-label" style={{
          color: active ? activeColor : 'rgba(255,255,255,0.92)', fontSize: 11, fontWeight: 700, whiteSpace: 'nowrap',
          textShadow: '0 1px 2px rgba(0,0,0,0.95), 0 1px 5px rgba(0,0,0,0.8)',
        }}>
          {label}
        </span>
      )}
    </Tag>
  );
}
