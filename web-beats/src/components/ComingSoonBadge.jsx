// Small contrasting badge for a feature that's visible but not yet tappable.
// Deliberately colourful, not greyed-out — the option should still read as
// "part of the app", just not live yet.
export default function ComingSoonBadge({ style }) {
  return (
    <span
      style={{
        position: 'absolute', top: -8, right: -6,
        background: 'linear-gradient(135deg, #a78bfa 0%, #7c3aed 100%)',
        color: '#fff', fontSize: 10, fontWeight: 800,
        letterSpacing: '0.03em', textTransform: 'uppercase',
        padding: '4px 9px', borderRadius: 999,
        boxShadow: '0 3px 10px rgba(124,58,237,0.5)',
        whiteSpace: 'nowrap',
        ...style,
      }}
    >
      Coming Soon
    </span>
  );
}
