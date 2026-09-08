import { memo, useEffect, useRef, useState } from 'react';
import { Link } from 'react-router-dom';
import WaveSurfer from 'wavesurfer.js';
import { QRCodeSVG, QRCodeCanvas } from 'qrcode.react';
import { useTranslation } from 'react-i18next';
import { BACKEND_URL } from '../brand';
import LyricsModal from './LyricsModal';
import { audioManager } from '../utils/audioManager';
import { isIOSWebView } from '../hooks/useIsIOSWebView';
// genreColor/gLabel stay defined in SongsPage.jsx (not duplicated here) because
// genres.test.mjs text-scans that file for a literal "const GENRE_CATEGORIES ="
// declaration; they're only referenced inside this component's render body
// below, never at this module's own top level, so importing them back from the
// page that imports this component is safe (no temporal-dead-zone issue).
import { genreColor, gLabel } from '../pages/SongsPage';

export const S = {
  card: {
    background: '#12121e',
    border: '1px solid rgba(255,255,255,0.07)',
    borderRadius: 12,
    overflow: 'hidden',
    display: 'flex',
    flexDirection: 'column',
  },
  artBox: {
    width: '100%',
    aspectRatio: '1 / 1',
    objectFit: 'cover',
    display: 'block',
  },
  artPlaceholder: {
    background: 'linear-gradient(135deg, #1a1040 0%, #0e0e22 100%)',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
  },
  cardBody: {
    padding: '12px 14px 14px',
    flex: 1,
    display: 'flex',
    flexDirection: 'column',
  },
  cardTitle: {
    color: '#e2d9f3',
    fontWeight: 600,
    fontSize: 14,
    whiteSpace: 'nowrap',
    overflow: 'hidden',
    textOverflow: 'ellipsis',
    marginTop: 4,
  },
  pill: {
    background: 'rgba(167,139,250,0.15)',
    color: '#c4b5fd',
    border: '1px solid rgba(167,139,250,0.3)',
    borderRadius: 20,
    padding: '2px 10px',
    fontSize: 11,
    fontWeight: 500,
    flexShrink: 0,
  },
  grid: {
    display: 'grid',
    gap: 16,
  },
};

export const actionBtnStyle = {
  flex: 1,
  minHeight: 44,
  padding: '6px 0',
  borderRadius: 6,
  border: '1px solid rgba(255,255,255,0.3)',
  background: 'transparent',
  color: '#ccc',
  fontSize: 11,
  fontWeight: 600,
  cursor: 'pointer',
  letterSpacing: '0.2px',
  textAlign: 'center',
  textDecoration: 'none',
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'center',
  transition: 'color 0.2s ease, border-color 0.2s ease, box-shadow 0.2s ease',
};

const OCCASION_OPTIONS = [
  { value: '', label: 'None (just the song title)' },
  { value: 'memorial', label: 'Memorial' },
  { value: 'birthday', label: 'Birthday' },
  { value: 'anniversary', label: 'Anniversary' },
  { value: 'celebration', label: 'Celebration' },
];

const SongCard = memo(function SongCard({
  variant, title, artistName, activeWsRef,
  canYouTube, ytConnected, ytStatus: ytSt, ytUrl, ytError, onYouTubeClick,
  canDid, didSt, videoUrl, onAvatarClick, videoCredits, didPlanOk, isAdmin,
  onDelete, deleting, musicVideoUrl, onRemake, onTelegramClick, onRegenerate,
  isFavourite, onToggleFavourite, isFreeTier,
  isPublic, onShareToggle,
  playlists, onAddToPlaylist,
  premiumCredits, stemsData: stemsProp, onGetStems, onOpenCover, onUpgrade,
  soundPersonaVariantId, onLockSound, onMarkQrGenerated,
  photos, onLoadPhotos, onUploadPhoto, onDeletePhoto, onSetOccasion, onSetCoverPhoto,
  isSaved, isDownloading, onSaveOffline, onRemoveSaved, onPlayOffline,
  lyricId,
}) {
  const { t } = useTranslation();
  const waveRef = useRef(null);
  const wsRef   = useRef(null);
  const [playing, setPlaying]     = useState(false);
  const [showLyrics, setShowLyrics] = useState(false);
  const effectiveLyricId = lyricId ?? variant.lyric_id;
  const hasLyrics = effectiveLyricId != null;
  const [wsReady, setWsReady]     = useState(false);
  const [copied, setCopied]       = useState(false);
  const [tgPosting, setTgPosting]       = useState(false);
  const [tgPosted, setTgPosted]         = useState(false);
  const [regenLoading, setRegenLoading] = useState(false);
  const [downloaded, setDownloaded] = useState(false);
  const [videoErr, setVideoErr] = useState(false);
  const [favToast, setFavToast] = useState(null); // null | 'added' | 'removed'
  const [igToast, setIgToast]         = useState('');
  const [addMenuOpen, setAddMenuOpen] = useState(false);
  const addMenuRef = useRef(null);
  const [addToast, setAddToast]       = useState(null);
  const addToastTimer = useRef(null);
  const [shareToast, setShareToast]   = useState(null); // null | 'public' | 'private'
  const shareToastTimer = useRef(null);
  const favToastTimer = useRef(null);
  const [stemsOpen, setStemsOpen] = useState(false);
  const [qrOpen, setQrOpen] = useState(false);
  const [qrJustMarked, setQrJustMarked] = useState(false);
  const [photosOpen, setPhotosOpen] = useState(false);
  const [photoUploading, setPhotoUploading] = useState(false);
  const [photoError, setPhotoError] = useState('');
  const [photoPrivacyChecked, setPhotoPrivacyChecked] = useState(false);
  const photoInputRef = useRef(null);
  const photoList = photos || [];
  const [coverSavingId, setCoverSavingId] = useState(null);

  const handleToggleCoverPhoto = async (photoId) => {
    const nextCoverId = variant.cover_photo_id === photoId ? null : photoId;
    setCoverSavingId(photoId);
    try {
      await onSetCoverPhoto(variant.variant_id, nextCoverId);
    } catch {
      // best-effort — thumbnail's cover badge just won't update, user can retry
    } finally {
      setCoverSavingId(null);
    }
  };

  const [occasionOpen, setOccasionOpen] = useState(false);
  const [occasionDraft, setOccasionDraft] = useState(variant.occasion || '');
  const [occasionNameDraft, setOccasionNameDraft] = useState(variant.occasion_name || '');
  const [occasionSaving, setOccasionSaving] = useState(false);
  const [occasionError, setOccasionError] = useState('');
  const [occasionSaved, setOccasionSaved] = useState(false);

  const toggleOccasionPanel = () => {
    const opening = !occasionOpen;
    setOccasionOpen(opening);
    if (opening) {
      // Reflect whatever's actually saved, not a stale draft from a previous open.
      setOccasionDraft(variant.occasion || '');
      setOccasionNameDraft(variant.occasion_name || '');
      setOccasionError('');
      setOccasionSaved(false);
    }
  };

  const handleSaveOccasion = async () => {
    setOccasionSaving(true);
    setOccasionError('');
    try {
      await onSetOccasion(variant.variant_id, occasionDraft || null, occasionDraft ? (occasionNameDraft || null) : null);
      setOccasionSaved(true);
      setTimeout(() => setOccasionSaved(false), 2000);
    } catch (err) {
      setOccasionError(err.message || 'Could not save');
    } finally {
      setOccasionSaving(false);
    }
  };

  const togglePhotosPanel = () => {
    const opening = !photosOpen;
    setPhotosOpen(opening);
    setPhotoError('');
    // Reset every time the panel opens — the tick must never be "remembered"
    // from a previous session, per the privacy requirement.
    setPhotoPrivacyChecked(false);
    if (opening && !photos) onLoadPhotos?.(variant.variant_id);
  };

  const handlePhotoFilesSelected = async (e) => {
    const files = [...(e.target.files || [])];
    e.target.value = '';
    if (!files.length) return;
    if (!photoPrivacyChecked) {
      setPhotoError('Please tick the box confirming you understand these photos will be visible to anyone with the link, before adding photos.');
      return;
    }
    const remaining = 5 - photoList.length;
    if (remaining <= 0) {
      setPhotoError('Maximum 5 photos per song.');
      return;
    }
    setPhotoError('');
    setPhotoUploading(true);
    try {
      for (const file of files.slice(0, remaining)) {
        await onUploadPhoto(variant.variant_id, file);
      }
    } catch (err) {
      setPhotoError(err.message || 'Upload failed');
    } finally {
      setPhotoUploading(false);
    }
  };
  const qrCanvasWrapRef = useRef(null);
  const qrSvgWrapRef = useRef(null);
  const qrAlreadyMarked = !!variant.qr_generated || qrJustMarked;
  // Prefer the unguessable share_token once the song has one (i.e. has photos) —
  // the plain numeric link never exposes photos, so a NEW QR/share link for a
  // photo-bearing song must use the token instead. A QR generated before photos
  // existed keeps using the numeric link and simply won't show them; that's a
  // known tradeoff, not a bug — see the "add photos to a QR'd song" notice below.
  const shareUrlForQr = variant.share_token
    ? `${window.location.origin}/songs/share/${variant.share_token}`
    : `${window.location.origin}/songs/share/${variant.variant_id}`;
  const qrFilenameBase = (title || `song-${variant.variant_id}`).replace(/[^a-z0-9]/gi, '-').toLowerCase();

  const handleQrDownload = (format) => {
    const node = (format === 'png' ? qrCanvasWrapRef : qrSvgWrapRef).current?.querySelector(format === 'png' ? 'canvas' : 'svg');
    if (!node) return;
    let url, revoke = true;
    if (format === 'png') {
      url = node.toDataURL('image/png');
      revoke = false;
    } else {
      const svgText = new XMLSerializer().serializeToString(node);
      url = URL.createObjectURL(new Blob([svgText], { type: 'image/svg+xml' }));
    }
    const a = document.createElement('a');
    a.href = url;
    a.download = `${qrFilenameBase}-qr.${format}`;
    document.body.appendChild(a);
    a.click();
    a.remove();
    if (revoke) URL.revokeObjectURL(url);
    if (!qrAlreadyMarked) {
      setQrJustMarked(true);
      onMarkQrGenerated?.(variant.variant_id);
    }
  };
  const handleFavToggle = () => {
    const adding = !isFavourite;
    onToggleFavourite(variant.variant_id);
    setFavToast(adding ? 'added' : 'removed');
    clearTimeout(favToastTimer.current);
    favToastTimer.current = setTimeout(() => setFavToast(null), 2500);
  };
  const [lockedMsg, setLockedMsg] = useState(null);
  const lockedTimer = useRef(null);
  const showLocked = (msg) => {
    setLockedMsg(msg);
    clearTimeout(lockedTimer.current);
    lockedTimer.current = setTimeout(() => setLockedMsg(null), 3500);
  };

  useEffect(() => {
    if (!addMenuOpen) return;
    const handler = (e) => {
      if (addMenuRef.current && !addMenuRef.current.contains(e.target)) setAddMenuOpen(false);
    };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, [addMenuOpen]);

  const handleAddToList = async (playlistId) => {
    const pl = playlists?.find(p => p.id === playlistId);
    setAddMenuOpen(false);
    const result = await onAddToPlaylist(variant.variant_id, playlistId);
    clearTimeout(addToastTimer.current);
    if (result?.added) {
      setAddToast(`Added to ${pl?.name || 'playlist'} ✅`);
    } else {
      setAddToast('Already in playlist');
    }
    addToastTimer.current = setTimeout(() => setAddToast(null), 2500);
  };

  const handleRegen = async () => {
    if (regenLoading || !onRegenerate) return;
    setRegenLoading(true);
    try {
      await onRegenerate(variant.variant_id, variant.genre_tag, title);
    } finally {
      setRegenLoading(false);
    }
  };

  useEffect(() => {
    if (!variant.mp3_url || !waveRef.current) return;
    const ws = WaveSurfer.create({
      container:     waveRef.current,
      url:           variant.mp3_url,
      waveColor:     '#252535',
      progressColor: '#a78bfa',
      height:        40,
      barWidth:      2,
      barGap:        1,
      barRadius:     2,
      cursorWidth:   0,
      normalize:     true,
      interact:      true,
    });
    ws.on('ready',  () => setWsReady(true));
    ws.on('play',   () => setPlaying(true));
    ws.on('pause',  () => setPlaying(false));
    ws.on('finish', () => setPlaying(false));
    wsRef.current = ws;
    return () => {
      ws.destroy();
      wsRef.current = null;
      setWsReady(false);
      setPlaying(false);
    };
  }, [variant.mp3_url]);

  const handlePlay = () => {
    if (!wsRef.current || !wsReady) return;
    if (playing) {
      wsRef.current.pause();
      audioManager.stop();
    } else {
      // Stops NowPlaying audio and any other WaveSurfer before starting this one
      audioManager.playWaveSurfer(wsRef.current, variant.variant_id);
      if (activeWsRef.current && activeWsRef.current !== wsRef.current) {
        activeWsRef.current.pause();
      }
      wsRef.current.play();
      activeWsRef.current = wsRef.current;
    }
  };

  const handleTelegram = async () => {
    if (tgPosting || !onTelegramClick) return;
    setTgPosting(true);
    try {
      await onTelegramClick(variant, title);
      setTgPosted(true);
    } finally {
      setTgPosting(false);
    }
  };

  const handleShare = async () => {
    // Same token preference as the QR value — once photos exist, every share
    // surface should point at the link that actually shows them.
    const shareUrl = variant.share_token
      ? `${window.location.origin}/songs/share/${variant.share_token}`
      : `${window.location.origin}/songs/share/${variant.variant_id}`;
    const shareData = {
      title: title || `Song #${variant.variant_id}`,
      text: 'Listen to my AI-generated song',
      url: shareUrl,
    };
    if (navigator.share) {
      try { await navigator.share(shareData); } catch (_) {}
    } else {
      try {
        await navigator.clipboard.writeText(shareUrl);
        setCopied(true);
        setTimeout(() => setCopied(false), 2000);
      } catch (_) {}
    }
  };

  const handleSharePublicToggle = () => {
    if (!onShareToggle) return;
    const makingPublic = !isPublic;
    onShareToggle(variant.variant_id);
    setShareToast(makingPublic ? 'public' : 'private');
    clearTimeout(shareToastTimer.current);
    shareToastTimer.current = setTimeout(() => setShareToast(null), 3000);
  };

  const handleInstagram = async () => {
    try {
      const response = await fetch(variant.mp3_url);
      const blob = await response.blob();
      const safeTitle = (title || 'song').replace(/[^a-z0-9]/gi, '-').toLowerCase();
      const file = new File([blob], `${safeTitle}.mp3`, { type: 'audio/mpeg' });

      // Web Share API on mobile opens the native share sheet (Instagram, etc).
      if (navigator.canShare && navigator.canShare({ files: [file] })) {
        await navigator.share({
          files: [file],
          title: title || 'My Zeus Beats track',
          text: 'Made with Zeus Beats — zeusbeats.com 🎵⚡',
        });
      } else {
        // Desktop / unsupported browsers — open Instagram in a new tab.
        window.open('https://www.instagram.com/', '_blank');
        setIgToast('Open Instagram and share manually');
        setTimeout(() => setIgToast(''), 5000);
      }
    } catch (e) {
      if (e.name !== 'AbortError') {
        setIgToast('Error sharing');
        setTimeout(() => setIgToast(''), 4000);
      }
    }
  };

  const dur = variant.duration_seconds;
  const durStr = dur ? `${Math.floor(dur / 60)}:${String(dur % 60).padStart(2, '0')}` : '';
  const isFailed = variant.status === 'failed';
  const safeFilename = `${(title || 'song').replace(/[^a-z0-9]/gi, '-').toLowerCase()}.mp3`;
  const displayMusicVideoUrl = !isFreeTier && musicVideoUrl;   // existing videos still play

  const avatarStyle = { ...actionBtnStyle, color: '#a78bfa', borderColor: 'rgba(167,139,250,0.55)' };
  let avatarBtn;
  if (!didPlanOk) {
    avatarBtn = (
      <button onClick={() => onUpgrade('avatar')} style={avatarStyle}>
        {t('songs.buttons.avatar')}
      </button>
    );
  } else if (!isAdmin && videoCredits === 0) {
    avatarBtn = (
      <button onClick={() => showLocked('no-avatar-credits')} style={avatarStyle}>
        {t('songs.buttons.avatar')}
      </button>
    );
  } else if (didSt === 'processing') {
    avatarBtn = (
      <button disabled style={{ ...avatarStyle, opacity: 0.55, cursor: 'default' }}>
        {t('songs.buttons.avatarMaking')}
      </button>
    );
  } else if (didSt === 'done' && videoUrl) {
    avatarBtn = (
      <button onClick={() => onAvatarClick(variant, title)} style={avatarStyle}>
        {t('songs.buttons.avatarRedo')}
      </button>
    );
  } else {
    avatarBtn = (
      <button onClick={() => onAvatarClick(variant, title)} style={{ ...avatarStyle, color: didSt === 'error' ? '#f87171' : '#a78bfa' }}>
        {didSt === 'error' ? t('songs.buttons.avatarRetry') : t('songs.buttons.avatar')}
      </button>
    );
  }

  const ytStyle = { ...actionBtnStyle, color: '#ff4444', borderColor: 'rgba(255,68,68,0.5)' };
  let ytBtn;
  if (!canYouTube) {
    ytBtn = (
      <button onClick={() => onUpgrade('youtube')} style={ytStyle}>
        {t('songs.buttons.youtube')}
      </button>
    );
  } else if (ytSt === 'done') {
    ytBtn = (
      <button style={{ ...ytStyle, color: '#4ade80', borderColor: 'rgba(74,222,128,0.55)', opacity: 0.6, cursor: 'default', pointerEvents: 'none' }}>
        ✓ Uploaded
      </button>
    );
  } else if (ytSt === 'uploading') {
    ytBtn = (
      <button disabled style={{ ...ytStyle, opacity: 0.55, cursor: 'default' }}>
        {t('songs.buttons.uploading')}
      </button>
    );
  } else if (!ytConnected) {
    ytBtn = (
      <button onClick={() => onYouTubeClick(variant, title)} style={ytStyle}>
        {t('songs.buttons.connectYT')}
      </button>
    );
  } else {
    ytBtn = (
      <button onClick={() => onYouTubeClick(variant, title)} style={{ ...ytStyle, color: ytSt === 'error' ? '#f87171' : '#ff4444' }}>
        {ytSt === 'error' ? t('songs.buttons.retryYT') : t('songs.buttons.youtube')}
      </button>
    );
  }

  return (
    <div className="song-card-anim" style={isFailed ? { ...S.card, border: '1px solid rgba(248,113,113,0.25)', background: '#180e0e' } : S.card}>
      <div style={{ position: 'relative' }}>
        {displayMusicVideoUrl && !videoErr ? (
          <video
            src={displayMusicVideoUrl}
            autoPlay
            muted
            loop
            playsInline
            className="cover-video"
            style={S.artBox}
            onError={(e) => { console.error('[MusicVideo] load error for variant', variant.variant_id, displayMusicVideoUrl, e.nativeEvent); setVideoErr(true); }}
          />
        ) : variant.image_url ? (
          <img src={variant.image_url} alt={title} style={S.artBox} className="cover-ken-burns" />
        ) : (
          <div style={{ ...S.artBox, ...S.artPlaceholder }}>
            <span style={{ fontSize: 40, opacity: 0.2 }}>♫</span>
          </div>
        )}
        {isFreeTier && variant.image_url && (
          <a
            href="#pricing"
            style={{
              position: 'absolute', bottom: 6, left: '50%', transform: 'translateX(-50%)',
              display: 'inline-block',
              background: 'rgba(0,0,0,0.78)',
              border: '1px solid rgba(255,0,153,0.4)',
              borderRadius: 20,
              padding: '3px 10px',
              fontSize: 11,
              fontWeight: 600,
              color: '#ff0099',
              textDecoration: 'none',
              whiteSpace: 'nowrap',
              letterSpacing: '0.02em',
            }}
          >🎬 Upgrade for HD Video Animation</a>
        )}
        {!isFailed && (
          <button
            onClick={onPlayOffline || handlePlay}
            style={{
              position: 'absolute', bottom: 8, left: 8,
              transform: 'none',
              width: 40, height: 40, borderRadius: '50%',
              border: '1.5px solid rgba(255,255,255,0.7)',
              background: playing ? 'rgba(124,58,237,0.85)' : 'rgba(0,0,0,0.6)',
              color: '#fff', fontSize: 16,
              cursor: (wsReady || !!onPlayOffline) ? 'pointer' : 'default',
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              backdropFilter: 'blur(6px)',
              opacity: (wsReady || !!onPlayOffline) ? 1 : 0.4,
              transition: 'all 0.2s',
              pointerEvents: (wsReady || !!onPlayOffline) ? 'auto' : 'none',
              flexShrink: 0,
            }}
            onMouseEnter={(e) => { if (wsReady || !!onPlayOffline) e.currentTarget.style.boxShadow = '0 0 10px rgba(0,240,255,0.6)'; }}
            onMouseLeave={(e) => { e.currentTarget.style.boxShadow = 'none'; }}
          >
            {playing ? '⏸' : '▶'}
          </button>
        )}
        {!isFailed && hasLyrics && (
          <button
            onClick={() => setShowLyrics(true)}
            aria-label="Show lyrics"
            title="Lyrics"
            style={{
              position: 'absolute', bottom: 8, left: 56,
              width: 40, height: 40, borderRadius: '50%',
              border: '1.5px solid rgba(255,255,255,0.7)',
              background: 'rgba(0,0,0,0.6)',
              color: '#fff', fontSize: 16,
              cursor: 'pointer',
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              backdropFilter: 'blur(6px)',
              transition: 'all 0.2s',
              flexShrink: 0,
            }}
            onMouseEnter={(e) => { e.currentTarget.style.boxShadow = '0 0 10px rgba(0,240,255,0.6)'; }}
            onMouseLeave={(e) => { e.currentTarget.style.boxShadow = 'none'; }}
          >📜</button>
        )}
        {showLyrics && hasLyrics && (
          <LyricsModal lyricId={effectiveLyricId} title={title} onClose={() => setShowLyrics(false)} />
        )}
        <button
          className="fav-star-btn"
          onClick={handleFavToggle}
          style={{
            position: 'absolute', top: 8, right: 8,
            width: 30, height: 30, borderRadius: '50%',
            background: 'rgba(0,0,0,0.6)', border: 'none', cursor: 'pointer',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            fontSize: 16, backdropFilter: 'blur(4px)', transition: 'transform 0.15s',
            color: isFavourite ? '#fbbf24' : 'rgba(255,255,255,0.8)',
          }}
          title={isFavourite ? t('songs.buttons.removeFavourite') : t('songs.buttons.addFavourite')}
        >
          {isFavourite ? '★' : '☆'}
        </button>
        {favToast && (
          <div style={{
            position: 'absolute', top: 44, right: 8,
            background: 'rgba(0,0,0,0.88)', borderRadius: 6,
            color: favToast === 'added' ? '#4ade80' : '#aaa',
            fontSize: 11, padding: '4px 9px', pointerEvents: 'none',
            whiteSpace: 'nowrap', zIndex: 10,
            border: `1px solid ${favToast === 'added' ? 'rgba(74,222,128,0.25)' : 'rgba(255,255,255,0.1)'}`,
            animation: 'favToastFade 2.5s forwards',
          }}>
            {favToast === 'added' ? t('songs.buttons.savedFavourite') : t('songs.buttons.removedFavourite')}
          </div>
        )}
      </div>

      {videoUrl && (
        <video
          src={`${BACKEND_URL}${videoUrl}`}
          controls
          playsInline
          style={{ width: '100%', display: 'block', background: '#000', maxHeight: 180 }}
        />
      )}

      <div style={S.cardBody}>
        {isFailed ? (
          <div style={{ padding: '8px 0 4px', display: 'flex', alignItems: 'center', gap: 8 }}>
            <span style={{ color: '#f87171', fontSize: 13, fontWeight: 600 }}>Generation failed ❌</span>
          </div>
        ) : (
          <div ref={waveRef} style={{ flex: 1, height: 32, opacity: wsReady ? 1 : 0.15, transition: 'opacity 0.4s', minWidth: 0, marginBottom: 8 }} />
        )}
        <div style={{ ...S.cardTitle, fontSize: 15, fontWeight: 700 }}>{title || `Song #${variant.variant_id}`}</div>
        {artistName && <div style={{ fontSize: 11, color: '#a78bfa', marginTop: 2, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{artistName}</div>}
        <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginTop: 6 }}>
          <span style={{ ...S.pill, color: genreColor(variant.genre_tag), borderColor: genreColor(variant.genre_tag) + '55', background: genreColor(variant.genre_tag) + '14' }}>{gLabel(variant.genre_tag)}</span>
          {durStr && <span style={{ color: '#999', fontSize: 12 }}>{durStr}</span>}
        </div>
        {isFailed && (
          <div style={{ marginTop: 12 }}>
            <button
              onClick={() => onDelete(variant.variant_id)}
              disabled={deleting}
              style={{
                width: '100%', padding: '8px 0', borderRadius: 6,
                border: '1px solid rgba(248,113,113,0.5)',
                background: deleting ? 'rgba(0,0,0,0.2)' : 'rgba(248,113,113,0.06)',
                color: deleting ? '#888' : '#f87171',
                fontSize: 12, fontWeight: 600,
                cursor: deleting ? 'default' : 'pointer',
                transition: 'all 0.15s',
              }}
            >
              {deleting ? 'Deleting…' : '🗑 Delete'}
            </button>
          </div>
        )}
        {!isFailed && variant.mp3_url && (
          <>
            {/* Row 1: Download — full width primary */}
            <div style={{ marginTop: 10 }}>
              <a
                className="dl-btn"
                href={variant.mp3_url}
                download={safeFilename}
                onClick={() => setDownloaded(true)}
                style={{
                  display: 'flex', alignItems: 'center', justifyContent: 'center',
                  width: '100%', minHeight: 44, borderRadius: 7, border: 'none',
                  background: downloaded ? 'rgba(74,222,128,0.15)' : 'linear-gradient(135deg, #7c3aed 0%, #a855f7 100%)',
                  color: downloaded ? '#4ade80' : '#fff', fontSize: 12, fontWeight: 600,
                  cursor: downloaded ? 'default' : 'pointer',
                  textDecoration: 'none', boxSizing: 'border-box',
                  transition: 'all 0.2s ease', pointerEvents: downloaded ? 'none' : 'auto',
                  border: downloaded ? '1px solid rgba(74,222,128,0.35)' : 'none',
                }}
              >
                {downloaded ? '✓ Downloaded' : t('songs.buttons.download')}
              </a>
            </div>
            {/* Row 1.5: Save for offline */}
            <div style={{ marginTop: 8 }}>
              <button
                onClick={isSaved ? onRemoveSaved : onSaveOffline}
                disabled={isDownloading}
                style={{
                  ...actionBtnStyle,
                  width:       '100%',
                  color:       isSaved ? '#4ade80' : '#a78bfa',
                  borderColor: isSaved ? 'rgba(74,222,128,0.5)' : 'rgba(167,139,250,0.5)',
                  opacity:     isDownloading ? 0.6 : 1,
                  cursor:      isDownloading ? 'default' : 'pointer',
                }}
              >
                {isDownloading ? '⬇ Saving…' : isSaved ? '✓ Saved Offline' : '⬇ Save Offline'}
              </button>
            </div>
            {/* Row 2: Share + Telegram */}
            <div style={{ display: 'flex', gap: 8, marginTop: 8 }}>
              <button onClick={handleShare} style={{ ...actionBtnStyle, flex: 1, color: '#38bdf8', borderColor: 'rgba(56,189,248,0.55)' }}>
                {copied ? t('songs.buttons.copied') : t('songs.buttons.share')}
              </button>
              <button
                onClick={handleTelegram}
                disabled={tgPosting}
                style={{ ...actionBtnStyle, flex: 1, color: tgPosted ? '#4ade80' : '#00aaff', borderColor: tgPosted ? 'rgba(74,222,128,0.55)' : 'rgba(0,170,255,0.55)', opacity: tgPosted ? 0.6 : 1, pointerEvents: tgPosted ? 'none' : 'auto', cursor: tgPosted ? 'default' : 'pointer' }}
              >
                {tgPosting ? '…' : tgPosted ? t('songs.buttons.telegramPosted') : '✈ Telegram'}
              </button>
            </div>
            {/* Row 2.5: Instagram */}
            <div style={{ marginTop: 8 }}>
              <button
                onClick={handleInstagram}
                style={{
                  ...actionBtnStyle,
                  width: '100%',
                  background: 'linear-gradient(90deg, #833ab4 0%, #fd1d1d 50%, #fcb045 100%)',
                  border: 'none',
                  color: '#fff',
                  fontWeight: 600,
                }}
              >
                📸 Share to Instagram
              </button>
              {igToast && (
                <p style={{ color: '#fcb045', fontSize: 11, marginTop: 4, marginBottom: 0, textAlign: 'center', lineHeight: 1.4 }}>
                  {igToast}
                </p>
              )}
            </div>
            {/* Row 2.6: Discover share toggle */}
            <div style={{ marginTop: 8 }}>
              <button
                onClick={handleSharePublicToggle}
                style={{
                  ...actionBtnStyle,
                  width: '100%',
                  minHeight: 48,
                  background: 'linear-gradient(135deg, #00f0ff, #ff0099)',
                  color: '#000',
                  border: 'none',
                  fontWeight: 700,
                  boxShadow: '0 0 15px rgba(0,240,255,0.5)',
                  opacity: isPublic ? 1 : 0.82,
                }}
              >
                {isPublic ? '🌐 Shared on Discover ✓' : '🌐 Share on Discover'}
              </button>
              {shareToast && (
                <p style={{ color: shareToast === 'public' ? '#00f0ff' : '#9ca3af', fontSize: 11, marginTop: 4, marginBottom: 0, textAlign: 'center' }}>
                  {shareToast === 'public' ? 'Now visible on the Discover feed ✓' : 'Removed from Discover feed'}
                </p>
              )}
            </div>
            {/* Row 3: YouTube + Avatar */}
            <div style={{ display: 'flex', gap: 8, marginTop: 8 }}>
              {ytBtn}
              {avatarBtn}
            </div>
            {ytSt === 'error' && ytError && (
              <p style={{ color: '#f87171', fontSize: 11, marginTop: 4, marginBottom: 0, wordBreak: 'break-word' }}>{ytError}</p>
            )}
            {/* Row 4: Remake + Regen */}
            <div style={{ display: 'flex', gap: 8, marginTop: 8 }}>
              <button onClick={() => onRemake(variant.variant_id, title)} style={{ ...actionBtnStyle, flex: 1, color: '#f59e0b', borderColor: 'rgba(245,158,11,0.5)' }}>
                {t('songs.buttons.remake')}
              </button>
              <button
                onClick={handleRegen}
                disabled={regenLoading}
                style={{ ...actionBtnStyle, flex: 1, color: '#4ade80', borderColor: 'rgba(74,222,128,0.5)', opacity: regenLoading ? 0.55 : 1 }}
              >
                {regenLoading ? '…' : t('songs.buttons.regenerate')}
              </button>
            </div>
            {/* Stems panel */}
            {variant.mp3_url && (() => {
              const st = stemsProp?.stems_status;
              if (st === 'complete') {
                return (
                  <div style={{ marginTop: 8 }}>
                    <button
                      onClick={() => setStemsOpen(o => !o)}
                      style={{ ...actionBtnStyle, width: '100%', color: '#a78bfa', borderColor: 'rgba(167,139,250,0.5)' }}
                    >
                      🎵 Stems {stemsOpen ? '▲' : '▼'}
                    </button>
                    {stemsOpen && (
                      <div style={{ marginTop: 8, background: 'rgba(167,139,250,0.05)', borderRadius: 8, border: '1px solid rgba(167,139,250,0.15)', overflow: 'hidden' }}>
                        {[
                          { label: '🎤 Vocals',       url: stemsProp.stems_vocals_url },
                          { label: '🥁 Drums',        url: stemsProp.stems_drums_url },
                          { label: '🎸 Bass',         url: stemsProp.stems_bass_url },
                          { label: '🎹 Melody/Other', url: stemsProp.stems_other_url },
                        ].map(({ label, url }) => (
                          <div key={label} style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '8px 12px', borderBottom: '1px solid rgba(255,255,255,0.04)' }}>
                            <span style={{ fontSize: 12, color: '#c4b5fd', width: 100, flexShrink: 0 }}>{label}</span>
                            {url ? (
                              <>
                                <audio controls src={url} style={{ flex: 1, height: 28, minWidth: 0 }} />
                                <a href={url} download style={{ color: '#a78bfa', fontSize: 18, textDecoration: 'none', flexShrink: 0 }} title="Download">⬇</a>
                              </>
                            ) : (
                              <span style={{ color: '#cccccc', fontSize: 12 }}>unavailable</span>
                            )}
                          </div>
                        ))}
                        <div style={{ padding: '10px 12px' }}>
                          <button
                            onClick={() => onOpenCover(variant.variant_id, title)}
                            style={{ width: '100%', padding: '9px 0', borderRadius: 7, border: '1px solid rgba(0,240,255,0.4)', background: 'rgba(0,240,255,0.06)', color: '#00f0ff', fontSize: 12, fontWeight: 700, cursor: 'pointer' }}
                          >
                            🎤 Cover This Song
                          </button>
                        </div>
                      </div>
                    )}
                  </div>
                );
              }
              if (st === 'pending') {
                return (
                  <div style={{ marginTop: 8, padding: '8px 12px', borderRadius: 7, background: 'rgba(167,139,250,0.06)', border: '1px solid rgba(167,139,250,0.2)', color: '#a78bfa', fontSize: 12, textAlign: 'center' }}>
                    ⏳ Separating stems… (check back in a minute)
                  </div>
                );
              }
              if (st === 'failed') {
                return (
                  <div style={{ marginTop: 8, padding: '8px 12px', borderRadius: 7, background: 'rgba(248,113,113,0.06)', border: '1px solid rgba(248,113,113,0.2)', color: '#f87171', fontSize: 12, textAlign: 'center' }}>
                    Stems failed — 1 premium credit refunded
                  </div>
                );
              }
              // No stems yet — show Get Stems button
              return (
                <div style={{ marginTop: 8 }}>
                  <button
                    onClick={() => premiumCredits > 0 ? onGetStems(variant.variant_id) : onUpgrade('stems')}
                    title={premiumCredits === 0 ? 'Unlock stem separation' : 'Separate into vocals, drums, bass, melody (costs 1 premium credit)'}
                    style={{
                      ...actionBtnStyle, width: '100%',
                      color: premiumCredits > 0 ? '#a78bfa' : '#7c6fb0',
                      borderColor: premiumCredits > 0 ? 'rgba(167,139,250,0.4)' : 'rgba(167,139,250,0.18)',
                      opacity: premiumCredits === 0 ? 0.8 : 1,
                      cursor: 'pointer',
                    }}
                  >
                    🎵 Get Stems {premiumCredits === 0 ? '(0 credits)' : '(1 credit)'}
                  </button>
                </div>
              );
            })()}
            {/* Preview — opens the real public share page, exactly as a visitor/QR-scanner would see it */}
            {variant.mp3_url && (
              <div style={{ marginTop: 8 }}>
                <button
                  onClick={() => window.open(shareUrlForQr, '_blank', 'noopener,noreferrer')}
                  style={{ ...actionBtnStyle, width: '100%', color: '#4ade80', borderColor: 'rgba(74,222,128,0.5)' }}
                >
                  👁 Preview
                </button>
              </div>
            )}
            {/* QR code panel */}
            {variant.mp3_url && (
              <div style={{ marginTop: 8 }}>
                <button
                  onClick={() => setQrOpen(o => !o)}
                  style={{ ...actionBtnStyle, width: '100%', color: '#00f0ff', borderColor: 'rgba(0,240,255,0.5)' }}
                >
                  📱 Create QR Code {qrOpen ? '▲' : '▼'}
                </button>
                {qrOpen && (
                  <div style={{ marginTop: 8, padding: '16px 12px', background: 'rgba(0,240,255,0.05)', borderRadius: 8, border: '1px solid rgba(0,240,255,0.15)', display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 12 }}>
                    <div ref={qrSvgWrapRef} style={{ padding: 10, background: '#ffffff', borderRadius: 10, lineHeight: 0 }}>
                      <QRCodeSVG value={shareUrlForQr} size={160} bgColor="#ffffff" fgColor="#0b0b14" level="H" includeMargin={false} />
                    </div>
                    {/* Hidden — same value, rendered off-screen purely so a real <canvas> exists to export as PNG */}
                    <div ref={qrCanvasWrapRef} style={{ width: 0, height: 0, overflow: 'hidden' }}>
                      <QRCodeCanvas value={shareUrlForQr} size={512} bgColor="#ffffff" fgColor="#0b0b14" level="H" includeMargin={false} />
                    </div>
                    <div style={{ display: 'flex', gap: 8, width: '100%' }}>
                      <button onClick={() => handleQrDownload('png')} style={{ ...actionBtnStyle, flex: 1, color: '#00f0ff', borderColor: 'rgba(0,240,255,0.5)' }}>
                        ⬇ PNG
                      </button>
                      <button onClick={() => handleQrDownload('svg')} style={{ ...actionBtnStyle, flex: 1, color: '#00f0ff', borderColor: 'rgba(0,240,255,0.5)' }}>
                        ⬇ SVG
                      </button>
                    </div>
                    <p style={{ fontSize: 11, color: '#999', textAlign: 'center', lineHeight: 1.5, margin: 0 }}>
                      This QR code stays live as long as you keep this song in your account. If you delete the song, the QR will stop working. Your downloaded song file is always yours to keep.
                    </p>
                  </div>
                )}
              </div>
            )}
            {/* Photos panel */}
            {variant.mp3_url && (
              <div style={{ marginTop: 8 }}>
                <button
                  onClick={togglePhotosPanel}
                  style={{ ...actionBtnStyle, width: '100%', color: '#fbbf24', borderColor: 'rgba(251,191,36,0.5)' }}
                >
                  📷 Add Photos {photoList.length > 0 ? `(${photoList.length}/5)` : ''} {photosOpen ? '▲' : '▼'}
                </button>
                {photosOpen && (
                  <div style={{ marginTop: 8, padding: '14px 12px', background: 'rgba(251,191,36,0.05)', borderRadius: 8, border: '1px solid rgba(251,191,36,0.2)' }}>
                    {/* Unmissable privacy warning — not fine print */}
                    <div style={{
                      background: 'rgba(248,113,113,0.12)', border: '1px solid rgba(248,113,113,0.4)',
                      borderRadius: 8, padding: '10px 12px', marginBottom: 12,
                    }}>
                      <p style={{ margin: 0, fontSize: 12, fontWeight: 700, color: '#f87171', lineHeight: 1.5 }}>
                        ⚠ Anyone you share this QR code or link with will be able to see these photos.
                      </p>
                      <p style={{ margin: '4px 0 0', fontSize: 12, color: '#f87171', lineHeight: 1.5 }}>
                        Only add photos you're happy to share this way.
                      </p>
                    </div>

                    <label style={{ display: 'flex', alignItems: 'flex-start', gap: 8, marginBottom: 12, cursor: 'pointer' }}>
                      <input
                        type="checkbox"
                        checked={photoPrivacyChecked}
                        onChange={(e) => { setPhotoPrivacyChecked(e.target.checked); setPhotoError(''); }}
                        style={{ marginTop: 2, flexShrink: 0 }}
                      />
                      <span style={{ fontSize: 12, color: '#e2e8f0', lineHeight: 1.4 }}>
                        I understand anyone with the link can see these
                      </span>
                    </label>

                    {photoList.length > 0 && (
                      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 6, marginBottom: 12 }}>
                        {photoList.map((p) => {
                          const isCover = variant.cover_photo_id === p.photo_id;
                          return (
                            <div key={p.photo_id} style={{ position: 'relative' }}>
                              <img
                                src={p.url}
                                alt=""
                                style={{
                                  width: '100%', aspectRatio: '1 / 1', objectFit: 'cover', borderRadius: 6, display: 'block',
                                  outline: isCover ? '2px solid #fbbf24' : 'none', outlineOffset: -2,
                                }}
                              />
                              <button
                                onClick={() => onDeletePhoto(variant.variant_id, p.photo_id)}
                                title="Remove photo"
                                style={{
                                  position: 'absolute', top: 2, right: 2, width: 20, height: 20, borderRadius: '50%',
                                  border: 'none', background: 'rgba(0,0,0,0.75)', color: '#f87171', fontSize: 12,
                                  cursor: 'pointer', display: 'flex', alignItems: 'center', justifyContent: 'center', lineHeight: 1,
                                }}
                              >
                                ✕
                              </button>
                              <button
                                onClick={() => handleToggleCoverPhoto(p.photo_id)}
                                disabled={coverSavingId === p.photo_id}
                                title={isCover ? 'Stop using as cover (switch back to AI art)' : 'Use as cover image'}
                                style={{
                                  position: 'absolute', bottom: 2, left: 2, right: 2, padding: '3px 0', borderRadius: 5,
                                  border: 'none', fontSize: 9, fontWeight: 700, cursor: 'pointer', lineHeight: 1.4,
                                  background: isCover ? '#fbbf24' : 'rgba(0,0,0,0.75)',
                                  color: isCover ? '#1a1a1a' : '#fbbf24',
                                  opacity: coverSavingId === p.photo_id ? 0.5 : 1,
                                }}
                              >
                                {coverSavingId === p.photo_id ? '…' : isCover ? '★ Cover' : 'Use as cover'}
                              </button>
                            </div>
                          );
                        })}
                      </div>
                    )}

                    <input
                      ref={photoInputRef}
                      type="file"
                      accept="image/*"
                      multiple
                      onChange={handlePhotoFilesSelected}
                      style={{ display: 'none' }}
                    />
                    <button
                      onClick={() => photoInputRef.current?.click()}
                      disabled={photoUploading || photoList.length >= 5}
                      style={{
                        ...actionBtnStyle, width: '100%', color: '#fbbf24', borderColor: 'rgba(251,191,36,0.5)',
                        opacity: (photoUploading || photoList.length >= 5) ? 0.5 : 1,
                        cursor: (photoUploading || photoList.length >= 5) ? 'default' : 'pointer',
                      }}
                    >
                      {photoUploading ? 'Uploading…' : photoList.length >= 5 ? 'Maximum 5 photos reached' : '📷 Choose Photos'}
                    </button>
                    {photoError && (
                      <p style={{ fontSize: 11, color: '#f87171', marginTop: 8, marginBottom: 0, lineHeight: 1.4 }}>{photoError}</p>
                    )}
                    {variant.qr_generated && photoList.length > 0 && (
                      <p style={{ fontSize: 11, color: '#999', marginTop: 8, marginBottom: 0, lineHeight: 1.4 }}>
                        Note: a QR code made before these photos were added won't show them — create a new QR to include them.
                      </p>
                    )}
                  </div>
                )}
              </div>
            )}
            {/* Occasion panel — changes the share page's heading/tone, not the song itself */}
            {variant.mp3_url && (
              <div style={{ marginTop: 8 }}>
                <button
                  onClick={toggleOccasionPanel}
                  style={{ ...actionBtnStyle, width: '100%', color: '#f472b6', borderColor: 'rgba(244,114,182,0.5)' }}
                >
                  🎀 Occasion {variant.occasion ? `(${OCCASION_OPTIONS.find(o => o.value === variant.occasion)?.label || variant.occasion})` : ''} {occasionOpen ? '▲' : '▼'}
                </button>
                {occasionOpen && (
                  <div style={{ marginTop: 8, padding: '14px 12px', background: 'rgba(244,114,182,0.05)', borderRadius: 8, border: '1px solid rgba(244,114,182,0.2)' }}>
                    <p style={{ margin: '0 0 10px', fontSize: 12, color: '#999', lineHeight: 1.5 }}>
                      Changes how the share page greets whoever opens the link — the song itself doesn't change.
                    </p>
                    <select
                      value={occasionDraft}
                      onChange={(e) => setOccasionDraft(e.target.value)}
                      style={{
                        width: '100%', padding: '9px 10px', borderRadius: 8, marginBottom: occasionDraft ? 10 : 0,
                        background: 'rgba(0,0,0,0.3)', color: '#e2e8f0', border: '1px solid rgba(244,114,182,0.3)', fontSize: 13,
                      }}
                    >
                      {OCCASION_OPTIONS.map(o => (
                        <option key={o.value} value={o.value}>{o.label}</option>
                      ))}
                    </select>
                    {occasionDraft && (
                      <input
                        type="text"
                        value={occasionNameDraft}
                        onChange={(e) => setOccasionNameDraft(e.target.value)}
                        placeholder={occasionDraft === 'memorial' ? 'Name(s) — e.g. Mary & Mike Rowle' : 'Name — e.g. Sarah'}
                        maxLength={80}
                        style={{
                          width: '100%', padding: '9px 10px', borderRadius: 8, marginBottom: 10, boxSizing: 'border-box',
                          background: 'rgba(0,0,0,0.3)', color: '#e2e8f0', border: '1px solid rgba(244,114,182,0.3)', fontSize: 13,
                        }}
                      />
                    )}
                    <button
                      onClick={handleSaveOccasion}
                      disabled={occasionSaving}
                      style={{
                        ...actionBtnStyle, width: '100%', color: '#f472b6', borderColor: 'rgba(244,114,182,0.5)',
                        opacity: occasionSaving ? 0.6 : 1, cursor: occasionSaving ? 'default' : 'pointer',
                      }}
                    >
                      {occasionSaving ? 'Saving…' : occasionSaved ? 'Saved ✓' : 'Save'}
                    </button>
                    {occasionError && (
                      <p style={{ fontSize: 11, color: '#f87171', marginTop: 8, marginBottom: 0, lineHeight: 1.4 }}>{occasionError}</p>
                    )}
                  </div>
                )}
              </div>
            )}
            {/* Lock My Sound */}
            {variant.mp3_url && (
              <div style={{ marginTop: 6 }}>
                {soundPersonaVariantId === variant.variant_id ? (
                  <div style={{ padding: '8px 12px', borderRadius: 8, border: '1px solid rgba(0,240,255,0.3)', background: 'rgba(0,240,255,0.06)', color: '#00f0ff', fontSize: 12, fontWeight: 700, textAlign: 'center' }}>
                    ✓ Your Sound
                  </div>
                ) : (
                  <button
                    onClick={() => onLockSound(variant, title)}
                    style={{ width: '100%', padding: '8px 0', borderRadius: 8, border: '1px solid rgba(255,255,255,0.15)', background: 'rgba(255,255,255,0.04)', color: 'rgba(255,255,255,0.7)', fontSize: 12, fontWeight: 600, cursor: 'pointer' }}
                  >
                    🔒 Lock My Sound
                  </button>
                )}
              </div>
            )}
            {/* Locked feature message */}
            {lockedMsg && (
              <div style={{
                marginTop: 8, padding: '8px 12px', borderRadius: 7,
                background: 'rgba(18,18,30,0.96)', border: '1px solid rgba(0,240,255,0.15)',
                fontSize: 11, color: '#c4b5fd', textAlign: 'center', lineHeight: 1.5,
              }}>
                {lockedMsg === 'upgrade-yt' && <>{t('songs.locked.upgradeYT')} {!isIOSWebView && <Link to="/billing" style={{ color: '#00f0ff', fontWeight: 600 }}>{t('songs.locked.upgradeLink')}</Link>}</>}
                {lockedMsg === 'connect-yt' && <>{t('songs.locked.connectYT')}</>}
                {lockedMsg === 'upgrade-avatar' && <>{t('songs.locked.upgradeAvatar')} {!isIOSWebView && <Link to="/billing" style={{ color: '#00f0ff', fontWeight: 600 }}>{t('songs.locked.upgradeLink')}</Link>}</>}
                {lockedMsg === 'no-avatar-credits' && <>{t('songs.locked.noAvatarCredits')} {!isIOSWebView && <Link to="/billing" style={{ color: '#00f0ff', fontWeight: 600 }}>{t('songs.locked.topUpLink')}</Link>}</>}
              </div>
            )}
            {/* Row 5: Add to Playlist + Delete */}
            {addToast && (
              <div style={{
                marginTop: 8, padding: '6px 12px', borderRadius: 6,
                background: 'rgba(0,240,255,0.08)', border: '1px solid rgba(0,240,255,0.25)',
                fontSize: 11, color: '#00f0ff', textAlign: 'center',
              }}>
                {addToast}
              </div>
            )}
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginTop: 10 }}>
              {/* Add to Playlist */}
              <div style={{ position: 'relative' }} ref={addMenuRef}>
                <button
                  onClick={() => setAddMenuOpen(o => !o)}
                  style={{
                    background: 'none', border: '1px solid rgba(0,240,255,0.35)', borderRadius: 5,
                    color: '#00f0ff', fontSize: 11, cursor: 'pointer', padding: '3px 10px',
                    transition: 'all 0.15s',
                  }}
                >
                  ➕ Playlist
                </button>
                {addMenuOpen && (
                  <div style={{
                    position: 'absolute', bottom: '110%', left: 0, zIndex: 200,
                    background: '#18182a', border: '1px solid rgba(0,240,255,0.2)', borderRadius: 8,
                    minWidth: 180, boxShadow: '0 8px 32px rgba(0,0,0,0.5)',
                    overflow: 'hidden',
                  }}>
                    {(!playlists || playlists.length === 0) ? (
                      <Link
                        to="/playlists"
                        onClick={() => setAddMenuOpen(false)}
                        style={{
                          display: 'block', padding: '10px 14px', fontSize: 12,
                          color: '#00f0ff', textDecoration: 'none',
                          background: 'none',
                        }}
                        onMouseEnter={e => e.currentTarget.style.background = 'rgba(0,240,255,0.06)'}
                        onMouseLeave={e => e.currentTarget.style.background = 'none'}
                      >
                        + Create your first playlist
                      </Link>
                    ) : (
                      <>
                        {playlists.map(pl => (
                          <button
                            key={pl.id}
                            onClick={() => handleAddToList(pl.id)}
                            style={{
                              display: 'block', width: '100%', textAlign: 'left',
                              background: 'none', border: 'none', borderBottom: '1px solid rgba(255,255,255,0.05)',
                              color: '#e2e8f0', fontSize: 12, padding: '9px 14px', cursor: 'pointer',
                            }}
                            onMouseEnter={e => e.currentTarget.style.background = 'rgba(0,240,255,0.06)'}
                            onMouseLeave={e => e.currentTarget.style.background = 'none'}
                          >
                            {pl.name}
                          </button>
                        ))}
                        <Link
                          to="/playlists"
                          onClick={() => setAddMenuOpen(false)}
                          style={{
                            display: 'block', padding: '8px 14px', fontSize: 11,
                            color: '#00f0ff', textDecoration: 'none', borderTop: '1px solid rgba(0,240,255,0.1)',
                          }}
                          onMouseEnter={e => e.currentTarget.style.background = 'rgba(0,240,255,0.06)'}
                          onMouseLeave={e => e.currentTarget.style.background = 'none'}
                        >
                          Manage playlists →
                        </Link>
                      </>
                    )}
                  </div>
                )}
              </div>
              <button
                onClick={() => onDelete(variant.variant_id)}
                disabled={deleting}
                style={{
                  background: 'none', border: '1px solid rgba(248,113,113,0.5)', borderRadius: 5,
                  color: deleting ? '#888' : '#f87171',
                  fontSize: 11, cursor: deleting ? 'default' : 'pointer', padding: '3px 10px',
                  transition: 'color 0.15s',
                }}
              >
                {deleting ? t('songs.buttons.deleting') : t('songs.buttons.delete')}
              </button>
            </div>
          </>
        )}
      </div>
    </div>
  );
});

export default SongCard;
