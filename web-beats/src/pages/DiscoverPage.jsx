import { useState, useEffect, useRef, useCallback, memo } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import { BACKEND_URL } from '../brand';
import { audioManager } from '../utils/audioManager';
import { markDiscoverSeen } from '../hooks/useDiscoverBadge';
import { useClipsEnabled } from '../hooks/useClipsEnabled';
import { deriveClipHandle } from '../utils/clipHandle';
import { formatCount } from '../utils/formatCount';
import { saveSongRemixIntent } from '../utils/remixIntent';
import { discoverSongToClipSong } from '../utils/discoverSong';
import ClipVisual, { frameCenter } from '../components/ClipVisual';
import TapToPause from '../components/TapToPause';
import ClipActionBtn from '../components/ClipActionBtn';
import { ZeusClipsWordmark, ClipsPillTab, ClipGenrePill } from '../components/ClipsBranding';

/* ── Zeus Clips design language (2026-09-24): true black, cyan → purple ── */
const CYAN   = '#00f0ff';
const PURPLE = '#7c3aed';
const BG     = '#000';
// Slide layout: the caption block and action column sit INFO_BOTTOM px up
// (clear of the playback bar); the framed cover stops FRAME_BOTTOM px up, above them.
const INFO_BOTTOM  = 108;
const FRAME_BOTTOM = 250;

function formatTime(secs) {
  if (!secs || isNaN(secs)) return '0:00';
  const m = Math.floor(secs / 60);
  const s = Math.floor(secs % 60);
  return `${m}:${s.toString().padStart(2, '0')}`;
}


/* ── Individual song slide ──────────────────────────────────────────────────
 * Styled like a Zeus Clips slide (2026-09-24): the cover shown whole over a
 * blurred copy (ClipVisual — never cropping text baked into the art), the
 * same genre pill / title / @handle typography, and the same round action
 * buttons down the right. Deliberately NO big "Remix This Sound" button —
 * that stays the hero action in Clips only; here Remix is one small button. */
const SongSlide = memo(function SongSlide({
  song, idx, isActive, isPaused, isLiked, likeCount, isCopied, canCreateClip,
  onLike, onShare, onRemix, onCreateClip, onTogglePause, onSlideRef, onVideoRef, onAudioRef,
}) {
  const { variant_id, title, artist_name, genre_tag, mp3_url, cover_url, music_video_url } = song;

  return (
    <div
      ref={onSlideRef}
      data-idx={idx}
      className="discover-slide"
      style={{
        position: 'relative', height: '100svh', width: '100%',
        scrollSnapAlign: 'start', overflow: 'hidden', background: BG, flexShrink: 0,
      }}
    >
      {/* Visual: a premium HD music video fills the screen as before; otherwise
          the Clips cover treatment. The video keeps its discover-video class and
          ref — the playback logic below drives it exactly as it always has. */}
      {music_video_url ? (
        <video
          ref={onVideoRef}
          src={music_video_url}
          autoPlay loop muted playsInline
          className="discover-video"
          style={{ position: 'absolute', inset: 0, width: '100%', height: '100%', objectFit: 'cover' }}
        />
      ) : (
        <ClipVisual
          mediaType="cover"
          url={cover_url}
          playing={isActive && !isPaused}
          duration={20}
          frameTop={112}
          frameBottom={FRAME_BOTTOM}
        />
      )}

      {/* Hidden audio element */}
      <audio
        ref={onAudioRef}
        src={mp3_url}
        loop
        className="discover-audio"
        style={{ display: 'none' }}
      />

      {/* Readability scrims — header strip and caption strip only (as in Clips). */}
      <div style={{
        position: 'absolute', top: 0, left: 0, right: 0, height: '18%',
        background: 'linear-gradient(to bottom, rgba(0,0,0,0.7) 0%, transparent 100%)',
        pointerEvents: 'none',
      }} />
      <div style={{
        position: 'absolute', bottom: 0, left: 0, right: 0, height: '42%',
        background: 'linear-gradient(to top, rgba(0,0,0,0.85) 0%, transparent 100%)',
        pointerEvents: 'none',
      }} />

      {/* Tap the picture to play/pause — the same control as the playback bar's ▶.
          Under every control below (z-index 10). */}
      <TapToPause paused={isActive && isPaused} onToggle={onTogglePause} center={frameCenter(112, FRAME_BOTTOM)} />

      {/* Song info — bottom left, Clips typography */}
      <div style={{ position: 'absolute', bottom: INFO_BOTTOM, left: 16, right: 76, zIndex: 10 }}>
        <ClipGenrePill genre={genre_tag} style={{ marginBottom: 10 }} />
        <p style={{
          margin: '0 0 4px', fontSize: 22, fontWeight: 800, color: '#fff', lineHeight: 1.2,
          textShadow: '0 2px 12px rgba(0,0,0,0.9)',
          WebkitLineClamp: 2, display: '-webkit-box', WebkitBoxOrient: 'vertical', overflow: 'hidden',
        }}>
          {title || `Song #${variant_id}`}
        </p>
        <p style={{ margin: 0, fontSize: 13, fontWeight: 600, color: 'rgba(255,255,255,0.6)', textShadow: '0 1px 4px rgba(0,0,0,0.85)' }}>
          @{deriveClipHandle(artist_name)}
        </p>
      </div>

      {/* Action column — like, remix, create clip (CLIPS_ENABLED), share */}
      <div style={{
        position: 'absolute', bottom: INFO_BOTTOM, right: 14, zIndex: 10,
        display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 14,
      }}>
        <ClipActionBtn onClick={onLike} icon="❤️" label={formatCount(likeCount)} active={isLiked} activeColor={PURPLE} />
        <ClipActionBtn onClick={onRemix} icon="🔁" label="Remix" />
        {canCreateClip && <ClipActionBtn onClick={onCreateClip} icon="🎬" label="Clip" />}
        <ClipActionBtn onClick={onShare} icon={isCopied ? '✓' : '🔗'} label={isCopied ? 'Copied' : 'Share'} active={isCopied} activeColor={CYAN} />
      </div>
    </div>
  );
});

/* ── Main page ──────────────────────────────────────────────────────────── */
export default function DiscoverPage() {
  const { token, user } = useAuth();
  const navigate = useNavigate();
  const [songs, setSongs]           = useState([]);
  const [muted, setMuted]           = useState(true);
  const [liked, setLiked]           = useState(new Set());
  const [counts, setCounts]         = useState({});
  const [copied, setCopied]         = useState(null);
  const [loading, setLoading]       = useState(false);
  const [hasMore, setHasMore]       = useState(true);
  const [signupPrompt, setSignupPrompt] = useState(false);
  const [activeTab, setActiveTab]         = useState('trending');
  const [forYouSongs, setForYouSongs]     = useState([]);
  const [forYouLoading, setForYouLoading] = useState(false);
  const [forYouFetched, setForYouFetched] = useState(false);
  // Server decides eligibility (1 like OR 3 plays) — client `liked` state starts
  // empty every session, so it cannot answer "has this user ever engaged?".
  // Defaults false so the tab is hidden until we positively hear otherwise.
  const [forYouEligible, setForYouEligible] = useState(false);
  const [activeAudioEl, setActiveAudioEl] = useState(null);
  const [playState, setPlayState]         = useState({ playing: false, currentTime: 0, duration: 0 });
  // Which slide is on screen — only drives the cover's Ken Burns zoom (the
  // playback logic keeps using activeRef, unchanged).
  const [activeIdx, setActiveIdx]         = useState(null);
  const canCreateClip = useClipsEnabled(user);

  // Refs that don't trigger re-renders
  const pageRef            = useRef(0);
  const loadingRef         = useRef(false);
  const hasMoreRef         = useRef(true);
  const mutedRef           = useRef(true);
  const activeRef          = useRef(null);
  const slideRefs          = useRef({});
  const videoRefs          = useRef({});
  const audioRefs          = useRef({});
  const scrollContainerRef = useRef(null);

  // Derived, not corrected after the fact: if For You is selected but no longer
  // offered, render Trending. An effect calling setActiveTab would work but costs a
  // cascading re-render (react-hooks/set-state-in-effect) for a purely derived value.
  const shownTab = activeTab === 'for_you' && !forYouEligible ? 'trending' : activeTab;

  // For You falls back to trending if the personalised fetch returns nothing
  const activeSongs = shownTab === 'for_you'
    ? (forYouSongs.length > 0 ? forYouSongs : songs)
    : songs;

  /* ── Fetch a page of songs ─────────────────────────────────────────────── */
  const fetchPage = useCallback(async () => {
    if (loadingRef.current || !hasMoreRef.current) return;
    loadingRef.current = true;
    setLoading(true);
    try {
      const r = await fetch(`${BACKEND_URL}/api/discover?page=${pageRef.current}`);
      if (!r.ok) return;
      const d = await r.json();
      const s = d.songs || [];
      if (s.length < 20) { hasMoreRef.current = false; setHasMore(false); }
      setSongs(prev => [...prev, ...s]);
      setCounts(prev => {
        const n = { ...prev };
        s.forEach(x => { n[x.variant_id] = x.like_count; });
        return n;
      });
      pageRef.current += 1;
    } catch (e) {
      console.error('discover:', e);
    } finally {
      loadingRef.current = false;
      setLoading(false);
    }
  }, []);

  useEffect(() => { fetchPage(); }, [fetchPage]);

  // Landing here IS having seen the feed, so reseed the "last seen" marker from the
  // server clock. The header re-checks on navigation, so the badge clears on the way
  // back out. Best-effort: a failure just leaves the badge up until the next visit.
  useEffect(() => { markDiscoverSeen(user?.id); }, [user?.id]);

  // Is a personalised feed worth offering yet? Until it is, For You returns the same
  // recency-ordered songs as Trending, and two tabs showing identical content reads
  // as broken. Any failure leaves the tab hidden.
  useEffect(() => {
    if (!token) return undefined;
    let cancelled = false;
    (async () => {
      try {
        const r = await fetch(`${BACKEND_URL}/api/discover/engagement`, {
          headers: { Authorization: `Bearer ${token}` },
        });
        if (!r.ok || cancelled) return;
        const d = await r.json();
        if (!cancelled) setForYouEligible(Boolean(d?.eligible));
      } catch { /* tab stays hidden */ }
    })();
    return () => { cancelled = true; };
  }, [token]);

  const fetchForYou = useCallback(async () => {
    if (!token || forYouFetched) return;
    setForYouLoading(true);
    try {
      const r = await fetch(`${BACKEND_URL}/api/discover/for-you`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (r.ok) {
        const d = await r.json();
        const s = d.songs || [];
        setForYouSongs(s);
        setCounts(prev => {
          const n = { ...prev };
          s.forEach(x => { n[x.variant_id] = x.like_count; });
          return n;
        });
      }
    } catch (e) {
      console.error('for-you:', e);
    } finally {
      setForYouFetched(true); // always mark done so we don't retry on every render
      setForYouLoading(false);
    }
  }, [token, forYouFetched]);

  const handleTabChange = (tab) => {
    if (tab === 'for_you' && !token) { setSignupPrompt(true); return; }
    if (tab === 'for_you' && !forYouEligible) return;   // not offered yet
    setActiveTab(tab);
    activeRef.current = null;
    if (scrollContainerRef.current) scrollContainerRef.current.scrollTop = 0;
    if (tab === 'for_you' && !forYouFetched) fetchForYou();
  };

  /* ── Intersection Observer — autoplay + infinite scroll trigger ─────────── */
  useEffect(() => {
    if (!activeSongs.length) return;

    const obs = new IntersectionObserver(entries => {
      entries.forEach(entry => {
        const idx = +entry.target.dataset.idx;
        const vid = videoRefs.current[idx];
        const aud = audioRefs.current[idx];

        if (entry.isIntersecting) {
          const prev = activeRef.current;
          if (prev !== null && prev !== idx) {
            videoRefs.current[prev]?.pause();
            const pa = audioRefs.current[prev];
            if (pa) { pa.pause(); pa.currentTime = 0; }
          }
          activeRef.current = idx;
          setActiveIdx(idx);
          setActiveAudioEl(aud || null);

          if (vid) { vid.muted = true; vid.play().catch(() => {}); }
          if (aud && !mutedRef.current) audioManager.play(aud, activeSongs[idx]?.variant_id);

          // Log play event (fire-and-forget)
          const song = activeSongs[idx];
          if (song) {
            fetch(`${BACKEND_URL}/api/discover/play`, {
              method: 'POST',
              headers: {
                'Content-Type': 'application/json',
                ...(token ? { Authorization: `Bearer ${token}` } : {}),
              },
              body: JSON.stringify({ variant_id: song.variant_id }),
            }).catch(() => {});
          }

          // Only infinite-scroll on trending tab
          if (shownTab === 'trending' && idx >= activeSongs.length - 3) fetchPage();
        } else {
          if (vid) vid.pause();
          if (aud) { aud.pause(); aud.currentTime = 0; }
        }
      });
    }, { threshold: 0.65 });

    Object.values(slideRefs.current).forEach(el => { if (el) obs.observe(el); });
    return () => obs.disconnect();
  }, [activeSongs, shownTab, fetchPage, token]);

  /* ── Attach playback listeners when the active audio element changes ───── */
  useEffect(() => {
    const aud = activeAudioEl;
    if (!aud) return;
    const onTime  = () => setPlayState(p => ({ ...p, currentTime: aud.currentTime }));
    const onMeta  = () => setPlayState(p => ({ ...p, duration: aud.duration || 0 }));
    const onPlay  = () => setPlayState(p => ({ ...p, playing: true }));
    const onPause = () => setPlayState(p => ({ ...p, playing: false }));
    aud.addEventListener('timeupdate', onTime);
    aud.addEventListener('loadedmetadata', onMeta);
    aud.addEventListener('play', onPlay);
    aud.addEventListener('pause', onPause);
    setPlayState({ playing: !aud.paused, currentTime: aud.currentTime, duration: aud.duration || 0 });
    return () => {
      aud.removeEventListener('timeupdate', onTime);
      aud.removeEventListener('loadedmetadata', onMeta);
      aud.removeEventListener('play', onPlay);
      aud.removeEventListener('pause', onPause);
    };
  }, [activeAudioEl]);

  /* ── Playback controls ───────────────────────────────────────────────── */
  const handlePlayPause = () => {
    const aud = activeAudioEl;
    if (!aud) return;
    // An HD music video pauses and resumes with the song.
    const vid = videoRefs.current[activeRef.current];
    if (aud.paused) {
      mutedRef.current = false;
      setMuted(false);
      audioManager.play(aud, activeSongs[activeRef.current]?.variant_id);
      vid?.play().catch(() => {});
    } else {
      aud.pause();
      vid?.pause();
    }
  };

  const handleRewind  = () => { if (activeAudioEl) activeAudioEl.currentTime = Math.max(0, activeAudioEl.currentTime - 10); };
  const handleForward = () => { if (activeAudioEl) activeAudioEl.currentTime = Math.min(activeAudioEl.duration || 0, activeAudioEl.currentTime + 10); };
  const handleSeek    = (e) => { if (activeAudioEl) activeAudioEl.currentTime = Number(e.target.value); };

  /* ── Mute toggle ──────────────────────────────────────────────────────── */
  const toggleMute = () => {
    const nm = !mutedRef.current;
    mutedRef.current = nm;
    setMuted(nm);
    const idx = activeRef.current;
    if (idx !== null) {
      const aud = audioRefs.current[idx];
      if (aud) {
        if (nm) { aud.pause(); audioManager.stop(); }
        else audioManager.play(aud, activeSongs[idx]?.variant_id);
      }
    }
  };

  /* ── Like / unlike ──────────────────────────────────────────────────────── */
  const handleLike = useCallback(async (variantId) => {
    if (!token) {
      setSignupPrompt(true);
      return;
    }
    const wasLiked = liked.has(variantId);
    // One like clears the threshold, so reveal the tab immediately rather than
    // making them reload to discover it exists.
    if (!wasLiked) setForYouEligible(true);
    setLiked(prev => { const n = new Set(prev); wasLiked ? n.delete(variantId) : n.add(variantId); return n; });
    setCounts(prev => ({ ...prev, [variantId]: Math.max(0, (prev[variantId] || 0) + (wasLiked ? -1 : 1)) }));
    try {
      await fetch(`${BACKEND_URL}/api/discover/${variantId}/like`, {
        method: wasLiked ? 'DELETE' : 'POST',
        headers: { Authorization: `Bearer ${token}` },
      });
    } catch (_) {
      setLiked(prev => { const n = new Set(prev); wasLiked ? n.add(variantId) : n.delete(variantId); return n; });
      setCounts(prev => ({ ...prev, [variantId]: Math.max(0, (prev[variantId] || 0) + (wasLiked ? 1 : -1)) }));
    }
  }, [token, liked]);

  /* ── Share ──────────────────────────────────────────────────────────────── */
  const handleShare = useCallback(async (variantId) => {
    const url = `${window.location.origin}/discover/${variantId}`;
    try {
      if (navigator.share) {
        await navigator.share({ title: 'Zeus Beats', url });
      } else {
        await navigator.clipboard.writeText(url);
      }
    } catch (_) {}
    setCopied(variantId);
    setTimeout(() => setCopied(c => c === variantId ? null : c), 2000);
  }, []);

  /* ── Remix — the same song-keyed hand-off as a Clips remix ──────────────── */
  const handleRemix = useCallback((variantId) => {
    if (!token) {
      saveSongRemixIntent(variantId);
      navigate(`/register?remixSong=${variantId}`);
      return;
    }
    navigate(`/discover/${variantId}/remix`);
  }, [token, navigate]);

  /* ── Create Clip from any public song (CLIPS_ENABLED) ───────────────────── */
  // /clips/new is account-only: logged out, it goes to login and comes back
  // here with ?song= intact, and the creator re-fetches the song itself.
  const handleCreateClip = useCallback((song) => {
    navigate(`/clips/new?song=${song.variant_id}`, { state: { song: discoverSongToClipSong(song) } });
  }, [navigate]);

  return (
    <div style={{ background: BG, height: '100svh', width: '100vw', overflow: 'hidden', position: 'relative' }}>

      {/* Fixed header — Clips-style: ZEUS wordmark, small speaker toggle, and
          "Make Your Own" (prominent for visitors, small for signed-in users). */}
      <div style={{
        position: 'fixed', top: 0, left: 0, right: 0, zIndex: 200,
        padding: '14px 16px 10px',
        display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 10,
        background: 'linear-gradient(to bottom, rgba(0,0,0,0.85) 0%, transparent 100%)',
        pointerEvents: 'none',
      }}>
        <div style={{ pointerEvents: 'auto' }}>
          <ZeusClipsWordmark to="/" word="BEATS" size={17} />
        </div>

        <div style={{ display: 'flex', gap: 8, alignItems: 'center', pointerEvents: 'auto' }}>
          {/* Speaker toggle — same small control as Clips */}
          <button
            onClick={toggleMute}
            aria-label={muted ? 'Tap to hear' : 'Sound on'}
            style={{
              background: muted ? 'rgba(255,255,255,0.08)' : `${CYAN}22`,
              border: `1px solid ${muted ? 'rgba(255,255,255,0.2)' : CYAN}`,
              borderRadius: 20, padding: '5px 10px', color: muted ? 'rgba(255,255,255,0.7)' : CYAN,
              cursor: 'pointer', fontSize: 15,
              boxShadow: muted ? 'none' : `0 0 10px ${CYAN}44`,
            }}
          >
            {muted ? '🔇' : '🔊'}
          </button>

          {token ? (
            <button
              onClick={() => navigate('/songs')}
              style={{
                background: 'rgba(10,10,20,0.6)', color: '#fff',
                fontSize: 12, fontWeight: 700, padding: '6px 12px', borderRadius: 999,
                border: `1px solid ${CYAN}55`, cursor: 'pointer', whiteSpace: 'nowrap',
              }}
            >
              ⚡ Make Your Own
            </button>
          ) : (
            <button
              onClick={() => navigate('/register')}
              style={{
                background: `linear-gradient(90deg, ${CYAN}, ${PURPLE})`, color: '#000',
                fontFamily: 'Orbitron, sans-serif', fontSize: 12, fontWeight: 800,
                padding: '10px 14px', borderRadius: 999, border: 'none', cursor: 'pointer',
                boxShadow: `0 0 16px ${CYAN}66, 0 0 28px ${PURPLE}55`,
                letterSpacing: '0.02em', whiteSpace: 'nowrap',
              }}
            >
              ⚡ Make Your Own
            </button>
          )}
        </div>
      </div>

      {/* Tabs — the same pill tabs as Clips' New / Trending */}
      <div style={{
        position: 'fixed', top: 62, left: 0, right: 0, zIndex: 199,
        display: 'flex', justifyContent: 'center', gap: 10,
        pointerEvents: 'auto',
      }}>
        {[
          ['trending', 'Trending'],
          // Signed out: shown deliberately. Tapping it raises the signup prompt
          // (handleTabChange checks !token first), which is a conversion touchpoint
          // worth keeping — there is no duplicate-feed problem for someone who
          // cannot load a personalised feed at all.
          // Signed in: hidden until there is history to personalise from, otherwise
          // For You returns the same recency-ordered songs as Trending.
          ...((!token || forYouEligible) ? [['for_you', 'For You']] : []),
        ].map(([tab, label]) => (
          <ClipsPillTab key={tab} active={shownTab === tab} onClick={() => handleTabChange(tab)}>
            {label}
          </ClipsPillTab>
        ))}
      </div>

      {/* Scroll feed */}
      <div
        ref={scrollContainerRef}
        style={{
          height: '100svh',
          overflowY: 'scroll',
          scrollSnapType: 'y mandatory',
          WebkitOverflowScrolling: 'touch',
        }}
      >
        {/* For You loading state */}
        {shownTab === 'for_you' && forYouLoading && (
          <div style={{
            height: '100svh', scrollSnapAlign: 'start',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
          }}>
            <div style={{
              width: 36, height: 36, borderRadius: '50%',
              border: `3px solid ${CYAN}33`, borderTopColor: CYAN,
              animation: 'spin 0.8s linear infinite',
            }} />
          </div>
        )}

        {/* For You empty state — only shown if trending also has nothing */}
        {shownTab === 'for_you' && !forYouLoading && forYouFetched && forYouSongs.length === 0 && songs.length === 0 && (
          <div style={{
            height: '100svh', scrollSnapAlign: 'start',
            display: 'flex', flexDirection: 'column',
            alignItems: 'center', justifyContent: 'center', gap: 16, padding: 32,
          }}>
            <p style={{ color: '#555', fontSize: 16, textAlign: 'center' }}>
              Nothing shared yet — be the first to drop a track 🎵
            </p>
          </div>
        )}

        {activeSongs.map((song, idx) => (
          <SongSlide
            key={song.variant_id}
            song={song}
            idx={idx}
            isActive={activeIdx === idx}
            isPaused={!playState.playing}
            onTogglePause={handlePlayPause}
            isLiked={liked.has(song.variant_id)}
            likeCount={counts[song.variant_id] || 0}
            isCopied={copied === song.variant_id}
            canCreateClip={canCreateClip}
            onLike={() => handleLike(song.variant_id)}
            onShare={() => handleShare(song.variant_id)}
            onRemix={() => handleRemix(song.variant_id)}
            onCreateClip={() => handleCreateClip(song)}
            onSlideRef={el => { slideRefs.current[idx] = el; }}
            onVideoRef={el => { videoRefs.current[idx] = el; }}
            onAudioRef={el => { audioRefs.current[idx] = el; }}
          />
        ))}

        <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>

        {shownTab === 'trending' && loading && (
          <div style={{
            height: '100svh', scrollSnapAlign: 'start',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
          }}>
            <div style={{
              width: 36, height: 36, borderRadius: '50%',
              border: `3px solid ${CYAN}33`,
              borderTopColor: CYAN,
              animation: 'spin 0.8s linear infinite',
            }} />
          </div>
        )}

        {shownTab === 'trending' && !hasMore && !loading && songs.length === 0 && (
          <div style={{
            height: '100svh', scrollSnapAlign: 'start',
            display: 'flex', flexDirection: 'column',
            alignItems: 'center', justifyContent: 'center', gap: 20,
            padding: 32,
          }}>
            <p style={{ color: '#555', fontSize: 16, textAlign: 'center' }}>
              Nothing shared yet — be the first to drop a track 🎵
            </p>
            <button
              onClick={() => navigate('/register')}
              style={{
                padding: '12px 28px', borderRadius: 8,
                background: `linear-gradient(90deg, ${CYAN}, ${PURPLE})`,
                color: '#000', fontWeight: 800, fontSize: 15,
                border: 'none', cursor: 'pointer',
              }}
            >
              Make your own ⚡
            </button>
          </div>
        )}

        {shownTab === 'trending' && !hasMore && !loading && songs.length > 0 && (
          <div style={{
            height: '100svh', scrollSnapAlign: 'start',
            display: 'flex', flexDirection: 'column',
            alignItems: 'center', justifyContent: 'center', gap: 20,
            background: BG,
          }}>
            <p style={{ color: '#555', fontSize: 16 }}>You've heard them all 🎵</p>
            <button
              onClick={() => navigate('/register')}
              style={{
                padding: '12px 28px', borderRadius: 8,
                background: `linear-gradient(90deg, ${CYAN}, ${PURPLE})`,
                color: '#000', fontWeight: 800, fontSize: 15,
                border: 'none', cursor: 'pointer',
                boxShadow: `0 0 20px ${CYAN}44`,
              }}
            >
              Make your own ⚡
            </button>
          </div>
        )}
      </div>

      {/* ── Playback controls bar (same controls, Clips styling) ──────────────── */}
      {activeAudioEl && (
        <div style={{
          position: 'fixed', bottom: 0, left: 0, right: 0, zIndex: 200,
          padding: '8px 16px 14px',
          background: 'linear-gradient(to top, rgba(0,0,0,0.97) 65%, transparent 100%)',
          pointerEvents: 'auto',
        }}>
          {/* Progress bar */}
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 6 }}>
            <span style={{ fontSize: 10, fontWeight: 700, color: 'rgba(255,255,255,0.75)', fontFamily: 'monospace', minWidth: 32, textAlign: 'right' }}>
              {formatTime(playState.currentTime)}
            </span>
            <input
              type="range"
              min="0"
              max={playState.duration || 0}
              step="0.1"
              value={playState.currentTime}
              onChange={handleSeek}
              aria-label="Seek"
              style={{
                flex: 1, height: 3, cursor: 'pointer', accentColor: CYAN,
                background: playState.duration
                  ? `linear-gradient(to right, ${CYAN} 0%, ${PURPLE} ${(playState.currentTime / playState.duration) * 100}%, rgba(255,255,255,0.15) ${(playState.currentTime / playState.duration) * 100}%)`
                  : 'rgba(255,255,255,0.15)',
                borderRadius: 2, outline: 'none', border: 'none',
                appearance: 'none', WebkitAppearance: 'none',
              }}
            />
            <span style={{ fontSize: 10, fontWeight: 700, color: 'rgba(255,255,255,0.45)', fontFamily: 'monospace', minWidth: 32 }}>
              {formatTime(playState.duration)}
            </span>
          </div>
          {/* Control buttons */}
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 28 }}>
            <button
              onClick={handleRewind}
              aria-label="Back 10 seconds"
              style={{ background: 'none', border: 'none', color: 'rgba(255,255,255,0.75)', fontSize: 13, fontWeight: 800, cursor: 'pointer', padding: 6 }}
            >↺ 10</button>
            <button
              onClick={handlePlayPause}
              aria-label={playState.playing ? 'Pause' : 'Play'}
              style={{
                width: 46, height: 46, borderRadius: '50%',
                background: `linear-gradient(135deg, ${CYAN}, ${PURPLE})`,
                border: 'none', color: '#000', fontSize: 18, cursor: 'pointer',
                display: 'flex', alignItems: 'center', justifyContent: 'center',
                boxShadow: playState.playing ? `0 0 18px ${CYAN}88, 0 0 30px ${PURPLE}66` : `0 0 10px ${CYAN}44`,
                transition: 'box-shadow 0.18s',
              }}
            >{playState.playing ? '⏸' : '▶'}</button>
            <button
              onClick={handleForward}
              aria-label="Forward 10 seconds"
              style={{ background: 'none', border: 'none', color: 'rgba(255,255,255,0.75)', fontSize: 13, fontWeight: 800, cursor: 'pointer', padding: 6 }}
            >10 ↻</button>
          </div>
        </div>
      )}

      {/* Sign-up prompt modal — shown when non-logged-in user taps like */}
      {signupPrompt && (
        <div
          onClick={() => setSignupPrompt(false)}
          style={{
            position: 'fixed', inset: 0, zIndex: 500,
            background: 'rgba(0,0,0,0.75)',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            padding: 24,
          }}
        >
          <div
            onClick={e => e.stopPropagation()}
            style={{
              background: '#0f0f1e',
              border: `1px solid ${CYAN}44`,
              borderRadius: 16,
              padding: '32px 28px',
              maxWidth: 340,
              width: '100%',
              textAlign: 'center',
              boxShadow: `0 0 40px ${CYAN}22`,
            }}
          >
            <div style={{ fontSize: 36, marginBottom: 12 }}>❤️</div>
            <p style={{
              color: '#fff', fontSize: 18, fontWeight: 800,
              margin: '0 0 8px', lineHeight: 1.3,
            }}>
              Sign up free to like songs
            </p>
            <p style={{
              color: 'rgba(255,255,255,0.55)', fontSize: 14,
              margin: '0 0 24px', lineHeight: 1.5,
            }}>
              Sign up free to like songs and make your own! 🎵
            </p>
            <button
              onClick={() => navigate('/register')}
              style={{
                width: '100%',
                padding: '14px 0',
                borderRadius: 10,
                background: `linear-gradient(90deg, ${CYAN}, ${PURPLE})`,
                color: '#000',
                fontWeight: 800,
                fontSize: 15,
                border: 'none',
                cursor: 'pointer',
                marginBottom: 12,
                boxShadow: `0 0 20px ${CYAN}44`,
              }}
            >
              ⚡ Sign Up Free
            </button>
            <button
              onClick={() => setSignupPrompt(false)}
              style={{
                background: 'none', border: 'none',
                color: 'rgba(255,255,255,0.4)',
                fontSize: 13, cursor: 'pointer',
              }}
            >
              Maybe later
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
