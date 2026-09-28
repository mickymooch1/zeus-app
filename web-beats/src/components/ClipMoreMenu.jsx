import { useEffect, useRef, useState } from 'react';
import { createPortal } from 'react-dom';
import { BACKEND_URL } from '../brand';
import { clipMenuItems, isOwnClip, clipLink } from '../utils/clipMoreMenu';

const CYAN = '#00f0ff';
const RED = '#f87171';

// Matches backend/clips.py's VALID_REPORT_REASONS exactly.
const REASONS = [
  ['spam', 'Spam'],
  ['inappropriate', 'Inappropriate'],
  ['copyright', 'Copyright'],
  ['other', 'Other'],
];

/**
 * The "⋯" action on a clip — opens a bottom sheet: Copy link for everyone,
 * plus Delete (with a confirm step) on your own clip or Report on anyone else's.
 *
 * The sheet is portalled to <body> above all page chrome (cookie banner 9999,
 * Clips nav 9000). It used to be a popover opening upward from the button, which
 * on /clips/:id (⋯ in the header) landed above the top of the screen and was
 * clipped by .clip-box's overflow:hidden, and on the smallest feed layouts sat
 * under the fixed header.
 *
 * onDeleted(clipId) runs after a successful delete; onRequireAuth() when a
 * logged-out viewer picks Report.
 */
export default function ClipMoreMenu({ clip, token, user, onRequireAuth, onDeleted }) {
  const [open, setOpen] = useState(false);
  // menu | reasons | confirmDelete | done | error
  const [view, setView] = useState('menu');
  const [message, setMessage] = useState('');
  const [busy, setBusy] = useState(false);
  const closeTimer = useRef(null);
  const sheetRef = useRef(null);

  const isOwn = isOwnClip(user, clip);
  const items = clipMenuItems({ isOwn });

  const close = () => {
    if (busy) return;
    clearTimeout(closeTimer.current);
    setOpen(false);
    setView('menu');
    setMessage('');
  };
  const finish = (text, ok = true) => {
    setView(ok ? 'done' : 'error');
    setMessage(text);
    clearTimeout(closeTimer.current);
    closeTimer.current = setTimeout(() => { setOpen(false); setView('menu'); setMessage(''); }, ok ? 1300 : 2200);
  };

  useEffect(() => () => clearTimeout(closeTimer.current), []);
  useEffect(() => {
    if (!open) return undefined;
    sheetRef.current?.querySelector("button:not([disabled])")?.focus();
    const onKey = (e) => { if (e.key === 'Escape') close(); };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  });

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(clipLink(clip.id));
      finish('✓ Link copied');
    } catch {
      finish("Couldn't copy the link", false);
    }
  };

  const handleReportPick = () => {
    if (!token) { close(); onRequireAuth?.(); return; }
    setView('reasons');
  };

  const handleReport = async (reason) => {
    setBusy(true);
    try {
      const r = await fetch(`${BACKEND_URL}/api/clips/${clip.id}/report`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
        body: JSON.stringify({ reason }),
      });
      setBusy(false);
      finish(r.ok ? 'Reported — thanks.' : "Couldn't send — try again.", r.ok);
    } catch {
      setBusy(false);
      finish("Couldn't send — try again.", false);
    }
  };

  const handleDelete = async () => {
    setBusy(true);
    try {
      const r = await fetch(`${BACKEND_URL}/api/clips/${clip.id}`, {
        method: 'DELETE',
        headers: { Authorization: `Bearer ${token}` },
      });
      setBusy(false);
      if (!r.ok) { finish("Couldn't delete — try again.", false); return; }
      setOpen(false);
      setView('menu');
      onDeleted?.(clip.id);
    } catch {
      setBusy(false);
      finish("Couldn't delete — try again.", false);
    }
  };

  const row = (extra = {}) => ({
    width: '100%', minHeight: 50, display: 'flex', alignItems: 'center', gap: 12,
    padding: '0 16px', borderRadius: 12, border: 'none', background: 'rgba(255,255,255,0.05)',
    color: '#fff', fontSize: 15, fontWeight: 600, fontFamily: 'inherit', textAlign: 'left',
    cursor: busy ? 'default' : 'pointer', opacity: busy ? 0.6 : 1, ...extra,
  });

  const ITEM = {
    copy:   { icon: '🔗', label: 'Copy link' },
    report: { icon: '🚩', label: 'Report clip', color: RED },
    delete: { icon: '🗑️', label: 'Delete clip', color: RED },
  };
  const pick = (key) => {
    if (key === 'copy') handleCopy();
    else if (key === 'report') handleReportPick();
    else if (key === 'delete') setView('confirmDelete');
  };

  let body;
  if (view === 'reasons') {
    body = (
      <>
        <p style={{ margin: '0 4px 10px', fontSize: 13, color: 'rgba(255,255,255,0.6)' }}>Why are you reporting this clip?</p>
        {REASONS.map(([value, label]) => (
          <button key={value} type="button"
            disabled={busy} onClick={() => handleReport(value)} style={row()}>
            {label}
          </button>
        ))}
      </>
    );
  } else if (view === 'confirmDelete') {
    body = (
      <>
        <p style={{ margin: '0 4px 4px', fontSize: 16, fontWeight: 800, color: '#fff' }}>Delete this clip?</p>
        <p style={{ margin: '0 4px 12px', fontSize: 13, lineHeight: 1.45, color: 'rgba(255,255,255,0.65)' }}>
          It&apos;ll be removed from Clips for everyone. This can&apos;t be undone.
        </p>
        <button type="button" disabled={busy} onClick={handleDelete}
          style={row({ justifyContent: 'center', background: RED, color: '#000', fontWeight: 800 })}>
          {busy ? 'Deleting…' : 'Delete clip'}
        </button>
      </>
    );
  } else if (view === 'done' || view === 'error') {
    body = (
      <p role="status" style={{ margin: 0, padding: '14px 4px', textAlign: 'center', fontSize: 15, fontWeight: 700,
        color: view === 'done' ? '#34d399' : RED }}>
        {message}
      </p>
    );
  } else {
    body = items.map((key) => {
      const it = ITEM[key];
      return (
        <button key={key} type="button" onClick={() => pick(key)}
          style={row({ color: it.color || '#fff' })}>
          <span aria-hidden="true" style={{ fontSize: 18, width: 22, textAlign: 'center' }}>{it.icon}</span>
          {it.label}
        </button>
      );
    });
  }

  return (
    <>
      <button
        type="button"
        onClick={() => setOpen(true)}
        aria-label="More"
        aria-haspopup="dialog"
        aria-expanded={open}
        style={{
          width: 40, height: 40, borderRadius: '50%',
          background: 'rgba(10,10,20,0.55)', backdropFilter: 'blur(8px)', WebkitBackdropFilter: 'blur(8px)',
          border: '1.5px solid rgba(255,255,255,0.22)', color: '#fff', fontSize: 18,
          cursor: 'pointer', display: 'flex', alignItems: 'center', justifyContent: 'center',
        }}
      >
        ⋯
      </button>

      {open && createPortal(
        // Portal events still bubble through the React tree — stop them here so a
        // tap in the sheet never reaches the slide underneath (tap-to-pause etc.).
        <div
          onClick={(e) => { e.stopPropagation(); close(); }}
          style={{
            position: 'fixed', inset: 0, zIndex: 10050,
            background: 'rgba(0,0,0,0.7)',
            display: 'flex', alignItems: 'flex-end', justifyContent: 'center',
          }}
        >
          <div
            ref={sheetRef}
            role="dialog"
            aria-modal="true"
            aria-label="Clip options"
            onClick={(e) => e.stopPropagation()}
            style={{
              width: '100%', maxWidth: 520, maxHeight: '85svh', overflowY: 'auto',
              background: '#0d0d1a', borderTop: `1px solid ${CYAN}44`, borderRadius: '20px 20px 0 0',
              boxShadow: '0 -10px 40px rgba(0,0,0,0.7)',
              padding: '10px 14px calc(14px + env(safe-area-inset-bottom))',
              display: 'flex', flexDirection: 'column', gap: 8,
            }}
          >
            <div aria-hidden="true" style={{ width: 40, height: 4, borderRadius: 2, background: 'rgba(255,255,255,0.22)', margin: '0 auto 6px', flex: 'none' }} />
            {body}
            {view !== 'done' && view !== 'error' && (
              <button type="button" onClick={close} disabled={busy}
                style={row({ justifyContent: 'center', background: 'transparent', border: '1px solid rgba(255,255,255,0.15)', color: 'rgba(255,255,255,0.8)' })}>
                Cancel
              </button>
            )}
          </div>
        </div>,
        document.body
      )}
    </>
  );
}
