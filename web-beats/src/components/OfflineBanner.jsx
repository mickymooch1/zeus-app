// web-beats/src/components/OfflineBanner.jsx
export default function OfflineBanner() {
  return (
    <div role="status" aria-live="polite" style={{
      background:   'linear-gradient(135deg, rgba(245,158,11,0.12), rgba(245,158,11,0.06))',
      border:       '1px solid rgba(245,158,11,0.3)',
      borderRadius: 8,
      padding:      '10px 16px',
      marginBottom: 16,
      display:      'flex',
      alignItems:   'center',
      gap:          10,
    }}>
      <span style={{ fontSize: 18 }}>📵</span>
      <span style={{ fontSize: 13, color: '#fbbf24', fontWeight: 500, lineHeight: 1.4 }}>
        <strong>You're offline</strong> — reconnect to create songs. Playing from your saved library.
      </span>
    </div>
  );
}
