import { useEffect, useState, useRef, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../../contexts/AuthContext';
import { BACKEND_URL } from '../../brand';

function resolveUrl(url) {
  if (!url) return null;
  return url.startsWith('http') ? url : `${BACKEND_URL}${url}`;
}

function fmtTime(s) {
  if (!isFinite(s) || s < 0) return '0:00';
  const m = Math.floor(s / 60);
  const ss = String(Math.floor(s % 60)).padStart(2, '0');
  return `${m}:${ss}`;
}

// ── Full-screen story/song player ──────────────────────────────────────────
function StoryPlayer({ item, onClose }) {
  const [isPlaying, setIsPlaying] = useState(false);
  const [currentTime, setCurrentTime] = useState(0);
  const [duration, setDuration] = useState(0);
  const [activeCue, setActiveCue] = useState(null);
  const [cues, setCues] = useState(null);
  const audioRef = useRef(null);
  const isStory = item.genre_tag === 'kids_story';
  const hasSubtitles = isStory && !!item.subtitles_url;

  // Load audio + subtitles on mount
  useEffect(() => {
    const url = resolveUrl(item.mp3_url);
    if (!url) return;

    const a = new Audio(url);
    audioRef.current = a;

    a.onloadedmetadata = () => setDuration(a.duration);
    a.ontimeupdate = () => setCurrentTime(a.currentTime);
    a.onended = () => { setIsPlaying(false); setCurrentTime(0); };

    // Play immediately
    a.play().then(() => setIsPlaying(true)).catch(() => {});

    // Load subtitles
    if (item.subtitles_url) {
      fetch(resolveUrl(item.subtitles_url))
        .then(r => r.ok ? r.json() : null)
        .then(data => { if (data) setCues(data); })
        .catch(() => {});
    }

    return () => {
      a.pause();
      a.ontimeupdate = null;
      a.onended = null;
      audioRef.current = null;
    };
  }, [item]);

  // Track active cue — only update, never clear (keeps last sentence visible)
  useEffect(() => {
    if (!cues || !cues.length) return;
    const cue = cues.find(s => currentTime >= s.start && currentTime < s.end);
    if (cue) setActiveCue(cue);
  }, [currentTime, cues]);

  const togglePlay = () => {
    const a = audioRef.current;
    if (!a) return;
    if (a.paused) { a.play(); setIsPlaying(true); }
    else          { a.pause(); setIsPlaying(false); }
  };

  const skip = (secs) => {
    const a = audioRef.current;
    if (!a) return;
    a.currentTime = Math.max(0, Math.min(duration || 0, a.currentTime + secs));
  };

  const seek = (e) => {
    const a = audioRef.current;
    if (!a) return;
    const t = Number(e.target.value);
    a.currentTime = t;
    setCurrentTime(t);
  };

  const pct = duration > 0 ? (currentTime / duration) * 100 : 0;

  return (
    <div style={{
      position: 'fixed', inset: 0, zIndex: 200,
      background: 'linear-gradient(175deg, #12083c 0%, #251270 28%, #422aaa 55%, #7040d8 80%, #9060f0 100%)',
      display: 'flex', flexDirection: 'column',
      fontFamily: "'Nunito', ui-rounded, system-ui, sans-serif",
      overflow: 'hidden',
    }}>
      {/* Top bar */}
      <div style={{
        display: 'flex', alignItems: 'center', padding: '14px 20px 10px',
        flexShrink: 0,
      }}>
        <button
          onClick={onClose}
          style={{
            background: 'rgba(255,255,255,0.7)', border: '1px solid rgba(0,0,0,0.1)',
            borderRadius: 20, padding: '6px 14px', cursor: 'pointer',
            fontFamily: 'inherit', fontWeight: 700, fontSize: 13, color: '#475569',
          }}
        >
          ← Library
        </button>
        <div style={{
          marginLeft: 'auto', fontSize: 11, fontWeight: 700, color: 'rgba(255,255,255,0.85)',
          background: isStory ? 'rgba(167,139,250,0.3)' : 'rgba(251,209,85,0.25)',
          border: `1px solid ${isStory ? 'rgba(167,139,250,0.5)' : 'rgba(251,209,85,0.5)'}`,
          borderRadius: 12, padding: '4px 10px',
        }}>
          {isStory ? '📖 Story' : '🎵 Song'}
        </div>
      </div>

      {/* Cover art */}
      <div style={{ flexShrink: 0, padding: '0 24px', display: 'flex', justifyContent: 'center' }}>
        {item.image_url ? (
          <img
            src={item.image_url}
            alt={item.title}
            style={{
              width: '100%', maxWidth: hasSubtitles ? 200 : 280,
              aspectRatio: '1/1', objectFit: 'cover',
              borderRadius: 24, boxShadow: '0 12px 40px rgba(0,0,0,0.15)',
              display: 'block',
            }}
          />
        ) : (
          <div style={{
            width: hasSubtitles ? 200 : 280, aspectRatio: '1/1',
            borderRadius: 24, boxShadow: '0 12px 40px rgba(0,0,0,0.12)',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            fontSize: hasSubtitles ? 72 : 96,
            background: isStory
              ? 'linear-gradient(135deg, #a78bfa 0%, #f472b6 100%)'
              : 'linear-gradient(135deg, #fbd155 0%, #ff6b6b 100%)',
          }}>
            {isStory ? '📖' : '🎵'}
          </div>
        )}
      </div>

      {/* Title */}
      <div style={{ textAlign: 'center', padding: '14px 24px 0', flexShrink: 0 }}>
        <h2 style={{
          margin: 0, fontSize: hasSubtitles ? 18 : 22, fontWeight: 900,
          color: '#ffffff', lineHeight: 1.2,
        }}>
          {item.title || (isStory ? 'My Story' : 'My Song')}
        </h2>
      </div>

      {/* Subtitle panel — foreign language stories only */}
      {hasSubtitles && (
        <div style={{
          flex: 1, margin: '14px 20px 8px', borderRadius: 20,
          background: 'rgba(255,255,255,0.75)',
          border: '2px solid rgba(167,139,250,0.25)',
          boxShadow: '0 4px 20px rgba(167,139,250,0.12)',
          display: 'flex', flexDirection: 'column',
          alignItems: 'center', justifyContent: 'center',
          padding: '20px 24px', overflow: 'hidden', position: 'relative',
        }}>
          {activeCue ? (
            <>
              {/* Foreign language text — highlighted, large */}
              <div style={{
                fontSize: 22, fontWeight: 800, color: '#1a2b4a',
                textAlign: 'center', lineHeight: 1.45,
                padding: '12px 16px', borderRadius: 14,
                background: 'rgba(251,209,85,0.25)',
                border: '2px solid rgba(251,209,85,0.6)',
                boxShadow: '0 0 0 4px rgba(251,209,85,0.12)',
                marginBottom: 18, width: '100%', boxSizing: 'border-box',
              }}>
                {activeCue.original}
              </div>
              {/* English translation */}
              <div style={{
                fontSize: 17, fontWeight: 700, color: '#475569',
                textAlign: 'center', lineHeight: 1.5,
                padding: '0 8px',
              }}>
                {activeCue.text}
              </div>
            </>
          ) : (
            <div style={{
              fontSize: 32, color: 'rgba(167,139,250,0.4)', textAlign: 'center',
            }}>
              📖
            </div>
          )}
        </div>
      )}

      {/* Spacer for non-subtitle stories/songs */}
      {!hasSubtitles && <div style={{ flex: 1 }} />}

      {/* Controls area */}
      <div style={{ flexShrink: 0, padding: '0 24px 32px' }}>
        {/* Progress bar */}
        <div style={{ marginBottom: 6 }}>
          <div style={{ position: 'relative', height: 6, borderRadius: 6, background: 'rgba(255,255,255,0.18)', marginBottom: 4 }}>
            <div style={{
              position: 'absolute', left: 0, top: 0, bottom: 0,
              width: `${pct}%`, borderRadius: 6,
              background: isStory
                ? 'linear-gradient(90deg, #a78bfa, #f472b6)'
                : 'linear-gradient(90deg, #fbd155, #ffa726)',
              transition: 'width 0.25s linear',
            }} />
            <input
              type="range" min={0} max={duration || 0} step={0.1}
              value={currentTime}
              onChange={seek}
              style={{
                position: 'absolute', inset: 0, width: '100%', opacity: 0,
                cursor: 'pointer', margin: 0, padding: 0, height: '100%',
              }}
            />
          </div>
          <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 12, fontWeight: 700, color: 'rgba(255,255,255,0.6)' }}>
            <span>{fmtTime(currentTime)}</span>
            <span>{fmtTime(duration)}</span>
          </div>
        </div>

        {/* Playback buttons */}
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 20, marginTop: 8 }}>
          {/* Rewind 10s */}
          <button
            onClick={() => skip(-10)}
            style={{
              width: 52, height: 52, borderRadius: '50%', border: 'none',
              background: 'rgba(255,255,255,0.8)', cursor: 'pointer',
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              boxShadow: '0 2px 8px rgba(0,0,0,0.1)',
              flexDirection: 'column', gap: 0,
            }}
          >
            <span style={{ fontSize: 20 }}>⏮</span>
            <span style={{ fontSize: 9, fontWeight: 800, color: '#64748b', fontFamily: 'inherit', marginTop: -2 }}>10s</span>
          </button>

          {/* Play / Pause */}
          <button
            onClick={togglePlay}
            style={{
              width: 72, height: 72, borderRadius: '50%', border: 'none',
              background: isStory
                ? 'linear-gradient(135deg, #a78bfa 0%, #f472b6 100%)'
                : 'linear-gradient(135deg, #fbd155 0%, #ffa726 100%)',
              cursor: 'pointer', fontSize: 28,
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              boxShadow: isStory
                ? '0 6px 24px rgba(167,139,250,0.5)'
                : '0 6px 24px rgba(251,209,85,0.5)',
              transition: 'transform 0.1s',
            }}
          >
            {isPlaying ? '⏸' : '▶'}
          </button>

          {/* Forward 10s */}
          <button
            onClick={() => skip(10)}
            style={{
              width: 52, height: 52, borderRadius: '50%', border: 'none',
              background: 'rgba(255,255,255,0.8)', cursor: 'pointer',
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              boxShadow: '0 2px 8px rgba(0,0,0,0.1)',
              flexDirection: 'column', gap: 0,
            }}
          >
            <span style={{ fontSize: 20 }}>⏭</span>
            <span style={{ fontSize: 9, fontWeight: 800, color: '#64748b', fontFamily: 'inherit', marginTop: -2 }}>10s</span>
          </button>
        </div>
      </div>
    </div>
  );
}

// ── Library grid ────────────────────────────────────────────────────────────
export default function KidsSongsListPage() {
  const { token } = useAuth();
  const navigate = useNavigate();
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(true);
  const [nowPlaying, setNowPlaying] = useState(null);

  const fetchLibrary = useCallback(async () => {
    if (!token) return;
    try {
      const r = await fetch(`${BACKEND_URL}/api/kids/songs`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!r.ok) {
        console.log('Kids songs fetch failed:', r.status, r.statusText);
        setLoading(false);
        return;
      }
      const data = await r.json();
      console.log('Kids songs fetched:', data);
      setItems(data.items || []);
    } catch (err) {
      console.log('Kids songs fetch error:', err);
      setItems([]);
    } finally {
      setLoading(false);
    }
  }, [token]);

  useEffect(() => { fetchLibrary(); }, [fetchLibrary]);

  const isStory = (item) => item.genre_tag === 'kids_story';

  return (
    <>
      {/* Full-screen player overlay */}
      {nowPlaying && (
        <StoryPlayer item={nowPlaying} onClose={() => setNowPlaying(null)} />
      )}

      {/* Library */}
      <div style={{ flex: 1, padding: '16px 20px 80px', maxWidth: 600, margin: '0 auto', width: '100%' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 20 }}>
          <h2 style={{ margin: 0, fontSize: 20 }}>Your Songs &amp; Stories 🎵</h2>
          <button
            onClick={() => navigate('/kids')}
            style={{ marginLeft: 'auto', background: 'none', border: 'none', color: '#45b7d1', fontWeight: 700, fontSize: 13, cursor: 'pointer' }}
          >
            ← Home
          </button>
        </div>

        {loading && (
          <p style={{ color: 'rgba(255,255,255,0.7)', textAlign: 'center', fontFamily: 'Nunito, sans-serif' }}>
            Loading your songs... ✨
          </p>
        )}

        {!loading && items.length === 0 && (
          <div style={{ textAlign: 'center', padding: '40px 20px' }}>
            <div style={{ fontSize: 56, marginBottom: 12 }}>🎵</div>
            <p style={{ color: 'rgba(255,255,255,0.8)', fontWeight: 600, fontFamily: 'Nunito, sans-serif' }}>
              No songs yet! Go make your first one.
            </p>
            <button className="kids-btn kids-btn-primary" onClick={() => navigate('/kids')} style={{ marginTop: 16 }}>
              Make a Song!
            </button>
          </div>
        )}

        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(155px, 1fr))', gap: 16 }}>
          {items.map(item => {
            const story = isStory(item);
            return (
              <div
                key={item.variant_id}
                className="kids-card"
                style={{ padding: 0, overflow: 'hidden', cursor: 'pointer' }}
                onClick={() => setNowPlaying(item)}
              >
                {item.image_url ? (
                  <img
                    src={item.image_url}
                    alt={item.title}
                    style={{ width: '100%', aspectRatio: '1/1', objectFit: 'cover', display: 'block' }}
                  />
                ) : (
                  <div style={{
                    width: '100%', aspectRatio: '1/1',
                    display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 44,
                    background: story
                      ? 'linear-gradient(135deg, #a78bfa, #f472b6)'
                      : 'linear-gradient(135deg, #fbd155, #ff6b6b)',
                  }}>
                    {story ? '📖' : '🎵'}
                  </div>
                )}
                <div style={{ padding: '10px 12px' }}>
                  <div style={{
                    fontWeight: 800, fontSize: 13, color: '#1a2b4a',
                    overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
                    fontFamily: 'Nunito, sans-serif', marginBottom: 4,
                  }}>
                    {item.title || (story ? 'My Story' : 'My Song')}
                  </div>
                  <div style={{
                    fontSize: 10, fontWeight: 700, fontFamily: 'Nunito, sans-serif',
                    color: story ? '#a78bfa' : '#fbbf24',
                  }}>
                    {story ? '📖 Story' : '🎵 Song'} {item.subtitles_url ? '• 🌍' : ''}
                  </div>
                  <div style={{
                    marginTop: 8, height: 32, borderRadius: 8,
                    background: story ? 'rgba(167,139,250,0.1)' : 'rgba(251,209,85,0.15)',
                    border: `1px solid ${story ? 'rgba(167,139,250,0.25)' : 'rgba(251,209,85,0.35)'}`,
                    display: 'flex', alignItems: 'center', justifyContent: 'center',
                    fontSize: 14, color: story ? '#a78bfa' : '#f59e0b', fontWeight: 700,
                    fontFamily: 'Nunito, sans-serif',
                  }}>
                    ▶ Play
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </>
  );
}
