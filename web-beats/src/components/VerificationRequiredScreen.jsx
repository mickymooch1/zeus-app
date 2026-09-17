import { useState } from 'react';
import { BACKEND_URL } from '../brand';

const CYAN = '#00f0ff';
const PINK = '#f472b6';
const RED = '#f87171';

/**
 * Hard block shown when /api/songs/generate (or /api/lyrics/workshop) rejects
 * with code "email_unverified".
 *
 * Distinct from EmailVerificationBanner, which is the dismissible nudge for users
 * who are already able to generate. This one cannot be dismissed into a working
 * app — the only ways out are verifying, or backing out to look around.
 *
 * Three things carry the weight here, all learned the hard way:
 *   * The spam-folder line is the FIRST thing after the headline, not a footnote.
 *     Deliverability is the single biggest reason a gated user gets stuck, so the
 *     answer has to arrive before they start hunting.
 *   * Resend is always available. Without it, anyone who lost the mail is locked
 *     out permanently with no self-serve route back in.
 *   * A bounced/suppressed address makes both of the above useless — Resend
 *     accepts and then silently drops mail to a suppressed address, so "check
 *     spam" and "resend" both look like they worked while doing nothing. When
 *     the backend reports that, this screen says so plainly and offers the one
 *     thing that can actually fix it: a different address.
 */
export default function VerificationRequiredScreen({
  email, message, token, bounced, bounceOrigin, onClose, onVerified, onEmailChanged,
}) {
  const [resend, setResend] = useState('idle');   // idle | loading | sent | ratelimited | error
  const [checking, setChecking] = useState(false);
  const [checkMsg, setCheckMsg] = useState('');

  // Read once at mount (matches how the rest of this app lazy-inits state from
  // props/location.state) — the component stays mounted for its whole overlay
  // lifetime, and every place bounce status can actually change afterward
  // (handleResend, handleChangeEmail) already updates these two directly.
  const [isBounced, setIsBounced] = useState(() => !!bounced);
  const [origin, setOrigin] = useState(() => bounceOrigin || null);

  const [newEmail, setNewEmail] = useState('');
  const [changeStatus, setChangeStatus] = useState('idle');   // idle | loading | error | sent | limit_reached
  const [changeError, setChangeError] = useState('');

  async function handleResend() {
    setResend('loading');
    try {
      const res = await fetch(`${BACKEND_URL}/api/auth/resend-verification`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
        body: JSON.stringify({ app: 'beats' }),
      });
      const data = await res.json().catch(() => ({}));
      // The endpoint checks Resend's suppression list before sending — a
      // bounced address comes back here instead of a false "sent".
      if (data?.bounced) {
        setIsBounced(true);
        setOrigin(data.bounce_origin || null);
        setResend('idle');
        return;
      }
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

  async function handleChangeEmail(e) {
    e.preventDefault();
    const trimmed = newEmail.trim();
    if (!trimmed) return;
    setChangeStatus('loading');
    setChangeError('');
    try {
      const res = await fetch(`${BACKEND_URL}/api/auth/change-email`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
        body: JSON.stringify({ new_email: trimmed, app: 'beats' }),
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) {
        // A lifetime-cap rejection is not retryable — submitting again just
        // 403s again, so it gets its own terminal state instead of sitting
        // under a form that looks like trying once more might work.
        if (data.detail && typeof data.detail === 'object' && data.detail.code === 'email_change_limit') {
          setChangeStatus('limit_reached');
          return;
        }
        setChangeStatus('error');
        setChangeError((typeof data.detail === 'string' ? data.detail : data.detail?.message) || 'Could not update your email.');
        return;
      }
      setChangeStatus('sent');
      setIsBounced(false);
      setOrigin(null);
      setResend('idle');
      setNewEmail('');
      onEmailChanged?.(trimmed);
    } catch {
      setChangeStatus('error');
      setChangeError('Network error — please try again.');
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
  const emailInput = {
    width: '100%', boxSizing: 'border-box', padding: '12px 14px', borderRadius: 10,
    border: `1px solid ${RED}55`, background: 'rgba(255,255,255,0.05)', color: '#fff',
    fontSize: 14, marginBottom: 8, outline: 'none',
  };

  return (
    <div style={overlay} data-testid="verification-required">
      <div style={card}>
        <div style={body}>
          <div style={{ fontSize: 44, textAlign: 'center', marginBottom: 12 }}>{isBounced ? '✉️‍🔥' : '📧'}</div>
          <h2 style={{
            fontFamily: "'Orbitron', sans-serif", fontSize: 19, fontWeight: 800,
            color: '#fff', textAlign: 'center', marginBottom: 12, lineHeight: 1.3,
          }}>
            {isBounced ? 'That email address rejected our message' : 'Verify your email to start creating'}
          </h2>

          <p style={{ color: 'rgba(255,255,255,0.6)', fontSize: 15, lineHeight: 1.65, textAlign: 'center', marginBottom: 16 }}>
            {message || 'Please verify your email address before creating songs.'}
            {email ? <><br /><strong style={{ color: '#fff' }}>{email}</strong></> : null}
          </p>

          {isBounced ? (
            <div style={{
              background: 'rgba(248,113,113,0.10)', border: `1px solid ${RED}70`,
              borderRadius: 12, padding: '14px 16px', marginBottom: 18,
            }}>
              <p style={{ margin: 0, color: RED, fontWeight: 800, fontSize: 15, marginBottom: 6 }}>
                ⛔ This address can&apos;t receive our mail
              </p>
              <p style={{ margin: 0, color: 'rgba(255,255,255,0.72)', fontSize: 14, lineHeight: 1.55 }}>
                {origin === 'complaint'
                  ? 'It was marked as spam, so we’re no longer able to send to it.'
                  : 'A previous message to this address bounced, so we’re no longer able to send to it.'}
                {' '}Resending won&apos;t help — enter a different address below and we&apos;ll send a fresh link there.
              </p>
            </div>
          ) : (
            // Deliberately loud and high up — this is the answer for most people.
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
          )}

          {!isBounced && (
            <p style={{ color: 'rgba(255,255,255,0.45)', fontSize: 13, lineHeight: 1.55, textAlign: 'center', marginBottom: 18 }}>
              Open the link in the email, then come back and tap “I’ve verified”.
            </p>
          )}

          {changeStatus === 'sent' && (
            <p style={{ margin: '0 0 16px', textAlign: 'center', fontSize: 13, color: '#34d399' }}>
              ✓ Verification link sent to your new address — check it (and spam) for the link.
            </p>
          )}
        </div>

        <div style={footer}>
          {!isBounced && (
            <>
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
            </>
          )}

          {isBounced && changeStatus === 'limit_reached' ? (
            // Terminal state, deliberately no input/button here — retrying
            // just 403s again. hello@zeusbeats.com, not the /contact form:
            // it's a real Google Workspace inbox (confirmed via MX lookup),
            // independent of anything in this app that could itself be broken.
            <div style={{
              background: 'rgba(248,113,113,0.08)', border: `1px solid ${RED}40`,
              borderRadius: 12, padding: '14px 16px', marginBottom: 10, textAlign: 'center',
            }}>
              <p style={{ margin: 0, color: 'rgba(255,255,255,0.75)', fontSize: 14, lineHeight: 1.55 }}>
                You&apos;ve changed your email address too many times on this account.
                {' '}Please email{' '}
                <a href="mailto:hello@zeusbeats.com" style={{ color: RED, fontWeight: 700 }}>
                  hello@zeusbeats.com
                </a>{' '}
                for help.
              </p>
            </div>
          ) : isBounced ? (
            <form onSubmit={handleChangeEmail} style={{ marginBottom: 10 }}>
              <input
                type="email"
                value={newEmail}
                onChange={(e) => setNewEmail(e.target.value)}
                placeholder="Enter a different email address"
                required
                style={emailInput}
              />
              {changeStatus === 'error' && (
                <p style={{ margin: '0 0 8px', fontSize: 13, color: RED }}>{changeError}</p>
              )}
              <button
                type="submit"
                disabled={changeStatus === 'loading' || !newEmail.trim()}
                style={{
                  width: '100%', padding: '14px 0', borderRadius: 12,
                  background: `linear-gradient(90deg, ${RED}, ${PINK})`,
                  color: '#000', fontWeight: 800, fontSize: 15, border: 'none',
                  cursor: changeStatus === 'loading' ? 'default' : 'pointer', fontFamily: "'Orbitron', sans-serif",
                  boxShadow: `0 0 24px ${RED}44`, opacity: changeStatus === 'loading' || !newEmail.trim() ? 0.7 : 1,
                }}
              >
                {changeStatus === 'loading' ? 'Updating…' : 'Update email & resend verification'}
              </button>
            </form>
          ) : (
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
          )}

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
