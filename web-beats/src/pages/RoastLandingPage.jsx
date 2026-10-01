import { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import { saveRoastDraft, clearRoastDraft } from '../utils/roastDraft';
import './roastNeon.css';

// Neon restyle (2026-10-01) — layout and styling from design-ref/DESIGN.md and
// the approved roast mockups. Behaviour is unchanged: the same draft hand-off
// to /songs (signed in) or /register, the same "Log in" draft save, the same
// draft clearing on log out, the same four vibes.

const EXAMPLES = ["Dominic's Always Late", 'Lazy Husband', 'Terrible Driver'];

// Same four values/labels/emoji as SongsPage's roast vibe picker — kept in sync
// by hand since the two pickers live in unrelated component trees.
const VIBES = [
  ['gentle', '😄', 'Gentle Banter', 'Warm & affectionate'],
  ['roast', '🔥', 'Proper Roast', 'Cheeky, going for it'],
  ['birthday', '🎂', 'Birthday Piss-take', 'Happy birthday 😬'],
  ['staghen', '🍺', 'Stag / Hen Do', 'Raucous send-off'],
];

const FEATURES = [
  ['Roast friends', 'M12 3c1 3 4 4 4 8a4 4 0 0 1-8 0c0-2 1-3 2-4 0 2 1 3 2 3 0-3-1-5 0-7zM6 14a6 6 0 0 0 12 0'],
  ['Make it a song', 'M9 18V5l11-2v13M6 18a3 3 0 1 0 0 .01M17 16a3 3 0 1 0 0 .01'],
  ['Share the laughs', 'M18 8a3 3 0 1 0 0-.01M6 15a3 3 0 1 0 0-.01M18 22a3 3 0 1 0 0-.01M8.6 13.5l6.8 4M15.4 6.5l-6.8 4'],
  ['Go viral', 'M3 3v18h18M7 15l4-4 3 3 6-6'],
];

export default function RoastLandingPage() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const [roastName, setRoastName] = useState('');
  const [roastDetails, setRoastDetails] = useState('');
  // Defaults to 'roast' here (not 'gentle', SongsPage's default) — this page's
  // traffic comes from roast Shorts, so Proper Roast matches what they clicked
  // through for. SongsPage's own default is unrelated and stays as-is.
  const [roastVibe, setRoastVibe] = useState('roast');

  const canSubmit = roastName.trim().length > 0;

  const handleSubmit = (e) => {
    e.preventDefault();
    if (!canSubmit) return;
    saveRoastDraft(roastName.trim(), roastDetails.trim(), roastVibe);
    navigate(user ? '/songs' : '/register');
  };

  // "Log in" is always clickable (unlike the disabled submit button), but only
  // worth saving a draft for if there's actually something typed — otherwise
  // a stranger who clicks straight through would land on /songs with Roast
  // Mode switched on over nothing.
  const handleLoginClick = () => {
    if (canSubmit) saveRoastDraft(roastName.trim(), roastDetails.trim(), roastVibe);
  };

  // Logging out must not hand the roast draft to whoever uses this browser next.
  const handleLogout = () => {
    clearRoastDraft();
    logout();
  };

  return (
    <div className="zb-roast">
      <div className="zb-roast-glow" aria-hidden="true" />
      <div className="zb-roast-hero-img" aria-hidden="true"><img src="/images/zeus-hero.jpg" alt="" /></div>
      <div className="zb-roast-corner zb-marker" aria-hidden="true">Good roasts,<br />better beats</div>

      <div className="zb-roast-inner">
        <header className="zb-roast-top">
          <Link to="/" className="zb-roast-logo">
            <svg width="26" height="30" viewBox="0 0 22 26" fill="#16c8ff" aria-hidden="true"><path d="M13 0 2 15h7l-2 11L20 9h-7l2-9z" /></svg>
            <span>ZEUS <b>BEATS</b></span>
          </Link>
          {user ? (
            <div className="zb-roast-account">
              <span className="zb-roast-account-name">{user.name?.trim() || user.email}</span>
              <button type="button" className="zb-roast-textbtn" onClick={handleLogout}>Log out</button>
            </div>
          ) : (
            <Link to="/login" className="zb-roast-textbtn" onClick={handleLoginClick}>Log in</Link>
          )}
        </header>

        <div className="zb-roast-head">
          <div className="zb-roast-title zb-marker">Roast Mode</div>
          <svg className="zb-roast-swoosh" viewBox="0 0 360 22" aria-hidden="true">
            <path d="M4 16 C 110 4, 240 2, 354 8" stroke="#16c8ff" strokeWidth="7" fill="none" strokeLinecap="round" />
          </svg>
          <h1 className="zb-roast-h1">Roast your <span>mates</span></h1>
          <p className="zb-roast-lede">
            Savage songs. Funny bars. Instant laughs. Tell Zeus who&apos;s getting it and he&apos;ll turn it into a track.
          </p>
        </div>

        <form className="zb-roast-card" onSubmit={handleSubmit}>
          <div className="zb-roast-cardtag zb-marker" aria-hidden="true">Bars, not basic</div>

          <div className="zb-roast-field">
            <label htmlFor="roast-landing-name">Who are we roasting?</label>
            <input
              id="roast-landing-name"
              type="text"
              className="zb-roast-input"
              value={roastName}
              onChange={(e) => setRoastName(e.target.value)}
              placeholder="Dave, Uncle Terry, Big Mike…"
              maxLength={80}
            />
          </div>

          <div className="zb-roast-field">
            <label htmlFor="roast-landing-details">Give Zeus some ammo</label>
            <textarea
              id="roast-landing-details"
              className="zb-roast-input"
              value={roastDetails}
              onChange={(e) => setRoastDetails(e.target.value)}
              placeholder="Never buys a round, always late, thinks he's a gym legend…"
              rows={3}
              maxLength={500}
            />
          </div>

          <div className="zb-roast-field">
            <span id="roast-vibe-label">How hard?</span>
            <div className="zb-roast-vibes" role="group" aria-labelledby="roast-vibe-label">
              {VIBES.map(([val, emoji, label, desc]) => (
                <button
                  key={val}
                  type="button"
                  className="zb-roast-vibe"
                  aria-pressed={roastVibe === val}
                  title={desc}
                  onClick={() => setRoastVibe(val)}
                >
                  <span aria-hidden="true">{emoji}</span> {label}
                </button>
              ))}
            </div>
          </div>

          <div className="zb-roast-submit">
            <button type="submit" className="zb-roast-cta" disabled={!canSubmit}>
              <svg width="20" height="22" viewBox="0 0 20 22" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                <path d="M7 17V3l11-2v14" /><circle cx="4.5" cy="17" r="2.8" /><circle cx="15.5" cy="15" r="2.8" />
              </svg>
              Start my roast song
            </button>
            {!user && <span className="zb-roast-note">Your first 3 songs are free.</span>}
          </div>
        </form>

        <section className="zb-roast-examples" aria-label="Example roasts">
          <span className="zb-roast-examples-label">Roasts people have made</span>
          <div className="zb-roast-examples-list">
            {EXAMPLES.map((title) => <span key={title} className="zb-roast-example">{title}</span>)}
          </div>
        </section>

        <ul className="zb-roast-feats">
          {FEATURES.map(([label, d]) => (
            <li key={label}>
              <span className="zb-roast-feat-ring" aria-hidden="true">
                <svg width="38" height="38" viewBox="0 0 24 24" fill="none" stroke="#16c8ff" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d={d} /></svg>
              </span>
              <span className="zb-roast-feat-label">{label}</span>
            </li>
          ))}
        </ul>

        <footer className="zb-roast-foot">Create today. Roast tonight.</footer>
      </div>
    </div>
  );
}
