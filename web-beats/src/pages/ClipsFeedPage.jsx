import { useState, useEffect, useRef, useCallback, memo } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import { BACKEND_URL } from '../brand';
import { clipSeekTarget, clipInitialTime } from '../utils/clipPlayback';
import { getClipAnonId } from '../utils/clipAnonId';
import { saveRemixIntent } from '../utils/remixIntent';
import { readUtmAttribution } from '../utils/utmAttribution';
import RemixButton from '../components/RemixButton';
import ClipSongBar from '../components/ClipSongBar';
import ClipMoreMenu from '../components/ClipMoreMenu';

/* ── Zeus Beats' own electric-blue → purple palette (App.jsx logo, NowPlayingBar,
 * PlaylistPage all use this pair already — not a new colour introduced here). ── */
const CYAN   = '#00f0ff';
const PURPLE = '#7c3aed';
const BG     = '#000';

/* ── One clip slide ─────────────────────────────────────────────────────────
 * A clip has its OWN media (cover/image/video) as the visual, and plays the
 * SOURCE SONG's mp3 clamped to clip_start_time..+clip_duration as the audio —
 * two separate media elements kept in sync. */
const ClipSlide = memo(function ClipSlide({
  clip, idx, isLiked, likeCount, isCopied, token,
  onLike, onShare, onRemix, onRequireAuth, onSlideRef, onVideoRef, onAudioRef,
}) {
  const { media_type, media_url, song_cover_url, song_title, artist_name, genre_tag,
          caption, clip_start_time, clip_duration, mp3_url, remix_count } = clip;

  const visualUrl = media_type === 'cover'
    ? song_cover_url
    : `${BACKEND_URL}${media_url}`;

  return (
    <div
      ref={onSlideRef}
      data-idx={idx}
      className="clip-slide"
      style={{
        position: 'relative', height: '100svh', width: '100%',
        scrollSnapAlign: 'start', overflow: 'hidden', background: '#0a0a14', flexShrink: 0,
      }}
    >
      {/* Visual background — the clip's own media (or the song's cover) fills the
          frame at full brightness, per the approved mockups; only the bottom
          gradient below dims for text legibility. The flat gradient is a
          genuine fallback (no image/video at all), never a stand-in for a
          slow-loading one. */}
      {media_type === 'video' ? (
        <video
          ref={onVideoRef}
          src={visualUrl}
          autoPlay muted loop playsInline
          className="clip-video"
          style={{ position: 'absolute', inset: 0, width: '100%', height: '100%', objectFit: 'cover' }}
        />
      ) : visualUrl ? (
        <img
          src={visualUrl}
          alt=""
          className="cover-ken-burns"
          style={{ position: 'absolute', inset: 0, width: '100%', height: '100%', objectFit: 'cover' }}
        />
      ) : (
        <div style={{ position: 'absolute', inset: 0, background: 'linear-gradient(135deg, #0d0d1a 0%, #1a0a2e 100%)' }} />
      )}

      {/* Hidden audio — the SOURCE SONG, clamped to the clip window by the parent's timeupdate handler */}
      <audio
        ref={el => { if (el) onAudioRef(el); }}
        src={mp3_url}
        loop={false}
        data-clip-start={clip_start_time}
        data-clip-duration={clip_duration}
        className="clip-audio"
        style={{ display: 'none' }}
      />

      <div style={{
        position: 'absolute', inset: 0,
        background: 'linear-gradient(to top, rgba(0,0,0,0.92) 0%, rgba(0,0,0,0.3) 45%, transparent 70%)',
        pointerEvents: 'none',
      }} />

      {/* Right-side action column — like, share, report (⋯) */}
      <div style={{
        position: 'absolute', bottom: 210, right: 14, zIndex: 10,
        display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 16,
      }}>
        <ClipActionBtn onClick={onLike} icon="❤️" label={String(likeCount)} active={isLiked} activeColor={PURPLE} />
        <ClipActionBtn icon="🔁" label={String(remix_count)} />
        <ClipActionBtn onClick={onShare} icon={isCopied ? '✓' : '🔗'} label={isCopied ? 'Copied' : 'Share'} active={isCopied} activeColor={CYAN} />
        <ClipMoreMenu clipId={clip.id} token={token} onRequireAuth={onRequireAuth} />
      </div>

      {/* Info — bottom left: @username + caption */}
      <div style={{ position: 'absolute', bottom: 210, left: 16, right: 76, zIndex: 10 }}>
        {genre_tag && (
          <span style={{
            display: 'inline-block', padding: '2px 10px', borderRadius: 20, fontSize: 11,
            fontWeight: 700, letterSpacing: '0.05em', textTransform: 'uppercase',
            background: `linear-gradient(90deg, ${CYAN}33, ${PURPLE}33)`, border: `1px solid ${CYAN}55`,
            color: CYAN, marginBottom: 8,
          }}>
            {genre_tag}
          </span>
        )}
        <p style={{ margin: '0 0 4px', fontSize: 15, fontWeight: 800, color: '#fff', textShadow: '0 2px 8px rgba(0,0,0,0.8)' }}>
          @{(artist_name || 'zeusbeats').replace(/\s+/g, '').toLowerCase()}
        </p>
        {caption && (
          <p style={{
            margin: 0, fontSize: 13, color: 'rgba(255,255,255,0.85)', lineHeight: 1.4,
            WebkitLineClamp: 2, display: '-webkit-box', WebkitBoxOrient: 'vertical', overflow: 'hidden',
          }}>
            {caption}
          </p>
        )}
      </div>

      {/* Song bar — cover art + title */}
      <div style={{ position: 'absolute', bottom: 158, left: 16, zIndex: 10 }}>
        <ClipSongBar coverUrl={song_cover_url} title={song_title} />
      </div>

      {/* ── "⚡ Remix This Sound" — the most prominent button on the page ── */}
      <div style={{ position: 'absolute', bottom: 24, left: 16, right: 16, zIndex: 10 }}>
        <RemixButton onClick={onRemix} />
      </div>
    </div>
  );
});

// onClick omitted renders a plain (non-interactive) stat — used for the remix
// count, which has nothing to do when tapped here (remixing lives on its own
// big button below, not in this column).
function ClipActionBtn({ onClick, icon, label, active, activeColor }) {
  const Tag = onClick ? 'button' : 'div';
  return (
    <Tag
      onClick={onClick}
      style={{
        background: 'none', border: 'none', cursor: onClick ? 'pointer' : 'default',
        display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 4, padding: 0,
      }}
    >
      <div style={{
        width: 44, height: 44, borderRadius: '50%',
        background: active ? `${activeColor}28` : 'rgba(10,10,20,0.55)',
        backdropFilter: 'blur(8px)', WebkitBackdropFilter: 'blur(8px)',
        border: `1.5px solid ${active ? activeColor : 'rgba(255,255,255,0.22)'}`,
        display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 18,
        boxShadow: active ? `0 0 20px ${activeColor}66` : 'none',
      }}>
        {icon}
      </div>
      {label && <span style={{ color: active ? activeColor : 'rgba(255,255,255,0.7)', fontSize: 11, fontWeight: 600 }}>{label}</span>}
    </Tag>
  );
}

/* ── Main page ──────────────────────────────────────────────────────────── */
export default function ClipsFeedPage() {
  const { token } = useAuth();
  const navigate = useNavigate();
  const [clips, setClips]     = useState([]);
  const [muted, setMuted]     = useState(true);
  const [liked, setLiked]     = useState(new Set());
  const [counts, setCounts]   = useState({});
  const [copied, setCopied]   = useState(null);
  const [loading, setLoading] = useState(false);
  const [hasMore, setHasMore] = useState(true);
  const [sort, setSort]       = useState('new'); // 'new' | 'trending'

  const pageRef            = useRef(0);
  const loadingRef         = useRef(false);
  const hasMoreRef         = useRef(true);
  const mutedRef           = useRef(true);
  const activeRef          = useRef(null);
  const viewedRef          = useRef(new Set()); // clip ids already POSTed a view this session
  const slideRefs          = useRef({});
  const videoRefs          = useRef({});
  const audioRefs          = useRef({});
  const scrollContainerRef = useRef(null);

  const fetchPage = useCallback(async (targetSort, reset) => {
    if (loadingRef.current || (!reset && !hasMoreRef.current)) return;
    loadingRef.current = true;
    setLoading(true);
    try {
      const p = reset ? 0 : pageRef.current;
      const r = await fetch(`${BACKEND_URL}/api/clips?sort=${targetSort}&page=${p}`);
      if (!r.ok) return;
      const d = await r.json();
      const c = d.clips || [];
      if (c.length < 20) { hasMoreRef.current = false; setHasMore(false); }
      else { hasMoreRef.current = true; setHasMore(true); }
      setClips(prev => (reset ? c : [...prev, ...c]));
      setCounts(prev => {
        const n = reset ? {} : { ...prev };
        c.forEach(x => { n[x.id] = x.like_count; });
        return n;
      });
      pageRef.current = p + 1;
    } catch (e) {
      console.error('clips feed:', e);
    } finally {
      loadingRef.current = false;
      setLoading(false);
    }
  }, []);

  useEffect(() => { fetchPage('new', true); }, [fetchPage]);

  const handleSortChange = (next) => {
    if (next === sort) return;
    setSort(next);
    activeRef.current = null;
    pageRef.current = 0;
    hasMoreRef.current = true;
    if (scrollContainerRef.current) scrollContainerRef.current.scrollTop = 0;
    fetchPage(next, true);
  };

  /* ── Autoplay + infinite scroll + view logging ──────────────────────────── */
  useEffect(() => {
    if (!clips.length) return undefined;

    const obs = new IntersectionObserver(entries => {
      entries.forEach(entry => {
        const idx = +entry.target.dataset.idx;
        const vid = videoRefs.current[idx];
        const aud = audioRefs.current[idx];
        const clip = clips[idx];

        if (entry.isIntersecting) {
          const prev = activeRef.current;
          if (prev !== null && prev !== idx) {
            videoRefs.current[prev]?.pause();
            const pa = audioRefs.current[prev];
            if (pa) pa.pause();
          }
          activeRef.current = idx;

          if (vid) { vid.muted = true; vid.play().catch(() => {}); }
          if (aud) {
            aud.currentTime = clipInitialTime(clip.clip_start_time, clip.clip_duration);
            aud.muted = mutedRef.current;
            if (!mutedRef.current) aud.play().catch(() => {});
          }

          if (clip && !viewedRef.current.has(clip.id)) {
            viewedRef.current.add(clip.id);
            fetch(`${BACKEND_URL}/api/clips/${clip.id}/view`, {
              method: 'POST',
              headers: {
                'Content-Type': 'application/json',
                ...(token ? { Authorization: `Bearer ${token}` } : {}),
              },
              body: JSON.stringify({
                ...(token ? {} : { anon_id: getClipAnonId() }),
                ...(readUtmAttribution() || {}),
              }),
            }).catch(() => {});
          }

          if (idx >= clips.length - 3) fetchPage(sort, false);
        } else {
          if (vid) vid.pause();
          if (aud) aud.pause();
        }
      });
    }, { threshold: 0.65 });

    Object.values(slideRefs.current).forEach(el => { if (el) obs.observe(el); });
    return () => obs.disconnect();
  }, [clips, sort, fetchPage, token]);

  /* ── Clamp each active audio element to its clip window ─────────────────────
   * Attaches the timeupdate/ended clamp once per element, reading clip_start/
   * clip_duration from its own data attributes (set on the <audio> above) so
   * this effect doesn't need to separately track which slide index owns which
   * element. */
  useEffect(() => {
    const cleanups = Object.values(audioRefs.current).filter(Boolean).map(aud => {
      const start = Number(aud.dataset.clipStart) || 0;
      const duration = Number(aud.dataset.clipDuration) || 0;
      const onTime = () => {
        const target = clipSeekTarget(aud.currentTime, start, duration);
        if (target !== null) aud.currentTime = target;
      };
      const onEnded = () => { aud.currentTime = start; aud.play().catch(() => {}); };
      aud.addEventListener('timeupdate', onTime);
      aud.addEventListener('ended', onEnded);
      return () => {
        aud.removeEventListener('timeupdate', onTime);
        aud.removeEventListener('ended', onEnded);
      };
    });
    return () => cleanups.forEach(fn => fn());
  }, [clips]);

  const toggleMute = () => {
    const nm = !mutedRef.current;
    mutedRef.current = nm;
    setMuted(nm);
    const idx = activeRef.current;
    if (idx !== null) {
      const aud = audioRefs.current[idx];
      if (aud) {
        aud.muted = nm;
        if (!nm) aud.play().catch(() => {});
      }
    }
  };

  const handleLike = useCallback(async (clipId) => {
    if (!token) { navigate('/register'); return; }
    const wasLiked = liked.has(clipId);
    setLiked(prev => { const n = new Set(prev); wasLiked ? n.delete(clipId) : n.add(clipId); return n; });
    setCounts(prev => ({ ...prev, [clipId]: Math.max(0, (prev[clipId] || 0) + (wasLiked ? -1 : 1)) }));
    try {
      // Unlike (DELETE) has no body — the endpoint doesn't log an event for it
      // (only "clip_liked" exists, not "clip_unliked"), so there's nothing to
      // attach attribution to on that path.
      await fetch(`${BACKEND_URL}/api/clips/${clipId}/like`, wasLiked
        ? { method: 'DELETE', headers: { Authorization: `Bearer ${token}` } }
        : {
            method: 'POST',
            headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
            body: JSON.stringify(readUtmAttribution() || {}),
          });
    } catch {
      setLiked(prev => { const n = new Set(prev); wasLiked ? n.add(clipId) : n.delete(clipId); return n; });
      setCounts(prev => ({ ...prev, [clipId]: Math.max(0, (prev[clipId] || 0) + (wasLiked ? 1 : -1)) }));
    }
  }, [token, liked, navigate]);

  const handleShare = useCallback(async (clipId) => {
    const url = `${window.location.origin}/clips/${clipId}`;
    try {
      if (navigator.share) await navigator.share({ title: 'Zeus Beats', url });
      else await navigator.clipboard.writeText(url);
    } catch { /* share sheet dismissed / clipboard denied — not worth surfacing */ }
    setCopied(clipId);
    setTimeout(() => setCopied(c => c === clipId ? null : c), 2000);
  }, []);

  const handleRemix = useCallback((clipId) => {
    if (!token) {
      saveRemixIntent(clipId);
      navigate(`/register?remix=${clipId}`);
      return;
    }
    navigate(`/clips/${clipId}/remix`);
  }, [token, navigate]);

  return (
    <div style={{ background: BG, height: '100svh', width: '100vw', overflow: 'hidden', position: 'relative' }}>
      {/* Fixed header */}
      <div style={{
        position: 'fixed', top: 0, left: 0, right: 0, zIndex: 200, padding: '12px 20px',
        display: 'flex', alignItems: 'center', justifyContent: 'space-between',
        background: 'linear-gradient(to bottom, rgba(0,0,0,0.85) 0%, transparent 100%)',
        pointerEvents: 'none',
      }}>
        <Link to="/" style={{ color: CYAN, textDecoration: 'none', fontSize: 17, fontWeight: 800, pointerEvents: 'auto', textShadow: `0 0 16px ${CYAN}88` }}>
          ⚡ Zeus Beats
        </Link>
        <button
          onClick={toggleMute}
          style={{
            background: muted ? 'rgba(255,255,255,0.08)' : `${CYAN}22`,
            border: `1px solid ${muted ? 'rgba(255,255,255,0.2)' : CYAN}`,
            borderRadius: 20, padding: '5px 14px', color: muted ? 'rgba(255,255,255,0.7)' : CYAN,
            cursor: 'pointer', fontSize: 13, fontWeight: 600, pointerEvents: 'auto',
          }}
        >
          {muted ? '🔇 Tap to hear' : '🔊 On'}
        </button>
      </div>

      {/* Pill-style New / Trending tabs */}
      <div style={{
        position: 'fixed', top: 56, left: 0, right: 0, zIndex: 199,
        display: 'flex', justifyContent: 'center', gap: 8, pointerEvents: 'auto',
      }}>
        {[['new', 'New'], ['trending', 'Trending']].map(([s, label]) => (
          <button
            key={s}
            onClick={() => handleSortChange(s)}
            style={{
              padding: '7px 20px', borderRadius: 999, fontSize: 13, fontWeight: 700, cursor: 'pointer',
              border: `1px solid ${sort === s ? 'transparent' : 'rgba(255,255,255,0.18)'}`,
              background: sort === s
                ? `linear-gradient(90deg, ${CYAN}, ${PURPLE})`
                : 'rgba(10,10,20,0.55)',
              color: sort === s ? '#000' : 'rgba(255,255,255,0.65)',
              backdropFilter: 'blur(8px)', WebkitBackdropFilter: 'blur(8px)',
              boxShadow: sort === s ? `0 0 18px ${CYAN}55` : 'none',
            }}
          >
            {label}
          </button>
        ))}
      </div>

      <div
        ref={scrollContainerRef}
        style={{ height: '100svh', overflowY: 'scroll', scrollSnapType: 'y mandatory', WebkitOverflowScrolling: 'touch' }}
      >
        {clips.map((clip, idx) => (
          <ClipSlide
            key={clip.id}
            clip={clip}
            idx={idx}
            token={token}
            isLiked={liked.has(clip.id)}
            likeCount={counts[clip.id] || 0}
            isCopied={copied === clip.id}
            onLike={() => handleLike(clip.id)}
            onShare={() => handleShare(clip.id)}
            onRemix={() => handleRemix(clip.id)}
            onRequireAuth={() => navigate('/register')}
            onSlideRef={el => { slideRefs.current[idx] = el; }}
            onVideoRef={el => { videoRefs.current[idx] = el; }}
            onAudioRef={el => { audioRefs.current[idx] = el; }}
          />
        ))}

        <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>

        {loading && (
          <div style={{ height: '100svh', scrollSnapAlign: 'start', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
            <div style={{ width: 36, height: 36, borderRadius: '50%', border: `3px solid ${CYAN}33`, borderTopColor: CYAN, animation: 'spin 0.8s linear infinite' }} />
          </div>
        )}

        {!hasMore && !loading && clips.length === 0 && (
          <div style={{ height: '100svh', scrollSnapAlign: 'start', display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', gap: 20, padding: 32 }}>
            <p style={{ color: '#555', fontSize: 16, textAlign: 'center' }}>No clips yet — be the first to publish one 🎬</p>
            <Link to="/songs" style={{
              padding: '12px 28px', borderRadius: 999, background: `linear-gradient(90deg, ${CYAN}, ${PURPLE})`,
              color: '#000', fontWeight: 800, fontSize: 15, textDecoration: 'none',
            }}>
              Go to my songs
            </Link>
          </div>
        )}
      </div>
    </div>
  );
}
