import { useState } from 'react';
import { BACKEND_URL } from '../brand';

/**
 * Optional, non-blocking verification tip. Access is never gated on verification
 * (see backend songs_generate) — this is a gentle, dismissible nudge only.
 * Hidden when: verified, already dismissed (persisted per user), or the user
 * hasn't made their first song yet (let them enjoy the app before nudging).
 */
export function EmailVerificationBanner({ user, token, app = 'beats', hasSongs = true }) {
  const dismissKey = user ? `zeus_verify_tip_dismissed_${user.id}` : null;
  const [dismissed, setDismissed] = useState(
    () => !!dismissKey && localStorage.getItem(dismissKey) === '1',
  );
  const [resendStatus, setResendStatus] = useState('idle');

  if (!user || user.email_verified || dismissed || !hasSongs) return null;

  function dismiss() {
    try { if (dismissKey) localStorage.setItem(dismissKey, '1'); } catch {}
    setDismissed(true);
  }

  async function handleResend() {
    setResendStatus('loading');
    try {
      const res = await fetch(`${BACKEND_URL}/api/auth/resend-verification`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
        body: JSON.stringify({ app }),
      });
      setResendStatus(res.ok ? 'sent' : 'error');
    } catch {
      setResendStatus('error');
    }
  }

  return (
    <div style={{
      // Thin, calm bar — a subtle cyan tint, not an alarming warning colour.
      background: 'rgba(0,240,255,0.05)',
      borderBottom: '1px solid rgba(0,240,255,0.10)',
      padding: '6px 16px',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      gap: 10,
      flexWrap: 'wrap',
      fontSize: '0.8rem',
      color: '#94a3b8',
    }}>
      <span>💡 Tip: verify your email to secure your account and enable password recovery.</span>
      {resendStatus === 'sent' ? (
        <span style={{ color: '#34d399' }}>Sent — check your inbox.</span>
      ) : resendStatus === 'error' ? (
        <span style={{ color: '#f87171' }}>Couldn't send — try again later.</span>
      ) : (
        <button
          onClick={handleResend}
          disabled={resendStatus === 'loading'}
          style={{ background: 'none', border: 'none', color: '#00f0ff', cursor: 'pointer', textDecoration: 'underline', padding: 0, fontSize: 'inherit' }}
        >
          {resendStatus === 'loading' ? 'Sending…' : 'Resend link'}
        </button>
      )}
      <button
        onClick={dismiss}
        aria-label="Dismiss tip"
        title="Dismiss"
        style={{ background: 'none', border: 'none', color: '#64748b', cursor: 'pointer', fontSize: 15, lineHeight: 1, padding: '2px 6px', marginLeft: 2 }}
      >✕</button>
    </div>
  );
}
