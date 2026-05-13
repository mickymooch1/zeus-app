import { Link } from 'react-router-dom';
import { Navbar } from '../components/Navbar';

const genres = [
  'Blues', 'Soul', 'R&B', 'Hip-Hop', 'Pop', 'Rock', 'EDM', 'House',
  'Jungle', 'D&B', 'Grime', 'UK Drill', 'UK Garage', 'Bassline House',
  'Lo-Fi', 'Acoustic', 'Country', 'Reggae', 'Lovers Rock', 'K-Pop',
  'Niche', 'Deep Soul Blues', 'Blues Soul', 'Irish Jig', 'Irish Folk',
];

const features = [
  {
    icon: '🎵',
    title: 'AI Lyrics',
    desc: 'Zeus writes professional lyrics from your brief, complete with verses, chorus, and bridge.',
  },
  {
    icon: '🎨',
    title: 'Cover Art',
    desc: 'Stunning AI-generated cover artwork unique to every song, styled to your genre.',
  },
  {
    icon: '🎬',
    title: 'Music Video',
    desc: 'Kling AI animates your cover art into a 5-second looping music video automatically.',
  },
  {
    icon: '📺',
    title: 'YouTube Upload',
    desc: 'One-click YouTube upload with auto-generated title, description, and tags.',
  },
  {
    icon: '⚡',
    title: 'Instant Results',
    desc: 'Songs generate in under 3 minutes. Multiple genres in parallel — get 7 takes at once.',
  },
  {
    icon: '🎤',
    title: 'Full Control',
    desc: 'Custom title, tempo, vocal style, explicit toggle, inspired-by artist lookup.',
  },
];

export default function LandingPage() {
  return (
    <div className="landing">
      <Navbar />

      {/* Hero Section */}
      <section className="hero">
        <div className="hero-orbs">
          <div className="orb orb-1" />
          <div className="orb orb-2" />
          <div className="orb orb-3" />
        </div>

        <div className="eyebrow-badge">♪ AI Music Studio</div>

        <h1>
          Create AI Music{' '}
          <span className="gradient-text">in Seconds</span>
        </h1>

        <p className="hero-sub">
          Describe your song idea. Zeus generates lyrics, picks the perfect style,
          creates cover art — and even animates it into a music video.
        </p>

        <div className="hero-cta">
          <Link to="/register" className="btn btn-primary btn-lg">
            Get Started Free
          </Link>
          <Link to="/pricing" className="btn btn-outline btn-lg">
            View Plans
          </Link>
        </div>
      </section>

      {/* Genre Showcase Section */}
      <section className="genre-showcase">
        <h2 className="section-title">25 Genres &amp; Styles</h2>
        <p className="section-sub">
          From Blues to K-Pop, Bassline to Irish Jig — every style covered.
        </p>
        <div className="genre-pills">
          {genres.map((genre) => (
            <span key={genre} className="genre-pill-static">
              {genre}
            </span>
          ))}
        </div>
      </section>

      {/* Features Section */}
      <section className="features-section" id="features">
        <h2 className="section-title">Everything You Need</h2>
        <p className="section-sub">
          Professional music production powered by AI — no studio required.
        </p>
        <div className="features-grid">
          {features.map((feat) => (
            <div key={feat.title} className="feat-card">
              <div className="feat-icon">{feat.icon}</div>
              <h3 className="feat-title">{feat.title}</h3>
              <p className="feat-desc">{feat.desc}</p>
            </div>
          ))}
        </div>
      </section>

      {/* Pricing Preview Section */}
      <section className="landing-pricing">
        <h2 className="section-title">Simple Music Pricing</h2>
        <p className="section-sub">Pay only for what you use. No hidden fees.</p>

        <div className="pricing-grid">
          {/* Starter */}
          <div className="pricing-card">
            <span className="badge-pro">Music Starter</span>
            <div className="pricing-name">Starter</div>
            <div className="pricing-price">£9<span>/mo</span></div>
            <ul className="pricing-features">
              <li><span className="plan-feature-check">✓</span> 15 AI songs/month</li>
              <li><span className="plan-feature-check">✓</span> Cover art included</li>
              <li><span className="plan-feature-check">✓</span> Animated music video</li>
              <li><span className="plan-feature-check">✓</span> YouTube upload</li>
              <li><span className="plan-feature-check">✓</span> Download &amp; share</li>
            </ul>
            <Link to="/register" className="btn btn-outline btn-full">Get Started</Link>
          </div>

          {/* Pro */}
          <div className="pricing-card pricing-card--featured">
            <span className="badge-pro">Music Pro</span>
            <div className="pricing-name">Pro</div>
            <div className="pricing-price">£19<span>/mo</span></div>
            <ul className="pricing-features">
              <li><span className="plan-feature-check">✓</span> 40 AI songs/month</li>
              <li><span className="plan-feature-check">✓</span> Cover art included</li>
              <li><span className="plan-feature-check">✓</span> Animated music video</li>
              <li><span className="plan-feature-check">✓</span> YouTube upload</li>
              <li><span className="plan-feature-check">✓</span> 3 avatar videos/month</li>
              <li><span className="plan-feature-check">✓</span> Download &amp; share</li>
            </ul>
            <Link to="/register" className="btn btn-primary btn-full">Get Started</Link>
          </div>

          {/* Agency */}
          <div className="pricing-card">
            <span className="badge-agency">Music Agency</span>
            <div className="pricing-name">Agency</div>
            <div className="pricing-price">£39<span>/mo</span></div>
            <ul className="pricing-features">
              <li><span className="plan-feature-check">✓</span> 80 AI songs/month</li>
              <li><span className="plan-feature-check">✓</span> Cover art included</li>
              <li><span className="plan-feature-check">✓</span> Animated music video</li>
              <li><span className="plan-feature-check">✓</span> YouTube upload</li>
              <li><span className="plan-feature-check">✓</span> 10 avatar videos/month</li>
              <li><span className="plan-feature-check">✓</span> Download &amp; share</li>
            </ul>
            <Link to="/register" className="btn btn-outline btn-full">Get Started</Link>
          </div>
        </div>

        <p style={{ textAlign: 'center', marginTop: 24 }}>
          <Link to="/pricing" className="auth-link">See full pricing →</Link>
        </p>
      </section>

      {/* Footer */}
      <footer className="footer">
        <p>© 2025 Zeus Beats. AI music creation platform.</p>
        <div className="footer-links">
          <Link to="/pricing" className="footer-link">Pricing</Link>
          <Link to="/login" className="footer-link">Login</Link>
          <Link to="/register" className="footer-link">Get Started</Link>
          <Link to="/terms" className="footer-link">Terms</Link>
          <Link to="/privacy" className="footer-link">Privacy</Link>
        </div>
      </footer>
    </div>
  );
}
