import { useEffect, useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { BRAND, BACKEND_URL } from '../brand';

export default function VerifyEmailPage() {
  const [searchParams] = useSearchParams();
  const token = searchParams.get('token') || '';
  const [status, setStatus] = useState('verifying');
  const [message, setMessage] = useState('');

  useEffect(() => {
    if (!token) { setStatus('error'); setMessage('No verification token found.'); return; }
    fetch(`${BACKEND_URL}/api/auth/verify-email`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ token }),
    })
      .then((r) => r.json())
      .then((data) => {
        if (data.ok) { setStatus('success'); setMessage(data.message); }
        else { setStatus('error'); setMessage(data.detail || 'Verification failed.'); }
      })
      .catch(() => { setStatus('error'); setMessage('Network error. Please try again.'); });
  }, [token]);

  return (
    <div className="auth-page">
      <div className="hero-orbs" aria-hidden>
        <div className="orb orb-1" />
        <div className="orb orb-2" />
      </div>
      <div className="auth-card">
        <div className="auth-logo">
          <span className="auth-logo-icon">⚡</span>
          <span className="auth-logo-text">{BRAND.name}</span>
        </div>
        <h1 className="auth-title">Email Verification</h1>
        {status === 'verifying' && <p className="auth-sub">Verifying your email…</p>}
        {status === 'success' && (
          <>
            <p className="auth-sub" style={{ color: '#22c55e' }}>{message}</p>
            <p className="auth-footer-text" style={{ marginTop: 24 }}>
              <Link to="/songs" className="auth-link">Go to songs</Link>
            </p>
          </>
        )}
        {status === 'error' && (
          <>
            <div className="form-error form-error--banner">{message}</div>
            <p className="auth-footer-text" style={{ marginTop: 16 }}>
              <Link to="/songs" className="auth-link">Go to songs</Link>
            </p>
          </>
        )}
      </div>
    </div>
  );
}
