import { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import './LandingPageV3.css';

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
            <span className="logo-text">Zeus <span className="logo-accent">AI</span></span>
          </a>
          <ul className="nav-links">
            <li><a href="#features">Features</a></li>
            <li><a href="#capabilities">What It Does</a></li>
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
          <a href="#capabilities" onClick={() => setMenuOpen(false)}>What It Does</a>
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
        </div>
        <div className="container hero-content">
          <div className="hero-badge">
            <span className="badge-dot" />
            Research · Create · Build
          </div>
          <h1 className="hero-title">
            One AI platform to research, create,<br />
            <span className="gradient-text">build and get things done.</span>
          </h1>
          <p className="hero-sub">
            Get answers with Ask Zeus, search the live web and compare AI perspectives with Zeus Council. Build websites, create music with Zeus Beats, create memorial QR tributes and use practical business tools—all in one place. Ask Zeus and Zeus Council are currently in private beta.
          </p>
          <div className="hero-actions">
            <Link to="/register" className="btn-primary btn-lg">
              Start for Free
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5"><path d="M5 12h14M12 5l7 7-7 7" /></svg>
            </Link>
            <a href="#features" className="btn-ghost btn-lg">See what it can do</a>
          </div>

          <p style={{ marginTop: 16, fontSize: 14, color: 'rgba(255,255,255,0.55)' }}>
            🎵 Just want music?{' '}
            <a href="https://zeusbeats.com" style={{ color: '#00f0ff', fontWeight: 600, textDecoration: 'none' }}>
              Try Zeus Beats
            </a>
          </p>

          {/* Chat mockup */}
          <div className="hero-mockup">
            <div className="mockup-bar">
              <span className="dot red" /><span className="dot yellow" /><span className="dot green" />
              <span className="mockup-title">Zeus AI</span>
            </div>
            <div className="mockup-body">
              <div className="chat-msg user">Build me a landing page for my plumbing business in Manchester</div>
              <div className="chat-msg zeus">
                <span className="zeus-label">⚡ Zeus</span>
                On it! Building your site now — dark navy theme, bold hero, services grid, contact form. Deploying to Netlify...
                <div className="chat-progress">
                  <div className="progress-bar"><div className="progress-fill" /></div>
                  <span className="progress-text">Deploying... ✓ Live at mike-plumbing-mcr.netlify.app</span>
                </div>
              </div>
              <div className="chat-msg user">Now write me 3 Instagram captions for my launch</div>
              <div className="chat-msg zeus">
                <span className="zeus-label">⚡ Zeus</span>
                Here are 3 captions ready to post — punchy, local, and conversion-focused. 🔧
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* FEATURES GRID */}
      <section className="features" id="features">
        <div className="container">
          <div className="section-label">What Zeus Can Do</div>
          <h2 className="section-title">Everything Zeus Can Do.<br /><span className="gradient-text">All in one place.</span></h2>
          <p className="section-sub">Answers, research, websites, music, tributes and business tools—choose what you need from one AI platform.</p>

          {/* RESEARCH, CREATE & BUILD */}
          <div style={{ marginBottom: 8 }}>
            <div style={{ fontSize: 13, fontWeight: 700, color: 'var(--accent-1)', letterSpacing: '0.08em', textTransform: 'uppercase', marginBottom: 14, marginTop: 40 }}>🎵 Research, Create &amp; Build</div>
            <div className="features-grid">
              <div className="feat-card feat-lead">
                <span className="feat-icon">🎵</span>
                <h3>Ask Zeus</h3>
                <p>Ask questions, explore ideas and get help with writing and everyday tasks.</p>
                <div className="feat-tags"><span>Answers</span><span>Writing</span><span>Ideas</span><span>Everyday Tasks</span></div>
              </div>
              <div className="feat-card"><span className="feat-icon">🎸</span><h3>Live Web Search</h3><p>Turn on Search the web to research current information, with source links to check the evidence.</p></div>
              <div className="feat-card"><span className="feat-icon">🎨</span><h3>Zeus Council</h3><p>Compare responses from multiple AIs and read a final Zeus Verdict. Optional web search gives them shared evidence.</p></div>
              <div className="feat-card"><span className="feat-icon">🎬</span><h3>Website Building</h3><p>Describe the website you need, refine its content and design, and publish when ready.</p></div>
              <div className="feat-card"><span className="feat-icon">🎛️</span><h3>Zeus Beats</h3><p>Create original music from your ideas and explore different genres, moods and sounds.</p></div>
              <div className="feat-card"><span className="feat-icon">🔄</span><h3>Memorial QR &amp; Tributes</h3><p>Create a digital tribute and connect people to it through a memorial QR code.</p></div>
              <div className="feat-card"><span className="feat-icon">🎤</span><h3>Business Tools</h3><p>Draft business content, plan projects and work through practical tasks.</p></div>
              <div className="feat-card"><span className="feat-icon">📋</span><h3>Publishing &amp; Sharing</h3><p>Share and publish your work using the options available within each Zeus tool.</p></div>
            </div>
          </div>

          {/* PUBLISHING */}
          <div style={{ marginBottom: 8 }}>
            <div style={{ fontSize: 13, fontWeight: 700, color: 'var(--accent-1)', letterSpacing: '0.08em', textTransform: 'uppercase', marginBottom: 14, marginTop: 40 }}>🌐 Publishing &amp; Sharing</div>
            <div className="features-grid">
              <div className="feat-card"><span className="feat-icon">▶️</span><h3>YouTube Upload</h3><p>One click — song goes live on your channel. Zeus uploads the audio, sets the title, and handles everything.</p></div>
              <div className="feat-card"><span className="feat-icon">📘</span><h3>Facebook Auto-posting</h3><p>Zeus writes the caption and posts directly to your Facebook page — no copying, no switching apps.</p></div>
              <div className="feat-card"><span className="feat-icon">✈️</span><h3>Telegram Sharing</h3><p>Share directly to your Telegram channel with one tap. Your audience gets it instantly.</p></div>
              <div className="feat-card"><span className="feat-icon">🔍</span><h3>Music Search</h3><p>Explore music for inspiration, then describe your own original direction through genre, mood and instrumentation.</p></div>
            </div>
          </div>

          {/* WEBSITE BUILDER */}
          <div style={{ marginBottom: 8 }}>
            <div style={{ fontSize: 13, fontWeight: 700, color: 'var(--accent-1)', letterSpacing: '0.08em', textTransform: 'uppercase', marginBottom: 14, marginTop: 40 }}>🖥️ Website Builder</div>
            <div className="features-grid">
              <div className="feat-card feat-lead">
                <span className="feat-icon">🌐</span>
                <h3>AI Website Builder</h3>
                <p>Describe your site in plain English — Zeus builds and deploys it. Clean HTML, CSS &amp; JS with mobile-first design. No coding required.</p>
                <div className="feat-tags"><span>Landing Pages</span><span>Portfolios</span><span>Business Sites</span><span>E-commerce Layouts</span></div>
              </div>
              <div className="feat-card"><span className="feat-icon">🚀</span><h3>Google Indexing</h3><p>Agency plan gets your site indexed in Google automatically — your clients appear in search results faster.</p></div>
              <div className="feat-card"><span className="feat-icon">📘</span><h3>Facebook Integration</h3><p>Post updates directly from Zeus to your Facebook page — keep your audience in the loop without leaving the chat.</p></div>
            </div>
          </div>

          {/* ADVANCED CONTROLS */}
          <div style={{ marginBottom: 8 }}>
            <div style={{ fontSize: 13, fontWeight: 700, color: 'var(--accent-1)', letterSpacing: '0.08em', textTransform: 'uppercase', marginBottom: 14, marginTop: 40 }}>🎛️ Advanced Controls</div>
            <div className="features-grid">
              <div className="feat-card"><span className="feat-icon">🤖</span><h3>Model Selector</h3><p>Choose your Suno model — V4, V5, or V5.5 for the latest sound quality and features.</p></div>
              <div className="feat-card"><span className="feat-icon">🎤</span><h3>Vocal Gender</h3><p>Male, Female, or Duet — control who sings your track.</p></div>
              <div className="feat-card"><span className="feat-icon">🗣️</span><h3>27+ Accents</h3><p>Punjabi, Jamaican, Grime MC, West African, Colombian, Puerto Rican, British, American Hip-Hop, Irish, Scottish and more.</p></div>
              <div className="feat-card"><span className="feat-icon">🔞</span><h3>Explicit Toggle</h3><p>Enable explicit content for grime, drill, and street genres — authentic language where it fits.</p></div>
              <div className="feat-card"><span className="feat-icon">🌀</span><h3>Weirdness Control</h3><p>Slide from Safe to Experimental — control how conventional or boundary-pushing your track sounds.</p></div>
              <div className="feat-card"><span className="feat-icon">🚫</span><h3>Avoid Tags</h3><p>Tell Zeus what NOT to include — no piano, no trumpet, no slow sections. You're in control.</p></div>
              <div className="feat-card"><span className="feat-icon">🎨</span><h3>Music Inspiration</h3><p>Shape an original musical direction with genres, moods and instruments that fit your idea.</p></div>
            </div>
          </div>

          {/* ACCOUNT FEATURES */}
          <div style={{ marginBottom: 8 }}>
            <div style={{ fontSize: 13, fontWeight: 700, color: 'var(--accent-1)', letterSpacing: '0.08em', textTransform: 'uppercase', marginBottom: 14, marginTop: 40 }}>👤 Account Features</div>
            <div className="features-grid">
              <div className="feat-card"><span className="feat-icon">🎭</span><h3>Artist Name</h3><p>Set your stage name — it's shown on all your songs and videos automatically.</p></div>
              <div className="feat-card"><span className="feat-icon">⭐</span><h3>Favourites</h3><p>Star and save your best songs. Find your hits instantly without scrolling through everything.</p></div>
              <div className="feat-card"><span className="feat-icon">🔎</span><h3>Song Filters</h3><p>All Songs, Favourites, Recent — find exactly what you need in seconds.</p></div>
              <div className="feat-card"><span className="feat-icon">🌍</span><h3>Multi-language</h3><p>English, French, Spanish, German, Portuguese — Zeus Beats speaks your language.</p></div>
            </div>
          </div>
        </div>
      </section>

      {/* CAPABILITIES */}
      <section className="capabilities" id="capabilities">
        <div className="container">
          <div className="section-label">How Zeus Works</div>
          <h2 className="section-title">One platform.<br /><span className="gradient-text">More ways to get things done.</span></h2>

          <div className="caps-layout">
            <div className="caps-list">
              <div className="cap-item">
                <div className="cap-num">01</div>
                <div className="cap-body">
                  <h4>Tell Zeus what you need</h4>
                  <p>Type naturally — no prompts to learn, no templates to fill in. Just describe what you want like you're talking to a colleague.</p>
                </div>
              </div>
              <div className="cap-item">
                <div className="cap-num">02</div>
                <div className="cap-body">
                  <h4>Use the tools your task needs</h4>
                  <p>Research with Ask Zeus, compare AI perspectives with Council, or open a creation tool. For live web results in Ask Zeus or Council, turn on Search the web and enter a public search query.</p>
                </div>
              </div>
              <div className="cap-item">
                <div className="cap-num">03</div>
                <div className="cap-body">
                  <h4>Deploy or download instantly</h4>
                  <p>Say "deploy it" and your site is live on Netlify with a real URL. Or download the ZIP to host anywhere you like.</p>
                </div>
              </div>
              <div className="cap-item">
                <div className="cap-num">04</div>
                <div className="cap-body">
                  <h4>Iterate in seconds</h4>
                  <p>"Change the colour to navy", "add a testimonials section", "make the headline punchier" — Zeus updates and redeploys instantly.</p>
                </div>
              </div>
            </div>

            <div className="caps-terminal">
              <div className="terminal-bar">
                <span className="dot red" /><span className="dot yellow" /><span className="dot green" />
                <span className="terminal-title">zeus-session.log</span>
              </div>
              <div className="terminal-body">
                <div className="t-line"><span className="t-user">you</span> <span>Build a florist website — soft pink, elegant, one page</span></div>
                <div className="t-line"><span className="t-zeus">zeus</span> <span>Planning: hero → about → services → gallery → contact</span></div>
                <div className="t-line"><span className="t-sys">▶</span> <span>Writing HTML...</span> <span className="t-ok">done</span></div>
                <div className="t-line"><span className="t-sys">▶</span> <span>Writing CSS...</span> <span className="t-ok">done</span></div>
                <div className="t-line"><span className="t-sys">▶</span> <span>Deploying to Netlify...</span> <span className="t-ok">live ✓</span></div>
                <div className="t-line"><span className="t-zeus">zeus</span> <span>Your site is live → hayleys-floristry.netlify.app</span></div>
                <div className="t-line t-gap"><span className="t-user">you</span> <span>Now write me an about page bio for Hayley</span></div>
                <div className="t-line"><span className="t-zeus">zeus</span> <span>Here's a warm, personal 150-word bio ready to use.</span></div>
                <div className="t-line t-gap"><span className="t-user">you</span> <span>Generate a hero image — pink roses, sunlit, premium</span></div>
                <div className="t-line"><span className="t-zeus">zeus</span> <span>Image generated ✓ — dropping into the project now.</span></div>
                <div className="t-line"><span className="t-sys">▶</span> <span>Redeploying...</span> <span className="t-ok">updated ✓</span></div>
                <div className="t-cursor">█</div>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* PRICING */}
      <section className="pricing" id="pricing">
        <div className="container">
          <div className="section-label">Pricing</div>
          <h2 className="section-title">Simple, honest pricing.</h2>
          <p className="section-sub">Start free. Upgrade when you're ready.</p>
          <p className="section-sub">Ask Zeus and Zeus Council use separate Hub Credits. These subscriptions do not include a monthly Hub Credit allowance.</p>

          <div className="pricing-grid">
            <div className="price-card">
              <div className="plan-name">Free</div>
              <div className="plan-price">£0<span>/mo</span></div>
              <p className="plan-desc">Try Zeus with no commitment. Perfect for exploring what's possible.</p>
              <ul className="plan-features">
                <li>✓ 30 messages per day with the website-builder assistant</li>
                <li>✓ AI chat assistant</li>
                <li>✓ Content writing</li>
                <li>✓ Web research</li>
                <li>✓ 3 song credits to get started — one-time allowance</li>
                <li className="feat-dim">✗ Website builds</li>
                <li className="feat-dim">✗ Netlify deployment</li>
              </ul>
              <Link to="/register" className="btn-plan-ghost">Get Started Free</Link>
            </div>

            <div className="price-card">
              <div className="plan-name">Pro</div>
              <div className="plan-price">£29<span>/mo</span></div>
              <p className="plan-desc">Everything you need to run a web design business with AI.</p>
              <ul className="plan-features">
                <li>✓ Unlimited chat with the website-builder assistant</li>
                <li>✓ 5 website builds/month</li>
                <li>✓ AI chat assistant</li>
                <li>✓ Deploy to Netlify</li>
                <li>✓ AI image generation</li>
                <li>✓ Email via Gmail</li>
                <li>✓ Client &amp; project CRM</li>
                <li>✓ Priority support</li>
                <li>✓ 20 song credits/month</li>
                <li>✓ 10 animations/month</li>
                <li>✓ AI song download &amp; share</li>
              </ul>
              <Link to="/register" className="btn-plan-ghost">Start Pro</Link>
            </div>

            <div className="price-card">
              <div className="plan-name">Agency</div>
              <div className="plan-price">£79<span>/mo</span></div>
              <p className="plan-desc">For teams and agencies running multiple clients at scale.</p>
              <ul className="plan-features">
                <li>✓ Unlimited chat with the website-builder assistant</li>
                <li>✓ 10 website builds/month</li>
                <li>✓ AI chat assistant</li>
                <li>✓ Everything in Pro</li>
                <li>✓ Team features</li>
                <li>✓ Priority support</li>
                <li>✓ 70 song credits/month</li>
                <li>✓ 20 animations/month</li>
                <li>✓ YouTube music upload</li>
                <li>✓ Explicit content toggle</li>
                <li>✓ Google indexing</li>
                <li>✓ Facebook posting</li>
              </ul>
              <Link to="/register" className="btn-plan-ghost">Start Agency</Link>
            </div>

            <div className="price-card price-featured price-enterprise">
              <div className="plan-name">Enterprise</div>
              <div className="plan-price">£150<span>/mo</span></div>
              <p className="plan-desc">The full Zeus AI power stack. Autonomous agents build and deploy sites while you sleep.</p>
              <ul className="plan-features">
                <li>✓ Unlimited chat with the website-builder assistant</li>
                <li>✓ Unlimited website builds</li>
                <li>✓ Multi-agent website builder</li>
                <li>✓ Background tasks</li>
                <li>✓ Scheduled tasks</li>
                <li>✓ Appointment booking</li>
                <li>✓ Priority support</li>
                <li>✓ 100 song credits/month</li>
                <li>✓ 50 animations/month</li>
                <li>✓ All Agency music features</li>
              </ul>
              <Link to="/register" className="btn-plan-primary">Start Enterprise</Link>
            </div>
          </div>

          {/* Music Plans */}
          <div style={{ marginTop: '5rem' }}>
            <h3 className="section-title" style={{ fontSize: '1.6rem', marginBottom: '0.5rem' }}>
              Just want the music?{' '}
              <span className="gradient-text">No website builder needed.</span>
            </h3>
            <p className="section-sub" style={{ marginBottom: '2rem' }}>
              Standalone music plans — all the AI music tools, none of the website stuff.
            </p>
            <div style={{ display: 'flex', justifyContent: 'center', marginBottom: 28 }}>
              <span style={{ display: 'inline-flex', alignItems: 'center', gap: 8, background: 'rgba(0,245,255,0.08)', border: '1px solid rgba(0,245,255,0.3)', borderRadius: 20, padding: '6px 18px', fontSize: 13, color: '#00f5ff', fontWeight: 600 }}>
                🎉 50% off your first month — no code needed
              </span>
            </div>
            <div className="pricing-grid pricing-grid--music">
              <div className="price-card">
                <div className="plan-name">Music Starter</div>
                <div className="plan-price">
                  <span style={{ textDecoration: 'line-through', opacity: 0.4, fontSize: '0.6em', marginRight: 6 }}>£9</span>£4.50<span>/mo</span>
                  <div style={{ fontSize: '0.38em', color: '#00f5ff', marginTop: 3, fontWeight: 600 }}>then £9/month</div>
                </div>
                <p className="plan-desc">For artists getting started with AI music creation.</p>
                <ul className="plan-features">
                  <li>✓ 30 song credits/month — up to 60 generated versions</li>
                  <li>✓ 3 animated cover arts/month</li>
                  <li>✓ YouTube upload</li>
                  <li>✓ Song download &amp; share</li>
                  <li>✓ All 100+ genres &amp; styles</li>
                  <li>✓ All 27+ accents</li>
                </ul>
                <Link to="/register" className="btn-plan-ghost">Get Music Starter</Link>
              </div>

              <div className="price-card">
                <div className="plan-name">Music Pro</div>
                <div className="plan-price">
                  <span style={{ textDecoration: 'line-through', opacity: 0.4, fontSize: '0.6em', marginRight: 6 }}>£19</span>£9.50<span>/mo</span>
                  <div style={{ fontSize: '0.38em', color: '#00f5ff', marginTop: 3, fontWeight: 600 }}>then £19/month</div>
                </div>
                <p className="plan-desc">For active creators who want avatar videos.</p>
                <ul className="plan-features">
                  <li>✓ 75 song credits/month — up to 150 generated versions</li>
                  <li>✓ 10 animated cover arts/month</li>
                  <li>✓ 3 avatar lip-sync videos/month</li>
                  <li>✓ YouTube upload</li>
                  <li>✓ Genre blending</li>
                  <li>✓ DJ Mixer</li>
                </ul>
                <Link to="/register" className="btn-plan-ghost">Get Music Pro</Link>
              </div>

              <div className="price-card">
                <div className="plan-name">Music Agency</div>
                <div className="plan-price">
                  <span style={{ textDecoration: 'line-through', opacity: 0.4, fontSize: '0.6em', marginRight: 6 }}>£39</span>£19.50<span>/mo</span>
                  <div style={{ fontSize: '0.38em', color: '#00f5ff', marginTop: 3, fontWeight: 600 }}>then £39/month</div>
                </div>
                <p className="plan-desc">For prolific creators and label teams.</p>
                <ul className="plan-features">
                  <li>✓ 150 song credits/month — up to 300 generated versions</li>
                  <li>✓ 20 animated cover arts/month</li>
                  <li>✓ 10 avatar lip-sync videos/month</li>
                  <li>✓ YouTube upload</li>
                  <li>✓ Genre blending</li>
                  <li>✓ DJ Mixer</li>
                  <li>✓ Priority support</li>
                </ul>
                <Link to="/register" className="btn-plan-ghost">Get Music Agency</Link>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* FINAL CTA */}
      <section className="final-cta">
        <div className="container">
          <div className="cta-box">
            <div className="cta-glow" />
            <h2>Ready to build something?</h2>
            <p>No credit card needed. Start chatting with Zeus in under a minute.</p>
            <Link to="/register" className="btn-primary btn-lg">
              Launch Zeus Free
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5"><path d="M5 12h14M12 5l7 7-7 7" /></svg>
            </Link>
          </div>
        </div>
      </section>

      {/* FOOTER */}
      <footer className="footer">
        <div className="container footer-inner">
          <a href="#" className="logo">
            <span className="logo-icon">⚡</span>
            <span className="logo-text">Zeus <span className="logo-accent">AI</span></span>
          </a>
          <p className="footer-copy">© {new Date().getFullYear()} Zeus Beats Ltd. All rights reserved. Company No. 17230535</p>
          <div className="footer-links">
            <Link to="/login">Sign In</Link>
            <a href="#pricing">Pricing</a>
            <a href="#features">Features</a>
            <Link to="/terms">Terms</Link>
            <Link to="/privacy">Privacy Policy</Link>
            <Link to="/refund-policy">Refund Policy</Link>
            <Link to="/data-deletion">Data Deletion</Link>
            <Link to="/contact">Contact</Link>
            <a href="https://zeusbeats.com" style={{ color: '#00f0ff', fontWeight: 600 }}>🎵 Zeus Beats</a>
          </div>
        </div>
      </footer>
    </div>
  );
}
