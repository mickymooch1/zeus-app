import { useEffect, useRef, useState } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { QRCodeCanvas } from 'qrcode.react';
import { BeatsNavbar } from '../components/BeatsNavbar';
import { useAuth } from '../contexts/AuthContext';
import { BACKEND_URL } from '../brand';
import { startGenerationPoll } from '../utils/generationPoller';

// Stripe's redirect to success_url frequently beats its own webhook delivery,
// so a customer who pays and moves quickly to the Song step can otherwise hit
// a 402 telling them to buy a package they just bought. When we land here via
// that redirect (?checkout=success), poll briefly for the credit to land
// before letting the Song step's button go live. A timeout here is NOT a
// failure — it just stops the confirming state and falls through to the
// normal flow, where the existing 402 handling covers a genuine no-credit case.
const CHECKOUT_POLL_INTERVAL_MS = 1500;
const CHECKOUT_POLL_MAX_ATTEMPTS = 8; // ~12s total

// The wizard's fixed genre. 'ambient' is a real key in backend/song_genres.py's
// GENRE_PRESETS ("ambient music, atmospheric soundscapes, ... no vocals,
// deep relaxing atmosphere") — chosen because a memorial tribute is read out
// over a calm instrumental bed rather than sung.
const MEMORIAL_GENRE = 'ambient';
const TRIBUTE_MAX = 1000;
const PHOTO_MAX = 10;

const STEPS = ['name', 'memories', 'song', 'photos', 'review', 'qr'];
const STEP_LABELS = {
  name: 'Name',
  memories: 'Memories',
  song: 'Song',
  photos: 'Photos',
  review: 'Review',
  qr: 'Share',
};

export default function MemorialWizardPage() {
  const navigate = useNavigate();
  const location = useLocation();
  const { token, refreshUser } = useAuth();

  const [confirmingPurchase, setConfirmingPurchase] = useState(false);

  const [stepIndex, setStepIndex] = useState(0);
  const [name, setName] = useState('');
  const [tribute, setTribute] = useState('');

  const [lyricId, setLyricId] = useState(null);
  const [variantId, setVariantId] = useState(null);
  const [shareToken, setShareToken] = useState(null);
  const [songStatus, setSongStatus] = useState('idle'); // idle | generating | complete | failed
  const [pollWarning, setPollWarning] = useState('');

  const [photos, setPhotos] = useState([]);
  const [photoUploading, setPhotoUploading] = useState(false);

  const [occasionFailed, setOccasionFailed] = useState(false);
  const [occasionSaving, setOccasionSaving] = useState(false);

  const [qrMarked, setQrMarked] = useState(false);

  const [error, setError] = useState('');

  const pollRef = useRef(null);
  const latestVariantRef = useRef(null);
  const qrWrapRef = useRef(null);
  const fileInputRef = useRef(null);

  // Stop any in-flight poll on unmount so it can't keep firing after the
  // wizard has been navigated away from.
  useEffect(() => () => pollRef.current?.stop(), []);

  // Only true right after Stripe's redirect (?checkout=success) — visiting
  // /memorials/create directly (e.g. an existing credit already on the
  // account) never sets this, so there's no polling delay in that case.
  useEffect(() => {
    if (new URLSearchParams(location.search).get('checkout') !== 'success') return;
    let cancelled = false;
    let timeoutId;
    let attempts = 0;
    setConfirmingPurchase(true);
    const poll = async () => {
      attempts += 1;
      const fresh = await refreshUser();
      if (cancelled) return;
      if ((fresh?.memorial_credits_available || 0) >= 1) {
        setConfirmingPurchase(false);
        return;
      }
      if (attempts >= CHECKOUT_POLL_MAX_ATTEMPTS) {
        setConfirmingPurchase(false);
        return;
      }
      timeoutId = setTimeout(poll, CHECKOUT_POLL_INTERVAL_MS);
    };
    poll();
    return () => {
      cancelled = true;
      clearTimeout(timeoutId);
    };
    // Runs once on mount only — re-reading location.search on every render
    // would restart the poll whenever stepIndex changes and re-renders this.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const step = STEPS[stepIndex];
  const next = () => setStepIndex((i) => Math.min(i + 1, STEPS.length - 1));
  const back = () => setStepIndex((i) => Math.max(i - 1, 0));

  // Sets the public-page occasion + tribute text on the variant. This is what
  // flips the server-side photo cap from 5 to 10 (backend/main.py gates it on
  // variant.occasion === 'memorial'), so a failure here is not cosmetic — it
  // silently halves the photo cap. Exposed as a standalone function so both
  // the post-generation call and the Review step's retry button can use it.
  async function postOccasion(vId) {
    setOccasionSaving(true);
    try {
      const resp = await fetch(`${BACKEND_URL}/api/songs/variants/${vId}/occasion`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
        body: JSON.stringify({
          occasion: 'memorial',
          occasion_name: name.trim() || null,
          tribute_message: tribute.trim() || null,
        }),
      });
      if (!resp.ok) throw new Error('occasion save failed');
      setOccasionFailed(false);
      return true;
    } catch (_) {
      setOccasionFailed(true);
      return false;
    } finally {
      setOccasionSaving(false);
    }
  }

  async function generateSong() {
    setSongStatus('generating');
    setError('');
    latestVariantRef.current = null;
    try {
      const resp = await fetch(`${BACKEND_URL}/api/songs/generate`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
        body: JSON.stringify({
          genres: [MEMORIAL_GENRE],
          brief: tribute.trim() || `A gentle memorial tribute song for ${name.trim()}`,
          song_title: name.trim() || undefined,
          is_memorial: true,
        }),
      });
      const data = await resp.json().catch(() => ({}));
      if (resp.status === 402) {
        setSongStatus('failed');
        setError(
          (typeof data.detail === 'string' && data.detail) ||
            'No memorial credits available — please purchase a Memorial Package.'
        );
        return;
      }
      if (!resp.ok) {
        throw new Error((typeof data.detail === 'string' && data.detail) || 'Generation failed to start');
      }

      const firstVariant = data.variants[0];
      setLyricId(data.lyric_id);
      setVariantId(firstVariant.variant_id);

      pollRef.current = startGenerationPoll({
        trackedIds: [firstVariant.variant_id],
        fetchVariants: async () => {
          const r = await fetch(`${BACKEND_URL}/api/lyrics/${data.lyric_id}/variants`, {
            headers: { Authorization: `Bearer ${token}` },
          });
          if (!r.ok) throw new Error(`variants → ${r.status}`);
          return (await r.json()).variants;
        },
        onUpdate: (mine) => {
          const mineForThis = mine.find((v) => v.variant_id === firstVariant.variant_id);
          if (mineForThis) latestVariantRef.current = mineForThis;
        },
        onSettled: async ({ anyComplete }) => {
          setPollWarning('');
          if (anyComplete && latestVariantRef.current?.status === 'complete') {
            await postOccasion(firstVariant.variant_id);
            setSongStatus('complete');
            next();
          } else {
            setSongStatus('failed');
            setError('Song generation failed — please try again.');
          }
        },
        onTrouble: (failures) => {
          setPollWarning(
            failures ? "Still working — we're having trouble checking progress, but your song is being made." : ''
          );
        },
      });
    } catch (err) {
      setSongStatus('failed');
      setError(err.message || 'Something went wrong starting generation.');
    }
  }

  async function uploadPhoto(file) {
    if (!variantId || photos.length >= PHOTO_MAX) return;
    setPhotoUploading(true);
    setError('');
    try {
      const form = new FormData();
      form.append('file', file);
      const resp = await fetch(`${BACKEND_URL}/api/songs/variants/${variantId}/photos`, {
        method: 'POST',
        headers: { Authorization: `Bearer ${token}` },
        body: form,
      });
      const data = await resp.json().catch(() => ({}));
      if (!resp.ok) {
        throw new Error((typeof data.detail === 'string' && data.detail) || 'Photo upload failed');
      }
      setPhotos((p) => [...p, { photo_id: data.photo_id, url: data.url }]);
      if (data.share_token) setShareToken(data.share_token);
    } catch (err) {
      setError(err.message || 'Photo upload failed');
    } finally {
      setPhotoUploading(false);
      if (fileInputRef.current) fileInputRef.current.value = '';
    }
  }

  async function markQrGenerated() {
    if (qrMarked || !variantId) return;
    setQrMarked(true);
    try {
      await fetch(`${BACKEND_URL}/api/songs/variants/${variantId}/mark-qr-generated`, {
        method: 'POST',
        headers: { Authorization: `Bearer ${token}` },
      });
    } catch (_) {
      // fire-and-forget, same as the library page's QR download handler
    }
  }

  function handleQrDownload() {
    const canvas = qrWrapRef.current?.querySelector('canvas');
    if (!canvas) return;
    const url = canvas.toDataURL('image/png');
    const a = document.createElement('a');
    a.href = url;
    a.download = `${(name.trim() || 'memorial').replace(/[^a-z0-9]/gi, '-').toLowerCase()}-qr.png`;
    document.body.appendChild(a);
    a.click();
    a.remove();
    markQrGenerated();
  }

  // /memorial/:token resolves tokens only — never the plain numeric variant
  // id (unlike the library's /songs/share/:id_or_token, which intentionally
  // supports both as a legacy pre-photos link). share_token is minted only
  // by the photo-upload endpoint, so the Photos step requires at least one
  // photo before Next is enabled, guaranteeing this is set by the QR step.
  const shareUrl = shareToken ? `${window.location.origin}/memorial/${shareToken}` : '';

  return (
    <div className="memorial-wizard-page">
      <BeatsNavbar />
      <div className="page" style={{ maxWidth: 560, margin: '0 auto', padding: '48px 24px 96px' }}>
        <div style={{ display: 'flex', gap: 8, justifyContent: 'center', marginBottom: 32, flexWrap: 'wrap' }}>
          {STEPS.map((s, i) => (
            <div
              key={s}
              style={{
                fontSize: 12,
                padding: '4px 10px',
                borderRadius: 999,
                opacity: i === stepIndex ? 1 : 0.45,
                fontWeight: i === stepIndex ? 700 : 400,
                border: '1px solid rgba(255,255,255,0.2)',
              }}
            >
              {i + 1}. {STEP_LABELS[s]}
            </div>
          ))}
        </div>

        {step === 'name' && (
          <div>
            <h2>Whose memorial is this for?</h2>
            <p style={{ opacity: 0.75 }}>We'll use their name on the song and the memorial page.</p>
            <input
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="Name"
              maxLength={120}
              style={{ width: '100%', padding: 12, fontSize: 16, marginTop: 12 }}
              autoFocus
            />
            <div style={{ marginTop: 24, display: 'flex', justifyContent: 'flex-end' }}>
              <button type="button" className="btn btn-primary" onClick={next} disabled={!name.trim()}>
                Next
              </button>
            </div>
          </div>
        )}

        {step === 'memories' && (
          <div>
            <h2>Share a memory or tribute</h2>
            <p style={{ opacity: 0.75 }}>
              This becomes part of the song's story, and can also be shown on the memorial page.
            </p>
            <textarea
              value={tribute}
              onChange={(e) => setTribute(e.target.value.slice(0, TRIBUTE_MAX))}
              placeholder={`In loving memory of ${name.trim() || '...'}, who...`}
              rows={6}
              style={{ width: '100%', padding: 12, fontSize: 16, marginTop: 12 }}
            />
            <div style={{ textAlign: 'right', fontSize: 12, opacity: 0.6 }}>
              {tribute.length}/{TRIBUTE_MAX}
            </div>
            <div style={{ marginTop: 12, display: 'flex', justifyContent: 'space-between' }}>
              <button type="button" className="btn btn-ghost" onClick={back}>
                Back
              </button>
              <button type="button" className="btn btn-primary" onClick={next}>
                Next
              </button>
            </div>
          </div>
        )}

        {step === 'song' && (
          <div>
            <h2>Create the song</h2>
            {songStatus === 'idle' && (
              <>
                <p style={{ opacity: 0.75 }}>
                  We'll create a gentle instrumental tribute song for {name.trim() || 'your loved one'}. This uses
                  one of your Memorial Package credits.
                </p>
                {confirmingPurchase && (
                  <p style={{ opacity: 0.7, fontSize: 14 }}>Confirming your purchase…</p>
                )}
                <div style={{ marginTop: 24, display: 'flex', justifyContent: 'space-between' }}>
                  <button type="button" className="btn btn-ghost" onClick={back}>
                    Back
                  </button>
                  <button
                    type="button"
                    className="btn btn-primary"
                    onClick={generateSong}
                    disabled={confirmingPurchase}
                  >
                    {confirmingPurchase ? 'Confirming purchase…' : 'Create Song'}
                  </button>
                </div>
              </>
            )}
            {songStatus === 'generating' && (
              <div style={{ marginTop: 24 }}>
                <div className="spinner" />
                <p>Creating your song… this usually takes a few minutes.</p>
                {pollWarning && <p style={{ opacity: 0.7, fontSize: 14 }}>{pollWarning}</p>}
              </div>
            )}
            {songStatus === 'complete' && (
              <div style={{ marginTop: 24 }}>
                <p>Your song is ready.</p>
                <div style={{ display: 'flex', justifyContent: 'flex-end' }}>
                  <button type="button" className="btn btn-primary" onClick={next}>
                    Next
                  </button>
                </div>
              </div>
            )}
            {songStatus === 'failed' && (
              <div style={{ marginTop: 24 }}>
                <p style={{ color: '#ef4444' }}>{error}</p>
                <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                  <button type="button" className="btn btn-ghost" onClick={back}>
                    Back
                  </button>
                  <button type="button" className="btn btn-primary" onClick={generateSong}>
                    Try again
                  </button>
                </div>
              </div>
            )}
          </div>
        )}

        {step === 'photos' && (
          <div>
            <h2>Add photos (up to {PHOTO_MAX})</h2>
            <p style={{ opacity: 0.75 }}>
              These appear in the memorial page's photo slideshow. Add at least one photo to
              generate the memorial's shareable link and QR code.
            </p>
            <input
              ref={fileInputRef}
              type="file"
              accept="image/*,.heic,.heif"
              disabled={photos.length >= PHOTO_MAX || photoUploading}
              onChange={(e) => e.target.files[0] && uploadPhoto(e.target.files[0])}
              style={{ marginTop: 12 }}
            />
            {photoUploading && <p style={{ fontSize: 14, opacity: 0.7 }}>Uploading…</p>}
            {error && <p style={{ color: '#ef4444', fontSize: 14 }}>{error}</p>}
            <p style={{ fontSize: 14, opacity: 0.75 }}>
              {photos.length}/{PHOTO_MAX} photos
            </p>
            {photos.length > 0 && (
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8, marginTop: 8 }}>
                {photos.map((p) => (
                  <img
                    key={p.photo_id}
                    src={p.url}
                    alt=""
                    style={{ width: 64, height: 64, objectFit: 'cover', borderRadius: 8 }}
                  />
                ))}
              </div>
            )}
            <div style={{ marginTop: 24, display: 'flex', justifyContent: 'space-between' }}>
              <button type="button" className="btn btn-ghost" onClick={back}>
                Back
              </button>
              <button type="button" className="btn btn-primary" onClick={next} disabled={photos.length === 0}>
                Next
              </button>
            </div>
          </div>
        )}

        {step === 'review' && (
          <div>
            <h2>Review</h2>
            <p style={{ fontWeight: 700 }}>{name}</p>
            {tribute && <p style={{ opacity: 0.85, whiteSpace: 'pre-wrap' }}>{tribute}</p>}
            <p style={{ fontSize: 14, opacity: 0.75 }}>{photos.length} photo(s) added</p>
            {occasionFailed && (
              <div style={{ marginTop: 12, padding: 12, border: '1px solid #ef4444', borderRadius: 8 }}>
                <p style={{ color: '#ef4444', fontSize: 14, margin: 0 }}>
                  We couldn't save the memorial details (name/tribute) to the song — your photo limit may
                  still be capped at 5 instead of 10 until this succeeds.
                </p>
                <button
                  type="button"
                  className="btn btn-outline"
                  style={{ marginTop: 8 }}
                  disabled={occasionSaving || !variantId}
                  onClick={() => postOccasion(variantId)}
                >
                  {occasionSaving ? 'Retrying…' : 'Retry'}
                </button>
              </div>
            )}
            <button type="button" className="btn btn-outline" disabled title="Coming soon" style={{ marginTop: 12 }}>
              Download plaque artwork — coming soon
            </button>
            <div style={{ marginTop: 24, display: 'flex', justifyContent: 'space-between' }}>
              <button type="button" className="btn btn-ghost" onClick={back}>
                Back
              </button>
              <button type="button" className="btn btn-primary" onClick={next}>
                Next
              </button>
            </div>
          </div>
        )}

        {step === 'qr' && (
          <div style={{ textAlign: 'center' }}>
            <h2>Your memorial page is ready</h2>
            {shareToken && shareUrl ? (
              <>
                <p style={{ wordBreak: 'break-all', opacity: 0.85 }}>{shareUrl}</p>
                <div
                  ref={qrWrapRef}
                  style={{ display: 'inline-block', padding: 16, background: '#fff', borderRadius: 12, marginTop: 12 }}
                >
                  <QRCodeCanvas value={shareUrl} size={200} bgColor="#ffffff" fgColor="#0b0b14" level="H" />
                </div>
                <div style={{ marginTop: 20, display: 'flex', gap: 12, justifyContent: 'center', flexWrap: 'wrap' }}>
                  <button type="button" className="btn btn-primary" onClick={handleQrDownload}>
                    Download QR code
                  </button>
                  <button type="button" className="btn btn-outline" onClick={() => navigate(`/memorial/${shareToken}`)}>
                    View memorial page
                  </button>
                </div>
              </>
            ) : (
              <div>
                <p style={{ opacity: 0.85 }}>
                  We don't have a shareable link yet — this memorial needs at least one photo before a
                  QR code and page link can be generated.
                </p>
                <button
                  type="button"
                  className="btn btn-primary"
                  style={{ marginTop: 12 }}
                  onClick={() => setStepIndex(STEPS.indexOf('photos'))}
                >
                  Back to Photos
                </button>
              </div>
            )}
            <div style={{ marginTop: 32 }}>
              <button type="button" className="btn btn-ghost" onClick={() => navigate('/songs')}>
                Done
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
