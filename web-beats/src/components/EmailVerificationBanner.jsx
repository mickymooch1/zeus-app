import { useState } from 'react';
import { BACKEND_URL } from '../brand';

export function EmailVerificationBanner({ user, token, app = 'beats' }) {
  const [resendStatus, setResendStatus] = useState('idle');

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
      background: 'rgba(250,204,21,0.08)',
      borderBottom: '1px solid rgba(250,204,21,0.2)',
      padding: '10px 20px',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      gap: 12,
      flexWrap: 'wrap',
      fontSize: '0.875rem',
      color: '#fbbf24',
    }}>
      <span>⚠ Please verify your email address to generate songs.</span>
      {resendStatus === 'sent' ? (
        <span style={{ color: '#34d399', fontWeight: 600 }}>Verification email sent!</span>
      ) : resendStatus === 'error' ? (
        <span style={{ color: '#f87171' }}>Failed to send — try again later.</span>
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
