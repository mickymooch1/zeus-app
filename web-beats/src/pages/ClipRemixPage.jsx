import { useEffect, useState } from 'react';
import { useParams, useNavigate, Link } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import { BACKEND_URL } from '../brand';
import { clearRemixIntent, saveRemixIntent, saveSongRemixIntent } from '../utils/remixIntent';
import { toRemixSource } from '../utils/remixSource';
import { quickPickGenres, remixButtonLabel, remixGenreBody, selectionTag } from '../utils/remixGenre';
import GenrePickerSheet from '../components/GenrePickerSheet';
import { readUtmAttribution } from '../utils/utmAttribution';
import VerificationRequiredScreen from '../components/VerificationRequiredScreen';
import RemixButton from '../components/RemixButton';
import { ClipGenrePill, ZeusClipsWordmark } from '../components/ClipsBranding';
import { gLabel } from '../utils/genres';

// Zeus Beats' own electric-blue → purple pair (see RemixButton.jsx).
const CYAN = '#00f0ff';
const PURPLE = '#7c3aed';

/**
 * The remix confirm screen (build brief Phase 2). Reached either directly (clip
 * page → already logged in) or via SongsPage's remix-intent redirect (register/
 * login/email-verification hand-off — see utils/remixIntent.js).
 *
 * Also serves Discover's song Remix at /discover/:variantId/remix (2026-09-24):
 * same page, keyed by song — GET /api/discover/:id and POST /api/songs/:id/remix.
 *
 * Deliberately thin: POST /api/clips/:id/remix takes no body and does everything
 * server-side (style/theme prefill, lyrics, generation submission) — see
 * backend/main.py's remix_clip. This page's only job is showing what's about to
 * happen and confirming, then handing off to /songs, whose existing library/
 * polling view shows the result exactly like any other generation — a remixed
 * song is not a different kind of row.
 */
export default function ClipRemixPage() {
  const { clipId, variantId } = useParams();
  const isSong = variantId != null;
  const navigate = useNavigate();
  const { token, refreshUser } = useAuth();

  const [clip, setClip]         = useState(null);
  const [loading, setLoading]   = useState(true);
  const [notFound, setNotFound] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError]       = useState('');
  const [verifyBlock, setVerifyBlock] = useState(null);
  const [showDetails, setShowDetails] = useState(false);
  // Remix genre: null = the original's genre (the default); else { genre, genreB? }.
  const [genreSel, setGenreSel] = useState(null);
  const [pickerOpen, setPickerOpen] = useState(false);
  // Genres a remix can't use (no vocals) — the server's list, hidden in "More genres".
  const [nonVocal, setNonVocal] = useState(undefined);
  useEffect(() => {
    fetch(`${BACKEND_URL}/api/clips/config`)
      .then(r => (r.ok ? r.json() : null))
      .then(d => setNonVocal(d?.non_vocal_genres))
      .catch(() => {});
  }, []);

  // The URL itself is now the source of truth for which clip to remix — clear the
  // stored intent so it can't stick around and bounce a later, unrelated /songs
  // visit back here. Re-armed below if we hit the email-verification wall.
  useEffect(() => { clearRemixIntent(); }, []);

  useEffect(() => {
    setLoading(true);
    setNotFound(false);
    fetch(`${BACKEND_URL}${isSong ? `/api/discover/${variantId}` : `/api/clips/${clipId}`}`)
      .then(r => { if (!r.ok) throw new Error('not found'); return r.json(); })
      .then(d => setClip(toRemixSource(d, { isSong, backendUrl: BACKEND_URL })))
      .catch(() => setNotFound(true))
      .finally(() => setLoading(false));
  }, [clipId, variantId, isSong]);

  const handleConfirm = async () => {
    setError('');
    setSubmitting(true);
    try {
      const r = await fetch(`${BACKEND_URL}${isSong ? `/api/songs/${variantId}/remix` : `/api/clips/${clipId}/remix`}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
        body: JSON.stringify({ ...(readUtmAttribution() || {}), ...remixGenreBody(genreSel, clip?.genreTag) }),
      });
      const d = await r.json().catch(() => ({}));
      if (!r.ok) {
        const det = d.detail;
        if (r.status === 403 && det && typeof det === 'object' && det.code === 'email_unverified') {
          // Re-arm the intent — verification opens in a NEW tab, and this page
          // will have already cleared it on mount above.
          if (isSong) saveSongRemixIntent(variantId); else saveRemixIntent(clipId);
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
        <p style={{ color: '#555', fontSize: 16 }}>
          {isSong ? 'Song not found or no longer public.' : 'Clip not found, hidden, or removed.'}
        </p>
        <Link to={isSong ? '/discover' : '/clips'} style={{ color: CYAN, fontWeight: 600, textDecoration: 'none' }}>
          {isSong ? '← Back to Discover' : '← Browse clips'}
        </Link>
      </div>
    );
  }

  const { visualUrl } = clip;
  const quickPicks = quickPickGenres(clip.genreTag);
  // The chosen genre, or null when it's the original (re-picking the original = default).
  const chosenTag = selectionTag(genreSel) !== clip.genreTag ? selectionTag(genreSel) : null;

  return (
    <div style={{ background: '#000', minHeight: '100svh', color: '#fff', display: 'flex', flexDirection: 'column', alignItems: 'center', padding: '32px 20px 48px' }}>
      <div style={{ marginBottom: 28 }}>
        {/* A song remix comes from Discover, so it wears Discover's ZEUS BEATS mark. */}
        {isSong ? <ZeusClipsWordmark word="BEATS" to="/discover" /> : <ZeusClipsWordmark />}
      </div>

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
          Remix &ldquo;{clip.title || 'this sound'}&rdquo;
        </h1>
        <ClipGenrePill genre={clip.genreTag} style={{ margin: '4px 0 12px' }} />
        <p style={{ color: 'rgba(255,255,255,0.6)', fontSize: 14, margin: '0 0 16px' }}>
          {chosenTag
            ? <>We&apos;ll make it {gLabel(chosenTag)}, with brand-new lyrics on the same theme — never the original song&apos;s words.</>
            : <>We&apos;ll write brand-new lyrics in the same {clip.genreTag ? gLabel(clip.genreTag) : 'style'} — never the original song&apos;s words.</>}
        </p>

        {/* Remix in a different genre — the original is the default (no taps needed). */}
        <div style={{ textAlign: 'left', marginBottom: 16 }}>
          <p style={{ margin: '0 0 8px', fontSize: 12, fontWeight: 700, color: 'rgba(255,255,255,0.55)', letterSpacing: '0.04em', textTransform: 'uppercase' }}>
            Remix in a different genre
          </p>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 7 }}>
            <GenreChip selected={!chosenTag} onClick={() => setGenreSel(null)}>Original</GenreChip>
            {quickPicks.map(g => (
              <GenreChip key={g} selected={chosenTag === g} onClick={() => setGenreSel({ genre: g })}>{gLabel(g)}</GenreChip>
            ))}
            {chosenTag && !quickPicks.includes(chosenTag) && (
              <GenreChip selected onClick={() => setPickerOpen(true)}>{gLabel(chosenTag)}</GenreChip>
            )}
            <GenreChip onClick={() => setPickerOpen(true)}>More genres…</GenreChip>
          </div>
        </div>

        {/* The raw style prompt is generation plumbing, not something a
            non-technical user needs to read — collapsed by default. */}
        {(clip.style || clip.theme) && (
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

        {showDetails && (clip.style || clip.theme) && (
          <div style={{
            background: 'rgba(255,255,255,0.04)', border: '1px solid rgba(255,255,255,0.08)',
            borderRadius: 12, padding: '14px 16px', marginBottom: 20, textAlign: 'left',
          }}>
            {chosenTag ? (
              <p style={{ margin: '0 0 6px', fontSize: 12, color: 'rgba(255,255,255,0.5)' }}>
                <strong style={{ color: CYAN }}>Style:</strong> {gLabel(chosenTag)} (its own sound, not the original&apos;s)
              </p>
            ) : clip.style && (
              <p style={{ margin: '0 0 6px', fontSize: 12, color: 'rgba(255,255,255,0.5)' }}>
                <strong style={{ color: CYAN }}>Style:</strong> {clip.style}
              </p>
            )}
            {clip.theme && (
              <p style={{ margin: 0, fontSize: 12, color: 'rgba(255,255,255,0.5)' }}>
                <strong style={{ color: CYAN }}>Theme:</strong> {clip.theme}
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
          label={submitting ? 'Starting your remix…' : remixButtonLabel(genreSel)}
        />
        <p style={{ color: 'rgba(255,255,255,0.35)', fontSize: 11, marginTop: 12 }}>
          Uses 1 song credit. You&apos;ll find it in your songs once it&apos;s ready.
        </p>
      </div>

      {pickerOpen && (
        <GenrePickerSheet
          exclude={(clip.genreTag || '').split('__')}
          nonVocal={nonVocal}
          initial={genreSel}
          onClose={() => setPickerOpen(false)}
          onPick={(sel) => { setGenreSel(sel); setPickerOpen(false); }}
        />
      )}

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

/** One genre option on the remix confirm page. */
function GenreChip({ selected, onClick, children }) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-pressed={!!selected}
      style={{
        padding: '7px 13px', borderRadius: 999, fontSize: 13, fontWeight: selected ? 800 : 600, cursor: 'pointer',
        color: selected ? '#000' : 'rgba(255,255,255,0.8)',
        background: selected ? `linear-gradient(90deg, ${CYAN}, ${PURPLE})` : 'rgba(255,255,255,0.05)',
        border: selected ? '1px solid transparent' : '1px solid rgba(255,255,255,0.18)',
        boxShadow: selected ? `0 0 12px ${CYAN}55` : 'none',
      }}
    >
      {children}
    </button>
  );
}
