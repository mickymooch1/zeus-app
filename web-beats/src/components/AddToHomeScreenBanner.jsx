import { useState, useEffect } from 'react';

const STORAGE_KEY = 'zb_a2hs_dismissed';

function isIosSafari() {
  const ua = navigator.userAgent;
  const isIos = /iphone|ipad|ipod/i.test(ua);
  const isSafari = /safari/i.test(ua) && !/crios|fxios|opios|edgios/i.test(ua);
  // Exclude the Zeus Beats native WebView (and any other WKWebView/UIWebView wrappers)
  const isInWebView = !ua.includes('Safari') || ua.includes('wv') || ua.includes('WebView');
  return isIos && isSafari && !isInWebView;
}

function isStandalone() {
  return window.navigator.standalone === true;
}

// The exact Safari share icon: upward arrow rising from a rounded box
function SafariShareIcon() {
  return (
    <svg
      width="16" height="20" viewBox="0 0 16 20" fill="none"
      aria-hidden="true"
      style={{ display: 'inline-block', verticalAlign: 'middle', flexShrink: 0 }}
    >
      {/* Upward arrow shaft + head */}
      <path
        d="M8 13V2M8 2L5 5M8 2l3 3"
        stroke="#00f0ff" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round"
      />
      {/* Box bottom */}
      <path
        d="M4 8H2.5A1.5 1.5 0 001 9.5v8A1.5 1.5 0 002.5 19h11a1.5 1.5 0 001.5-1.5v-8A1.5 1.5 0 0013.5 8H12"
        stroke="#00f0ff" strokeWidth="1.5" strokeLinecap="round"
      />
    </svg>
  );
}

// Chevron arrow that bounces downward (points toward Safari's toolbar)
function BouncingArrow() {
  return (
    <>
      <style>{`
        @keyframes zbBounce {
          0%,100% { transform: translateY(0); opacity: 0.5; }
          50%      { transform: translateY(5px); opacity: 1; }
        }
      `}</style>
      <svg
        width="22" height="13" viewBox="0 0 22 13" fill="none"
        style={{ animation: 'zbBounce 1.2s ease-in-out infinite', display: 'block' }}
        aria-hidden="true"
      >
        <path
          d="M2 2l9 9 9-9"
          stroke="rgba(0,240,255,0.55)" strokeWidth="2.5"
          strokeLinecap="round" strokeLinejoin="round"
        />
      </svg>
    </>
  );
}

export default function AddToHomeScreenBanner() {
  const [visible, setVisible] = useState(false);

  useEffect(() => {
    if (isStandalone()) return;
    if (!isIosSafari()) return;
    if (sessionStorage.getItem(STORAGE_KEY)) return;
    const t = setTimeout(() => setVisible(true), 2500);
    return () => clearTimeout(t);
  }, []);

  const dismiss = () => {
    sessionStorage.setItem(STORAGE_KEY, '1');
    setVisible(false);
  };

  if (!visible) return null;

  return (
    <div style={s.overlay}>
      <div style={s.banner}>

        {/* Dismiss */}
        <button onClick={dismiss} style={s.close} aria-label="Dismiss banner">✕</button>

        {/* Title row */}
        <div style={s.titleRow}>
          <span style={s.bolt}>⚡</span>
          <span style={s.title}>Install Zeus Beats</span>
        </div>

        {/* Steps */}
        <ol style={s.list}>
          <li style={s.item}>
            <span style={s.num}>1</span>
            <span style={s.itemText}>
              Tap the{' '}
              <span style={s.chip}>
                <SafariShareIcon />
                <span style={s.chipLabel}>Share</span>
              </span>
              {' '}button at the bottom of Safari
            </span>
          </li>
          <li style={s.item}>
            <span style={s.num}>2</span>
            <span style={s.itemText}>
              Tap <span style={s.highlight}>"Add to Home Screen"</span>
            </span>
          </li>
        </ol>

        {/* Bouncing arrow pointing down toward Safari toolbar */}
        <div style={s.arrowWrap}>
          <BouncingArrow />
        </div>

      </div>
    </div>
  );
}

const s = {
  overlay: {
    position: 'fixed',
    bottom: 0,
    left: 0,
    right: 0,
    zIndex: 9999,
    display: 'flex',
    justifyContent: 'center',
    padding: '0 12px 10px',
    pointerEvents: 'none',
  },
  banner: {
    background: 'rgba(8,8,20,0.97)',
    border: '1px solid rgba(0,240,255,0.22)',
    borderRadius: 18,
    padding: '16px 16px 12px',
    maxWidth: 375,
    width: '100%',
    boxShadow: '0 -4px 36px rgba(0,0,0,0.65)',
    pointerEvents: 'auto',
    position: 'relative',
  },
  close: {
    position: 'absolute',
    top: 11,
    right: 13,
    background: 'none',
    border: 'none',
    color: '#4a5568',
    fontSize: 15,
    lineHeight: 1,
    cursor: 'pointer',
    padding: '2px 4px',
  },
  titleRow: {
    display: 'flex',
    alignItems: 'center',
    gap: 8,
    marginBottom: 12,
    paddingRight: 24,
  },
  bolt: {
    fontSize: 20,
    lineHeight: 1,
    flexShrink: 0,
  },
  title: {
    color: '#e2e8f0',
    fontSize: 15,
    fontWeight: 700,
    letterSpacing: 0.1,
  },
  list: {
    listStyle: 'none',
    margin: 0,
    padding: 0,
    display: 'flex',
    flexDirection: 'column',
    gap: 9,
  },
  item: {
    display: 'flex',
    alignItems: 'center',
    gap: 10,
  },
  num: {
    width: 20,
    height: 20,
    borderRadius: '50%',
    background: 'rgba(0,240,255,0.12)',
    border: '1px solid rgba(0,240,255,0.3)',
    color: '#00f0ff',
    fontSize: 11,
    fontWeight: 700,
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    flexShrink: 0,
  },
  itemText: {
    color: '#94a3b8',
    fontSize: 13,
    lineHeight: 1.45,
    display: 'flex',
    alignItems: 'center',
    flexWrap: 'wrap',
    gap: '0 5px',
  },
  chip: {
    display: 'inline-flex',
    alignItems: 'center',
    gap: 4,
    background: 'rgba(0,240,255,0.08)',
    border: '1px solid rgba(0,240,255,0.25)',
    borderRadius: 6,
    padding: '2px 6px',
    verticalAlign: 'middle',
  },
  chipLabel: {
    color: '#00f0ff',
    fontSize: 12,
    fontWeight: 600,
  },
  highlight: {
    color: '#e2e8f0',
    fontWeight: 600,
  },
  arrowWrap: {
    display: 'flex',
    justifyContent: 'center',
    marginTop: 10,
  },
};
