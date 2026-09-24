import { useState, useEffect, useRef, useCallback, memo } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import { BACKEND_URL } from '../brand';
import { clipSeekTarget, clipInitialTime } from '../utils/clipPlayback';
import { getClipAnonId } from '../utils/clipAnonId';
import { saveRemixIntent } from '../utils/remixIntent';
import { readUtmAttribution } from '../utils/utmAttribution';
import { deriveClipHandle } from '../utils/clipHandle';
import { formatCount } from '../utils/formatCount';
import RemixButton from '../components/RemixButton';
import ClipSongBar from '../components/ClipSongBar';
import ClipMoreMenu from '../components/ClipMoreMenu';
import ClipActionBtn from '../components/ClipActionBtn';
import ClipVisual, { FramedCover } from '../components/ClipVisual';
import { usePublishedHeight } from '../hooks/usePublishedHeight';
import TapToPause from '../components/TapToPause';
import { ZeusClipsWordmark, ClipsAiBadge, ClipsPillTab, ClipGenrePill, BackToBeatsLink } from '../components/ClipsBranding';

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
  clip, idx, isLiked, likeCount, isCopied, token, isPlaying, isActive, isPaused,
  onLike, onShare, onRemix, onRequireAuth, onTogglePause, onSlideRef, onVideoRef, onAudioRef, onProgressRef,
}) {
  const { media_type, media_url, song_cover_url, song_title, artist_name, genre_tag,
          caption, clip_start_time, clip_duration, mp3_url, remix_count } = clip;
  const handle = deriveClipHandle(artist_name);

  const visualUrl = media_type === 'cover'
    ? song_cover_url
    : `${BACKEND_URL}${media_url}`;

  return (
    <div
      ref={onSlideRef}
      data-idx={idx}
      className="clip-slide clip-box"
      style={{
        position: 'relative', height: '100svh', width: '100%',
        scrollSnapAlign: 'start', overflow: 'hidden', background: '#0a0a14', flexShrink: 0,
      }}
    >
      {/* Visual — see ClipVisual for the cover/photo/video treatments. The
          Ken Burns zoom follows the ACTIVE slide (it plays muted like a video
          clip does until sound is turned on); the visualiser bars below only
          move while audio is actually playing. */}
      <ClipVisual
        mediaType={media_type}
        url={visualUrl}
        playing={isActive && !isPaused}
        duration={clip_duration}
        videoRef={onVideoRef}
      />

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

      {/* Scrims (2026-09-23 readability fix): the image plays at full brightness
          (see above) — these dim only the header/tabs strip and the caption/
          stats/Remix-button strip that sit on top of it, leaving the middle of
          the frame untouched. Two separate gradients rather than one long one,
          so neither reaches into the middle. */}
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

      {/* Tap-to-pause lives in the picture box below; everything the viewer
          reads or taps is one flex column (.clip-layout, index.css) — header
          space → picture + actions → info → Remix → song bar — so nothing can
          overlap at any text size, and the picture takes what's left. */}
      <div
        className="clip-layout"
        style={{
          paddingTop: 'calc(var(--clips-header-h, 120px) + 4px)',
          paddingBottom: 'calc(10px + var(--cookie-banner-h, 0px) + var(--clips-nav-h, 0px))',
        }}
      >
        <div className="clip-stage"><div className="clip-stage-inner">
          <div className="clip-picture">
            <FramedCover mediaType={media_type} url={visualUrl} playing={isActive && !isPaused} duration={clip_duration} />
            <TapToPause paused={isActive && isPaused} onToggle={onTogglePause} />
          </div>
          {/* Action column — like, remix count, share, report (⋯) */}
          <div className="clip-actions">
            <ClipActionBtn onClick={onLike} icon="❤️" label={formatCount(likeCount)} active={isLiked} activeColor={PURPLE} />
            <ClipActionBtn icon="🔁" label={formatCount(remix_count)} />
            <ClipActionBtn onClick={onShare} icon={isCopied ? '✓' : '🔗'} label={isCopied ? 'Copied' : 'Share'} active={isCopied} activeColor={CYAN} />
            <ClipMoreMenu clipId={clip.id} token={token} onRequireAuth={onRequireAuth} />
          </div>
        </div></div>

        {/* Info: genre, @username (links to their profile), caption */}
        <div className="clip-info">
          <ClipGenrePill genre={genre_tag} style={{ marginBottom: 6 }} />
          <Link
            to={`/clips/u/${handle}`}
            className="clip-oneline"
            style={{
              margin: '0 0 2px', fontSize: 'clamp(13px, 4cqw, 15px)', fontWeight: 800, color: '#fff',
              textShadow: '0 2px 8px rgba(0,0,0,0.8)', textDecoration: 'none',
            }}
          >
            @{handle}
          </Link>
          {caption && (
            <p className="clip-caption" style={{
              margin: 0, fontSize: 'clamp(12px, 3.6cqw, 13px)', color: 'rgba(255,255,255,0.85)', lineHeight: 1.4,
              textShadow: '0 1px 4px rgba(0,0,0,0.85)',
            }}>
              {caption}
            </p>
          )}
        </div>

        {/* ── "⚡ Remix This Sound" — the most prominent button on the page ── */}
        <RemixButton onClick={onRemix} />

        {/* Song bar, with its progress strip */}
        <ClipSongBar
          coverUrl={song_cover_url}
          title={song_title}
          artistName={clip.song_artist_name || artist_name}
          spinning={isPlaying}
          onUseSound={onRemix}
          progressBarRef={el => { if (el) onProgressRef(el); }}
        />
      </div>
    </div>
  );
});

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
  const [activeIdx, setActiveIdx] = useState(null); // which slide is current — drives the song-bar disc spin
  // Tap-to-pause: pauses the active clip's video + sound (and with them the Ken
  // Burns zoom and visualiser). Cleared whenever a new clip comes on screen.
  const [paused, setPaused]   = useState(false);
  const pausedRef             = useRef(false);

  const pageRef            = useRef(0);
  const loadingRef         = useRef(false);
  const hasMoreRef         = useRef(true);
  const mutedRef           = useRef(true);
  const activeRef          = useRef(null);
  const viewedRef          = useRef(new Set()); // clip ids already POSTed a view this session
  const slideRefs          = useRef({});
  const videoRefs          = useRef({});
  const audioRefs          = useRef({});
  const progressRefs       = useRef({});
  const scrollContainerRef = useRef(null);
  const headerRef          = useRef(null);
  usePublishedHeight(headerRef, '--clips-header-h');

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
          setActiveIdx(idx);
          pausedRef.current = false;   // a newly shown clip always plays, from its start point
          setPaused(false);

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

  /* ── Clamp each active audio element to its clip window, and drive its
   * song-bar progress strip ────────────────────────────────────────────────
   * Attaches the timeupdate/ended clamp once per element, reading clip_start/
   * clip_duration from its own data attributes (set on the <audio> above).
   * The progress bar width is set IMPERATIVELY here (ref.style.width), never
   * via React state, so a ~4x/second timeupdate never triggers a re-render —
   * same reasoning as the clamp itself being imperative. */
  useEffect(() => {
    const cleanups = Object.entries(audioRefs.current).filter(([, aud]) => aud).map(([idxStr, aud]) => {
      const idx = Number(idxStr);
      const start = Number(aud.dataset.clipStart) || 0;
      const duration = Number(aud.dataset.clipDuration) || 0;
      const onTime = () => {
        const target = clipSeekTarget(aud.currentTime, start, duration);
        if (target !== null) aud.currentTime = target;
        const bar = progressRefs.current[idx];
        if (bar && duration > 0) {
          const pct = Math.min(100, Math.max(0, ((aud.currentTime - start) / duration) * 100));
          bar.style.width = `${pct}%`;
        }
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
      // Turning the sound on while paused means "play" — never unmute into silence.
      if (!nm && pausedRef.current) {
        pausedRef.current = false;
        setPaused(false);
        videoRefs.current[idx]?.play().catch(() => {});
      }
    }
  };

  const togglePause = useCallback(() => {
    const idx = activeRef.current;
    if (idx === null) return;
    const vid = videoRefs.current[idx];
    const aud = audioRefs.current[idx];
    if (pausedRef.current) {
      pausedRef.current = false;
      setPaused(false);
      vid?.play().catch(() => {});
      if (aud && !mutedRef.current) aud.play().catch(() => {});
    } else {
      pausedRef.current = true;
      setPaused(true);
      vid?.pause();
      aud?.pause();
    }
  }, []);

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
      {/* Fixed header — wordmark centred with the mute toggle at the edge, the
          AI badge (dropped on short screens), then the New / Trending tabs. One
          block whose live height is published as --clips-header-h, so every
          slide's layout starts below it at any text size. */}
      <div
        ref={headerRef}
        style={{
          position: 'fixed', top: 0, left: 0, right: 0, zIndex: 200,
          padding: 'max(10px, env(safe-area-inset-top)) 14px 8px',
          background: 'linear-gradient(to bottom, rgba(0,0,0,0.85) 0%, rgba(0,0,0,0.55) 70%, transparent 100%)',
          pointerEvents: 'none',
        }}
      >
        {/* minmax(0,1fr) | auto | minmax(0,1fr) keeps the wordmark centred and lets the sides shrink. */}
        <div style={{ display: 'grid', gridTemplateColumns: 'minmax(0,1fr) auto minmax(0,1fr)', alignItems: 'center', gap: 8 }}>
          <div style={{ pointerEvents: 'auto', justifySelf: 'start', minWidth: 0 }}>
            <BackToBeatsLink />
          </div>
          <div style={{ pointerEvents: 'auto' }}>
            <ZeusClipsWordmark />
          </div>
          <button
            onClick={toggleMute}
            style={{
              justifySelf: 'end',
              background: muted ? 'rgba(255,255,255,0.08)' : `${CYAN}22`,
              border: `1px solid ${muted ? 'rgba(255,255,255,0.2)' : CYAN}`,
              borderRadius: 20, padding: '5px 10px', color: muted ? 'rgba(255,255,255,0.7)' : CYAN,
              cursor: 'pointer', fontSize: 15, pointerEvents: 'auto',
            }}
            aria-label={muted ? 'Tap to hear' : 'Sound on'}
          >
            {muted ? '🔇' : '🔊'}
          </button>
        </div>
        <div className="clips-ai-badge" style={{ display: 'flex', justifyContent: 'flex-end', marginTop: 6, pointerEvents: 'auto' }}>
          <ClipsAiBadge />
        </div>
        {/* Pill-style New / Trending tabs */}
        <div style={{ display: 'flex', justifyContent: 'center', gap: 10, marginTop: 8, pointerEvents: 'auto' }}>
          <ClipsPillTab active={sort === 'new'} onClick={() => handleSortChange('new')}>New</ClipsPillTab>
          <ClipsPillTab active={sort === 'trending'} onClick={() => handleSortChange('trending')}>Trending</ClipsPillTab>
        </div>
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
            isPlaying={activeIdx === idx && !muted && !paused}
            isActive={activeIdx === idx}
            isPaused={paused}
            onTogglePause={togglePause}
            onLike={() => handleLike(clip.id)}
            onShare={() => handleShare(clip.id)}
            onRemix={() => handleRemix(clip.id)}
            onRequireAuth={() => navigate('/register')}
            onSlideRef={el => { slideRefs.current[idx] = el; }}
            onVideoRef={el => { videoRefs.current[idx] = el; }}
            onAudioRef={el => { audioRefs.current[idx] = el; }}
            onProgressRef={el => { progressRefs.current[idx] = el; }}
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
