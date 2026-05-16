import { useEffect, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { Navbar } from '../components/Navbar';
import { useAuth } from '../contexts/AuthContext';

const BACKEND_URL = import.meta.env.VITE_BACKEND_URL || '';

const FREE_FEATURES = [
  '5 free songs on signup',
  'Song download & share',
  'All music genres',
];

const MUSIC_PLANS = {
  music_starter: {
    name: 'Music Starter',
    price: '£9/mo',
    features: [
      '15 AI songs/month',
      'YouTube upload',
      'Song download & share',
      'All music genres & styles',
      'Cover art included',
      'Animated music video',
    ],
  },
  music_pro: {
    name: 'Music Pro',
    price: '£19/mo',
    features: [
      '40 AI songs/month',
      'YouTube upload',
      '3 avatar videos/month',
      'Song download & share',
      'All music genres & styles',
      'Cover art included',
      'Animated music video',
    ],
  },
  music_agency: {
    name: 'Music Agency',
    price: '£39/mo',
    features: [
      '80 AI songs/month',
      'YouTube upload',
      '10 avatar videos/month',
      'Song download & share',
      'All music genres & styles',
      'Cover art included',
      'Animated music video',
    ],
  },
};

export default function PricingPage() {
  const navigate = useNavigate();
  const { user, token } = useAuth();
  const [plans, setPlans] = useState(MUSIC_PLANS);
  const [loadingCheckout, setLoadingCheckout] = useState(null);
  const [error, setError] = useState('');

  useEffect(() => {
    fetch(`${BACKEND_URL}/billing/music-plans`)
      .then(async (res) => {
        if (!res.ok) return;
        const data = await res.json();
        if (data && typeof data === 'object') {
          setPlans(data);
        }
      })
      .catch(() => {
        // silently fall back to hardcoded plans
      });
  }, []);

  const handleCheckout = async (plan) => {
    if (!user) {
      navigate('/register');
      return;
    }
    setLoadingCheckout(plan);
    setError('');
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

  return (
    <div className="landing">
      <Navbar />

      <div className="page pricing-page">
        {/* Hero */}
        <div className="hero-orbs" aria-hidden>
          <div className="orb orb-1" /><div className="orb orb-2" />
        </div>
        <div style={{ textAlign: 'center', padding: '80px 0 48px' }}>
          <div className="hero-eyebrow">♪ Zeus Beats Pricing</div>
          <h1 className="hero-title">Simple, <span className="hero-gradient">Music-First</span> Pricing</h1>
          <p className="hero-sub">Pay only for what you use. Full music production suite — no website builder bundled in.</p>
        </div>

        {/* Free tier card */}
        <div style={{ textAlign: 'center', marginBottom: 48 }}>
          <div style={{ display: 'inline-block', background: 'rgba(255,255,255,0.04)', border: '1px solid var(--border)', borderRadius: 14, padding: '24px 40px', minWidth: 280 }}>
            <span className="badge-free">Free</span>
            <div className="pricing-price" style={{ margin: '12px 0' }}>£0<span>/mo</span></div>
            <ul className="pricing-features" style={{ textAlign: 'left', marginBottom: 20 }}>
              {FREE_FEATURES.map(f => (
                <li key={f} className="plan-feature"><span className="plan-feature-check">✓</span>{f}</li>
              ))}
            </ul>
            <Link to="/register" className="btn btn-outline btn-full">Get Started Free</Link>
          </div>
        </div>

        {/* Paid plans grid */}
        <div className="pricing-grid">
          {Object.entries(plans).map(([plan, planData]) => {
            const priceDisplay = planData.price ? planData.price.replace('/mo', '') : '';
            const features = planData.features || [];
            return (
              <div key={plan} className={`pricing-card${plan === 'music_pro' ? ' pricing-card--featured' : ''}`}>
                {plan === 'music_pro' && <span className="badge-pro">{planData.name}</span>}
                {plan === 'music_starter' && <span className="badge-pro">{planData.name}</span>}
                {plan === 'music_agency' && <span className="badge-agency">{planData.name}</span>}
                <div className="pricing-name">{planData.name}</div>
                <div className="pricing-price">{priceDisplay}<span>/mo</span></div>
                <ul className="pricing-features">
                  {features.map(f => (
                    <li key={f} className="plan-feature"><span className="plan-feature-check">✓</span>{f}</li>
                  ))}
                </ul>
                <button
                  className={`btn ${plan === 'music_pro' ? 'btn-primary' : 'btn-outline'} btn-full`}
                  disabled={loadingCheckout === plan}
                  onClick={() => handleCheckout(plan)}
                >
                  {loadingCheckout === plan ? <span className="spinner spinner--inline" /> : `Get ${planData.name}`}
                </button>
              </div>
            );
          })}
        </div>

        {/* Error banner */}
        {error && <div className="form-error form-error--banner" style={{ marginTop: 20 }}>{error}</div>}

        {/* FAQ / note */}
        <div style={{ textAlign: 'center', marginTop: 60, color: 'var(--text-dim)', fontSize: 13 }}>
          <p>All plans include cover art generation and animated music video. No website builder. No chat assistant.</p>
          <p style={{ marginTop: 8 }}>Questions? <a href="mailto:dominic.rowle@yahoo.com" className="auth-link">Contact us</a></p>
        </div>

        {/* Footer */}
        <footer className="footer">
          <p>© 2025 Zeus Beats</p>
          <div className="footer-links">
            <Link to="/" className="footer-link">Home</Link>
            <Link to="/login" className="footer-link">Login</Link>
            <Link to="/terms" className="footer-link">Terms</Link>
            <Link to="/privacy" className="footer-link">Privacy</Link>
          </div>
        </footer>
      </div>
    </div>
  );
}
