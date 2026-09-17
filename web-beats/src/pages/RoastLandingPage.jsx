import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import { BRAND } from '../brand';
import { saveRoastDraft } from '../utils/roastDraft';

const EXAMPLES = ["Dominic's Always Late", 'Lazy Husband', 'Terrible Driver'];

export default function RoastLandingPage() {
  const { user } = useAuth();
  const navigate = useNavigate();
  const [roastName, setRoastName] = useState('');
  const [roastDetails, setRoastDetails] = useState('');

  const canSubmit = roastName.trim().length > 0;

  const handleSubmit = (e) => {
    e.preventDefault();
    if (!canSubmit) return;
    saveRoastDraft(roastName.trim(), roastDetails.trim());
    navigate(user ? '/songs' : '/register');
  };

  return (
    <div className="auth-page roast-page">
      <div className="auth-card auth-card--wide">
        <div className="auth-logo">
          <span className="auth-logo-icon">⚡</span>
          <span className="auth-logo-text">{BRAND.name}</span>
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

          <button type="submit" className="btn btn-primary btn-lg btn-full roast-cta" disabled={!canSubmit}>
            Start my roast song
          </button>
        </form>

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
      `}</style>
    </div>
  );
}
