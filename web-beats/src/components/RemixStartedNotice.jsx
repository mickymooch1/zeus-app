import { useEffect, useState } from 'react';

const CYAN = '#00f0ff';
const PURPLE = '#7c3aed';

/**
 * Shown on /songs right after a Zeus Clips remix was started, in place of the
 * first-visit "explore first" welcome (someone mid-remix wants to know their
 * song is coming, not a tour). Dismissable; hides itself after a few seconds.
 */
export default function RemixStartedNotice() {
  const [visible, setVisible] = useState(true);

  useEffect(() => {
    const t = setTimeout(() => setVisible(false), 8000);
    return () => clearTimeout(t);
  }, []);

  if (!visible) return null;

  return (
    <div
      role="status"
      style={{
        position: 'fixed', top: 'max(16px, env(safe-area-inset-top))', left: 16, right: 16,
        margin: '0 auto', maxWidth: 440, zIndex: 9998,
        display: 'flex', alignItems: 'center', gap: 12, padding: '12px 14px', borderRadius: 14,
        background: 'rgba(10,10,20,0.95)', border: `1px solid ${CYAN}55`,
        boxShadow: `0 0 24px ${CYAN}22, 0 10px 30px rgba(0,0,0,0.6)`, color: '#fff',
      }}
    >
      <span style={{
        flexShrink: 0, width: 30, height: 30, borderRadius: '50%', display: 'flex',
        alignItems: 'center', justifyContent: 'center', fontSize: 15,
        background: `linear-gradient(135deg, ${CYAN}, ${PURPLE})`,
      }}>⚡</span>
      <p style={{ margin: 0, flex: 1, fontSize: 14, lineHeight: 1.4 }}>
        Your remix is being made, it&apos;ll appear in your songs shortly.
      </p>
      <button
        type="button"
        onClick={() => setVisible(false)}
        aria-label="Dismiss"
        style={{ background: 'none', border: 'none', color: 'rgba(255,255,255,0.5)', fontSize: 18, cursor: 'pointer', padding: 4 }}
      >
        ×
      </button>
    </div>
  );
}
