// Friendly "not yet" modal for features that are visible but not tappable.
// Reuses the same fixed-overlay + kids-card convention as ParentPINGate.jsx.
export default function ComingSoonModal({ emoji = '🎵', message, onClose }) {
  return (
    <div
      onClick={onClose}
      style={{
        position: 'fixed', inset: 0, zIndex: 9999,
        background: 'rgba(26,43,74,0.55)', backdropFilter: 'blur(6px)',
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        padding: 16,
      }}
    >
      <div
        onClick={(e) => e.stopPropagation()}
        className="kids-card"
        style={{ maxWidth: 340, width: '100%', textAlign: 'center' }}
      >
        <div style={{ fontSize: 40, marginBottom: 8 }}>{emoji}</div>
        <p style={{ margin: '0 0 20px', fontSize: 16, fontWeight: 700, color: '#1a2b4a', lineHeight: 1.4 }}>
          {message}
        </p>
        <button
          onClick={onClose}
          className="kids-btn kids-btn-primary"
          style={{ width: '100%', minHeight: 56, fontSize: 16 }}
        >
          Got it! 👍
        </button>
      </div>
    </div>
  );
}
