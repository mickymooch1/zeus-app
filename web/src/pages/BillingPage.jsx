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
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);
  const [deleteLoading, setDeleteLoading] = useState(false);
  const [deleteSuccess, setDeleteSuccess] = useState(false);
  const [showCancelConfirm, setShowCancelConfirm] = useState(false);
  const [cancelLoading, setCancelLoading] = useState(false);
  const [cancelResult, setCancelResult] = useState(null);

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

  const handleCancel = async () => {
    setCancelLoading(true);
    try {
      const res = await fetch(`${BACKEND_URL}/api/subscription/cancel`, {
        method: 'POST',
        headers: { Authorization: `Bearer ${token}` },
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || 'Cancellation failed');
      setCancelResult(data);
      setShowCancelConfirm(false);
      setStatus((prev) => prev ? { ...prev, cancel_at: data.cancel_at } : prev);
    } catch (err) {
      setError(err.message);
    } finally {
      setCancelLoading(false);
    }
  };

  const handleDeleteRequest = async () => {
    setDeleteLoading(true);
    try {
      const res = await fetch(`${BACKEND_URL}/api/account/delete-request`, {
        method: 'POST',
        headers: { Authorization: `Bearer ${token}` },
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || 'Request failed');
      setDeleteSuccess(true);
      setShowDeleteConfirm(false);
    } catch (err) {
      setError(err.message);
    } finally {
      setDeleteLoading(false);
    }
  };

  const isAdmin = status?.is_admin === true;
  const isActive = status?.is_active || isAdmin;
  const effectivePlan = isAdmin ? 'enterprise' : status?.plan;
  const planName = isAdmin ? 'Enterprise (Admin)' : (status?.plan_name || 'Free');

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
            {effectivePlan === 'pro' && <span className="badge-pro">Pro</span>}
            {effectivePlan === 'agency' && <span className="badge-agency">Agency</span>}
            {effectivePlan === 'enterprise' && <span className="badge-enterprise">Enterprise</span>}
            {effectivePlan === 'music_starter' && <span className="badge-pro">Music Starter</span>}
            {effectivePlan === 'music_pro' && <span className="badge-pro">Music Pro</span>}
            {effectivePlan === 'music_agency' && <span className="badge-agency">Music Agency</span>}
            {(!effectivePlan || !isActive) && <span className="badge-free">Free</span>}
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

          {/* Cancel subscription */}
          {(() => {
            const cancelAt = cancelResult?.cancel_at || status?.cancel_at;
            const cancelDateDisplay = cancelAt
              ? new Date(cancelAt).toLocaleDateString('en-GB', { day: 'numeric', month: 'long', year: 'numeric' })
              : null;
            if (cancelDateDisplay) {
              return (
                <p style={{ marginTop: 12, fontSize: '0.85rem', color: '#64748b' }}>
                  Subscription cancels on {cancelDateDisplay}
                </p>
              );
            }
            if (isActive && !isAdmin) {
              return (
                <button
                  className="btn"
                  style={{ marginTop: 12, background: 'transparent', border: '1px solid rgba(255,255,255,0.15)', color: '#94a3b8', padding: '6px 14px', borderRadius: 6, cursor: 'pointer', fontSize: '0.8rem' }}
                  onClick={() => setShowCancelConfirm(true)}
                >
                  Cancel Subscription
                </button>
              );
            }
            return null;
          })()}
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

            <h2 className="billing-section-title" style={{ marginTop: '2rem' }}>Music-only plans</h2>
            <p style={{ fontSize: '0.85rem', color: '#888', marginBottom: '1rem' }}>
              All the music tools — no website builder needed.
            </p>
            <div className="billing-upgrade-grid">
              <div className="billing-upgrade-card">
                <span className="badge-pro">Music Starter</span>
                <div className="billing-upgrade-price">£9/mo</div>
                <p className="billing-upgrade-desc">15 songs/month, YouTube upload</p>
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
                <p className="billing-upgrade-desc">80 songs/month, YouTube upload, 10 avatar videos</p>
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
            {(!status?.plan || !isActive) && [
              '20 messages per month',
              '0 website builds',
              'AI chat assistant',
            ].map((f) => (
              <li key={f} className="plan-feature">
                <span className="plan-feature-check">✓</span>{f}
              </li>
            ))}
            {effectivePlan === 'pro' && isActive && [
              'Unlimited messages',
              '5 website builds/month',
              'AI chat assistant',
              'Priority support',
            ].map((f) => (
              <li key={f} className="plan-feature">
                <span className="plan-feature-check">✓</span>{f}
              </li>
            ))}
            {effectivePlan === 'agency' && isActive && [
              'Unlimited messages',
              '10 website builds/month',
              'AI chat assistant',
              'Team features',
              'Priority support',
            ].map((f) => (
              <li key={f} className="plan-feature">
                <span className="plan-feature-check">✓</span>{f}
              </li>
            ))}
            {effectivePlan === 'enterprise' && isActive && [
              'Unlimited messages',
              '20 website builds/month',
              'Multi-agent website builder',
              'Background tasks',
              'Scheduled tasks',
              'Appointment booking',
              'Priority support',
            ].map((f) => (
              <li key={f} className="plan-feature">
                <span className="plan-feature-check">✓</span>{f}
              </li>
            ))}
            {effectivePlan === 'music_starter' && isActive && [
              '15 AI songs/month',
              'YouTube upload',
              'Song download & share',
              'All music genres & styles',
            ].map((f) => (
              <li key={f} className="plan-feature">
                <span className="plan-feature-check">✓</span>{f}
              </li>
            ))}
            {effectivePlan === 'music_pro' && isActive && [
              '40 AI songs/month',
              'YouTube upload',
              '3 avatar videos/month',
              'Song download & share',
              'All music genres & styles',
            ].map((f) => (
              <li key={f} className="plan-feature">
                <span className="plan-feature-check">✓</span>{f}
              </li>
            ))}
            {effectivePlan === 'music_agency' && isActive && [
              '80 AI songs/month',
              'YouTube upload',
              '10 avatar videos/month',
              'Song download & share',
              'All music genres & styles',
            ].map((f) => (
              <li key={f} className="plan-feature">
                <span className="plan-feature-check">✓</span>{f}
              </li>
            ))}
          </ul>
        </div>

        <p className="billing-note">
          Questions? Email us at{' '}
          <a href="mailto:dominic.rowle@yahoo.com" className="auth-link">
            dominic.rowle@yahoo.com
          </a>
          {'. '}
          View our <Link to="/refund-policy" className="auth-link">Refund Policy</Link>.
        </p>

        {/* Danger zone */}
        <div className="billing-card" style={{ borderColor: 'rgba(239,68,68,0.3)', marginTop: '2rem' }}>
          <h2 className="billing-card-title" style={{ color: '#ef4444' }}>Delete Account</h2>
          <p style={{ fontSize: '0.9rem', color: '#94a3b8', marginBottom: '1rem' }}>
            Requesting deletion will permanently remove your account, songs, videos and all
            associated data within 30 days.
          </p>
          {deleteSuccess ? (
            <p style={{ color: '#22c55e', fontSize: '0.9rem' }}>
              Your deletion request has been received. We will delete your account and all associated data within 30 days.
            </p>
          ) : (
            <button
              className="btn"
              style={{ background: 'transparent', border: '1px solid #ef4444', color: '#ef4444', padding: '8px 18px', borderRadius: 6, cursor: 'pointer', fontSize: '0.875rem', fontWeight: 600 }}
              onClick={() => setShowDeleteConfirm(true)}
            >
              Request Account Deletion
            </button>
          )}
        </div>

        {/* Cancel subscription modal */}
        {showCancelConfirm && (
          <div style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.7)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 1000, padding: 20 }}>
            <div style={{ background: '#1a1a2e', border: '1px solid rgba(255,255,255,0.1)', borderRadius: 12, padding: '28px 32px', maxWidth: 420, width: '100%' }}>
              <h3 style={{ margin: '0 0 12px', fontSize: '1.1rem' }}>Cancel subscription?</h3>
              <p style={{ margin: '0 0 24px', color: '#94a3b8', fontSize: '0.9rem', lineHeight: 1.5 }}>
                {status?.cancel_at
                  ? `You'll keep access until ${new Date(status.cancel_at).toLocaleDateString('en-GB', { day: 'numeric', month: 'long', year: 'numeric' })}, then your account moves to the free plan.`
                  : "You'll keep access until the end of your current billing period, then your account moves to the free plan."}
              </p>
              <div style={{ display: 'flex', gap: 12, justifyContent: 'flex-end' }}>
                <button
                  onClick={() => setShowCancelConfirm(false)}
                  style={{ background: 'transparent', border: '1px solid rgba(255,255,255,0.15)', color: '#94a3b8', padding: '8px 18px', borderRadius: 6, cursor: 'pointer', fontSize: '0.875rem' }}
                >
                  Keep subscription
                </button>
                <button
                  onClick={handleCancel}
                  disabled={cancelLoading}
                  style={{ background: '#374151', border: 'none', color: '#fff', padding: '8px 18px', borderRadius: 6, cursor: cancelLoading ? 'not-allowed' : 'pointer', fontSize: '0.875rem', fontWeight: 600, opacity: cancelLoading ? 0.7 : 1 }}
                >
                  {cancelLoading ? 'Cancelling…' : 'Yes, cancel'}
                </button>
              </div>
            </div>
          </div>
        )}

        {/* Confirmation modal */}
        {showDeleteConfirm && (
          <div style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.7)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 1000, padding: 20 }}>
            <div style={{ background: '#1a1a2e', border: '1px solid rgba(239,68,68,0.4)', borderRadius: 12, padding: '28px 32px', maxWidth: 420, width: '100%' }}>
              <h3 style={{ margin: '0 0 12px', color: '#ef4444', fontSize: '1.1rem' }}>Are you sure?</h3>
              <p style={{ margin: '0 0 24px', color: '#94a3b8', fontSize: '0.9rem', lineHeight: 1.5 }}>
                This cannot be undone. Your account, songs, videos and all associated data will be permanently deleted within 30 days.
              </p>
              <div style={{ display: 'flex', gap: 12, justifyContent: 'flex-end' }}>
                <button
                  onClick={() => setShowDeleteConfirm(false)}
                  style={{ background: 'transparent', border: '1px solid rgba(255,255,255,0.15)', color: '#94a3b8', padding: '8px 18px', borderRadius: 6, cursor: 'pointer', fontSize: '0.875rem' }}
                >
                  Cancel
                </button>
                <button
                  onClick={handleDeleteRequest}
                  disabled={deleteLoading}
                  style={{ background: '#ef4444', border: 'none', color: '#fff', padding: '8px 18px', borderRadius: 6, cursor: deleteLoading ? 'not-allowed' : 'pointer', fontSize: '0.875rem', fontWeight: 600, opacity: deleteLoading ? 0.7 : 1 }}
                >
                  {deleteLoading ? 'Submitting…' : 'Yes, request deletion'}
                </button>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
