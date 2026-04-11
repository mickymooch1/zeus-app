import React from 'react';
import './AdPoster.css';

export default function AdPoster() {
  return (
    <div className="ad-wrapper">
      <div className="ad-card">
        {/* Background grid */}
        <div className="ad-grid" />

        {/* Glow blobs */}
        <div className="glow glow-1" />
        <div className="glow glow-2" />

        {/* Top badge */}
        <div className="ad-badge">
          <span className="badge-dot" />
          AI-POWERED WEB DESIGN
        </div>

        {/* Logo */}
        <div className="ad-logo">
          <span className="logo-bolt">&#9889;</span>
          <span className="logo-text">Zeus AI Design</span>
        </div>

        {/* Headline */}
        <h1 className="ad-headline">
          Your AI That
          <span className="ad-headline-green"> Builds Websites</span>
        </h1>

        {/* Subline */}
        <p className="ad-sub">
          Describe your business. Get a live website in minutes.
        </p>

        {/* Feature list */}
        <ul className="ad-features">
          <li><span className="check">&#10003;</span> Full websites built by AI — no code needed</li>
          <li><span className="check">&#10003;</span> Deployed live to the web instantly</li>
          <li><span className="check">&#10003;</span> Copy, branding &amp; design — all included</li>
          <li><span className="check">&#10003;</span> Free to try — no credit card required</li>
        </ul>

        {/* CTA */}
        <div className="ad-cta">
          <div className="cta-btn">Start Building Free &nbsp;&#8594;</div>
          <p className="cta-url">zeusaidesign.com</p>
        </div>

        {/* Bottom bar */}
        <div className="ad-bottom-bar">
          <span>&#9889; zeusaidesign.com</span>
          <span>Free &nbsp;|&nbsp; Pro &nbsp;|&nbsp; Enterprise</span>
        </div>
      </div>
    </div>
  );
}
