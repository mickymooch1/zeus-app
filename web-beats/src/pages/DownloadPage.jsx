import { QRCodeSVG } from 'qrcode.react';

const SITE_URL    = 'https://zeusbeats.com';
const ANDROID_URL = 'https://play.google.com/store/apps/details?id=com.zeusbeats.app';

const CYAN  = '#00f5ff';
const PINK  = '#f72585';
const BG    = '#09090f';
const CARD  = '#0f0f1a';
const BORDER = 'rgba(0,245,255,0.18)';

const styles = {
  page: {
    minHeight: '100vh',
    background: BG,
    display: 'flex',
    flexDirection: 'column',
    alignItems: 'center',
    justifyContent: 'center',
    padding: '40px 20px',
    fontFamily: "'Inter', 'Segoe UI', sans-serif",
    position: 'relative',
    overflow: 'hidden',
  },
  // subtle radial glow behind the content
  glow: {
    position: 'absolute',
    top: '50%',
    left: '50%',
    transform: 'translate(-50%, -50%)',
    width: 700,
    height: 700,
    borderRadius: '50%',
    background: `radial-gradient(circle, rgba(0,245,255,0.06) 0%, rgba(247,37,133,0.04) 50%, transparent 70%)`,
    pointerEvents: 'none',
  },
  header: {
    textAlign: 'center',
    marginBottom: 48,
    position: 'relative',
    zIndex: 1,
  },
  logoRow: {
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 12,
    marginBottom: 16,
  },
  logoIcon: {
    width: 44,
    height: 44,
    background: `linear-gradient(135deg, ${CYAN}, ${PINK})`,
    borderRadius: 12,
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    fontSize: 24,
    boxShadow: `0 0 20px rgba(0,245,255,0.4)`,
  },
  logoText: {
    fontSize: 28,
    fontWeight: 800,
    letterSpacing: '-0.5px',
    background: `linear-gradient(90deg, ${CYAN} 0%, #a78bfa 50%, ${PINK} 100%)`,
    WebkitBackgroundClip: 'text',
    WebkitTextFillColor: 'transparent',
    backgroundClip: 'text',
  },
  tagline: {
    color: 'rgba(255,255,255,0.45)',
    fontSize: 14,
    letterSpacing: '2px',
    textTransform: 'uppercase',
  },
  cards: {
    display: 'flex',
    gap: 32,
    flexWrap: 'wrap',
    justifyContent: 'center',
    position: 'relative',
    zIndex: 1,
  },
  card: {
    background: CARD,
    border: `1px solid ${BORDER}`,
    borderRadius: 20,
    padding: '32px 28px',
    display: 'flex',
    flexDirection: 'column',
    alignItems: 'center',
    gap: 20,
    width: 220,
    boxShadow: `0 0 40px rgba(0,245,255,0.07), 0 8px 32px rgba(0,0,0,0.5)`,
    transition: 'box-shadow 0.2s',
  },
  qrWrap: {
    padding: 12,
    background: '#ffffff',
    borderRadius: 12,
    lineHeight: 0,
    boxShadow: `0 0 0 3px ${BORDER}`,
  },
  cardLabel: {
    textAlign: 'center',
  },
  labelTitle: {
    display: 'block',
    fontSize: 13,
    fontWeight: 700,
    letterSpacing: '1.5px',
    textTransform: 'uppercase',
    marginBottom: 6,
  },
  labelSub: {
    display: 'block',
    fontSize: 11,
    color: 'rgba(255,255,255,0.38)',
    letterSpacing: '0.5px',
  },
  divider: {
    width: 1,
    background: `linear-gradient(to bottom, transparent, ${BORDER}, transparent)`,
    alignSelf: 'stretch',
    flexShrink: 0,
  },
  footer: {
    marginTop: 48,
    textAlign: 'center',
    position: 'relative',
    zIndex: 1,
  },
  footerText: {
    color: 'rgba(255,255,255,0.2)',
    fontSize: 11,
    letterSpacing: '1px',
    textTransform: 'uppercase',
  },
  printBtn: {
    marginTop: 20,
    padding: '9px 22px',
    background: 'transparent',
    border: `1px solid ${BORDER}`,
    borderRadius: 8,
    color: CYAN,
    fontSize: 12,
    letterSpacing: '1px',
    textTransform: 'uppercase',
    cursor: 'pointer',
    transition: 'background 0.15s, box-shadow 0.15s',
  },
};

export default function DownloadPage() {
  return (
    <div style={styles.page}>
      <div style={styles.glow} />

      {/* Header */}
      <header style={styles.header}>
        <div style={styles.logoRow}>
          <div style={styles.logoIcon}>⚡</div>
          <span style={styles.logoText}>Zeus Beats</span>
        </div>
        <p style={styles.tagline}>AI Music Creation · No Limits</p>
      </header>

      {/* QR code cards */}
      <div style={styles.cards}>
        {/* Website QR */}
        <div style={styles.card}>
          <div style={styles.qrWrap}>
            <QRCodeSVG
              value={SITE_URL}
              size={160}
              bgColor="#ffffff"
              fgColor="#09090f"
              level="H"
              includeMargin={false}
            />
          </div>
          <div style={styles.cardLabel}>
            <span style={{ ...styles.labelTitle, color: CYAN }}>Scan to visit</span>
            <span style={styles.labelSub}>zeusbeats.com</span>
          </div>
        </div>

        {/* Vertical divider — hidden on mobile when cards wrap */}
        <div style={styles.divider} />

        {/* Android QR */}
        <div style={styles.card}>
          <div style={styles.qrWrap}>
            <QRCodeSVG
              value={ANDROID_URL}
              size={160}
              bgColor="#ffffff"
              fgColor="#09090f"
              level="H"
              includeMargin={false}
            />
          </div>
          <div style={styles.cardLabel}>
            <span style={{ ...styles.labelTitle, color: PINK }}>Download on Android</span>
            <span style={styles.labelSub}>Google Play Store</span>
          </div>
        </div>
      </div>

      {/* Footer */}
      <footer style={styles.footer}>
        <p style={styles.footerText}>zeusbeats.com · AI-powered music for everyone</p>
        <button
          style={styles.printBtn}
          onClick={() => window.print()}
          onMouseEnter={(e) => {
            e.currentTarget.style.background = 'rgba(0,245,255,0.08)';
            e.currentTarget.style.boxShadow = `0 0 12px rgba(0,245,255,0.2)`;
          }}
          onMouseLeave={(e) => {
            e.currentTarget.style.background = 'transparent';
            e.currentTarget.style.boxShadow = 'none';
          }}
        >
          🖨 Print / Save as PDF
        </button>
      </footer>

      {/* Print-only styles — hides the button and optimises layout */}
      <style>{`
        @media print {
          button { display: none !important; }
          body { background: #fff !important; }
        }
        @media (max-width: 520px) {
          [data-divider] { display: none; }
        }
      `}</style>
    </div>
  );
}
