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
            AI-Powered · Built for Business
          </div>
          <h1 className="hero-title">
            Your AI assistant that<br />
            <span className="gradient-text">builds, writes &amp; deploys</span>
          </h1>
          <p className="hero-sub">
            Zeus is more than a website builder. It's a full AI business assistant — chat to create stunning websites, write copy, generate images, manage clients, and deploy live to Netlify in seconds.
          </p>
          <div className="hero-actions">
            <Link to="/register" className="btn-primary btn-lg">
              Start for Free
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5"><path d="M5 12h14M12 5l7 7-7 7" /></svg>
            </Link>
            <a href="#features" className="btn-ghost btn-lg">See what it can do</a>
          </div>

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
          <div className="section-label">Core Features</div>
          <h2 className="section-title">Everything you need.<br /><span className="gradient-text">Nothing you don't.</span></h2>
          <p className="section-sub">From idea to live website in minutes — Zeus handles the building, writing, designing, and deploying.</p>

          <div className="features-grid">
            <div className="feat-card feat-lead">
              <span className="feat-icon">🌐</span>
              <h3>Website Builder</h3>
              <p>Describe any website in plain English and Zeus builds it — clean HTML, CSS &amp; JS with mobile-first responsive design, smooth animations, and modern layouts. No coding required.</p>
              <div className="feat-tags">
                <span>Landing Pages</span><span>Portfolios</span><span>Business Sites</span><span>E-commerce Layouts</span>
              </div>
            </div>

            <div className="feat-card">
              <span className="feat-icon">🚀</span>
              <h3>Deploy to Netlify</h3>
              <p>One command and your site is live. Zeus deploys directly to Netlify with a shareable URL — no FTP, no hosting dashboards, no faff.</p>
            </div>

            <div className="feat-card">
              <span className="feat-icon">📦</span>
              <h3>Upload &amp; Unzip</h3>
              <p>Got an existing project? Upload a ZIP file and Zeus will unzip it, read the code, fix issues, and redeploy — all in the same chat.</p>
            </div>

            <div className="feat-card">
              <span className="feat-icon">✍️</span>
              <h3>Content Writing</h3>
              <p>Essays, blog posts, CVs, cover letters, proposals, website copy, cold emails — Zeus writes it all with the right tone and structure.</p>
            </div>

            <div className="feat-card">
              <span className="feat-icon">🎨</span>
              <h3>AI Image Generation</h3>
              <p>Generate logos, hero banners, illustrations, and mockups from a text prompt. Real images, ready to drop into your site.</p>
            </div>

            <div className="feat-card">
              <span className="feat-icon">📊</span>
              <h3>Stock &amp; Market Data</h3>
              <p>Get real-time stock prices, P/E ratios, market cap, and key financial stats for any ticker — right inside your conversation.</p>
            </div>

            <div className="feat-card">
              <span className="feat-icon">🔍</span>
              <h3>Live Web Research</h3>
              <p>Zeus searches the web and fetches live pages so your content is always current — competitor research, industry news, product info.</p>
            </div>

            <div className="feat-card">
              <span className="feat-icon">📧</span>
              <h3>Send Emails via Gmail</h3>
              <p>Draft and send client proposals, follow-ups, and invoices directly from Zeus — connected to your Gmail account.</p>
            </div>

            <div className="feat-card">
              <span className="feat-icon">🧠</span>
              <h3>Persistent Memory</h3>
              <p>Zeus remembers your clients, preferences, past projects, and learnings — getting smarter and more personalised every session.</p>
            </div>

            <div className="feat-card">
              <span className="feat-icon">👥</span>
              <h3>Client &amp; Project CRM</h3>
              <p>Track clients, active projects, budgets, and live URLs. Zeus manages your entire pipeline and recalls every detail on demand.</p>
            </div>

            <div className="feat-card">
              <span className="feat-icon">📁</span>
              <h3>File &amp; Code Management</h3>
              <p>Read, write, edit, and organise files across your whole project. Search codebases, fix bugs, restructure folders — full filesystem access.</p>
            </div>

            <div className="feat-card">
              <span className="feat-icon">📤</span>
              <h3>Export &amp; Download</h3>
              <p>Package any project into a ZIP file and download it instantly. Essays, CVs, proposals, and full websites — all exportable in one click.</p>
            </div>
          </div>
        </div>
      </section>

      {/* CAPABILITIES */}
      <section className="capabilities" id="capabilities">
        <div className="container">
          <div className="section-label">How Zeus Works</div>
          <h2 className="section-title">One chat.<br /><span className="gradient-text">Infinite possibilities.</span></h2>

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
                  <h4>Zeus plans and executes</h4>
                  <p>It builds the site, writes the copy, generates images, searches the web — whatever the task needs. You see a live progress summary.</p>
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

          <div className="pricing-grid">
            <div className="price-card">
              <div className="plan-name">Free</div>
              <div className="plan-price">£0<span>/mo</span></div>
              <p className="plan-desc">Try Zeus with no commitment. Perfect for exploring what's possible.</p>
              <ul className="plan-features">
                <li>✓ 20 messages per month</li>
                <li>✓ AI chat assistant</li>
                <li>✓ Content writing</li>
                <li>✓ Web research</li>
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
                <li>✓ Unlimited messages</li>
                <li>✓ 5 website builds/month</li>
                <li>✓ AI chat assistant</li>
                <li>✓ Deploy to Netlify</li>
                <li>✓ AI image generation</li>
                <li>✓ Email via Gmail</li>
                <li>✓ Client &amp; project CRM</li>
                <li>✓ Priority support</li>
              </ul>
              <Link to="/register" className="btn-plan-ghost">Start Pro</Link>
            </div>

            <div className="price-card">
              <div className="plan-name">Agency</div>
              <div className="plan-price">£79<span>/mo</span></div>
              <p className="plan-desc">For teams and agencies running multiple clients at scale.</p>
              <ul className="plan-features">
                <li>✓ Unlimited messages</li>
                <li>✓ 10 website builds/month</li>
                <li>✓ AI chat assistant</li>
                <li>✓ Everything in Pro</li>
                <li>✓ Team features</li>
                <li>✓ Priority support</li>
              </ul>
              <Link to="/register" className="btn-plan-ghost">Start Agency</Link>
            </div>

            <div className="price-card price-featured price-enterprise">
              <div className="plan-badge plan-badge--enterprise">Best Plan</div>
              <div className="plan-name">Enterprise</div>
              <div className="plan-price">£150<span>/mo</span></div>
              <p className="plan-desc">The full Zeus AI power stack. Autonomous agents build and deploy sites while you sleep.</p>
              <ul className="plan-features">
                <li>✓ Unlimited messages</li>
                <li>✓ 20 website builds/month</li>
                <li>✓ Multi-agent website builder</li>
                <li>✓ Background tasks</li>
                <li>✓ Scheduled tasks</li>
                <li>✓ Appointment booking</li>
                <li>✓ Priority support</li>
              </ul>
              <Link to="/register" className="btn-plan-primary">Start Enterprise</Link>
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
          <p className="footer-copy">© {new Date().getFullYear()} Zeus AI Design. Built with ⚡ by Zeus.</p>
          <div className="footer-links">
            <Link to="/login">Sign In</Link>
            <a href="#pricing">Pricing</a>
            <a href="#features">Features</a>
            <Link to="/terms">Terms</Link>
            <Link to="/privacy">Privacy Policy</Link>
          </div>
        </div>
      </footer>
    </div>
  );
}
