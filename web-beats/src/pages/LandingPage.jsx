import { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { BRAND } from '../brand';
import './LandingPageBeats.css';

export default function LandingPage() {
  const [scrolled, setScrolled] = useState(false);
  const [menuOpen, setMenuOpen] = useState(false);

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
            <li><a href="#features">Features</a></li>
            <li><a href="#how">How It Works</a></li>
            <li><a href="#pricing">Pricing</a></li>
          </ul>
          <div className="nav-cta">
            <Link to="/login" className="btn-nav-ghost">Sign In</Link>
            <Link to="/register" className="btn-nav-primary">Start Free</Link>
          </div>
          <button
            className="hamburger"
            aria-label="Menu"
            onClick={() => setMenuOpen(o => !o)}
          >
            <span /><span /><span />
          </button>
        </div>
        <div className={`mobile-menu${menuOpen ? ' open' : ''}`}>
          <a href="#features" onClick={() => setMenuOpen(false)}>Features</a>
          <a href="#how" onClick={() => setMenuOpen(false)}>How It Works</a>
          <a href="#pricing" onClick={() => setMenuOpen(false)}>Pricing</a>
          <Link to="/login" onClick={() => setMenuOpen(false)}>Sign In</Link>
          <Link to="/register" className="mobile-cta" onClick={() => setMenuOpen(false)}>Start Free →</Link>
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
            AI-Powered · Music Creation
          </div>
          <h1 className="hero-title">
            <span className="hero-word-cyan">CREATE</span>{' '}
            <span className="hero-word-pink">original</span>{' '}
            <span className="hero-word-green">AI music.</span><br />
            <span className="gradient-text">Your music. Your way.</span>
          </h1>
          <p className="hero-sub">
            {BRAND.name} turns your ideas into full original songs — lyrics written by AI, audio produced by Suno. Publish to YouTube and beyond in minutes.
          </p>
          <div className="hero-actions">
            <Link to="/register" className="btn-primary btn-lg">
              Start Creating
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5"><path d="M5 12h14M12 5l7 7-7 7" /></svg>
            </Link>
            <a href="#features" className="btn-ghost btn-lg">See how it works</a>
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
          <div className="section-label">Core Features</div>
          <h2 className="section-title">Everything for AI music.<br /><span className="gradient-text">Nothing you don't need.</span></h2>
          <p className="section-sub">From brief to published track in minutes — {BRAND.name} handles the lyrics, audio, cover art, and distribution.</p>

          <div className="features-grid">
            <div className="feat-card feat-lead">
              <span className="feat-icon">🎵</span>
              <h3>AI Song Generator</h3>
              <p>Turn a text brief into a full original song — lyrics written by Claude AI, audio produced by Suno. Choose from 20+ genres and get a unique track every time, with optional instrumental mode and custom style prompts.</p>
              <div className="feat-tags">
                <span>20+ Genres</span><span>Custom Lyrics</span><span>AI Vocals</span><span>Instrumental Mode</span>
              </div>
            </div>

            <div className="feat-card">
              <span className="feat-icon">🎬</span>
              <h3>Avatar Lip-Sync Videos</h3>
              <p>Turn your song into a video with a realistic AI avatar that lip-syncs to your track. Perfect for YouTube, Instagram Reels, and music promotion.</p>
            </div>

            <div className="feat-card">
              <span className="feat-icon">▶️</span>
              <h3>YouTube Upload</h3>
              <p>Publish your finished track directly to your YouTube channel from inside {BRAND.name} — no extra tools, no manual uploading.</p>
            </div>

            <div className="feat-card">
              <span className="feat-icon">📘</span>
              <h3>Facebook Posting</h3>
              <p>Share your songs to Facebook pages and groups automatically. Grow your audience while {BRAND.name} handles the distribution.</p>
            </div>

            <div className="feat-card">
              <span className="feat-icon">🖼️</span>
              <h3>AI Cover Art</h3>
              <p>Every song gets a unique AI-generated cover image matched to the genre and mood of your track — created automatically at generation time.</p>
            </div>
          </div>
        </div>
      </section>

      <div className="section-divider" />

      {/* HOW IT WORKS */}
      <section className="capabilities" id="how">
        <div className="container">
          <div className="section-label">How {BRAND.name} Works</div>
          <h2 className="section-title">Brief to published.<br /><span className="gradient-text">In minutes.</span></h2>

          <div className="caps-layout">
            <div className="caps-list">
              <div className="cap-item">
                <div className="cap-num">01</div>
                <div className="cap-body">
                  <h4>Describe your track</h4>
                  <p>Type a brief — genre, mood, theme, anything. "Dark hip-hop, late night, motivational" is all {BRAND.name} needs to get started.</p>
                </div>
              </div>
              <div className="cap-item">
                <div className="cap-num">02</div>
                <div className="cap-body">
                  <h4>Zeus writes, Suno generates</h4>
                  <p>Claude AI writes the lyrics and structure. Suno generates the audio. Cover art is created automatically to match the mood.</p>
                </div>
              </div>
              <div className="cap-item">
                <div className="cap-num">03</div>
                <div className="cap-body">
                  <h4>Listen and download</h4>
                  <p>Preview your track in the browser with the waveform player. Download the audio or share a public link with anyone.</p>
                </div>
              </div>
              <div className="cap-item">
                <div className="cap-num">04</div>
                <div className="cap-body">
                  <h4>Publish everywhere</h4>
                  <p>One click uploads your song directly to your YouTube channel. Share to Facebook instantly. No extra tools, no switching apps.</p>
                </div>
              </div>
            </div>

            <div className="caps-terminal">
              <div className="terminal-bar">
                <span className="dot red" /><span className="dot yellow" /><span className="dot green" />
                <span className="terminal-title">beats-session.log</span>
              </div>
              <div className="terminal-body">
                <div className="t-line"><span className="t-user">you</span> <span>Dark hip-hop track — late night grind, motivational</span></div>
                <div className="t-line"><span className="t-zeus">zeus</span> <span>Writing lyrics... midnight themes, hustle hook ready</span></div>
                <div className="t-line"><span className="t-sys">▶</span> <span>Sending to Suno...</span> <span className="t-ok">done</span></div>
                <div className="t-line"><span className="t-sys">▶</span> <span>Generating cover art...</span> <span className="t-ok">done</span></div>
                <div className="t-line"><span className="t-zeus">zeus</span> <span>"Midnight Drive" is ready — 3:42, hip-hop</span></div>
                <div className="t-line t-gap"><span className="t-user">you</span> <span>[clicked Upload to YouTube]</span></div>
                <div className="t-line"><span className="t-zeus">zeus</span> <span>Uploading to your channel...</span></div>
                <div className="t-line"><span className="t-sys">▶</span> <span>Publishing...</span> <span className="t-ok">live ✓</span></div>
                <div className="t-line"><span className="t-zeus">zeus</span> <span>Live → youtu.be/xyz123 🎵</span></div>
                <div className="t-cursor">█</div>
              </div>
            </div>
          </div>
        </div>
      </section>

      <div className="section-divider" />

      {/* PRICING */}
      <section className="pricing" id="pricing">
        <div className="container">
          <div className="section-label">Pricing</div>
          <h2 className="section-title">Simple, honest pricing.</h2>
          <p className="section-sub">Start free. Upgrade when you're ready.</p>

          <div className="pricing-grid pricing-grid--music">
            <div className="price-card">
              <div className="plan-name">Music Starter</div>
              <div className="plan-price">£9<span>/mo</span></div>
              <p className="plan-desc">For artists getting started with AI music creation.</p>
              <ul className="plan-features">
                <li>15 AI songs/month</li>
                <li>YouTube upload</li>
                <li>Song download &amp; share</li>
                <li>All 20+ genres &amp; styles</li>
                <li>AI cover art</li>
              </ul>
              <Link to="/register" className="btn-plan-ghost">Get Music Starter</Link>
            </div>

            <div className="price-card price-featured">
              <div className="plan-name">Music Pro</div>
              <div className="plan-price">£19<span>/mo</span></div>
              <p className="plan-desc">For active creators who want avatar videos.</p>
              <ul className="plan-features">
                <li>40 AI songs/month</li>
                <li>YouTube upload</li>
                <li>3 avatar lip-sync videos/month</li>
                <li>Song download &amp; share</li>
                <li>All 20+ genres &amp; styles</li>
                <li>AI cover art</li>
              </ul>
              <Link to="/register" className="btn-plan-primary">Get Music Pro</Link>
            </div>

            <div className="price-card">
              <div className="plan-name">Music Agency</div>
              <div className="plan-price">£39<span>/mo</span></div>
              <p className="plan-desc">For prolific creators and label teams.</p>
              <ul className="plan-features">
                <li>80 AI songs/month</li>
                <li>YouTube upload</li>
                <li>10 avatar lip-sync videos/month</li>
                <li>Song download &amp; share</li>
                <li>All 20+ genres &amp; styles</li>
                <li>AI cover art</li>
                <li>Facebook posting</li>
              </ul>
              <Link to="/register" className="btn-plan-ghost">Get Music Agency</Link>
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
            <h2>Ready to create your first song?</h2>
            <p>No credit card needed. Start creating in under a minute.</p>
            <Link to="/register" className="btn-primary btn-lg">
              Start for Free
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
          <p className="footer-copy">© {new Date().getFullYear()} {BRAND.name}. {BRAND.tagline}</p>
          <div className="footer-links">
            <Link to="/login">Sign In</Link>
            <a href="#pricing">Pricing</a>
            <a href="#features">Features</a>
            <Link to="/terms">Terms</Link>
            <Link to="/privacy">Privacy</Link>
          </div>
        </div>
      </footer>
    </div>
  );
}
