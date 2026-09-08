import { useState } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { BeatsNavbar } from '../components/BeatsNavbar';
import { useAuth } from '../contexts/AuthContext';
import { BACKEND_URL } from '../brand';
import { isIOSWebView } from '../hooks/useIsIOSWebView';
import IOSWebViewBanner from '../components/IOSWebViewBanner';

export default function MemorialsLandingPage() {
  const navigate = useNavigate();
  const location = useLocation();
  const { user, token } = useAuth();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  async function handleCreate() {
    if (!user) {
      navigate('/login', { state: { from: location } });
      return;
    }
    setError('');
    if ((user.memorial_credits_available || 0) > 0) {
      navigate('/memorials/create');
      return;
    }
    setLoading(true);
    try {
      const res = await fetch(`${BACKEND_URL}/api/memorials/checkout`, {
        method: 'POST',
        headers: { Authorization: `Bearer ${token}` },
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(data.detail || 'Failed to start checkout');
      window.location.href = data.url;
    } catch (err) {
      setError(err.message || 'Something went wrong — please try again.');
      setLoading(false);
    }
  }

  return (
    <div className="memorials-landing-page">
      <BeatsNavbar />
      <div className="page" style={{ maxWidth: 640, margin: '0 auto', padding: '64px 24px', textAlign: 'center' }}>
        <div className="hero-orbs" aria-hidden>
          <div className="orb orb-2" />
        </div>

        <h1 style={{ fontSize: 32, fontWeight: 700, margin: 0 }}>
          Create a Lasting Memorial Tribute
        </h1>
        <p style={{ opacity: 0.75, marginTop: 14, fontSize: 16, lineHeight: 1.6 }}>
          Personalised song • Up to 10 photos • Slideshow • Memorial page • Permanent QR code
        </p>

        {isIOSWebView ? (
          <div style={{ marginTop: 32, textAlign: 'left' }}>
            <IOSWebViewBanner />
          </div>
        ) : (
          <>
            <button
              type="button"
              className="btn btn-primary"
              onClick={handleCreate}
              disabled={loading}
              style={{ marginTop: 32, padding: '14px 32px', fontSize: 16 }}
            >
              {loading ? 'One moment…' : 'Create a Memorial'}
            </button>
            {error && (
              <p style={{ color: '#ef4444', marginTop: 14, fontSize: 14 }}>{error}</p>
            )}
          </>
        )}
      </div>
    </div>
  );
}
