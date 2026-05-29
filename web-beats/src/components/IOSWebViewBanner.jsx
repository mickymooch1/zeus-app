export default function IOSWebViewBanner() {
  return (
    <div style={{
      padding: '16px 20px',
      borderRadius: 12,
      background: 'rgba(0,240,255,0.06)',
      border: '1px solid rgba(0,240,255,0.25)',
      marginBottom: 24,
    }}>
      <div style={{ display: 'flex', alignItems: 'flex-start', gap: 12, marginBottom: 14 }}>
        <span style={{ fontSize: 22, flexShrink: 0 }}>🌐</span>
        <div>
          <p style={{ margin: 0, fontWeight: 700, color: '#e2e8f0', fontSize: 14, marginBottom: 4 }}>
            Subscribe or upgrade on the web
          </p>
          <p style={{ margin: 0, color: '#94a3b8', fontSize: 13, lineHeight: 1.6 }}>
            To subscribe or upgrade, visit{' '}
            <strong style={{ color: '#00f0ff' }}>zeusbeats.com</strong>{' '}
            in Safari. Your account and songs are the same everywhere.
          </p>
        </div>
      </div>
      <button
        onClick={() => window.open('https://zeusbeats.com/pricing', '_blank')}
        style={{
          display: 'block',
          width: '100%',
          padding: '14px 20px',
          borderRadius: 10,
          border: 'none',
          background: 'linear-gradient(90deg, #00c8d4, #00f0ff)',
          color: '#000',
          fontWeight: 800,
          fontSize: 15,
          cursor: 'pointer',
          letterSpacing: '0.01em',
          boxShadow: '0 0 18px rgba(0,240,255,0.35)',
        }}
      >
        Subscribe on zeusbeats.com →
      </button>
    </div>
  );
}
