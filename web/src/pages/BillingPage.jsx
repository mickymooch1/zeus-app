import { useEffect, useState } from 'react';
import { Link, useLocation } from 'react-router-dom';
import { Navbar } from '../components/Navbar';
import { useAuth } from '../contexts/AuthContext';

const BACKEND_URL = import.meta.env.VITE_BACKEND_URL || '';

function UsageBar({ used, limit }) {
  if (limit === null || limit === undefined) {
    return (
      <div className="usage-bar-wrap">
        <div className="usage-bar">
          <div className="usage-bar-fill usage-bar-fill--unlimited" style={{ width: '100%' }} />
        </div>
        <span className="usage-label">Unlimited messages</span>
      </div>
    );
  }
  const pct = Math.min(100, (used / limit) * 100);
  const isNearLimit = pct >= 75;
  return (
    <div className="usage-bar-wrap">
      <div className="usage-bar">
        <div
          className={`usage-bar-fill${isNearLimit ? ' usage-bar-fill--warn' : ''}`}
          style={{ width: `${pct}%` }}
        />
      </div>
      <span className="usage-label">
        {used} / {limit} messages this month
      </span>
    </div>
  );
}

export default function BillingPage() {
  const { user, token } = useAuth();
  const location = useLocation();
  const [status, setStatus] = useState(null);
  const [loadingPortal, setLoadingPortal] = useState(false);
  const [loadingCheckout, setLoadingCheckout] = useState(null);
  const [error, setError] = useState('');
  const [successMsg, setSuccessMsg] = useState('');

  const successParam = new URLSearchParams(location.search).get('success');

  useEffect(() => {
    if (successParam === 'true') {
      setSuccessMsg('Payment successful! Your plan is being activated. This may take a moment.');
    }
  }, [successParam]);

  useEffect(() => {
    if (!token) return;
    fetch(`${BACKEND_URL}/billing/status`, {
      headers: { Authorization: `Bearer ${token}` },
    })
      .then((r) => r.ok ? r.json() : null)
      .then((data) => { if (data) setStatus(data); })
      .catch(() => {});
  }, [token]);

  const handlePortal = async () => {
    setError('');
    setLoadingPortal(true);
    try {
      const res = await fetch(`${BACKEND_URL}/billing/portal`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || 'Failed to open billing portal');
      window.location.href = data.url;
    } catch (err) {
      setError(err.message);
      setLoadingPortal(false);
    }
  };

  const handleCheckout = async (plan) => {
    setError('');
    setLoadingCheckout(plan);
    try {
      const res = await fetch(`${BACKEND_URL}/billing/checkout`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({ plan }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || 'Failed to create checkout');
      window.location.href = data.url;
    } catch (err) {
      setError(err.message);
      setLoadingCheckout(null);
    }
  };

  const isActive = status?.is_active;
  const planName = status?.plan_name || 'Free';

  return (
    <div className="billing-page">
      <Navbar />
      <div className="page billing-page-inner">
        <div className="hero-orbs" aria-hidden>
          <div className="orb orb-2" />
        </div>

        <h1 className="billing-title">Billing &amp; Subscription</h1>

        {successMsg && (
          <div className="success-banner">{successMsg}</div>
        )}
        {error && (
          <div className="form-error form-error--banner">{error}</div>
        )}

        {/* Current plan card */}
        <div className="billing-card">
          <div className="billing-card-header">
            <h2 className="billing-card-title">Current Plan</h2>
            {status?.plan === 'pro' && <span className="badge-pro">Pro</span>}
            {status?.plan === 'agency' && <span className="badge-agency">Agency</span>}
            {(!status?.plan || !isActive) && <span className="badge-free">Free</span>}
          </div>

          <div className="billing-plan-name">{planName}</div>

          {status ? (
            <UsageBar used={status.messages_used} limit={status.messages_limit} />
          ) : (
            <div className="spinner" />
          )}

          <div className="billing-actions">
            {isActive && user?.stripe_customer_id ? (
              <button
                className="btn btn-outline"
                onClick={handlePortal}
                disabled={loadingPortal}
              >
                {loadingPortal ? <span className="spinner spinner--inline" /> : 'Manage Subscription'}
              </button>
            ) : null}
            {!isActive && (
              <Link to="/pricing" className="btn btn-primary">
                Upgrade Plan
              </Link>
            )}
          </div>
        </div>

        {/* Upgrade options for free users */}
        {!isActive && (
          <div className="billing-upgrade-section">
            <h2 className="billing-section-title">Upgrade for unlimited access</h2>
            <div className="billing-upgrade-grid">
              <div className="billing-upgrade-card">
                <span className="badge-pro">Pro</span>
                <div className="billing-upgrade-price">£29/mo</div>
                <p className="billing-upgrade-desc">
                  Unlimited messages, all features, Netlify deploy, persistent memory
                </p>
                <button
                  className="btn btn-primary btn-full"
                  disabled={loadingCheckout === 'pro'}
                  onClick={() => handleCheckout('pro')}
                >
                  {loadingCheckout === 'pro' ? <span className="spinner spinner--inline" /> : 'Upgrade to Pro'}
                </button>
              </div>

              <div className="billing-upgrade-card">
                <span className="badge-agency">Agency</span>
                <div className="billing-upgrade-price">£79/mo</div>
                <p className="billing-upgrade-desc">
                  Everything in Pro plus team features, priority support, and custom integrations
                </p>
                <button
                  className="btn btn-outline btn-full"
                  disabled={loadingCheckout === 'agency'}
                  onClick={() => handleCheckout('agency')}
                >
                  {loadingCheckout === 'agency' ? <span className="spinner spinner--inline" /> : 'Upgrade to Agency'}
                </button>
              </div>
            </div>
          </div>
        )}

        {/* Plan features */}
        <div className="billing-card">
          <h2 className="billing-card-title">Your plan includes</h2>
          <ul className="pricing-features" style={{ marginTop: '1rem' }}>
            {(!status?.plan || !isActive) && [
              '20 messages per month',
              'AI chat assistant',
            ].map((f) => (
              <li key={f} className="plan-feature">
                <span className="plan-feature-check">✓</span>{f}
              </li>
            ))}
            {status?.plan === 'pro' && isActive && [
              'Unlimited messages',
              'AI chat assistant',
              'Priority support',
            ].map((f) => (
              <li key={f} className="plan-feature">
                <span className="plan-feature-check">✓</span>{f}
              </li>
            ))}
            {status?.plan === 'agency' && isActive && [
              'Unlimited messages',
              'AI chat assistant',
              'Team features',
              'Priority support',
            ].map((f) => (
              <li key={f} className="plan-feature">
                <span className="plan-feature-check">✓</span>{f}
              </li>
            ))}
            {status?.plan === 'enterprise' && isActive && [
              { label: 'Unlimited messages', soon: false },
              { label: 'AI chat assistant', soon: false },
              { label: 'Multi-agent website builder', soon: false },
              { label: 'Background tasks', soon: false },
              { label: 'Scheduled tasks', soon: true },
              { label: 'Appointment booking', soon: true },
              { label: 'Priority support', soon: false },
            ].map(({ label, soon }) => (
              <li key={label} className="plan-feature">
                <span className="plan-feature-check">✓</span>
                {label}
                {soon && <span className="badge-coming-soon">coming soon</span>}
              </li>
            ))}
          </ul>
        </div>

        <p className="billing-note">
          Questions? Email us at{' '}
          <a href="mailto:support@zeusai.co.uk" className="auth-link">
            support@zeusai.co.uk
          </a>
        </p>
      </div>
    </div>
  );
}
