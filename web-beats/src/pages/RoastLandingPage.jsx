import { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import { BRAND } from '../brand';
import { saveRoastDraft, clearRoastDraft } from '../utils/roastDraft';

const EXAMPLES = ["Dominic's Always Late", 'Lazy Husband', 'Terrible Driver'];

// Same four values/labels/emoji as SongsPage's roast vibe picker — kept in sync
// by hand since the two pickers live in unrelated component trees.
const VIBES = [
  ['gentle', '😄', 'Gentle Banter', 'Warm & affectionate'],
  ['roast', '🔥', 'Proper Roast', 'Cheeky, going for it'],
  ['birthday', '🎂', 'Birthday Piss-take', 'Happy birthday 😬'],
  ['staghen', '🍺', 'Stag / Hen Do', 'Raucous send-off'],
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
    <div className="auth-page roast-page">
      <div className="auth-card auth-card--wide">
        <div className="roast-header-row">
          <div className="auth-logo">
            <span className="auth-logo-icon">⚡</span>
            <span className="auth-logo-text">{BRAND.name}</span>
          </div>
          {user && (
            <div className="roast-account-chip">
              <span className="roast-account-name">{user.name?.trim() || user.email}</span>
              <button type="button" className="auth-link roast-logout-link" onClick={handleLogout}>
                Log out
              </button>
            </div>
          )}
        </div>

        <h1 className="auth-title roast-title">Roast your mate with AI</h1>
        <p className="auth-sub roast-sub">Tell us who, and what&apos;s fair game. Zeus writes the song.</p>

        <form className="auth-form" onSubmit={handleSubmit}>
          <div className="form-group">
            <label className="form-label" htmlFor="roast-landing-name">Their name</label>
            <input
              id="roast-landing-name"
              type="text"
              className="form-input roast-input"
              value={roastName}
              onChange={(e) => setRoastName(e.target.value)}
              placeholder="Dave, Uncle Terry, Big Mike..."
              maxLength={80}
            />
          </div>

          <div className="form-group">
            <label className="form-label" htmlFor="roast-landing-details">What do you want to roast them about?</label>
            <textarea
              id="roast-landing-details"
              className="form-input roast-input"
              value={roastDetails}
              onChange={(e) => setRoastDetails(e.target.value)}
              placeholder="Funny habits, legendary stories, what they're known for..."
              rows={3}
              maxLength={500}
              style={{ resize: 'vertical', fontFamily: 'inherit' }}
            />
          </div>

          <div className="form-group">
            <label className="form-label">Pick the vibe</label>
            <div className="roast-vibe-grid">
              {VIBES.map(([val, emoji, label, desc]) => (
                <button
                  key={val}
                  type="button"
                  className={`roast-vibe-btn${roastVibe === val ? ' roast-vibe-btn--selected' : ''}`}
                  onClick={() => setRoastVibe(val)}
                >
                  <span className="roast-vibe-emoji">{emoji}</span>
                  <span className="roast-vibe-name">{label}</span>
                  <span className="roast-vibe-desc">{desc}</span>
                </button>
              ))}
            </div>
          </div>

          <button type="submit" className="btn btn-primary btn-lg btn-full roast-cta" disabled={!canSubmit}>
            Start my roast song
          </button>
        </form>

        {!user && (
          <p className="roast-login-hint">
            Already have an account?{' '}
            <Link to="/login" className="auth-link" onClick={handleLoginClick}>Log in</Link>
          </p>
        )}

        <div className="roast-examples">
          <p className="roast-examples-label">Some roasts people have made</p>
          <div className="roast-examples-list">
            {EXAMPLES.map((title) => (
              <span key={title} className="roast-example-chip">{title}</span>
            ))}
          </div>
        </div>
      </div>

      <style>{`
        @import url('https://fonts.googleapis.com/css2?family=Rajdhani:wght@500;600&display=swap');

        .roast-page .roast-header-row {
          display: flex;
          align-items: center;
          justify-content: space-between;
          flex-wrap: wrap;
          gap: 8px 16px;
          margin-bottom: 24px;
        }
        .roast-page .roast-header-row .auth-logo {
          margin-bottom: 0;
        }
        .roast-page .roast-account-chip {
          display: flex;
          align-items: center;
          gap: 10px;
          min-width: 0;
        }
        .roast-page .roast-account-name {
          font-family: 'Rajdhani', sans-serif;
          font-size: 12px;
          color: var(--text-dim);
          overflow: hidden;
          text-overflow: ellipsis;
          white-space: nowrap;
          max-width: 160px;
        }
        .roast-page .roast-logout-link {
          font-family: 'Rajdhani', sans-serif;
          font-size: 12px;
          background: none;
          border: none;
          padding: 0;
          cursor: pointer;
          flex-shrink: 0;
        }
        .roast-page .roast-login-hint {
          font-family: 'Rajdhani', sans-serif;
          font-size: 13px;
          color: var(--text-dim);
          text-align: center;
          margin-top: 12px;
        }

        .roast-page .roast-title {
          font-family: 'Orbitron', sans-serif;
          color: #f87171;
          text-shadow: 0 0 24px rgba(248,113,113,0.35);
        }
        .roast-page .roast-sub,
        .roast-page .form-label,
        .roast-page .roast-input,
        .roast-page .roast-example-chip,
        .roast-page .roast-examples-label {
          font-family: 'Rajdhani', sans-serif;
        }
        .roast-page .roast-input {
          border-color: rgba(248,113,113,0.30);
          background: rgba(248,113,113,0.06);
        }
        .roast-page .roast-input:focus {
          border-color: rgba(248,113,113,0.65);
        }
        .roast-page .roast-cta {
          background: linear-gradient(135deg, #f87171 0%, #ef4444 100%);
        }
        .roast-page .roast-cta:hover {
          box-shadow: 0 0 20px rgba(248,113,113,0.6), 0 8px 24px rgba(248,113,113,0.3);
          filter: brightness(1.08);
        }
        .roast-page .roast-examples {
          margin-top: 24px;
          border-top: 1px solid rgba(248,113,113,0.15);
          padding-top: 18px;
        }
        .roast-page .roast-examples-label {
          font-size: 11px;
          font-weight: 600;
          letter-spacing: 0.6px;
          text-transform: uppercase;
          color: var(--text-dim);
          margin-bottom: 10px;
        }
        .roast-page .roast-examples-list {
          display: flex;
          flex-wrap: wrap;
          gap: 8px;
        }
        .roast-page .roast-example-chip {
          font-size: 13px;
          font-weight: 600;
          color: #f87171;
          background: rgba(248,113,113,0.08);
          border: 1px solid rgba(248,113,113,0.25);
          border-radius: 999px;
          padding: 6px 12px;
        }
        .roast-page .roast-vibe-grid {
          display: grid;
          grid-template-columns: repeat(2, 1fr);
          gap: 8px;
        }
        .roast-page .roast-vibe-btn {
          font-family: 'Rajdhani', sans-serif;
          display: flex;
          flex-direction: column;
          align-items: flex-start;
          gap: 2px;
          padding: 10px 12px;
          border-radius: 10px;
          cursor: pointer;
          transition: all 0.15s;
          text-align: left;
          border: 2px solid rgba(248,113,113,0.25);
          background: rgba(248,113,113,0.04);
        }
        .roast-page .roast-vibe-btn--selected {
          border-color: #f87171;
          background: rgba(248,113,113,0.15);
          box-shadow: 0 0 14px rgba(248,113,113,0.25);
        }
        .roast-page .roast-vibe-emoji {
          font-size: 18px;
          line-height: 1;
          margin-bottom: 2px;
        }
        .roast-page .roast-vibe-name {
          font-size: 12px;
          font-weight: 700;
          color: rgba(248,113,113,0.7);
        }
        .roast-page .roast-vibe-btn--selected .roast-vibe-name {
          color: #f87171;
        }
        .roast-page .roast-vibe-desc {
          font-size: 10px;
          color: rgba(248,113,113,0.5);
          line-height: 1.3;
        }
        @media (max-width: 420px) {
          .roast-page .roast-vibe-grid {
            grid-template-columns: 1fr;
          }
        }
      `}</style>
    </div>
  );
}
