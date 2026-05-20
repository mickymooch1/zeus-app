import { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { BRAND } from '../brand';
import { LanguageSelector } from '../components/LanguageSelector';
import './LandingPageBeats.css';

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

          {/* MUSIC CREATION */}
          <div style={{ marginBottom: 8 }}>
            <div style={{ fontSize: 13, fontWeight: 700, color: '#00f0ff', letterSpacing: '0.08em', textTransform: 'uppercase', marginBottom: 14 }}>🎵 Music Creation</div>
            <div className="features-grid">
              <div className="feat-card feat-lead">
                <span className="feat-icon">🎵</span>
                <h3>AI Song Generator</h3>
                <p>Turn a text brief into a full original song — lyrics by Claude AI, audio by Suno. Full lyrics and vocals in 60 seconds.</p>
                <div className="feat-tags"><span>35+ Genres</span><span>Custom Lyrics</span><span>AI Vocals</span><span>Instrumental Mode</span></div>
              </div>
              <div className="feat-card"><span className="feat-icon">🎸</span><h3>35+ Genres</h3><p>Soul, Grime, D&amp;B, Afrobeats, Jungle, Jazz, Drill, Amapiano, Niche, UK Garage, Lo-Fi, Reggae, Bassline and more.</p></div>
              <div className="feat-card"><span className="feat-icon">🎨</span><h3>Animated Cover Art</h3><p>AI generates and animates your artwork automatically — every song gets a unique, genre-matched cover image that moves.</p></div>
              <div className="feat-card"><span className="feat-icon">🎬</span><h3>Avatar Lip-Sync Videos</h3><p>AI performer sings your track in HD video. Perfect for YouTube, Instagram Reels, and music promotion.</p></div>
              <div className="feat-card"><span className="feat-icon">🎛️</span><h3>DJ Mixer</h3><p>Mix your songs together and record your set — a built-in DJ deck for blending your AI tracks.</p></div>
              <div className="feat-card"><span className="feat-icon">🔄</span><h3>Song Remake</h3><p>Regenerate any song in a completely different genre — same lyrics, totally new sound.</p></div>
              <div className="feat-card"><span className="feat-icon">🎤</span><h3>Voice to Text</h3><p>Describe your song by speaking, not typing. Hit the mic and Zeus transcribes your idea instantly.</p></div>
              <div className="feat-card"><span className="feat-icon">📋</span><h3>Song Templates</h3><p>One-click starters: Club Banger, Emotional R&amp;B, Grime Bars and more — skip the blank page.</p></div>
            </div>
          </div>

          {/* PUBLISHING */}
          <div style={{ marginBottom: 8 }}>
            <div style={{ fontSize: 13, fontWeight: 700, color: '#00f0ff', letterSpacing: '0.08em', textTransform: 'uppercase', marginBottom: 14, marginTop: 40 }}>🌐 Publishing &amp; Sharing</div>
            <div className="features-grid">
              <div className="feat-card"><span className="feat-icon">▶️</span><h3>YouTube Upload</h3><p>One click — song goes live on your channel. Zeus uploads the audio, sets the title, and handles everything.</p></div>
              <div className="feat-card"><span className="feat-icon">📘</span><h3>Facebook Auto-posting</h3><p>Zeus writes the caption and posts directly to your Facebook page — no copying, no switching apps.</p></div>
              <div className="feat-card"><span className="feat-icon">✈️</span><h3>Telegram Sharing</h3><p>Share directly to your Telegram channel with one tap. Your audience gets it instantly.</p></div>
              <div className="feat-card"><span className="feat-icon">🔍</span><h3>Music Search</h3><p>Find any artist, copy their style, generate your version — search for inspiration and make it your own.</p></div>
            </div>
          </div>

          {/* ADVANCED CONTROLS */}
          <div style={{ marginBottom: 8 }}>
            <div style={{ fontSize: 13, fontWeight: 700, color: '#00f0ff', letterSpacing: '0.08em', textTransform: 'uppercase', marginBottom: 14, marginTop: 40 }}>🎛️ Advanced Controls</div>
            <div className="features-grid">
              <div className="feat-card"><span className="feat-icon">🤖</span><h3>Model Selector</h3><p>Choose your Suno model — V4, V5, or V5.5 for the latest sound quality and features.</p></div>
              <div className="feat-card"><span className="feat-icon">🎤</span><h3>Vocal Gender</h3><p>Male, Female, or Duet — control who sings your track.</p></div>
              <div className="feat-card"><span className="feat-icon">🗣️</span><h3>25+ Accents</h3><p>British, Jamaican, Grime MC, West African, American Hip-Hop, Irish, Scottish and more — pinpoint the vocal style.</p></div>
              <div className="feat-card"><span className="feat-icon">🔞</span><h3>Explicit Toggle</h3><p>Enable explicit content for grime, drill, and street genres — authentic language where it fits.</p></div>
              <div className="feat-card"><span className="feat-icon">🌀</span><h3>Weirdness Control</h3><p>Slide from Safe to Experimental — control how conventional or boundary-pushing your track sounds.</p></div>
              <div className="feat-card"><span className="feat-icon">🚫</span><h3>Avoid Tags</h3><p>Tell Zeus what NOT to include — no piano, no trumpet, no slow sections. You're in control.</p></div>
              <div className="feat-card"><span className="feat-icon">🎨</span><h3>Inspired by Artist</h3><p>Type any artist name for style inspiration — Zeus captures the vibe without copying the sound.</p></div>
            </div>
          </div>

          {/* ACCOUNT FEATURES */}
          <div style={{ marginBottom: 8 }}>
            <div style={{ fontSize: 13, fontWeight: 700, color: '#00f0ff', letterSpacing: '0.08em', textTransform: 'uppercase', marginBottom: 14, marginTop: 40 }}>👤 Account Features</div>
            <div className="features-grid">
              <div className="feat-card"><span className="feat-icon">🎭</span><h3>Artist Name</h3><p>Set your stage name — it's shown on all your songs and videos automatically.</p></div>
              <div className="feat-card"><span className="feat-icon">⭐</span><h3>Favourites</h3><p>Star and save your best songs. Find your hits instantly without scrolling through everything.</p></div>
              <div className="feat-card"><span className="feat-icon">🔎</span><h3>Song Filters</h3><p>All Songs, Favourites, Recent — find exactly what you need in seconds.</p></div>
              <div className="feat-card"><span className="feat-icon">🌍</span><h3>Multi-language</h3><p>English, French, Spanish, German, Portuguese — Zeus Beats speaks your language.</p></div>
            </div>
          </div>
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
                <div className="t-line"><span className="t-sys">▶</span> <span>Animating cover art...</span> <span className="t-ok">done</span></div>
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

      {/* PRICING */}
      <section className="pricing" id="pricing">
        <div className="container">
          <div className="section-label">{t('landing.pricingLabel')}</div>
          <div style={{ display: 'flex', justifyContent: 'center', marginBottom: 48 }}>
            <span style={{ display: 'inline-flex', alignItems: 'center', gap: 8, background: 'rgba(0,240,255,0.08)', border: '1px solid rgba(0,240,255,0.3)', borderRadius: 20, padding: '6px 16px', fontSize: 13, color: '#00F0FF', fontWeight: 600 }}>
              <span>🎵</span> New users get 5 free songs on signup
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

          <div className="pricing-grid pricing-grid--music">
            <div className="price-card">
              <div className="plan-name">{t('landing.starterName')}</div>
              <div className="plan-price">£9<span>/mo</span></div>
              <p className="plan-desc">{t('landing.starterDesc')}</p>
              <ul className="plan-features">
                <li>{t('billing.plans.features.songs15')}</li>
                <li>{t('billing.plans.features.youtube')}</li>
                <li>{t('billing.plans.features.download')}</li>
                <li>{t('billing.plans.features.genres')}</li>
                <li>{t('billing.plans.features.coverArt')}</li>
              </ul>
              <Link to="/register" className="btn-plan-ghost">{t('landing.getStarter')}</Link>
            </div>

            <div className="price-card price-featured">
              <div className="plan-name">{t('landing.proName')}</div>
              <div className="plan-price">£19<span>/mo</span></div>
              <p className="plan-desc">{t('landing.proDesc')}</p>
              <ul className="plan-features">
                <li>{t('billing.plans.features.songs40')}</li>
                <li>{t('billing.plans.features.youtube')}</li>
                <li>{t('billing.plans.features.avatar3')}</li>
                <li>{t('billing.plans.features.download')}</li>
                <li>{t('billing.plans.features.genres')}</li>
                <li>{t('billing.plans.features.coverArt')}</li>
              </ul>
              <Link to="/register" className="btn-plan-primary">{t('landing.getPro')}</Link>
            </div>

            <div className="price-card">
              <div className="plan-name">{t('landing.agencyName')}</div>
              <div className="plan-price">£39<span>/mo</span></div>
              <p className="plan-desc">{t('landing.agencyDesc')}</p>
              <ul className="plan-features">
                <li>{t('billing.plans.features.songs80')}</li>
                <li>{t('billing.plans.features.youtube')}</li>
                <li>{t('billing.plans.features.avatar10')}</li>
                <li>{t('billing.plans.features.download')}</li>
                <li>{t('billing.plans.features.genres')}</li>
                <li>{t('billing.plans.features.coverArt')}</li>
                <li>{t('billing.plans.features.facebook')}</li>
              </ul>
              <Link to="/register" className="btn-plan-ghost">{t('landing.getAgency')}</Link>
            </div>
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
        </div>
      </footer>
    </div>
  );
}
