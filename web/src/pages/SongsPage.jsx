import { useCallback, useEffect, useRef, useState } from 'react';
import { Link, useLocation } from 'react-router-dom';
import WaveSurfer from 'wavesurfer.js';
import { useAuth } from '../contexts/AuthContext';
import { DashboardHeader } from '../components/DashboardHeader';

const BACKEND_URL = import.meta.env.VITE_BACKEND_URL || '';

const GENRES = ['country','reggae','pop','rock','hiphop','lofi','edm','acoustic','irishjig','irishfolk','blues','soul','rnb','bluessoul','drumandbass','grime','ukgarage','jungle','bassline','house','loversrock','ukdrill','kpop','deepsoulblues','niche','ukstreetsoul','classical','indie','techno','technhouse','hyperpop','afrobeats','amapiano','driftphonk','jerseyclub','afroswing','rastadub','deeprotbassline','jazz'];
const GENRE_LABEL = { hiphop:'Hip-hop', lofi:'Lo-Fi', edm:'EDM', irishjig:'Irish Jig', irishfolk:'Irish Folk', rnb:'R&B', bluessoul:'Blues Soul', drumandbass:'D&B', grime:'Grime', ukgarage:'UK Garage', jungle:'Jungle', bassline:'Bassline House', house:'House', loversrock:'Lovers Rock', ukdrill:'UK Drill', kpop:'K-Pop', deepsoulblues:'Deep Soul Blues', ukstreetsoul:'UK Street Soul', technhouse:'Tech House', driftphonk:'Drift Phonk', jerseyclub:'Jersey Club', afroswing:'Afroswing', rastadub:'Rasta Dub', deeprotbassline:'Deeprot Bassline', jazz:'Jazz' };
const gLabel = (g) => GENRE_LABEL[g] || g.charAt(0).toUpperCase() + g.slice(1);

const ACCENT_VOICES = {
  'British':               { lang: 'en-GB', text: 'Hello, welcome to Zeus AI Design, let me create something for you' },
  'American (Southern)':   { lang: 'en-US', text: 'Hey, welcome to Zeus AI Design, let me create something for you' },
  'American (NYC)':        { lang: 'en-US', text: 'Hey, welcome to Zeus AI Design, let me create something for you' },
  'Australian':            { lang: 'en-AU', text: 'G\'day, welcome to Zeus AI Design, let me create something for you' },
  'Irish':                 { lang: 'en-IE', text: 'Ah sure, welcome to Zeus AI Design, let me create something for you' },
  'Scottish':              { lang: 'en-GB', text: 'Och, welcome to Zeus AI Design, let me create something for you' },
  'South African':         { lang: 'en-ZA', text: 'Hello, welcome to Zeus AI Design, let me create something for you' },
  'Indian':                { lang: 'hi-IN', text: 'नमस्ते, Zeus AI Design में आपका स्वागत है' },
  'Nigerian':              { lang: 'en-NG', text: 'Hello, welcome to Zeus AI Design, let me create something for you' },
  'Jamaican':              { lang: 'en-JM', text: 'Greetings, welcome to Zeus AI Design, let me create something for you' },
  'French':                { lang: 'fr-FR', text: 'Bonjour, bienvenue sur Zeus AI Design, laissez-moi créer quelque chose pour vous' },
  'Spanish':               { lang: 'es-ES', text: 'Hola, bienvenido a Zeus AI Design, déjame crear algo para ti' },
  'Italian':               { lang: 'it-IT', text: 'Ciao, benvenuto su Zeus AI Design, lasciami creare qualcosa per te' },
  'German':                { lang: 'de-DE', text: 'Hallo, willkommen bei Zeus AI Design, lass mich etwas für dich erstellen' },
  'Portuguese':            { lang: 'pt-PT', text: 'Olá, bem-vindo ao Zeus AI Design, deixa-me criar algo para ti' },
  'Brazilian':             { lang: 'pt-BR', text: 'Olá, bem-vindo ao Zeus AI Design, deixa eu criar algo para você' },
  'Japanese':              { lang: 'ja-JP', text: 'こんにちは、Zeus AI Designへようこそ、何か作りましょう' },
  'Korean':                { lang: 'ko-KR', text: '안녕하세요, Zeus AI Design에 오신 것을 환영합니다' },
  'Mandarin':              { lang: 'zh-CN', text: '你好，欢迎来到Zeus AI Design，让我为你创作些东西' },
  'Arabic':                { lang: 'ar-SA', text: 'مرحباً، أهلاً بك في Zeus AI Design' },
  'Russian':               { lang: 'ru-RU', text: 'Привет, добро пожаловать в Zeus AI Design, давайте создадим что-нибудь для вас' },
  'Welsh':                 { lang: 'cy-GB', text: 'Helo, croeso i Zeus AI Design, gadewch i mi greu rhywbeth i chi' },
};

if (typeof window !== 'undefined') {
  window.speechSynthesis.onvoiceschanged = () => window.speechSynthesis.getVoices();
}

function previewAccent(accentLabel) {
  window.speechSynthesis.cancel();
  const voices = window.speechSynthesis.getVoices();
  const config = ACCENT_VOICES[accentLabel] || { lang: 'en-GB', text: 'Welcome to Zeus AI Design' };
  const utterance = new SpeechSynthesisUtterance(config.text);
  utterance.lang = config.lang;
  const match = voices.find(v => v.lang.startsWith(config.lang.substring(0, 5)));
  if (match) utterance.voice = match;
  window.speechSynthesis.speak(utterance);
}

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
.avatar-thumb:hover { border-color: #a78bfa !important; opacity: 1 !important; }
.genre-pill:hover { border-color: rgba(255,255,255,0.65) !important; background: rgba(255,255,255,0.13) !important; color: #fff !important; }
.genre-pill--sel:hover { background: #6d28d9 !important; }
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
function SongCard({
  variant, title, activeWsRef,
  canYouTube, ytConnected, ytStatus: ytSt, ytUrl, onYouTubeClick,
  canDid, didSt, videoUrl, onAvatarClick, videoCredits, didPlanOk, isAdmin,
  onDelete, deleting, musicVideoUrl,
}) {
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

  // ── Avatar video button state ──────────────────────────────────────────────
  let avatarBtn;
  if (!didPlanOk) {
    avatarBtn = (
      <button disabled title="Available on Agency plan and above"
        style={{ ...actionBtnStyle, opacity: 0.25, cursor: 'not-allowed' }}>
        ◉ Avatar
      </button>
    );
  } else if (!isAdmin && videoCredits === 0) {
    avatarBtn = (
      <button disabled title="No avatar video credits remaining"
        style={{ ...actionBtnStyle, opacity: 0.35, cursor: 'not-allowed', color: '#f87171' }}>
        ◉ No credits
      </button>
    );
  } else if (didSt === 'processing') {
    avatarBtn = (
      <button disabled style={{ ...actionBtnStyle, opacity: 0.55, cursor: 'default' }}>
        Making…
      </button>
    );
  } else if (didSt === 'done' && videoUrl) {
    avatarBtn = (
      <button onClick={onAvatarClick}
        style={{ ...actionBtnStyle, color: '#a78bfa', borderColor: 'rgba(167,139,250,0.3)' }}>
        ◉ Redo
      </button>
    );
  } else {
    avatarBtn = (
      <button onClick={onAvatarClick}
        style={{ ...actionBtnStyle, color: didSt === 'error' ? '#f87171' : '#555' }}>
        {didSt === 'error' ? 'Retry' : '◉ Avatar'}
      </button>
    );
  }

  // ── YouTube button state ───────────────────────────────────────────────────
  let ytBtn;
  if (!canYouTube) {
    ytBtn = (
      <button disabled title="Available on Agency plan and above"
        style={{ ...actionBtnStyle, opacity: 0.25, cursor: 'not-allowed' }}>
        ▲ YouTube
      </button>
    );
  } else if (ytSt === 'done' && ytUrl) {
    ytBtn = (
      <a href={ytUrl} target="_blank" rel="noopener noreferrer"
        style={{ ...actionBtnStyle, color: '#a78bfa', borderColor: 'rgba(167,139,250,0.3)' }}>
        ▶ View on YT
      </a>
    );
  } else if (ytSt === 'uploading') {
    ytBtn = (
      <button disabled style={{ ...actionBtnStyle, opacity: 0.55, cursor: 'default' }}>
        Uploading…
      </button>
    );
  } else if (!ytConnected) {
    ytBtn = (
      <button onClick={onYouTubeClick} style={{ ...actionBtnStyle, color: '#a78bfa' }}>
        + Connect YT
      </button>
    );
  } else {
    ytBtn = (
      <button onClick={onYouTubeClick}
        style={{ ...actionBtnStyle, color: ytSt === 'error' ? '#f87171' : '#555' }}>
        {ytSt === 'error' ? 'Retry YT' : '▲ YouTube'}
      </button>
    );
  }

  return (
    <div className="song-card-anim" style={S.card}>
      {musicVideoUrl ? (
        <video
          src={musicVideoUrl}
          autoPlay
          muted
          loop
          playsInline
          style={S.artBox}
        />
      ) : variant.image_url ? (
        <img src={variant.image_url} alt={title} style={S.artBox} />
      ) : (
        <div style={{ ...S.artBox, ...S.artPlaceholder }}>
          <span style={{ fontSize: 40, opacity: 0.2 }}>♫</span>
        </div>
      )}

      {/* Inline video player — shown when avatar video is ready */}
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
          <>
            {/* Row 1: Download + Share */}
            <div style={{ display: 'flex', gap: 6, marginTop: 10 }}>
              <a href={variant.mp3_url} download={safeFilename} style={actionBtnStyle}>
                ↓ Download
              </a>
              <button onClick={handleShare} style={actionBtnStyle}>
                {copied ? '✓ Copied!' : '↗ Share'}
              </button>
            </div>
            {/* Row 2: YouTube + Avatar Video */}
            <div style={{ display: 'flex', gap: 6, marginTop: 6 }}>
              {ytBtn}
              {avatarBtn}
            </div>
            {/* Row 3: Delete */}
            <div style={{ display: 'flex', marginTop: 6 }}>
              <button
                onClick={onDelete}
                disabled={deleting}
                style={{
                  ...actionBtnStyle,
                  color: deleting ? '#444' : '#555',
                  cursor: deleting ? 'default' : 'pointer',
                  opacity: deleting ? 0.5 : 1,
                }}
              >
                {deleting ? 'Deleting…' : '✕ Delete'}
              </button>
            </div>
          </>
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

  const [credits, setCredits]           = useState({ balance: 0, monthly_allowance: 0, is_admin: false, plan: null, youtube_connected: false, video_credits: 0, video_monthly_allowance: 0 });
  const [brief, setBrief]               = useState('');
  const [selGenres, setSelGenres]       = useState(new Set());
  const [generating, setGenerating]     = useState(false);
  const [activeJob, setActiveJob]       = useState(null);
  const [library, setLibrary]           = useState([]);
  const [error, setError]               = useState('');
  const [topupLoading, setTopupLoading] = useState(null);

  // Advanced options
  const [showAdvanced, setShowAdvanced]   = useState(() => window.innerWidth >= 600);
  const [vocalGender, setVocalGender]     = useState('');
  const [accent, setAccent]               = useState('');
  const [creativity, setCreativity]       = useState(50);
  const [styleWeight, setStyleWeight]     = useState(70);
  const [tempo, setTempo]                 = useState('');
  const [tempoBpm, setTempoBpm]           = useState(120);
  const [modelVersion, setModelVersion]   = useState('V5');
  const [explicit, setExplicit]           = useState(false);
  const [vocals, setVocals]               = useState(true);
  const [songTitle, setSongTitle]         = useState('');

  // YouTube upload state
  const [ytStatus, setYtStatus]   = useState({});
  const [ytUrls, setYtUrls]       = useState({});
  const [ytModal, setYtModal]     = useState(null);
  const [ytPrivacy, setYtPrivacy] = useState('unlisted');

  // Inspired-by artist state
  const [inspiredBy, setInspiredBy]               = useState('');
  const [artistDescriptors, setArtistDescriptors] = useState('');
  const [artistLoading, setArtistLoading]         = useState(false);

  // D-ID avatar video state
  const [avatarModal, setAvatarModal]             = useState(null);
  const [avatars, setAvatars]                     = useState([]);
  const [selectedAvatarUrl, setSelectedAvatarUrl] = useState(null);
  const [uploadingPhoto, setUploadingPhoto]       = useState(false);
  const [avatarSubmitting, setAvatarSubmitting]   = useState(false);
  const [didStatus, setDidStatus]                 = useState({});
  const [videoUrls, setVideoUrls]                 = useState({});
  const [musicVideoUrls, setMusicVideoUrls]       = useState({});

  // Portrait generation state
  const [portraitGenerating, setPortraitGenerating] = useState(false);
  const [portraitJobId, setPortraitJobId]           = useState(null);
  const [portraitImageUrl, setPortraitImageUrl]     = useState(null);
  const [portraitTimedOut, setPortraitTimedOut]     = useState(false);

  // Custom lyrics mode
  const [useCustomLyrics, setUseCustomLyrics] = useState(false);
  const [customLyrics, setCustomLyrics]       = useState('');

  // Delete state
  const [deletingVariants, setDeletingVariants]     = useState(new Set());

  const activeWsRef     = useRef(null);
  const pollTimerRef    = useRef(null);
  const photoInputRef   = useRef(null);
  const portraitPollRef = useRef(null);

  const isAdmin          = credits.is_admin;
  const isMusicPlan      = ['music_starter', 'music_pro', 'music_agency'].includes(credits.plan);
  const canShowExplicit  = isAdmin || ['agency', 'enterprise'].includes(credits.plan);
  const canYouTube       = isAdmin || ['agency', 'enterprise'].includes(credits.plan) || isMusicPlan;
  const didPlanOk        = isAdmin || ['agency', 'enterprise', 'music_pro', 'music_agency'].includes(credits.plan);
  const canDid           = didPlanOk && (isAdmin || credits.video_credits > 0);
  const youtubeConnected = credits.youtube_connected;
  const ytConnectedParam = new URLSearchParams(location.search).get('youtube');
  const cost           = selGenres.size;
  const canAfford      = isAdmin || (credits.balance >= cost && cost > 0);
  const briefReady     = useCustomLyrics ? customLyrics.trim().length > 0 : brief.trim().length > 0;
  const canGenerate    = briefReady && cost > 0 && canAfford && !generating;
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
      const flat = groups.flat().sort((a, b) => b.variant_id - a.variant_id);
      setLibrary(flat);

      // Sync D-ID state from DB — DB wins over stale UI state
      const newDidSt = {};
      const newVidUrls = {};
      for (const v of flat) {
        if (v.video_url) {
          newDidSt[v.variant_id] = 'done';
          newVidUrls[v.variant_id] = v.video_url;
        } else if (v.did_job_id) {
          newDidSt[v.variant_id] = 'processing';
        }
      }
      setDidStatus((prev) => ({ ...prev, ...newDidSt }));
      setVideoUrls((prev) => ({ ...prev, ...newVidUrls }));

      // Sync YouTube URLs from DB
      const newYtUrls = {};
      const newYtSt = {};
      for (const v of flat) {
        if (v.youtube_url) {
          newYtUrls[v.variant_id] = v.youtube_url;
          newYtSt[v.variant_id] = 'done';
        }
      }
      setYtUrls((prev) => ({ ...prev, ...newYtUrls }));
      setYtStatus((prev) => ({ ...prev, ...newYtSt }));

      // Sync Kling music video URLs from DB
      const newMusicVideoUrls = {};
      for (const v of flat) {
        if (v.music_video_url) newMusicVideoUrls[v.variant_id] = v.music_video_url;
      }
      setMusicVideoUrls((prev) => ({ ...prev, ...newMusicVideoUrls }));
    } catch (_) {}
  }, [token]);

  useEffect(() => {
    fetchCredits();
    fetchLibrary();
  }, [fetchCredits, fetchLibrary]);

  // Song generation polling (5s)
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

  // D-ID avatar video polling (10s) — only while jobs are in flight
  useEffect(() => {
    const processingIds = Object.entries(didStatus)
      .filter(([, st]) => st === 'processing')
      .map(([id]) => Number(id));
    if (processingIds.length === 0) return;

    const timer = setTimeout(async () => {
      for (const vid of processingIds) {
        try {
          const r = await fetch(`${BACKEND_URL}/api/songs/variants/${vid}/did-status`, {
            headers: { Authorization: `Bearer ${token}` },
          });
          if (!r.ok) continue;
          const d = await r.json();
          if (d.status === 'done' && d.video_url) {
            setDidStatus((prev) => ({ ...prev, [vid]: 'done' }));
            setVideoUrls((prev) => ({ ...prev, [vid]: d.video_url }));
          } else if (d.status === 'error') {
            setDidStatus((prev) => ({ ...prev, [vid]: 'error' }));
          }
        } catch (_) {}
      }
    }, 10000);
    return () => clearTimeout(timer);
  }, [didStatus, token]);

  // Portrait generation polling (5s, max 36 polls = 3 min)
  useEffect(() => {
    if (!portraitJobId) return;
    let pollCount = 0;
    const poll = async () => {
      pollCount += 1;
      if (pollCount > 36) {
        setPortraitGenerating(false);
        setPortraitJobId(null);
        setPortraitTimedOut(true);
        return;
      }
      try {
        const r = await fetch(`${BACKEND_URL}/api/did/portrait-status/${portraitJobId}`, {
          headers: { Authorization: `Bearer ${token}` },
        });
        if (!r.ok) { portraitPollRef.current = setTimeout(poll, 5000); return; }
        const d = await r.json();
        if (d.status === 'completed' && d.image_url) {
          setPortraitImageUrl(d.image_url);
          setSelectedAvatarUrl(d.image_url);
          setPortraitGenerating(false);
          setPortraitJobId(null);
        } else if (d.status === 'failed') {
          setPortraitGenerating(false);
          setPortraitJobId(null);
          setError('Portrait generation failed — try again');
        } else {
          portraitPollRef.current = setTimeout(poll, 5000);
        }
      } catch (_) {
        portraitPollRef.current = setTimeout(poll, 5000);
      }
    };
    portraitPollRef.current = setTimeout(poll, 5000);
    return () => { if (portraitPollRef.current) clearTimeout(portraitPollRef.current); };
  }, [portraitJobId, token]);

  const handleGenerate = async () => {
    setError('');
    setGenerating(true);
    try {
      let body;
      if (useCustomLyrics) {
        // Custom lyrics path: save lyrics first, then generate variants
        body = JSON.stringify({
          custom_lyrics: customLyrics.trim(),
          genres: Array.from(selGenres),
          song_title: songTitle.trim() || undefined,
          ...(showAdvanced ? {
            vocal_gender: vocalGender || undefined,
            accent: accent || undefined,
            creativity: creativity / 100,
            style_weight: styleWeight / 100,
            tempo: tempo || undefined,
            tempo_bpm: tempo === 'custom' ? tempoBpm : undefined,
            model_version: modelVersion,
            explicit: explicit || undefined,
            instrumental: !vocals || undefined,
          } : {}),
        });
      } else {
        body = JSON.stringify({
          brief: brief.trim(),
          genres: Array.from(selGenres),
          inspired_by_descriptors: artistDescriptors || undefined,
          song_title: songTitle.trim() || undefined,
          ...(showAdvanced ? {
            vocal_gender: vocalGender || undefined,
            accent: accent || undefined,
            creativity: creativity / 100,
            style_weight: styleWeight / 100,
            tempo: tempo || undefined,
            tempo_bpm: tempo === 'custom' ? tempoBpm : undefined,
            model_version: modelVersion,
            explicit: explicit || undefined,
            instrumental: !vocals || undefined,
          } : {}),
        });
      }

      const r = await fetch(`${BACKEND_URL}/api/songs/generate`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
        body,
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
      setCustomLyrics('');
      setSongTitle('');
      setSelGenres(new Set());
      setInspiredBy('');
      setArtistDescriptors('');
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

  const handleArtistLookup = async () => {
    const name = inspiredBy.trim();
    if (!name) { setArtistDescriptors(''); return; }
    setArtistLoading(true);
    try {
      const r = await fetch(`${BACKEND_URL}/api/songs/artist-style`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
        body: JSON.stringify({ artist_name: name }),
      });
      const d = await r.json();
      if (r.ok) setArtistDescriptors(d.style_descriptors || '');
      else setArtistDescriptors('');
    } catch (_) {
      setArtistDescriptors('');
    } finally {
      setArtistLoading(false);
    }
  };

  const handleYouTubeClick = (variant) => {
    if (!canYouTube) return;
    if (!youtubeConnected) {
      window.location.href = `${BACKEND_URL}/api/youtube/auth?token=${token}`;
      return;
    }
    setYtModal(variant);
  };

  const handleYouTubeUpload = async () => {
    if (!ytModal) return;
    const vId = ytModal.variant_id;
    const vTitle = ytModal.title;
    setYtModal(null);
    setYtStatus((prev) => ({ ...prev, [vId]: 'uploading' }));
    try {
      const r = await fetch(`${BACKEND_URL}/api/songs/variants/${vId}/upload-youtube`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
        body: JSON.stringify({ privacy: ytPrivacy, title: vTitle }),
      });
      const d = await r.json();
      if (!r.ok) throw new Error(d.detail || 'Upload failed');
      setYtStatus((prev) => ({ ...prev, [vId]: 'done' }));
      setYtUrls((prev) => ({ ...prev, [vId]: d.youtube_url }));
    } catch (_) {
      setYtStatus((prev) => ({ ...prev, [vId]: 'error' }));
    }
  };

  // ── D-ID handlers ──────────────────────────────────────────────────────────

  const closeAvatarModal = () => {
    setAvatarModal(null);
    setPortraitGenerating(false);
    setPortraitJobId(null);
    setPortraitImageUrl(null);
    setPortraitTimedOut(false);
    if (portraitPollRef.current) clearTimeout(portraitPollRef.current);
  };

  const handleAvatarClick = async (variant) => {
    if (!canDid) return;
    setSelectedAvatarUrl(null);
    setPortraitGenerating(false);
    setPortraitJobId(null);
    setPortraitImageUrl(null);
    setPortraitTimedOut(false);
    setAvatarModal(variant);
    if (avatars.length === 0) {
      try {
        const r = await fetch(`${BACKEND_URL}/api/did/avatars`, {
          headers: { Authorization: `Bearer ${token}` },
        });
        if (r.ok) {
          const d = await r.json();
          setAvatars(d.avatars || []);
        }
      } catch (_) {}
    }
  };

  const handlePhotoUpload = async (e) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setUploadingPhoto(true);
    try {
      const fd = new FormData();
      fd.append('file', file);
      const r = await fetch(`${BACKEND_URL}/api/avatars/upload`, {
        method: 'POST',
        headers: { Authorization: `Bearer ${token}` },
        body: fd,
      });
      const d = await r.json();
      if (!r.ok) throw new Error(d.detail || 'Upload failed');
      setSelectedAvatarUrl(d.url);
    } catch (err) {
      setError(err.message);
    } finally {
      setUploadingPhoto(false);
      if (photoInputRef.current) photoInputRef.current.value = '';
    }
  };

  const handleGeneratePortrait = async (gender) => {
    if (!avatarModal || portraitGenerating) return;
    setPortraitGenerating(true);
    setPortraitImageUrl(null);
    setPortraitJobId(null);
    setPortraitTimedOut(false);
    try {
      const r = await fetch(`${BACKEND_URL}/api/did/generate-portrait`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
        body: JSON.stringify({
          genre: avatarModal.genre_tag || 'pop',
          gender,
          variant_id: avatarModal.variant_id,
        }),
      });
      const d = await r.json();
      if (!r.ok) throw new Error(d.detail || 'Portrait generation failed');
      setPortraitJobId(d.job_id);
    } catch (err) {
      setPortraitGenerating(false);
      setError(err.message);
    }
  };

  const handlePortraitRetry = () => {
    setPortraitTimedOut(false);
    setPortraitGenerating(false);
    setPortraitJobId(null);
    setPortraitImageUrl(null);
  };

  const handleDeleteVariant = async (variantId) => {
    setDeletingVariants((prev) => new Set(prev).add(variantId));
    try {
      const r = await fetch(`${BACKEND_URL}/api/songs/variants/${variantId}`, {
        method: 'DELETE',
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!r.ok) {
        const d = await r.json().catch(() => ({}));
        throw new Error(d.detail || 'Delete failed');
      }
      setLibrary((prev) => prev.filter((v) => v.variant_id !== variantId));
      setActiveJob((prev) => {
        if (!prev) return prev;
        const variants = prev.variants.filter((v) => v.variant_id !== variantId);
        return variants.length === 0 ? null : { ...prev, variants };
      });
    } catch (err) {
      setError(err.message);
    } finally {
      setDeletingVariants((prev) => { const s = new Set(prev); s.delete(variantId); return s; });
    }
  };

  const handleAvatarSubmit = async () => {
    if (!avatarModal || !selectedAvatarUrl || avatarSubmitting) return;
    const vId = avatarModal.variant_id;
    setAvatarSubmitting(true);
    setAvatarModal(null);
    setDidStatus((prev) => ({ ...prev, [vId]: 'processing' }));
    try {
      const r = await fetch(`${BACKEND_URL}/api/songs/variants/${vId}/create-avatar-video`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
        body: JSON.stringify({ source_url: selectedAvatarUrl }),
      });
      const d = await r.json();
      if (!r.ok) throw new Error(d.detail || 'Submission failed');
    } catch (err) {
      setDidStatus((prev) => ({ ...prev, [vId]: 'error' }));
      setError(err.message);
    } finally {
      setAvatarSubmitting(false);
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
      <input
        ref={photoInputRef}
        type="file"
        accept="image/jpeg,image/png,image/webp"
        style={{ display: 'none' }}
        onChange={handlePhotoUpload}
      />
      <div style={{ background: '#0b0b14', minHeight: '100vh', color: '#f0eeff' }}>

        {/* ── Header ─────────────────────────────────────────────────────── */}
        <DashboardHeader />

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
            {didPlanOk && !isAdmin && (
              <span style={{ fontSize: 13, color: credits.video_credits === 0 ? '#f87171' : '#666', whiteSpace: 'nowrap' }}>
                · {credits.video_credits} avatar video{credits.video_credits !== 1 ? 's' : ''} remaining
              </span>
            )}
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

          {/* YouTube connected banner */}
          {ytConnectedParam === 'connected' && (
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
              YouTube connected — you can now upload songs directly to your channel.
            </div>
          )}
          {ytConnectedParam === 'error' && (
            <div style={{
              background: 'rgba(251,191,36,0.08)',
              border: '1px solid rgba(251,191,36,0.25)',
              borderRadius: 10,
              padding: '12px 18px',
              marginBottom: 24,
              color: '#fbbf24',
              fontWeight: 600,
              fontSize: 14,
            }}>
              YouTube connection failed — please try again.
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
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 4 }}>
              <h1 style={{ fontSize: '1.35rem', fontWeight: 700, color: '#f0eeff', margin: 0 }}>
                Create a Song
              </h1>
              {/* Custom lyrics toggle */}
              <label style={{ display: 'flex', alignItems: 'center', gap: 8, cursor: 'pointer', flexShrink: 0 }}>
                <span style={{ fontSize: 12, color: useCustomLyrics ? '#a78bfa' : '#555', fontWeight: 500, transition: 'color 0.2s' }}>
                  Custom lyrics
                </span>
                <div
                  onClick={() => setUseCustomLyrics((v) => !v)}
                  style={{
                    width: 36, height: 20, borderRadius: 10,
                    background: useCustomLyrics ? '#7c3aed' : 'rgba(255,255,255,0.08)',
                    position: 'relative', flexShrink: 0,
                    transition: 'background 0.2s', cursor: 'pointer',
                  }}
                >
                  <div style={{
                    position: 'absolute', top: 3,
                    left: useCustomLyrics ? 19 : 3,
                    width: 14, height: 14, borderRadius: '50%',
                    background: '#fff', transition: 'left 0.2s',
                  }} />
                </div>
              </label>
            </div>
            <p style={{ color: '#555', fontSize: 14, marginBottom: 22 }}>
              {useCustomLyrics
                ? 'Paste your own lyrics — Suno will turn them into music.'
                : 'Describe your song — Zeus writes the lyrics, Suno turns them into music.'}
            </p>

            {/* Brief OR custom lyrics textarea */}
            {useCustomLyrics ? (
              <textarea
                className="songs-textarea"
                value={customLyrics}
                onChange={(e) => setCustomLyrics(e.target.value)}
                placeholder={`Paste your lyrics here…\n\n[Verse 1]\nLine one\nLine two\n\n[Chorus]\nHook line here…`}
                rows={10}
                style={{
                  width: '100%',
                  boxSizing: 'border-box',
                  background: 'rgba(167,139,250,0.04)',
                  border: '1px solid rgba(167,139,250,0.2)',
                  borderRadius: 10,
                  padding: '12px 14px',
                  color: '#f0eeff',
                  fontSize: 14,
                  resize: 'vertical',
                  fontFamily: 'ui-monospace, monospace',
                  outline: 'none',
                  marginBottom: 12,
                  transition: 'border-color 0.2s',
                  lineHeight: 1.6,
                }}
              />
            ) : (
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
                  marginBottom: 12,
                  transition: 'border-color 0.2s',
                }}
              />
            )}

            <input
              type="text"
              value={songTitle}
              onChange={(e) => setSongTitle(e.target.value)}
              placeholder={vocals ? 'Song title (optional)' : 'e.g. Midnight Run, Deep Blue, Storm'}
              maxLength={100}
              style={{
                width: '100%',
                boxSizing: 'border-box',
                background: 'rgba(255,255,255,0.04)',
                border: '1px solid rgba(255,255,255,0.1)',
                borderRadius: 10,
                padding: '10px 14px',
                color: '#f0eeff',
                fontSize: 14,
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
                    className={sel ? 'genre-pill genre-pill--sel' : 'genre-pill'}
                    style={{
                      padding: '8px 16px',
                      borderRadius: 20,
                      border: sel ? 'none' : '2px solid rgba(255,255,255,0.4)',
                      background: sel ? '#7c3aed' : 'rgba(255,255,255,0.08)',
                      color: sel ? '#fff' : 'rgba(255,255,255,0.85)',
                      fontSize: 14,
                      fontWeight: 600,
                      cursor: 'pointer',
                      transition: 'all 0.15s',
                    }}
                  >
                    {gLabel(g)}
                  </button>
                );
              })}
            </div>

            {/* ── Inspired by artist ─────────────────────────────────── */}
            <div style={{ marginBottom: 18 }}>
              <div style={{ position: 'relative' }}>
                <input
                  type="text"
                  value={inspiredBy}
                  onChange={(e) => {
                    setInspiredBy(e.target.value);
                    if (artistDescriptors) setArtistDescriptors('');
                  }}
                  onBlur={handleArtistLookup}
                  placeholder="Inspired by artist (e.g. Bob Marley) — optional"
                  style={{
                    width: '100%',
                    boxSizing: 'border-box',
                    background: 'rgba(255,255,255,0.04)',
                    border: '1px solid rgba(255,255,255,0.1)',
                    borderRadius: 10,
                    padding: '10px 14px',
                    paddingRight: artistLoading ? 36 : 14,
                    color: '#f0eeff',
                    fontSize: 14,
                    fontFamily: 'inherit',
                    outline: 'none',
                  }}
                />
                {artistLoading && (
                  <span style={{
                    position: 'absolute',
                    right: 12,
                    top: '50%',
                    transform: 'translateY(-50%)',
                    fontSize: 12,
                    color: '#555',
                  }}>
                    ···
                  </span>
                )}
              </div>
              {artistDescriptors && !artistLoading && (
                <div style={{ marginTop: 8, display: 'flex', flexWrap: 'wrap', gap: 5, alignItems: 'center' }}>
                  <span style={{ fontSize: 11, color: '#444', fontWeight: 600, letterSpacing: '0.4px', textTransform: 'uppercase', flexShrink: 0 }}>Style:</span>
                  {artistDescriptors.split(',').map((d, i) => (
                    <span key={i} style={{
                      background: 'rgba(167,139,250,0.08)',
                      border: '1px solid rgba(167,139,250,0.2)',
                      color: '#9b8ec4',
                      borderRadius: 12,
                      padding: '2px 8px',
                      fontSize: 11,
                    }}>
                      {d.trim()}
                    </span>
                  ))}
                </div>
              )}
            </div>

            {/* ── Advanced options toggle ─────────────────────────────── */}
            <button
              onClick={() => setShowAdvanced((v) => !v)}
              style={{
                width: '100%', display: 'flex', alignItems: 'center', gap: 10,
                background: 'rgba(0,240,255,0.06)', border: '1px solid rgba(0,240,255,0.30)',
                borderRadius: 8, padding: '9px 14px', cursor: 'pointer', marginBottom: 14,
              }}
            >
              <span style={{ fontFamily: "'Orbitron', sans-serif", fontSize: 10, fontWeight: 700, color: '#00f0ff', letterSpacing: '0.14em' }}>⚡ ADVANCED OPTIONS</span>
              <span style={{ marginLeft: 'auto', color: '#00f0ff', fontSize: 12, fontWeight: 600 }}>{showAdvanced ? '▲ Hide' : '▼ Show'}</span>
            </button>

            {/* ── Advanced panel ─────────────────────────────────────── */}
            {showAdvanced && (
              <div style={{
                background: 'rgba(0,240,255,0.04)',
                border: '1px solid #00f0ff',
                borderRadius: 10,
                padding: '18px 20px',
                marginBottom: 18,
                display: 'grid',
                gridTemplateColumns: '1fr 1fr',
                gap: '20px 28px',
                animation: 'advGlow 2.5s ease-in-out infinite',
              }}>
                {/* Vocal gender */}
                <div>
                  <p style={{ fontSize: 11, fontWeight: 600, color: '#555', letterSpacing: '0.6px', textTransform: 'uppercase', marginBottom: 8 }}>Vocal Gender</p>
                  <div style={{ display: 'flex', gap: 6 }}>
                    {[['', 'Either'], ['m', 'Male'], ['f', 'Female'], ['duet', 'Duet']].map(([val, label]) => (
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
                  <div style={{ display: 'flex', gap: 6, alignItems: 'center' }}>
                    <select
                      value={accent}
                      onChange={(e) => setAccent(e.target.value)}
                      style={{ flex: 1, background: 'rgba(255,255,255,0.04)', border: '1px solid rgba(255,255,255,0.1)', borderRadius: 6, padding: '6px 10px', color: accent ? '#c4b5fd' : '#555', fontSize: 13, outline: 'none' }}
                    >
                      <option value="">Default</option>
                      {[
                        'British', 'American (Southern)', 'Irish', 'Scottish', 'Australian',
                        'Caribbean', 'French', 'Spanish', 'American Soul', 'Jamaican',
                        'D&B MC', 'UK Rave MC', 'British MC Grime', 'Jazz Vocal',
                        'American Hip-Hop', 'K-Pop', 'West African', 'South African',
                        'American Phonk', 'New Jersey / Newark', 'British African', 'Jamaican Rasta',
                      ].map((a) => (
                        <option key={a} value={a}>{a}</option>
                      ))}
                    </select>
                    {accent && (
                      <button
                        type="button"
                        title={`Preview ${accent} accent`}
                        onClick={() => previewAccent(accent)}
                        style={{ flexShrink: 0, width: 30, height: 30, borderRadius: 6, background: 'rgba(167,139,250,0.12)', border: '1px solid rgba(167,139,250,0.2)', color: '#a78bfa', cursor: 'pointer', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 12 }}
                      >▶</button>
                    )}
                  </div>
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

                {/* Vocals toggle */}
                <div style={{ gridColumn: '1 / -1', borderTop: '1px solid rgba(255,255,255,0.05)', paddingTop: 16 }}>
                  <label style={{ display: 'flex', alignItems: 'center', gap: 10, cursor: 'pointer' }}>
                    <div
                      onClick={() => setVocals((v) => !v)}
                      style={{
                        width: 36,
                        height: 20,
                        borderRadius: 10,
                        background: vocals ? '#7c3aed' : 'rgba(255,255,255,0.08)',
                        position: 'relative',
                        flexShrink: 0,
                        transition: 'background 0.2s',
                        cursor: 'pointer',
                      }}
                    >
                      <div style={{
                        position: 'absolute',
                        top: 3,
                        left: vocals ? 19 : 3,
                        width: 14,
                        height: 14,
                        borderRadius: '50%',
                        background: '#fff',
                        transition: 'left 0.2s',
                      }} />
                    </div>
                    <span style={{ fontSize: 12, color: vocals ? '#c4b5fd' : '#555', fontWeight: 500 }}>
                      {vocals ? 'Vocals' : 'Instrumental'}
                    </span>
                  </label>
                </div>

                {/* Explicit content */}
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
                ? (useCustomLyrics ? 'Sending to Suno…' : 'Generating lyrics…')
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
                      ytConnected={youtubeConnected}
                      ytStatus={ytStatus[v.variant_id]}
                      ytUrl={ytUrls[v.variant_id]}
                      onYouTubeClick={() => handleYouTubeClick({ ...v, title: activeJob.title })}
                      canDid={canDid}
                      didSt={didStatus[v.variant_id]}
                      videoUrl={videoUrls[v.variant_id]}
                      onAvatarClick={() => handleAvatarClick({ ...v, title: activeJob.title })}
                      videoCredits={credits.video_credits}
                      didPlanOk={didPlanOk}
                      isAdmin={isAdmin}
                      onDelete={() => handleDeleteVariant(v.variant_id)}
                      deleting={deletingVariants.has(v.variant_id)}
                      musicVideoUrl={musicVideoUrls[v.variant_id]}
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
                    ytConnected={youtubeConnected}
                    ytStatus={ytStatus[v.variant_id]}
                    ytUrl={ytUrls[v.variant_id]}
                    onYouTubeClick={() => handleYouTubeClick(v)}
                    canDid={canDid}
                    didSt={didStatus[v.variant_id]}
                    videoUrl={videoUrls[v.variant_id]}
                    onAvatarClick={() => handleAvatarClick(v)}
                    videoCredits={credits.video_credits}
                    didPlanOk={didPlanOk}
                    isAdmin={isAdmin}
                    onDelete={() => handleDeleteVariant(v.variant_id)}
                    deleting={deletingVariants.has(v.variant_id)}
                    musicVideoUrl={musicVideoUrls[v.variant_id]}
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

      {/* ── YouTube upload modal ──────────────────────────────────────────── */}
      {ytModal && (
        <div
          onClick={() => setYtModal(null)}
          style={{
            position: 'fixed', inset: 0,
            background: 'rgba(0,0,0,0.7)',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            zIndex: 1000, padding: 24,
          }}
        >
          <div
            onClick={(e) => e.stopPropagation()}
            style={{
              background: '#12121e',
              border: '1px solid rgba(255,255,255,0.1)',
              borderRadius: 16,
              padding: '28px 28px 24px',
              width: '100%',
              maxWidth: 380,
            }}
          >
            <h3 style={{ fontSize: 16, fontWeight: 700, color: '#e2d9f3', marginBottom: 6 }}>
              Upload to YouTube
            </h3>
            <p style={{ fontSize: 13, color: '#555', marginBottom: 20 }}>
              {ytModal.title || `Song #${ytModal.variant_id}`}
            </p>

            <label style={{ fontSize: 11, fontWeight: 600, color: '#555', letterSpacing: '0.6px', textTransform: 'uppercase', display: 'block', marginBottom: 8 }}>
              Privacy
            </label>
            <select
              value={ytPrivacy}
              onChange={(e) => setYtPrivacy(e.target.value)}
              style={{
                width: '100%',
                background: 'rgba(255,255,255,0.04)',
                border: '1px solid rgba(255,255,255,0.1)',
                borderRadius: 8,
                padding: '10px 12px',
                color: '#c4b5fd',
                fontSize: 14,
                outline: 'none',
                marginBottom: 24,
              }}
            >
              <option value="unlisted">Unlisted (only people with the link)</option>
              <option value="public">Public</option>
              <option value="private">Private (only you)</option>
            </select>

            <div style={{ display: 'flex', gap: 10 }}>
              <button
                onClick={() => setYtModal(null)}
                style={{
                  flex: 1, padding: '11px 0', borderRadius: 8,
                  border: '1px solid rgba(255,255,255,0.1)',
                  background: 'transparent', color: '#666', fontSize: 14, cursor: 'pointer',
                }}
              >
                Cancel
              </button>
              <button
                onClick={handleYouTubeUpload}
                style={{
                  flex: 1, padding: '11px 0', borderRadius: 8,
                  border: 'none',
                  background: 'linear-gradient(135deg, #7c3aed 0%, #a855f7 100%)',
                  color: '#fff', fontSize: 14, fontWeight: 700, cursor: 'pointer',
                }}
              >
                Upload
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ── Avatar picker modal ───────────────────────────────────────────── */}
      {avatarModal && (
        <div
          onClick={closeAvatarModal}
          style={{
            position: 'fixed', inset: 0,
            background: 'rgba(0,0,0,0.75)',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            zIndex: 1000, padding: 24,
          }}
        >
          <div
            onClick={(e) => e.stopPropagation()}
            style={{
              background: '#12121e',
              border: '1px solid rgba(255,255,255,0.1)',
              borderRadius: 16,
              padding: '28px 28px 24px',
              width: '100%',
              maxWidth: 480,
              maxHeight: '90vh',
              overflowY: 'auto',
            }}
          >
            <h3 style={{ fontSize: 16, fontWeight: 700, color: '#e2d9f3', marginBottom: 4 }}>
              Create Avatar Video
            </h3>
            <p style={{ fontSize: 13, color: '#555', marginBottom: 16 }}>
              Pick a presenter — they'll lip-sync to your song.
            </p>
            <p style={{
              fontSize: 12,
              color: '#4a4a6a',
              background: 'rgba(167,139,250,0.06)',
              border: '1px solid rgba(167,139,250,0.12)',
              borderRadius: 8,
              padding: '8px 12px',
              marginBottom: 20,
              lineHeight: 1.5,
            }}>
              For best lip-sync quality, use a clear frontal face photo. Upload your own for a custom performer.
            </p>

            {/* Preset avatars grid */}
            {avatars.length > 0 ? (
              <div style={{
                display: 'grid',
                gridTemplateColumns: 'repeat(3, 1fr)',
                gap: 10,
                marginBottom: 20,
              }}>
                {avatars.map((av) => {
                  const sel = selectedAvatarUrl === av.image_url;
                  const isFemale = av.id.startsWith('w');
                  return (
                    <button
                      key={av.id}
                      className="avatar-thumb"
                      onClick={() => setSelectedAvatarUrl(av.image_url)}
                      style={{
                        border: `2px solid ${sel ? '#a78bfa' : 'rgba(255,255,255,0.08)'}`,
                        borderRadius: 10,
                        padding: 0,
                        overflow: 'hidden',
                        background: 'transparent',
                        cursor: 'pointer',
                        opacity: sel ? 1 : 0.65,
                        transition: 'border-color 0.15s, opacity 0.15s',
                        display: 'flex',
                        flexDirection: 'column',
                        alignItems: 'stretch',
                      }}
                    >
                      <img
                        src={av.image_url}
                        alt={av.name}
                        style={{ width: '100%', aspectRatio: '1/1', objectFit: 'cover', display: 'block' }}
                      />
                      <span style={{
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        gap: 4,
                        fontSize: 11,
                        fontWeight: 500,
                        color: sel ? '#c4b5fd' : '#666',
                        padding: '5px 4px',
                      }}>
                        {av.name}
                        <span style={{
                          fontSize: 9,
                          fontWeight: 600,
                          color: isFemale ? '#f9a8d4' : '#93c5fd',
                          background: isFemale ? 'rgba(249,168,212,0.12)' : 'rgba(147,197,253,0.12)',
                          borderRadius: 4,
                          padding: '1px 4px',
                          letterSpacing: '0.3px',
                        }}>
                          {isFemale ? 'F' : 'M'}
                        </span>
                      </span>
                    </button>
                  );
                })}
              </div>
            ) : (
              <div style={{ height: 40, display: 'flex', alignItems: 'center', marginBottom: 20 }}>
                <span style={{ color: '#444', fontSize: 13 }}>Loading avatars…</span>
              </div>
            )}

            {/* Custom photo upload */}
            <div style={{
              borderTop: '1px solid rgba(255,255,255,0.06)',
              paddingTop: 16,
              marginBottom: 24,
            }}>
              <p style={{ fontSize: 12, color: '#555', marginBottom: 10 }}>
                Or upload your own photo (JPEG / PNG / WebP, under 10 MB):
              </p>
              <div style={{ display: 'flex', gap: 10, alignItems: 'center' }}>
                <button
                  onClick={() => photoInputRef.current?.click()}
                  disabled={uploadingPhoto}
                  style={{
                    padding: '7px 16px',
                    borderRadius: 8,
                    border: '1px solid rgba(255,255,255,0.12)',
                    background: 'rgba(255,255,255,0.04)',
                    color: '#888',
                    fontSize: 12,
                    cursor: uploadingPhoto ? 'default' : 'pointer',
                    flexShrink: 0,
                  }}
                >
                  {uploadingPhoto ? 'Uploading…' : 'Choose Photo'}
                </button>
                {selectedAvatarUrl && selectedAvatarUrl.startsWith('/files/avatars/') && (
                  <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                    <img
                      src={`${BACKEND_URL}${selectedAvatarUrl}`}
                      alt="Custom"
                      style={{ width: 40, height: 40, borderRadius: 6, objectFit: 'cover', border: '2px solid #a78bfa' }}
                    />
                    <span style={{ fontSize: 11, color: '#a78bfa' }}>Custom photo selected</span>
                  </div>
                )}
              </div>
            </div>

            {/* Generate AI Performer */}
            <div style={{
              borderTop: '1px solid rgba(255,255,255,0.06)',
              paddingTop: 16,
              marginBottom: 24,
            }}>
              <p style={{ fontSize: 11, fontWeight: 600, color: '#555', letterSpacing: '0.6px', textTransform: 'uppercase', marginBottom: 10 }}>
                Generate AI Performer
              </p>
              {portraitTimedOut ? (
                <div>
                  <p style={{ fontSize: 13, color: '#f87171', marginBottom: 10 }}>
                    Portrait generation timed out — Apiframe may be unavailable. Please try again.
                  </p>
                  <button
                    onClick={handlePortraitRetry}
                    style={{
                      padding: '7px 18px', borderRadius: 8,
                      border: '1px solid rgba(248,113,113,0.35)',
                      background: 'rgba(248,113,113,0.08)',
                      color: '#f87171', fontSize: 12, fontWeight: 500, cursor: 'pointer',
                    }}
                  >
                    ↺ Retry
                  </button>
                </div>
              ) : portraitImageUrl ? (
                <div style={{ display: 'flex', alignItems: 'center', gap: 14 }}>
                  <button
                    onClick={() => setSelectedAvatarUrl(portraitImageUrl)}
                    style={{
                      border: `2px solid ${selectedAvatarUrl === portraitImageUrl ? '#a78bfa' : 'rgba(255,255,255,0.15)'}`,
                      borderRadius: 10,
                      padding: 0,
                      overflow: 'hidden',
                      background: 'transparent',
                      cursor: 'pointer',
                      width: 80,
                      height: 80,
                      flexShrink: 0,
                      transition: 'border-color 0.15s',
                    }}
                  >
                    <img src={portraitImageUrl} alt="AI Generated" style={{ width: '100%', height: '100%', objectFit: 'cover', display: 'block' }} />
                  </button>
                  <div>
                    <span style={{
                      display: 'inline-block', fontSize: 10, fontWeight: 700, color: '#a78bfa',
                      background: 'rgba(167,139,250,0.12)', border: '1px solid rgba(167,139,250,0.25)',
                      borderRadius: 4, padding: '2px 7px', letterSpacing: '0.3px',
                      textTransform: 'uppercase', marginBottom: 6,
                    }}>AI Generated</span>
                    <p style={{ fontSize: 12, color: '#555', margin: '0 0 4px' }}>
                      {selectedAvatarUrl === portraitImageUrl ? 'Selected — click Create Video' : 'Click to select'}
                    </p>
                    <button
                      onClick={() => {
                        if (selectedAvatarUrl === portraitImageUrl) setSelectedAvatarUrl(null);
                        setPortraitImageUrl(null);
                        setPortraitJobId(null);
                      }}
                      style={{ fontSize: 11, color: '#444', background: 'none', border: 'none', cursor: 'pointer', padding: 0, textDecoration: 'underline' }}
                    >
                      Regenerate
                    </button>
                  </div>
                </div>
              ) : portraitGenerating ? (
                <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                  <span style={{ fontSize: 13, color: '#666' }}>Generating portrait (~30s)…</span>
                  <span style={{ fontSize: 14, color: '#444', letterSpacing: 2 }}>···</span>
                </div>
              ) : (
                <div style={{ display: 'flex', gap: 8 }}>
                  <button
                    onClick={() => handleGeneratePortrait('m')}
                    style={{
                      padding: '7px 18px', borderRadius: 8,
                      border: '1px solid rgba(147,197,253,0.3)',
                      background: 'rgba(147,197,253,0.06)',
                      color: '#93c5fd', fontSize: 12, fontWeight: 500, cursor: 'pointer',
                    }}
                  >
                    ♂ Male
                  </button>
                  <button
                    onClick={() => handleGeneratePortrait('f')}
                    style={{
                      padding: '7px 18px', borderRadius: 8,
                      border: '1px solid rgba(249,168,212,0.3)',
                      background: 'rgba(249,168,212,0.06)',
                      color: '#f9a8d4', fontSize: 12, fontWeight: 500, cursor: 'pointer',
                    }}
                  >
                    ♀ Female
                  </button>
                </div>
              )}
            </div>

            {/* Actions */}
            <div style={{ display: 'flex', gap: 10 }}>
              <button
                onClick={closeAvatarModal}
                style={{
                  flex: 1, padding: '11px 0', borderRadius: 8,
                  border: '1px solid rgba(255,255,255,0.1)',
                  background: 'transparent', color: '#666', fontSize: 14, cursor: 'pointer',
                }}
              >
                Cancel
              </button>
              <button
                onClick={handleAvatarSubmit}
                disabled={!selectedAvatarUrl || avatarSubmitting}
                style={{
                  flex: 1, padding: '11px 0', borderRadius: 8,
                  border: 'none',
                  background: selectedAvatarUrl
                    ? 'linear-gradient(135deg, #7c3aed 0%, #a855f7 100%)'
                    : 'rgba(255,255,255,0.05)',
                  color: selectedAvatarUrl ? '#fff' : '#444',
                  fontSize: 14,
                  fontWeight: 700,
                  cursor: selectedAvatarUrl ? 'pointer' : 'default',
                }}
              >
                {avatarSubmitting ? 'Submitting…' : 'Create Video'}
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}
