import { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { BRAND } from '../brand';
import { LanguageSelector } from '../components/LanguageSelector';
import './LandingPageBeats.css';

// Icons and layout live here; every string comes from landing.features.* so the
// grid translates. Card order within a group is the display order.
const FEATURE_GROUPS = [
  {
    id: 'music',
    icon: '🎵',
    cards: [
      { id: 'songGenerator', icon: '🎵', lead: true, tags: ['genres', 'customLyrics', 'aiVocals', 'instrumental'] },
      { id: 'genres', icon: '🎸' },
      { id: 'coverArt', icon: '🎨' },
      { id: 'avatarVideos', icon: '🎬' },
      { id: 'genreBlending', icon: '🎚️' },
      { id: 'djMixer', icon: '🎛️' },
      { id: 'voiceToText', icon: '🎤' },
      { id: 'templates', icon: '📋' },
      { id: 'stemSeparator', icon: '🎚️' },
    ],
  },
  {
    id: 'publishing',
    icon: '🌐',
    cards: [
      { id: 'youtube', icon: '▶️' },
      { id: 'facebookInstagram', icon: '📱' },
      { id: 'discoverFeed', icon: '🌐' },
      { id: 'playlist', icon: '🎶' },
      { id: 'musicSearch', icon: '🔍' },
    ],
  },
  {
    id: 'advanced',
    icon: '🎛️',
    cards: [
      { id: 'modelSelector', icon: '🤖' },
      { id: 'vocalGender', icon: '🎤' },
      { id: 'accents', icon: '🗣️' },
      { id: 'explicit', icon: '🔞' },
      { id: 'weirdness', icon: '🌀' },
      { id: 'avoidTags', icon: '🚫' },
      { id: 'inspiredBy', icon: '🎨' },
    ],
  },
  {
    id: 'account',
    icon: '👤',
    cards: [
      { id: 'artistName', icon: '🎭' },
      { id: 'favourites', icon: '⭐' },
      { id: 'songFilters', icon: '🔎' },
      { id: 'multiLanguage', icon: '🌍' },
    ],
  },
];

const GROUP_LABEL_STYLE = {
  fontSize: 13,
  fontWeight: 700,
  color: '#00f0ff',
  letterSpacing: '0.08em',
  textTransform: 'uppercase',
  marginBottom: 14,
};

export default function LandingPage() {
  const [scrolled, setScrolled] = useState(false);
  const [menuOpen, setMenuOpen] = useState(false);
  const { t } = useTranslation();

  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 10);
    window.addEventListener('scroll', onScroll, { passive: true });
    return () => window.removeEventListener('scroll', onScroll);
  }, []);

  return (
    <div className="lp">
      {/* NAV */}
      <nav className={`nav${scrolled ? ' scrolled' : ''}`}>
        <div className="nav-inner">
          <a href="#" className="logo">
            <span className="logo-icon">⚡</span>
            <span className="logo-text">{BRAND.name}</span>
          </a>
          <ul className="nav-links">
            <li><a href="#features">{t('nav.features')}</a></li>
            <li><a href="#how">{t('nav.howItWorks')}</a></li>
            <li><a href="#pricing">{t('nav.pricing')}</a></li>
          </ul>
          <div className="nav-cta">
            <Link to="/login" className="btn-nav-ghost">{t('nav.signIn')}</Link>
            <Link to="/register" className="btn-nav-primary">{t('nav.startFree')}</Link>
            <LanguageSelector />
          </div>
          <button
            className="hamburger"
            aria-label={t('nav.openMenu')}
            onClick={() => setMenuOpen(o => !o)}
          >
            <span /><span /><span />
          </button>
        </div>
        <div className={`mobile-menu${menuOpen ? ' open' : ''}`}>
          <a href="#features" onClick={() => setMenuOpen(false)}>{t('nav.features')}</a>
          <a href="#how" onClick={() => setMenuOpen(false)}>{t('nav.howItWorks')}</a>
          <a href="#pricing" onClick={() => setMenuOpen(false)}>{t('nav.pricing')}</a>
          <Link to="/login" onClick={() => setMenuOpen(false)}>{t('nav.signIn')}</Link>
          <Link to="/register" className="mobile-cta" onClick={() => setMenuOpen(false)}>{t('nav.startFree')} →</Link>
        </div>
      </nav>

      {/* HERO */}
      <section className="hero">
        <div className="hero-bg">
          <div className="grid-overlay" />
          <div className="glow glow-1" />
          <div className="glow glow-2" />
          <div className="glow glow-3" />
          <div className="hero-corner hero-corner--tl" />
          <div className="hero-corner hero-corner--tr" />
          <div className="hero-corner hero-corner--bl" />
          <div className="hero-corner hero-corner--br" />
        </div>
        <div className="container hero-content">
          <div className="hero-badge">
            <span className="badge-dot" />
            {t('landing.badge')}
          </div>
          <h1 className="hero-title">
            <span className="hero-word-cyan">{t('landing.heroTitle1')}</span>{' '}
            <span className="hero-word-pink">{t('landing.heroTitle2')}</span>{' '}
            <span className="hero-word-green">{t('landing.heroTitle3')}</span>
          </h1>
          <p className="hero-sub">
            {t('landing.heroSub', { brand: BRAND.name })}
          </p>
          <div className="hero-actions">
            <Link to="/register" className="btn-primary btn-lg">
              {t('landing.startCreating')}
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5"><path d="M5 12h14M12 5l7 7-7 7" /></svg>
            </Link>
            <a href="#features" className="btn-ghost btn-lg">{t('landing.seeHow')}</a>
          </div>

          <div className="hero-mockup">
            <div className="mockup-bar">
              <span className="dot red" /><span className="dot yellow" /><span className="dot green" />
              <span className="mockup-title">{BRAND.name}</span>
            </div>
            <div className="mockup-body">
              <div className="chat-msg user">Create a dark hip-hop track — late night vibes, hustling, motivational</div>
              <div className="chat-msg zeus">
                <span className="zeus-label">⚡ {BRAND.name}</span>
                Writing lyrics now — midnight hustle theme, anthemic hook. Sending to Suno for audio...
                <div className="chat-progress">
                  <div className="progress-bar"><div className="progress-fill" /></div>
                  <span className="progress-text">Generating audio... ✓ "Midnight Drive" ready — 3:42</span>
                </div>
              </div>
              <div className="chat-msg user">Upload it to my YouTube channel</div>
              <div className="chat-msg zeus">
                <span className="zeus-label">⚡ {BRAND.name}</span>
                Published to YouTube ✓ — track is live with AI-generated cover art. 🎵
              </div>
            </div>
          </div>
        </div>
      </section>

      <div className="section-divider" />

      {/* FEATURES */}
      <section className="features" id="features">
        <div className="container">
          <div className="section-label">{t('landing.featuresLabel')}</div>
          <h2 className="section-title">{t('landing.featuresTitle')}<br /><span className="gradient-text">{t('landing.featuresTitle2')}</span></h2>
          <p className="section-sub">{t('landing.featuresSub', { brand: BRAND.name })}</p>

          {FEATURE_GROUPS.map((group, gi) => (
            <div key={group.id} style={{ marginBottom: 8 }}>
              <div style={gi === 0 ? GROUP_LABEL_STYLE : { ...GROUP_LABEL_STYLE, marginTop: 40 }}>
                {group.icon} {t(`landing.features.groups.${group.id}`)}
              </div>
              <div className="features-grid">
                {group.cards.map((card) => (
                  <div key={card.id} className={card.lead ? 'feat-card feat-lead' : 'feat-card'}>
                    <span className="feat-icon">{card.icon}</span>
                    <h3>{t(`landing.features.cards.${card.id}.title`)}</h3>
                    <p>{t(`landing.features.cards.${card.id}.desc`)}</p>
                    {card.tags && (
                      <div className="feat-tags">
                        {card.tags.map((tag) => (
                          <span key={tag}>{t(`landing.features.tags.${tag}`)}</span>
                        ))}
                      </div>
                    )}
                  </div>
                ))}
              </div>
            </div>
          ))}
        </div>
      </section>

      <div className="section-divider" />

      {/* HOW IT WORKS */}
      <section className="capabilities" id="how">
        <div className="container">
          <div className="section-label">{t('landing.howLabel', { brand: BRAND.name })}</div>
          <h2 className="section-title">{t('landing.howTitle1')}<br /><span className="gradient-text">{t('landing.howTitle2')}</span></h2>

          <div className="caps-layout">
            <div className="caps-list">
              <div className="cap-item">
                <div className="cap-num">01</div>
                <div className="cap-body">
                  <h4>{t('landing.step1Title')}</h4>
                  <p>{t('landing.step1Desc')}</p>
                </div>
              </div>
              <div className="cap-item">
                <div className="cap-num">02</div>
                <div className="cap-body">
                  <h4>{t('landing.step2Title')}</h4>
                  <p>{t('landing.step2Desc')}</p>
                </div>
              </div>
              <div className="cap-item">
                <div className="cap-num">03</div>
                <div className="cap-body">
                  <h4>{t('landing.step3Title')}</h4>
                  <p>{t('landing.step3Desc')}</p>
                </div>
              </div>
            </div>

            <div className="caps-terminal">
              <div className="terminal-bar">
                <span className="dot red" /><span className="dot yellow" /><span className="dot green" />
                <span className="terminal-title">beats-session.log</span>
              </div>
              <div className="terminal-body">
                <div className="t-line"><span className="t-user">you</span> <span>A sad R&amp;B song about moving on</span></div>
                <div className="t-line"><span className="t-zeus">zeus</span> <span>Writing lyrics... soulful, heartbreak theme, hook ready</span></div>
                <div className="t-line"><span className="t-sys">▶</span> <span>Producing track...</span> <span className="t-ok">done</span></div>
                <div className="t-line"><span className="t-sys">▶</span> <span>Generating cover art...</span> <span className="t-ok">done</span></div>
                <div className="t-line"><span className="t-sys">▶</span> <span>Applying cinematic motion...</span> <span className="t-ok">done</span></div>
                <div className="t-line"><span className="t-zeus">zeus</span> <span>"Let You Go" is ready — 3:28, R&amp;B 🎵</span></div>
                <div className="t-line t-gap"><span className="t-user">you</span> <span>[clicked Upload to YouTube]</span></div>
                <div className="t-line"><span className="t-sys">▶</span> <span>Publishing to your channel...</span> <span className="t-ok">live ✓</span></div>
                <div className="t-line"><span className="t-zeus">zeus</span> <span>Live → youtu.be/abc456 · 0:58 total 🚀</span></div>
                <div className="t-cursor">█</div>
              </div>
            </div>
          </div>
        </div>
      </section>

      <div className="section-divider" />

      {/* FIND YOUR SOUND */}
      <section style={{ padding: '80px 24px', textAlign: 'center', background: 'linear-gradient(180deg, #000 0%, #050510 100%)' }}>
        <div style={{ maxWidth: 680, margin: '0 auto' }}>
          <h2 style={{
            fontFamily: "'Orbitron', sans-serif",
            fontSize: 'clamp(26px, 5vw, 44px)',
            fontWeight: 900,
            background: 'linear-gradient(90deg, #00f0ff 0%, #00bfff 50%, #00f0ff 100%)',
            WebkitBackgroundClip: 'text',
            WebkitTextFillColor: 'transparent',
            backgroundClip: 'text',
            marginBottom: 16,
            lineHeight: 1.1,
            letterSpacing: '-0.5px',
          }}>Find Your Sound</h2>
          <p style={{ color: '#aaa', fontSize: 16, lineHeight: 1.7, marginBottom: 36, maxWidth: 560, margin: '0 auto 36px' }}>
            Search artists, genres or tracks for inspiration, then generate original songs with the same energy — from Grime and Garage to Afrobeats, Jungle and Drill.
          </p>
          <a
            href="/search"
            style={{
              display: 'inline-block',
              padding: '14px 32px',
              background: 'transparent',
              border: '2px solid #00f0ff',
              borderRadius: 10,
              color: '#00f0ff',
              fontWeight: 700,
              fontSize: 15,
              textDecoration: 'none',
              letterSpacing: '0.5px',
              boxShadow: '0 0 18px rgba(0,240,255,0.25)',
              transition: 'all 0.2s',
            }}
            onMouseEnter={e => { e.currentTarget.style.background = 'rgba(0,240,255,0.10)'; e.currentTarget.style.boxShadow = '0 0 28px rgba(0,240,255,0.45)'; }}
            onMouseLeave={e => { e.currentTarget.style.background = 'transparent'; e.currentTarget.style.boxShadow = '0 0 18px rgba(0,240,255,0.25)'; }}
          >
            Search for Inspiration →
          </a>
        </div>
      </section>

      <div className="section-divider" />

      {/* DISCOVER */}
      <section style={{ padding: '80px 24px', textAlign: 'center', background: 'rgba(0,240,255,0.02)' }}>
        <div className="container" style={{ maxWidth: 640, margin: '0 auto' }}>
          <div style={{ display: 'inline-block', padding: '4px 14px', borderRadius: 20, background: 'rgba(0,240,255,0.08)', border: '1px solid rgba(0,240,255,0.25)', fontSize: 12, fontWeight: 700, color: '#00f0ff', letterSpacing: '0.08em', textTransform: 'uppercase', marginBottom: 20 }}>
            Discover
          </div>
          <h2 style={{ fontFamily: "'Orbitron', sans-serif", fontSize: 'clamp(24px, 5vw, 40px)', fontWeight: 900, color: '#fff', marginBottom: 14, letterSpacing: '-0.3px' }}>
            Discover AI Music
          </h2>
          <p style={{ fontSize: 17, color: 'rgba(255,255,255,0.6)', marginBottom: 36, lineHeight: 1.6 }}>
            Listen to songs created by Zeus Beats users from around the world
          </p>
          <a
            href="/discover"
            style={{
              display: 'inline-block',
              padding: '16px 36px',
              borderRadius: 50,
              background: 'linear-gradient(135deg, #00f0ff, #ff0099)',
              color: '#000',
              fontWeight: 800,
              fontSize: 16,
              textDecoration: 'none',
              fontFamily: "'Orbitron', sans-serif",
              letterSpacing: '0.02em',
              boxShadow: '0 0 32px rgba(0,240,255,0.4)',
              transition: 'transform 0.2s, box-shadow 0.2s',
            }}
            onMouseEnter={e => { e.currentTarget.style.transform = 'scale(1.04)'; e.currentTarget.style.boxShadow = '0 0 48px rgba(0,240,255,0.6)'; }}
            onMouseLeave={e => { e.currentTarget.style.transform = 'scale(1)'; e.currentTarget.style.boxShadow = '0 0 32px rgba(0,240,255,0.4)'; }}
          >
            🎵 Browse the Discover Feed
          </a>
        </div>
      </section>

      <div className="section-divider" />

      {/* PRICING */}
      <section className="pricing" id="pricing">
        <div className="container">
          <div className="section-label">{t('landing.pricingLabel')}</div>
          <div style={{ display: 'flex', justifyContent: 'center', marginBottom: 48 }}>
            <span style={{ display: 'inline-flex', alignItems: 'center', gap: 8, background: 'rgba(0,240,255,0.08)', border: '1px solid rgba(0,240,255,0.3)', borderRadius: 20, padding: '6px 16px', fontSize: 13, color: '#00F0FF', fontWeight: 600 }}>
              <span>🎵</span> New users get 3 free songs on signup
            </span>
          </div>

          {/* PAYG — first */}
          <div style={{ textAlign: 'center', marginBottom: 72 }}>
            <h2 style={{
              fontFamily: "'Orbitron', sans-serif",
              fontSize: 'clamp(22px, 4vw, 36px)',
              fontWeight: 900,
              color: '#00F0FF',
              marginBottom: 10,
              letterSpacing: '-0.3px',
              textShadow: '0 0 24px rgba(0,240,255,0.45)',
            }}>
              Just want to try? No commitment needed.
            </h2>
            <p style={{ fontSize: 15, color: '#94a3b8', marginBottom: 36 }}>
              Buy songs instantly — credits never expire
            </p>
            <div style={{ display: 'flex', gap: 16, justifyContent: 'center', flexWrap: 'wrap', maxWidth: 520, margin: '0 auto' }}>
              {[
                { label: '2 Songs', price: '£0.99' },
                { label: '5 Songs', price: '£2.00' },
                { label: '10 Songs', price: '£4.00' },
              ].map(({ label, price }) => (
                <Link
                  key={label}
                  to="/register"
                  style={{
                    flex: '1 1 140px',
                    maxWidth: 160,
                    padding: '22px 12px',
                    borderRadius: 14,
                    border: '1px solid rgba(0,240,255,0.3)',
                    background: 'rgba(0,240,255,0.06)',
                    textDecoration: 'none',
                    textAlign: 'center',
                    boxShadow: '0 0 18px rgba(0,240,255,0.08)',
                    transition: 'all 0.2s',
                  }}
                  onMouseEnter={e => { e.currentTarget.style.background = 'rgba(0,240,255,0.12)'; e.currentTarget.style.boxShadow = '0 0 28px rgba(0,240,255,0.22)'; }}
                  onMouseLeave={e => { e.currentTarget.style.background = 'rgba(0,240,255,0.06)'; e.currentTarget.style.boxShadow = '0 0 18px rgba(0,240,255,0.08)'; }}
                >
                  <div style={{ fontSize: 26, fontWeight: 900, color: '#00F0FF', marginBottom: 6, fontFamily: "'Orbitron', sans-serif" }}>{price}</div>
                  <div style={{ fontSize: 13, color: '#94a3b8', fontWeight: 600 }}>{label}</div>
                </Link>
              ))}
            </div>

            {/* Premium Credits top-ups */}
            <div style={{ marginTop: 32, textAlign: 'center' }}>
              <p style={{ fontSize: 12, color: '#555', letterSpacing: '0.08em', textTransform: 'uppercase', marginBottom: 14 }}>Premium Credits Top-ups</p>
              <div style={{ display: 'flex', gap: 12, justifyContent: 'center', flexWrap: 'wrap' }}>
                {[
                  { label: '5 credits', price: '£2' },
                  { label: '15 credits', price: '£5' },
                ].map(({ label, price }) => (
                  <Link
                    key={label}
                    to="/register"
                    style={{
                      flex: '1 1 130px',
                      maxWidth: 150,
                      padding: '18px 12px',
                      borderRadius: 14,
                      border: '1px solid rgba(255,0,153,0.3)',
                      background: 'rgba(255,0,153,0.05)',
                      textDecoration: 'none',
                      textAlign: 'center',
                      boxShadow: '0 0 14px rgba(255,0,153,0.06)',
                      transition: 'all 0.2s',
                    }}
                    onMouseEnter={e => { e.currentTarget.style.background = 'rgba(255,0,153,0.10)'; e.currentTarget.style.boxShadow = '0 0 22px rgba(255,0,153,0.18)'; }}
                    onMouseLeave={e => { e.currentTarget.style.background = 'rgba(255,0,153,0.05)'; e.currentTarget.style.boxShadow = '0 0 14px rgba(255,0,153,0.06)'; }}
                  >
                    <div style={{ fontSize: 22, fontWeight: 900, color: '#ff0099', marginBottom: 6, fontFamily: "'Orbitron', sans-serif" }}>{price}</div>
                    <div style={{ fontSize: 12, color: '#94a3b8', fontWeight: 600 }}>{label}</div>
                  </Link>
                ))}
              </div>
              <p style={{ fontSize: 12, color: '#555', marginTop: 10 }}>Use for HD Video Animation or stem separation · Credits never expire</p>
            </div>
          </div>

          {/* Divider between PAYG and plans */}
          <div style={{ display: 'flex', alignItems: 'center', gap: 16, marginBottom: 56 }}>
            <div style={{ flex: 1, height: 1, background: 'linear-gradient(90deg, transparent, rgba(0,240,255,0.2))' }} />
            <span style={{ fontSize: 12, color: '#555', letterSpacing: '1px', textTransform: 'uppercase', whiteSpace: 'nowrap' }}>or</span>
            <div style={{ flex: 1, height: 1, background: 'linear-gradient(90deg, rgba(0,240,255,0.2), transparent)' }} />
          </div>

          {/* Subscription plans — second */}
          <div style={{ textAlign: 'center', marginBottom: 40 }}>
            <h2 style={{
              fontFamily: "'Orbitron', sans-serif",
              fontSize: 'clamp(22px, 4vw, 36px)',
              fontWeight: 900,
              background: 'linear-gradient(90deg, #c084fc 0%, #a855f7 50%, #c084fc 100%)',
              WebkitBackgroundClip: 'text',
              WebkitTextFillColor: 'transparent',
              backgroundClip: 'text',
              marginBottom: 10,
              letterSpacing: '-0.3px',
              textShadow: 'none',
            }}>
              Ready to create more? Subscribe and save.
            </h2>
            <p style={{ fontSize: 15, color: '#94a3b8' }}>
              Monthly plans with more songs, avatar videos and YouTube upload
            </p>
          </div>

          <div style={{ display: 'flex', justifyContent: 'center', marginBottom: 28 }}>
            <span style={{ display: 'inline-flex', alignItems: 'center', gap: 8, background: 'rgba(0,240,255,0.08)', border: '1px solid rgba(0,240,255,0.3)', borderRadius: 20, padding: '6px 18px', fontSize: 13, color: '#00F0FF', fontWeight: 600 }}>
              🎉 50% off your first month — no code needed
            </span>
          </div>

          <div className="pricing-grid pricing-grid--music">
            <div className="price-card">
              <div className="plan-name">Free</div>
              <div className="plan-price">£0<span>/mo</span></div>
              <p className="plan-desc">Start creating with no commitment.</p>
              <ul className="plan-features">
                <li>✓ 3 songs to get started</li>
                <li>✓ All 90+ genres</li>
                <li>✓ Cinematic Motion Covers</li>
                <li>✓ Discover feed access</li>
                <li>❌ No stems</li>
              </ul>
              <Link to="/register" className="btn-plan-ghost">Get Started Free</Link>
            </div>

            <div className="price-card">
              <div className="plan-name">Music Starter</div>
              <div className="plan-price">
                <span style={{ textDecoration: 'line-through', opacity: 0.4, fontSize: '0.6em', marginRight: 6 }}>£9</span>£4.50<span>/mo</span>
                <div style={{ fontSize: '0.38em', color: '#00F0FF', marginTop: 3, fontWeight: 600 }}>then £9/month</div>
              </div>
              <p className="plan-desc">For artists getting started with AI music creation.</p>
              <ul className="plan-features">
                <li>✓ 25 songs/month</li>
                <li>✓ 3 premium credits (animations OR stems)</li>
                <li>✓ YouTube upload</li>
                <li>✓ All 90+ genres</li>
                <li>✓ All 27+ accents</li>
              </ul>
              <Link to="/register" className="btn-plan-ghost">Get Music Starter</Link>
            </div>

            <div className="price-card price-featured">
              <div className="plan-name">Music Pro</div>
              <div className="plan-price">
                <span style={{ textDecoration: 'line-through', opacity: 0.4, fontSize: '0.6em', marginRight: 6 }}>£19</span>£9.50<span>/mo</span>
                <div style={{ fontSize: '0.38em', color: '#00F0FF', marginTop: 3, fontWeight: 600 }}>then £19/month</div>
              </div>
              <p className="plan-desc">For active creators who want avatar videos.</p>
              <ul className="plan-features">
                <li>✓ 55 songs/month</li>
                <li>✓ 10 premium credits (animations OR stems)</li>
                <li>✓ 3 avatar videos/month</li>
                <li>✓ YouTube upload</li>
                <li>✓ Genre blending</li>
                <li>✓ DJ Mixer</li>
              </ul>
              <Link to="/register" className="btn-plan-primary">Get Music Pro</Link>
            </div>

            <div className="price-card">
              <div className="plan-name">Music Agency</div>
              <div className="plan-price">
                <span style={{ textDecoration: 'line-through', opacity: 0.4, fontSize: '0.6em', marginRight: 6 }}>£39</span>£19.50<span>/mo</span>
                <div style={{ fontSize: '0.38em', color: '#00F0FF', marginTop: 3, fontWeight: 600 }}>then £39/month</div>
              </div>
              <p className="plan-desc">For prolific creators and label teams.</p>
              <ul className="plan-features">
                <li>✓ 110 songs/month</li>
                <li>✓ 20 premium credits (animations OR stems)</li>
                <li>✓ 10 avatar videos/month</li>
                <li>✓ YouTube upload</li>
                <li>✓ Genre blending</li>
                <li>✓ DJ Mixer</li>
                <li>✓ Priority support</li>
              </ul>
              <Link to="/register" className="btn-plan-ghost">Get Music Agency</Link>
            </div>
          </div>
        </div>
      </section>

      <div className="section-divider" />

      {/* PREMIUM CREDITS EXPLAINER */}
      <section style={{ padding: '72px 24px', background: 'linear-gradient(180deg, #000 0%, #05050f 100%)' }}>
        <div style={{ maxWidth: 640, margin: '0 auto', textAlign: 'center' }}>
          <div style={{ display: 'inline-block', padding: '4px 14px', borderRadius: 20, background: 'rgba(255,0,153,0.10)', border: '1px solid rgba(255,0,153,0.35)', fontSize: 12, fontWeight: 700, color: '#ff0099', letterSpacing: '0.08em', textTransform: 'uppercase', marginBottom: 20 }}>
            ⭐ Premium Credits
          </div>
          <h2 style={{ fontFamily: "'Orbitron', sans-serif", fontSize: 'clamp(22px, 4vw, 34px)', fontWeight: 900, color: '#fff', marginBottom: 14, letterSpacing: '-0.3px' }}>
            What are Premium Credits?
          </h2>
          <p style={{ fontSize: 16, color: 'rgba(255,255,255,0.55)', marginBottom: 40, lineHeight: 1.7 }}>
            Premium credits unlock advanced features — use them for HD Video Animation or stem separation, your choice.
          </p>
          <div style={{ display: 'flex', gap: 20, justifyContent: 'center', flexWrap: 'wrap', marginBottom: 40 }}>
            <div style={{ flex: '1 1 240px', maxWidth: 280, padding: '28px 24px', borderRadius: 16, border: '1px solid rgba(255,0,153,0.3)', background: 'rgba(255,0,153,0.05)', textAlign: 'left' }}>
              <div style={{ fontSize: 28, marginBottom: 12 }}>🎬</div>
              <h3 style={{ fontFamily: "'Orbitron', sans-serif", fontSize: 15, fontWeight: 700, color: '#ff0099', marginBottom: 8 }}>HD Video Animation</h3>
              <p style={{ fontSize: 14, color: 'rgba(255,255,255,0.55)', lineHeight: 1.6, margin: 0 }}>Bring your cover to life with Kling AI — true HD video matched to your genre. (Cinematic motion covers are free for everyone.)</p>
            </div>
            <div style={{ flex: '1 1 240px', maxWidth: 280, padding: '28px 24px', borderRadius: 16, border: '1px solid rgba(255,0,153,0.3)', background: 'rgba(255,0,153,0.05)', textAlign: 'left' }}>
              <div style={{ fontSize: 28, marginBottom: 12 }}>🎚️</div>
              <h3 style={{ fontFamily: "'Orbitron', sans-serif", fontSize: 15, fontWeight: 700, color: '#ff0099', marginBottom: 8 }}>Stem Separator</h3>
              <p style={{ fontSize: 14, color: 'rgba(255,255,255,0.55)', lineHeight: 1.6, margin: 0 }}>Get vocals, drums, bass and instrumental as separate downloadable tracks.</p>
            </div>
          </div>
          <div style={{ padding: '20px 28px', borderRadius: 14, background: 'rgba(255,0,153,0.07)', border: '1px solid rgba(255,0,153,0.2)', display: 'inline-block' }}>
            <p style={{ margin: 0, fontSize: 14, color: 'rgba(255,255,255,0.7)', lineHeight: 1.8 }}>
              <strong style={{ color: '#ff0099' }}>1 premium credit</strong> per feature use<br />
              Top up anytime: <strong style={{ color: '#ff0099' }}>5 credits for £2</strong> or <strong style={{ color: '#ff0099' }}>15 credits for £5</strong><br />
              <span style={{ fontSize: 12, color: '#555' }}>Credits never expire · No subscription needed</span>
            </p>
          </div>
        </div>
      </section>

      <div className="section-divider" />

      {/* FINAL CTA */}
      <section className="final-cta">
        <div className="container">
          <div className="cta-box">
            <div className="cta-glow" />
            <h2>{t('landing.ctaTitle')}</h2>
            <p>{t('landing.ctaSub')}</p>
            <Link to="/register" className="btn-primary btn-lg">
              {t('landing.ctaButton')}
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5"><path d="M5 12h14M12 5l7 7-7 7" /></svg>
            </Link>
          </div>
        </div>
      </section>

      {/* FOOTER */}
      <footer className="footer">
        <div className="container footer-inner">
          <a href="#" className="footer-logo">
            <span className="logo-icon">⚡</span>
            <span>{BRAND.name}</span>
          </a>
          <p className="footer-copy">© {new Date().getFullYear()} Zeus Beats Ltd. All rights reserved. Company No. 17230535</p>
          <div className="footer-links">
            <Link to="/login">{t('landing.footerSignIn')}</Link>
            <a href="#pricing">{t('landing.footerPricing')}</a>
            <a href="#features">{t('landing.footerFeatures')}</a>
            <Link to="/terms">{t('landing.footerTerms')}</Link>
            <Link to="/privacy">{t('landing.footerPrivacy')}</Link>
            <Link to="/refund-policy">{t('landing.footerRefund')}</Link>
            <Link to="/data-deletion">{t('landing.footerDataDeletion')}</Link>
            <Link to="/contact">{t('landing.footerContact')}</Link>
          </div>
          <a
            href="https://t.me/zeusbeatsmusic"
            target="_blank"
            rel="noopener noreferrer"
            className="footer-tg"
          >
            ✈️ Join our Telegram
          </a>
        </div>
      </footer>

      {/* Floating Telegram button — mobile only */}
      <a
        href="https://t.me/zeusbeatsmusic"
        target="_blank"
        rel="noopener noreferrer"
        className="tg-float"
        aria-label="Join our Telegram"
      >
        ✈️ Telegram
      </a>
    </div>
  );
}
