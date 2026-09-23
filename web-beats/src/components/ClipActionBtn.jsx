// One round glass button in the right-side action column (like, remix count,
// share, ⋯) — shared between the feed and the single-clip page so both read
// as the same product. onClick omitted renders a plain (non-interactive)
// stat — used for the remix count, which has nothing to do when tapped here.
export default function ClipActionBtn({ onClick, icon, label, active, activeColor }) {
  const Tag = onClick ? 'button' : 'div';
  return (
    <Tag
      onClick={onClick}
      style={{
        background: 'none', border: 'none', cursor: onClick ? 'pointer' : 'default',
        display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 4, padding: 0,
      }}
    >
      <div style={{
        width: 44, height: 44, borderRadius: '50%',
        background: active ? `${activeColor}28` : 'rgba(10,10,20,0.55)',
        backdropFilter: 'blur(8px)', WebkitBackdropFilter: 'blur(8px)',
        border: `1.5px solid ${active ? activeColor : 'rgba(255,255,255,0.22)'}`,
        display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 18,
        boxShadow: active ? `0 0 20px ${activeColor}66` : 'none',
      }}>
        {icon}
      </div>
      {label && (
        <span style={{
          color: active ? activeColor : 'rgba(255,255,255,0.92)', fontSize: 11, fontWeight: 700,
          textShadow: '0 1px 2px rgba(0,0,0,0.95), 0 1px 5px rgba(0,0,0,0.8)',
        }}>
          {label}
        </span>
      )}
    </Tag>
  );
}
