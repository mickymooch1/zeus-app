import { useEffect, useRef, useState, useCallback } from 'react';
import { useParams, useNavigate, Link } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import { BACKEND_URL } from '../brand';
import { clipSeekTarget, clipInitialTime } from '../utils/clipPlayback';
import { getClipAnonId } from '../utils/clipAnonId';
import { saveRemixIntent } from '../utils/remixIntent';
import { readUtmAttribution } from '../utils/utmAttribution';
import RemixButton from '../components/RemixButton';
import ClipMoreMenu from '../components/ClipMoreMenu';

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

      <div style={{ position: 'absolute', inset: 0, background: 'linear-gradient(to top, rgba(0,0,0,0.95) 0%, rgba(0,0,0,0.3) 50%, transparent 75%)', pointerEvents: 'none' }} />

      <div style={{ position: 'absolute', top: 0, left: 0, right: 0, padding: '20px 24px', display: 'flex', alignItems: 'center', justifyContent: 'space-between', zIndex: 20 }}>
        <Link to="/" style={{ color: CYAN, textDecoration: 'none', fontSize: 17, fontWeight: 800, textShadow: `0 0 16px ${CYAN}88` }}>⚡ Zeus Beats</Link>
        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
          <Link to="/clips" style={{ color: 'rgba(255,255,255,0.5)', textDecoration: 'none', fontSize: 13, fontWeight: 600 }}>← All clips</Link>
          <ClipMoreMenu clipId={clipId} token={token} onRequireAuth={() => navigate('/register')} />
        </div>
      </div>

      <div style={{ position: 'absolute', bottom: 0, left: 0, right: 0, padding: '0 24px 40px', zIndex: 20 }}>
        {clip.genre_tag && (
          <span style={{
            display: 'inline-block', padding: '3px 12px', borderRadius: 20, fontSize: 11, fontWeight: 700,
            letterSpacing: '0.06em', textTransform: 'uppercase',
            background: `linear-gradient(90deg, ${CYAN}33, ${PURPLE}33)`, border: `1px solid ${CYAN}55`, color: CYAN, marginBottom: 10,
          }}>
            {clip.genre_tag}
          </span>
        )}
        <p style={{ margin: '0 0 4px', fontSize: 26, fontWeight: 800, color: '#fff', lineHeight: 1.2, textShadow: '0 2px 12px rgba(0,0,0,0.9)' }}>
          {clip.song_title || 'Untitled'}
        </p>
        <p style={{ margin: '0 0 6px', fontSize: 15, color: 'rgba(255,255,255,0.65)', fontWeight: 500 }}>
          @{(clip.artist_name || 'zeusbeats').replace(/\s+/g, '').toLowerCase()}
        </p>
        {clip.caption && (
          <p style={{ margin: '0 0 14px', fontSize: 14, color: 'rgba(255,255,255,0.8)', lineHeight: 1.5 }}>{clip.caption}</p>
        )}

        <div style={{ display: 'flex', gap: 10, alignItems: 'center', marginBottom: 18 }}>
          <button
            onClick={togglePlay}
            style={{
              width: 52, height: 52, borderRadius: '50%', border: `2px solid ${CYAN}`,
              background: playing ? `${CYAN}22` : 'rgba(0,0,0,0.6)', color: CYAN, fontSize: 18, cursor: 'pointer',
              display: 'flex', alignItems: 'center', justifyContent: 'center', boxShadow: `0 0 20px ${CYAN}44`, flexShrink: 0,
            }}
          >
            {playing ? '⏸' : '▶'}
          </button>
          <button
            onClick={handleLike}
            style={{
              padding: '13px 18px', borderRadius: 999, border: `1px solid ${liked ? PURPLE : 'rgba(255,255,255,0.2)'}`,
              background: liked ? `${PURPLE}22` : 'rgba(10,10,20,0.55)', color: liked ? '#c4b5fd' : 'rgba(255,255,255,0.8)',
              fontSize: 14, fontWeight: 700, cursor: 'pointer', backdropFilter: 'blur(8px)', WebkitBackdropFilter: 'blur(8px)',
            }}
          >
            ❤️ {likeCount > 0 ? likeCount : 'Like'}
          </button>
          <div style={{
            padding: '13px 16px', borderRadius: 999, border: '1px solid rgba(255,255,255,0.2)',
            background: 'rgba(10,10,20,0.55)', color: 'rgba(255,255,255,0.8)', fontSize: 14, fontWeight: 700,
            backdropFilter: 'blur(8px)', WebkitBackdropFilter: 'blur(8px)', flexShrink: 0,
          }}>
            🔁 {clip.remix_count}
          </div>
          <button
            onClick={handleCopy}
            style={{
              flex: 1, padding: '13px 0', borderRadius: 999, border: `1px solid ${copied ? CYAN : 'rgba(255,255,255,0.2)'}`,
              background: copied ? `${CYAN}15` : 'rgba(10,10,20,0.55)', color: copied ? CYAN : 'rgba(255,255,255,0.75)',
              fontSize: 13, fontWeight: 600, cursor: 'pointer', backdropFilter: 'blur(8px)', WebkitBackdropFilter: 'blur(8px)',
            }}
          >
            {copied ? '✓ Copied' : '🔗 Share'}
          </button>
        </div>

        {/* ── "⚡ Remix This Sound" — the most prominent button on the page, same
             pill/waveform style as the feed (RemixButton.jsx) ── */}
        <RemixButton onClick={handleRemix} />
      </div>
    </div>
  );
}
