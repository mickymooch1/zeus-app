import { useEffect, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { BeatsNavbar } from '../components/BeatsNavbar';
import { useAuth } from '../contexts/AuthContext';
import { BACKEND_URL } from '../brand';

const DEFAULT_PLANS = {
  music_starter: {
    name: 'Music Starter',
    price: '£9/mo',
    features: [
      '15 AI songs/month',
      'YouTube upload',
      'Song download & share',
      'All 20+ genres & styles',
      'AI cover art',
    ],
  },
  music_pro: {
    name: 'Music Pro',
    price: '£19/mo',
    features: [
      '55 AI songs/month',
      'YouTube upload',
      '3 avatar lip-sync videos/month',
      'Song download & share',
      'All 20+ genres & styles',
      'AI cover art',
    ],
  },
  music_agency: {
    name: 'Music Agency',
    price: '£39/mo',
    features: [
      '110 AI songs/month',
      'YouTube upload',
      '10 avatar lip-sync videos/month',
      'Song download & share',
      'All 20+ genres & styles',
      'AI cover art',
      'Facebook posting',
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
      .then((data) => { if (data) setPlans(prev => ({ ...prev, ...data })); })
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

  const planDefs = [
    { key: 'music_starter', popular: false },
    { key: 'music_pro',     popular: true  },
    { key: 'music_agency',  popular: false },
  ];

  return (
    <div className="pricing-page">
      <BeatsNavbar />
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

        {error && (
          <div className="form-error form-error--banner" style={{ marginBottom: '1.5rem' }}>
            {error}
          </div>
        )}

        <div className="pricing-grid" style={{ maxWidth: 900, margin: '0 auto' }}>
          {planDefs.map(({ key, popular }) => {
            const plan = plans[key] || DEFAULT_PLANS[key];
            const isCurrent = isActive && currentPlan === key;
            return (
              <div key={key} className={`pricing-card${popular ? ' pricing-card--popular' : ''}`}>
                {popular && <div className="pricing-popular-badge">BEST VALUE</div>}
                <div className="pricing-card-header">
                  <span className={`badge-${popular ? 'pro' : 'agency'}`}>{plan.name}</span>
                  <div className="pricing-price">{plan.price}</div>
                  <p className="pricing-desc">
                    {key === 'music_starter' && 'For artists getting started with AI music creation.'}
                    {key === 'music_pro'     && 'For active creators who want avatar videos.'}
                    {key === 'music_agency'  && 'For prolific creators and label teams.'}
                  </p>
                </div>
                <ul className="pricing-features">
                  {plan.features.map((f) => (
                    <li key={f} className="plan-feature">
                      <span className="plan-feature-check">✓</span>
                      {f}
                    </li>
                  ))}
                </ul>
                <div className="pricing-card-footer">
                  {isCurrent ? (
                    <Link to="/billing" className={`btn ${popular ? 'btn-primary' : 'btn-outline'} btn-full`}>
                      Current Plan
                    </Link>
                  ) : (
                    <button
                      className={`btn ${popular ? 'btn-primary' : 'btn-outline'} btn-full`}
                      disabled={loadingPlan === key}
                      onClick={() => handleCheckout(key)}
                    >
                      {loadingPlan === key
                        ? <span className="spinner spinner--inline" />
                        : `Get ${plan.name}`}
                    </button>
                  )}
                </div>
              </div>
            );
          })}
        </div>

        <p className="pricing-footer-note">
          All plans include a 7-day free trial. Cancel anytime. Prices in GBP (+ VAT where applicable).
        </p>
      </div>
    </div>
  );
}
