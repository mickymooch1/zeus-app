import { useEffect, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { Navbar } from '../components/Navbar';
import { useAuth } from '../contexts/AuthContext';

const BACKEND_URL = import.meta.env.VITE_BACKEND_URL || '';

const FREE_FEATURES = [
  '20 messages to explore Zeus',
  'Website builder',
  'Content & copy writing',
  'Email drafting',
  'Business advice',
];

const DEFAULT_PLANS = {
  pro: {
    name: 'Professional',
    price: '£29/mo',
    features: [
      'Unlimited messages',
      'Persistent memory & learning',
      'Client & project tracking',
      'Website builder',
      'Email drafting',
      'Content & copy generation',
      'Netlify deployment integration',
      'Business operations assistant',
      'Priority response',
    ],
  },
  agency: {
    name: 'Agency',
    price: '£79/mo',
    features: [
      'Everything in Professional',
      'Team features (coming soon)',
      'Multiple workspaces (coming soon)',
      'Priority support',
      'Custom integrations',
      'White-label options (coming soon)',
      'Dedicated account manager',
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
        </div>

        <p className="pricing-footer-note">
          All plans include a 7-day free trial. Cancel anytime. Prices in GBP (+ VAT where applicable).
        </p>
      </div>
    </div>
  );
}
