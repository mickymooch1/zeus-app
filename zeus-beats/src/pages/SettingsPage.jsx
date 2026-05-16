import { useEffect, useState } from 'react';
import { Link, useLocation } from 'react-router-dom';
import { Navbar } from '../components/Navbar';
import { useAuth } from '../contexts/AuthContext';

const BACKEND_URL = import.meta.env.VITE_BACKEND_URL || '';

function UsageBar({ used, limit }) {
  if (limit === null || limit === undefined) {
    return (
      <div className="usage-bar-wrap">
        <div className="usage-bar"><div className="usage-bar-fill usage-bar-fill--unlimited" style={{ width: '100%' }} /></div>
        <span className="usage-label">Unlimited messages</span>
      </div>
    );
  }
  const pct = Math.min(100, (used / limit) * 100);
  const isNearLimit = pct >= 75;
  return (
    <div className="usage-bar-wrap">
      <div className="usage-bar">
        <div className={`usage-bar-fill${isNearLimit ? ' usage-bar-fill--warn' : ''}`} style={{ width: `${pct}%` }} />
      </div>
      <span className="usage-label">{used} / {limit} messages this month</span>
    </div>
  );
}

function CreditBar({ balance, allowance, isAdmin }) {
  if (isAdmin) return <span className="usage-label">Unlimited (admin)</span>;
  const pct = allowance > 0 ? Math.min(100, (balance / allowance) * 100) : 0;
  const barColor = pct > 30 ? '#a78bfa' : pct > 10 ? '#fbbf24' : '#f87171';
  return (
    <div className="usage-bar-wrap">
      <div className="usage-bar"><div className="usage-bar-fill" style={{ width: `${pct}%`, background: barColor }} /></div>
      <span className="usage-label">{balance} / {allowance} songs remaining this month</span>
    </div>
  );
}

const SONG_PACKS = [
  { pack: 'song_pack_10',  label: '10 songs', price: '£8'  },
  { pack: 'song_pack_50',  label: '50 songs', price: '£30' },
  { pack: 'song_pack_200', label: '200 songs', price: '£99' },
];

export default function SettingsPage() {
  const { user, token } = useAuth();
  const location = useLocation();
  const [status, setStatus] = useState(null);
  const [credits, setCredits] = useState(null);
  const [loadingPortal, setLoadingPortal] = useState(false);
  const [loadingCheckout, setLoadingCheckout] = useState(null);
  const [topupLoading, setTopupLoading] = useState(null);
  const [error, setError] = useState('');
  const [successMsg, setSuccessMsg] = useState('');

  const successParam = new URLSearchParams(location.search).get('success');
  const topupSuccess = new URLSearchParams(location.search).get('topup') === 'success';

  useEffect(() => {
    if (successParam === 'true') setSuccessMsg('Payment successful! Your plan is being activated.');
    if (topupSuccess) setSuccessMsg('Payment successful — your song credits have been added.');
  }, [successParam, topupSuccess]);

  useEffect(() => {
    if (!token) return;
    fetch(`${BACKEND_URL}/billing/status`, { headers: { Authorization: `Bearer ${token}` } })
      .then(r => r.ok ? r.json() : null)
      .then(data => { if (data) setStatus(data); })
      .catch(() => {});
    fetch(`${BACKEND_URL}/api/users/me/song_credits`, { headers: { Authorization: `Bearer ${token}` } })
      .then(r => r.ok ? r.json() : null)
      .then(data => { if (data) setCredits(data); })
      .catch(() => {});
  }, [token]);

  const handlePortal = async () => {
    setError(''); setLoadingPortal(true);
    try {
      const res = await fetch(`${BACKEND_URL}/billing/portal`, { headers: { Authorization: `Bearer ${token}` } });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || 'Failed to open billing portal');
      window.location.href = data.url;
    } catch (err) { setError(err.message); setLoadingPortal(false); }
  };

  const handleCheckout = async (plan) => {
    setError(''); setLoadingCheckout(plan);
    try {
      const res = await fetch(`${BACKEND_URL}/billing/checkout`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
        body: JSON.stringify({ plan }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || 'Failed to create checkout');
      window.location.href = data.url;
    } catch (err) { setError(err.message); setLoadingCheckout(null); }
  };

  const handleTopup = async (pack) => {
    setTopupLoading(pack);
    try {
      const r = await fetch(`${BACKEND_URL}/api/songs/topup`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
        body: JSON.stringify({ pack }),
      });
      const d = await r.json();
      if (!r.ok) throw new Error(d.detail || 'Checkout failed');
      window.location.href = d.url;
    } catch (e) { setError(e.message); setTopupLoading(null); }
  };

  const isAdmin = status?.is_admin === true;
  const isActive = status?.is_active || isAdmin;
  const effectivePlan = isAdmin ? 'enterprise' : status?.plan;
  const planName = isAdmin ? 'Enterprise (Admin)' : (status?.plan_name || 'Free');
  const isMusicPlan = ['music_starter', 'music_pro', 'music_agency'].includes(effectivePlan);

  return (
    <div className="landing settings-page">
      <Navbar />
      <div className="page">
        <div className="hero-orbs" aria-hidden><div className="orb orb-2" /></div>

        <h1 className="billing-title">Settings</h1>

        {successMsg && <div className="success-banner">{successMsg}</div>}
        {error && <div className="form-error form-error--banner">{error}</div>}

        {/* Section 1: Account info */}
        <div className="billing-card">
          <div className="billing-card-header">
            <h2 className="billing-card-title">Account</h2>
            {isMusicPlan && effectivePlan === 'music_starter' && <span className="badge-pro">Music Starter</span>}
            {isMusicPlan && effectivePlan === 'music_pro' && <span className="badge-pro">Music Pro</span>}
            {isMusicPlan && effectivePlan === 'music_agency' && <span className="badge-agency">Music Agency</span>}
            {!effectivePlan || !isActive ? <span className="badge-free">Free</span> : null}
            {isAdmin && <span className="badge-enterprise">Admin</span>}
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
            <div style={{ fontSize: 14, color: 'var(--text-dim)' }}>
              <strong style={{ color: 'var(--text)' }}>Name:</strong> {user?.name || '—'}
            </div>
            <div style={{ fontSize: 14, color: 'var(--text-dim)' }}>
              <strong style={{ color: 'var(--text)' }}>Email:</strong> {user?.email || '—'}
            </div>
            <div style={{ fontSize: 14, color: 'var(--text-dim)' }}>
              <strong style={{ color: 'var(--text)' }}>Plan:</strong> {planName}
            </div>
          </div>
        </div>

        {/* Section 2: Subscription / Messages */}
        <div className="billing-card">
          <h2 className="billing-card-title">Subscription</h2>
          {status ? (
            <UsageBar used={status.messages_used} limit={status.messages_limit} />
          ) : (
            <div className="spinner" style={{ margin: '16px 0' }} />
          )}
          <div className="billing-actions">
            {isActive && user?.stripe_customer_id && (
              <button className="btn btn-outline" onClick={handlePortal} disabled={loadingPortal}>
                {loadingPortal ? <span className="spinner spinner--inline" /> : 'Manage Subscription'}
              </button>
            )}
            {!isActive && (
              <Link to="/pricing" className="btn btn-primary">Upgrade Plan</Link>
            )}
          </div>
        </div>

        {/* Section 3: Song Credits */}
        <div className="billing-card">
          <h2 className="billing-card-title">Song Credits</h2>
          {credits ? (
            <CreditBar balance={credits.balance} allowance={credits.monthly_allowance} isAdmin={credits.is_admin} />
          ) : (
            <div className="spinner" style={{ margin: '16px 0' }} />
          )}
          <div style={{ marginTop: 20 }}>
            <p style={{ fontSize: 13, color: 'var(--text-dim)', marginBottom: 12 }}>Need more songs? Buy a top-up pack:</p>
            <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
              {SONG_PACKS.map(({ pack, label, price }) => (
                <button
                  key={pack}
                  onClick={() => handleTopup(pack)}
                  disabled={topupLoading !== null}
                  className="btn btn-outline btn-sm"
                >
                  {topupLoading === pack ? <span className="spinner spinner--inline" /> : `${label} — ${price}`}
                </button>
              ))}
            </div>
          </div>
        </div>

        {/* Section 4: Upgrade cards (only for non-active / free users) */}
        {!isActive && (
          <div>
            <h2 className="billing-section-title">Upgrade to a Music Plan</h2>
            <div className="billing-upgrade-grid">
              {[
                { plan: 'music_starter', name: 'Music Starter', price: '£9/mo', desc: '15 songs/month, YouTube upload', badge: 'badge-pro' },
                { plan: 'music_pro', name: 'Music Pro', price: '£19/mo', desc: '40 songs/month, YouTube upload, 3 avatar videos', badge: 'badge-pro' },
                { plan: 'music_agency', name: 'Music Agency', price: '£39/mo', desc: '80 songs/month, YouTube upload, 10 avatar videos', badge: 'badge-agency' },
              ].map(({ plan, name, price, desc, badge }) => (
                <div key={plan} className="billing-upgrade-card">
                  <span className={badge}>{name}</span>
                  <div className="billing-upgrade-price">{price}</div>
                  <p className="billing-upgrade-desc">{desc}</p>
                  <button
                    className="btn btn-primary btn-full"
                    disabled={loadingCheckout === plan}
                    onClick={() => handleCheckout(plan)}
                  >
                    {loadingCheckout === plan ? <span className="spinner spinner--inline" /> : `Get ${name}`}
                  </button>
                </div>
              ))}
            </div>
          </div>
        )}

        <p className="billing-note">
          Questions? Email <a href="mailto:hello@zeusbeats.com" className="auth-link">hello@zeusbeats.com</a>
        </p>
      </div>

      <footer className="footer">
        <p>© 2025 Zeus Beats</p>
        <div className="footer-links">
          <Link to="/" className="footer-link">Home</Link>
          <Link to="/pricing" className="footer-link">Pricing</Link>
          <Link to="/terms" className="footer-link">Terms</Link>
          <Link to="/privacy" className="footer-link">Privacy</Link>
        </div>
      </footer>
    </div>
  );
}
