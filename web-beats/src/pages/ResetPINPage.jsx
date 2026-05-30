import { useEffect, useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { BRAND, BACKEND_URL } from '../brand';

export default function ResetPINPage() {
  const [searchParams] = useSearchParams();
  const token = searchParams.get('token') || '';
  const [status, setStatus] = useState('idle'); // idle | loading | done | error
  const [message, setMessage] = useState('');

  useEffect(() => {
    if (!token) return;
    setStatus('loading');
    fetch(`${BACKEND_URL}/api/user/reset-pin?token=${encodeURIComponent(token)}`)
      .then(async (res) => {
        const data = await res.json();
        if (!res.ok) throw new Error(data.detail || 'Reset failed');
        localStorage.setItem('zeus_explicit_pin', '1234');
        setStatus('done');
      })
      .catch((err) => {
        setMessage(err.message);
        setStatus('error');
      });
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
        <h1 className="auth-title">Explicit Content PIN Reset</h1>

        {!token && (
          <>
            <p className="form-error form-error--banner">Invalid reset link. Please request a new one from Settings.</p>
            <p className="auth-footer-text"><Link to="/billing" className="auth-link">Back to Settings</Link></p>
          </>
        )}

        {token && status === 'loading' && (
          <p style={{ color: '#94a3b8', textAlign: 'center' }}>Verifying reset link…</p>
        )}

        {status === 'done' && (
          <>
            <p style={{ color: '#22c55e', fontSize: '15px', textAlign: 'center', lineHeight: 1.6 }}>
              ✅ Your explicit content PIN has been reset to <strong>1234</strong>.
            </p>
            <p style={{ color: '#94a3b8', fontSize: '13px', textAlign: 'center', marginTop: 8 }}>
              You can set a new PIN in Settings → Billing.
            </p>
            <p className="auth-footer-text" style={{ marginTop: 20 }}>
              <Link to="/billing" className="auth-link">Go to Settings</Link>
            </p>
          </>
        )}

        {status === 'error' && (
          <>
            <p className="form-error form-error--banner">{message || 'This reset link is invalid or has expired.'}</p>
            <p className="auth-footer-text"><Link to="/billing" className="auth-link">Back to Settings</Link></p>
          </>
        )}
      </div>
    </div>
  );
}
