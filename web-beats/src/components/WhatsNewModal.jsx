import { useEffect, useRef, useState } from 'react';
import { createPortal } from 'react-dom';
import { BACKEND_URL } from '../brand';
import { useAuth } from '../contexts/AuthContext';

// "What's New" popup — fetches unseen announcements once per authenticated
// session (fires on login AND on a returning session with a persisted
// token, since both mean the app just mounted with a logged-in user) and
// shows them as a single dismissible modal. "Got it" marks the user caught
// up on ALL pending announcements (not just the ones shown here — see
// POST /announcements/seen), matching the 3-item display cap in
// GET /announcements/unseen.
export default function WhatsNewModal() {
  const { user, token } = useAuth();
  const [announcements, setAnnouncements] = useState([]);
  const [dismissing, setDismissing] = useState(false);
  const closeRef = useRef(null);
  const checkedForRef = useRef(null);

  useEffect(() => {
    if (!user || !token) return;
    if (checkedForRef.current === user.id) return; // already checked this session
    checkedForRef.current = user.id;

    let cancelled = false;
    (async () => {
      try {
        const r = await fetch(`${BACKEND_URL}/announcements/unseen`, {
          headers: { Authorization: `Bearer ${token}` },
        });
        if (!r.ok) return;
        const data = await r.json();
        if (!cancelled && Array.isArray(data.announcements) && data.announcements.length > 0) {
          setAnnouncements(data.announcements);
        }
      } catch { /* silent — announcements are non-critical */ }
    })();
    return () => { cancelled = true; };
  }, [user, token]);

  useEffect(() => {
    if (announcements.length === 0) return;
    const onKey = (e) => { if (e.key === 'Escape') handleGotIt(); };
    window.addEventListener('keydown', onKey);
    closeRef.current?.focus({ preventScroll: true });
    return () => window.removeEventListener('keydown', onKey);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [announcements]);

  if (announcements.length === 0) return null;

  async function handleGotIt() {
    if (dismissing) return;
    setDismissing(true);
    setAnnouncements([]);
    try {
      await fetch(`${BACKEND_URL}/announcements/seen`, {
        method: 'POST',
        headers: { Authorization: `Bearer ${token}` },
      });
    } catch { /* best-effort — worst case they see this batch again next login */ }
  }

  return createPortal(
    <div
      style={{
        position: 'fixed', inset: 0, zIndex: 10000,
        background: 'rgba(6,6,12,0.92)', backdropFilter: 'blur(6px)',
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        padding: 16,
      }}
    >
      <div
        role="dialog"
        aria-label="What's New"
        style={{
          width: '100%', maxWidth: 420, maxHeight: '80vh',
          display: 'flex', flexDirection: 'column',
          background: '#0a0a14',
          border: '1px solid rgba(0,240,255,0.14)',
          borderRadius: 16,
          boxShadow: '0 -4px 60px rgba(0,240,255,0.10)',
          overflow: 'hidden',
        }}
      >
        <div style={{
          padding: '18px 20px 14px', borderBottom: '1px solid rgba(255,255,255,0.06)',
          flexShrink: 0,
        }}>
          <div style={{ fontSize: 16, fontWeight: 700, color: '#e2e8f0' }}>
            🎉 What's New
          </div>
        </div>

        <div style={{ flex: 1, overflowY: 'auto', padding: '18px 20px' }}>
          {announcements.map((a, i) => (
            <div key={a.id} style={{ marginTop: i === 0 ? 0 : 22 }}>
              <div style={{ fontSize: 15, fontWeight: 700, color: '#00f0ff', marginBottom: 6 }}>
                {a.title}
              </div>
              <div style={{ fontSize: 14, lineHeight: 1.6, color: '#e2e8f0' }}>
                {a.body}
              </div>
            </div>
          ))}
        </div>

        <div style={{ padding: '14px 20px 20px', flexShrink: 0 }}>
          <button
            ref={closeRef}
            onClick={handleGotIt}
            style={{
              width: '100%', minHeight: 48, borderRadius: 10,
              background: 'rgba(0,240,255,0.12)', border: '1px solid rgba(0,240,255,0.35)',
              color: '#00f0ff', fontSize: 15, fontWeight: 700, cursor: 'pointer',
            }}
          >
            Got it
          </button>
        </div>
      </div>
    </div>,
    document.body,
  );
}
