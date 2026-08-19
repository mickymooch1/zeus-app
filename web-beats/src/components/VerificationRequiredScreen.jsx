import { useState } from 'react';
import { BACKEND_URL } from '../brand';

const CYAN = '#00f0ff';
const PINK = '#f472b6';

/**
 * Hard block shown when /api/songs/generate rejects with code "email_unverified".
 *
 * Distinct from EmailVerificationBanner, which is the dismissible nudge for users
 * who are already able to generate. This one cannot be dismissed into a working
 * app — the only ways out are verifying, or backing out to look around.
 *
 * Two things carry the weight here, both learned the hard way:
 *   * The spam-folder line is the FIRST thing after the headline, not a footnote.
 *     Deliverability is the single biggest reason a gated user gets stuck, so the
 *     answer has to arrive before they start hunting.
 *   * Resend is always available. Without it, anyone who lost the mail is locked
 *     out permanently with no self-serve route back in.
 */
export default function VerificationRequiredScreen({ email, message, token, onClose, onVerified }) {
  const [resend, setResend] = useState('idle');   // idle | loading | sent | ratelimited | error
  const [checking, setChecking] = useState(false);
  const [checkMsg, setCheckMsg] = useState('');

  async function handleResend() {
    setResend('loading');
    try {
      const res = await fetch(`${BACKEND_URL}/api/auth/resend-verification`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
        body: JSON.stringify({ app: 'beats' }),
      });
      // The endpoint is limited to 3/minute; say so rather than showing a generic
      // failure, or people hammer the button believing it is broken.
      if (res.status === 429) setResend('ratelimited');
      else setResend(res.ok ? 'sent' : 'error');
    } catch {
      setResend('error');
    }
  }

  // Verification happens in another tab (or on a phone), so nothing tells this tab
  // about it. Re-fetch the user on demand instead of polling.
  async function handleCheck() {
    setChecking(true);
    setCheckMsg('');
    try {
      const fresh = await onVerified?.();
      if (fresh?.email_verified) return;          // parent unmounts this screen
      setCheckMsg('Not verified yet — open the link in the email first.');
    } finally {
      setChecking(false);
    }
  }

  // Layout mirrors OnboardingTour: the overlay scrolls, the card is centred with
  // auto margins (never align-items:center, which strands content above the
  // scroll origin), and the actions sit in a non-shrinking footer so they stay
  // reachable on a short viewport without scrolling.
  const overlay = {
    position: 'fixed', inset: 0, zIndex: 10000,
    background: 'rgba(0,0,0,0.9)',
    display: 'flex', alignItems: 'flex-start', justifyContent: 'center',
    overflowY: 'auto', WebkitOverflowScrolling: 'touch', overscrollBehavior: 'contain',
    maxHeight: '100dvh',
    padding: 'max(16px, env(safe-area-inset-top)) max(12px, env(safe-area-inset-right)) max(16px, env(safe-area-inset-bottom)) max(12px, env(safe-area-inset-left))',
    backdropFilter: 'blur(4px)',
  };
  const card = {
    background: 'linear-gradient(135deg, #0d0d1a 0%, #1a0a2e 100%)',
    border: `1px solid ${CYAN}44`, borderRadius: 20,
    padding: 'clamp(20px, 5vw, 32px) clamp(18px, 5vw, 28px)',
    maxWidth: 460, width: '100%',
    boxShadow: `0 0 60px ${CYAN}18, 0 24px 60px rgba(0,0,0,0.8)`,
    maxHeight: '100%', display: 'flex', flexDirection: 'column', minHeight: 0,
    margin: 'auto',
  };
  const body = { flex: '1 1 auto', minHeight: 0, overflowY: 'auto', WebkitOverflowScrolling: 'touch' };
  const footer = { flexShrink: 0, paddingTop: 14, marginTop: 4, borderTop: '1px solid rgba(255,255,255,0.07)' };

  return (
    <div style={overlay} data-testid="verification-required">
      <div style={card}>
        <div style={body}>
          <div style={{ fontSize: 44, textAlign: 'center', marginBottom: 12 }}>📧</div>
          <h2 style={{
            fontFamily: "'Orbitron', sans-serif", fontSize: 19, fontWeight: 800,
            color: '#fff', textAlign: 'center', marginBottom: 12, lineHeight: 1.3,
          }}>
            Verify your email to start creating
          </h2>

          <p style={{ color: 'rgba(255,255,255,0.6)', fontSize: 15, lineHeight: 1.65, textAlign: 'center', marginBottom: 16 }}>
            {message || 'Please verify your email address before creating songs.'}
            {email ? <><br /><strong style={{ color: '#fff' }}>{email}</strong></> : null}
          </p>

          {/* Deliberately loud and high up — this is the answer for most people. */}
          <div style={{
            background: 'rgba(251,191,36,0.10)', border: '1px solid rgba(251,191,36,0.45)',
            borderRadius: 12, padding: '14px 16px', marginBottom: 18,
          }}>
            <p style={{ margin: 0, color: '#fbbf24', fontWeight: 800, fontSize: 15, marginBottom: 6 }}>
              ⚠️ Check your spam or junk folder
            </p>
            <p style={{ margin: 0, color: 'rgba(255,255,255,0.72)', fontSize: 14, lineHeight: 1.55 }}>
              Verification emails very often land there. If you find it in spam, please
              mark it as “Not spam” so future emails reach your inbox.
            </p>
          </div>

          <p style={{ color: 'rgba(255,255,255,0.45)', fontSize: 13, lineHeight: 1.55, textAlign: 'center', marginBottom: 18 }}>
            Open the link in the email, then come back and tap “I’ve verified”.
          </p>
        </div>

        <div style={footer}>
          <button
            onClick={handleCheck}
            disabled={checking}
            style={{
              width: '100%', padding: '14px 0', borderRadius: 12,
              background: `linear-gradient(90deg, ${CYAN}, ${PINK})`,
              color: '#000', fontWeight: 800, fontSize: 15, border: 'none',
              cursor: checking ? 'default' : 'pointer', fontFamily: "'Orbitron', sans-serif",
              boxShadow: `0 0 24px ${CYAN}44`, opacity: checking ? 0.7 : 1, marginBottom: 10,
            }}
          >
            {checking ? 'Checking…' : "I’ve verified — continue"}
          </button>
          {checkMsg && (
            <p style={{ margin: '0 0 10px', textAlign: 'center', fontSize: 13, color: '#fbbf24' }}>{checkMsg}</p>
          )}

          <button
            onClick={handleResend}
            disabled={resend === 'loading' || resend === 'sent'}
            style={{
              width: '100%', padding: '12px 0', borderRadius: 12,
              background: 'transparent', border: `1px solid ${CYAN}55`,
              color: resend === 'sent' ? '#34d399' : CYAN,
              fontSize: 14, fontWeight: 600,
              cursor: resend === 'loading' || resend === 'sent' ? 'default' : 'pointer',
              marginBottom: 10,
            }}
          >
            {resend === 'loading' ? 'Sending…'
              : resend === 'sent' ? '✓ Sent — check your inbox and spam folder'
              : resend === 'ratelimited' ? 'Too many requests — wait a minute'
              : resend === 'error' ? "Couldn't send — tap to retry"
              : 'Resend verification email'}
          </button>

          <button
            onClick={onClose}
            style={{
              width: '100%', padding: '10px 0', borderRadius: 12,
              background: 'transparent', border: 'none',
              color: 'rgba(255,255,255,0.4)', fontSize: 13, cursor: 'pointer',
            }}
          >
            Back
          </button>
        </div>
      </div>
    </div>
  );
}
