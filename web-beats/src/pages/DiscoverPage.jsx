import { useState, useEffect, useRef, useCallback, memo } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import { BACKEND_URL } from '../brand';
import { audioManager } from '../utils/audioManager';

/* ── Neon cyberpunk tokens ──────────────────────────────────────────────── */
const CYAN  = '#00f0ff';
const PINK  = '#f472b6';
const BG    = '#000';

/* ── Genre label → display ─────────────────────────────────────────────── */
const GENRE_LABELS = {
  hiphop:'Hip-Hop', rnb:'R&B', pop:'Pop', rock:'Rock', soul:'Soul',
  blues:'Blues', jazz:'Jazz', reggae:'Reggae', lofi:'Lo-Fi', edm:'EDM',
  drumandbass:'D&B', grime:'Grime', ukgarage:'UK Garage', jungle:'Jungle',
  bassline:'Bassline', house:'House', techno:'Techno', loversrock:'Lovers Rock',
  ukdrill:'UK Drill', kpop:'K-Pop', classical:'Classical', indie:'Indie',
  afrobeats:'Afrobeats', amapiano:'Amapiano', afroswing:'Afroswing',
  country:'Country', acoustic:'Acoustic', hyperpop:'Hyperpop',
};
const gLabel = (g) => GENRE_LABELS[g] || (g ? g.charAt(0).toUpperCase() + g.slice(1) : '');

/* ── Individual song slide ──────────────────────────────────────────────── */
const SongSlide = memo(function SongSlide({
  song, idx, muted, isLiked, likeCount, isCopied,
  onLike, onShare, onSlideRef, onVideoRef, onAudioRef,
}) {
  const { variant_id, title, artist_name, genre_tag, mp3_url, cover_url, music_video_url } = song;

  return (
    <div
      ref={onSlideRef}
      data-idx={idx}
      className="discover-slide"
      style={{
        position: 'relative',
        height: '100svh',
        width: '100%',
        scrollSnapAlign: 'start',
        overflow: 'hidden',
        background: '#0a0a14',
        flexShrink: 0,
      }}
    >
      {/* Background: animated cover or still image */}
      {music_video_url ? (
        <video
          ref={onVideoRef}
          src={music_video_url}
          autoPlay
          loop
          muted
          playsInline
          className="discover-video"
          style={{
            position: 'absolute', inset: 0,
            width: '100%', height: '100%',
            objectFit: 'cover',
            filter: 'brightness(0.55)',
          }}
        />
      ) : cover_url ? (
        <img
          src={cover_url}
          alt=""
          style={{
            position: 'absolute', inset: 0,
            width: '100%', height: '100%',
            objectFit: 'cover',
            filter: 'brightness(0.45)',
          }}
        />
      ) : (
        <div style={{
          position: 'absolute', inset: 0,
          background: 'linear-gradient(135deg, #0d0d1a 0%, #1a0a2e 100%)',
        }} />
      )}

      {/* Hidden audio element */}
      <audio
        ref={onAudioRef}
        src={mp3_url}
        loop
        className="discover-audio"
        style={{ display: 'none' }}
      />

      {/* Bottom gradient overlay */}
      <div style={{
        position: 'absolute', inset: 0,
        background: 'linear-gradient(to top, rgba(0,0,0,0.92) 0%, rgba(0,0,0,0.3) 45%, transparent 70%)',
        pointerEvents: 'none',
      }} />

      {/* Cyan left edge glow */}
      <div style={{
        position: 'absolute', top: 0, bottom: 0, left: 0,
        width: 3,
        background: `linear-gradient(to bottom, transparent, ${CYAN}, transparent)`,
        opacity: 0.6,
        pointerEvents: 'none',
      }} />

      {/* Song info — bottom left */}
      <div style={{
        position: 'absolute', bottom: 80, left: 20, right: 80,
        zIndex: 10,
      }}>
        {/* Genre badge */}
        <span style={{
          display: 'inline-block',
          padding: '2px 10px',
          borderRadius: 20,
          fontSize: 11,
          fontWeight: 700,
          letterSpacing: '0.05em',
          textTransform: 'uppercase',
          background: `linear-gradient(90deg, ${CYAN}33, ${PINK}33)`,
          border: `1px solid ${CYAN}55`,
          color: CYAN,
          marginBottom: 8,
        }}>
          {gLabel(genre_tag)}
        </span>
        <p style={{
          margin: '0 0 4px',
          fontSize: 22,
          fontWeight: 800,
          color: '#fff',
          lineHeight: 1.2,
          textShadow: '0 2px 8px rgba(0,0,0,0.8)',
          WebkitLineClamp: 2,
          display: '-webkit-box',
          WebkitBoxOrient: 'vertical',
          overflow: 'hidden',
        }}>
          {title || `Song #${variant_id}`}
        </p>
        <p style={{ margin: '0 0 10px', fontSize: 14, color: 'rgba(255,255,255,0.7)', fontWeight: 500 }}>
          {artist_name || 'Zeus Beats Artist'}
        </p>
        {/* Made with Zeus Beats branding */}
        <span style={{
          fontSize: 11,
          color: `${CYAN}99`,
          fontWeight: 600,
          letterSpacing: '0.04em',
        }}>
          ⚡ Made with Zeus Beats
        </span>
      </div>

      {/* Action buttons — bottom right column */}
      <div style={{
        position: 'absolute', bottom: 80, right: 16,
        display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 20,
        zIndex: 10,
      }}>
        {/* Like */}
        <ActionBtn
          onClick={onLike}
          icon="❤️"
          label={likeCount > 0 ? String(likeCount) : ''}
          active={isLiked}
          activeColor={PINK}
        />
        {/* Share */}
        <ActionBtn
          onClick={onShare}
          icon={isCopied ? '✓' : '🔗'}
          label={isCopied ? 'Copied! 🎵' : 'Share'}
          active={isCopied}
          activeColor={CYAN}
        />
      </div>
    </div>
  );
});

function ActionBtn({ onClick, icon, label, active, activeColor }) {
  return (
    <button
      onClick={onClick}
      style={{
        background: 'none', border: 'none', cursor: 'pointer',
        display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 4,
        padding: 0,
      }}
    >
      <div style={{
        width: 44, height: 44,
        borderRadius: '50%',
        background: active ? `${activeColor}22` : 'rgba(0,0,0,0.45)',
        border: `1.5px solid ${active ? activeColor : 'rgba(255,255,255,0.25)'}`,
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        fontSize: 20,
        transition: 'all 0.2s',
        boxShadow: active ? `0 0 12px ${activeColor}55` : 'none',
      }}>
        {icon}
      </div>
      {label && (
        <span style={{ color: active ? activeColor : 'rgba(255,255,255,0.7)', fontSize: 11, fontWeight: 600 }}>
          {label}
        </span>
      )}
    </button>
  );
}

/* ── Main page ──────────────────────────────────────────────────────────── */
export default function DiscoverPage() {
  const { token } = useAuth();
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

  const activeSongs = activeTab === 'for_you' ? forYouSongs : songs;

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

  const fetchForYou = useCallback(async () => {
    if (!token || forYouFetched) return;
    setForYouLoading(true);
    try {
      const r = await fetch(`${BACKEND_URL}/api/discover/for-you`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!r.ok) return;
      const d = await r.json();
      const s = d.songs || [];
      setForYouSongs(s);
      setCounts(prev => {
        const n = { ...prev };
        s.forEach(x => { n[x.variant_id] = x.like_count; });
        return n;
      });
      setForYouFetched(true);
    } catch (e) {
      console.error('for-you:', e);
    } finally {
      setForYouLoading(false);
    }
  }, [token, forYouFetched]);

  const handleTabChange = (tab) => {
    if (tab === 'for_you' && !token) { setSignupPrompt(true); return; }
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
          if (activeTab === 'trending' && idx >= activeSongs.length - 3) fetchPage();
        } else {
          if (vid) vid.pause();
          if (aud) { aud.pause(); aud.currentTime = 0; }
        }
      });
    }, { threshold: 0.65 });

    Object.values(slideRefs.current).forEach(el => { if (el) obs.observe(el); });
    return () => obs.disconnect();
  }, [activeSongs, activeTab, fetchPage, token]);

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
        else audioManager.play(aud, songs[idx]?.variant_id);
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

  return (
    <div style={{ background: BG, height: '100svh', width: '100vw', overflow: 'hidden', position: 'relative' }}>

      {/* Fixed header */}
      <div style={{
        position: 'fixed', top: 0, left: 0, right: 0, zIndex: 200,
        padding: '12px 20px',
        display: 'flex', alignItems: 'center', justifyContent: 'space-between',
        background: 'linear-gradient(to bottom, rgba(0,0,0,0.85) 0%, transparent 100%)',
        pointerEvents: 'none',
      }}>
        {/* Logo — taps to landing page */}
        <Link to="/" style={{
          color: CYAN, textDecoration: 'none', fontSize: 17, fontWeight: 800,
          letterSpacing: '-0.02em', pointerEvents: 'auto',
          textShadow: `0 0 16px ${CYAN}88`,
        }}>
          ⚡ Zeus Beats
        </Link>

        <div style={{ display: 'flex', gap: 10, alignItems: 'center', pointerEvents: 'auto' }}>
          {/* Mute toggle */}
          <button
            onClick={toggleMute}
            style={{
              background: muted ? 'rgba(255,255,255,0.08)' : `${CYAN}22`,
              border: `1px solid ${muted ? 'rgba(255,255,255,0.2)' : CYAN}`,
              borderRadius: 20, padding: '5px 14px',
              color: muted ? 'rgba(255,255,255,0.7)' : CYAN,
              cursor: 'pointer', fontSize: 13, fontWeight: 600,
              transition: 'all 0.2s',
              boxShadow: muted ? 'none' : `0 0 10px ${CYAN}44`,
            }}
          >
            {muted ? '🔇 Tap to hear' : '🔊 On'}
          </button>

          {/* Make Your Own CTA */}
          <button
            onClick={() => navigate('/register')}
            style={{
              background: CYAN,
              color: '#000',
              fontFamily: 'Orbitron, sans-serif',
              fontSize: '12px',
              fontWeight: '700',
              padding: '10px 16px',
              borderRadius: '20px',
              border: 'none',
              cursor: 'pointer',
              boxShadow: `0 0 16px ${CYAN}66`,
              letterSpacing: '0.02em',
              whiteSpace: 'nowrap',
            }}
          >
            ⚡ Make Your Own
          </button>
        </div>
      </div>

      {/* Tab bar */}
      <div style={{
        position: 'fixed', top: 54, left: 0, right: 0, zIndex: 199,
        display: 'flex', justifyContent: 'center',
        pointerEvents: 'auto',
      }}>
        {[['trending', '🔥 Trending'], ['for_you', '✨ For You']].map(([tab, label]) => (
          <button
            key={tab}
            onClick={() => handleTabChange(tab)}
            style={{
              background: 'none', border: 'none',
              borderBottom: `2px solid ${activeTab === tab ? CYAN : 'transparent'}`,
              color: activeTab === tab ? CYAN : 'rgba(255,255,255,0.45)',
              fontSize: 13, fontWeight: 700, padding: '6px 22px',
              cursor: 'pointer', transition: 'all 0.18s',
              textShadow: activeTab === tab ? `0 0 10px ${CYAN}88` : 'none',
            }}
          >
            {label}
          </button>
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
        {activeTab === 'for_you' && forYouLoading && (
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

        {/* For You empty state */}
        {activeTab === 'for_you' && !forYouLoading && forYouFetched && forYouSongs.length === 0 && (
          <div style={{
            height: '100svh', scrollSnapAlign: 'start',
            display: 'flex', flexDirection: 'column',
            alignItems: 'center', justifyContent: 'center', gap: 16, padding: 32,
          }}>
            <p style={{ color: '#555', fontSize: 16, textAlign: 'center' }}>
              Like some songs on Trending to get personalised picks ❤️
            </p>
          </div>
        )}

        {activeSongs.map((song, idx) => (
          <SongSlide
            key={song.variant_id}
            song={song}
            idx={idx}
            muted={muted}
            isLiked={liked.has(song.variant_id)}
            likeCount={counts[song.variant_id] || 0}
            isCopied={copied === song.variant_id}
            onLike={() => handleLike(song.variant_id)}
            onShare={() => handleShare(song.variant_id)}
            onSlideRef={el => { slideRefs.current[idx] = el; }}
            onVideoRef={el => { videoRefs.current[idx] = el; }}
            onAudioRef={el => { audioRefs.current[idx] = el; }}
          />
        ))}

        <style>{`@keyframes spin { to { transform: rotate(360deg); } } @keyframes videoFade { 0% { opacity: 1; } 85% { opacity: 1; } 95% { opacity: 0.3; } 100% { opacity: 1; } } .discover-video { animation: videoFade 5s ease-in-out infinite; }`}</style>

        {activeTab === 'trending' && loading && (
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

        {activeTab === 'trending' && !hasMore && !loading && songs.length === 0 && (
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
                background: `linear-gradient(90deg, ${CYAN}, ${PINK})`,
                color: '#000', fontWeight: 800, fontSize: 15,
                border: 'none', cursor: 'pointer',
              }}
            >
              Make your own ⚡
            </button>
          </div>
        )}

        {activeTab === 'trending' && !hasMore && !loading && songs.length > 0 && (
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
                background: `linear-gradient(90deg, ${CYAN}, ${PINK})`,
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
                background: `linear-gradient(90deg, ${CYAN}, ${PINK})`,
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
