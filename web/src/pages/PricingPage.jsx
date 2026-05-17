import { useEffect, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { Navbar } from '../components/Navbar';
import { useAuth } from '../contexts/AuthContext';

const BACKEND_URL = import.meta.env.VITE_BACKEND_URL || '';

const FREE_FEATURES = [
  '20 messages per month',
  '0 website builds',
  'AI chat assistant',
  'Content & copy writing',
  'Web research',
  '5 free songs on signup',
];

const DEFAULT_PLANS = {
  pro: {
    name: 'Professional',
    price: '£29/mo',
    features: [
      'Unlimited messages',
      '5 website builds/month',
      'AI chat assistant',
      'Content & copy writing',
      'Netlify deployment',
      'AI image generation',
      'Email via Gmail',
      'Client & project CRM',
      'Priority support',
      '20 AI songs/month',
      'AI song download & share',
    ],
  },
  agency: {
    name: 'Agency',
    price: '£79/mo',
    features: [
      'Unlimited messages',
      '10 website builds/month',
      'AI chat assistant',
      'Everything in Pro',
      'Team features',
      'Priority support',
      '80 AI songs/month',
      'YouTube music upload',
      'Explicit content toggle',
      'Google indexing',
      'Facebook posting',
    ],
  },
  enterprise: {
    name: 'Enterprise',
    price: '£150/mo',
    features: [
      'Unlimited messages',
      '20 website builds/month',
      'Multi-agent website builder',
      'Background tasks',
      'Scheduled tasks',
      'Appointment booking',
      'Priority support',
      '100 AI songs/month',
      'All Agency music features',
    ],
  },
};

const DEFAULT_MUSIC_PLANS = {
  music_starter: {
    name: 'Music Starter',
    price: '£9/mo',
    features: [
      '25 AI songs/month',
      'YouTube upload',
      'Song download & share',
      'All music genres & styles',
      'No website builder',
    ],
  },
  music_pro: {
    name: 'Music Pro',
    price: '£19/mo',
    features: [
      '55 AI songs/month',
      'YouTube upload',
      '3 avatar videos/month',
      'Song download & share',
      'All music genres & styles',
      'No website builder',
    ],
  },
  music_agency: {
    name: 'Music Agency',
    price: '£39/mo',
    features: [
      '110 AI songs/month',
      'YouTube upload',
      '10 avatar videos/month',
      'Song download & share',
      'All music genres & styles',
      'No website builder',
    ],
  },
};

export default function PricingPage() {
  const { user, token } = useAuth();
  const navigate = useNavigate();
  const [plans, setPlans] = useState(DEFAULT_PLANS);
  const [loadingPlan, setLoadingPlan] = useState(null);
  const [error, setError] = useState('');

  useEffect(() => {
    fetch(`${BACKEND_URL}/billing/plans`)
      .then((r) => r.ok ? r.json() : null)
      .then((data) => { if (data) setPlans(data); })
      .catch(() => {});
  }, []);

  const handleCheckout = async (planKey) => {
    if (!user) {
      navigate('/register');
      return;
    }
    setError('');
    setLoadingPlan(planKey);
    try {
      const res = await fetch(`${BACKEND_URL}/billing/checkout`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({ plan: planKey }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || 'Failed to create checkout');
      window.location.href = data.url;
    } catch (err) {
      setError(err.message);
      setLoadingPlan(null);
    }
  };

  const currentPlan = user?.subscription_plan;
  const isActive = user?.subscription_status === 'active';

  return (
    <div className="pricing-page">
      <Navbar />
      <div className="hero-orbs" aria-hidden>
        <div className="orb orb-1" />
        <div className="orb orb-2" />
      </div>

      <div className="page pricing-page-inner">
        <div className="section-label" style={{ textAlign: 'center' }}>Pricing</div>
        <h1 className="section-title" style={{ textAlign: 'center', marginBottom: '0.5rem' }}>
          Simple, honest pricing
        </h1>
        <p className="section-sub" style={{ textAlign: 'center', marginBottom: '3rem' }}>
          Start free. No credit card required. Upgrade when you're ready.
        </p>

        {error && <div className="form-error form-error--banner" style={{ marginBottom: '1.5rem' }}>{error}</div>}

        <div className="pricing-grid">
          {/* Free tier */}
          <div className="pricing-card">
            <div className="pricing-card-header">
              <span className="badge-free">Free</span>
              <div className="pricing-price">£0</div>
              <p className="pricing-desc">Try Zeus with no commitment</p>
            </div>
            <ul className="pricing-features">
              {FREE_FEATURES.map((f) => (
                <li key={f} className="plan-feature">
                  <span className="plan-feature-check">✓</span>
                  {f}
                </li>
              ))}
            </ul>
            <div className="pricing-card-footer">
              {user ? (
                <Link to="/dashboard" className="btn btn-outline btn-full">
                  Go to Dashboard
                </Link>
              ) : (
                <Link to="/register" className="btn btn-outline btn-full">
                  Start Free
                </Link>
              )}
            </div>
          </div>

          {/* Pro tier */}
          <div className="pricing-card pricing-card--popular">
            <div className="pricing-popular-badge">MOST POPULAR</div>
            <div className="pricing-card-header">
              <span className="badge-pro">Pro</span>
              <div className="pricing-price">{plans.pro?.price || '£29/mo'}</div>
              <p className="pricing-desc">Everything you need to run your business</p>
            </div>
            <ul className="pricing-features">
              {(plans.pro?.features || DEFAULT_PLANS.pro.features).map((f) => (
                <li key={f} className="plan-feature">
                  <span className="plan-feature-check">✓</span>
                  {f}
                </li>
              ))}
            </ul>
            <div className="pricing-card-footer">
              {isActive && currentPlan === 'pro' ? (
                <Link to="/billing" className="btn btn-primary btn-full">
                  Current Plan
                </Link>
              ) : (
                <button
                  className="btn btn-primary btn-full"
                  disabled={loadingPlan === 'pro'}
                  onClick={() => handleCheckout('pro')}
                >
                  {loadingPlan === 'pro' ? <span className="spinner spinner--inline" /> : 'Upgrade to Pro'}
                </button>
              )}
            </div>
          </div>

          {/* Agency tier */}
          <div className="pricing-card">
            <div className="pricing-card-header">
              <span className="badge-agency">Agency</span>
              <div className="pricing-price">{plans.agency?.price || '£79/mo'}</div>
              <p className="pricing-desc">For teams and growing agencies</p>
            </div>
            <ul className="pricing-features">
              {(plans.agency?.features || DEFAULT_PLANS.agency.features).map((f) => (
                <li key={f} className="plan-feature">
                  <span className="plan-feature-check">✓</span>
                  {f}
                </li>
              ))}
            </ul>
            <div className="pricing-card-footer">
              {isActive && currentPlan === 'agency' ? (
                <Link to="/billing" className="btn btn-outline btn-full">
                  Current Plan
                </Link>
              ) : (
                <button
                  className="btn btn-outline btn-full"
                  disabled={loadingPlan === 'agency'}
                  onClick={() => handleCheckout('agency')}
                >
                  {loadingPlan === 'agency' ? <span className="spinner spinner--inline" /> : 'Upgrade to Agency'}
                </button>
              )}
            </div>
          </div>

          {/* Enterprise tier */}
          <div className="pricing-card">
            <div className="pricing-card-header">
              <span className="badge-enterprise">Enterprise</span>
              <div className="pricing-price">{plans.enterprise?.price || '£150/mo'}</div>
              <p className="pricing-desc">Advanced automation for power users</p>
            </div>
            <ul className="pricing-features">
              {(plans.enterprise?.features || DEFAULT_PLANS.enterprise.features).map((f) => (
                <li key={f} className="plan-feature">
                  <span className="plan-feature-check">✓</span>
                  {f}
                </li>
              ))}
            </ul>
            <div className="pricing-card-footer">
              {isActive && currentPlan === 'enterprise' ? (
                <Link to="/billing" className="btn btn-outline btn-full">
                  Current Plan
                </Link>
              ) : (
                <button
                  className="btn btn-outline btn-full"
                  disabled={loadingPlan === 'enterprise'}
                  onClick={() => handleCheckout('enterprise')}
                >
                  {loadingPlan === 'enterprise' ? <span className="spinner spinner--inline" /> : 'Upgrade to Enterprise'}
                </button>
              )}
            </div>
          </div>
        </div>

        <p className="pricing-footer-note">
          All plans include a 7-day free trial. Cancel anytime. Prices in GBP (+ VAT where applicable).
        </p>

        {/* ── Music Plans ──────────────────────────────────────────────────── */}
        <div style={{ marginTop: '5rem' }}>
          <div className="section-label" style={{ textAlign: 'center' }}>Music Plans</div>
          <h2 className="section-title" style={{ textAlign: 'center', marginBottom: '0.5rem' }}>
            For music creators
          </h2>
          <p className="section-sub" style={{ textAlign: 'center', marginBottom: '3rem' }}>
            All the music tools — no website builder needed.
          </p>

          <div className="pricing-grid" style={{ maxWidth: 860, margin: '0 auto' }}>
            {/* Music Starter */}
            <div className="pricing-card">
              <div className="pricing-card-header">
                <span className="badge-pro">Music Starter</span>
                <div className="pricing-price">{plans.music_starter?.price || DEFAULT_MUSIC_PLANS.music_starter.price}</div>
                <p className="pricing-desc">Perfect for solo artists getting started</p>
              </div>
              <ul className="pricing-features">
                {(plans.music_starter?.features || DEFAULT_MUSIC_PLANS.music_starter.features).map((f) => (
                  <li key={f} className="plan-feature">
                    <span className="plan-feature-check">✓</span>{f}
                  </li>
                ))}
              </ul>
              <div className="pricing-card-footer">
                {isActive && currentPlan === 'music_starter' ? (
                  <Link to="/billing" className="btn btn-primary btn-full">Current Plan</Link>
                ) : (
                  <button
                    className="btn btn-primary btn-full"
                    disabled={loadingPlan === 'music_starter'}
                    onClick={() => handleCheckout('music_starter')}
                  >
                    {loadingPlan === 'music_starter' ? <span className="spinner spinner--inline" /> : 'Get Music Starter'}
                  </button>
                )}
              </div>
            </div>

            {/* Music Pro */}
            <div className="pricing-card pricing-card--popular">
              <div className="pricing-popular-badge">BEST VALUE</div>
              <div className="pricing-card-header">
                <span className="badge-pro">Music Pro</span>
                <div className="pricing-price">{plans.music_pro?.price || DEFAULT_MUSIC_PLANS.music_pro.price}</div>
                <p className="pricing-desc">For active creators who want avatar videos</p>
              </div>
              <ul className="pricing-features">
                {(plans.music_pro?.features || DEFAULT_MUSIC_PLANS.music_pro.features).map((f) => (
                  <li key={f} className="plan-feature">
                    <span className="plan-feature-check">✓</span>{f}
                  </li>
                ))}
              </ul>
              <div className="pricing-card-footer">
                {isActive && currentPlan === 'music_pro' ? (
                  <Link to="/billing" className="btn btn-primary btn-full">Current Plan</Link>
                ) : (
                  <button
                    className="btn btn-primary btn-full"
                    disabled={loadingPlan === 'music_pro'}
                    onClick={() => handleCheckout('music_pro')}
                  >
                    {loadingPlan === 'music_pro' ? <span className="spinner spinner--inline" /> : 'Get Music Pro'}
                  </button>
                )}
              </div>
            </div>

            {/* Music Agency */}
            <div className="pricing-card">
              <div className="pricing-card-header">
                <span className="badge-agency">Music Agency</span>
                <div className="pricing-price">{plans.music_agency?.price || DEFAULT_MUSIC_PLANS.music_agency.price}</div>
                <p className="pricing-desc">For prolific creators and label teams</p>
              </div>
              <ul className="pricing-features">
                {(plans.music_agency?.features || DEFAULT_MUSIC_PLANS.music_agency.features).map((f) => (
                  <li key={f} className="plan-feature">
                    <span className="plan-feature-check">✓</span>{f}
                  </li>
                ))}
              </ul>
              <div className="pricing-card-footer">
                {isActive && currentPlan === 'music_agency' ? (
                  <Link to="/billing" className="btn btn-outline btn-full">Current Plan</Link>
                ) : (
                  <button
                    className="btn btn-outline btn-full"
                    disabled={loadingPlan === 'music_agency'}
                    onClick={() => handleCheckout('music_agency')}
                  >
                    {loadingPlan === 'music_agency' ? <span className="spinner spinner--inline" /> : 'Get Music Agency'}
                  </button>
                )}
              </div>
            </div>
          </div>

          <p className="pricing-footer-note" style={{ marginTop: '2rem' }}>
            Music plans do not include website building. Song top-ups available on all plans. Cancel anytime.
          </p>
        </div>

        {/* PAYG */}
        <div style={{ marginTop: '5rem', textAlign: 'center' }}>
          <div className="section-label" style={{ textAlign: 'center' }}>Pay As You Go</div>
          <h2 className="section-title" style={{ textAlign: 'center', marginBottom: '0.5rem' }}>
            No subscription needed
          </h2>
          <p className="section-sub" style={{ textAlign: 'center', marginBottom: '2.5rem' }}>
            Buy song credits whenever you need them. Credits never expire.
          </p>
          <div style={{ display: 'flex', gap: 20, justifyContent: 'center', flexWrap: 'wrap', maxWidth: 540, margin: '0 auto' }}>
            {[
              { label: '2 songs', price: '£0.99' },
              { label: '5 songs', price: '£2.00' },
              { label: '10 songs', price: '£4.00' },
            ].map(({ label, price }) => (
              <div
                key={label}
                style={{ flex: '1 1 140px', maxWidth: 160, padding: '24px 16px', borderRadius: 14, border: '1px solid rgba(139,92,246,0.3)', background: 'rgba(139,92,246,0.05)', textAlign: 'center' }}
              >
                <div style={{ fontSize: 28, fontWeight: 800, color: '#a78bfa', marginBottom: 6 }}>{price}</div>
                <div style={{ fontSize: 14, color: '#94a3b8', marginBottom: 20 }}>{label}</div>
                <button
                  className="btn btn-outline btn-full"
                  onClick={() => navigate(user ? '/billing' : '/register')}
                >
                  Buy Now
                </button>
              </div>
            ))}
          </div>
          <p className="pricing-footer-note" style={{ marginTop: '2rem' }}>
            Credits never expire. Use them anytime. Purchased after sign-in.
          </p>
        </div>
      </div>
    </div>
  );
}
