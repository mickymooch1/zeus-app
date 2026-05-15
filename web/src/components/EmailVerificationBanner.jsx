import { useState } from 'react';

const BACKEND_URL = import.meta.env.VITE_BACKEND_URL || '';

export function EmailVerificationBanner({ user, token, app = 'ai' }) {
  const [resendStatus, setResendStatus] = useState('idle'); // idle | loading | sent | error

  if (!user || user.email_verified) return null;

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
      background: 'rgba(234,179,8,0.1)',
      borderBottom: '1px solid rgba(234,179,8,0.3)',
      padding: '10px 20px',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      gap: 12,
      flexWrap: 'wrap',
      fontSize: '0.875rem',
      color: '#ca8a04',
    }}>
      <span>⚠ Please verify your email address to generate songs.</span>
      {resendStatus === 'sent' ? (
        <span style={{ color: '#16a34a', fontWeight: 600 }}>Verification email sent!</span>
      ) : resendStatus === 'error' ? (
        <span style={{ color: '#dc2626' }}>Failed to send — try again later.</span>
      ) : (
        <button
          onClick={handleResend}
          disabled={resendStatus === 'loading'}
          style={{ background: 'none', border: 'none', color: 'inherit', cursor: 'pointer', textDecoration: 'underline', padding: 0, fontWeight: 600, fontSize: 'inherit' }}
        >
          {resendStatus === 'loading' ? 'Sending…' : 'Resend email'}
        </button>
      )}
    </div>
  );
}
