import { useEffect, useRef, useState, useCallback } from 'react';
import { useParams, useNavigate, Link } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import { BACKEND_URL } from '../brand';
import { clipSeekTarget, clipInitialTime } from '../utils/clipPlayback';
import { getClipAnonId } from '../utils/clipAnonId';
import { saveRemixIntent } from '../utils/remixIntent';
import { readUtmAttribution } from '../utils/utmAttribution';
import { deriveClipHandle } from '../utils/clipHandle';
import RemixButton from '../components/RemixButton';
import ClipSongBar from '../components/ClipSongBar';
import ClipMoreMenu from '../components/ClipMoreMenu';
import ClipActionBtn from '../components/ClipActionBtn';
import { ZeusClipsWordmark, ClipsAiBadge } from '../components/ClipsBranding';

// Zeus Beats' own electric-blue → purple pair (see RemixButton.jsx).
const CYAN = '#00f0ff';
const PURPLE = '#7c3aed';

function setMetaTag(property, content, attr = 'property') {
  let el = document.querySelector(`meta[${attr}="${property}"]`);
  if (!el) { el = document.createElement('meta'); el.setAttribute(attr, property); document.head.appendChild(el); }
  el.setAttribute('content', content);
}
function removeMetaTag(property, attr = 'property') {
  const el = document.querySelector(`meta[${attr}="${property}"]`);
  if (el) el.remove();
}

export default function ClipPage() {
  const { clipId } = useParams();
  const navigate = useNavigate();
  const { token } = useAuth();
  const audioRef = useRef(null);
  const viewedRef = useRef(false);
  const progressBarRef = useRef(null);

  const [clip, setClip]         = useState(null);
  const [loading, setLoading]   = useState(true);
  const [notFound, setNotFound] = useState(false);
  const [playing, setPlaying]   = useState(false);
  const [copied, setCopied]     = useState(false);
  const [liked, setLiked]       = useState(false);
  const [likeCount, setLikeCount] = useState(0);

  useEffect(() => {
    setLoading(true);
    setNotFound(false);
    fetch(`${BACKEND_URL}/api/clips/${clipId}`)
      .then(r => { if (!r.ok) throw new Error('not found'); return r.json(); })
      .then(d => { setClip(d); setLikeCount(d.like_count || 0); })
      .catch(() => setNotFound(true))
      .finally(() => setLoading(false));
  }, [clipId]);

  /* ── OG meta tags ────────────────────────────────────────────────────── */
  useEffect(() => {
    if (!clip) return undefined;
    const title = `${clip.song_title || 'Untitled'} — Zeus Beats Clip`;
    const desc  = clip.caption || `Watch this clip and remix the sound — free at zeusbeats.com`;
    const pageUrl = `https://zeusbeats.com/clips/${clipId}`;
    const image = clip.media_type === 'cover' ? clip.song_cover_url : `${BACKEND_URL}${clip.media_url}`;

    document.title = title;
    setMetaTag('og:title', title);
    setMetaTag('og:description', desc);
    setMetaTag('og:url', pageUrl);
    setMetaTag('og:type', 'video.other');
    if (image) setMetaTag('og:image', image);
    setMetaTag('twitter:card', 'summary_large_image', 'name');
    setMetaTag('twitter:title', title, 'name');
    setMetaTag('twitter:description', desc, 'name');
    if (image) setMetaTag('twitter:image', image, 'name');

    return () => {
      document.title = 'Zeus Beats';
      ['og:title', 'og:description', 'og:url', 'og:type', 'og:image'].forEach(p => removeMetaTag(p));
      ['twitter:card', 'twitter:title', 'twitter:description', 'twitter:image'].forEach(p => removeMetaTag(p, 'name'));
    };
  }, [clip, clipId]);

  /* ── Log a view once the clip has loaded ────────────────────────────────── */
  useEffect(() => {
    if (!clip || viewedRef.current) return;
    viewedRef.current = true;
    fetch(`${BACKEND_URL}/api/clips/${clipId}/view`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', ...(token ? { Authorization: `Bearer ${token}` } : {}) },
      body: JSON.stringify({
        ...(token ? {} : { anon_id: getClipAnonId() }),
        ...(readUtmAttribution() || {}),
      }),
    }).catch(() => {});
  }, [clip, clipId, token]);

  /* ── Clamp playback to the clip window ──────────────────────────────────── */
  useEffect(() => {
    const a = audioRef.current;
    if (!a || !clip) return undefined;
    const onTime = () => {
      const target = clipSeekTarget(a.currentTime, clip.clip_start_time, clip.clip_duration);
      if (target !== null) a.currentTime = target;
      const bar = progressBarRef.current;
      if (bar && clip.clip_duration > 0) {
        const pct = Math.min(100, Math.max(0, ((a.currentTime - clip.clip_start_time) / clip.clip_duration) * 100));
        bar.style.width = `${pct}%`;
      }
    };
    const onEnded = () => { a.currentTime = clip.clip_start_time; a.play().catch(() => {}); };
    a.addEventListener('timeupdate', onTime);
    a.addEventListener('ended', onEnded);
    return () => {
      a.removeEventListener('timeupdate', onTime);
      a.removeEventListener('ended', onEnded);
    };
  }, [clip]);

  const togglePlay = () => {
    const a = audioRef.current;
    if (!a || !clip) return;
    if (playing) { a.pause(); setPlaying(false); }
    else {
      a.currentTime = clipInitialTime(clip.clip_start_time, clip.clip_duration);
      a.play().then(() => setPlaying(true)).catch(() => {});
    }
  };

  const handleCopy = async () => {
    const url = `https://zeusbeats.com/clips/${clipId}`;
    try {
      if (navigator.share) await navigator.share({ title: clip?.song_title || 'Zeus Beats', url });
      else await navigator.clipboard.writeText(url);
    } catch { /* share sheet dismissed / clipboard denied — not worth surfacing */ }
    setCopied(true);
    setTimeout(() => setCopied(false), 3000);
  };

  const handleLike = useCallback(async () => {
    if (!token) { navigate('/register'); return; }
    const was = liked;
    setLiked(!was);
    setLikeCount(c => Math.max(0, c + (was ? -1 : 1)));
    try {
      await fetch(`${BACKEND_URL}/api/clips/${clipId}/like`, was
        ? { method: 'DELETE', headers: { Authorization: `Bearer ${token}` } }
        : {
            method: 'POST',
            headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
            body: JSON.stringify(readUtmAttribution() || {}),
          });
    } catch {
      setLiked(was);
      setLikeCount(c => Math.max(0, c + (was ? 1 : -1)));
    }
  }, [token, liked, clipId, navigate]);

  const handleRemix = useCallback(() => {
    if (!token) {
      saveRemixIntent(clipId);
      navigate(`/register?remix=${clipId}`);
      return;
    }
    navigate(`/clips/${clipId}/remix`);
  }, [token, clipId, navigate]);

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
    <div style={{ background: '#000', height: '100svh', width: '100vw', overflow: 'hidden', position: 'relative' }}>
      <audio ref={audioRef} src={clip.mp3_url} onEnded={() => setPlaying(false)} />

      {/* The clip's own media fills the frame at full brightness, per the
          approved mockups — only the bottom gradient below dims for text. */}
      {clip.media_type === 'video' ? (
        <video
          src={visualUrl}
          autoPlay muted loop playsInline
          style={{ position: 'absolute', inset: 0, width: '100%', height: '100%', objectFit: 'cover' }}
        />
      ) : visualUrl ? (
        <img
          src={visualUrl}
          alt={clip.song_title}
          className="cover-ken-burns"
          style={{ position: 'absolute', inset: 0, width: '100%', height: '100%', objectFit: 'cover' }}
        />
      ) : (
        <div style={{ position: 'absolute', inset: 0, background: 'linear-gradient(135deg, #0d0d1a 0%, #1a0a2e 100%)' }} />
      )}

      {/* Scrims (2026-09-23 readability fix): dim only the header strip and the
          caption/stats/Remix-button strip, leaving the middle of the image
          untouched — see ClipsFeedPage.jsx's ClipSlide for the same pattern. */}
      <div style={{
        position: 'absolute', top: 0, left: 0, right: 0, height: '20%',
        background: 'linear-gradient(to bottom, rgba(0,0,0,0.6) 0%, transparent 100%)',
        pointerEvents: 'none',
      }} />
      <div style={{
        position: 'absolute', bottom: 0, left: 0, right: 0, height: '45%',
        background: 'linear-gradient(to top, rgba(0,0,0,0.75) 0%, transparent 100%)',
        pointerEvents: 'none',
      }} />

      {/* Header — wordmark centered, "All clips" + report menu at the edges,
          AI badge on its own row underneath (same shape as the feed header) */}
      <div style={{ position: 'absolute', top: 0, left: 0, right: 0, padding: '14px 18px 10px', zIndex: 20 }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
          <Link to="/clips" style={{ color: 'rgba(255,255,255,0.6)', textDecoration: 'none', fontSize: 13, fontWeight: 600, width: 60 }}>← Clips</Link>
          <ZeusClipsWordmark />
          <ClipMoreMenu clipId={clipId} token={token} onRequireAuth={() => navigate('/register')} />
        </div>
        <div style={{ display: 'flex', justifyContent: 'flex-end', marginTop: 8 }}>
          <ClipsAiBadge />
        </div>
      </div>

      {/* Centered play/pause — this page has no autoplay (reached via a direct
          link/share, not a scrolling feed), so it needs its own explicit control. */}
      <button
        onClick={togglePlay}
        aria-label={playing ? 'Pause' : 'Play'}
        style={{
          position: 'absolute', top: '50%', left: '50%', transform: 'translate(-50%, -50%)', zIndex: 15,
          width: 64, height: 64, borderRadius: '50%', border: `2px solid ${CYAN}`,
          background: playing ? `${CYAN}18` : 'rgba(0,0,0,0.45)', color: CYAN, fontSize: 22, cursor: 'pointer',
          display: 'flex', alignItems: 'center', justifyContent: 'center', boxShadow: `0 0 24px ${CYAN}44`,
          opacity: playing ? 0 : 1, transition: 'opacity 0.2s',
        }}
      >
        {playing ? '⏸' : '▶'}
      </button>

      {/* Right-side action column — like, remix count, share (same as the feed) */}
      <div style={{
        position: 'absolute', bottom: 232, right: 14, zIndex: 20,
        display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 16,
      }}>
        <ClipActionBtn onClick={handleLike} icon="❤️" label={String(likeCount)} active={liked} activeColor={PURPLE} />
        <ClipActionBtn icon="🔁" label={String(clip.remix_count)} />
        <ClipActionBtn onClick={handleCopy} icon={copied ? '✓' : '🔗'} label={copied ? 'Copied' : 'Share'} active={copied} activeColor={CYAN} />
      </div>

      <div style={{ position: 'absolute', bottom: 232, left: 24, right: 76, zIndex: 20 }}>
        {clip.genre_tag && (
          <span style={{
            display: 'inline-block', padding: '3px 12px', borderRadius: 20, fontSize: 11, fontWeight: 700,
            letterSpacing: '0.06em', textTransform: 'uppercase',
            background: `linear-gradient(90deg, ${CYAN}33, ${PURPLE}33)`, border: `1px solid ${CYAN}55`, color: CYAN, marginBottom: 10,
          }}>
            {clip.genre_tag}
          </span>
        )}
        <p style={{ margin: '0 0 4px', fontSize: 22, fontWeight: 800, color: '#fff', lineHeight: 1.2, textShadow: '0 2px 12px rgba(0,0,0,0.9)' }}>
          {clip.song_title || 'Untitled'}
        </p>
        <Link
          to={`/clips/u/${deriveClipHandle(clip.artist_name)}`}
          style={{ display: 'block', margin: '0 0 6px', fontSize: 14, color: 'rgba(255,255,255,0.7)', fontWeight: 600, textDecoration: 'none' }}
        >
          @{deriveClipHandle(clip.artist_name)}
        </Link>
        {clip.caption && (
          <p style={{ margin: 0, fontSize: 13, color: 'rgba(255,255,255,0.85)', lineHeight: 1.5, textShadow: '0 1px 4px rgba(0,0,0,0.85)' }}>{clip.caption}</p>
        )}
      </div>

      {/* ── "⚡ Remix This Sound" — the most prominent button on the page ── */}
      <div style={{ position: 'absolute', bottom: 96, left: 16, right: 16, zIndex: 20 }}>
        <RemixButton onClick={handleRemix} />
      </div>

      {/* Song bar — pinned at the very bottom, full width, with its progress strip */}
      <div style={{ position: 'absolute', bottom: 16, left: 16, right: 16, zIndex: 20 }}>
        <ClipSongBar
          coverUrl={clip.song_cover_url}
          title={clip.song_title}
          artistName={clip.artist_name}
          spinning={playing}
          onUseSound={handleRemix}
          progressBarRef={progressBarRef}
        />
      </div>
    </div>
  );
}
