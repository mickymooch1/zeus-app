import { useState, useEffect } from 'react';

const STORAGE_KEY = 'zb_a2hs_dismissed';

function isIosSafari() {
  const ua = navigator.userAgent;
  const isIos = /iphone|ipad|ipod/i.test(ua);
  // Safari on iOS: has "Safari" in UA, does NOT have "CriOS", "FxiOS", "OPiOS"
  const isSafari = /safari/i.test(ua) && !/crios|fxios|opios|edgios/i.test(ua);
  // Exclude WebViews: no standalone check needed here, handled below
  // Exclude the Zeus Beats native WebView wrapper (navigator.standalone is undefined in WebView)
  const isInWebView = !ua.includes('Safari') || ua.includes('wv') || ua.includes('WebView');
  return isIos && isSafari && !isInWebView;
}

function isStandalone() {
  return window.navigator.standalone === true;
}

export default function AddToHomeScreenBanner() {
  const [visible, setVisible] = useState(false);

  useEffect(() => {
    if (isStandalone()) return;
    if (!isIosSafari()) return;
    if (sessionStorage.getItem(STORAGE_KEY)) return;
    // Small delay so it doesn't fire before page content loads
    const t = setTimeout(() => setVisible(true), 2500);
    return () => clearTimeout(t);
  }, []);

  const dismiss = () => {
    sessionStorage.setItem(STORAGE_KEY, '1');
    setVisible(false);
  };

  if (!visible) return null;

  return (
    <div style={styles.overlay}>
      <div style={styles.banner}>
        <button onClick={dismiss} style={styles.close} aria-label="Dismiss">✕</button>
        <div style={styles.row}>
          <span style={styles.icon}>⚡</span>
          <div style={styles.text}>
            <strong style={styles.title}>Add Zeus Beats to Home Screen</strong>
            <span style={styles.body}>
              Tap{' '}
              <span style={styles.shareIcon} aria-label="Share">
                {/* iOS share icon SVG */}
                <svg width="14" height="18" viewBox="0 0 14 18" fill="none" style={{ verticalAlign: 'middle', marginBottom: 1 }}>
                  <path d="M7 12V1M7 1L4 4M7 1l3 3" stroke="#00f0ff" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round"/>
                  <rect x="1" y="6" width="12" height="11" rx="2" stroke="#00f0ff" strokeWidth="1.4"/>
                </svg>
              </span>
              {' '}then <strong>Add to Home Screen</strong> for the full app experience.
            </span>
          </div>
        </div>
        {/* Arrow pointing down to bottom share bar */}
        <div style={styles.arrow} />
      </div>
    </div>
  );
}

const styles = {
  overlay: {
    position: 'fixed',
    bottom: 0,
    left: 0,
    right: 0,
    zIndex: 9999,
    display: 'flex',
    justifyContent: 'center',
    padding: '0 12px 12px',
    pointerEvents: 'none',
  },
  banner: {
    background: 'rgba(10,10,24,0.97)',
    border: '1px solid rgba(0,240,255,0.25)',
    borderRadius: 16,
    padding: '14px 16px 18px',
    maxWidth: 375,
    width: '100%',
    boxShadow: '0 -4px 32px rgba(0,0,0,0.6)',
    position: 'relative',
    pointerEvents: 'auto',
  },
  close: {
    position: 'absolute',
    top: 10,
    right: 12,
    background: 'none',
    border: 'none',
    color: '#555',
    fontSize: 14,
    cursor: 'pointer',
    padding: 4,
    lineHeight: 1,
  },
  row: {
    display: 'flex',
    alignItems: 'flex-start',
    gap: 12,
  },
  icon: {
    fontSize: 28,
    lineHeight: 1,
    flexShrink: 0,
  },
  text: {
    display: 'flex',
    flexDirection: 'column',
    gap: 4,
    paddingRight: 20,
  },
  title: {
    color: '#e2e8f0',
    fontSize: 14,
    fontWeight: 700,
    lineHeight: 1.3,
  },
  body: {
    color: '#94a3b8',
    fontSize: 13,
    lineHeight: 1.5,
  },
  shareIcon: {
    display: 'inline-flex',
    alignItems: 'center',
  },
  arrow: {
    width: 14,
    height: 14,
    borderRight: '2px solid rgba(0,240,255,0.3)',
    borderBottom: '2px solid rgba(0,240,255,0.3)',
    transform: 'rotate(45deg)',
    margin: '10px auto 0',
  },
};
