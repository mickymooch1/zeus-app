import { useEffect, useRef } from 'react';
import { Link } from 'react-router-dom';
import { Navbar } from '../components/Navbar';

const FEATURES = [
  {
    icon: '🌐',
    title: 'Website Builder',
    desc: 'Build complete, responsive websites from a single prompt. HTML, CSS, JS — clean, modern, production-ready.',
    large: true,
  },
  {
    icon: '🧠',
    title: 'Memory & Learning',
    desc: 'Zeus remembers your clients, projects, and preferences across every session.',
    large: false,
  },
  {
    icon: '👥',
    title: 'Client Profiles',
    desc: 'Track clients, deadlines, and project history automatically.',
    large: false,
  },
  {
    icon: '✉️',
    title: 'Email Drafting',
    desc: 'Proposals, follow-ups, cold outreach — professional emails in seconds.',
    large: false,
  },
  {
    icon: '✍️',
    title: 'Content & Copy',
    desc: 'SEO copy, about pages, taglines, and blog posts tailored to any industry.',
    large: false,
  },
  {
    icon: '⚙️',
    title: 'Business Ops',
    desc: 'Pricing advice, project scoping, contract templates, and growth strategy.',
    large: true,
  },
];

const STEPS = [
  { num: '01', title: 'Create your account', desc: 'Sign up free in 30 seconds. No credit card required to start.' },
  { num: '02', title: 'Tell Zeus what you need', desc: 'Describe your project, client, or task in plain English.' },
  { num: '03', title: 'Zeus gets to work', desc: 'Watch it write code, draft emails, and plan projects in real time.' },
  { num: '04', title: 'Ship faster', desc: 'Review, refine, and deploy. Zeus remembers everything for next time.' },
];

function useScrollReveal() {
  const ref = useRef(null);
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const observer = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting) {
          el.classList.add('revealed');
          observer.disconnect();
        }
      },
      { threshold: 0.15 }
    );
    observer.observe(el);
    return () => observer.disconnect();
  }, []);
  return ref;
}

function RevealSection({ className, children }) {
  const ref = useScrollReveal();
  return (
    <div ref={ref} className={`reveal-section ${className || ''}`}>
      {children}
    </div>
  );
}

export default function LandingPage() {
  return (
    <div className="landing">
      <Navbar />

      {/* Background orbs */}
      <div className="hero-orbs" aria-hidden>
        <div className="orb orb-1" />
        <div className="orb orb-2" />
        <div className="orb orb-3" />
      </div>

      {/* ── Hero ── */}
      <section className="hero" id="hero">
        <div className="hero-content">
          <div className="hero-badge">AI-Powered Web Design Assistant</div>
          <h1 className="hero-title">
            The AI that runs your<br />
            <span className="gradient-text">web design business</span>
          </h1>
          <p className="hero-sub">
            Zeus builds websites, writes copy, drafts client emails, tracks projects,
            and handles the ops — so you can focus on doing great work.
          </p>
          <div className="hero-ctas">
            <Link to="/register" className="btn btn-primary btn-lg">
              Start Free — No card needed
            </Link>
            <Link to="/pricing" className="btn btn-outline btn-lg">
              See Pricing
            </Link>
          </div>
        </div>

        {/* Animated chat mockup */}
        <div className="hero-mockup" aria-hidden>
          <div className="mockup-card">
            <div className="mockup-header">
              <span className="mockup-dot red" />
              <span className="mockup-dot yellow" />
              <span className="mockup-dot green" />
              <span className="mockup-title">Zeus — AI Assistant</span>
            </div>
            <div className="mockup-body">
              <div className="mockup-msg user">Build a portfolio site for my agency</div>
              <div className="mockup-msg zeus">
                <span className="mockup-zeus-label">⚡ Zeus</span>
                On it. Creating a modern, responsive portfolio with a hero section, work gallery, about page, and contact form. Using clean CSS Grid with dark-mode support…
                <div className="mockup-tools">
                  <span className="mockup-tool done">✓ create_file index.html</span>
                  <span className="mockup-tool done">✓ create_file style.css</span>
                  <span className="mockup-tool running">⋯ create_file portfolio.js</span>
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* ── Features ── */}
      <section className="section" id="features">
        <RevealSection>
          <div className="section-label">What Zeus can do</div>
          <h2 className="section-title">Everything your business needs</h2>
          <p className="section-sub">One AI. Every task in your web design workflow.</p>
        </RevealSection>

        <RevealSection className="bento-grid">
          {FEATURES.map((f) => (
            <div key={f.title} className={`bento-card${f.large ? ' bento-card--large' : ''}`}>
              <div className="bento-icon">{f.icon}</div>
              <h3 className="bento-title">{f.title}</h3>
              <p className="bento-desc">{f.desc}</p>
            </div>
          ))}
        </RevealSection>
      </section>

      {/* ── How it works ── */}
      <section className="section section--alt">
        <RevealSection>
          <div className="section-label">Process</div>
          <h2 className="section-title">How it works</h2>
        </RevealSection>
        <RevealSection className="steps-grid">
          {STEPS.map((s) => (
            <div key={s.num} className="step-card">
              <div className="step-num">{s.num}</div>
              <h3 className="step-title">{s.title}</h3>
              <p className="step-desc">{s.desc}</p>
            </div>
          ))}
        </RevealSection>
      </section>

      {/* ── Pricing preview ── */}
      <section className="section" id="pricing-preview">
        <RevealSection>
          <div className="section-label">Pricing</div>
          <h2 className="section-title">Simple, honest pricing</h2>
          <p className="section-sub">Start free. Upgrade when you're ready.</p>
        </RevealSection>
        <RevealSection className="pricing-preview-grid">
          <div className="pricing-preview-card">
            <div className="pp-plan">Free</div>
            <div className="pp-price">£0</div>
            <p className="pp-desc">20 messages to try Zeus for yourself</p>
            <Link to="/register" className="btn btn-outline">Get started</Link>
          </div>
          <div className="pricing-preview-card pricing-preview-card--popular">
            <div className="pp-badge">Most Popular</div>
            <div className="pp-plan">Professional</div>
            <div className="pp-price">£29<span>/mo</span></div>
            <p className="pp-desc">Unlimited messages, all features, Netlify deploy</p>
            <Link to="/pricing" className="btn btn-primary">View plan</Link>
          </div>
          <div className="pricing-preview-card">
            <div className="pp-plan">Agency</div>
            <div className="pp-price">£79<span>/mo</span></div>
            <p className="pp-desc">Everything in Pro + team features & priority support</p>
            <Link to="/pricing" className="btn btn-outline">View plan</Link>
          </div>
        </RevealSection>
      </section>

      {/* ── CTA ── */}
      <section className="section section--cta">
        <RevealSection className="cta-box">
          <h2 className="cta-title">Ready to put Zeus to work?</h2>
          <p className="cta-sub">Join hundreds of web designers saving hours every week.</p>
          <div className="cta-buttons">
            <Link to="/register" className="btn btn-primary btn-lg">Start Free Today</Link>
            <Link to="/pricing" className="btn btn-outline btn-lg">See all plans</Link>
          </div>
        </RevealSection>
      </section>

      {/* ── Footer ── */}
      <footer className="footer">
        <div className="footer-inner">
          <div className="footer-logo">
            <span>⚡</span> Zeus
          </div>
          <div className="footer-links">
            <Link to="/pricing">Pricing</Link>
            <Link to="/terms">Terms</Link>
            <Link to="/privacy">Privacy</Link>
            <Link to="/login">Login</Link>
          </div>
          <p className="footer-copy">© {new Date().getFullYear()} Zeus. All rights reserved.</p>
        </div>
      </footer>
    </div>
  );
}
