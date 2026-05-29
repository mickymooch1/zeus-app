export default function IOSWebViewBanner() {
  return (
    <div style={{
      padding: '16px 20px',
      borderRadius: 12,
      background: 'rgba(0,240,255,0.06)',
      border: '1px solid rgba(0,240,255,0.25)',
      marginBottom: 24,
      display: 'flex',
      alignItems: 'flex-start',
      gap: 12,
    }}>
      <span style={{ fontSize: 22, flexShrink: 0 }}>🌐</span>
      <div>
        <p style={{ margin: 0, fontWeight: 700, color: '#e2e8f0', fontSize: 14, marginBottom: 4 }}>
          Subscribe or upgrade on the web
        </p>
        <p style={{ margin: 0, color: '#94a3b8', fontSize: 13, lineHeight: 1.6 }}>
          To subscribe or upgrade, visit{' '}
          <strong style={{ color: '#00f0ff' }}>zeusbeats.com</strong>{' '}
          in Safari or your web browser. Your account and songs are the same everywhere.
        </p>
      </div>
    </div>
  );
}
