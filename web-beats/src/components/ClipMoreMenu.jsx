import { useState } from 'react';
import { BACKEND_URL } from '../brand';

const CYAN = '#00f0ff';

// Matches backend/clips.py's VALID_REPORT_REASONS exactly.
const REASONS = [
  ['spam', 'Spam'],
  ['inappropriate', 'Inappropriate'],
  ['copyright', 'Copyright'],
  ['other', 'Other'],
];

// The "⋯" action — currently just Report (the only thing behind it in the
// approved mockup; everything else in that menu — Save, Message, etc. — is out
// of scope for this phase).
export default function ClipMoreMenu({ clipId, token, onRequireAuth }) {
  const [open, setOpen] = useState(false);
  const [picking, setPicking] = useState(false);
  const [status, setStatus] = useState('idle'); // idle | sending | sent | error

  const handleToggle = () => {
    if (!token) { onRequireAuth?.(); return; }
    setOpen(o => !o);
    setPicking(false);
  };

  const handleReport = async (reason) => {
    setStatus('sending');
    try {
      const r = await fetch(`${BACKEND_URL}/api/clips/${clipId}/report`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
        body: JSON.stringify({ reason }),
      });
      setStatus(r.ok ? 'sent' : 'error');
    } catch {
      setStatus('error');
    }
    setTimeout(() => { setOpen(false); setPicking(false); setStatus('idle'); }, 1400);
  };

  return (
    <div style={{ position: 'relative' }}>
      <button
        onClick={handleToggle}
        aria-label="More"
        style={{
          width: 40, height: 40, borderRadius: '50%',
          background: 'rgba(10,10,20,0.55)', backdropFilter: 'blur(8px)', WebkitBackdropFilter: 'blur(8px)',
          border: '1.5px solid rgba(255,255,255,0.22)', color: '#fff', fontSize: 18,
          cursor: 'pointer', display: 'flex', alignItems: 'center', justifyContent: 'center',
        }}
      >
        ⋯
      </button>

      {open && (
        <div style={{
          position: 'absolute', bottom: 46, right: 0, zIndex: 30, minWidth: 168,
          background: 'rgba(13,13,26,0.95)', backdropFilter: 'blur(12px)',
          border: `1px solid ${CYAN}33`, borderRadius: 14, padding: 8,
          boxShadow: `0 8px 28px rgba(0,0,0,0.6), 0 0 18px ${CYAN}22`,
        }}>
          {!picking ? (
            <button
              onClick={() => setPicking(true)}
              style={{
                width: '100%', textAlign: 'left', padding: '9px 10px', borderRadius: 8,
                background: 'none', border: 'none', color: '#f87171', fontSize: 13, fontWeight: 600, cursor: 'pointer',
              }}
            >
              🚩 Report
            </button>
          ) : status === 'sent' ? (
            <p style={{ margin: 0, padding: '9px 10px', color: '#34d399', fontSize: 12 }}>Reported — thanks.</p>
          ) : status === 'error' ? (
            <p style={{ margin: 0, padding: '9px 10px', color: '#f87171', fontSize: 12 }}>Couldn&apos;t send — try again.</p>
          ) : (
            REASONS.map(([value, label]) => (
              <button
                key={value}
                onClick={() => handleReport(value)}
                disabled={status === 'sending'}
                style={{
                  width: '100%', textAlign: 'left', padding: '8px 10px', borderRadius: 8,
                  background: 'none', border: 'none', color: 'rgba(255,255,255,0.8)', fontSize: 13, cursor: 'pointer',
                }}
              >
                {label}
              </button>
            ))
          )}
        </div>
      )}
    </div>
  );
}
