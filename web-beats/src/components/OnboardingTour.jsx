import { useState } from 'react';
import i18n from '../i18n';

const CYAN = '#00f0ff';
const PINK = '#f472b6';

const ONBOARDING_LANGUAGES = [
  { code: 'en', label: 'English',    flag: '🇬🇧' },
  { code: 'fr', label: 'Français',   flag: '🇫🇷' },
  { code: 'es', label: 'Español',    flag: '🇪🇸' },
  { code: 'de', label: 'Deutsch',    flag: '🇩🇪' },
  { code: 'pt', label: 'Português',  flag: '🇧🇷' },
  { code: 'it', label: 'Italiano',   flag: '🇮🇹' },
  { code: 'nl', label: 'Nederlands', flag: '🇳🇱' },
  { code: 'ru', label: 'Русский',    flag: '🇷🇺' },
  { code: 'ja', label: '日本語',      flag: '🇯🇵' },
  { code: 'ko', label: '한국어',      flag: '🇰🇷' },
  { code: 'zh', label: '中文',        flag: '🇨🇳' },
  { code: 'ar', label: 'العربية',    flag: '🇦🇪' },
  { code: 'th', label: 'ภาษาไทย',    flag: '🇹🇭' },
];

function detectLang() {
  const nav = (navigator.language || navigator.userLanguage || 'en').slice(0, 2).toLowerCase();
  return ONBOARDING_LANGUAGES.find(l => l.code === nav) || ONBOARDING_LANGUAGES[0];
}

const GENRE_CHOICES = [
  { key: 'soul_rnb',    label: '🎤 Soul / R&B',          genres: ['soul', 'rnb', 'bluessoul'] },
  { key: 'grime_rap',   label: '🎤 Grime / Rap / Drill',  genres: ['grime', 'hiphop', 'ukdrill'] },
  { key: 'electronic',  label: '🎶 Electronic / Dance',   genres: ['edm', 'drumandbass', 'house'] },
  { key: 'everything',  label: '🎸 Everything else',      genres: ['pop', 'rock', 'indie'] },
];

const STEPS = [
  {
    icon: '⚡',
    title: 'Welcome to Zeus Beats ⚡',
    text: 'Create original AI songs in 100+ genres. Let\'s show you around.',
  },
  {
    icon: '🎵',
    title: 'Pick a Genre',
    text: 'Choose from 100+ genres including Soul, Grime, Afrobeats, D&B, Jazz and more.',
  },
  {
    icon: '✍️',
    title: 'Describe Your Song',
    text: 'Tell Zeus what you want — or leave it blank and let Zeus surprise you.',
  },
  {
    icon: '⚙️',
    title: 'Advanced Options',
    text: 'Fine tune your sound with accents, tempo, weirdness and more.',
  },
  {
    icon: '🚀',
    title: 'Generate',
    text: 'Hit Generate and your song will be ready in under 2 minutes.',
  },
  {
    icon: '🎧',
    title: 'Your Songs',
    text: 'Your songs appear here — download, share to Discover, upload to YouTube and more.',
  },
  {
    icon: '🌐',
    title: 'Discover Feed',
    text: 'Check out the Discover feed to hear what other Zeus Beats users are creating.',
  },
  {
    icon: '🎵',
    title: "You're ready!",
    isFinal: true,
  },
];

export default function OnboardingTour({ onComplete, onAutoGenerate, balance }) {
  const [phase, setPhase] = useState('lang_pick');
  const [selectedLang, setSelectedLang] = useState(detectLang);
  const [genrePref, setGenrePref] = useState(null);
  const [step, setStep] = useState(0);
  const [fade, setFade] = useState(true);

  const dismiss = (reason) => {
    localStorage.setItem('zeus_onboarding_done', Date.now().toString());
    onComplete?.({ genrePref, reason });
  };

  const transition = (fn) => {
    setFade(false);
    setTimeout(() => { fn(); setFade(true); }, 140);
  };

  const handleNext = () => {
    if (step < STEPS.length - 1) transition(() => setStep(s => s + 1));
    else dismiss('completed');
  };

  const cur = STEPS[step];

  // ── Layout notes (2026-07-31, fixes a first-screen trap) ───────────────────
  // This overlay used to be `align-items:center` with no overflow. Once the card
  // grew taller than the viewport (small phone, large accessibility font, or page
  // zoom) it overflowed BOTH ends — the top half was unreachable by definition and
  // the bottom half, including "Continue", sat off-screen with nothing scrollable.
  // Users were trapped on the very first screen with no way into the app.
  //
  // The fix has two independent halves, either of which alone would be enough:
  //   1. The overlay scrolls (`overflowY:auto`), and centring is done with
  //      `margin:auto` on the card instead of `align-items:center`. Auto margins
  //      centre when there IS room and collapse when there isn't, so content is
  //      never pushed above the scrollable origin the way align-items:center does.
  //   2. The card is capped at the viewport height and laid out as a flex column:
  //      the body scrolls internally while the CTA sits in a non-shrinking footer,
  //      so the primary button is visible WITHOUT any scrolling at any size.
  // Font sizes are deliberately untouched — the answer is scrolling, not shrinking.

  const cardStyle = {
    background: 'linear-gradient(135deg, #0d0d1a 0%, #1a0a2e 100%)',
    border: `1px solid ${CYAN}44`,
    borderRadius: 20,
    padding: 'clamp(20px, 5vw, 32px) clamp(18px, 5vw, 28px)',
    maxWidth: 420,
    width: '100%',
    boxShadow: `0 0 60px ${CYAN}18, 0 24px 60px rgba(0,0,0,0.8)`,
    opacity: fade ? 1 : 0,
    transition: 'opacity 0.14s ease',
    // Cap to the viewport and become a flex column so the CTA footer can pin.
    maxHeight: '100%',
    display: 'flex',
    flexDirection: 'column',
    minHeight: 0,
    // Centres the card when there's room; collapses (rather than clipping) when
    // there isn't. Must NOT be align-items:center on the parent — see note above.
    margin: 'auto',
  };

  const overlayStyle = {
    position: 'fixed', top: 0, left: 0, right: 0, bottom: 0, zIndex: 9999,
    background: 'rgba(0,0,0,0.88)',
    display: 'flex',
    alignItems: 'flex-start',      // NEVER 'center' — see note above
    justifyContent: 'center',
    overflowY: 'auto',             // the page can always scroll
    WebkitOverflowScrolling: 'touch',
    overscrollBehavior: 'contain',
    // dvh tracks the *visible* viewport as mobile browser chrome shows/hides.
    maxHeight: '100dvh',
    padding: 'max(16px, env(safe-area-inset-top)) max(12px, env(safe-area-inset-right)) max(16px, env(safe-area-inset-bottom)) max(12px, env(safe-area-inset-left))',
    backdropFilter: 'blur(4px)',
  };

  // Scrollable region inside the card. minHeight:0 is load-bearing — without it a
  // flex child refuses to shrink below its content and the footer gets pushed off.
  const cardBodyStyle = {
    flex: '1 1 auto',
    minHeight: 0,
    overflowY: 'auto',
    WebkitOverflowScrolling: 'touch',
    overscrollBehavior: 'contain',
  };

  // Non-shrinking footer holding the primary CTA — always on screen.
  const cardFooterStyle = {
    flexShrink: 0,
    paddingTop: 14,
    marginTop: 4,
    borderTop: '1px solid rgba(255,255,255,0.07)',
  };

  if (phase === 'lang_pick') {
    return (
      <div style={overlayStyle} onClick={() => dismiss('skip')}>
        <div style={{ ...cardStyle, maxWidth: 480, textAlign: 'center' }} onClick={e => e.stopPropagation()}>
          {/* Scrollable body — grows to 13 languages on a narrow screen */}
          <div style={cardBodyStyle}>
            <div style={{ fontSize: 42, marginBottom: 12 }}>🌐</div>
            <h2 style={{ fontFamily: "'Orbitron', sans-serif", fontSize: 19, fontWeight: 800, color: '#fff', marginBottom: 8 }}>
              Choose your language
            </h2>
            <p style={{ color: 'rgba(255,255,255,0.45)', fontSize: 13, marginBottom: 24 }}>
              Select the language for the Zeus Beats app
            </p>
            <div style={{
              display: 'grid',
              gridTemplateColumns: 'repeat(auto-fill, minmax(90px, 1fr))',
              gap: 10,
              marginBottom: 20,
            }}>
              {ONBOARDING_LANGUAGES.map((lang) => (
                <button
                  key={lang.code}
                  onClick={() => setSelectedLang(lang)}
                  style={{
                    display: 'flex',
                    flexDirection: 'column',
                    alignItems: 'center',
                    gap: 4,
                    padding: '10px 8px',
                    borderRadius: 10,
                    border: `2px solid ${selectedLang.code === lang.code ? CYAN : 'rgba(255,255,255,0.15)'}`,
                    background: selectedLang.code === lang.code ? `${CYAN}18` : 'rgba(255,255,255,0.04)',
                    color: selectedLang.code === lang.code ? '#fff' : 'rgba(255,255,255,0.65)',
                    cursor: 'pointer',
                    fontSize: 22,
                    transition: 'all 0.15s ease',
                    boxShadow: selectedLang.code === lang.code ? `0 0 12px ${CYAN}44` : 'none',
                  }}
                >
                  <span>{lang.flag}</span>
                  <span style={{ fontSize: 10, lineHeight: 1.2 }}>{lang.label}</span>
                </button>
              ))}
            </div>
          </div>

          {/* Pinned footer — Continue is reachable without scrolling, always */}
          <div style={cardFooterStyle}>
            <button
              onClick={() => {
                i18n.changeLanguage(selectedLang.code);
                transition(() => setPhase('genre_q'));
              }}
              style={{
                width: '100%', padding: '14px 0', borderRadius: 12,
                background: `linear-gradient(90deg, ${CYAN}, ${PINK})`,
                color: '#000', fontWeight: 800, fontSize: 15, border: 'none', cursor: 'pointer',
                fontFamily: "'Orbitron', sans-serif",
                boxShadow: `0 0 24px ${CYAN}44`,
                marginBottom: 10,
              }}
            >
              Continue →
            </button>
            <button onClick={() => dismiss('skip')} style={{ background: 'none', border: 'none', color: 'rgba(255,255,255,0.28)', fontSize: 13, cursor: 'pointer' }}>
              Skip introduction
            </button>
          </div>
        </div>
      </div>
    );
  }

  if (phase === 'genre_q') {
    return (
      <div style={overlayStyle} onClick={() => dismiss('skip')}>
        <div style={{ ...cardStyle, maxWidth: 440, textAlign: 'center' }} onClick={e => e.stopPropagation()}>
          <div style={cardBodyStyle}>
            <div style={{ fontSize: 46, marginBottom: 14 }}>🎵</div>
            <h2 style={{ fontFamily: "'Orbitron', sans-serif", fontSize: 20, fontWeight: 800, color: '#fff', marginBottom: 8 }}>
              What kind of music are you into?
            </h2>
            <p style={{ color: 'rgba(255,255,255,0.45)', fontSize: 14, marginBottom: 28 }}>
              We'll pre-select the best genres for you
            </p>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 10, marginBottom: 20 }}>
              {GENRE_CHOICES.map(({ key, label }) => (
                <button
                  key={key}
                  onClick={() => {
                    setGenrePref(key);
                    transition(() => setPhase('tour'));
                  }}
                  style={{
                    padding: '14px 20px', borderRadius: 12, textAlign: 'left',
                    border: `1px solid ${CYAN}33`,
                    background: 'rgba(0,240,255,0.04)',
                    color: '#fff', fontSize: 15, fontWeight: 600, cursor: 'pointer',
                    transition: 'border-color 0.15s, background 0.15s',
                  }}
                  onMouseEnter={e => { e.currentTarget.style.borderColor = CYAN; e.currentTarget.style.background = `${CYAN}12`; }}
                  onMouseLeave={e => { e.currentTarget.style.borderColor = `${CYAN}33`; e.currentTarget.style.background = 'rgba(0,240,255,0.04)'; }}
                >
                  {label}
                </button>
              ))}
            </div>
          </div>
          <div style={cardFooterStyle}>
            <button onClick={() => dismiss('skip')} style={{ background: 'none', border: 'none', color: 'rgba(255,255,255,0.28)', fontSize: 13, cursor: 'pointer' }}>
              Skip introduction
            </button>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div style={overlayStyle} onClick={() => dismiss('skip')}>
      <div style={cardStyle} onClick={e => e.stopPropagation()}>
       <div style={cardBodyStyle}>

        {/* Header */}
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 24 }}>
          <span style={{ fontSize: 10, color: `${CYAN}88`, fontWeight: 700, letterSpacing: '0.12em', textTransform: 'uppercase' }}>
            Zeus Beats Tour
          </span>
          <span style={{ fontSize: 12, color: 'rgba(255,255,255,0.3)' }}>
            {step + 1} of {STEPS.length}
          </span>
        </div>

        {/* Icon */}
        <div style={{ fontSize: 46, textAlign: 'center', marginBottom: 14 }}>{cur.icon}</div>

        {/* Title */}
        <h2 style={{ fontFamily: "'Orbitron', sans-serif", fontSize: 19, fontWeight: 800, color: '#fff', textAlign: 'center', marginBottom: 12, lineHeight: 1.3 }}>
          {cur.title}
        </h2>

        {/* Body */}
        {cur.isFinal ? (
          <div style={{ textAlign: 'center', marginBottom: 24 }}>
            <div style={{
              display: 'inline-flex', alignItems: 'center', gap: 8,
              background: `${CYAN}10`, border: `1px solid ${CYAN}44`,
              borderRadius: 50, padding: '9px 20px', marginBottom: 14,
              boxShadow: `0 0 20px ${CYAN}22`,
            }}>
              <span>⚡</span>
              <span style={{ color: CYAN, fontWeight: 700, fontSize: 14 }}>
                You have {balance ?? 5} free songs — let's use one right now!
              </span>
            </div>
            <p style={{ color: 'rgba(255,255,255,0.5)', fontSize: 14, lineHeight: 1.7 }}>
              {/* Use the real balance — the hardcoded "5" contradicted the badge above it. */}
              {balance ?? 3} free songs are waiting for you. Go make something 🎵⚡
            </p>
          </div>
        ) : (
          <p style={{ color: 'rgba(255,255,255,0.55)', fontSize: 15, lineHeight: 1.7, textAlign: 'center', marginBottom: 28 }}>
            {cur.text}
          </p>
        )}

       </div>

        {/* Actions — pinned footer so the CTA is always reachable */}
        <div style={cardFooterStyle}>
        {cur.isFinal ? (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 10, marginBottom: 20 }}>
            <button
              onClick={() => {
                const choice = GENRE_CHOICES.find(c => c.key === genrePref);
                dismiss('auto_generate');
                onAutoGenerate?.(choice?.genres || ['soul']);
              }}
              style={{
                width: '100%', padding: '15px 0', borderRadius: 12,
                background: `linear-gradient(90deg, ${CYAN}, ${PINK})`,
                color: '#000', fontWeight: 800, fontSize: 15, border: 'none', cursor: 'pointer',
                fontFamily: "'Orbitron', sans-serif",
                boxShadow: `0 0 24px ${CYAN}44`,
              }}
            >
              🎵 Make My First Song
            </button>
            <button
              onClick={() => dismiss('completed')}
              style={{
                width: '100%', padding: '12px 0', borderRadius: 12,
                background: 'transparent', border: '1px solid rgba(255,255,255,0.1)',
                color: 'rgba(255,255,255,0.45)', fontSize: 14, cursor: 'pointer',
              }}
            >
              I'll explore myself
            </button>
          </div>
        ) : (
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 20 }}>
            <button
              onClick={() => dismiss('skip')}
              style={{ background: 'none', border: 'none', color: 'rgba(255,255,255,0.28)', fontSize: 13, cursor: 'pointer', padding: '8px 0' }}
            >
              Skip
            </button>
            <button
              onClick={handleNext}
              style={{
                padding: '11px 28px', borderRadius: 10,
                background: `linear-gradient(90deg, ${CYAN}cc, ${PINK}99)`,
                border: 'none', color: '#000', fontWeight: 700, fontSize: 14, cursor: 'pointer',
                boxShadow: `0 0 16px ${CYAN}44`,
              }}
            >
              Next →
            </button>
          </div>
        )}

        {/* Progress dots */}
        <div style={{ display: 'flex', justifyContent: 'center', gap: 6 }}>
          {STEPS.map((_, i) => (
            <div
              key={i}
              style={{
                height: 6,
                width: i === step ? 22 : 6,
                borderRadius: 3,
                background: i === step ? CYAN : 'rgba(255,255,255,0.14)',
                transition: 'width 0.3s, background 0.3s',
              }}
            />
          ))}
        </div>
        </div>
      </div>
    </div>
  );
}
