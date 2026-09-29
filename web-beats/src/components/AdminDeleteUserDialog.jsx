import { useEffect, useState } from 'react';
import { BACKEND_URL } from '../brand';
import { apiErrorMessage } from '../utils/apiErrorMessage';
import { canConfirmDelete, formatBytes } from '../utils/adminDelete';

/**
 * Admin panel "Delete account" confirmation (2026-09-29). Loads the server's
 * dry-run preview (GET /admin/users/:id/delete-preview — changes nothing),
 * shows what would be removed, and only then offers the delete. Blockers
 * (admin account, yourself, active subscription) hide the button entirely;
 * warnings (past Stripe purchases, generated QR codes) need an explicit
 * "I understand"; the account's email must be typed to confirm.
 */
export default function AdminDeleteUserDialog({ row, token, onClose, onDeleted }) {
  const [preview, setPreview] = useState(null);
  const [loadError, setLoadError] = useState('');
  const [typed, setTyped] = useState('');
  const [acknowledged, setAcknowledged] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    let cancelled = false;
    fetch(`${BACKEND_URL}/admin/users/${encodeURIComponent(row.id)}/delete-preview`, {
      headers: { Authorization: `Bearer ${token}` },
    })
      .then(r => r.json().then(d => (r.ok ? d : Promise.reject(apiErrorMessage(d.detail, 'Could not load preview')))))
      .then(d => { if (!cancelled) setPreview(d); })
      .catch(e => { if (!cancelled) setLoadError(typeof e === 'string' ? e : 'Could not load preview'); });
    return () => { cancelled = true; };
  }, [row.id, token]);

  useEffect(() => {
    const onKey = (e) => { if (e.key === 'Escape' && !busy) onClose(); };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [busy, onClose]);

  const enabled = canConfirmDelete({ preview, typedEmail: typed, acknowledged, busy });

  async function handleDelete() {
    if (!enabled) return;
    setBusy(true);
    setError('');
    try {
      const r = await fetch(`${BACKEND_URL}/admin/users/${encodeURIComponent(row.id)}`, {
        method: 'DELETE',
        headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
        body: JSON.stringify({ confirm_email: typed.trim(), acknowledge_warnings: acknowledged }),
      });
      const d = await r.json().catch(() => ({}));
      if (!r.ok) throw new Error(apiErrorMessage(d.detail, 'Delete failed'));
      onDeleted(d);
    } catch (e) {
      setError(e.message || 'Delete failed');
      setBusy(false);
    }
  }

  const facts = preview ? [
    ['Name', preview.name || '—'],
    ['Joined', preview.created_at ? new Date(preview.created_at).toLocaleDateString('en-GB') : '—'],
    ['Plan / status', `${preview.subscription_plan} / ${preview.subscription_status}`],
    ['Songs', preview.songs],
    ['Song credits', preview.song_credits],
    ['Memorial credits', preview.memorial_credits],
    ['Memorial pages', preview.memorial_pages],
    ['Credit ledger rows', `${preview.ledger_rows} (${preview.stripe_purchases} Stripe)`],
    ['QR codes generated', preview.qr_codes],
    ['Files on the volume', `${preview.files} (${formatBytes(preview.file_bytes)})`],
  ] : [];

  return (
    <div
      role="dialog" aria-modal="true" aria-labelledby="admin-delete-title"
      onClick={(e) => { if (e.target === e.currentTarget && !busy) onClose(); }}
      style={{ position: 'fixed', inset: 0, zIndex: 1000, background: 'rgba(0,0,0,0.75)', display: 'flex',
               alignItems: 'center', justifyContent: 'center', padding: 16 }}
    >
      <div style={{ width: '100%', maxWidth: 480, maxHeight: '90vh', overflowY: 'auto', background: '#0a0a0a',
                    border: '1px solid rgba(239,68,68,0.35)', borderRadius: 12, padding: 22, color: '#e2e8f0' }}>
        <h2 id="admin-delete-title" style={{ fontSize: 18, fontWeight: 800, margin: '0 0 4px', color: '#fff' }}>Delete account</h2>
        <p style={{ margin: '0 0 16px', fontFamily: 'monospace', fontSize: 13, color: '#fca5a5', wordBreak: 'break-all' }}>{row.email}</p>

        {!preview && !loadError && <p style={{ color: '#555', fontSize: 13 }}>Loading what would be deleted…</p>}
        {loadError && <p style={{ color: '#fca5a5', fontSize: 13 }}>{loadError}</p>}

        {preview && (
          <>
            <dl style={{ display: 'grid', gridTemplateColumns: 'auto 1fr', gap: '6px 14px', margin: '0 0 16px', fontSize: 13 }}>
              {facts.map(([k, v]) => (
                <div key={k} style={{ display: 'contents' }}>
                  <dt style={{ color: '#666' }}>{k}</dt>
                  <dd style={{ margin: 0, color: '#e2e8f0', textAlign: 'right' }}>{v}</dd>
                </div>
              ))}
            </dl>

            {preview.blockers.length > 0 && (
              <div style={{ background: 'rgba(239,68,68,0.12)', border: '1px solid rgba(239,68,68,0.4)', borderRadius: 8,
                            padding: '10px 12px', fontSize: 13, color: '#fca5a5', marginBottom: 14 }}>
                <strong>Can't delete this account:</strong>
                <ul style={{ margin: '6px 0 0', paddingLeft: 18 }}>{preview.blockers.map(b => <li key={b}>{b}</li>)}</ul>
              </div>
            )}

            {preview.blockers.length === 0 && (
              <>
                {preview.warnings.length > 0 && (
                  <div style={{ background: 'rgba(251,191,36,0.12)', border: '1px solid rgba(251,191,36,0.5)', borderRadius: 8,
                                padding: '10px 12px', fontSize: 13, color: '#fcd34d', marginBottom: 14 }}>
                    <strong>⚠️ Check before deleting:</strong>
                    <ul style={{ margin: '6px 0 8px', paddingLeft: 18 }}>{preview.warnings.map(w => <li key={w}>{w}</li>)}</ul>
                    <label style={{ display: 'flex', gap: 8, alignItems: 'center', cursor: 'pointer', color: '#fff' }}>
                      <input type="checkbox" checked={acknowledged} onChange={e => setAcknowledged(e.target.checked)} disabled={busy} />
                      I understand
                    </label>
                  </div>
                )}
                <p style={{ fontSize: 12, color: '#888', margin: '0 0 6px' }}>
                  This permanently deletes the account, its songs, credits, ledger rows, memorial pages and files. Type the email to confirm:
                </p>
                <input
                  type="email" value={typed} onChange={e => setTyped(e.target.value)} disabled={busy}
                  placeholder={preview.email} aria-label="Type the account email to confirm" autoComplete="off"
                  style={{ width: '100%', boxSizing: 'border-box', padding: '9px 11px', borderRadius: 8, fontSize: 13,
                           background: '#111', color: '#fff', border: '1px solid rgba(255,255,255,0.12)', marginBottom: 12 }}
                />
              </>
            )}
          </>
        )}

        {error && <p style={{ color: '#fca5a5', fontSize: 13, margin: '0 0 12px' }}>{error}</p>}

        <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 10, flexWrap: 'wrap' }}>
          <button type="button" onClick={onClose} disabled={busy}
                  style={{ padding: '8px 16px', borderRadius: 8, border: '1px solid rgba(255,255,255,0.15)', background: 'transparent',
                           color: '#ccc', fontWeight: 600, cursor: busy ? 'default' : 'pointer' }}>
            Cancel
          </button>
          {preview && preview.blockers.length === 0 && (
            <button type="button" onClick={handleDelete} disabled={!enabled}
                    style={{ padding: '8px 16px', borderRadius: 8, border: 'none', fontWeight: 700,
                             background: enabled ? '#dc2626' : 'rgba(220,38,38,0.3)', color: enabled ? '#fff' : 'rgba(255,255,255,0.5)',
                             cursor: enabled ? 'pointer' : 'not-allowed' }}>
              {busy ? 'Deleting…' : 'Delete account'}
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
