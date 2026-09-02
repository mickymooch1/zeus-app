import { useTranslation } from 'react-i18next';

const CYAN = '#00f0ff';
const PINK = '#f472b6';

/**
 * A single warm welcome screen shown before the 4-step OnboardingTour, on a
 * true first visit only. Not part of the tour itself — SongsPage decides
 * whether to route into the tour or straight past it based on which button
 * is pressed here.
 *
 * Mirrors OnboardingTour's overlay/card/footer structure (see that file's
 * layout notes) so it reads as one product rather than two different modals
 * stacked in sequence: scrollable card body, pinned footer so the primary
 * button is always reachable without scrolling, no click-to-dismiss on the
 * backdrop (this is a first-run flow, not an interrupting dialog).
 */
export default function ExploreFirstWelcome({ onShowTour, onDismiss }) {
  const { t } = useTranslation();

  const overlayStyle = {
    position: 'fixed', top: 0, left: 0, right: 0, bottom: 0, zIndex: 9999,
    background: 'rgba(0,0,0,0.88)',
    display: 'flex',
    alignItems: 'flex-start',
    justifyContent: 'center',
    overflowY: 'auto',
    WebkitOverflowScrolling: 'touch',
    overscrollBehavior: 'contain',
    maxHeight: '100dvh',
    padding: 'max(16px, env(safe-area-inset-top)) max(12px, env(safe-area-inset-right)) max(16px, env(safe-area-inset-bottom)) max(12px, env(safe-area-inset-left))',
    backdropFilter: 'blur(4px)',
  };

  const cardStyle = {
    background: 'linear-gradient(135deg, #0d0d1a 0%, #1a0a2e 100%)',
    border: `1px solid ${CYAN}44`,
    borderRadius: 20,
    padding: 'clamp(24px, 6vw, 36px) clamp(20px, 5vw, 30px)',
    maxWidth: 440,
    width: '100%',
    boxShadow: `0 0 60px ${CYAN}18, 0 24px 60px rgba(0,0,0,0.8)`,
    maxHeight: '100%',
    display: 'flex',
    flexDirection: 'column',
    minHeight: 0,
    margin: 'auto',
    textAlign: 'center',
  };

  const cardBodyStyle = { flex: '1 1 auto', minHeight: 0, overflowY: 'auto', WebkitOverflowScrolling: 'touch', overscrollBehavior: 'contain' };
  const cardFooterStyle = { flexShrink: 0, paddingTop: 16, marginTop: 6 };

  return (
    <div style={overlayStyle}>
      <div style={cardStyle}>
        <div style={cardBodyStyle}>
          <div style={{ fontSize: 44, marginBottom: 14 }}>⚡</div>
          <h2 style={{ fontFamily: "'Orbitron', sans-serif", fontSize: 19, fontWeight: 800, color: '#fff', marginBottom: 14, lineHeight: 1.35 }}>
            {t('onboarding.exploreFirst.title')}
          </h2>
          <p style={{ color: 'rgba(255,255,255,0.6)', fontSize: 15, lineHeight: 1.7, marginBottom: 4 }}>
            {t('onboarding.exploreFirst.body')}
          </p>
        </div>

        <div style={cardFooterStyle}>
          <button
            onClick={onShowTour}
            style={{
              width: '100%', minHeight: 44, padding: '14px 0', borderRadius: 12,
              background: `linear-gradient(90deg, ${CYAN}, ${PINK})`,
              color: '#000', fontWeight: 800, fontSize: 15, border: 'none', cursor: 'pointer',
              fontFamily: "'Orbitron', sans-serif",
              boxShadow: `0 0 24px ${CYAN}44`,
              marginBottom: 10,
            }}
          >
            {t('onboarding.exploreFirst.showMeAround')}
          </button>
          <button
            onClick={onDismiss}
            style={{
              width: '100%', minHeight: 44, padding: '12px 0', borderRadius: 12,
              background: 'transparent', border: '1px solid rgba(255,255,255,0.15)',
              color: 'rgba(255,255,255,0.65)', fontSize: 14, fontWeight: 600, cursor: 'pointer',
            }}
          >
            {t('onboarding.exploreFirst.exploreMyself')}
          </button>
        </div>
      </div>
    </div>
  );
}
