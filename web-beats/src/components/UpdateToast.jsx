import { useSWUpdate } from '../hooks/useSWUpdate';

export function UpdateToast() {
  const { updating } = useSWUpdate();
  if (!updating) return null;

  return (
    <div style={{
      position: 'fixed', bottom: 24, left: '50%', transform: 'translateX(-50%)',
      background: 'rgba(10,10,24,0.97)',
      border: '1px solid rgba(0,240,255,0.35)',
      borderRadius: 10, padding: '10px 22px',
      color: '#e2e8f0', fontSize: 13, fontWeight: 600,
      zIndex: 99999, boxShadow: '0 4px 28px rgba(0,0,0,0.6)',
      display: 'flex', alignItems: 'center', gap: 8,
      whiteSpace: 'nowrap', pointerEvents: 'none',
      animation: 'zbFadeIn 0.25s ease',
    }}>
      <style>{`@keyframes zbFadeIn{from{opacity:0;transform:translateX(-50%) translateY(8px)}to{opacity:1;transform:translateX(-50%) translateY(0)}}`}</style>
      <span style={{ color: '#00f0ff' }}>⚡</span>
      Zeus Beats updated — refreshing…
    </div>
  );
}
