import { useCallback, useEffect, useRef, useState } from 'react';
import { Link, useLocation } from 'react-router-dom';
import WaveSurfer from 'wavesurfer.js';
import { useAuth } from '../contexts/AuthContext';

const BACKEND_URL = import.meta.env.VITE_BACKEND_URL || '';

const GENRES = ['country','reggae','pop','rock','hiphop','lofi','edm','acoustic','irishjig','irishfolk'];
const GENRE_LABEL = { hiphop:'Hip-hop', lofi:'Lo-Fi', edm:'EDM', irishjig:'Irish Jig', irishfolk:'Irish Folk' };
const gLabel = (g) => GENRE_LABEL[g] || g.charAt(0).toUpperCase() + g.slice(1);

const SONG_PACKS = [
  { pack: 'song_pack_10',  label: 'Buy 10 songs',  price: '£8'  },
  { pack: 'song_pack_50',  label: 'Buy 50 songs',  price: '£30' },
  { pack: 'song_pack_200', label: 'Buy 200 songs', price: '£99' },
];

const PAGE_CSS = `
@keyframes shimmer {
  0%   { transform: translateX(-100%); }
  100% { transform: translateX(200%);  }
}
@keyframes fadeInUp {
  from { opacity: 0; transform: translateY(8px); }
  to   { opacity: 1; transform: translateY(0);   }
}
.song-card-anim { animation: fadeInUp 0.3s ease both; }
.songs-textarea:focus { border-color: rgba(167,139,250,0.4) !important; }
`;

// ── shared style objects ─────────────────────────────────────────────────────
const S = {
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
    gridTemplateColumns: 'repeat(auto-fill, minmax(200px, 1fr))',
    gap: 16,
  },
};

const playBtnStyle = (active, ready) => ({
  width: 32,
  height: 32,
  borderRadius: '50%',
  border: 'none',
  background: active ? '#7c3aed' : 'rgba(167,139,250,0.12)',
  color: '#c4b5fd',
  cursor: ready ? 'pointer' : 'default',
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'center',
  fontSize: 11,
  flexShrink: 0,
  transition: 'background 0.2s',
  opacity: ready ? 1 : 0.35,
});

// ── SkeletonCard ─────────────────────────────────────────────────────────────
function SkeletonCard({ genre }) {
  return (
    <div style={S.card}>
      <div style={{ ...S.artBox, ...S.artPlaceholder, position: 'relative', overflow: 'hidden' }}>
        <span style={{ fontSize: 40, opacity: 0.12 }}>♫</span>
        <div style={{ position: 'absolute', inset: 0, overflow: 'hidden' }}>
          <div style={{
            position: 'absolute', inset: 0,
            background: 'linear-gradient(90deg, transparent 0%, rgba(255,255,255,0.06) 50%, transparent 100%)',
            animation: 'shimmer 1.8s ease-in-out infinite',
          }} />
        </div>
      </div>
      <div style={S.cardBody}>
        <div style={{ height: 40, borderRadius: 4, background: 'rgba(255,255,255,0.04)', marginBottom: 10 }} />
        <div style={{ height: 13, borderRadius: 4, background: 'rgba(255,255,255,0.04)', width: '60%', marginBottom: 10 }} />
        <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
          {genre && <span style={S.pill}>{gLabel(genre)}</span>}
          <span style={{ color: '#444', fontSize: 12 }}>~60s</span>
        </div>
      </div>
    </div>
  );
}

const actionBtnStyle = {
  flex: 1,
  padding: '5px 0',
  borderRadius: 6,
  border: '1px solid rgba(255,255,255,0.08)',
  background: 'transparent',
  color: '#555',
  fontSize: 11,
  fontWeight: 500,
  cursor: 'pointer',
  letterSpacing: '0.2px',
  textAlign: 'center',
  textDecoration: 'none',
  display: 'block',
  transition: 'color 0.15s, border-color 0.15s',
};

// ── SongCard ─────────────────────────────────────────────────────────────────
function SongCard({ variant, title, activeWsRef, canYouTube }) {
  const waveRef = useRef(null);
  const wsRef   = useRef(null);
  const [playing, setPlaying] = useState(false);
  const [wsReady, setWsReady] = useState(false);
  const [copied, setCopied]   = useState(false);

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
    if (activeWsRef.current && activeWsRef.current !== wsRef.current) {
      activeWsRef.current.pause();
    }
    if (playing) {
      wsRef.current.pause();
    } else {
      wsRef.current.play();
      activeWsRef.current = wsRef.current;
    }
  };

  const handleShare = async () => {
    const shareUrl = `${window.location.origin}/songs/share/${variant.variant_id}`;
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

  const dur = variant.duration_seconds;
  const durStr = dur ? `${Math.floor(dur / 60)}:${String(dur % 60).padStart(2, '0')}` : '';
  const isFailed = variant.status === 'failed';
  const safeFilename = `${(title || 'song').replace(/[^a-z0-9]/gi, '-').toLowerCase()}.mp3`;

  return (
    <div className="song-card-anim" style={S.card}>
      {variant.image_url ? (
        <img src={variant.image_url} alt={title} style={S.artBox} />
      ) : (
        <div style={{ ...S.artBox, ...S.artPlaceholder }}>
          <span style={{ fontSize: 40, opacity: 0.2 }}>♫</span>
        </div>
      )}

      <div style={S.cardBody}>
        {isFailed ? (
          <div style={{ height: 40, display: 'flex', alignItems: 'center' }}>
            <span style={{ color: '#f87171', fontSize: 12 }}>Generation failed</span>
          </div>
        ) : (
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 8 }}>
            <button onClick={handlePlay} disabled={!wsReady} style={playBtnStyle(playing, wsReady)}>
              {playing ? '⏸' : '▶'}
            </button>
            <div ref={waveRef} style={{ flex: 1, opacity: wsReady ? 1 : 0.2, transition: 'opacity 0.4s', minWidth: 0 }} />
          </div>
        )}
        <div style={S.cardTitle}>{title || `Song #${variant.variant_id}`}</div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginTop: 6 }}>
          <span style={S.pill}>{gLabel(variant.genre_tag)}</span>
          {durStr && <span style={{ color: '#555', fontSize: 12 }}>{durStr}</span>}
        </div>
        {!isFailed && variant.mp3_url && (
          <div style={{ display: 'flex', gap: 6, marginTop: 10 }}>
            <a href={variant.mp3_url} download={safeFilename} style={actionBtnStyle}>
              ↓ Download
            </a>
            <button onClick={handleShare} style={actionBtnStyle}>
              {copied ? '✓ Copied!' : '↗ Share'}
            </button>
            <button
              disabled
              title={canYouTube ? 'YouTube upload coming soon' : 'Available on Agency plan and above'}
              style={{
                ...actionBtnStyle,
                opacity: canYouTube ? 0.5 : 0.25,
                cursor: 'not-allowed',
              }}
            >
              ▲ YouTube
            </button>
          </div>
        )}
      </div>
    </div>
  );
}

// ── SongsPage ────────────────────────────────────────────────────────────────
export default function SongsPage() {
  const { token, user } = useAuth();
  const location = useLocation();
  const topupSuccess = new URLSearchParams(location.search).get('topup') === 'success';

  const [credits, setCredits]           = useState({ balance: 0, monthly_allowance: 0, is_admin: false, plan: null });
  const [brief, setBrief]               = useState('');
  const [selGenres, setSelGenres]       = useState(new Set());
  const [generating, setGenerating]     = useState(false);
  const [activeJob, setActiveJob]       = useState(null);
  const [library, setLibrary]           = useState([]);
  const [error, setError]               = useState('');
  const [topupLoading, setTopupLoading] = useState(null);

  // Advanced options
  const [showAdvanced, setShowAdvanced]   = useState(false);
  const [vocalGender, setVocalGender]     = useState('');    // '' | 'm' | 'f'
  const [accent, setAccent]               = useState('');    // '' = Default
  const [creativity, setCreativity]       = useState(50);    // 0–100
  const [styleWeight, setStyleWeight]     = useState(70);    // 0–100
  const [tempo, setTempo]                 = useState('');    // '' | 'slow' | 'medium' | 'fast' | 'custom'
  const [tempoBpm, setTempoBpm]           = useState(120);
  const [modelVersion, setModelVersion]   = useState('V5');
  const [explicit, setExplicit]           = useState(false);

  const activeWsRef  = useRef(null);
  const pollTimerRef = useRef(null);

  const isAdmin          = credits.is_admin;
  const canShowExplicit  = isAdmin || ['agency', 'enterprise'].includes(credits.plan);
  const canYouTube       = isAdmin || ['agency', 'enterprise'].includes(credits.plan);
  const cost           = selGenres.size;
  const canAfford      = isAdmin || (credits.balance >= cost && cost > 0);
  const canGenerate    = brief.trim().length > 0 && cost > 0 && canAfford && !generating;
  const creditExceeded = !isAdmin && cost > 0 && cost > credits.balance;

  const fetchCredits = useCallback(async () => {
    try {
      const r = await fetch(`${BACKEND_URL}/api/users/me/song_credits`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (r.ok) setCredits(await r.json());
    } catch (_) {}
  }, [token]);

  const fetchLibrary = useCallback(async () => {
    try {
      const r = await fetch(`${BACKEND_URL}/api/lyrics`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!r.ok) return;
      const { lyrics } = await r.json();
      const groups = await Promise.all(
        (lyrics || []).map(async (lyric) => {
          const vr = await fetch(`${BACKEND_URL}/api/lyrics/${lyric.id}/variants`, {
            headers: { Authorization: `Bearer ${token}` },
          });
          if (!vr.ok) return [];
          const d = await vr.json();
          return (d.variants || []).map((v) => ({ ...v, title: lyric.title, lyric_id: lyric.id }));
        })
      );
      setLibrary(groups.flat().sort((a, b) => b.variant_id - a.variant_id));
    } catch (_) {}
  }, [token]);

  useEffect(() => {
    fetchCredits();
    fetchLibrary();
  }, [fetchCredits, fetchLibrary]);

  // Polling
  useEffect(() => {
    if (!activeJob) return;
    const allSettled = activeJob.variants.every(
      (v) => v.status === 'complete' || v.status === 'failed'
    );
    if (allSettled) {
      Promise.all([fetchCredits(), fetchLibrary()]).then(() => setActiveJob(null));
      return;
    }
    pollTimerRef.current = setTimeout(async () => {
      try {
        const r = await fetch(`${BACKEND_URL}/api/lyrics/${activeJob.lyric_id}/variants`, {
          headers: { Authorization: `Bearer ${token}` },
        });
        if (r.ok) {
          const d = await r.json();
          setActiveJob((prev) =>
            prev
              ? { ...prev, variants: d.variants.map((v) => ({ ...v, title: prev.title })) }
              : null
          );
        }
      } catch (_) {}
    }, 5000);
    return () => clearTimeout(pollTimerRef.current);
  }, [activeJob, token, fetchCredits, fetchLibrary]);

  const handleGenerate = async () => {
    setError('');
    setGenerating(true);
    try {
      const r = await fetch(`${BACKEND_URL}/api/songs/generate`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
        body: JSON.stringify({
          brief: brief.trim(),
          genres: Array.from(selGenres),
          ...(showAdvanced ? {
            vocal_gender: vocalGender || undefined,
            accent: accent || undefined,
            creativity: creativity / 100,
            style_weight: styleWeight / 100,
            tempo: tempo || undefined,
            tempo_bpm: tempo === 'custom' ? tempoBpm : undefined,
            model_version: modelVersion,
            explicit: explicit || undefined,
          } : {}),
        }),
      });
      const d = await r.json();
      if (!r.ok) throw new Error(d.detail || 'Generation failed');
      setActiveJob({
        lyric_id: d.lyric_id,
        title: d.title,
        variants: d.variants.map((v) => ({ ...v, title: d.title })),
      });
      setCredits((p) => ({ ...p, balance: Math.max(0, p.balance - cost) }));
      setBrief('');
      setSelGenres(new Set());
    } catch (e) {
      setError(e.message);
    } finally {
      setGenerating(false);
    }
  };

  const handleTopup = async (pack) => {
    setTopupLoading(pack);
    try {
      const r = await fetch(`${BACKEND_URL}/api/songs/topup`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
        body: JSON.stringify({ pack }),
      });
      const d = await r.json();
      if (!r.ok) throw new Error(d.detail || 'Checkout failed');
      window.location.href = d.url;
    } catch (e) {
      setError(e.message);
      setTopupLoading(null);
    }
  };

  const toggleGenre = (g) =>
    setSelGenres((prev) => {
      const next = new Set(prev);
      next.has(g) ? next.delete(g) : next.add(g);
      return next;
    });

  const { balance, monthly_allowance: allowance } = credits;
  const pct      = isAdmin ? 100 : (allowance > 0 ? Math.min(100, (balance / allowance) * 100) : 0);
  const barColor = isAdmin ? '#a78bfa' : (pct > 30 ? '#a78bfa' : pct > 10 ? '#fbbf24' : '#f87171');

  const activeLyricId    = activeJob?.lyric_id;
  const filteredLibrary  = library.filter((v) => v.lyric_id !== activeLyricId);

  return (
    <>
      <style>{PAGE_CSS}</style>
      <div style={{ background: '#0b0b14', minHeight: '100vh', color: '#f0eeff' }}>

        {/* ── Header ─────────────────────────────────────────────────────── */}
        <header className="dashboard-header">
          <Link to="/dashboard" className="dashboard-logo">
            <span className="zeus-icon">⚡</span>
            <span className="zeus-title">Zeus</span>
          </Link>
          <nav className="dashboard-header-right">
            <Link to="/dashboard" className="dashboard-header-link">Chat</Link>
            <Link to="/songs" className="dashboard-header-link" style={{ fontWeight: 700, color: '#c4b5fd' }}>Songs</Link>
            <Link to="/websites" className="dashboard-header-link">Websites</Link>
            <Link to="/tasks" className="dashboard-header-link">Tasks</Link>
            <Link to="/billing" className="dashboard-header-link">{user?.email}</Link>
          </nav>
        </header>

        {/* ── Credit strip ───────────────────────────────────────────────── */}
        <div style={{ borderBottom: '1px solid rgba(255,255,255,0.05)', padding: '10px 32px' }}>
          <div style={{ maxWidth: 880, margin: '0 auto', display: 'flex', alignItems: 'center', gap: 16 }}>
            <div style={{ flex: 1, height: 5, borderRadius: 3, background: 'rgba(255,255,255,0.07)', overflow: 'hidden' }}>
              <div style={{
                height: '100%',
                width: `${pct}%`,
                background: barColor,
                borderRadius: 3,
                transition: 'width 0.5s, background 0.5s',
              }} />
            </div>
            <span style={{ fontSize: 13, color: '#666', whiteSpace: 'nowrap' }}>
              {isAdmin ? 'Unlimited' : `${balance} / ${allowance} songs`}
            </span>
            {!isAdmin && balance <= 2 && (
              <Link to="/billing" style={{ fontSize: 13, color: barColor, fontWeight: 600, whiteSpace: 'nowrap' }}>
                Top up →
              </Link>
            )}
          </div>
        </div>

        {/* ── Main content ───────────────────────────────────────────────── */}
        <div style={{ maxWidth: 880, margin: '0 auto', padding: '32px 24px 80px' }}>

          {/* Top-up success */}
          {topupSuccess && (
            <div style={{
              background: 'rgba(52,211,153,0.08)',
              border: '1px solid rgba(52,211,153,0.25)',
              borderRadius: 10,
              padding: '12px 18px',
              marginBottom: 24,
              color: '#34d399',
              fontWeight: 600,
              fontSize: 14,
            }}>
              Payment successful — your song credits have been added.
            </div>
          )}

          {/* ── Creation panel ─────────────────────────────────────────── */}
          <div style={{
            background: 'rgba(255,255,255,0.025)',
            border: '1px solid rgba(255,255,255,0.08)',
            borderRadius: 16,
            padding: '28px 28px 24px',
            marginBottom: 12,
          }}>
            <h1 style={{ fontSize: '1.35rem', fontWeight: 700, color: '#f0eeff', marginBottom: 4 }}>
              Create a Song
            </h1>
            <p style={{ color: '#555', fontSize: 14, marginBottom: 22 }}>
              Describe your song — Zeus writes the lyrics, Suno turns them into music.
            </p>

            <textarea
              className="songs-textarea"
              value={brief}
              onChange={(e) => setBrief(e.target.value)}
              placeholder="e.g. An upbeat jingle for a Manchester coffee shop with Friday-morning energy…"
              rows={3}
              style={{
                width: '100%',
                boxSizing: 'border-box',
                background: 'rgba(255,255,255,0.04)',
                border: '1px solid rgba(255,255,255,0.1)',
                borderRadius: 10,
                padding: '12px 14px',
                color: '#f0eeff',
                fontSize: 15,
                resize: 'vertical',
                fontFamily: 'inherit',
                outline: 'none',
                marginBottom: 20,
                transition: 'border-color 0.2s',
              }}
            />

            <p style={{ fontSize: 11, fontWeight: 600, color: '#555', letterSpacing: '0.6px', textTransform: 'uppercase', marginBottom: 10 }}>
              Style
            </p>
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8, marginBottom: 18 }}>
              {GENRES.map((g) => {
                const sel = selGenres.has(g);
                return (
                  <button
                    key={g}
                    onClick={() => toggleGenre(g)}
                    style={{
                      padding: '7px 16px',
                      borderRadius: 20,
                      border: `1px solid ${sel ? '#a78bfa' : 'rgba(255,255,255,0.1)'}`,
                      background: sel ? 'rgba(167,139,250,0.18)' : 'rgba(255,255,255,0.03)',
                      color: sel ? '#c4b5fd' : '#666',
                      fontSize: 13,
                      fontWeight: sel ? 600 : 400,
                      cursor: 'pointer',
                      transition: 'all 0.15s',
                    }}
                  >
                    {gLabel(g)}
                  </button>
                );
              })}
            </div>

            {/* ── Advanced options toggle ─────────────────────────────── */}
            <div style={{ marginBottom: showAdvanced ? 12 : 18 }}>
              <button
                onClick={() => setShowAdvanced((v) => !v)}
                style={{
                  background: 'none',
                  border: 'none',
                  color: '#555',
                  fontSize: 12,
                  cursor: 'pointer',
                  display: 'flex',
                  alignItems: 'center',
                  gap: 4,
                  padding: 0,
                  letterSpacing: '0.2px',
                }}
              >
                Advanced options {showAdvanced ? '▴' : '▾'}
              </button>
            </div>

            {/* ── Advanced panel ─────────────────────────────────────── */}
            {showAdvanced && (
              <div style={{
                background: 'rgba(255,255,255,0.02)',
                border: '1px solid rgba(255,255,255,0.06)',
                borderRadius: 10,
                padding: '18px 20px',
                marginBottom: 18,
                display: 'grid',
                gridTemplateColumns: '1fr 1fr',
                gap: '20px 28px',
              }}>
                {/* Vocal gender */}
                <div>
                  <p style={{ fontSize: 11, fontWeight: 600, color: '#555', letterSpacing: '0.6px', textTransform: 'uppercase', marginBottom: 8 }}>Vocal Gender</p>
                  <div style={{ display: 'flex', gap: 6 }}>
                    {[['', 'Either'], ['m', 'Male'], ['f', 'Female']].map(([val, label]) => (
                      <button
                        key={val}
                        onClick={() => setVocalGender(val)}
                        style={{
                          padding: '5px 12px',
                          borderRadius: 6,
                          border: `1px solid ${vocalGender === val ? '#a78bfa' : 'rgba(255,255,255,0.08)'}`,
                          background: vocalGender === val ? 'rgba(167,139,250,0.15)' : 'transparent',
                          color: vocalGender === val ? '#c4b5fd' : '#555',
                          fontSize: 12,
                          cursor: 'pointer',
                          transition: 'all 0.15s',
                        }}
                      >{label}</button>
                    ))}
                  </div>
                </div>

                {/* Accent */}
                <div>
                  <p style={{ fontSize: 11, fontWeight: 600, color: '#555', letterSpacing: '0.6px', textTransform: 'uppercase', marginBottom: 8 }}>Accent</p>
                  <select
                    value={accent}
                    onChange={(e) => setAccent(e.target.value)}
                    style={{
                      width: '100%',
                      background: 'rgba(255,255,255,0.04)',
                      border: '1px solid rgba(255,255,255,0.1)',
                      borderRadius: 6,
                      padding: '6px 10px',
                      color: accent ? '#c4b5fd' : '#555',
                      fontSize: 13,
                      outline: 'none',
                    }}
                  >
                    <option value="">Default</option>
                    {['British','American (Southern)','Irish','Scottish','Australian','Caribbean','French','Spanish'].map((a) => (
                      <option key={a} value={a}>{a}</option>
                    ))}
                  </select>
                </div>

                {/* Model version */}
                <div>
                  <p style={{ fontSize: 11, fontWeight: 600, color: '#555', letterSpacing: '0.6px', textTransform: 'uppercase', marginBottom: 8 }}>Model</p>
                  <select
                    value={modelVersion}
                    onChange={(e) => setModelVersion(e.target.value)}
                    style={{
                      width: '100%',
                      background: 'rgba(255,255,255,0.04)',
                      border: '1px solid rgba(255,255,255,0.1)',
                      borderRadius: 6,
                      padding: '6px 10px',
                      color: '#c4b5fd',
                      fontSize: 13,
                      outline: 'none',
                    }}
                  >
                    {['V4.5', 'V4.5 Plus', 'V5', 'V5.5'].map((v) => (
                      <option key={v} value={v}>{v}</option>
                    ))}
                  </select>
                </div>

                {/* Creativity slider */}
                <div>
                  <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 8 }}>
                    <p style={{ fontSize: 11, fontWeight: 600, color: '#555', letterSpacing: '0.6px', textTransform: 'uppercase', margin: 0 }}>Creativity</p>
                    <span style={{ fontSize: 11, color: '#a78bfa' }}>{creativity}%</span>
                  </div>
                  <input
                    type="range" min={0} max={100} value={creativity}
                    onChange={(e) => setCreativity(Number(e.target.value))}
                    style={{ width: '100%', accentColor: '#a78bfa', cursor: 'pointer' }}
                  />
                </div>

                {/* Style strength slider */}
                <div>
                  <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 8 }}>
                    <p style={{ fontSize: 11, fontWeight: 600, color: '#555', letterSpacing: '0.6px', textTransform: 'uppercase', margin: 0 }}>Style Strength</p>
                    <span style={{ fontSize: 11, color: '#a78bfa' }}>{styleWeight}%</span>
                  </div>
                  <input
                    type="range" min={0} max={100} value={styleWeight}
                    onChange={(e) => setStyleWeight(Number(e.target.value))}
                    style={{ width: '100%', accentColor: '#a78bfa', cursor: 'pointer' }}
                  />
                </div>

                {/* Tempo */}
                <div style={{ gridColumn: '1 / -1' }}>
                  <p style={{ fontSize: 11, fontWeight: 600, color: '#555', letterSpacing: '0.6px', textTransform: 'uppercase', marginBottom: 8 }}>Tempo</p>
                  <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap', alignItems: 'center' }}>
                    {[['', 'Default'], ['slow', 'Slow'], ['medium', 'Medium'], ['fast', 'Fast'], ['custom', 'Custom BPM']].map(([val, label]) => (
                      <button
                        key={val}
                        onClick={() => setTempo(val)}
                        style={{
                          padding: '5px 12px',
                          borderRadius: 6,
                          border: `1px solid ${tempo === val ? '#a78bfa' : 'rgba(255,255,255,0.08)'}`,
                          background: tempo === val ? 'rgba(167,139,250,0.15)' : 'transparent',
                          color: tempo === val ? '#c4b5fd' : '#555',
                          fontSize: 12,
                          cursor: 'pointer',
                          transition: 'all 0.15s',
                        }}
                      >{label}</button>
                    ))}
                    {tempo === 'custom' && (
                      <input
                        type="number" min={40} max={300} value={tempoBpm}
                        onChange={(e) => setTempoBpm(Number(e.target.value))}
                        style={{
                          width: 72,
                          background: 'rgba(255,255,255,0.04)',
                          border: '1px solid rgba(255,255,255,0.1)',
                          borderRadius: 6,
                          padding: '5px 8px',
                          color: '#c4b5fd',
                          fontSize: 12,
                          outline: 'none',
                        }}
                      />
                    )}
                  </div>
                </div>

                {/* Explicit content — agency / enterprise only */}
                {canShowExplicit && (
                  <div style={{ gridColumn: '1 / -1', borderTop: '1px solid rgba(255,255,255,0.05)', paddingTop: 16 }}>
                    <label style={{ display: 'flex', alignItems: 'center', gap: 10, cursor: 'pointer' }}>
                      <div
                        onClick={() => setExplicit((v) => !v)}
                        style={{
                          width: 36,
                          height: 20,
                          borderRadius: 10,
                          background: explicit ? '#7c3aed' : 'rgba(255,255,255,0.08)',
                          position: 'relative',
                          flexShrink: 0,
                          transition: 'background 0.2s',
                          cursor: 'pointer',
                        }}
                      >
                        <div style={{
                          position: 'absolute',
                          top: 3,
                          left: explicit ? 19 : 3,
                          width: 14,
                          height: 14,
                          borderRadius: '50%',
                          background: '#fff',
                          transition: 'left 0.2s',
                        }} />
                      </div>
                      <span style={{ fontSize: 12, color: explicit ? '#c4b5fd' : '#555', fontWeight: 500 }}>
                        Explicit content
                      </span>
                    </label>
                    {explicit && (
                      <p style={{ fontSize: 11, color: '#f87171', marginTop: 8, lineHeight: 1.5 }}>
                        May include strong language. You are responsible for content generated.
                      </p>
                    )}
                  </div>
                )}
              </div>
            )}

            {/* Cost preview */}
            {cost > 0 ? (
              <p style={{
                fontSize: 13,
                color: creditExceeded ? '#f87171' : '#666',
                marginBottom: 16,
                fontWeight: creditExceeded ? 600 : 400,
              }}>
                {isAdmin ? `Generating ${cost} variant${cost !== 1 ? 's' : ''} (unlimited).` : `Will use ${cost} of your ${balance} remaining credit${balance !== 1 ? 's' : ''}.`}
                {creditExceeded && (
                  <> <Link to="/billing" style={{ color: '#f87171' }}>Top up to continue →</Link></>
                )}
              </p>
            ) : (
              <div style={{ height: 16 }} />
            )}

            <button
              onClick={handleGenerate}
              disabled={!canGenerate}
              style={{
                width: '100%',
                padding: '14px',
                borderRadius: 10,
                border: 'none',
                background: canGenerate
                  ? 'linear-gradient(135deg, #7c3aed 0%, #a855f7 100%)'
                  : 'rgba(255,255,255,0.05)',
                color: canGenerate ? '#fff' : '#444',
                fontSize: 15,
                fontWeight: 700,
                cursor: canGenerate ? 'pointer' : 'default',
                transition: 'all 0.2s',
                letterSpacing: '0.2px',
              }}
            >
              {generating
                ? 'Generating lyrics…'
                : cost > 0
                  ? `Generate — ${cost} credit${cost !== 1 ? 's' : ''}`
                  : 'Select a style to generate'}
            </button>

            {error && (
              <p style={{ color: '#f87171', fontSize: 13, marginTop: 12 }}>{error}</p>
            )}
          </div>

          {/* ── Top-up row ─────────────────────────────────────────────── */}
          <div style={{
            display: 'flex',
            gap: 8,
            flexWrap: 'wrap',
            justifyContent: 'flex-end',
            marginBottom: 44,
            padding: '8px 0',
          }}>
            {SONG_PACKS.map(({ pack, label, price }) => (
              <button
                key={pack}
                onClick={() => handleTopup(pack)}
                disabled={topupLoading !== null}
                style={{
                  padding: '7px 14px',
                  borderRadius: 8,
                  border: '1px solid rgba(255,255,255,0.1)',
                  background: 'transparent',
                  color: '#666',
                  fontSize: 12,
                  cursor: topupLoading ? 'default' : 'pointer',
                }}
              >
                {topupLoading === pack ? 'Redirecting…' : `${label} — ${price}`}
              </button>
            ))}
          </div>

          {/* ── Currently generating ───────────────────────────────────── */}
          {activeJob && (
            <section style={{ marginBottom: 48 }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 14, marginBottom: 20 }}>
                <h2 style={{ fontSize: '0.95rem', fontWeight: 700, color: '#e2d9f3', margin: 0 }}>
                  {activeJob.title}
                </h2>
                <span style={{
                  background: 'rgba(167,139,250,0.1)',
                  color: '#a78bfa',
                  borderRadius: 20,
                  padding: '3px 12px',
                  fontSize: 12,
                  fontWeight: 500,
                }}>
                  Generating — usually ready in 60 seconds
                </span>
              </div>
              <div style={S.grid}>
                {activeJob.variants.map((v) =>
                  v.status === 'complete' || v.status === 'failed' ? (
                    <SongCard
                      key={v.variant_id}
                      variant={v}
                      title={activeJob.title}
                      activeWsRef={activeWsRef}
                      canYouTube={canYouTube}
                    />
                  ) : (
                    <SkeletonCard key={v.variant_id} genre={v.genre_tag} />
                  )
                )}
              </div>
            </section>
          )}

          {/* ── Library ────────────────────────────────────────────────── */}
          {filteredLibrary.length > 0 && (
            <section>
              <h2 style={{ fontSize: '0.95rem', fontWeight: 700, color: '#e2d9f3', marginBottom: 20 }}>
                Your Songs
              </h2>
              <div style={S.grid}>
                {filteredLibrary.map((v) => (
                  <SongCard
                    key={v.variant_id}
                    variant={v}
                    title={v.title}
                    activeWsRef={activeWsRef}
                    canYouTube={canYouTube}
                  />
                ))}
              </div>
            </section>
          )}

          {/* ── Empty state ────────────────────────────────────────────── */}
          {!activeJob && filteredLibrary.length === 0 && (
            <div style={{ textAlign: 'center', padding: '80px 0' }}>
              <div style={{ fontSize: 56, marginBottom: 16, opacity: 0.15 }}>♫</div>
              <p style={{ fontSize: 15, color: '#555' }}>
                No songs yet — create your first one above.
              </p>
            </div>
          )}

        </div>
      </div>
    </>
  );
}
