import { useEffect, useState } from 'react';
import { useParams, useNavigate, Link } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import { BACKEND_URL } from '../brand';
import { clearRemixIntent, saveRemixIntent } from '../utils/remixIntent';
import { readUtmAttribution } from '../utils/utmAttribution';
import VerificationRequiredScreen from '../components/VerificationRequiredScreen';
import RemixButton from '../components/RemixButton';
import { ClipGenrePill } from '../components/ClipsBranding';
import { gLabel } from '../utils/genres';

// Zeus Beats' own electric-blue → purple pair (see RemixButton.jsx).
const CYAN = '#00f0ff';
const PURPLE = '#7c3aed';

/**
 * The remix confirm screen (build brief Phase 2). Reached either directly (clip
 * page → already logged in) or via SongsPage's remix-intent redirect (register/
 * login/email-verification hand-off — see utils/remixIntent.js).
 *
 * Deliberately thin: POST /api/clips/:id/remix takes no body and does everything
 * server-side (style/theme prefill, lyrics, generation submission) — see
 * backend/main.py's remix_clip. This page's only job is showing what's about to
 * happen and confirming, then handing off to /songs, whose existing library/
 * polling view shows the result exactly like any other generation — a remixed
 * song is not a different kind of row.
 */
export default function ClipRemixPage() {
  const { clipId } = useParams();
  const navigate = useNavigate();
  const { token, refreshUser } = useAuth();

  const [clip, setClip]         = useState(null);
  const [loading, setLoading]   = useState(true);
  const [notFound, setNotFound] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError]       = useState('');
  const [verifyBlock, setVerifyBlock] = useState(null);
  const [showDetails, setShowDetails] = useState(false);

  // The URL itself is now the source of truth for which clip to remix — clear the
  // stored intent so it can't stick around and bounce a later, unrelated /songs
  // visit back here. Re-armed below if we hit the email-verification wall.
  useEffect(() => { clearRemixIntent(); }, []);

  useEffect(() => {
    setLoading(true);
    setNotFound(false);
    fetch(`${BACKEND_URL}/api/clips/${clipId}`)
      .then(r => { if (!r.ok) throw new Error('not found'); return r.json(); })
      .then(setClip)
      .catch(() => setNotFound(true))
      .finally(() => setLoading(false));
  }, [clipId]);

  const handleConfirm = async () => {
    setError('');
    setSubmitting(true);
    try {
      const r = await fetch(`${BACKEND_URL}/api/clips/${clipId}/remix`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
        body: JSON.stringify(readUtmAttribution() || {}),
      });
      const d = await r.json().catch(() => ({}));
      if (!r.ok) {
        const det = d.detail;
        if (r.status === 403 && det && typeof det === 'object' && det.code === 'email_unverified') {
          // Re-arm the intent — verification opens in a NEW tab, and this page
          // will have already cleared it on mount above.
          saveRemixIntent(clipId);
          setVerifyBlock({ message: det.message, email: det.email, bounced: !!det.bounced, bounceOrigin: det.bounce_origin || null });
          return;
        }
        if (r.status === 402) { setError('Not enough song credits for a remix.'); return; }
        setError((typeof det === 'string' ? det : det?.message) || 'Could not start the remix — please try again.');
        return;
      }
      // remixStarted: SongsPage skips its first-visit welcome and shows a
      // "your remix is being made" notice instead (see arrivedViaRemix).
      navigate('/songs', { replace: true, state: { remixStarted: true } });
    } catch {
      setError('Network error — please try again.');
    } finally {
      setSubmitting(false);
    }
  };

  if (loading) {
    return (
      <div style={{ background: '#000', height: '100svh', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
        <div style={{ width: 36, height: 36, borderRadius: '50%', border: `3px solid ${CYAN}33`, borderTopColor: CYAN, animation: 'spin 0.8s linear infinite' }} />
        <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
      </div>
    );
  }

  if (notFound) {
    return (
      <div style={{ background: '#000', height: '100svh', color: '#fff', display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', gap: 20, padding: 24 }}>
        <p style={{ color: '#555', fontSize: 16 }}>Clip not found, hidden, or removed.</p>
        <Link to="/clips" style={{ color: CYAN, fontWeight: 600, textDecoration: 'none' }}>← Browse clips</Link>
      </div>
    );
  }

  const visualUrl = clip.media_type === 'cover' ? clip.song_cover_url : `${BACKEND_URL}${clip.media_url}`;

  return (
    <div style={{ background: '#000', minHeight: '100svh', color: '#fff', display: 'flex', flexDirection: 'column', alignItems: 'center', padding: '32px 20px 48px' }}>
      <Link to="/" style={{ color: CYAN, textDecoration: 'none', fontSize: 17, fontWeight: 800, marginBottom: 28, textShadow: `0 0 16px ${CYAN}88` }}>
        ⚡ Zeus Beats
      </Link>

      <div style={{
        width: '100%', maxWidth: 420, background: 'linear-gradient(135deg, #0d0d1a 0%, #1a0a2e 100%)',
        border: `1px solid ${CYAN}33`, borderRadius: 20, padding: '28px 24px', textAlign: 'center',
        boxShadow: `0 0 40px ${CYAN}18`,
      }}>
        {visualUrl && (
          <img
            src={visualUrl}
            alt=""
            style={{ width: 96, height: 96, borderRadius: 16, objectFit: 'cover', margin: '0 auto 16px', boxShadow: `0 0 24px ${CYAN}33` }}
          />
        )}

        <h1 style={{ fontFamily: 'Orbitron, sans-serif', fontSize: 20, fontWeight: 800, margin: '0 0 6px' }}>
          Remix &ldquo;{clip.song_title || 'this sound'}&rdquo;
        </h1>
        <ClipGenrePill genre={clip.genre_tag} style={{ margin: '4px 0 12px' }} />
        <p style={{ color: 'rgba(255,255,255,0.6)', fontSize: 14, margin: '0 0 16px' }}>
          We&apos;ll write brand-new lyrics in the same {clip.genre_tag ? gLabel(clip.genre_tag) : 'style'} — never the original song&apos;s words.
        </p>

        {/* The raw style prompt is generation plumbing, not something a
            non-technical user needs to read — collapsed by default. */}
        {(clip.remix_style_descriptors || clip.remix_theme) && (
          <button
            type="button"
            onClick={() => setShowDetails(v => !v)}
            aria-expanded={showDetails}
            style={{
              background: 'none', border: 'none', color: 'rgba(255,255,255,0.45)', fontSize: 12,
              cursor: 'pointer', padding: 4, marginBottom: showDetails ? 8 : 18,
            }}
          >
            {showDetails ? 'Hide style details ▴' : 'See style details ▾'}
          </button>
        )}

        {showDetails && (clip.remix_style_descriptors || clip.remix_theme) && (
          <div style={{
            background: 'rgba(255,255,255,0.04)', border: '1px solid rgba(255,255,255,0.08)',
            borderRadius: 12, padding: '14px 16px', marginBottom: 20, textAlign: 'left',
          }}>
            {clip.remix_style_descriptors && (
              <p style={{ margin: '0 0 6px', fontSize: 12, color: 'rgba(255,255,255,0.5)' }}>
                <strong style={{ color: CYAN }}>Style:</strong> {clip.remix_style_descriptors}
              </p>
            )}
            {clip.remix_theme && (
              <p style={{ margin: 0, fontSize: 12, color: 'rgba(255,255,255,0.5)' }}>
                <strong style={{ color: CYAN }}>Theme:</strong> {clip.remix_theme}
              </p>
            )}
          </div>
        )}

        {error && (
          <p style={{ color: '#f87171', fontSize: 13, marginBottom: 14 }}>{error}</p>
        )}

        <RemixButton
          onClick={handleConfirm}
          disabled={submitting}
          label={submitting ? 'Starting your remix…' : undefined}
        />
        <p style={{ color: 'rgba(255,255,255,0.35)', fontSize: 11, marginTop: 12 }}>
          Uses 1 song credit. You&apos;ll find it in your songs once it&apos;s ready.
        </p>
      </div>

      {verifyBlock && (
        <VerificationRequiredScreen
          email={verifyBlock.email}
          message={verifyBlock.message}
          bounced={verifyBlock.bounced}
          bounceOrigin={verifyBlock.bounceOrigin}
          remixSaved
          token={token}
          onClose={() => setVerifyBlock(null)}
          onVerified={async () => {
            const fresh = await refreshUser();
            if (fresh?.email_verified) setVerifyBlock(null);
            return fresh;
          }}
          onEmailChanged={() => {}}
        />
      )}
    </div>
  );
}
