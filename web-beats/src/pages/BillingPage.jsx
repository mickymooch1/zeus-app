import { useEffect, useState } from 'react';
import { Link, useLocation } from 'react-router-dom';
import { BeatsNavbar } from '../components/BeatsNavbar';
import { useAuth } from '../contexts/AuthContext';
import { BACKEND_URL } from '../brand';

function UsageBar({ used, limit }) {
  if (limit === null || limit === undefined) {
    return (
      <div className="usage-bar-wrap">
        <div className="usage-bar">
          <div className="usage-bar-fill usage-bar-fill--unlimited" style={{ width: '100%' }} />
        </div>
        <span className="usage-label">Unlimited</span>
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
      <span className="usage-label">{used} / {limit} songs this month</span>
    </div>
  );
}

export default function BillingPage() {
  const { user, token } = useAuth();
  const location = useLocation();
  const [status, setStatus]           = useState(null);
  const [credits, setCredits]         = useState(null);
  const [loadingPortal, setLoadingPortal]     = useState(false);
  const [loadingCheckout, setLoadingCheckout] = useState(null);
  const [error, setError]             = useState('');
  const [successMsg, setSuccessMsg]   = useState('');

  const successParam = new URLSearchParams(location.search).get('success');
  const ytParam      = new URLSearchParams(location.search).get('youtube');

  useEffect(() => {
    if (successParam === 'true') {
      setSuccessMsg('Payment successful! Your plan is being activated.');
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

    fetch(`${BACKEND_URL}/api/users/me/song_credits`, {
      headers: { Authorization: `Bearer ${token}` },
    })
      .then((r) => r.ok ? r.json() : null)
      .then((data) => { if (data) setCredits(data); })
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
        headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
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

  const handleConnectYouTube = () => {
    window.location.href = `${BACKEND_URL}/api/youtube/auth?token=${token}`;
  };

  const isAdmin       = status?.is_admin === true;
  const isActive      = status?.is_active || isAdmin;
  const effectivePlan = isAdmin ? 'enterprise' : status?.plan;
  const planName      = isAdmin ? 'Enterprise (Admin)' : (status?.plan_name || 'Free');
  const ytConnected   = credits?.youtube_connected || false;
  const songBalance   = credits?.balance ?? 0;
  const songAllowance = credits?.monthly_allowance ?? 0;
  const isMusicPlan   = ['music_starter', 'music_pro', 'music_agency'].includes(effectivePlan);
  const canFacebook   = isAdmin || effectivePlan === 'music_agency';

  const PLAN_FEATURES = {
    music_starter: ['15 AI songs/month', 'YouTube upload', 'Song download & share', 'All 20+ genres & styles', 'AI cover art'],
    music_pro:     ['40 AI songs/month', 'YouTube upload', '3 avatar lip-sync videos/month', 'Song download & share', 'All 20+ genres & styles', 'AI cover art'],
    music_agency:  ['80 AI songs/month', 'YouTube upload', '10 avatar lip-sync videos/month', 'Song download & share', 'All 20+ genres & styles', 'AI cover art', 'Facebook posting'],
    free:          ['5 songs/month (free tier)', 'Song download & share', 'All genres'],
  };
  const planFeatures = (isMusicPlan && isActive)
    ? PLAN_FEATURES[effectivePlan]
    : PLAN_FEATURES.free;

  return (
    <div className="billing-page">
      <BeatsNavbar />
      <div className="page billing-page-inner">
        <div className="hero-orbs" aria-hidden>
          <div className="orb orb-2" />
        </div>

        <h1 className="billing-title">Billing &amp; Subscription</h1>

        {successMsg && <div className="success-banner">{successMsg}</div>}
        {ytParam === 'connected' && (
          <div className="success-banner">YouTube connected — you can now upload songs directly to your channel.</div>
        )}
        {ytParam === 'error' && (
          <div className="form-error form-error--banner">YouTube connection failed — please try again.</div>
        )}
        {error && <div className="form-error form-error--banner">{error}</div>}

        {/* Current plan card */}
        <div className="billing-card">
          <div className="billing-card-header">
            <h2 className="billing-card-title">Current Plan</h2>
            {effectivePlan === 'music_starter' && <span className="badge-pro">Music Starter</span>}
            {effectivePlan === 'music_pro'     && <span className="badge-pro">Music Pro</span>}
            {effectivePlan === 'music_agency'  && <span className="badge-agency">Music Agency</span>}
            {(!isMusicPlan && !isAdmin) && <span className="badge-free">Free</span>}
            {isAdmin && <span className="badge-enterprise">Admin</span>}
          </div>

          <div className="billing-plan-name">{planName}</div>

          {credits ? (
            <UsageBar used={songBalance} limit={isAdmin ? null : songAllowance} />
          ) : (
            <div className="spinner" />
          )}

          <div className="billing-actions">
            {isActive && user?.stripe_customer_id ? (
              <button className="btn btn-outline" onClick={handlePortal} disabled={loadingPortal}>
                {loadingPortal ? <span className="spinner spinner--inline" /> : 'Manage Subscription'}
              </button>
            ) : null}
            {!isActive && (
              <Link to="/pricing" className="btn btn-primary">Upgrade Plan</Link>
            )}
          </div>
        </div>

        {/* Upgrade grid — music plans only */}
        {!isActive && (
          <div className="billing-upgrade-section">
            <h2 className="billing-section-title">Choose your music plan</h2>
            <div className="billing-upgrade-grid">
              <div className="billing-upgrade-card">
                <span className="badge-pro">Music Starter</span>
                <div className="billing-upgrade-price">£9/mo</div>
                <p className="billing-upgrade-desc">15 songs/month, YouTube upload, AI cover art</p>
                <button
                  className="btn btn-primary btn-full"
                  disabled={loadingCheckout === 'music_starter'}
                  onClick={() => handleCheckout('music_starter')}
                >
                  {loadingCheckout === 'music_starter' ? <span className="spinner spinner--inline" /> : 'Get Music Starter'}
                </button>
              </div>

              <div className="billing-upgrade-card">
                <span className="badge-pro">Music Pro</span>
                <div className="billing-upgrade-price">£19/mo</div>
                <p className="billing-upgrade-desc">40 songs/month, YouTube upload, 3 avatar videos</p>
                <button
                  className="btn btn-primary btn-full"
                  disabled={loadingCheckout === 'music_pro'}
                  onClick={() => handleCheckout('music_pro')}
                >
                  {loadingCheckout === 'music_pro' ? <span className="spinner spinner--inline" /> : 'Get Music Pro'}
                </button>
              </div>

              <div className="billing-upgrade-card">
                <span className="badge-agency">Music Agency</span>
                <div className="billing-upgrade-price">£39/mo</div>
                <p className="billing-upgrade-desc">80 songs/month, YouTube upload, 10 avatar videos, Facebook posting</p>
                <button
                  className="btn btn-outline btn-full"
                  disabled={loadingCheckout === 'music_agency'}
                  onClick={() => handleCheckout('music_agency')}
                >
                  {loadingCheckout === 'music_agency' ? <span className="spinner spinner--inline" /> : 'Get Music Agency'}
                </button>
              </div>
            </div>
          </div>
        )}

        {/* Plan features */}
        <div className="billing-card">
          <h2 className="billing-card-title">Your plan includes</h2>
          <ul className="pricing-features" style={{ marginTop: '1rem' }}>
            {planFeatures.map((f) => (
              <li key={f} className="plan-feature">
                <span className="plan-feature-check">✓</span>{f}
              </li>
            ))}
          </ul>
        </div>

        {/* Connected Accounts */}
        <div className="billing-card">
          <h2 className="billing-card-title">Connected Accounts</h2>

          {/* YouTube */}
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '16px 0', borderBottom: '1px solid rgba(255,255,255,0.06)' }}>
            <div>
              <div style={{ fontWeight: 600, color: '#e2d9f3', marginBottom: 4 }}>
                ▶ YouTube
              </div>
              <div style={{ fontSize: 13, color: '#666' }}>
                {ytConnected
                  ? 'Connected — upload songs directly to your channel'
                  : 'Connect to upload songs directly to your YouTube channel'}
              </div>
            </div>
            {ytConnected ? (
              <span style={{ background: 'rgba(52,211,153,0.1)', color: '#34d399', border: '1px solid rgba(52,211,153,0.2)', borderRadius: 999, padding: '4px 14px', fontSize: 12, fontWeight: 600 }}>
                Connected
              </span>
            ) : (
              <button
                onClick={handleConnectYouTube}
                disabled={!isActive && !isAdmin}
                className="btn btn-outline"
                style={{ fontSize: 13, padding: '6px 16px' }}
                title={(!isActive && !isAdmin) ? 'Requires an active music plan' : undefined}
              >
                Connect YouTube
              </button>
            )}
          </div>

          {/* Facebook */}
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '16px 0' }}>
            <div>
              <div style={{ fontWeight: 600, color: '#e2d9f3', marginBottom: 4 }}>
                📘 Facebook
              </div>
              <div style={{ fontSize: 13, color: '#666' }}>
                {canFacebook
                  ? 'Facebook posting is enabled on your plan — posts are published automatically via Make.com'
                  : 'Automatic Facebook posting — available on Music Agency plan'}
              </div>
            </div>
            {canFacebook ? (
              <span style={{ background: 'rgba(52,211,153,0.1)', color: '#34d399', border: '1px solid rgba(52,211,153,0.2)', borderRadius: 999, padding: '4px 14px', fontSize: 12, fontWeight: 600 }}>
                Active
              </span>
            ) : (
              <Link to="/pricing" style={{ fontSize: 13, color: '#a855f7', textDecoration: 'none', fontWeight: 500 }}>
                Upgrade →
              </Link>
            )}
          </div>
        </div>

        <p className="billing-note">
          Questions? Email us at{' '}
          <a href="mailto:dominic.rowle@yahoo.com" className="auth-link">
            dominic.rowle@yahoo.com
          </a>
        </p>
      </div>
    </div>
  );
}
