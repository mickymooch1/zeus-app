import { useState } from 'react';
import { Link } from 'react-router-dom';

const STORAGE_KEY = 'zeus_cookie_accepted';

export default function CookieBanner() {
  const [visible, setVisible] = useState(() => !localStorage.getItem(STORAGE_KEY));

  if (!visible) return null;

  const accept = () => {
    localStorage.setItem(STORAGE_KEY, '1');
    setVisible(false);
  };

  return (
    <div style={{
      position: 'fixed',
      bottom: 0,
      left: 0,
      right: 0,
      zIndex: 9999,
      background: 'rgba(15, 12, 41, 0.97)',
      borderTop: '1px solid rgba(167, 139, 250, 0.25)',
      padding: '14px 24px',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'space-between',
      gap: '16px',
      flexWrap: 'wrap',
    }}>
      <p style={{ color: '#e2d9f3', fontSize: '13px', lineHeight: 1.5, flex: 1, minWidth: '220px' }}>
        We use cookies to improve your experience. By using Zeus AI Design you agree to our{' '}
        <Link to="/privacy" style={{ color: '#a78bfa', textDecoration: 'underline' }}>
          Privacy Policy
        </Link>.
      </p>
      <div style={{ display: 'flex', gap: '10px', flexShrink: 0 }}>
        <Link
          to="/privacy"
          style={{
            padding: '7px 16px',
            borderRadius: '6px',
            fontSize: '13px',
            color: '#a78bfa',
            border: '1px solid rgba(167, 139, 250, 0.35)',
            background: 'transparent',
            textDecoration: 'none',
            whiteSpace: 'nowrap',
          }}
        >
          Learn More
        </Link>
        <button
          onClick={accept}
          style={{
            padding: '7px 20px',
            borderRadius: '6px',
            fontSize: '13px',
            fontWeight: 600,
            background: 'linear-gradient(135deg, #a78bfa, #60a5fa)',
            color: '#fff',
            border: 'none',
            cursor: 'pointer',
            whiteSpace: 'nowrap',
          }}
        >
          Accept
        </button>
      </div>
    </div>
  );
}
