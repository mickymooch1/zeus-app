import { useEffect, useRef, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { QRCodeCanvas } from 'qrcode.react';
import WaveSurfer from 'wavesurfer.js';
import PhotoCarousel from '../components/PhotoCarousel';
import SongCard from '../components/SongCard';
import CollapsibleSection from '../components/CollapsibleSection';
import { useAuth } from '../contexts/AuthContext';
import { BACKEND_URL } from '../brand';
import { isIOSWebView } from '../hooks/useIsIOSWebView';
import { gLabel } from '../utils/genres';

// Share tokens are generated via secrets.token_urlsafe(24) (backend/db.py,
// get_or_create_share_token) — urlsafe base64, no padding, 32 chars for 24
// random bytes. A purely numeric string (or anything shorter/outside the
// urlsafe alphabet) never matches this and is rejected locally, before any
// network call — the enumeration-safety guard: a stranger guessing sequential
// numeric ids must never even reach the backend from this page.
const TOKEN_SHAPE = /^[A-Za-z0-9_-]{16,}$/;

// Matches the wizard's memorial photo cap (backend/main.py gates the photo
// endpoint's limit on variant.occasion === 'memorial': 10 instead of 5).
const PHOTO_MAX = 10;
const TRIBUTE_MAX = 1000;

// Same per-occasion tone as SongSharePage.jsx (the numeric-id share page this
// page's token-only route was split off from) — a memorial reached by a
// numeric legacy link and one reached by /memorial/:token should still read
// the same way.
const OCCASION_COPY = {
  memorial: { heading: (name, title) => name || title, subheading: 'Forever loved, never forgotten' },
  birthday: { heading: (name, title) => (name ? `Happy Birthday ${name}!` : title), subheading: 'A song made just for you' },
  anniversary: { heading: (name, title) => (name ? `Happy Anniversary ${name}!` : title), subheading: "Here's to many more" },
  celebration: { heading: (name, title) => name || title, subheading: 'A moment worth celebrating' },
};

// Same warm/paper visual identity as SongSharePage.jsx — deliberately not the
// main app's dark neon UI. PhotoCarousel (Task 8) reads --sp-mat/--sp-shadow/
// --sp-accent/--sp-border from its nearest ancestor; this page must define
// them itself since it is not nested inside SongSharePage's own wrapper.
const PAGE_CSS = `
@keyframes memFadeInUp { from { opacity: 0; transform: translateY(10px); } to { opacity: 1; transform: translateY(0); } }
.zb-share-page {
  --sp-bg: #f7f2ea; --sp-text: #2b2622; --sp-muted: #8a7f74; --sp-accent: #a8593f;
  --sp-mat: #fffdf9; --sp-border: rgba(43,38,34,0.12); --sp-shadow: rgba(43,38,34,0.16);
}
@media (prefers-color-scheme: dark) {
  .zb-share-page {
    --sp-bg: #211f1c; --sp-text: #ede7de; --sp-muted: #a89a8c; --sp-accent: #d98a6f;
    --sp-mat: #2b2724; --sp-border: rgba(237,231,222,0.14); --sp-shadow: rgba(0,0,0,0.45);
  }
}
.zb-share-content { animation: memFadeInUp 0.4s ease both; }
.zb-share-btn { background: transparent; border: 1px solid var(--sp-border); color: var(--sp-text); cursor: pointer; transition: border-color 0.2s, color 0.2s; }
.zb-share-btn:hover { border-color: var(--sp-accent); color: var(--sp-accent); }
.zb-owner-input {
  width: 100%; box-sizing: border-box; padding: 10px 12px; border-radius: 8px;
  border: 1px solid var(--sp-border); background: var(--sp-mat); color: var(--sp-text);
  font-size: 14px; font-family: inherit;
}
`;

const SERIF = "Georgia, 'Iowan Old Style', 'Palatino Linotype', 'Book Antiqua', serif";
const SANS = "-apple-system, BlinkMacSystemFont, 'Segoe UI', Helvetica, Arial, sans-serif";

export default function MemorialPage() {
  const { token } = useParams();
  const navigate = useNavigate();
  const { user, token: authToken, loading: authLoading } = useAuth();

  const [data, setData] = useState(null);
  const [notFound, setNotFound] = useState(false);

  // Ownership: the /public payload never carries anything auth-scoped, so
  // ownership is determined the same way SongsPage.jsx already builds its own
  // library view — GET /api/library (authenticated, owner-scoped server
  // side) and match this page's variant_id against it. This never sends a
  // numeric id anywhere: /api/library takes no id at all, and its match is
  // done entirely client-side against ids the server already scoped to the
  // logged-in user.
  const [ownerChecked, setOwnerChecked] = useState(false);
  const [isOwner, setIsOwner] = useState(false);
  const [fullVariant, setFullVariant] = useState(null); // richer row from /api/library, feeds SongCard

  const [credits, setCredits] = useState({});
  const [playlists, setPlaylists] = useState([]);

  const waveRef = useRef(null);
  const wsRef = useRef(null); // this page's OWN WaveSurfer instance — driven by handlePlay below
  // Separate from wsRef: SongsPage.jsx uses activeWsRef purely as cross-card
  // bookkeeping (never a page's own player) so a second WaveSurfer instance
  // (SongCard's) can pause the first one when both exist. Passing wsRef
  // itself here would let SongCard overwrite wsRef.current with its OWN
  // instance on play, silently hijacking this page's ▶ button.
  const activeWsRef = useRef(null);
  const [playing, setPlaying] = useState(false);
  const [wsReady, setWsReady] = useState(false);

  // ── Owner edit form (name / tribute) ──────────────────────────────────
  const [editName, setEditName] = useState('');
  const [editTribute, setEditTribute] = useState('');
  const [editSaving, setEditSaving] = useState(false);
  const [editSaved, setEditSaved] = useState(false);
  const [editError, setEditError] = useState('');

  // ── Owner photo management (separate, simpler panel than SongCard's own —
  // deliberate duplication, same as the brief's YAGNI note for Task 13: a
  // follow-up UI-only task can factor these together if it becomes a problem) ──
  const [photos, setPhotos] = useState([]);
  const [photoUploading, setPhotoUploading] = useState(false);
  const [photoError, setPhotoError] = useState('');
  const photoInputRef = useRef(null);

  // ── Owner share link + QR — the canonical /memorial/{token} URL, same
  // canvas-ref + toDataURL pattern as MemorialWizardPage.jsx's QR step. ──
  const qrWrapRef = useRef(null);
  const [linkCopied, setLinkCopied] = useState(false);

  // ── SongCard wiring state (favourite / discover-share / stems / YouTube /
  // sound-lock / delete) — real handlers backed by the same endpoints
  // SongsPage.jsx uses for the exact same actions ──
  const [isFavourite, setIsFavourite] = useState(false);
  const [isPublicDiscover, setIsPublicDiscover] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [deleteError, setDeleteError] = useState('');
  const [stemsData, setStemsData] = useState(undefined);
  const stemsPollRef = useRef(null);
  const [ytStatus, setYtStatus] = useState(undefined);
  const [ytUrl, setYtUrl] = useState(undefined);
  const [ytError, setYtError] = useState(undefined);
  const [soundToast, setSoundToast] = useState('');
  const soundToastTimer = useRef(null);
  const [upgradeNotice, setUpgradeNotice] = useState('');
  const upgradeTimer = useRef(null);

  // ── noindex — this page can carry personal photos and a tribute, and must
  // only ever be reached via a direct link/QR, never discovered through
  // search. Matches SongSharePage.jsx's more careful version (restores
  // whatever robots tag was there before, rather than assuming there wasn't
  // one) — the brief's own sketch used a cruder version of this. ──
  useEffect(() => {
    document.title = data?.occasion_name || data?.title || 'Memorial';
    let tag = document.querySelector('meta[name="robots"]');
    const existed = !!tag;
    const previousContent = tag?.getAttribute('content') ?? null;
    if (!tag) {
      tag = document.createElement('meta');
      tag.setAttribute('name', 'robots');
      document.head.appendChild(tag);
    }
    tag.setAttribute('content', 'noindex, nofollow');
    return () => {
      if (!existed) tag.remove();
      else if (previousContent !== null) tag.setAttribute('content', previousContent);
    };
  }, [data?.occasion_name, data?.title]);

  // ── Fetch the public payload — token-shape validated locally FIRST, so a
  // non-token param (e.g. a bare numeric id) never reaches the network at all. ──
  useEffect(() => {
    // TOKEN_SHAPE alone technically admits a 16+ digit numeric string (it's
    // still urlsafe-base64-alphabet). Reject that explicitly too, so a
    // numeric-shaped identifier can never reach the network call even in
    // that edge case — not just in practice (real tokens always mix in
    // letters/`_`/`-`), but as a literal guarantee.
    if (!TOKEN_SHAPE.test(token || '') || /^\d+$/.test(token || '')) {
      setNotFound(true);
      return;
    }
    let cancelled = false;
    fetch(`${BACKEND_URL}/api/songs/variants/${token}/public`)
      .then((r) => {
        if (!r.ok) throw new Error('not found');
        return r.json();
      })
      .then((json) => {
        if (cancelled) return;
        setData(json);
        setPhotos(json.photos || []);
        setEditName(json.occasion_name || '');
        setEditTribute(json.tribute_message || '');
      })
      .catch(() => { if (!cancelled) setNotFound(true); });
    return () => { cancelled = true; };
  }, [token]);

  // ── Ownership check + richer variant, once the public payload is in and
  // auth has finished loading (avoids a logged-in owner flashing as a
  // visitor while AuthContext is still validating the stored token). ──
  useEffect(() => {
    if (!data || authLoading) return;
    if (!user || !authToken) { setOwnerChecked(true); return; }
    let cancelled = false;
    fetch(`${BACKEND_URL}/api/library`, { headers: { Authorization: `Bearer ${authToken}` } })
      .then((r) => (r.ok ? r.json() : null))
      .then((json) => {
        if (cancelled) return;
        const mine = json?.variants?.find((v) => v.variant_id === data.variant_id);
        if (mine) {
          setIsOwner(true);
          setFullVariant(mine);
          setIsFavourite(!!mine.is_favourite);
          setIsPublicDiscover(!!mine.is_public);
        }
      })
      .catch(() => {})
      .finally(() => { if (!cancelled) setOwnerChecked(true); });
    return () => { cancelled = true; };
  }, [data, user, authToken, authLoading]);

  // Owner-only follow-up data — feature-gating credits and the playlist list
  // for SongCard's "More song tools" panel.
  useEffect(() => {
    if (!isOwner || !authToken) return;
    fetch(`${BACKEND_URL}/api/users/me/song_credits`, { headers: { Authorization: `Bearer ${authToken}` } })
      .then((r) => (r.ok ? r.json() : null)).then((j) => j && setCredits(j)).catch(() => {});
    fetch(`${BACKEND_URL}/api/playlists`, { headers: { Authorization: `Bearer ${authToken}` } })
      .then((r) => (r.ok ? r.json() : null)).then((j) => j && setPlaylists(j)).catch(() => {});
  }, [isOwner, authToken]);

  useEffect(() => () => {
    if (stemsPollRef.current) clearInterval(stemsPollRef.current);
    clearTimeout(soundToastTimer.current);
    clearTimeout(upgradeTimer.current);
  }, []);

  useEffect(() => {
    if (!data?.mp3_url || !waveRef.current) return;
    const isDark = window.matchMedia?.('(prefers-color-scheme: dark)').matches;
    const ws = WaveSurfer.create({
      container: waveRef.current,
      url: data.mp3_url,
      waveColor: isDark ? 'rgba(237,231,222,0.25)' : 'rgba(43,38,34,0.18)',
      progressColor: isDark ? '#d98a6f' : '#a8593f',
      height: 44, barWidth: 2, barGap: 2, barRadius: 2, cursorWidth: 0,
      normalize: true, interact: true,
    });
    ws.on('ready', () => setWsReady(true));
    ws.on('play', () => setPlaying(true));
    ws.on('pause', () => setPlaying(false));
    ws.on('finish', () => setPlaying(false));
    wsRef.current = ws;
    return () => { ws.destroy(); wsRef.current = null; setWsReady(false); setPlaying(false); };
  }, [data?.mp3_url]);

  const handlePlay = () => {
    if (!wsRef.current || !wsReady) return;
    playing ? wsRef.current.pause() : wsRef.current.play();
  };

  // ── Owner: name / tribute edit — same POST /occasion endpoint the wizard
  // (Task 13) uses. Always resends the CURRENT tribute_message when this
  // form itself isn't the source of the change (see handleSetOccasion
  // below) — the endpoint has no partial-update semantics: any field left
  // out of the request body is written back as NULL, so omitting
  // tribute_message here would silently erase it. ──
  async function saveTribute() {
    if (!fullVariant) return;
    setEditSaving(true); setEditError(''); setEditSaved(false);
    try {
      const r = await fetch(`${BACKEND_URL}/api/songs/variants/${fullVariant.variant_id}/occasion`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${authToken}` },
        body: JSON.stringify({
          occasion: data.occasion || 'memorial',
          occasion_name: editName.trim() || null,
          tribute_message: editTribute.trim() || null,
        }),
      });
      const json = await r.json().catch(() => ({}));
      if (!r.ok) throw new Error(json.detail || 'Could not save');
      setData((d) => (d ? { ...d, occasion_name: json.occasion_name, tribute_message: json.tribute_message } : d));
      setEditSaved(true);
      setTimeout(() => setEditSaved(false), 2000);
    } catch (err) {
      setEditError(err.message || 'Could not save');
    } finally {
      setEditSaving(false);
    }
  }

  // ── Owner: photo add/remove — same endpoints as the wizard's Photos step. ──
  async function handleAddPhoto(file) {
    if (!fullVariant || photos.length >= PHOTO_MAX) return;
    setPhotoUploading(true); setPhotoError('');
    try {
      const form = new FormData();
      form.append('file', file);
      const r = await fetch(`${BACKEND_URL}/api/songs/variants/${fullVariant.variant_id}/photos`, {
        method: 'POST', headers: { Authorization: `Bearer ${authToken}` }, body: form,
      });
      const j = await r.json().catch(() => ({}));
      if (!r.ok) throw new Error(j.detail || 'Photo upload failed');
      setPhotos((p) => [...p, { photo_id: j.photo_id, url: j.url }]);
    } catch (err) {
      setPhotoError(err.message || 'Photo upload failed');
    } finally {
      setPhotoUploading(false);
      if (photoInputRef.current) photoInputRef.current.value = '';
    }
  }

  async function handleRemovePhoto(photoId) {
    if (!fullVariant) return;
    try {
      const r = await fetch(`${BACKEND_URL}/api/songs/variants/${fullVariant.variant_id}/photos/${photoId}`, {
        method: 'DELETE', headers: { Authorization: `Bearer ${authToken}` },
      });
      if (r.ok) setPhotos((p) => p.filter((x) => x.photo_id !== photoId));
    } catch {
      // best-effort — the button just stays clickable, user can retry
    }
  }

  // ── Owner: share link + QR download. The memorial product's canonical URL
  // is /memorial/{token} (what the wizard mints and QR-encodes —
  // MemorialWizardPage.jsx:217,430,433), NOT SongCard's own QR panel, which
  // encodes /songs/share/{share_token} — the wrong page entirely for this
  // product. mark-qr-generated is only fired on an actual download (same as
  // the wizard), not just from rendering the code, so it doesn't arm the
  // delete-confirmation guard for a QR the owner never downloaded. ──
  const shareUrl = `${window.location.origin}/memorial/${token}`;

  async function handleCopyShareLink() {
    try {
      await navigator.clipboard.writeText(shareUrl);
      setLinkCopied(true);
      setTimeout(() => setLinkCopied(false), 2000);
    } catch {
      // clipboard access denied/unavailable — button just won't confirm, non-fatal
    }
  }

  function handleQrDownload() {
    const canvas = qrWrapRef.current?.querySelector('canvas');
    if (!canvas) return;
    const url = canvas.toDataURL('image/png');
    const a = document.createElement('a');
    a.href = url;
    a.download = `${(data?.occasion_name || data?.title || 'memorial').replace(/[^a-z0-9]/gi, '-').toLowerCase()}-qr.png`;
    document.body.appendChild(a);
    a.click();
    a.remove();
    if (fullVariant) handleMarkQrGenerated(fullVariant.variant_id);
  }

  // ── SongCard handlers ("More song tools") — real REST calls against the
  // same owner-scoped endpoints SongsPage.jsx already uses for these exact
  // actions. Two (onRemake, onAvatarClick) fall back to sending the owner to
  // their full Songs library instead of reimplementing SongsPage's
  // multi-step genre-picker / D-ID portrait modals here — those are real UI
  // flows, not simple REST calls, and out of scope for a memorial page's
  // secondary tools panel. Everything else here is a real, working call. ──

  async function handleSetOccasion(variantId, occasion, occasionName) {
    const r = await fetch(`${BACKEND_URL}/api/songs/variants/${variantId}/occasion`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${authToken}` },
      // tribute_message is deliberately resent here too (see saveTribute's
      // comment) — SongCard's own Occasion panel only knows about
      // occasion/occasion_name, and the endpoint nulls out any field it
      // isn't given.
      body: JSON.stringify({ occasion, occasion_name: occasionName, tribute_message: data?.tribute_message ?? null }),
    });
    const j = await r.json().catch(() => ({}));
    if (!r.ok) throw new Error(j.detail || 'Could not save');
    setFullVariant((v) => (v ? { ...v, occasion: j.occasion, occasion_name: j.occasion_name } : v));
    setData((d) => (d ? { ...d, occasion: j.occasion, occasion_name: j.occasion_name } : d));
    if (j.occasion_name != null) setEditName(j.occasion_name);
  }

  async function handleSetCoverPhoto(variantId, photoId) {
    const r = await fetch(`${BACKEND_URL}/api/songs/variants/${variantId}/cover-photo`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${authToken}` },
      body: JSON.stringify({ photo_id: photoId }),
    });
    const j = await r.json().catch(() => ({}));
    if (!r.ok) throw new Error(j.detail || 'Could not save');
    setFullVariant((v) => (v ? { ...v, cover_photo_id: j.cover_photo_id, image_url: j.image_url } : v));
  }

  function handleLoadPhotos() {
    // No-op: `photos` is already loaded from the /public payload (which
    // includes the token-gated photo list) and kept live via
    // handleAddPhoto/handleRemovePhoto above, so there's nothing to fetch.
  }

  async function handleUploadPhoto(_variantId, file) {
    await handleAddPhoto(file);
  }

  async function handleDeletePhoto(_variantId, photoId) {
    await handleRemovePhoto(photoId);
  }

  async function handleToggleFavourite(variantId) {
    setIsFavourite((v) => !v);
    try {
      const r = await fetch(`${BACKEND_URL}/api/songs/variants/${variantId}/favourite`, {
        method: 'PATCH', headers: { Authorization: `Bearer ${authToken}` },
      });
      if (!r.ok) throw new Error();
    } catch {
      setIsFavourite((v) => !v);
    }
  }

  async function handleShareToggle(variantId) {
    setIsPublicDiscover((v) => !v);
    try {
      const r = await fetch(`${BACKEND_URL}/api/songs/variants/${variantId}/share`, {
        method: 'PATCH', headers: { Authorization: `Bearer ${authToken}` },
      });
      if (!r.ok) throw new Error();
    } catch {
      setIsPublicDiscover((v) => !v);
    }
  }

  async function handleAddToPlaylist(variantId, playlistId) {
    try {
      const r = await fetch(`${BACKEND_URL}/api/playlists/${playlistId}/songs`, {
        method: 'POST',
        headers: { Authorization: `Bearer ${authToken}`, 'Content-Type': 'application/json' },
        body: JSON.stringify({ variant_id: variantId }),
      });
      if (r.ok) return await r.json();
      return null;
    } catch {
      return null;
    }
  }

  function handleMarkQrGenerated(variantId) {
    fetch(`${BACKEND_URL}/api/songs/variants/${variantId}/mark-qr-generated`, {
      method: 'POST', headers: { Authorization: `Bearer ${authToken}` },
    }).catch(() => {});
  }

  async function handleGetStems(variantId) {
    try {
      const r = await fetch(`${BACKEND_URL}/api/songs/variants/${variantId}/stems`, {
        method: 'POST', headers: { Authorization: `Bearer ${authToken}` },
      });
      const j = await r.json();
      if (!r.ok) { alert(j.detail || 'Could not start stem separation'); return; }
      setStemsData(j);
      if (j.stems_status === 'pending') {
        stemsPollRef.current = setInterval(async () => {
          const pr = await fetch(`${BACKEND_URL}/api/songs/variants/${variantId}/stems`, {
            headers: { Authorization: `Bearer ${authToken}` },
          });
          if (!pr.ok) return;
          const pd = await pr.json();
          setStemsData(pd);
          if (pd.stems_status !== 'pending') clearInterval(stemsPollRef.current);
        }, 5000);
      }
    } catch {
      alert('Network error starting stem separation');
    }
  }

  async function handleTelegramClick(variant, songTitle) {
    const genre = gLabel(variant.genre_tag || '');
    const message = `🎵 <b>${songTitle || 'New Song'}</b> — ${genre}\n\nCreated with Zeus Beats AI Music\n🌐 zeusbeats.com`;
    const r = await fetch(`${BACKEND_URL}/api/telegram/post`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${authToken}` },
      body: JSON.stringify({ message, image_url: variant.image_url || null }),
    });
    if (!r.ok) throw new Error('Telegram post failed');
  }

  async function handleLockSound(variant) {
    const isPaid = user?.is_admin ||
      (user?.subscription_status === 'active' && ['music_starter', 'music_pro', 'music_agency'].includes(user?.subscription_plan));
    if (!isPaid) {
      clearTimeout(soundToastTimer.current);
      setSoundToast('Upgrade to Music Starter to unlock Your Sound 🔒');
      soundToastTimer.current = setTimeout(() => setSoundToast(''), 4000);
      return;
    }
    try {
      const r = await fetch(`${BACKEND_URL}/api/user/sound`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${authToken}` },
        body: JSON.stringify({ variant_id: variant.variant_id }),
      });
      const j = await r.json();
      if (!r.ok) throw new Error(j.detail || 'Failed to lock sound');
      clearTimeout(soundToastTimer.current);
      setSoundToast(`Your Sound locked to "${j.sound_persona_title}" 🔒`);
      soundToastTimer.current = setTimeout(() => setSoundToast(''), 4000);
    } catch (err) {
      clearTimeout(soundToastTimer.current);
      setSoundToast(`Error: ${err.message}`);
      soundToastTimer.current = setTimeout(() => setSoundToast(''), 4000);
    }
  }

  function handleUpgrade() {
    // iOS App Store compliance: no pricing/upgrade CTA inside the native
    // wrapper (see project_ios_app_store_compliance) — point people at the
    // website instead of navigating to /billing.
    if (isIOSWebView) {
      clearTimeout(upgradeTimer.current);
      setUpgradeNotice('Visit zeusbeats.com to upgrade your plan.');
      upgradeTimer.current = setTimeout(() => setUpgradeNotice(''), 4000);
      return;
    }
    navigate('/billing');
  }

  function handleYouTubeClick(variant) {
    if (!canYouTube(credits)) { handleUpgrade(); return; }
    if (!credits.youtube_connected) {
      window.location.href = `${BACKEND_URL}/api/youtube/auth?token=${authToken}&origin=beats`;
      return;
    }
    handleYouTubeUpload(variant);
  }

  async function handleYouTubeUpload(variant) {
    setYtStatus('uploading'); setYtError(undefined);
    try {
      const r = await fetch(`${BACKEND_URL}/api/songs/variants/${variant.variant_id}/upload-youtube`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${authToken}` },
        // No privacy/title picker modal here (unlike SongsPage's) — default
        // to unlisted, which is the sensible default for a memorial song.
        body: JSON.stringify({ privacy: 'unlisted', title: data?.occasion_name || data?.title }),
      });
      let j = {};
      try { j = await r.json(); } catch { /* non-JSON error body — j stays {} */ }
      if (!r.ok) throw new Error(j.detail || `Upload failed (HTTP ${r.status})`);
      setYtStatus('done'); setYtUrl(j.youtube_url);
    } catch (err) {
      setYtError(err.message || 'Upload failed — network or server error');
      setYtStatus('error');
    }
  }

  async function handleOpenCover(variantId) {
    const lyrics = window.prompt("Enter lyrics for a cover of this song (leave blank to cancel):");
    if (!lyrics || !lyrics.trim()) return;
    try {
      const r = await fetch(`${BACKEND_URL}/api/songs/variants/${variantId}/cover`, {
        method: 'POST',
        headers: { Authorization: `Bearer ${authToken}`, 'Content-Type': 'application/json' },
        body: JSON.stringify({ lyrics: lyrics.trim() }),
      });
      const j = await r.json().catch(() => ({}));
      if (!r.ok) { alert(j.detail || 'Something went wrong'); return; }
      alert('Cover started — check your Songs library shortly.');
    } catch {
      alert('Network error. Try again.');
    }
  }

  function goToLibrary() {
    navigate('/songs');
  }

  async function handleDelete(variantId) {
    if (!window.confirm('Delete this song? This cannot be undone.')) return;
    setDeleting(true); setDeleteError('');
    try {
      let r = await fetch(`${BACKEND_URL}/api/songs/variants/${variantId}`, {
        method: 'DELETE', headers: { Authorization: `Bearer ${authToken}` },
      });
      if (r.status === 409) {
        const j = await r.json().catch(() => ({}));
        const confirmed = window.confirm(`${j.detail || 'A QR code was generated for this song.'} Delete anyway?`);
        if (!confirmed) { setDeleting(false); return; }
        r = await fetch(`${BACKEND_URL}/api/songs/variants/${variantId}?confirm_qr_delete=true`, {
          method: 'DELETE', headers: { Authorization: `Bearer ${authToken}` },
        });
      }
      if (!r.ok) throw new Error('Delete failed');
      navigate('/songs');
    } catch (err) {
      setDeleteError(err.message || 'Delete failed');
      setDeleting(false);
    }
  }

  // Same feature-gating logic as SongsPage.jsx, computed from the same
  // GET /api/users/me/song_credits shape.
  function canYouTube(c) {
    return !!c.is_admin || ['agency', 'enterprise'].includes(c.plan) ||
      ['music_starter', 'music_pro', 'music_agency'].includes(c.plan);
  }
  const isAdmin = !!credits.is_admin;
  const isFreeTier = !isAdmin && !credits.plan && !credits.has_paid;
  const didPlanOk = isAdmin || ['agency', 'enterprise', 'music_pro', 'music_agency'].includes(credits.plan);
  const canDid = didPlanOk && (isAdmin || credits.video_credits > 0);

  if (notFound) {
    return (
      <>
        <style>{PAGE_CSS}</style>
        <div className="zb-share-page" style={{ background: 'var(--sp-bg)', minHeight: '100vh', display: 'flex', alignItems: 'center', justifyContent: 'center', color: 'var(--sp-text)', fontFamily: SANS, padding: 24, textAlign: 'center' }}>
          <p style={{ color: 'var(--sp-muted)', fontSize: 15 }}>This memorial page could not be found.</p>
        </div>
      </>
    );
  }

  if (!data) {
    return (
      <>
        <style>{PAGE_CSS}</style>
        <div className="zb-share-page" style={{ background: 'var(--sp-bg)', minHeight: '100vh', display: 'flex', alignItems: 'center', justifyContent: 'center', color: 'var(--sp-muted)', fontFamily: SANS }}>
          Loading…
        </div>
      </>
    );
  }

  const dur = data.duration_seconds;
  const durStr = dur ? `${Math.floor(dur / 60)}:${String(dur % 60).padStart(2, '0')}` : '';
  const occasionCopy = data.occasion ? OCCASION_COPY[data.occasion] : null;
  const heading = occasionCopy ? occasionCopy.heading(data.occasion_name, data.title) : data.title;
  const subheading = occasionCopy?.subheading;

  return (
    <>
      <style>{PAGE_CSS}</style>
      <div className="zb-share-page" style={{ background: 'var(--sp-bg)', minHeight: '100vh', display: 'flex', flexDirection: 'column', alignItems: 'center', padding: '48px 20px 64px', color: 'var(--sp-text)', fontFamily: SANS }}>
        <div className="zb-share-content" style={{ width: '100%', maxWidth: 420, textAlign: 'center' }}>
          {/* Cover art / photos */}
          {photos.length > 1 ? (
            <div style={{ marginBottom: 22 }}>
              <PhotoCarousel photos={photos} />
            </div>
          ) : photos.length === 1 ? (
            <div style={{ background: 'var(--sp-mat)', padding: 8, borderRadius: 10, boxShadow: '0 4px 16px var(--sp-shadow)', marginBottom: 22 }}>
              <img src={photos[0].url} alt="" style={{ width: '100%', aspectRatio: '1 / 1', objectFit: 'cover', borderRadius: 4, display: 'block' }} />
            </div>
          ) : (
            <div style={{ background: 'var(--sp-mat)', padding: 12, borderRadius: 14, boxShadow: '0 8px 28px var(--sp-shadow)', marginBottom: 22 }}>
              {data.image_url ? (
                <img src={data.image_url} alt={data.title} style={{ width: '100%', aspectRatio: '1 / 1', objectFit: 'cover', display: 'block', borderRadius: 6 }} />
              ) : (
                <div style={{ width: '100%', aspectRatio: '1 / 1', borderRadius: 6, background: 'var(--sp-bg)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                  <span style={{ fontSize: 56, opacity: 0.2 }}>♫</span>
                </div>
              )}
            </div>
          )}

          <div style={{ fontFamily: SERIF, fontWeight: 500, fontSize: 26, lineHeight: 1.3, marginBottom: subheading ? 4 : 6 }}>
            {heading}
          </div>
          {subheading && (
            <div style={{ fontFamily: SERIF, fontStyle: 'italic', fontSize: 15, color: 'var(--sp-accent)', marginBottom: 14 }}>
              {subheading}
            </div>
          )}

          {/* Tribute message */}
          {data.tribute_message && (
            <p style={{ fontFamily: SERIF, fontSize: 15, lineHeight: 1.7, color: 'var(--sp-text)', whiteSpace: 'pre-wrap', margin: '0 0 22px' }}>
              {data.tribute_message}
            </p>
          )}

          {(gLabel(data.genre_tag) || durStr) && (
            <div style={{ fontSize: 13, color: 'var(--sp-muted)', marginBottom: 20 }}>
              {[gLabel(data.genre_tag), durStr].filter(Boolean).join(' · ')}
            </div>
          )}

          {/* Player */}
          <div style={{ display: 'flex', alignItems: 'center', gap: 14, marginBottom: 22 }}>
            <button
              onClick={handlePlay}
              disabled={!wsReady}
              aria-label={playing ? 'Pause' : 'Play'}
              style={{
                width: 42, height: 42, borderRadius: '50%', border: '1px solid var(--sp-accent)',
                background: 'transparent', color: 'var(--sp-accent)', fontSize: 14,
                cursor: wsReady ? 'pointer' : 'default', display: 'flex', alignItems: 'center', justifyContent: 'center',
                flexShrink: 0, opacity: wsReady ? 1 : 0.35, transition: 'opacity 0.3s',
              }}
            >
              {playing ? '⏸' : '▶'}
            </button>
            <div ref={waveRef} style={{ flex: 1, opacity: wsReady ? 1 : 0.2, transition: 'opacity 0.4s', minWidth: 0 }} />
          </div>

          <div style={{ marginBottom: 4 }}>
            <a
              href={data.mp3_url}
              download={`${(data.title || 'song').replace(/[^a-z0-9]/gi, '-').toLowerCase()}.mp3`}
              className="zb-share-btn"
              style={{ display: 'inline-block', padding: '11px 22px', borderRadius: 9, fontSize: 13, textDecoration: 'none' }}
            >
              Download
            </a>
          </div>
        </div>

        {/* Owner-only management */}
        {ownerChecked && isOwner && fullVariant && (
          <div style={{ width: '100%', maxWidth: 420, marginTop: 44, textAlign: 'left' }}>
            <h2 style={{ fontFamily: SERIF, fontSize: 18, fontWeight: 600, marginBottom: 4 }}>Manage this memorial</h2>
            <p style={{ fontSize: 13, color: 'var(--sp-muted)', marginBottom: 18 }}>Only visible to you.</p>

            <div style={{ background: 'var(--sp-mat)', border: '1px solid var(--sp-border)', borderRadius: 12, padding: 18, marginBottom: 18 }}>
              <label style={{ display: 'block', fontSize: 12, color: 'var(--sp-muted)', marginBottom: 6 }}>Name</label>
              <input
                value={editName}
                onChange={(e) => setEditName(e.target.value)}
                maxLength={120}
                className="zb-owner-input"
                style={{ marginBottom: 14 }}
              />
              <label style={{ display: 'block', fontSize: 12, color: 'var(--sp-muted)', marginBottom: 6 }}>Tribute message</label>
              <textarea
                value={editTribute}
                onChange={(e) => setEditTribute(e.target.value.slice(0, TRIBUTE_MAX))}
                rows={5}
                className="zb-owner-input"
              />
              <div style={{ textAlign: 'right', fontSize: 11, color: 'var(--sp-muted)', marginBottom: 12 }}>
                {editTribute.length}/{TRIBUTE_MAX}
              </div>
              <button type="button" className="zb-share-btn" onClick={saveTribute} disabled={editSaving} style={{ padding: '9px 18px', borderRadius: 8, fontSize: 13 }}>
                {editSaving ? 'Saving…' : editSaved ? 'Saved ✓' : 'Save'}
              </button>
              {editError && <p style={{ color: '#c0392b', fontSize: 12, marginTop: 8 }}>{editError}</p>}
            </div>

            <div style={{ background: 'var(--sp-mat)', border: '1px solid var(--sp-border)', borderRadius: 12, padding: 18, marginBottom: 18 }}>
              <label style={{ display: 'block', fontSize: 12, color: 'var(--sp-muted)', marginBottom: 10 }}>
                Photos ({photos.length}/{PHOTO_MAX})
              </label>
              {photos.length > 0 && (
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8, marginBottom: 12 }}>
                  {photos.map((p) => (
                    <div key={p.photo_id} style={{ position: 'relative' }}>
                      <img src={p.url} alt="" style={{ width: 56, height: 56, objectFit: 'cover', borderRadius: 6, display: 'block' }} />
                      <button
                        type="button"
                        onClick={() => handleRemovePhoto(p.photo_id)}
                        title="Remove photo"
                        style={{
                          position: 'absolute', top: -6, right: -6, width: 20, height: 20, borderRadius: '50%',
                          border: 'none', background: 'rgba(0,0,0,0.75)', color: '#fff', fontSize: 11,
                          cursor: 'pointer', display: 'flex', alignItems: 'center', justifyContent: 'center', lineHeight: 1,
                        }}
                      >
                        ✕
                      </button>
                    </div>
                  ))}
                </div>
              )}
              <input
                ref={photoInputRef}
                type="file"
                accept="image/*,.heic,.heif"
                disabled={photos.length >= PHOTO_MAX || photoUploading}
                onChange={(e) => e.target.files[0] && handleAddPhoto(e.target.files[0])}
              />
              {photoUploading && <p style={{ fontSize: 12, color: 'var(--sp-muted)', marginTop: 8 }}>Uploading…</p>}
              {photoError && <p style={{ color: '#c0392b', fontSize: 12, marginTop: 8 }}>{photoError}</p>}
            </div>

            <div style={{ background: 'var(--sp-mat)', border: '1px solid var(--sp-border)', borderRadius: 12, padding: 18, marginBottom: 18 }}>
              <label style={{ display: 'block', fontSize: 12, color: 'var(--sp-muted)', marginBottom: 10 }}>Share this memorial</label>
              <div style={{ display: 'flex', gap: 8, alignItems: 'center', marginBottom: 14 }}>
                <input readOnly value={shareUrl} className="zb-owner-input" style={{ flex: 1, fontSize: 12 }} onFocus={(e) => e.target.select()} />
                <button type="button" className="zb-share-btn" onClick={handleCopyShareLink} style={{ padding: '9px 14px', borderRadius: 8, fontSize: 12, flexShrink: 0 }}>
                  {linkCopied ? 'Copied ✓' : 'Copy'}
                </button>
              </div>
              <div style={{ display: 'flex', alignItems: 'center', gap: 14 }}>
                <div ref={qrWrapRef} style={{ display: 'inline-block', padding: 8, background: '#fff', borderRadius: 8, lineHeight: 0 }}>
                  <QRCodeCanvas value={shareUrl} size={96} bgColor="#ffffff" fgColor="#0b0b14" level="H" />
                </div>
                <button type="button" className="zb-share-btn" onClick={handleQrDownload} style={{ padding: '9px 16px', borderRadius: 8, fontSize: 12 }}>
                  Download QR code
                </button>
              </div>
            </div>

            {deleteError && <p style={{ color: '#c0392b', fontSize: 13, marginBottom: 10 }}>{deleteError}</p>}
            {soundToast && <p style={{ fontSize: 13, color: 'var(--sp-accent)', marginBottom: 10 }}>{soundToast}</p>}
            {upgradeNotice && <p style={{ fontSize: 13, color: 'var(--sp-accent)', marginBottom: 10 }}>{upgradeNotice}</p>}

            <CollapsibleSection title="More song tools">
              <SongCard
                variant={{ ...fullVariant, is_favourite: isFavourite, is_public: isPublicDiscover }}
                title={fullVariant.title || data.title}
                lyricId={fullVariant.lyric_id}
                activeWsRef={activeWsRef}
                canYouTube={canYouTube(credits)}
                ytConnected={!!credits.youtube_connected}
                ytStatus={ytStatus}
                ytUrl={ytUrl}
                ytError={ytError}
                onYouTubeClick={handleYouTubeClick}
                canDid={canDid}
                didSt={undefined}
                videoUrl={fullVariant.video_url}
                onAvatarClick={goToLibrary}
                videoCredits={credits.video_credits}
                didPlanOk={didPlanOk}
                isAdmin={isAdmin}
                onDelete={handleDelete}
                deleting={deleting}
                musicVideoUrl={fullVariant.music_video_url}
                onRemake={goToLibrary}
                onTelegramClick={handleTelegramClick}
                artistName={credits.artist_name}
                // Same reduction as onRemake/onAvatarClick above (a real
                // regenerate needs credits + job-polling infrastructure this
                // page doesn't have) — but leaving this undefined made the
                // button silently do nothing on click (SongCard's handleRegen
                // no-ops when !onRegenerate) rather than visibly redirecting
                // like Remake/Avatar do. Route it the same way instead.
                onRegenerate={goToLibrary}
                isFavourite={isFavourite}
                onToggleFavourite={handleToggleFavourite}
                isFreeTier={isFreeTier}
                isPublic={isPublicDiscover}
                onShareToggle={handleShareToggle}
                playlists={playlists}
                onAddToPlaylist={handleAddToPlaylist}
                premiumCredits={credits.premium_credits}
                stemsData={stemsData}
                onGetStems={handleGetStems}
                onOpenCover={handleOpenCover}
                onUpgrade={handleUpgrade}
                soundPersonaVariantId={null}
                onLockSound={handleLockSound}
                onMarkQrGenerated={handleMarkQrGenerated}
                photos={photos}
                onLoadPhotos={handleLoadPhotos}
                onUploadPhoto={handleUploadPhoto}
                onDeletePhoto={handleDeletePhoto}
                onSetOccasion={handleSetOccasion}
                onSetCoverPhoto={handleSetCoverPhoto}
                isSaved={false}
                isDownloading={false}
                // Offline save is a PWA feature backed by useOfflineSongs in
                // SongsPage.jsx, not reimplemented here — but null left the
                // "Save Offline" button enabled and silently inert on click
                // (unlike Remake/Avatar/Regenerate, which visibly redirect).
                // Route it the same way instead of leaving it dead.
                onSaveOffline={goToLibrary}
                onRemoveSaved={goToLibrary}
                onPlayOffline={null}
              />
            </CollapsibleSection>
          </div>
        )}

        <p style={{ marginTop: 44, fontSize: 12, color: 'var(--sp-muted)', textAlign: 'center' }}>
          Made with{' '}
          <a href="/" style={{ color: 'var(--sp-muted)', textDecoration: 'underline' }}>Zeus Beats</a>
        </p>
      </div>
    </>
  );
}
