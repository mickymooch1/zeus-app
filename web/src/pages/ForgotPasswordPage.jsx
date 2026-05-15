import { useState } from 'react';
import { Link } from 'react-router-dom';
import { Navbar } from '../components/Navbar';

const BACKEND_URL = import.meta.env.VITE_BACKEND_URL || '';

export default function ForgotPasswordPage() {
  const [email, setEmail] = useState('');
  const [status, setStatus] = useState('idle');
  const [error, setError] = useState('');

  async function handleSubmit(e) {
    e.preventDefault();
    setStatus('loading');
    setError('');
    try {
      const res = await fetch(`${BACKEND_URL}/api/auth/forgot-password`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email, app: 'ai' }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || 'Request failed');
      setStatus('sent');
    } catch (err) {
      setError(err.message);
      setStatus('idle');
    }
  }

  return (
    <div className="auth-page">
      <div className="hero-orbs" aria-hidden>
        <div className="orb orb-1" />
        <div className="orb orb-2" />
      </div>
      <div className="auth-card">
        <div className="auth-logo">
          <span className="auth-logo-icon">⚡</span>
          <span className="auth-logo-text">Zeus</span>
        </div>
        <h1 className="auth-title">Reset password</h1>
        {status === 'sent' ? (
          <>
            <p className="auth-sub" style={{ color: '#22c55e' }}>
              If that email is registered, a reset link has been sent. Check your inbox.
            </p>
            <p className="auth-footer-text" style={{ marginTop: 24 }}>
              <Link to="/login" className="auth-link">Back to sign in</Link>
            </p>
          </>
        ) : (
          <>
            <p className="auth-sub">Enter your email and we'll send you a reset link.</p>
            {error && <div className="form-error form-error--banner">{error}</div>}
            <form onSubmit={handleSubmit} className="auth-form">
              <div className="form-group">
                <label className="form-label" htmlFor="email">Email address</label>
                <input
                  id="email"
                  type="email"
                  className="form-input"
                  placeholder="you@example.com"
                  required
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  autoComplete="email"
                />
              </div>
              <button
                type="submit"
                className="btn btn-primary btn-full"
                disabled={status === 'loading' || !email}
              >
                {status === 'loading' ? <span className="spinner spinner--inline" /> : 'Send reset link'}
              </button>
            </form>
            <p className="auth-footer-text">
              <Link to="/login" className="auth-link">Back to sign in</Link>
            </p>
          </>
        )}
      </div>
    </div>
  );
}
