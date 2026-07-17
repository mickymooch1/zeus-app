import { memo, useCallback, useEffect, useMemo, useRef, useState, lazy, Suspense } from 'react';
import { Link, useLocation } from 'react-router-dom';
import WaveSurfer from 'wavesurfer.js';
import { useTranslation } from 'react-i18next';
import { useAuth } from '../contexts/AuthContext';
import { BeatsDashboardHeader } from '../components/BeatsDashboardHeader';
import { EmailVerificationBanner } from '../components/EmailVerificationBanner';
import { BACKEND_URL } from '../brand';
import OnboardingTour from '../components/OnboardingTour';
import { audioManager } from '../utils/audioManager';
import { isIOSWebView } from '../hooks/useIsIOSWebView';
import IOSWebViewBanner from '../components/IOSWebViewBanner';
import { useOnlineStatus }  from '../hooks/useOnlineStatus';
import { useOfflineSongs }  from '../hooks/useOfflineSongs';
import OfflineBanner        from '../components/OfflineBanner';
import { useNowPlaying }    from '../contexts/NowPlayingContext';
import LyricsModal          from '../components/LyricsModal';

const GENRES = ['country','reggae','pop','rock','hiphop','lofi','edm','acoustic','irishjig','irishfolk','blues','soul','rnb','bluessoul','drumandbass','grime','ukgarage','jungle','bassline','house','deephouse','loversrock','ukdrill','kpop','deepsoulblues','niche','ukstreetsoul','classical','indie','techno','technhouse','hyperpop','afrobeats','amapiano','driftphonk','jerseyclub','afroswing','rastadub','deeprotbassline','jazz','swing','vocaljazz','electronicfunk','syntheticpop','ragga','dubstep','bhangra','rockney','metal','reggaeton','latintrap','rootsreggae','countryamericana','southemsoul','traditionalpop','rocknroll','trap','eastcoasthiphop','poprap','synthwave','gospel','trapsoul','meditation','christmas','corridos','healingfrequency','purebassline'];
const GENRE_LABEL = { bluegrass:'Bluegrass', britpop:'Britpop', indierock:'Indie Rock', folk:'Folk', acousticballad:'Acoustic Ballad', folkblues:'Folk Blues', roots:'Roots', acousticblues:'Acoustic Blues', patriotic:'Patriotic', hiphop:'Hip-hop', lofi:'Lo-Fi', edm:'EDM', irishjig:'Irish Jig', irishfolk:'Irish Folk', rnb:'R&B', bluessoul:'Blues Soul', drumandbass:'D&B', grime:'Grime', ukgarage:'UK Garage', jungle:'Jungle', bassline:'Bassline House', house:'House', deephouse:'Deep House', dancehouse:'Dance House', loversrock:'Lovers Rock', ukdrill:'UK Drill', kpop:'K-Pop', deepsoulblues:'Deep Soul Blues', ukstreetsoul:'UK Street Soul', technhouse:'Tech House', driftphonk:'Drift Phonk', jerseyclub:'Jersey Club', afroswing:'Afroswing', rastadub:'Rasta Dub', deeprotbassline:'Deeprot Bassline', jazz:'Jazz', swing:'Swing', vocaljazz:'Vocal Jazz', electronicfunk:'Electronic Funk', syntheticpop:'Synthetic Pop', ragga:'Ragga', dubstep:'Dubstep', bhangra:'Bhangra', rockney:'Rockney', metal:'Metal', bluesrock:'Blues Rock', hardrock:'Hard Rock', punkrock:'Punk Rock', reggaeton:'Reggaeton', latintrap:'Latin Trap', rootsreggae:'Roots Reggae', countryamericana:'Country Americana', countrypop:'Country Pop', southemsoul:'Southern Soul', soulrnb:'Soul R&B', orchestralsoul:'Orchestral Soul', classicfunk:'Classic Funk', traditionalpop:'Traditional Pop', rocknroll:'Rock & Roll', trap:'Trap', eastcoasthiphop:'East Coast Hip-Hop', westcoasthiphop:'West Coast Hip-Hop', poprap:'Pop Rap', synthwave:'Synthwave', trance:'Trance', triphop:'Trip-Hop', salsa:'Salsa', gospel:'Gospel', trapsoul:'Trap Soul', meditation:'Meditation', ambient:'Ambient', christmas:'Christmas', corridos:'Corridos', healingfrequency:'Healing Frequencies', naturesounds:'Nature Sounds', whalesong:'Whale Song', cracklingfire:'Crackling Fire', thunderstorm:'Thunderstorm', oceanwaves:'Ocean Waves', forest:'Forest', nightsounds:'Night Sounds', purebassline:'Pure Bassline', psychedelicguitar:'Psychedelic Guitar', saxophone:'Saxophone', pianosolo:'Piano', violinsolo:'Violin', electricbluesguitar:'Blues Guitar', trumpet:'Trumpet', flamencoguitar:'Flamenco Guitar' };
const GENRE_CATEGORIES = [
  { id: 'uk_street',  label: '🎤 UK Street & Hip Hop', color: '#00f0ff',
    genres: ['grime','ukdrill','afroswing','bassline','ukgarage','niche','drumandbass','jungle','deeprotbassline','ukstreetsoul','triphop'] },
  { id: 'soul',       label: '🎵 Soul & Blues',        color: '#fb923c',
    genres: ['soul','bluessoul','southemsoul','soulrnb','orchestralsoul','classicfunk','gospel','trapsoul','vocaljazz','swing','rnb','blues','deepsoulblues'] },
  { id: 'rock',       label: '🎸 Rock & Metal',        color: '#f87171',
    genres: ['rock','hardrock','metal','punkrock','rocknroll','traditionalpop','bluesrock','indie','britpop','indierock','rockney'] },
  { id: 'country_folk', label: '🤠 Country & Folk',    color: '#d97706',
    genres: ['country','bluegrass','countryamericana','countrypop','folk','acousticballad','folkblues','roots','acousticblues'] },
  { id: 'electronic', label: '🎹 Electronic & Dance',  color: '#4ade80',
    genres: ['house','technhouse','deephouse','dancehouse','purebassline','synthwave','driftphonk','techno','trance','edm','electronicfunk','dubstep','jerseyclub','hyperpop','syntheticpop'] },
  { id: 'world',      label: '🌍 World & Urban',       color: '#fbbf24',
    genres: ['afrobeats','reggae','rootsreggae','reggaeton','ragga','corridos','salsa','bhangra','loversrock','rastadub','amapiano','latintrap'] },
  { id: 'pop',        label: '🎶 Pop & Hip Hop',       color: '#f472b6',
    genres: ['pop','patriotic','trap','eastcoasthiphop','westcoasthiphop','poprap','kpop','hiphop'] },
  { id: 'chill',      label: '🧘 Chill & Wellness',    color: '#e2e8f0',
    genres: ['lofi','meditation','ambient','healingfrequency','naturesounds','whalesong','cracklingfire','thunderstorm','oceanwaves','forest','nightsounds','classical','acoustic','jazz','irishfolk','irishjig','christmas'] },
  { id: 'instrumental_solo', label: '🎷 Instrumental & Solo', color: '#a78bfa',
    genres: ['saxophone','pianosolo','violinsolo','electricbluesguitar','psychedelicguitar','trumpet','flamencoguitar'] },
];
const _genreColorMap = Object.fromEntries(
  GENRE_CATEGORIES.flatMap(cat => cat.genres.map(g => [g, cat.color]))
);
const genreColor = (g) => {
  if (!g) return '#cccccc';
  const base = g.includes('__') ? g.split('__')[0] : g;
  return _genreColorMap[base] || '#cccccc';
};
const gLabel = (g) => {
  if (!g) return '';
  if (g.includes('__')) {
    const [a, b] = g.split('__');
    const la = GENRE_LABEL[a] || a.charAt(0).toUpperCase() + a.slice(1);
    const lb = GENRE_LABEL[b] || b.charAt(0).toUpperCase() + b.slice(1);
    return `${la} × ${lb}`;
  }
  return GENRE_LABEL[g] || g.charAt(0).toUpperCase() + g.slice(1);
};

function _matchGenreSlug(text) {
  if (!text) return null;
  const t = text.toLowerCase();
  const checks = [
    ['hip', 'hiphop'], ['rap', 'hiphop'], ['trap', 'trap'], ['jazz', 'jazz'],
    ['rock', 'rock'], ['pop', 'pop'], ['edm', 'edm'], ['electronic', 'edm'],
    ['house', 'house'], ['r&b', 'rnb'], ['soul', 'soul'], ['country', 'country'],
    ['reggae', 'reggae'], ['afro', 'afrobeats'], ['lo-fi', 'lofi'], ['lofi', 'lofi'],
    ['classical', 'classical'], ['indie', 'indie'], ['blues', 'blues'],
    ['grime', 'grime'], ['drum', 'drumandbass'], ['d&b', 'drumandbass'],
    ['techno', 'techno'], ['k-pop', 'kpop'], ['kpop', 'kpop'],
    ['amapiano', 'amapiano'], ['drill', 'ukdrill'], ['phonk', 'driftphonk'],
    ['jersey', 'jerseyclub'], ['acoustic', 'acoustic'], ['hyperpop', 'hyperpop'],
    ['rnb', 'rnb'],
  ];
  for (const [key, slug] of checks) {
    if (t.includes(key) && GENRES.includes(slug)) return slug;
  }
  return null;
}

function _matchTempo(text) {
  if (!text) return '';
  const t = text.toLowerCase();
  if (t.includes('slow') || t.includes('ballad') || t.includes('laid')) return 'slow';
  if (t.includes('fast') || t.includes('uptempo') || t.includes('energet') || t.includes('upbeat')) return 'fast';
  if (t.includes('medium') || t.includes('moderate') || t.includes('mid') || t.includes('groove')) return 'medium';
  return '';
}

const SONG_PACKS = [
  { pack: 'song_pack_099', label: '2 Songs',  price: '£0.99' },
  { pack: 'song_pack_200', label: '5 Songs',  price: '£2.00' },
  { pack: 'song_pack_400', label: '10 Songs', price: '£4.00' },
];

const ANIMATION_PACKS = [
  { pack: 'animation_pack_5',  label: '5 premium credits',  price: '£2' },
  { pack: 'animation_pack_15', label: '15 premium credits', price: '£5' },
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
.genre-pill:not(.genre-pill--sel):hover { background: var(--pill-hover-bg, rgba(255,255,255,0.13)) !important; border-color: var(--pill-color, rgba(255,255,255,0.65)) !important; color: var(--pill-color, #fff) !important; }
.genre-pill--sel:hover { opacity: 0.88 !important; }
@keyframes favToastFade { 0% { opacity:0 } 10% { opacity:1 } 70% { opacity:1 } 100% { opacity:0 } }
.adv-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 20px 28px; }
/* Advanced options — labels/hints/inactive states were #555 (unreadable on the dark panel). Force legible text; !important beats the inline styles. Active buttons stay indicated by their bg + border. */
.adv-grid p, .adv-grid label { color: #cccccc !important; }
.adv-grid button { color: #dddddd !important; }
.adv-grid input, .adv-grid textarea, .adv-grid select { color: #ffffff !important; }
.adv-grid select option { color: #111111; }
@media (max-width: 599px) {
  .adv-grid { grid-template-columns: 1fr !important; gap: 14px !important; }
  .adv-grid > * { grid-column: auto !important; }
  .songs-content-wrap { padding: 20px 12px 60px !important; }
  .songs-bar-wrap { padding: 10px 12px !important; }
}
@keyframes micPulse {
  0%, 100% { box-shadow: 0 0 0 0 rgba(239,68,68,0.5); }
  50%       { box-shadow: 0 0 0 7px rgba(239,68,68,0); }
}
.mic-btn-listening { animation: micPulse 1s ease-in-out infinite !important; }
.songs-search-input { outline: none; }
.songs-search-input:focus { border-color: #00f0ff !important; box-shadow: 0 0 0 2px rgba(0,240,255,0.18), 0 0 14px rgba(0,240,255,0.12) !important; }
.songs-grid { display: grid; gap: 16px; grid-template-columns: 1fr; }
@media (min-width: 640px)  { .songs-grid { grid-template-columns: repeat(2, 1fr); } }
@media (min-width: 1024px) { .songs-grid { grid-template-columns: repeat(3, 1fr); } }
.song-card-anim { transition: transform 0.28s cubic-bezier(0.34,1.56,0.64,1), box-shadow 0.28s ease, border-color 0.2s ease; }
.song-card-anim:hover { transform: translateY(-5px); box-shadow: 0 16px 48px rgba(0,0,0,0.55), 0 0 24px rgba(0,240,255,0.14); border-color: rgba(0,240,255,0.25) !important; }
.dl-btn:hover { box-shadow: 0 0 16px rgba(124,58,237,0.5) !important; }
.fav-star-btn:hover { transform: scale(1.2); }
.cover-video { transition: filter 0.2s; }
.cover-video:hover { filter: brightness(1.12); }
@keyframes pulse-glow {
  0%, 100% { box-shadow: 0 0 15px rgba(0,240,255,0.3), inset 0 0 15px rgba(0,240,255,0.03); border-color: #00f0ff; }
  50%       { box-shadow: 0 0 28px rgba(0,240,255,0.55), inset 0 0 20px rgba(0,240,255,0.06); border-color: #66f9ff; }
}
.topup-section { animation: pulse-glow 3s ease-in-out infinite; }
.topup-btn:hover { background: linear-gradient(135deg, rgba(0,240,255,0.22) 0%, rgba(0,191,255,0.22) 100%) !important; box-shadow: 0 0 14px rgba(0,240,255,0.45) !important; transform: translateY(-1px) !important; }
@media (max-width: 599px) { .topup-section .topup-btn { width: 100% !important; justify-content: center !important; } }
@media (max-width: 360px) {
  .genre-pill { padding: 4px 8px !important; font-size: 11px !important; }
  .songs-content-wrap { padding: 12px 8px 80px !important; }
  .songs-bar-wrap { padding: 8px !important; }
}
`;

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
          {genre && <span style={{ ...S.pill, color: genreColor(genre), borderColor: genreColor(genre) + '55', background: genreColor(genre) + '14' }}>{gLabel(genre)}</span>}
          <span style={{ color: '#444', fontSize: 12 }}>~60s</span>
        </div>
      </div>
    </div>
  );
}

const actionBtnStyle = {
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

const SONG_TEMPLATES = [
  { emoji: '🔥', label: 'Club Banger', value: 'An energetic club banger with a massive drop, euphoric build up and a crowd going crazy' },
  { emoji: '😢', label: 'Emotional R&B', value: 'A heartfelt emotional R&B song about losing someone you love and trying to move on' },
  { emoji: '🎤', label: 'Grime Bars', value: 'Hard hitting grime bars about coming from nothing and making it against all odds, fast aggressive flow' },
  { emoji: '📱', label: 'TikTok Viral', value: 'A catchy viral TikTok song with an irresistible hook that gets stuck in your head instantly' },
  { emoji: '💔', label: 'Sad Love Song', value: 'A sad love song about heartbreak and missing someone who left, slow and emotional' },
  { emoji: '🌴', label: 'Afrobeats Vibe', value: 'A feel good afrobeats song about summer, good vibes and celebrating life' },
];

function formatStoryTime(secs) {
  if (!secs || isNaN(secs)) return '0:00';
  const m = Math.floor(secs / 60);
  const s = Math.floor(secs % 60);
  return `${m}:${s.toString().padStart(2, '0')}`;
}

const StoryCard = memo(function StoryCard({ variant, title, onDelete, deleting }) {
  const [playing, setPlaying]       = useState(false);
  const [copied, setCopied]         = useState(false);
  const [currentTime, setCurrentTime] = useState(0);
  const [duration, setDuration]     = useState(0);
  const audioRef = useRef(null);

  const audioUrl = variant.mp3_url
    ? (variant.mp3_url.startsWith('http') ? variant.mp3_url : `${BACKEND_URL}${variant.mp3_url}`)
    : null;

  const handlePlay = () => {
    if (!audioUrl) return;
    if (!audioRef.current) {
      const a = new Audio(audioUrl);
      a.onended = () => setPlaying(false);
      a.onpause = () => setPlaying(false);
      a.onplay  = () => setPlaying(true);
      a.addEventListener('timeupdate', () => setCurrentTime(a.currentTime));
      a.addEventListener('loadedmetadata', () => setDuration(a.duration));
      audioRef.current = a;
    }
    if (playing) {
      audioRef.current.pause();
    } else {
      audioManager.play(audioRef.current, variant.variant_id);
    }
  };

  const handleSeek = (e) => {
    const val = Number(e.target.value);
    if (audioRef.current) audioRef.current.currentTime = val;
    setCurrentTime(val);
  };

  useEffect(() => () => { if (audioRef.current) { audioRef.current.pause(); audioRef.current = null; } }, []);

  const handleShare = async () => {
    const shareUrl = `${window.location.origin}/songs/share/${variant.variant_id}`;
    if (navigator.share) {
      try { await navigator.share({ title: title || 'Kids Story', url: shareUrl }); } catch (_) {}
    } else {
      try { await navigator.clipboard.writeText(shareUrl); setCopied(true); setTimeout(() => setCopied(false), 2000); } catch (_) {}
    }
  };

  const safeFilename = `${(title || 'story').replace(/[^a-z0-9]/gi, '-').toLowerCase()}.mp3`;

  return (
    <div className="song-card-anim" style={S.card}>
      <div style={{ position: 'relative' }}>
        {variant.image_url ? (
          <img src={variant.image_url} alt={title} style={S.artBox} className="cover-ken-burns" />
        ) : (
          <div style={{ ...S.artBox, ...S.artPlaceholder }}>
            <span style={{ fontSize: 40, opacity: 0.2 }}>📖</span>
          </div>
        )}
        {audioUrl && (
          <button
            onClick={handlePlay}
            style={{
              position: 'absolute', bottom: 8, left: 8,
              width: 40, height: 40, borderRadius: '50%',
              border: '1.5px solid rgba(255,255,255,0.7)',
              background: playing ? 'rgba(124,58,237,0.85)' : 'rgba(0,0,0,0.6)',
              color: '#fff', fontSize: 16, cursor: 'pointer',
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              backdropFilter: 'blur(6px)', transition: 'all 0.2s', flexShrink: 0,
            }}
          >
            {playing ? '⏸' : '▶'}
          </button>
        )}
      </div>
      <div style={S.cardBody}>
        <div style={{ ...S.cardTitle, fontSize: 15, fontWeight: 700 }}>{title || `Story #${variant.variant_id}`}</div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginTop: 6 }}>
          <span style={{ ...S.pill, color: '#a78bfa', borderColor: 'rgba(167,139,250,0.35)', background: 'rgba(167,139,250,0.1)' }}>🧒 Kids Story</span>
        </div>
        {audioUrl && (
          <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginTop: 10 }}>
            <span style={{ fontSize: 10, fontWeight: 700, color: '#a78bfa', minWidth: 28, textAlign: 'right', fontFamily: 'monospace' }}>
              {formatStoryTime(currentTime)}
            </span>
            <input
              type="range"
              min="0"
              max={duration || 0}
              step="0.1"
              value={currentTime}
              onChange={handleSeek}
              style={{
                flex: 1, height: 4, cursor: 'pointer', accentColor: '#a855f7',
                background: duration
                  ? `linear-gradient(to right, #a855f7 ${(currentTime / duration) * 100}%, rgba(167,139,250,0.2) ${(currentTime / duration) * 100}%)`
                  : 'rgba(167,139,250,0.2)',
                borderRadius: 2, outline: 'none', border: 'none', appearance: 'none', WebkitAppearance: 'none',
              }}
            />
            <span style={{ fontSize: 10, fontWeight: 700, color: 'rgba(167,139,250,0.6)', minWidth: 28, fontFamily: 'monospace' }}>
              {formatStoryTime(duration)}
            </span>
          </div>
        )}
        {audioUrl && (
          <div style={{ marginTop: 8 }}>
            <a
              href={audioUrl}
              download={safeFilename}
              style={{
                display: 'flex', alignItems: 'center', justifyContent: 'center',
                width: '100%', minHeight: 44, borderRadius: 7,
                background: 'linear-gradient(135deg, #7c3aed 0%, #a855f7 100%)',
                color: '#fff', fontSize: 12, fontWeight: 600,
                cursor: 'pointer', textDecoration: 'none', boxSizing: 'border-box',
                transition: 'all 0.2s ease',
              }}
            >
              ⬇ Download Story
            </a>
          </div>
        )}
        <div style={{ display: 'flex', gap: 8, marginTop: 8 }}>
          <button
            onClick={handleShare}
            style={{ ...actionBtnStyle, flex: 1, color: '#38bdf8', borderColor: 'rgba(56,189,248,0.55)' }}
          >
            {copied ? '✓ Copied' : '🔗 Share'}
          </button>
          <button
            onClick={() => onDelete(variant.variant_id)}
            disabled={deleting}
            style={{ ...actionBtnStyle, flex: 1, color: '#f87171', borderColor: 'rgba(248,113,113,0.5)', opacity: deleting ? 0.55 : 1, cursor: deleting ? 'default' : 'pointer' }}
          >
            {deleting ? 'Deleting…' : '🗑 Delete'}
          </button>
        </div>
      </div>
    </div>
  );
});

const LazyPINGate = lazy(() => import('../components/ParentPINGate'));
function KidsPinGateLoader({ token, hasPIN, onSuccess, onCancel }) {
  return <LazyPINGate token={token} hasPIN={hasPIN} action="enter" onSuccess={onSuccess} onCancel={onCancel} />;
}

// Paid-feature upgrade prompts. On web → modal with a /billing CTA; inside the
// iOS webview → plain "visit zeusbeats.com" message (App Store: no in-app
// purchase steering). A locked feature button must never silently do nothing.
const UPGRADE_FEATURES = {
  youtube: { icon: '📺', title: 'YouTube Upload', desc: 'Upload your songs directly to YouTube with Music Starter and above.' },
  stems:   { icon: '🎵', title: 'Stem Separator', desc: 'Split your track into separate vocals, drums, bass and melody stems — available with premium credits on paid plans.' },
  avatar:  { icon: '🎬', title: 'Avatar Videos',  desc: 'Turn your songs into animated avatar performance videos with Music Pro and above.' },
};

const SongCard = memo(function SongCard({
  variant, title, artistName, activeWsRef,
  canYouTube, ytConnected, ytStatus: ytSt, ytUrl, ytError, onYouTubeClick,
  canDid, didSt, videoUrl, onAvatarClick, videoCredits, didPlanOk, isAdmin,
  onDelete, deleting, musicVideoUrl, onRemake, onTelegramClick, onRegenerate,
  isFavourite, onToggleFavourite, isFreeTier, animateCover,
  isPublic, onShareToggle,
  playlists, onAddToPlaylist,
  premiumCredits, stemsData: stemsProp, onGetStems, onOpenCover, onUpgrade,
  soundPersonaVariantId, onLockSound,
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
  const displayMusicVideoUrl = !isFreeTier && animateCover && musicVideoUrl;

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

export default function SongsPage() {
  const { token, user } = useAuth();
  const isOnline = useOnlineStatus();
  const { savedSongs, downloading, isSaved, saveForOffline, removeSaved, getOfflineAudioUrl } = useOfflineSongs();
  const { playOne } = useNowPlaying();
  const { t } = useTranslation();
  const location = useLocation();
  const topupSuccess = new URLSearchParams(location.search).get('topup') === 'success';

  const [credits, setCredits]           = useState({ balance: 0, monthly_allowance: 0, is_admin: false, plan: null, has_paid: false, youtube_connected: false, video_credits: 0, video_monthly_allowance: 0, artist_name: '', premium_credits: 0, premium_monthly_allowance: 0 });
  const [creditsLoaded, setCreditsLoaded] = useState(false);
  const [brief, setBrief]               = useState('');
  const [selGenres, setSelGenres]       = useState(() => { const s = _matchGenreSlug(location.state?.prefillGenre); return s ? new Set([s]) : new Set(); });
  const [generating, setGenerating]     = useState(false);
  const [activeJob, setActiveJob]       = useState(null);
  const [library, setLibrary]           = useState([]);
  const [error, setError]               = useState('');
  const [topupLoading, setTopupLoading] = useState(null);

  const [showAdvanced, setShowAdvanced]   = useState(() => window.innerWidth >= 600 || !!(location.state?.prefillStyle || location.state?.prefillGenre));
  const [vocalGender, setVocalGender]     = useState('');
  const [accent, setAccent]               = useState('');
  // Genre blend
  const [genreBlend, setGenreBlend]       = useState(false);
  const [genreB, setGenreB]               = useState('');
  const [blendRatio, setBlendRatio]       = useState(50);
  // Collapsible genre categories — all collapsed by default, except any category
  // that already contains a (prefilled) selection so the choice stays visible.
  const [openCats, setOpenCats] = useState(() => {
    const open = new Set();
    GENRE_CATEGORIES.forEach(cat => { if (cat.genres.some(g => selGenres.has(g))) open.add(cat.id); });
    return open;
  });
  const toggleCat = (id) => setOpenCats(prev => {
    const next = new Set(prev);
    if (next.has(id)) next.delete(id); else next.add(id);
    return next;
  });
  const [remakeOpenCats, setRemakeOpenCats] = useState(() => new Set());
  const toggleRemakeCat = (id) => setRemakeOpenCats(prev => {
    const next = new Set(prev);
    if (next.has(id)) next.delete(id); else next.add(id);
    return next;
  });
  // Onboarding
  const [showTour, setShowTour]           = useState(() => !localStorage.getItem('zeus_onboarding_done'));
  const [pendingAutoGen, setPendingAutoGen] = useState(null);
  const [showRetrigger, setShowRetrigger] = useState(false);
  const [tempo, setTempo]                 = useState(() => _matchTempo(location.state?.prefillTempo));
  const [tempoBpm, setTempoBpm]           = useState(120);
  const [modelVersion, setModelVersion]   = useState('V5');
  const [negativeTags, setNegativeTags]   = useState('');
  const [explicit, setExplicit]           = useState(false);
  const [pinModalOpen, setPinModalOpen]   = useState(false);
  const [pinInput, setPinInput]           = useState('');
  const [pinError, setPinError]           = useState('');
  const [vocalMode, setVocalMode]         = useState('full'); // 'full' | 'intermittent' | 'instrumental'
  const [animateCoverPref, setAnimateCoverPref] = useState(
    () => localStorage.getItem('zeus_animated_covers') === 'true'
  );
  const [songTitle, setSongTitle]         = useState('');
  const [healingFrequency, setHealingFrequency] = useState('432');

  const [showWelcome, setShowWelcome] = useState(() => !!user?.is_new_user);

  const [ytStatus, setYtStatus]   = useState({});
  const [ytUrls, setYtUrls]       = useState({});
  const [ytErrors, setYtErrors]   = useState({});
  const [ytModal, setYtModal]         = useState(null);
  const [ytPrivacy, setYtPrivacy]     = useState('unlisted');
  const [ytUpgradePrompt, setYtUpgradePrompt] = useState(false);

  const [inspiredBy, setInspiredBy]               = useState('');
  const [artistDescriptors, setArtistDescriptors] = useState(() => [location.state?.prefillStyle || '', location.state?.prefillMood || ''].filter(Boolean).join(', '));
  const [artistLoading, setArtistLoading]         = useState(false);

  const [avatarModal, setAvatarModal]             = useState(null);
  const [avatars, setAvatars]                     = useState([]);
  const [selectedAvatarUrl, setSelectedAvatarUrl] = useState(null);
  const [uploadingPhoto, setUploadingPhoto]       = useState(false);
  const [avatarSubmitting, setAvatarSubmitting]   = useState(false);
  const [didStatus, setDidStatus]                 = useState({});
  const [videoUrls, setVideoUrls]                 = useState({});
  const [musicVideoUrls, setMusicVideoUrls]       = useState({});

  const [remakeModal, setRemakeModal]     = useState(null);
  const [remakeGenre, setRemakeGenre]     = useState('');
  const [remakeStyle, setRemakeStyle]     = useState('');
  const [remakeLoading, setRemakeLoading] = useState(false);
  const [remakeError, setRemakeError]     = useState('');

  const [portraitGenerating, setPortraitGenerating] = useState(false);
  const [portraitJobId, setPortraitJobId]           = useState(null);
  const [portraitImageUrl, setPortraitImageUrl]     = useState(null);
  const [portraitTimedOut, setPortraitTimedOut]     = useState(false);

  const [deletingVariants, setDeletingVariants]     = useState(new Set());

  const [playlists, setPlaylists]         = useState([]);
  const [newPlModal, setNewPlModal]       = useState(false);
  const [newPlName, setNewPlName]         = useState('');
  const [newPlLoading, setNewPlLoading]   = useState(false);

  const [favourites, setFavourites]       = useState(new Set());
  const [publicVariants, setPublicVariants] = useState(new Set());
  const [activeTab, setActiveTab] = useState('all');
  const [search, setSearch] = useState('');

  const [stemsData, setStemsData] = useState({});
  const stemsPollRef = useRef({});
  const [coverModal, setCoverModal] = useState(null);
  const [upgradeFeature, setUpgradeFeature] = useState(null);
  const [coverLyrics, setCoverLyrics] = useState('');
  const [coverLoading, setCoverLoading] = useState(false);
  const [coverError, setCoverError] = useState('');
  const [coverToast, setCoverToast] = useState(false);
  const [soundPersona, setSoundPersona] = useState(null);
  const [lockToast, setLockToast] = useState('');
  const lockToastTimer = useRef(null);
  const [offlineToast, setOfflineToast] = useState('');
  const offlineToastRef = useRef(null);

  // Kids Mode
  const [isKidsMode, setIsKidsMode]         = useState(false);
  const [showKidsPinGate, setShowKidsPinGate] = useState(false);
  // Roast Mode
  const [isRoastMode, setIsRoastMode]       = useState(false);
  const [roastName, setRoastName]           = useState('');
  const [roastDetails, setRoastDetails]     = useState('');
  const [roastVibe, setRoastVibe]           = useState('gentle');
  const [kidsSubMode, setKidsSubMode]       = useState('song'); // 'song' | 'story'
  const [kidsAccent, setKidsAccent]         = useState('');     // Suno vocal accent (song mode)
  const [kidsNarratorVoice, setKidsNarratorVoice]   = useState('british');    // ElevenLabs narrator (story mode)
  const [kidsChildVoice, setKidsChildVoice]         = useState('younggirl'); // ElevenLabs child hero voice
  const [kidsCharacterVoice, setKidsCharacterVoice] = useState('');           // ElevenLabs other character voice (optional)
  const [storyLanguage, setStoryLanguage]           = useState('english');  // language Claude writes story in
  const [previewingVoice, setPreviewingVoice]       = useState(null);        // voice key currently previewing
  const previewAudioRef = useRef(null);
  const [mainCharacter, setMainCharacter]   = useState('');
  const [storyEvent, setStoryEvent]         = useState('');
  const [kidsAgeRange, setKidsAgeRange]     = useState('little_ones');
  const [kidsMusicStyle, setKidsMusicStyle] = useState('funpop');

  // Custom lyrics
  const [useCustomLyrics, setUseCustomLyrics]   = useState(false);
  const [customLyricsText, setCustomLyricsText] = useState('');

  const [listening, setListening] = useState(false);

  const activeWsRef     = useRef(null);
  const pollTimerRef    = useRef(null);
  const photoInputRef   = useRef(null);
  const portraitPollRef = useRef(null);
  const recognitionRef  = useRef(null);

  const isAdmin          = credits.is_admin;
  const isFreeTier       = !isAdmin && !credits.plan && !credits.has_paid;
  const animateCover     = !isFreeTier && animateCoverPref;
  const isMusicPlan      = ['music_starter', 'music_pro', 'music_agency'].includes(credits.plan);
  const canShowExplicit  = true;
  const canYouTube       = isAdmin || ['agency', 'enterprise'].includes(credits.plan) || isMusicPlan;
  const didPlanOk        = isAdmin || ['agency', 'enterprise', 'music_pro', 'music_agency'].includes(credits.plan);
  const canDid           = didPlanOk && (isAdmin || credits.video_credits > 0);
  const youtubeConnected = credits.youtube_connected;
  const ytConnectedParam = new URLSearchParams(location.search).get('youtube');
  const cost           = isKidsMode ? 1 : selGenres.size;
  // Before credits load, optimistically allow — server rejects if truly insufficient
  const canAfford      = isAdmin || !creditsLoaded || (credits.balance >= cost && cost > 0);
  const canGenerate    = cost > 0 && canAfford && !generating && (
    isKidsMode
      ? true
      : isRoastMode
        ? roastName.trim().length > 0
        : (!useCustomLyrics || customLyricsText.trim().length > 0)
  );
  if (process.env.NODE_ENV === 'development') {
    // eslint-disable-next-line no-console
    console.log('[Generate] disabled:', !canGenerate, { cost, creditsLoaded, balance: credits.balance, canAfford, generating, isKidsMode, useCustomLyrics });
  }
  const creditExceeded = !isAdmin && cost > 0 && cost > credits.balance;
  const generateEffective = isOnline ? canGenerate : true;

  const fetchCredits = useCallback(async () => {
    try {
      const r = await fetch(`${BACKEND_URL}/api/users/me/song_credits`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (r.ok) setCredits(await r.json());
    } catch (_) {}
    finally { setCreditsLoaded(true); }
  }, [token]);

  const fetchLibrary = useCallback(async () => {
    try {
      console.log('[SongsPage] Fetching library, token present:', !!token);
      const r = await fetch(`${BACKEND_URL}/api/lyrics`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      console.log('[SongsPage] /api/lyrics status:', r.status);
      if (!r.ok) {
        console.log('[SongsPage] /api/lyrics failed — body:', await r.text().catch(() => '(unreadable)'));
        return;
      }
      const { lyrics } = await r.json();
      console.log('[SongsPage] lyrics count:', lyrics?.length, 'ids:', lyrics?.map(l => l.id));
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
      setFavourites(new Set(flat.filter(v => v.is_favourite).map(v => v.variant_id)));
      setPublicVariants(new Set(flat.filter(v => v.is_public).map(v => v.variant_id)));

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

      const newMusicVideoUrls = {};
      for (const v of flat) {
        if (v.music_video_url) newMusicVideoUrls[v.variant_id] = v.music_video_url;
      }
      console.log('[MusicVideo] variants with music_video_url:', Object.keys(newMusicVideoUrls).length, newMusicVideoUrls);
      setMusicVideoUrls((prev) => ({ ...prev, ...newMusicVideoUrls }));
    } catch (_) {}
  }, [token]);

  const fetchPlaylists = useCallback(async () => {
    try {
      const r = await fetch(`${BACKEND_URL}/api/playlists`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (r.ok) setPlaylists(await r.json());
    } catch (_) {}
  }, [token]);

  const handleAddToPlaylist = useCallback(async (variantId, playlistId) => {
    try {
      const r = await fetch(`${BACKEND_URL}/api/playlists/${playlistId}/songs`, {
        method: 'POST',
        headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
        body: JSON.stringify({ variant_id: variantId }),
      });
      if (r.ok) return await r.json();
      return null;
    } catch (_) { return null; }
  }, [token]);

  const handleCreatePlaylist = async (e) => {
    e.preventDefault();
    const name = newPlName.trim();
    if (!name) return;
    setNewPlLoading(true);
    try {
      const r = await fetch(`${BACKEND_URL}/api/playlists`, {
        method: 'POST',
        headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
        body: JSON.stringify({ name }),
      });
      if (r.ok) {
        const pl = await r.json();
        setPlaylists(prev => [...prev, pl]);
        setNewPlModal(false);
        setNewPlName('');
      }
    } catch (_) {}
    setNewPlLoading(false);
  };

  useEffect(() => {
    if (!isOnline) return;
    fetchCredits();
    fetchLibrary();
    fetchPlaylists();
  }, [fetchCredits, fetchLibrary, fetchPlaylists, isOnline]);

  // Kids mode and Roast mode force explicit off and hide the toggle
  useEffect(() => { if (isKidsMode || isRoastMode) setExplicit(false); }, [isKidsMode, isRoastMode]);

  const handleExplicitToggle = () => {
    if (explicit) { setExplicit(false); return; }
    setPinInput(''); setPinError(''); setPinModalOpen(true);
  };
  const handlePinSubmit = () => {
    const savedPin = localStorage.getItem('zeus_explicit_pin') || '1234';
    if (pinInput === savedPin) {
      setExplicit(true); setPinModalOpen(false); setPinInput(''); setPinError('');
    } else {
      setPinError('Incorrect PIN');
    }
  };

  useEffect(() => {
    if (!user) return;
    setSoundPersona(
      user.sound_persona_id
        ? {
            sound_persona_id: user.sound_persona_id,
            sound_persona_title: user.sound_persona_title,
            sound_persona_variant_id: user.sound_persona_variant_id,
          }
        : null
    );
  }, [user]);

  // First-visit timestamp + re-trigger banner
  useEffect(() => {
    if (!localStorage.getItem('zeus_first_visit_songs')) {
      localStorage.setItem('zeus_first_visit_songs', Date.now().toString());
    }
  }, []);

  useEffect(() => {
    const done = localStorage.getItem('zeus_onboarding_done');
    const firstVisit = parseInt(localStorage.getItem('zeus_first_visit_songs') || '0');
    const under24h = Date.now() - firstVisit < 24 * 60 * 60 * 1000;
    if (done && library.length === 0 && under24h) setShowRetrigger(true);
    else setShowRetrigger(false);
  }, [library.length]);

  // Pending auto-generate from onboarding "Make My First Song"
  useEffect(() => {
    if (!pendingAutoGen || selGenres.size === 0) return;
    setPendingAutoGen(null);
    handleGenerate();
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [pendingAutoGen, selGenres]);

  useEffect(() => {
    localStorage.setItem('zeus_animated_covers', animateCoverPref ? 'true' : 'false');
  }, [animateCoverPref]);

  useEffect(() => {
    if (!showWelcome) return;
    const t = setTimeout(() => setShowWelcome(false), 10000);
    return () => clearTimeout(t);
  }, [showWelcome]);

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
          setActiveJob((prev) => {
            if (!prev) return null;
            const tracked = new Set(prev.variants.map((v) => v.variant_id));
            return {
              ...prev,
              variants: d.variants
                .filter((v) => tracked.has(v.variant_id))
                .map((v) => ({ ...v, title: prev.title })),
            };
          });
        }
      } catch (_) {}
    }, 5000);
    return () => clearTimeout(pollTimerRef.current);
  }, [activeJob, token, fetchCredits, fetchLibrary]);

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

  // Music video URL polling (30s) — silently re-fetches library while videos are pending
  useEffect(() => {
    const hasPending = library.some(v => v.image_url && !musicVideoUrls[v.variant_id]);
    if (!hasPending) return;
    const t = setTimeout(fetchLibrary, 30_000);
    return () => clearTimeout(t);
  }, [library, musicVideoUrls, fetchLibrary]);

  // Cleanup all stems poll intervals on unmount
  useEffect(() => {
    return () => {
      Object.values(stemsPollRef.current).forEach(clearInterval);
    };
  }, []);

  useEffect(() => () => clearTimeout(lockToastTimer.current), []);

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

  const handleVoicePreview = (voiceKey) => {
    // Toggle off: user taps the same voice that is currently playing
    if (previewingVoice === voiceKey && previewAudioRef.current) {
      previewAudioRef.current.onpause = null; // prevent double-clear
      previewAudioRef.current.pause();
      previewAudioRef.current = null;
      setPreviewingVoice(null);
      return;
    }
    // Stop any current preview without triggering the onpause clear
    if (previewAudioRef.current) {
      previewAudioRef.current.onpause = null;
      previewAudioRef.current.pause();
      previewAudioRef.current = null;
    }
    // Pre-generated file — play instantly, no API fetch needed
    const url = `${BACKEND_URL}/files/voice-previews/${voiceKey}.mp3`;
    const audio = new Audio(url);
    // onpause fires when audioManager stops this preview (e.g. a story or song starts)
    audio.onpause = () => { setPreviewingVoice(null); previewAudioRef.current = null; };
    audio.onended = () => { setPreviewingVoice(null); previewAudioRef.current = null; };
    previewAudioRef.current = audio;
    setPreviewingVoice(voiceKey);
    audioManager.play(audio, 'voice-preview');
  };

  const handleGenerate = async () => {
    setError('');
    setGenerating(true);
    const KIDS_MUSIC_GENRES = {
      nursery:  ['acoustic'],
      funpop:   ['pop'],
      acoustic: ['acoustic'],
      piano:    ['classical'],
      reggae:   ['reggae'],
    };
    try {
      let requestBody;
      if (isKidsMode) {
        const kidsBrief = [
          mainCharacter.trim() && `Main character: ${mainCharacter.trim()}`,
          storyEvent.trim()    && `What happens: ${storyEvent.trim()}`,
          kidsAgeRange === 'tiny_tots'    && 'Age range: tiny tots aged 2-4',
          kidsAgeRange === 'little_ones'  && 'Age range: little ones aged 4-6',
          kidsAgeRange === 'big_kids'     && 'Age range: big kids aged 7-10',
        ].filter(Boolean).join('. ');
        requestBody = {
          brief: kidsBrief,
          genres: KIDS_MUSIC_GENRES[kidsMusicStyle] || ['pop'],
          song_title: songTitle.trim() || undefined,
          animate_cover: animateCover,
          kids_story: true,
          kids_mode: kidsSubMode,
          kids_age_range: kidsAgeRange || undefined,
          accent: kidsSubMode === 'story' ? (kidsNarratorVoice || undefined) : (kidsAccent || undefined),
          child_voice: kidsSubMode === 'story' ? (kidsChildVoice || undefined) : undefined,
          character_voice: kidsSubMode === 'story' ? (kidsCharacterVoice || undefined) : undefined,
          story_language: kidsSubMode === 'story' ? (storyLanguage || 'english') : undefined,
        };
        if (process.env.NODE_ENV === 'development') console.log('Kids Mode request:', requestBody);
      } else if (isRoastMode) {
        requestBody = {
          brief: `Roast song about ${roastName.trim()}`,
          genres: Array.from(selGenres),
          song_title: songTitle.trim() || undefined,
          animate_cover: animateCover,
          is_roast: true,
          roast_name: roastName.trim(),
          roast_details: roastDetails.trim() || undefined,
          roast_vibe: roastVibe,
          ...(showAdvanced ? {
            accent: accent || undefined,
            model_version: modelVersion,
          } : {}),
        };
      } else {
        console.log('animate_cover:', animateCover);
        if (genreBlend && genreB) console.log('Genre blend:', genreB, 'ratio:', blendRatio);
        requestBody = {
          brief: useCustomLyrics ? (songTitle.trim() || 'Custom song') : brief.trim(),
          genres: Array.from(selGenres),
          custom_lyrics: useCustomLyrics ? customLyricsText.trim() : undefined,
          inspired_by_descriptors: artistDescriptors || undefined,
          song_title: songTitle.trim() || undefined,
          animate_cover: animateCover,
          ...(showAdvanced ? {
            vocal_gender: vocalGender || undefined,
            accent: accent || undefined,

            tempo: tempo || undefined,
            tempo_bpm: tempo === 'custom' ? tempoBpm : undefined,
            model_version: modelVersion,
            explicit: explicit || undefined,
            instrumental: vocalMode === 'instrumental' || undefined,
            intermittent_vocals: vocalMode === 'intermittent' || undefined,
            negative_tags: negativeTags.trim() || undefined,
            genre_b: genreBlend && genreB ? genreB : undefined,
            blend_ratio: genreBlend && genreB ? blendRatio : undefined,
            healing_frequency: selGenres.has('healingfrequency') ? healingFrequency : undefined,
          } : {}),
        };
      }
      const r = await fetch(`${BACKEND_URL}/api/songs/generate`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
        body: JSON.stringify(requestBody),
      });
      const d = await r.json();
      if (!r.ok) throw new Error(d.detail || 'Generation failed');
      const _storyUrl = d.story_audio_url
        ? (d.story_audio_url.startsWith('http') ? d.story_audio_url : `${BACKEND_URL}${d.story_audio_url}`)
        : null;
      setActiveJob({
        lyric_id: d.lyric_id,
        title: d.title,
        variants: d.variants.map((v) => {
          const tag = v.genre_tag || v.genre || null;
          return {
            ...v,
            title: d.title,
            genre_tag: tag,
            mp3_url: tag === 'kids_story' ? _storyUrl : (v.mp3_url || null),
          };
        }),
      });
      setCredits((p) => ({ ...p, balance: Math.max(0, p.balance - cost) }));
      setBrief('');
      setSongTitle('');
      setSelGenres(new Set());
      setInspiredBy('');
      setArtistDescriptors('');
      setCustomLyricsText('');
      setUseCustomLyrics(false);
      setMainCharacter('');
      setStoryEvent('');
      setRoastName('');
      setRoastDetails('');
      setRoastVibe('gentle');
    } catch (e) {
      setError(e.message);
    } finally {
      setGenerating(false);
    }
  };

  const showOfflineToast = useCallback((msg = "You're offline — reconnect to create songs") => {
    setOfflineToast(msg);
    clearTimeout(offlineToastRef.current);
    offlineToastRef.current = setTimeout(() => setOfflineToast(''), 3500);
  }, []);

  const handleSaveOffline = useCallback(async (song) => {
    try {
      await saveForOffline(song);
    } catch (err) {
      if (err?.isQuota) {
        showOfflineToast('Not enough storage — remove a saved song to free space');
      }
    }
  }, [saveForOffline, showOfflineToast]);

  const handlePlayOffline = useCallback(async (song) => {
    try {
      const blobUrl = await getOfflineAudioUrl(song.variant_id);
      if (!blobUrl) {
        showOfflineToast('Song file not found — try saving it again while online');
        return;
      }
      playOne({ ...song, mp3_url: blobUrl });
    } catch (_) {}
  }, [getOfflineAudioUrl, playOne, showOfflineToast]);

  const handleTopup = async (pack) => {
    setTopupLoading(pack);
    try {
      const r = await fetch(`${BACKEND_URL}/api/songs/payg`, {
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

  const handleAnimationTopup = async (pack) => {
    setTopupLoading(pack);
    try {
      const r = await fetch(`${BACKEND_URL}/api/songs/animation-topup`, {
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

  const handleTelegramPost = useCallback(async (variant, songTitle) => {
    const genre = gLabel(variant.genre_tag || '');
    const message = `🎵 <b>${songTitle || 'New Song'}</b> — ${genre}\n\nCreated with Zeus Beats AI Music\n🌐 zeusbeats.com`;
    const r = await fetch(`${BACKEND_URL}/api/telegram/post`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
      body: JSON.stringify({ message, image_url: variant.image_url || null }),
    });
    if (!r.ok) throw new Error('Telegram post failed');
  }, [token]);

  const handleRegenerate = useCallback(async (variantId, genreTag, songTitle) => {
    const res = await fetch(`${BACKEND_URL}/api/songs/variants/${variantId}/regenerate`, {
      method: 'POST',
      headers: { Authorization: `Bearer ${token}` },
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || 'Regenerate failed');
    setCredits((p) => ({ ...p, balance: Math.max(0, p.balance - 1) }));
    setActiveJob({
      lyric_id: data.lyric_id,
      title: songTitle,
      variants: [{ variant_id: data.variant_id, genre_tag: genreTag, status: 'generating', title: songTitle }],
    });
  }, [token]);

  const handleToggleFavourite = useCallback(async (variantId) => {
    setFavourites(prev => {
      const next = new Set(prev);
      if (next.has(variantId)) next.delete(variantId); else next.add(variantId);
      return next;
    });
    try {
      await fetch(`${BACKEND_URL}/api/songs/variants/${variantId}/favourite`, {
        method: 'PATCH',
        headers: { Authorization: `Bearer ${token}` },
      });
    } catch (_) {
      setFavourites(prev => {
        const next = new Set(prev);
        if (next.has(variantId)) next.delete(variantId); else next.add(variantId);
        return next;
      });
    }
  }, [token]);

  const handleShareToggle = useCallback(async (variantId) => {
    const wasPublic = publicVariants.has(variantId);
    setPublicVariants(prev => {
      const next = new Set(prev);
      if (next.has(variantId)) next.delete(variantId); else next.add(variantId);
      return next;
    });
    try {
      const res = await fetch(`${BACKEND_URL}/api/songs/variants/${variantId}/share`, {
        method: 'PATCH',
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!res.ok) throw new Error('share toggle failed');
    } catch (_) {
      setPublicVariants(prev => {
        const next = new Set(prev);
        if (wasPublic) next.add(variantId); else next.delete(variantId);
        return next;
      });
    }
  }, [token, publicVariants]);

  const handleYouTubeClick = useCallback((variant, titleArg) => {
    console.log('YouTube upload clicked — canYouTube:', canYouTube, 'connected:', youtubeConnected, 'plan:', credits.plan, 'variant:', variant?.variant_id);
    if (!canYouTube) {
      setYtUpgradePrompt(true);
      return;
    }
    if (!youtubeConnected) {
      console.log('YouTube not connected — redirecting to OAuth');
      window.location.href = `${BACKEND_URL}/api/youtube/auth?token=${token}&origin=beats`;
      return;
    }
    setYtModal({ ...variant, title: titleArg || variant.title });
  }, [canYouTube, youtubeConnected, token, credits.plan]);

  const handleGetStems = async (variantId) => {
    try {
      const r = await fetch(`${BACKEND_URL}/api/songs/variants/${variantId}/stems`, {
        method: 'POST',
        headers: { Authorization: `Bearer ${token}` },
      });
      const data = await r.json();
      if (!r.ok) { alert(data.detail || 'Could not start stem separation'); return; }
      setStemsData(prev => ({ ...prev, [variantId]: data }));
      if (data.stems_status === 'pending') {
        const intervalId = setInterval(async () => {
          const pr = await fetch(`${BACKEND_URL}/api/songs/variants/${variantId}/stems`, {
            headers: { Authorization: `Bearer ${token}` },
          });
          if (!pr.ok) return;
          const pd = await pr.json();
          setStemsData(prev => ({ ...prev, [variantId]: pd }));
          if (pd.stems_status !== 'pending') {
            clearInterval(stemsPollRef.current[variantId]);
            delete stemsPollRef.current[variantId];
          }
        }, 5000);
        stemsPollRef.current[variantId] = intervalId;
      }
    } catch {
      alert('Network error starting stem separation');
    }
  };

  const handleLockSound = useCallback(async (variant, title) => {
    const isPaid =
      user?.is_admin ||
      (user?.subscription_status === 'active' &&
        ['music_starter', 'music_pro', 'music_agency'].includes(user?.subscription_plan));
    if (!isPaid) {
      clearTimeout(lockToastTimer.current);
      setLockToast('Upgrade to Music Starter to unlock Your Sound 🔒');
      lockToastTimer.current = setTimeout(() => setLockToast(''), 4000);
      return;
    }
    try {
      const resp = await fetch(`${BACKEND_URL}/api/user/sound`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
        body: JSON.stringify({ variant_id: variant.variant_id }),
      });
      const data = await resp.json();
      if (!resp.ok) {
        if (data.detail === 'upgrade_required') {
          clearTimeout(lockToastTimer.current);
          setLockToast('Upgrade to Music Starter to unlock Your Sound 🔒');
          lockToastTimer.current = setTimeout(() => setLockToast(''), 4000);
          return;
        }
        throw new Error(data.detail || 'Failed to lock sound');
      }
      setSoundPersona(data);
      clearTimeout(lockToastTimer.current);
      setLockToast(`Your Sound locked to "${data.sound_persona_title}" 🔒`);
      lockToastTimer.current = setTimeout(() => setLockToast(''), 4000);
    } catch (err) {
      clearTimeout(lockToastTimer.current);
      setLockToast(`Error: ${err.message}`);
      lockToastTimer.current = setTimeout(() => setLockToast(''), 4000);
    }
  }, [user, token]);

  const handleResetSound = useCallback(async () => {
    try {
      await fetch(`${BACKEND_URL}/api/user/sound`, {
        method: 'DELETE',
        headers: { Authorization: `Bearer ${token}` },
      });
      setSoundPersona(null);
    } catch (err) {
      console.error('Failed to reset sound:', err);
    }
  }, [token]);

  const handleCoverSubmit = async () => {
    if (!coverModal || !coverLyrics.trim()) return;
    setCoverLoading(true);
    setCoverError('');
    try {
      const r = await fetch(`${BACKEND_URL}/api/songs/variants/${coverModal.variantId}/cover`, {
        method: 'POST',
        headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
        body: JSON.stringify({ lyrics: coverLyrics.trim() }),
      });
      const data = await r.json();
      if (!r.ok) { setCoverError(data.detail || 'Something went wrong'); return; }
      setCoverModal(null);
      setCoverLyrics('');
      setCoverToast(true);
      setTimeout(() => setCoverToast(false), 4000);
    } catch {
      setCoverError('Network error. Try again.');
    } finally {
      setCoverLoading(false);
    }
  };

  const handleYouTubeUpload = async () => {
    if (!ytModal) return;
    const vId = ytModal.variant_id;
    const vTitle = ytModal.title;
    setYtModal(null);
    setYtStatus((prev) => ({ ...prev, [vId]: 'uploading' }));
    setYtErrors((prev) => { const n = { ...prev }; delete n[vId]; return n; });
    try {
      const r = await fetch(`${BACKEND_URL}/api/songs/variants/${vId}/upload-youtube`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
        body: JSON.stringify({ privacy: ytPrivacy, title: vTitle }),
      });
      let d = {};
      try { d = await r.json(); } catch (_) {}
      if (r.status === 401) { fetchCredits(); throw new Error('YouTube session expired — please reconnect your account'); }
      if (!r.ok) throw new Error(d.detail || `Upload failed (HTTP ${r.status})`);
      setYtStatus((prev) => ({ ...prev, [vId]: 'done' }));
      setYtUrls((prev) => ({ ...prev, [vId]: d.youtube_url }));
    } catch (err) {
      const msg = err?.message || 'Upload failed — network or server error';
      console.error('YouTube upload failed:', err);
      setYtErrors((prev) => ({ ...prev, [vId]: msg }));
      setYtStatus((prev) => ({ ...prev, [vId]: 'error' }));
    }
  };

  const closeAvatarModal = () => {
    setAvatarModal(null);
    setPortraitGenerating(false);
    setPortraitJobId(null);
    setPortraitImageUrl(null);
    setPortraitTimedOut(false);
    if (portraitPollRef.current) clearTimeout(portraitPollRef.current);
  };

  const handleAvatarClick = useCallback(async (variant, titleArg) => {
    if (!canDid) return;
    setSelectedAvatarUrl(null);
    setPortraitGenerating(false);
    setPortraitJobId(null);
    setPortraitImageUrl(null);
    setPortraitTimedOut(false);
    setAvatarModal({ ...variant, title: titleArg || variant.title });
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
  }, [canDid, token, avatars.length]);

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

  const handleDeleteVariant = useCallback(async (variantId) => {
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
  }, [token]);

  const handleOpenRemake = useCallback((variantId, title) => {
    setRemakeModal({ variantId, title });
  }, []);

  const handleRemake = async () => {
    if (!remakeGenre || remakeLoading) return;
    setRemakeLoading(true);
    setRemakeError('');
    try {
      const res = await fetch(`${BACKEND_URL}/api/songs/variants/${remakeModal.variantId}/remake`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
        body: JSON.stringify({ genre: remakeGenre, style_override: remakeStyle || null }),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: 'Remake failed' }));
        throw new Error(err.detail || 'Remake failed');
      }
      const data = await res.json();
      setRemakeModal(null);
      setRemakeGenre('');
      setRemakeStyle('');
      setCredits((p) => ({ ...p, balance: Math.max(0, p.balance - 1) }));
      setActiveJob({
        lyric_id: data.lyric_id,
        title: remakeModal.title,
        variants: [{ variant_id: data.variant_id, genre_tag: remakeGenre, status: 'generating', title: remakeModal.title }],
      });
    } catch (err) {
      setRemakeError(err.message);
    } finally {
      setRemakeLoading(false);
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

  const startListening = () => {
    const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SR) return;
    if (listening) { recognitionRef.current?.stop(); return; }
    const recognition = new SR();
    recognition.lang = 'en-GB';
    recognition.continuous = false;
    recognition.interimResults = false;
    recognition.onstart = () => setListening(true);
    recognition.onresult = (e) => setBrief(e.results[0][0].transcript);
    recognition.onerror = () => setListening(false);
    recognition.onend = () => setListening(false);
    recognitionRef.current = recognition;
    recognition.start();
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

  const activeLyricId   = activeJob?.lyric_id;
  const displayLibrary  = isOnline ? library : savedSongs;
  const filteredLibrary = useMemo(() => {
    const q = search.trim().toLowerCase();
    return displayLibrary
      .filter((v) => activeLyricId == null || v.lyric_id !== activeLyricId)
      .filter((v) => !q ||
        v.title?.toLowerCase().includes(q) ||
        v.genre_tag?.toLowerCase().includes(q) ||
        gLabel(v.genre_tag).toLowerCase().includes(q) ||
        v.brief?.toLowerCase().includes(q)
      );
  }, [displayLibrary, activeLyricId, search]);

  const MAX_RENDERED = 30;
  const [windowStart, setWindowStart] = useState(0);

  const tabFilteredLibrary = useMemo(() => {
    if (activeTab === 'favourites') return filteredLibrary.filter(v => favourites.has(v.variant_id));
    if (activeTab === 'recent') return filteredLibrary.slice(0, 10);
    return filteredLibrary;
  }, [filteredLibrary, activeTab, favourites]);

  const visibleLibrary = useMemo(
    () => tabFilteredLibrary.slice(windowStart, windowStart + MAX_RENDERED),
    [tabFilteredLibrary, windowStart]
  );

  useEffect(() => { setWindowStart(0); }, [activeTab, search]);

  return (
    <>
      {showTour && (
        <OnboardingTour
          balance={credits.balance}
          onComplete={() => setShowTour(false)}
          onAutoGenerate={(genres) => {
            setSelGenres(new Set(genres.filter(g => GENRES.includes(g))));
            setPendingAutoGen(genres);
          }}
        />
      )}

      <style>{PAGE_CSS}</style>
      <input
        ref={photoInputRef}
        type="file"
        accept="image/jpeg,image/png,image/webp"
        style={{ display: 'none' }}
        onChange={handlePhotoUpload}
      />
      <div style={{ background: '#0b0b14', minHeight: '100vh', color: '#f0eeff', overflowX: 'hidden' }}>

        <BeatsDashboardHeader />
        <EmailVerificationBanner user={user} token={token} app="beats" />

        <div className="songs-bar-wrap" style={{ borderBottom: '1px solid rgba(255,255,255,0.05)', padding: '10px 24px' }}>
          <div style={{ maxWidth: 880, margin: '0 auto', display: 'flex', alignItems: 'center', gap: 16, flexWrap: 'wrap' }}>
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
              {isAdmin ? t('songs.unlimited') : t('songs.songsBalance', { balance, allowance })}
            </span>
            {didPlanOk && !isAdmin && (
              <span style={{ fontSize: 13, color: credits.video_credits === 0 ? '#f87171' : '#666', whiteSpace: 'nowrap' }}>
                {t('songs.videoCredits', { count: credits.video_credits })}
              </span>
            )}
            {!isFreeTier && !isAdmin && credits.premium_monthly_allowance > 0 && (
              <span style={{ fontSize: 13, color: credits.premium_credits === 0 ? '#f87171' : '#666', whiteSpace: 'nowrap' }}>
                · {credits.premium_credits} premium credit{credits.premium_credits !== 1 ? 's' : ''} remaining
              </span>
            )}
            {!isAdmin && !isIOSWebView && balance <= 2 && (
              <Link to="/billing" style={{ fontSize: 13, color: barColor, fontWeight: 600, whiteSpace: 'nowrap' }}>
                {t('songs.topUp')}
              </Link>
            )}
          </div>
        </div>

        {!isAdmin && !credits.plan && !isIOSWebView && (
          <div style={{ background: 'rgba(0,240,255,0.04)', borderBottom: '1px solid rgba(0,240,255,0.08)', padding: '8px 24px', textAlign: 'center' }}>
            <span style={{ fontSize: 12, color: '#cccccc' }}>
              {t('songs.upgradeBanner')}{' '}
              <Link to="/billing" style={{ color: '#00f0ff', fontWeight: 600 }}>→ {t('songs.viewPlans')}</Link>
            </span>
          </div>
        )}
        {!isAdmin && !credits.plan && isIOSWebView && (
          <div style={{ padding: '6px 24px' }}><IOSWebViewBanner /></div>
        )}

        {!isAdmin && balance <= 0 && (
          <div style={{ borderBottom: '1px solid rgba(0,240,255,0.12)', padding: '16px 24px' }}>
            <div className="topup-section" style={{ maxWidth: 880, margin: '0 auto', padding: '20px 24px', borderRadius: 14, border: '1px solid #00f0ff', background: 'rgba(0,240,255,0.03)' }}>
              <h3 style={{ fontFamily: "'Orbitron', sans-serif", fontSize: 13, fontWeight: 700, color: '#00f0ff', marginBottom: 14, letterSpacing: '0.5px' }}>
                ⚡ Buy More Songs
              </h3>
              <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap' }}>
                {SONG_PACKS.map(({ pack, label, price }) => (
                  <button
                    key={pack}
                    className="topup-btn"
                    onClick={() => handleTopup(pack)}
                    disabled={topupLoading !== null}
                    style={{ padding: '11px 22px', borderRadius: 10, border: '1px solid rgba(0,240,255,0.5)', background: 'linear-gradient(135deg, rgba(0,240,255,0.1) 0%, rgba(0,191,255,0.08) 100%)', color: '#00f0ff', fontSize: 13, fontWeight: 700, cursor: topupLoading ? 'default' : 'pointer', transition: 'all 0.2s', letterSpacing: '0.3px' }}
                  >
                    {topupLoading === pack ? t('songs.redirecting') : `${label} — ${price}`}
                  </button>
                ))}
              </div>
              <p style={{ fontSize: 11, color: '#4a9fb5', marginTop: 12, marginBottom: 0 }}>
                Credits never expire · No subscription needed
              </p>
            </div>
          </div>
        )}

        {!isAdmin && !isFreeTier && animateCoverPref && credits.premium_credits === 0 && (
          <div style={{ borderBottom: '1px solid rgba(167,139,250,0.12)', padding: '16px 24px' }}>
            <div style={{ maxWidth: 880, margin: '0 auto', padding: '20px 24px', borderRadius: 14, border: '1px solid rgba(167,139,250,0.4)', background: 'rgba(124,58,237,0.04)' }}>
              <h3 style={{ fontFamily: "'Orbitron', sans-serif", fontSize: 13, fontWeight: 700, color: '#c4b5fd', marginBottom: 14, letterSpacing: '0.5px' }}>
                🎬 Buy Premium Credits
              </h3>
              <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap' }}>
                {ANIMATION_PACKS.map(({ pack, label, price }) => (
                  <button
                    key={pack}
                    onClick={() => handleAnimationTopup(pack)}
                    disabled={topupLoading !== null}
                    style={{ padding: '11px 22px', borderRadius: 10, border: '1px solid rgba(167,139,250,0.5)', background: 'linear-gradient(135deg, rgba(124,58,237,0.12) 0%, rgba(139,92,246,0.08) 100%)', color: '#c4b5fd', fontSize: 13, fontWeight: 700, cursor: topupLoading ? 'default' : 'pointer', transition: 'all 0.2s', letterSpacing: '0.3px' }}
                  >
                    {topupLoading === pack ? t('songs.redirecting') : `${label} — ${price}`}
                  </button>
                ))}
              </div>
              <p style={{ fontSize: 11, color: '#7c3aed', marginTop: 12, marginBottom: 0 }}>
                Credits never expire · Use for animated cover art or stem separation
              </p>
            </div>
          </div>
        )}

        {showRetrigger && (
          <div style={{ borderBottom: '1px solid rgba(0,240,255,0.1)', padding: '10px 24px', background: 'rgba(0,240,255,0.03)' }}>
            <div style={{ maxWidth: 880, margin: '0 auto', display: 'flex', alignItems: 'center', gap: 12, flexWrap: 'wrap' }}>
              <span style={{ fontSize: 14, color: 'rgba(255,255,255,0.6)', flex: 1 }}>
                👋 Haven't made your first song yet? We'll help you get started ⚡
              </span>
              <button
                onClick={() => { setShowRetrigger(false); setShowTour(true); localStorage.removeItem('zeus_onboarding_done'); }}
                style={{ padding: '8px 18px', borderRadius: 8, background: 'rgba(0,240,255,0.12)', border: '1px solid rgba(0,240,255,0.4)', color: '#00f0ff', fontSize: 13, fontWeight: 600, cursor: 'pointer' }}
              >
                Show me how
              </button>
              <button onClick={() => setShowRetrigger(false)} style={{ background: 'none', border: 'none', color: '#444', fontSize: 18, cursor: 'pointer', lineHeight: 1, padding: '4px 6px' }}>×</button>
            </div>
          </div>
        )}

        <div className="songs-content-wrap" style={{ maxWidth: 880, margin: '0 auto', padding: '32px 24px 80px' }}>
          {!isOnline && <OfflineBanner />}

          {showWelcome && (
            <div style={{
              background: 'rgba(0,0,0,0.6)',
              border: '1px solid #00F0FF',
              borderRadius: 10,
              padding: '14px 18px',
              marginBottom: 24,
              color: '#e0fffe',
              fontSize: 14,
              boxShadow: '0 0 18px rgba(0,240,255,0.15)',
              display: 'flex',
              alignItems: 'flex-start',
              gap: 12,
            }}>
              <span style={{ fontSize: 20, lineHeight: 1 }}>🎵</span>
              <div style={{ flex: 1 }}>
                <strong style={{ color: '#00F0FF', display: 'block', marginBottom: 4 }}>Welcome to Zeus Beats!</strong>
                <span>You have 3 free songs to get started. Generate your first track below — pick a genre and hit Create.</span>
              </div>
              <button
                onClick={() => setShowWelcome(false)}
                style={{ background: 'none', border: 'none', color: '#00F0FF', cursor: 'pointer', fontSize: 18, lineHeight: 1, padding: 0, flexShrink: 0 }}
                aria-label="Dismiss"
              >×</button>
            </div>
          )}

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
              {t('songs.topupSuccess')}
            </div>
          )}

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
              {t('songs.ytConnectedSuccess')}
            </div>
          )}
          {ytConnectedParam === 'error' && (
            <div style={{
              background: 'rgba(251,191,36,0.1)',
              border: '2px solid rgba(251,191,36,0.5)',
              borderRadius: 10,
              padding: '14px 18px',
              marginBottom: 24,
              color: '#fbbf24',
              fontWeight: 600,
              fontSize: 14,
            }}>
              ⚠️ {t('songs.ytConnectedFail')}
              <div style={{ fontSize: 12, fontWeight: 400, marginTop: 6, color: 'rgba(251,191,36,0.85)' }}>
                If you're seeing this on a different account, the Google OAuth app may still be in testing mode — only approved test accounts can connect. Contact the app owner to add your Google account as a test user.
              </div>
            </div>
          )}

          <div style={{
            background: 'rgba(255,255,255,0.025)',
            border: '1px solid rgba(255,255,255,0.08)',
            borderRadius: 16,
            padding: '28px 28px 24px',
            marginBottom: 12,
          }}>
            <h1 style={{ fontSize: '1.35rem', fontWeight: 700, color: '#f0eeff', marginBottom: 4 }}>
              {t('songs.pageTitle')}
            </h1>
            <p style={{ color: '#cccccc', fontSize: 14, marginBottom: 14 }}>
              {useCustomLyrics ? t('songs.subtitleOwn') : t('songs.subtitleAI')}
            </p>

            {!isKidsMode && !isRoastMode && (<>
            {/* Custom lyrics toggle */}
            <div style={{ marginBottom: 14, display: 'flex', gap: 8 }}>
              <button
                onClick={() => setUseCustomLyrics(false)}
                style={{ padding: '6px 14px', borderRadius: 20, border: 'none', background: !useCustomLyrics ? '#7c3aed' : 'rgba(255,255,255,0.08)', color: !useCustomLyrics ? '#fff' : 'rgba(255,255,255,0.6)', fontSize: 13, fontWeight: 600, cursor: 'pointer' }}
              >{t('songs.modeAI')}</button>
              <button
                onClick={() => setUseCustomLyrics(true)}
                style={{ padding: '6px 14px', borderRadius: 20, border: 'none', background: useCustomLyrics ? '#7c3aed' : 'rgba(255,255,255,0.08)', color: useCustomLyrics ? '#fff' : 'rgba(255,255,255,0.6)', fontSize: 13, fontWeight: 600, cursor: 'pointer' }}
              >{t('songs.modeOwn')}</button>
            </div>

            {!useCustomLyrics && (
              <>
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6, marginBottom: 10 }}>
                  {SONG_TEMPLATES.map(({ emoji, label, value }) => (
                    <button
                      key={label}
                      onClick={() => setBrief(value)}
                      style={{
                        padding: '4px 10px',
                        borderRadius: 20,
                        border: '1px solid rgba(0,240,255,0.25)',
                        background: 'rgba(0,240,255,0.04)',
                        color: '#00f0ff',
                        fontSize: 11,
                        cursor: 'pointer',
                        transition: 'all 0.15s',
                      }}
                    >{emoji} {label}</button>
                  ))}
                </div>
              <div style={{ position: 'relative', marginBottom: 12 }}>
                <textarea
                  className="songs-textarea"
                  value={brief}
                  onChange={(e) => setBrief(e.target.value)}
                  placeholder={t('songs.briefPlaceholder')}
                  rows={3}
                  style={{
                    width: '100%',
                    boxSizing: 'border-box',
                    background: 'rgba(255,255,255,0.04)',
                    border: '1px solid rgba(255,255,255,0.1)',
                    borderRadius: 10,
                    padding: '12px 42px 12px 14px',
                    color: '#f0eeff',
                    fontSize: 15,
                    resize: 'vertical',
                    fontFamily: 'inherit',
                    outline: 'none',
                    transition: 'border-color 0.2s',
                  }}
                />
                {!!(window.SpeechRecognition || window.webkitSpeechRecognition) && (
                  <button
                    onClick={startListening}
                    className={listening ? 'mic-btn-listening' : ''}
                    title={listening ? t('songs.listenStop') : t('songs.listenStart')}
                    style={{
                      position: 'absolute',
                      top: 8,
                      right: 8,
                      width: 28,
                      height: 28,
                      borderRadius: '50%',
                      border: 'none',
                      background: listening ? '#ef4444' : 'rgba(0,240,255,0.12)',
                      color: listening ? '#fff' : '#00f0ff',
                      cursor: 'pointer',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      fontSize: 13,
                      transition: 'background 0.2s, color 0.2s',
                      flexShrink: 0,
                    }}
                  >
                    🎤
                  </button>
                )}
                {listening && (
                  <p style={{ fontSize: 12, color: '#ef4444', marginTop: 5, marginBottom: 0 }}>{t('songs.listeningLabel')}</p>
                )}
              </div>
              </>
            )}

            {useCustomLyrics && (
              <textarea
                className="songs-textarea"
                value={customLyricsText}
                onChange={(e) => setCustomLyricsText(e.target.value)}
                placeholder={t('songs.lyricsPlaceholder')}
                rows={10}
                style={{
                  width: '100%',
                  boxSizing: 'border-box',
                  background: 'rgba(255,255,255,0.04)',
                  border: '1px solid rgba(255,255,255,0.1)',
                  borderRadius: 10,
                  padding: '12px 14px',
                  color: '#f0eeff',
                  fontSize: 14,
                  resize: 'vertical',
                  fontFamily: 'inherit',
                  outline: 'none',
                  marginBottom: 12,
                  transition: 'border-color 0.2s',
                }}
              />
            )}
            </>)}

            {isRoastMode && (
              <div style={{ marginBottom: 16 }}>
                <p style={{ fontSize: 11, fontWeight: 700, color: '#f87171', letterSpacing: '0.6px', textTransform: 'uppercase', marginBottom: 8 }}>
                  🎤 Who&apos;s It About?
                </p>
                <input
                  type="text"
                  value={roastName}
                  onChange={(e) => setRoastName(e.target.value)}
                  placeholder="Name (e.g. Dave, Uncle Terry, Big Mike)"
                  maxLength={60}
                  style={{ width: '100%', boxSizing: 'border-box', background: 'rgba(248,113,113,0.06)', border: '1px solid rgba(248,113,113,0.30)', borderRadius: 10, padding: '10px 14px', color: '#f0eeff', fontSize: 14, fontFamily: 'inherit', outline: 'none', marginBottom: 12, transition: 'border-color 0.2s' }}
                />
                <p style={{ fontSize: 11, fontWeight: 700, color: '#f87171', letterSpacing: '0.6px', textTransform: 'uppercase', marginBottom: 6 }}>
                  Tell Us About Them
                </p>
                <textarea
                  value={roastDetails}
                  onChange={(e) => setRoastDetails(e.target.value)}
                  placeholder="Funny habits, legendary stories, what they&apos;re known for... (optional but the more you give us, the better the roast!)"
                  rows={3}
                  style={{ width: '100%', boxSizing: 'border-box', background: 'rgba(248,113,113,0.06)', border: '1px solid rgba(248,113,113,0.30)', borderRadius: 10, padding: '10px 14px', color: '#f0eeff', fontSize: 14, resize: 'vertical', fontFamily: 'inherit', outline: 'none', marginBottom: 14, transition: 'border-color 0.2s' }}
                />
                <p style={{ fontSize: 11, fontWeight: 700, color: '#f87171', letterSpacing: '0.6px', textTransform: 'uppercase', marginBottom: 8 }}>
                  Pick the Vibe
                </p>
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: 8, marginBottom: 4 }}>
                  {[
                    ['gentle',   '😄', 'Gentle Banter',     'Warm & affectionate'],
                    ['roast',    '🔥', 'Proper Roast',       'Cheeky, going for it'],
                    ['birthday', '🎂', 'Birthday Piss-take', 'Happy birthday 😬'],
                    ['staghen',  '🍺', 'Stag / Hen Do',      'Raucous send-off'],
                  ].map(([val, emoji, label, desc]) => (
                    <button key={val} onClick={() => setRoastVibe(val)} style={{
                      display: 'flex', flexDirection: 'column', alignItems: 'flex-start', gap: 2,
                      padding: '10px 12px', borderRadius: 10, cursor: 'pointer', transition: 'all 0.15s', textAlign: 'left',
                      border: `2px solid ${roastVibe === val ? '#f87171' : 'rgba(248,113,113,0.25)'}`,
                      background: roastVibe === val ? 'rgba(248,113,113,0.15)' : 'rgba(248,113,113,0.04)',
                      boxShadow: roastVibe === val ? '0 0 14px rgba(248,113,113,0.25)' : 'none',
                    }}>
                      <span style={{ fontSize: 18, lineHeight: 1, marginBottom: 2 }}>{emoji}</span>
                      <span style={{ fontSize: 12, fontWeight: 700, color: roastVibe === val ? '#f87171' : 'rgba(248,113,113,0.7)' }}>{label}</span>
                      <span style={{ fontSize: 10, color: 'rgba(248,113,113,0.5)', lineHeight: 1.3 }}>{desc}</span>
                    </button>
                  ))}
                </div>
              </div>
            )}

            <input
              type="text"
              value={songTitle}
              onChange={(e) => setSongTitle(e.target.value)}
              placeholder={vocalMode === 'instrumental' ? t('songs.titlePlaceholderInstrumental') : t('songs.titlePlaceholderVocals')}
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

            <p style={{ fontSize: 11, fontWeight: 600, color: '#cccccc', letterSpacing: '0.6px', textTransform: 'uppercase', marginBottom: 10 }}>
              {t('songs.styleLabel')}
            </p>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 8, marginBottom: 18 }}>
              {GENRE_CATEGORIES.map(cat => {
                const open = openCats.has(cat.id);
                const selCount = cat.genres.reduce((n, g) => n + (selGenres.has(g) ? 1 : 0), 0);
                return (
                  <div key={cat.id}>
                    <button
                      type="button"
                      onClick={() => toggleCat(cat.id)}
                      aria-expanded={open}
                      style={{
                        width: '100%', display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 8,
                        padding: '9px 12px', borderRadius: 10,
                        border: `1.5px solid ${cat.color}${open ? 'aa' : '40'}`,
                        background: open ? cat.color + '14' : 'transparent',
                        cursor: 'pointer', transition: 'all 0.2s ease', fontFamily: 'inherit',
                      }}
                    >
                      <span style={{ display: 'flex', alignItems: 'center', gap: 9 }}>
                        <span style={{ fontSize: 11, color: cat.color, transition: 'transform 0.2s ease', transform: open ? 'rotate(90deg)' : 'rotate(0deg)', display: 'inline-block' }}>▶</span>
                        <span style={{ fontSize: 12, fontWeight: 700, color: cat.color, letterSpacing: '0.8px', textTransform: 'uppercase' }}>{cat.label}</span>
                      </span>
                      {selCount > 0 && (
                        <span style={{ fontSize: 11, fontWeight: 800, color: '#000', background: cat.color, borderRadius: 10, padding: '1px 8px', minWidth: 20, textAlign: 'center' }}>{selCount}</span>
                      )}
                    </button>
                    {open && (
                      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 7, padding: '10px 2px 4px' }}>
                        {cat.genres.map(g => {
                          const sel = selGenres.has(g);
                          return (
                            <button
                              key={g}
                              onClick={() => toggleGenre(g)}
                              className={sel ? 'genre-pill genre-pill--sel' : 'genre-pill'}
                              style={{
                                '--pill-color': cat.color,
                                '--pill-hover-bg': cat.color + '28',
                                padding: '7px 15px',
                                borderRadius: 20,
                                border: sel ? `2px solid ${cat.color}` : `1.5px solid ${cat.color}55`,
                                background: sel ? cat.color : 'transparent',
                                color: sel ? '#000' : cat.color,
                                fontSize: 13,
                                fontWeight: sel ? 700 : 500,
                                cursor: 'pointer',
                                transition: 'all 0.2s ease',
                                boxShadow: sel ? `0 0 16px ${cat.color}, 0 0 30px ${cat.color}60` : 'none',
                                transform: sel ? 'scale(1.05)' : 'scale(1)',
                              }}
                            >
                              {gLabel(g)}
                            </button>
                          );
                        })}
                      </div>
                    )}
                  </div>
                );
              })}
            </div>

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
                  placeholder={t('songs.artistPlaceholder')}
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
                  <span style={{ position: 'absolute', right: 12, top: '50%', transform: 'translateY(-50%)', fontSize: 12, color: '#cccccc' }}>
                    ···
                  </span>
                )}
              </div>
              {artistDescriptors && !artistLoading && (
                <div style={{ marginTop: 8, display: 'flex', flexWrap: 'wrap', gap: 5, alignItems: 'center' }}>
                  <span style={{ fontSize: 11, color: '#444', fontWeight: 600, letterSpacing: '0.4px', textTransform: 'uppercase', flexShrink: 0 }}>{t('songs.styleTag')}</span>
                  {artistDescriptors.split(',').map((d, i) => (
                    <span key={i} style={{ background: 'rgba(167,139,250,0.08)', border: '1px solid rgba(167,139,250,0.2)', color: '#9b8ec4', borderRadius: 12, padding: '2px 8px', fontSize: 11 }}>
                      {d.trim()}
                    </span>
                  ))}
                </div>
              )}
            </div>

            <button
              onClick={() => setShowAdvanced((v) => !v)}
              style={{
                width: '100%', display: 'flex', alignItems: 'center', gap: 10,
                background: 'rgba(0,240,255,0.06)', border: '1px solid rgba(0,240,255,0.30)',
                borderRadius: 8, padding: '9px 14px', cursor: 'pointer', marginBottom: 14,
              }}
            >
              <span style={{ fontFamily: "'Orbitron', sans-serif", fontSize: 10, fontWeight: 700, color: '#00f0ff', letterSpacing: '0.14em' }}>⚡ {t('songs.advancedOptions')}</span>
              <span style={{ marginLeft: 'auto', color: '#00f0ff', fontSize: 12, fontWeight: 600 }}>{showAdvanced ? t('songs.hideOptions') : t('songs.showOptions')}</span>
            </button>

            {showAdvanced && (
              <div className="adv-grid" style={{
                background: 'rgba(0,240,255,0.04)',
                border: '1px solid #00f0ff',
                borderRadius: 10,
                padding: '18px 20px',
                marginBottom: 18,
                animation: 'advGlow 2.5s ease-in-out infinite',
              }}>
                <div>
                  <p style={{ fontSize: 11, fontWeight: 600, color: '#cccccc', letterSpacing: '0.6px', textTransform: 'uppercase', marginBottom: 8 }}>{t('songs.vocalGenderLabel')}</p>
                  <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
                    {[['', t('songs.vocalEither')], ['m', t('songs.vocalMale')], ['f', t('songs.vocalFemale')], ['duet', t('songs.vocalDuet')]].map(([val, label]) => (
                      <button
                        key={val}
                        onClick={() => setVocalGender(val)}
                        style={{
                          padding: '5px 12px', borderRadius: 6,
                          border: `1px solid ${vocalGender === val ? '#a78bfa' : 'rgba(255,255,255,0.08)'}`,
                          background: vocalGender === val ? 'rgba(167,139,250,0.15)' : 'transparent',
                          color: vocalGender === val ? '#c4b5fd' : '#cccccc',
                          fontSize: 12, cursor: 'pointer', transition: 'all 0.15s',
                        }}
                      >{label}</button>
                    ))}
                  </div>
                </div>

                {!['meditation','healingfrequency'].some(g => selGenres.has(g)) && <div>
                  <p style={{ fontSize: 11, fontWeight: 600, color: '#cccccc', letterSpacing: '0.6px', textTransform: 'uppercase', marginBottom: 8 }}>{t('songs.accentLabel')}</p>
                  <select
                    value={accent}
                    onChange={(e) => setAccent(e.target.value)}
                    style={{ width: '100%', background: 'rgba(255,255,255,0.04)', border: '1px solid rgba(255,255,255,0.1)', borderRadius: 6, padding: '6px 10px', color: accent ? '#c4b5fd' : '#cccccc', fontSize: 13, outline: 'none' }}
                  >
                    <option value="">🎤 Auto (matches your genre)</option>
                    {['British','American (Southern)','Irish','Scottish','Australian','Caribbean','French','Spanish','American Soul','Jamaican','D&B MC','UK Rave MC','British MC Grime','Jazz Vocal','American Hip-Hop','K-Pop','West African','South African','American Phonk','New Jersey / Newark','British African','Jamaican Rasta','West Coast G-Funk','British Street Soul'].map((a) => (
                      <option key={a} value={a}>{a}</option>
                    ))}
                    {[
                      ['Southern American', 'deep Southern American accent, Alabama or Georgia drawl, thick Southern US vowels, slow deliberate Southern delivery, authentic Deep South pronunciation, Tennessee or Mississippi vocal style, warm country Southern tone'],
                      ['UK D&B MC', 'energetic UK drum and bass MC delivery, rapid fire hype, crowd control shouts, classic jungle MC style, rewind calls'],
                      ['UK Jungle MC', 'old school jungle MC flow, ragga influenced delivery, rewind calls, authentic 90s rave MC energy'],
                      ['Bashment MC', 'Jamaican bashment MC delivery, dancehall ragga style, riddim riding vocals, Caribbean MC energy'],
                      ['Jamaican Dancehall', 'fast Jamaican dancehall ragga delivery, aggressive patois flow, digital riddim MC style, bashment energy, rapid fire Jamaican pronunciation'],
                      ['Vocoder / Talk Box', 'vocoder effect on vocals, robotic talk box voice, synthesized voice processing, Zapp and Roger style, computerised speech melody, electro funk vocoder, Roger Troutman talk box technique, robotic singing voice, pitch shifted electronic vocal effect'],
                      ['Cyborg / Synthesised', 'vocoder processed vocals, robotic voice effect, synthesised speech, digital pitch correction, computerised vocal tone, sci-fi robot voice, electronic vocal processing'],
                      ['Punjabi', 'authentic Punjabi vocal delivery, Punjabi mother tongue singer, strong Punjabi pronunciation, Gurmukhī influenced phonetics, traditional Punjabi singing style, bhangra vocal technique, nasal Punjabi tones, desi authentic delivery, not English accent'],
                      ['Spanish Latin', 'authentic Spanish Latin accent, native Spanish speaker singing in Spanish, Cuban or Puerto Rican Caribbean pronunciation, warm Latin vowels, rolling R sounds, natural Spanish flow, not English accent at all'],
                      ['Colombian', 'authentic Colombian accent, Medellin or Bogota pronunciation, warm Colombian Spanish delivery, melodic Colombian vowel sounds, natural Latin warmth, native Colombian Spanish speaker'],
                      ['Puerto Rican', 'authentic Puerto Rican accent, Boricua Spanish pronunciation, Caribbean Puerto Rican delivery, urban San Juan flow, authentic PR Spanish vowels, native Puerto Rican speaker'],
                      ['Cockney Grime', 'thick East London Cockney grime delivery, working class London accent mixed with grime flow, Cockney rhyming slang inflection, hard London vowels, street grime MC style with Cockney twist, authentic East End London road man delivery, sharp clipped Cockney consonants with grime energy'],
                    ].map(([label, value]) => (
                      <option key={label} value={value}>{label}</option>
                    ))}
                    <optgroup label="🎸 Rock & Blues">
                      <option value="classic rock vocalist, powerful raw rock delivery, gritty emotional rock voice, stadium rock energy">🎸 Classic Rock</option>
                      <option value="Southern rock drawl, Alabama Georgia rock delivery, country rock vocal twang, raw swampy Southern rock grit">🤘 Southern Rock</option>
                      <option value="raw blues rock vocalist, gritty soulful blues delivery, Southern blues emotional power, whiskey-soaked blues voice">🎵 Blues Rock</option>
                      <option value="punk rock vocalist, raw aggressive punk delivery, rebellious British punk energy, fast aggressive vocal style">🏴‍☠️ Punk Rock</option>
                    </optgroup>
                    <optgroup label="🎵 Vocal Style">
                      <option value="extremely deep resonant bass-baritone male vocalist, ultra low rich deep voice, velvet smooth deep bass delivery, romantic intimate low register singing, deep chest resonance, powerful low bass vocal presence">🎤 Deep Bass Voice</option>
                      <option value="extremely fast rapid-fire rap delivery, machine gun flow, tongue-twisting fast paced lyrics, technical speed rapping, double-time triple-time flow, intricate fast wordplay, breathless rapid syllable delivery, lightning fast verbal dexterity, hypersped lyrical flow">🔥 Rapid Fire Rap</option>
                    </optgroup>
                    <optgroup label="🇪🇺 European Languages (lyrics in that language)">
                      <option value="French">🇫🇷 French</option>
                      <option value="Spanish">🇪🇸 Spanish</option>
                      <option value="Portuguese">🇵🇹 Portuguese</option>
                      <option value="Dutch">🇳🇱 Dutch</option>
                      <option value="German">🇩🇪 German</option>
                      <option value="Italian">🇮🇹 Italian</option>
                      <option value="Russian">🇷🇺 Russian</option>
                      <option value="Polish">🇵🇱 Polish</option>
                      <option value="Swedish">🇸🇪 Swedish</option>
                      <option value="Norwegian">🇳🇴 Norwegian</option>
                      <option value="Danish">🇩🇰 Danish</option>
                      <option value="Greek">🇬🇷 Greek</option>
                      <option value="Romanian">🇷🇴 Romanian</option>
                      <option value="Ukrainian">🇺🇦 Ukrainian</option>
                      <option value="Hungarian">🇭🇺 Hungarian</option>
                      <option value="Czech">🇨🇿 Czech</option>
                    </optgroup>
                    <optgroup label="🌏 Asian Languages (lyrics in that language)">
                      <option value="Korean">🇰🇷 Korean</option>
                      <option value="Japanese">🇯🇵 Japanese</option>
                      <option value="Mandarin">🇨🇳 Mandarin Chinese</option>
                      <option value="Hindi">🇮🇳 Hindi</option>
                      <option value="Thai">🇹🇭 Thai</option>
                      <option value="Tagalog">🇵🇭 Tagalog (Filipino)</option>
                      <option value="Indonesian">🇮🇩 Indonesian</option>
                      <option value="Vietnamese">🇻🇳 Vietnamese</option>
                      <option value="Arabic">🇦🇪 Arabic</option>
                      <option value="Turkish">🇹🇷 Turkish</option>
                    </optgroup>
                    <optgroup label="🌍 African & Caribbean Languages (lyrics in that language)">
                      <option value="Swahili">🇰🇪 Swahili</option>
                      <option value="Yoruba">🇳🇬 Yoruba</option>
                      <option value="Amharic">🇪🇹 Amharic</option>
                      <option value="Zulu">🇿🇦 Zulu</option>
                      <option value="Haitian Creole">🇭🇹 Haitian Creole</option>
                    </optgroup>
                    <optgroup label="🌎 Americas Languages (lyrics in that language)">
                      <option value="Brazilian Portuguese">🇧🇷 Brazilian Portuguese</option>
                    </optgroup>
                  </select>
                  <p style={{ fontSize: 11, color: '#cccccc', marginTop: 5 }}>Leave on Auto to let Zeus match the accent to your genre</p>
                </div>}

                <div>
                  <p style={{ fontSize: 11, fontWeight: 600, color: '#cccccc', letterSpacing: '0.6px', textTransform: 'uppercase', marginBottom: 8 }}>{t('songs.modelLabel')}</p>
                  <select
                    value={modelVersion}
                    onChange={(e) => setModelVersion(e.target.value)}
                    style={{ width: '100%', background: 'rgba(255,255,255,0.04)', border: '1px solid rgba(255,255,255,0.1)', borderRadius: 6, padding: '6px 10px', color: '#c4b5fd', fontSize: 13, outline: 'none' }}
                  >
                    {['V4.5', 'V4.5 Plus', 'V5', 'V5.5'].map((v) => (
                      <option key={v} value={v}>{v}</option>
                    ))}
                  </select>
                </div>

                <div style={{ gridColumn: '1 / -1' }}>
                  <p style={{ fontSize: 11, fontWeight: 600, color: '#cccccc', letterSpacing: '0.6px', textTransform: 'uppercase', marginBottom: 6 }}>{t('songs.negativeTagsLabel')}</p>
                  <input
                    type="text"
                    maxLength={500}
                    value={negativeTags}
                    onChange={(e) => setNegativeTags(e.target.value)}
                    placeholder={t('songs.negativeTagsPlaceholder')}
                    style={{ width: '100%', background: 'rgba(255,255,255,0.04)', border: '1px solid rgba(255,255,255,0.12)', borderRadius: 6, padding: '7px 10px', color: '#c4b5fd', fontSize: 12, outline: 'none', boxSizing: 'border-box' }}
                  />
                  {negativeTags.length > 400 && <span style={{ fontSize: 10, color: '#f59e0b', float: 'right', marginTop: 3 }}>{500 - negativeTags.length} chars left</span>}
                </div>

                {/* Genre Blend */}
                <div style={{ gridColumn: '1 / -1', borderTop: '1px solid rgba(255,255,255,0.05)', paddingTop: 16 }}>
                  <label style={{ display: 'flex', alignItems: 'center', gap: 10, cursor: 'pointer', marginBottom: genreBlend ? 14 : 0 }}>
                    <div
                      onClick={() => { setGenreBlend(v => !v); if (genreBlend) setGenreB(''); }}
                      style={{ width: 36, height: 20, borderRadius: 10, background: genreBlend ? '#7c3aed' : 'rgba(255,255,255,0.08)', position: 'relative', flexShrink: 0, transition: 'background 0.2s', cursor: 'pointer' }}
                    >
                      <div style={{ position: 'absolute', top: 3, left: genreBlend ? 19 : 3, width: 14, height: 14, borderRadius: '50%', background: '#fff', transition: 'left 0.2s' }} />
                    </div>
                    <span style={{ fontSize: 12, color: genreBlend ? '#c4b5fd' : '#cccccc', fontWeight: 500 }}>Blend Genres</span>
                    {genreBlend && genreB && selGenres.size > 0 && (
                      <span style={{
                        marginLeft: 'auto', padding: '3px 10px', borderRadius: 20,
                        background: 'linear-gradient(90deg, #00f0ff22, #f472b622)',
                        border: '1px solid #00f0ff44',
                        fontSize: 11, fontWeight: 700,
                        background: 'linear-gradient(90deg, rgba(0,240,255,0.15), rgba(244,114,182,0.15))',
                        color: '#e0f7ff',
                      }}>
                        {gLabel([...selGenres][0])} × {gLabel(genreB)}
                      </span>
                    )}
                  </label>

                  {genreBlend && (
                    <div style={{ paddingLeft: 46 }}>
                      <p style={{ fontSize: 11, fontWeight: 600, color: '#cccccc', letterSpacing: '0.6px', textTransform: 'uppercase', marginBottom: 6 }}>Genre B</p>
                      <select
                        value={genreB}
                        onChange={e => setGenreB(e.target.value)}
                        style={{ width: '100%', background: 'rgba(255,255,255,0.04)', border: '1px solid rgba(255,255,255,0.1)', borderRadius: 6, padding: '6px 10px', color: genreB ? '#00f0ff' : '#cccccc', fontSize: 13, outline: 'none', marginBottom: genreB ? 14 : 0 }}
                      >
                        <option value="">Pick a second genre…</option>
                        {GENRES.filter(g => !selGenres.has(g)).map(g => (
                          <option key={g} value={g}>{gLabel(g)}</option>
                        ))}
                      </select>

                      {genreB && (
                        <>
                          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 6 }}>
                            <span style={{ fontSize: 12, color: '#00f0ff', fontWeight: 600 }}>{selGenres.size > 0 ? gLabel([...selGenres][0]) : 'Genre A'}</span>
                            <span style={{ fontSize: 11, color: '#cccccc' }}>{100 - blendRatio}% / {blendRatio}%</span>
                            <span style={{ fontSize: 12, color: '#f472b6', fontWeight: 600 }}>{gLabel(genreB)}</span>
                          </div>
                          <input
                            type="range" min={0} max={100} value={blendRatio}
                            onChange={e => setBlendRatio(Number(e.target.value))}
                            style={{ width: '100%', cursor: 'pointer', accentColor: '#f472b6' }}
                          />
                        </>
                      )}
                    </div>
                  )}
                </div>

                <div style={{ gridColumn: '1 / -1' }}>
                  <p style={{ fontSize: 11, fontWeight: 600, color: '#cccccc', letterSpacing: '0.6px', textTransform: 'uppercase', marginBottom: 8 }}>{t('songs.tempoLabel')}</p>
                  <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap', alignItems: 'center' }}>
                    {[['', t('songs.tempoDefault')], ['slow', t('songs.tempoSlow')], ['medium', t('songs.tempoMedium')], ['fast', t('songs.tempoFast')], ['custom', t('songs.tempoCustom')]].map(([val, label]) => (
                      <button
                        key={val}
                        onClick={() => setTempo(val)}
                        style={{
                          padding: '5px 12px', borderRadius: 6,
                          border: `1px solid ${tempo === val ? '#a78bfa' : 'rgba(255,255,255,0.08)'}`,
                          background: tempo === val ? 'rgba(167,139,250,0.15)' : 'transparent',
                          color: tempo === val ? '#c4b5fd' : '#cccccc',
                          fontSize: 12, cursor: 'pointer', transition: 'all 0.15s',
                        }}
                      >{label}</button>
                    ))}
                    {tempo === 'custom' && (
                      <input
                        type="number" min={40} max={300} value={tempoBpm}
                        onChange={(e) => setTempoBpm(Number(e.target.value))}
                        style={{ width: 72, background: 'rgba(255,255,255,0.04)', border: '1px solid rgba(255,255,255,0.1)', borderRadius: 6, padding: '5px 8px', color: '#c4b5fd', fontSize: 12, outline: 'none' }}
                      />
                    )}
                  </div>
                </div>

                {selGenres.has('healingfrequency') && (
                  <div style={{ gridColumn: '1 / -1', borderTop: '1px solid rgba(255,255,255,0.05)', paddingTop: 16 }}>
                    <p style={{ fontSize: 11, fontWeight: 600, color: '#e2e8f0', letterSpacing: '0.6px', textTransform: 'uppercase', margin: '0 0 10px' }}>Healing Frequency</p>
                    <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
                      {[
                        ['432', '432 Hz — Natural Tuning'],
                        ['528', '528 Hz — Miracle Tone'],
                        ['396', '396 Hz — Release Fear'],
                        ['639', '639 Hz — Connection'],
                        ['741', '741 Hz — Expression'],
                        ['852', '852 Hz — Intuition'],
                        ['963', '963 Hz — Spiritual'],
                      ].map(([hz, label]) => (
                        <button
                          key={hz}
                          onClick={() => setHealingFrequency(hz)}
                          style={{
                            padding: '5px 10px', borderRadius: 6, fontSize: 11, cursor: 'pointer', transition: 'all 0.15s',
                            border: `1px solid ${healingFrequency === hz ? '#e2e8f0' : 'rgba(255,255,255,0.08)'}`,
                            background: healingFrequency === hz ? 'rgba(226,232,240,0.12)' : 'transparent',
                            color: healingFrequency === hz ? '#e2e8f0' : '#cccccc',
                          }}
                        >{label}</button>
                      ))}
                    </div>
                  </div>
                )}

                {!['meditation','healingfrequency'].some(g => selGenres.has(g)) && (
                <div style={{ gridColumn: '1 / -1', borderTop: '1px solid rgba(255,255,255,0.05)', paddingTop: 16 }}>
                  <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
                    {[
                      { value: 'full',         label: t('songs.vocalsOn') },
                      { value: 'instrumental', label: t('songs.vocalsOff') },
                      { value: 'intermittent', label: t('songs.vocalsIntermittent') },
                    ].map(({ value, label }) => (
                      <button
                        key={value}
                        onClick={() => setVocalMode(value)}
                        style={{
                          padding: '6px 14px',
                          borderRadius: 20,
                          border: `1px solid ${vocalMode === value ? '#a78bfa' : 'rgba(255,255,255,0.08)'}`,
                          background: vocalMode === value ? 'rgba(167,139,250,0.15)' : 'transparent',
                          color: vocalMode === value ? '#c4b5fd' : '#cccccc',
                          fontSize: 12,
                          fontWeight: 500,
                          cursor: 'pointer',
                        }}
                      >{label}</button>
                    ))}
                  </div>
                </div>
                )}

                {!isFreeTier && (
                  <div style={{ gridColumn: '1 / -1', borderTop: '1px solid rgba(255,255,255,0.05)', paddingTop: 16 }}>
                    <label style={{ display: 'flex', alignItems: 'center', gap: 10, cursor: 'pointer' }}>
                      <div
                        onClick={() => setAnimateCoverPref((v) => !v)}
                        style={{ width: 36, height: 20, borderRadius: 10, background: animateCoverPref ? '#7c3aed' : 'rgba(255,255,255,0.08)', position: 'relative', flexShrink: 0, transition: 'background 0.2s', cursor: 'pointer' }}
                      >
                        <div style={{ position: 'absolute', top: 3, left: animateCoverPref ? 19 : 3, width: 14, height: 14, borderRadius: '50%', background: '#fff', transition: 'left 0.2s' }} />
                      </div>
                      <span style={{ fontSize: 12, color: animateCoverPref ? '#c4b5fd' : '#cccccc', fontWeight: 500 }}>
                        {animateCoverPref ? t('songs.animatedCoverOn') : t('songs.animatedCoverOff')}
                      </span>
                    </label>
                    {animateCoverPref && !isAdmin && credits.premium_credits === 0 && (
                      <p style={{ fontSize: 11, color: '#f87171', margin: '6px 0 0 46px' }}>
                        No premium credits left this month.{!isIOSWebView && <> <button onClick={() => handleAnimationTopup('animation_pack_5')} disabled={topupLoading !== null} style={{ background: 'none', border: 'none', color: '#f87171', textDecoration: 'underline', cursor: 'pointer', padding: 0, fontSize: 11 }}>Buy more</button> or <Link to="/billing" style={{ color: '#f87171' }}>upgrade</Link>.</>}
                      </p>
                    )}
                  </div>
                )}

                {/* PIN modal for explicit content */}
                {pinModalOpen && (
                  <div
                    style={{ position: 'fixed', inset: 0, zIndex: 9999, background: 'rgba(0,0,0,0.75)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}
                    onClick={() => { setPinModalOpen(false); setPinError(''); }}
                  >
                    <div
                      style={{ background: '#0f0f1e', border: '1px solid rgba(0,240,255,0.25)', borderRadius: 14, padding: '28px 24px', width: 280, textAlign: 'center' }}
                      onClick={(e) => e.stopPropagation()}
                    >
                      <p style={{ margin: '0 0 6px', fontWeight: 700, color: '#e2e8f0', fontSize: 15 }}>Enter PIN to enable explicit content</p>
                      <p style={{ margin: '0 0 16px', color: '#cccccc', fontSize: 12 }}>Default PIN is 1234. Change in settings.</p>
                      <input
                        type="password"
                        inputMode="numeric"
                        maxLength={4}
                        value={pinInput}
                        onChange={(e) => { setPinInput(e.target.value.replace(/\D/g, '')); setPinError(''); }}
                        onKeyDown={(e) => e.key === 'Enter' && handlePinSubmit()}
                        autoFocus
                        placeholder="••••"
                        style={{ width: '100%', padding: '10px 14px', borderRadius: 8, border: '1px solid rgba(255,255,255,0.15)', background: 'rgba(255,255,255,0.05)', color: '#fff', fontSize: 22, textAlign: 'center', letterSpacing: 8, outline: 'none', boxSizing: 'border-box' }}
                      />
                      {pinError && <p style={{ color: '#f87171', fontSize: 12, margin: '8px 0 0' }}>{pinError}</p>}
                      <div style={{ display: 'flex', gap: 10, marginTop: 16 }}>
                        <button onClick={() => { setPinModalOpen(false); setPinError(''); setPinInput(''); }} style={{ flex: 1, padding: 10, borderRadius: 8, border: '1px solid rgba(255,255,255,0.15)', background: 'transparent', color: '#cccccc', cursor: 'pointer', fontSize: 14 }}>Cancel</button>
                        <button onClick={handlePinSubmit} style={{ flex: 1, padding: 10, borderRadius: 8, border: 'none', background: '#7c3aed', color: '#fff', cursor: 'pointer', fontWeight: 700, fontSize: 14 }}>Unlock</button>
                      </div>
                    </div>
                  </div>
                )}

                {/* Explicit content — hidden in kids mode */}
                {canShowExplicit && !isKidsMode && (
                  <div style={{ gridColumn: '1 / -1', borderTop: '1px solid rgba(255,255,255,0.05)', paddingTop: 16 }}>
                    <label style={{ display: 'flex', alignItems: 'center', gap: 10, cursor: 'pointer' }}>
                      <div
                        onClick={handleExplicitToggle}
                        style={{ width: 36, height: 20, borderRadius: 10, background: explicit ? '#7c3aed' : 'rgba(255,255,255,0.08)', position: 'relative', flexShrink: 0, transition: 'background 0.2s', cursor: 'pointer' }}
                      >
                        <div style={{ position: 'absolute', top: 3, left: explicit ? 19 : 3, width: 14, height: 14, borderRadius: '50%', background: '#fff', transition: 'left 0.2s' }} />
                      </div>
                      <span style={{ fontSize: 12, color: explicit ? '#c4b5fd' : '#cccccc', fontWeight: 500 }}>{t('songs.explicitLabel')}</span>
                    </label>
                    {explicit && (
                      <p style={{ fontSize: 11, color: '#f87171', marginTop: 8, lineHeight: 1.5 }}>
                        {t('songs.explicitWarning')}
                      </p>
                    )}
                  </div>
                )}
              </div>
            )}

            {/* ── Zeus Kids Beats ─────────────────────────────────── */}
            {user?.account_type !== 'school' && <button
              onClick={() => setShowKidsPinGate(true)}
              style={{
                display: 'flex', alignItems: 'center', gap: 8,
                padding: '8px 16px', borderRadius: 20, cursor: 'pointer',
                background: 'rgba(251,209,85,0.10)',
                border: '1px solid rgba(251,209,85,0.5)',
                color: '#fbbf24', fontSize: 13, fontWeight: 700,
                transition: 'background 0.2s', marginBottom: 10, width: '100%',
              }}
            >
              ⚡ Zeus Kids Beats
            </button>}

            {/* ── Kids Story Mode ─────────────────────────────────── */}
            <button
              onClick={() => { setIsKidsMode(v => !v); setIsRoastMode(false); setKidsAccent(''); setKidsNarratorVoice('british'); setKidsChildVoice('younggirl'); setKidsCharacterVoice(''); setKidsSubMode('song'); setStoryLanguage('english'); }}
              style={{
                width: '100%', display: 'flex', alignItems: 'center', gap: 10,
                background: isKidsMode ? 'rgba(251,191,36,0.10)' : 'rgba(251,191,36,0.04)',
                border: `1px solid ${isKidsMode ? 'rgba(251,191,36,0.70)' : 'rgba(251,191,36,0.25)'}`,
                borderRadius: 8, padding: '9px 14px', cursor: 'pointer', marginBottom: 14,
              }}
            >
              <span style={{ fontSize: 10, fontWeight: 700, color: '#fbbf24', letterSpacing: '0.14em', textTransform: 'uppercase' }}>🧒 Kids Story Mode</span>
              <span style={{ marginLeft: 'auto', color: '#fbbf24', fontSize: 12, fontWeight: 600 }}>{isKidsMode ? '▲ On' : '▼ Off'}</span>
            </button>

            {isKidsMode && (
              <div style={{ background: 'rgba(251,191,36,0.05)', border: '1px solid rgba(251,191,36,0.30)', borderRadius: 10, padding: '18px 18px', marginBottom: 18 }}>

                {/* ── Sub-mode toggle ── */}
                <div style={{ display: 'flex', gap: 8, marginBottom: 18 }}>
                  {[
                    ['song',  '🎵', 'Song Mode',  'Suno sings a fun children\'s song'],
                    ['story', '📖', 'Story Mode', 'Story narrated with gentle music'],
                  ].map(([val, emoji, label, desc]) => (
                    <button
                      key={val}
                      onClick={() => setKidsSubMode(val)}
                      style={{
                        flex: 1, display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 4,
                        padding: '12px 8px', borderRadius: 12, cursor: 'pointer', transition: 'all 0.15s',
                        border: `2px solid ${kidsSubMode === val ? '#fbbf24' : 'rgba(251,191,36,0.25)'}`,
                        background: kidsSubMode === val ? 'rgba(251,191,36,0.18)' : 'rgba(251,191,36,0.04)',
                        boxShadow: kidsSubMode === val ? '0 0 14px rgba(251,191,36,0.30)' : 'none',
                      }}
                    >
                      <span style={{ fontSize: 22 }}>{emoji}</span>
                      <span style={{ fontSize: 13, fontWeight: 800, color: kidsSubMode === val ? '#fbbf24' : 'rgba(251,191,36,0.7)' }}>{label}</span>
                      <span style={{ fontSize: 10, color: 'rgba(251,191,36,0.5)', textAlign: 'center', lineHeight: 1.3 }}>{desc}</span>
                    </button>
                  ))}
                </div>

                {/* ── Shared fields: title, character, what happens ── */}
                <p style={{ fontSize: 11, fontWeight: 700, color: '#fbbf24', letterSpacing: '0.5px', textTransform: 'uppercase', marginBottom: 6 }}>📖 {kidsSubMode === 'story' ? 'Story Title' : 'Song Title'}</p>
                <input
                  type="text"
                  value={songTitle}
                  onChange={(e) => setSongTitle(e.target.value)}
                  placeholder="e.g. The Adventures of Benny the Bear"
                  maxLength={80}
                  style={{
                    width: '100%', boxSizing: 'border-box',
                    background: 'rgba(251,191,36,0.06)', border: '1px solid rgba(251,191,36,0.30)',
                    borderRadius: 10, padding: '10px 14px', color: '#f0eeff',
                    fontSize: 14, fontFamily: 'inherit', outline: 'none', marginBottom: 14,
                  }}
                />

                <p style={{ fontSize: 11, fontWeight: 700, color: '#fbbf24', letterSpacing: '0.5px', textTransform: 'uppercase', marginBottom: 6 }}>🦁 Main Character</p>
                <input
                  type="text"
                  value={mainCharacter}
                  onChange={(e) => setMainCharacter(e.target.value)}
                  placeholder="e.g. a friendly dragon, a little robot, Rosie the rabbit"
                  maxLength={80}
                  style={{
                    width: '100%', boxSizing: 'border-box',
                    background: 'rgba(251,191,36,0.06)', border: '1px solid rgba(251,191,36,0.30)',
                    borderRadius: 10, padding: '10px 14px', color: '#f0eeff',
                    fontSize: 14, fontFamily: 'inherit', outline: 'none', marginBottom: 14,
                  }}
                />

                <p style={{ fontSize: 11, fontWeight: 700, color: '#fbbf24', letterSpacing: '0.5px', textTransform: 'uppercase', marginBottom: 6 }}>✨ What Happens?</p>
                <textarea
                  value={storyEvent}
                  onChange={(e) => setStoryEvent(e.target.value)}
                  placeholder="e.g. goes on a big adventure to find the magic rainbow cake"
                  rows={2}
                  maxLength={200}
                  style={{
                    width: '100%', boxSizing: 'border-box',
                    background: 'rgba(251,191,36,0.06)', border: '1px solid rgba(251,191,36,0.30)',
                    borderRadius: 10, padding: '10px 14px', color: '#f0eeff',
                    fontSize: 14, fontFamily: 'inherit', outline: 'none', resize: 'vertical', marginBottom: 16,
                  }}
                />

                {/* ── Age Range (both modes) ── */}
                <p style={{ fontSize: 11, fontWeight: 700, color: '#fbbf24', letterSpacing: '0.5px', textTransform: 'uppercase', marginBottom: 8 }}>👶 Age Range</p>
                <div style={{ display: 'flex', gap: 8, marginBottom: 16, flexWrap: 'wrap' }}>
                  {[
                    ['tiny_tots',   '🍼', 'Tiny Tots',   '2–4'],
                    ['little_ones', '🌟', 'Little Ones', '4–6'],
                    ['big_kids',    '📚', 'Big Kids',    '7–10'],
                  ].map(([val, emoji, label, ages]) => (
                    <button key={val} onClick={() => setKidsAgeRange(val)} style={{
                      flex: 1, minWidth: 80, display: 'flex', flexDirection: 'column', alignItems: 'center',
                      padding: '10px 8px', borderRadius: 12, cursor: 'pointer', transition: 'all 0.15s',
                      border: `1px solid ${kidsAgeRange === val ? '#fbbf24' : 'rgba(251,191,36,0.25)'}`,
                      background: kidsAgeRange === val ? 'rgba(251,191,36,0.18)' : 'rgba(251,191,36,0.04)',
                      boxShadow: kidsAgeRange === val ? '0 0 10px rgba(251,191,36,0.25)' : 'none',
                    }}>
                      <span style={{ fontSize: 24, lineHeight: 1, marginBottom: 3 }}>{emoji}</span>
                      <span style={{ fontSize: 11, fontWeight: 700, color: kidsAgeRange === val ? '#fbbf24' : 'rgba(251,191,36,0.7)' }}>{label}</span>
                      <span style={{ fontSize: 10, color: 'rgba(251,191,36,0.5)' }}>ages {ages}</span>
                    </button>
                  ))}
                </div>

                {/* ── SONG MODE fields ── */}
                {kidsSubMode === 'song' && (<>
                  <p style={{ fontSize: 11, fontWeight: 700, color: '#fbbf24', letterSpacing: '0.5px', textTransform: 'uppercase', marginBottom: 8 }}>🎵 Music Style</p>
                  <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(90px, 1fr))', gap: 8, marginBottom: 16 }}>
                    {[
                      ['nursery',  '🎠', 'Nursery Rhyme'],
                      ['funpop',   '🎉', 'Fun Pop'],
                      ['acoustic', '🎸', 'Gentle Acoustic'],
                      ['piano',    '🎹', 'Happy Piano'],
                      ['reggae',   '🏝️', 'Reggae Fun'],
                    ].map(([val, emoji, label]) => (
                      <button key={val} onClick={() => setKidsMusicStyle(val)} style={{
                        display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center',
                        padding: '10px 6px 8px', borderRadius: 12, cursor: 'pointer', transition: 'all 0.15s',
                        border: `1px solid ${kidsMusicStyle === val ? '#fbbf24' : 'rgba(251,191,36,0.20)'}`,
                        background: kidsMusicStyle === val ? 'rgba(251,191,36,0.18)' : 'rgba(251,191,36,0.04)',
                        boxShadow: kidsMusicStyle === val ? '0 0 10px rgba(251,191,36,0.25)' : 'none',
                        minHeight: 66,
                      }}>
                        <span style={{ fontSize: 24, lineHeight: 1, marginBottom: 4 }}>{emoji}</span>
                        <span style={{ fontSize: 10, fontWeight: kidsMusicStyle === val ? 700 : 500, textAlign: 'center', lineHeight: 1.2, color: kidsMusicStyle === val ? '#fbbf24' : 'rgba(251,191,36,0.65)' }}>{label}</span>
                      </button>
                    ))}
                  </div>

                  <p style={{ fontSize: 11, fontWeight: 700, color: '#fbbf24', letterSpacing: '0.5px', textTransform: 'uppercase', marginBottom: 6 }}>🎤 Singing Accent</p>
                  <select
                    value={kidsAccent}
                    onChange={(e) => setKidsAccent(e.target.value)}
                    style={{ width: '100%', background: 'rgba(251,191,36,0.06)', border: '1px solid rgba(251,191,36,0.35)', borderRadius: 8, padding: '8px 12px', color: kidsAccent ? '#fbbf24' : 'rgba(251,191,36,0.5)', fontSize: 13, outline: 'none', marginBottom: 4 }}
                  >
                    <option value="">🌟 Default</option>
                    {['British','Irish','Scottish','Australian','Caribbean','American Soul','Jamaican','French','Spanish'].map((a) => (
                      <option key={a} value={a}>{a}</option>
                    ))}
                  </select>
                </>)}

                {/* ── STORY MODE fields ── */}
                {kidsSubMode === 'story' && (<>
                  {/* ── 📖 Narrator Voice ── */}
                  <p style={{ fontSize: 11, fontWeight: 700, color: '#fbbf24', letterSpacing: '0.5px', textTransform: 'uppercase', marginBottom: 8 }}>📖 Narrator Voice</p>
                  <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 8, marginBottom: 16 }}>
                    {[
                      ['british',    '🇬🇧', 'British',     'Default'],
                      ['australian', '🦘',  'Australian',  'Warm'],
                      ['newzealand', '🇳🇿', 'New Zealand', 'Clear'],
                      ['indian',     '🇮🇳', 'Indian',      'Rich'],
                      ['scouse',     '🎸',  'Scouse',      'Liverpool'],
                      ['irish',      '🍀',  'Irish',       'Musical'],
                      ['scottish',   '🏴󠁧󠁢󠁳󠁣󠁴󠁿', 'Scottish',   'Lively'],
                    ].map(([val, emoji, name, desc]) => (
                      <div key={val} style={{ position: 'relative' }}>
                        <button
                          onClick={() => setKidsNarratorVoice(val)}
                          style={{
                            display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 3,
                            padding: '10px 6px 8px', borderRadius: 12, cursor: 'pointer', transition: 'all 0.15s',
                            border: `1px solid ${kidsNarratorVoice === val ? '#fbbf24' : 'rgba(251,191,36,0.25)'}`,
                            background: kidsNarratorVoice === val ? 'rgba(251,191,36,0.18)' : 'rgba(251,191,36,0.04)',
                            boxShadow: kidsNarratorVoice === val ? '0 0 10px rgba(251,191,36,0.25)' : 'none',
                            width: '100%',
                          }}
                        >
                          <span style={{ fontSize: 20 }}>{emoji}</span>
                          <span style={{ fontSize: 11, fontWeight: 700, color: kidsNarratorVoice === val ? '#fbbf24' : 'rgba(251,191,36,0.8)' }}>{name}</span>
                          <span style={{ fontSize: 9, color: 'rgba(251,191,36,0.5)' }}>{desc}</span>
                        </button>
                        <button
                          onClick={(e) => { e.stopPropagation(); handleVoicePreview(val); }}
                          title="Preview voice"
                          style={{
                            position: 'absolute', top: 4, right: 4, width: 18, height: 18,
                            borderRadius: '50%', border: '1px solid rgba(251,191,36,0.5)',
                            background: previewingVoice === val ? 'rgba(251,191,36,0.7)' : 'rgba(0,0,0,0.45)',
                            color: '#fbbf24', fontSize: 7, cursor: 'pointer',
                            display: 'flex', alignItems: 'center', justifyContent: 'center',
                            backdropFilter: 'blur(4px)', transition: 'all 0.15s', padding: 0,
                          }}
                        >{previewingVoice === val ? '⏸' : '▶'}</button>
                      </div>
                    ))}
                  </div>

                  {/* ── 🧒 Child Hero Voice ── */}
                  <p style={{ fontSize: 11, fontWeight: 700, color: '#34d399', letterSpacing: '0.5px', textTransform: 'uppercase', marginBottom: 8 }}>🧒 Main Character Voice</p>
                  <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 8, marginBottom: 16 }}>
                    {[
                      ['younggirl',  '👧',  'Young Girl',  'Youthful'],
                      ['youngboy',   '👦',  'Young Boy',   'Boyish'],
                      ['australian', '🦘',  'Australian',  'Warm'],
                      ['newzealand', '🇳🇿', 'New Zealand', 'Bright'],
                      ['irish',      '🍀',  'Irish',       'Musical'],
                      ['british',    '🇬🇧', 'British',     'Clear'],
                      ['indian',     '🇮🇳', 'Indian',      'Rich'],
                      ['scouse',     '🎸',  'Scouse',      'Cheeky'],
                      ['scottish',   '🏴󠁧󠁢󠁳󠁣󠁴󠁿', 'Scottish',   'Lively'],
                    ].map(([val, emoji, name, desc]) => (
                      <div key={val} style={{ position: 'relative' }}>
                        <button
                          onClick={() => setKidsChildVoice(val)}
                          style={{
                            display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 3,
                            padding: '10px 6px 8px', borderRadius: 12, cursor: 'pointer', transition: 'all 0.15s',
                            border: `1px solid ${kidsChildVoice === val ? '#34d399' : 'rgba(52,211,153,0.25)'}`,
                            background: kidsChildVoice === val ? 'rgba(52,211,153,0.15)' : 'rgba(52,211,153,0.04)',
                            boxShadow: kidsChildVoice === val ? '0 0 10px rgba(52,211,153,0.25)' : 'none',
                            width: '100%',
                          }}
                        >
                          <span style={{ fontSize: 20 }}>{emoji}</span>
                          <span style={{ fontSize: 11, fontWeight: 700, color: kidsChildVoice === val ? '#34d399' : 'rgba(52,211,153,0.8)' }}>{name}</span>
                          <span style={{ fontSize: 9, color: 'rgba(52,211,153,0.5)' }}>{desc}</span>
                        </button>
                        <button
                          onClick={(e) => { e.stopPropagation(); handleVoicePreview(val); }}
                          title="Preview voice"
                          style={{
                            position: 'absolute', top: 4, right: 4, width: 18, height: 18,
                            borderRadius: '50%', border: '1px solid rgba(52,211,153,0.5)',
                            background: previewingVoice === val ? 'rgba(52,211,153,0.7)' : 'rgba(0,0,0,0.45)',
                            color: '#34d399', fontSize: 7, cursor: 'pointer',
                            display: 'flex', alignItems: 'center', justifyContent: 'center',
                            backdropFilter: 'blur(4px)', transition: 'all 0.15s', padding: 0,
                          }}
                        >{previewingVoice === val ? '⏸' : '▶'}</button>
                      </div>
                    ))}
                  </div>

                  {/* ── 🎭 Character Voice ── */}
                  <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 8 }}>
                    <p style={{ fontSize: 11, fontWeight: 700, color: '#f472b6', letterSpacing: '0.5px', textTransform: 'uppercase', margin: 0 }}>🎭 Character Voice</p>
                    <span style={{ fontSize: 10, color: 'rgba(244,114,182,0.55)', fontStyle: 'italic' }}>optional — gives the main character their own voice</span>
                    {kidsCharacterVoice && (
                      <button
                        onClick={() => setKidsCharacterVoice('')}
                        style={{ marginLeft: 'auto', background: 'none', border: '1px solid rgba(244,114,182,0.3)', borderRadius: 6, color: 'rgba(244,114,182,0.7)', fontSize: 10, cursor: 'pointer', padding: '2px 8px' }}
                      >✕ None</button>
                    )}
                  </div>
                  {kidsCharacterVoice && (
                    <div style={{ marginBottom: 8, padding: '6px 10px', borderRadius: 8, background: 'rgba(244,114,182,0.08)', border: '1px solid rgba(244,114,182,0.2)', fontSize: 10, color: '#f472b6' }}>
                      ✨ 3-voice mode — narrator, child hero, and {kidsCharacterVoice} each get their own distinct voice
                    </div>
                  )}
                  <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 8, marginBottom: 16 }}>
                    {[
                      ['dragon',  '🐉',   'Dragon',   'Fierce'],
                      ['villain', '😈',   'Villain',  'Menacing'],
                      ['fairy',   '🧚',   'Fairy',    'Magical'],
                      ['cranky',  '👴',   'Cranky',   'Old man'],
                      ['pirate',  '🏴‍☠️',  'Pirate',   'Swashbuckling'],
                      ['wizard',  '🧙',   'Wizard',   'Wise & old'],
                      ['raspy',   '👹',   'Raspy',    'Scary'],
                      ['gnarly',  '🤙',   'Gnarly',   'Wild'],
                      ['cockney', '🎩',   'Cockney',  'London'],
                    ].map(([val, emoji, name, desc]) => (
                      <div key={val} style={{ position: 'relative' }}>
                        <button
                          onClick={() => setKidsCharacterVoice(v => v === val ? '' : val)}
                          style={{
                            display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 3,
                            padding: '10px 6px 8px', borderRadius: 12, cursor: 'pointer', transition: 'all 0.15s',
                            border: `1px solid ${kidsCharacterVoice === val ? '#f472b6' : 'rgba(244,114,182,0.25)'}`,
                            background: kidsCharacterVoice === val ? 'rgba(244,114,182,0.18)' : 'rgba(244,114,182,0.04)',
                            boxShadow: kidsCharacterVoice === val ? '0 0 12px rgba(244,114,182,0.35)' : 'none',
                            width: '100%',
                          }}
                        >
                          <span style={{ fontSize: 20 }}>{emoji}</span>
                          <span style={{ fontSize: 11, fontWeight: 700, color: kidsCharacterVoice === val ? '#f472b6' : 'rgba(244,114,182,0.8)' }}>{name}</span>
                          <span style={{ fontSize: 9, color: 'rgba(244,114,182,0.5)' }}>{desc}</span>
                        </button>
                        <button
                          onClick={(e) => { e.stopPropagation(); handleVoicePreview(val); }}
                          title="Preview voice"
                          style={{
                            position: 'absolute', top: 4, right: 4, width: 18, height: 18,
                            borderRadius: '50%', border: '1px solid rgba(244,114,182,0.5)',
                            background: previewingVoice === val ? 'rgba(244,114,182,0.7)' : 'rgba(0,0,0,0.45)',
                            color: '#f472b6', fontSize: 7, cursor: 'pointer',
                            display: 'flex', alignItems: 'center', justifyContent: 'center',
                            backdropFilter: 'blur(4px)', transition: 'all 0.15s', padding: 0,
                          }}
                        >{previewingVoice === val ? '⏸' : '▶'}</button>
                      </div>
                    ))}
                  </div>

                  <p style={{ fontSize: 11, fontWeight: 700, color: '#fbbf24', letterSpacing: '0.5px', textTransform: 'uppercase', marginBottom: 8 }}>🌍 Story Language</p>
                  <div style={{ display: 'grid', gridTemplateColumns: 'repeat(5, 1fr)', gap: 6, marginBottom: 16 }}>
                    {[
                      ['english',  '🇬🇧', 'English'],
                      ['french',   '🇫🇷', 'French'],
                      ['spanish',  '🇪🇸', 'Spanish'],
                      ['german',   '🇩🇪', 'German'],
                      ['italian',  '🇮🇹', 'Italian'],
                    ].map(([val, flag, label]) => (
                      <button
                        key={val}
                        onClick={() => setStoryLanguage(val)}
                        style={{
                          display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 3,
                          padding: '8px 4px 6px', borderRadius: 10, cursor: 'pointer', transition: 'all 0.15s',
                          border: `1px solid ${storyLanguage === val ? '#fbbf24' : 'rgba(251,191,36,0.25)'}`,
                          background: storyLanguage === val ? 'rgba(251,191,36,0.18)' : 'rgba(251,191,36,0.04)',
                          boxShadow: storyLanguage === val ? '0 0 10px rgba(251,191,36,0.25)' : 'none',
                        }}
                      >
                        <span style={{ fontSize: 18 }}>{flag}</span>
                        <span style={{ fontSize: 9, fontWeight: storyLanguage === val ? 700 : 500, color: storyLanguage === val ? '#fbbf24' : 'rgba(251,191,36,0.7)', textAlign: 'center' }}>{label}</span>
                      </button>
                    ))}
                  </div>

                  <p style={{ fontSize: 11, fontWeight: 700, color: '#fbbf24', letterSpacing: '0.5px', textTransform: 'uppercase', marginBottom: 8 }}>🎵 Background Music</p>
                  <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(90px, 1fr))', gap: 8, marginBottom: 4 }}>
                    {[
                      ['piano',    '🎹', 'Gentle Piano'],
                      ['acoustic', '🎸', 'Soft Acoustic'],
                      ['nursery',  '🎠', 'Nursery Tune'],
                      ['funpop',   '🎵', 'Light Pop'],
                      ['reggae',   '🏝️', 'Soft Reggae'],
                    ].map(([val, emoji, label]) => (
                      <button key={val} onClick={() => setKidsMusicStyle(val)} style={{
                        display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center',
                        padding: '10px 6px 8px', borderRadius: 12, cursor: 'pointer', transition: 'all 0.15s',
                        border: `1px solid ${kidsMusicStyle === val ? '#fbbf24' : 'rgba(251,191,36,0.20)'}`,
                        background: kidsMusicStyle === val ? 'rgba(251,191,36,0.18)' : 'rgba(251,191,36,0.04)',
                        boxShadow: kidsMusicStyle === val ? '0 0 10px rgba(251,191,36,0.25)' : 'none',
                        minHeight: 66,
                      }}>
                        <span style={{ fontSize: 24, lineHeight: 1, marginBottom: 4 }}>{emoji}</span>
                        <span style={{ fontSize: 10, fontWeight: kidsMusicStyle === val ? 700 : 500, textAlign: 'center', lineHeight: 1.2, color: kidsMusicStyle === val ? '#fbbf24' : 'rgba(251,191,36,0.65)' }}>{label}</span>
                      </button>
                    ))}
                  </div>
                </>)}

              </div>
            )}

            {/* ── Roast / Funny Song Mode ─────────────────────────── */}
            <button
              onClick={() => { setIsRoastMode(v => !v); setIsKidsMode(false); setRoastName(''); setRoastDetails(''); setRoastVibe('gentle'); }}
              style={{
                width: '100%', display: 'flex', alignItems: 'center', gap: 10,
                background: isRoastMode ? 'rgba(248,113,113,0.10)' : 'rgba(248,113,113,0.04)',
                border: `1px solid ${isRoastMode ? 'rgba(248,113,113,0.70)' : 'rgba(248,113,113,0.25)'}`,
                borderRadius: 8, padding: '9px 14px', cursor: 'pointer', marginBottom: 14,
              }}
            >
              <span style={{ fontSize: 10, fontWeight: 700, color: '#f87171', letterSpacing: '0.14em', textTransform: 'uppercase' }}>🎤 Roast Mode — Funny Song</span>
              <span style={{ marginLeft: 'auto', color: '#f87171', fontSize: 12, fontWeight: 600 }}>{isRoastMode ? '▲ On' : '▼ Off'}</span>
            </button>

            {cost > 0 ? (
              <p style={{ fontSize: 13, color: creditExceeded ? '#f87171' : '#666', marginBottom: 16, fontWeight: creditExceeded ? 600 : 400 }}>
                {isAdmin ? t('songs.creditUnlimited', { cost }) : t('songs.creditInfo', { cost, balance })}
                {creditExceeded && !isIOSWebView && (
                  <> <Link to="/billing" style={{ color: '#f87171' }}>{t('songs.creditExceeded')}</Link></>
                )}
              </p>
            ) : (
              <div style={{ height: 16 }} />
            )}

            {soundPersona && (
              <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 10, padding: '7px 12px', borderRadius: 8, background: 'rgba(0,240,255,0.07)', border: '1px solid rgba(0,240,255,0.25)' }}>
                <span style={{ flex: 1, fontSize: 12, color: '#00f0ff', fontWeight: 600 }}>
                  🔒 Your Sound Active — {soundPersona.sound_persona_title}
                </span>
                <button
                  onClick={handleResetSound}
                  aria-label="Reset Your Sound"
                  style={{ background: 'none', border: 'none', color: 'rgba(0,240,255,0.6)', fontSize: 16, cursor: 'pointer', lineHeight: 1, padding: '2px 4px', flexShrink: 0 }}
                >
                  ×
                </button>
              </div>
            )}
            <button
              onClick={isOnline ? handleGenerate : () => showOfflineToast()}
              disabled={!generateEffective}
              style={{
                width: '100%',
                padding: '14px',
                borderRadius: 10,
                border: 'none',
                background: generateEffective
                  ? isKidsMode
                    ? 'linear-gradient(135deg, #f59e0b 0%, #fbbf24 100%)'
                    : 'linear-gradient(135deg, #7c3aed 0%, #a855f7 100%)'
                  : 'rgba(255,255,255,0.05)',
                color: generateEffective ? (isKidsMode ? '#1a0a00' : '#fff') : '#444',
                fontSize: isKidsMode ? 16 : 15,
                fontWeight: 700,
                cursor: generateEffective ? 'pointer' : 'default',
                transition: 'all 0.2s',
                letterSpacing: '0.2px',
              }}
            >
              {generating
                ? (isKidsMode ? '✨ Creating your story song...' : t('songs.generatingBtn'))
                : isKidsMode
                  ? `🌟 Create My Story Song! (1 credit)`
                  : cost > 0
                    ? t('songs.generateBtn', { cost })
                    : t('songs.selectStyleBtn')}
            </button>

            {error && <p style={{ color: '#f87171', fontSize: 13, marginTop: 12 }}>{error}</p>}
          </div>

          {/* ── Top-up section ─────────────────────────────────────────── */}
          <div className="topup-section" style={{
            marginBottom: 44,
            padding: '20px 24px',
            borderRadius: 14,
            border: '1px solid #00f0ff',
            background: 'rgba(0,240,255,0.03)',
          }}>
            <h3 style={{
              fontFamily: "'Orbitron', sans-serif",
              fontSize: 13,
              fontWeight: 700,
              color: '#00f0ff',
              marginBottom: 14,
              letterSpacing: '0.5px',
            }}>⚡ Buy More Songs</h3>
            <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap' }}>
              {SONG_PACKS.map(({ pack, label, price }) => (
                <button
                  key={pack}
                  className="topup-btn"
                  onClick={() => handleTopup(pack)}
                  disabled={topupLoading !== null}
                  style={{
                    padding: '11px 22px',
                    borderRadius: 10,
                    border: '1px solid rgba(0,240,255,0.5)',
                    background: 'linear-gradient(135deg, rgba(0,240,255,0.1) 0%, rgba(0,191,255,0.08) 100%)',
                    color: '#00f0ff',
                    fontSize: 13,
                    fontWeight: 700,
                    cursor: topupLoading ? 'default' : 'pointer',
                    transition: 'all 0.2s',
                    letterSpacing: '0.3px',
                  }}
                >
                  {topupLoading === pack ? t('songs.redirecting') : `${label} — ${price}`}
                </button>
              ))}
            </div>
            <p style={{ fontSize: 11, color: '#4a9fb5', marginTop: 12, marginBottom: 0 }}>
              Credits never expire · No subscription needed
            </p>
          </div>

          {isOnline && activeJob && (
            <section style={{ marginBottom: 48 }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 14, marginBottom: 20, flexWrap: 'wrap' }}>
                <h2 style={{ fontSize: '0.95rem', fontWeight: 700, color: '#e2d9f3', margin: 0 }}>{activeJob.title}</h2>
                <span style={{ background: 'rgba(167,139,250,0.1)', color: '#a78bfa', borderRadius: 20, padding: '3px 12px', fontSize: 12, fontWeight: 500 }}>
                  {t('songs.generatingStatus')}
                </span>
              </div>
              <div className="songs-grid" style={S.grid}>
                {activeJob.variants.map((v) =>
                  v.status === 'complete' || v.status === 'failed' ? (
                    v.genre_tag === 'kids_story' ? (
                      <StoryCard
                        key={v.variant_id}
                        variant={v}
                        title={activeJob.title}
                        onDelete={handleDeleteVariant}
                        deleting={deletingVariants.has(v.variant_id)}
                      />
                    ) : (
                      <SongCard
                        key={v.variant_id}
                        variant={v}
                        title={activeJob.title}
                        lyricId={activeJob.lyric_id}
                        activeWsRef={activeWsRef}
                        canYouTube={canYouTube}
                        ytConnected={youtubeConnected}
                        ytStatus={ytStatus[v.variant_id]}
                        ytUrl={ytUrls[v.variant_id]}
                        ytError={ytErrors[v.variant_id]}
                        onYouTubeClick={handleYouTubeClick}
                        canDid={canDid}
                        didSt={didStatus[v.variant_id]}
                        videoUrl={videoUrls[v.variant_id]}
                        onAvatarClick={handleAvatarClick}
                        videoCredits={credits.video_credits}
                        didPlanOk={didPlanOk}
                        isAdmin={isAdmin}
                        onDelete={handleDeleteVariant}
                        deleting={deletingVariants.has(v.variant_id)}
                        musicVideoUrl={musicVideoUrls[v.variant_id]}
                        onRemake={handleOpenRemake}
                        onTelegramClick={handleTelegramPost}
                        artistName={credits.artist_name}
                        onRegenerate={handleRegenerate}
                        isFavourite={favourites.has(v.variant_id)}
                        onToggleFavourite={handleToggleFavourite}
                        isFreeTier={isFreeTier}
                        animateCover={animateCover}
                        isPublic={publicVariants.has(v.variant_id)}
                        onShareToggle={handleShareToggle}
                        playlists={playlists}
                        onAddToPlaylist={handleAddToPlaylist}
                        premiumCredits={credits.premium_credits}
                        stemsData={stemsData[v.variant_id]}
                        onGetStems={handleGetStems}
                        onUpgrade={setUpgradeFeature}
                        onOpenCover={(variantId, title) => { setCoverModal({ variantId, sourceTitle: title }); setCoverLyrics(''); setCoverError(''); }}
                        soundPersonaVariantId={soundPersona?.sound_persona_variant_id ?? null}
                        onLockSound={handleLockSound}
                        isSaved={false}
                        isDownloading={false}
                        onSaveOffline={null}
                        onRemoveSaved={null}
                        onPlayOffline={null}
                      />
                    )
                  ) : (
                    <SkeletonCard key={v.variant_id} genre={v.genre_tag} />
                  )
                )}
              </div>
            </section>
          )}

          {filteredLibrary.length > 0 && (
            <div style={{ display: 'flex', gap: 8, marginBottom: 20, overflowX: 'auto', WebkitOverflowScrolling: 'touch', paddingBottom: 4 }}>
              {[['all', t('songs.tabs.all')], ['favourites', t('songs.tabs.favourites')], ['recent', t('songs.tabs.recent')]].map(([tab, label]) => (
                <button
                  key={tab}
                  onClick={() => setActiveTab(tab)}
                  style={{
                    padding: '6px 12px', borderRadius: 20, fontSize: 13, cursor: 'pointer', flexShrink: 0,
                    border: `1px solid ${activeTab === tab ? 'rgba(0,240,255,0.5)' : 'rgba(255,255,255,0.1)'}`,
                    background: activeTab === tab ? 'rgba(0,240,255,0.1)' : 'transparent',
                    color: activeTab === tab ? '#00f0ff' : '#cccccc',
                    fontWeight: activeTab === tab ? 600 : 400,
                    transition: 'all 0.15s', whiteSpace: 'nowrap',
                  }}
                >{label}</button>
              ))}
            </div>
          )}

          {filteredLibrary.length > 0 && (
            <section>
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 14 }}>
                <h2 style={{ fontSize: '0.95rem', fontWeight: 700, color: '#e2d9f3', margin: 0 }}>{t('songs.yourSongs')}</h2>
                <button
                  onClick={() => setNewPlModal(true)}
                  style={{
                    background: 'none', border: '1px solid rgba(0,240,255,0.35)', borderRadius: 5,
                    color: '#00f0ff', fontSize: 11, cursor: 'pointer', padding: '4px 12px',
                    transition: 'all 0.15s',
                  }}
                >
                  + New Playlist
                </button>
              </div>

              {/* Search bar */}
              <div style={{ position: 'relative', marginBottom: 18 }}>
                <span style={{ position: 'absolute', left: 12, top: '50%', transform: 'translateY(-50%)', fontSize: 15, pointerEvents: 'none', color: '#cccccc' }}>🔍</span>
                <input
                  className="songs-search-input"
                  type="text"
                  placeholder="Search songs, genres, descriptions…"
                  value={search}
                  onChange={(e) => setSearch(e.target.value)}
                  style={{
                    width: '100%', boxSizing: 'border-box',
                    padding: '10px 36px 10px 36px',
                    borderRadius: 10,
                    border: '1px solid rgba(0,240,255,0.2)',
                    background: 'rgba(0,0,0,0.4)',
                    color: '#e2d9f3',
                    fontSize: 14,
                    transition: 'border-color 0.2s, box-shadow 0.2s',
                  }}
                />
                {search && (
                  <button
                    onClick={() => setSearch('')}
                    style={{
                      position: 'absolute', right: 10, top: '50%', transform: 'translateY(-50%)',
                      background: 'none', border: 'none', color: '#cccccc', fontSize: 16,
                      cursor: 'pointer', padding: '0 4px', lineHeight: 1,
                    }}
                    title="Clear search"
                  >✕</button>
                )}
              </div>

              {activeTab === 'favourites' && tabFilteredLibrary.length === 0 && !search && (
                <p style={{ color: '#444', fontSize: 13, textAlign: 'center', padding: '40px 0' }}>
                  {t('songs.tabs.noFavourites')}
                </p>
              )}
              {activeTab === 'recent' && tabFilteredLibrary.length === 0 && !search && (
                <p style={{ color: '#444', fontSize: 13, textAlign: 'center', padding: '40px 0' }}>
                  {t('songs.tabs.noRecent')}
                </p>
              )}
              {search && tabFilteredLibrary.length === 0 && (
                <p style={{ color: '#cccccc', fontSize: 13, textAlign: 'center', padding: '40px 0' }}>
                  No songs found for &ldquo;{search}&rdquo;
                </p>
              )}
              <div className="songs-grid" style={S.grid}>
                {visibleLibrary.map((v) => (
                  v.genre_tag === 'kids_story' ? (
                    <StoryCard
                      key={v.variant_id}
                      variant={v}
                      title={v.title}
                      onDelete={handleDeleteVariant}
                      deleting={deletingVariants.has(v.variant_id)}
                    />
                  ) : (
                    <SongCard
                      key={v.variant_id}
                      variant={v}
                      title={v.title}
                      activeWsRef={activeWsRef}
                      canYouTube={canYouTube}
                      ytConnected={youtubeConnected}
                      ytStatus={ytStatus[v.variant_id]}
                      ytUrl={ytUrls[v.variant_id]}
                      ytError={ytErrors[v.variant_id]}
                      onYouTubeClick={handleYouTubeClick}
                      canDid={canDid}
                      didSt={didStatus[v.variant_id]}
                      videoUrl={videoUrls[v.variant_id]}
                      onAvatarClick={handleAvatarClick}
                      videoCredits={credits.video_credits}
                      didPlanOk={didPlanOk}
                      isAdmin={isAdmin}
                      onDelete={handleDeleteVariant}
                      deleting={deletingVariants.has(v.variant_id)}
                      musicVideoUrl={musicVideoUrls[v.variant_id]}
                      onRemake={handleOpenRemake}
                      onTelegramClick={handleTelegramPost}
                      artistName={credits.artist_name}
                      onRegenerate={handleRegenerate}
                      isFavourite={favourites.has(v.variant_id)}
                      onToggleFavourite={handleToggleFavourite}
                      isFreeTier={isFreeTier}
                      animateCover={animateCover}
                      isPublic={publicVariants.has(v.variant_id)}
                      onShareToggle={handleShareToggle}
                      playlists={playlists}
                      onAddToPlaylist={handleAddToPlaylist}
                      premiumCredits={credits.premium_credits}
                      stemsData={stemsData[v.variant_id]}
                      onGetStems={handleGetStems}
                      onUpgrade={setUpgradeFeature}
                      onOpenCover={(variantId, title) => { setCoverModal({ variantId, sourceTitle: title }); setCoverLyrics(''); setCoverError(''); }}
                      soundPersonaVariantId={soundPersona?.sound_persona_variant_id ?? null}
                      onLockSound={handleLockSound}
                      isSaved={isSaved(v.variant_id)}
                      isDownloading={downloading.has(v.variant_id)}
                      onSaveOffline={() => handleSaveOffline(v)}
                      onRemoveSaved={() => removeSaved(v.variant_id)}
                      onPlayOffline={!isOnline && isSaved(v.variant_id) ? () => handlePlayOffline(v) : null}
                    />
                  )
                ))}
              </div>
              {tabFilteredLibrary.length > MAX_RENDERED && (
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 10, marginTop: 24 }}>
                  <button
                    onClick={() => setWindowStart((s) => Math.max(0, s - 10))}
                    disabled={windowStart === 0}
                    style={{
                      padding: '9px 20px', borderRadius: 8,
                      border: '1px solid rgba(255,255,255,0.1)', background: 'transparent',
                      color: windowStart === 0 ? '#333' : '#888', fontSize: 13, cursor: windowStart === 0 ? 'default' : 'pointer',
                    }}
                  >
                    ← Newer
                  </button>
                  <span style={{ fontSize: 12, color: '#444' }}>
                    {windowStart + 1}–{Math.min(windowStart + MAX_RENDERED, tabFilteredLibrary.length)} of {tabFilteredLibrary.length}
                  </span>
                  <button
                    onClick={() => setWindowStart((s) => Math.min(s + 10, tabFilteredLibrary.length - MAX_RENDERED))}
                    disabled={windowStart + MAX_RENDERED >= tabFilteredLibrary.length}
                    style={{
                      padding: '9px 20px', borderRadius: 8,
                      border: '1px solid rgba(255,255,255,0.1)', background: 'transparent',
                      color: windowStart + MAX_RENDERED >= tabFilteredLibrary.length ? '#333' : '#888',
                      fontSize: 13, cursor: windowStart + MAX_RENDERED >= tabFilteredLibrary.length ? 'default' : 'pointer',
                    }}
                  >
                    Older →
                  </button>
                </div>
              )}
            </section>
          )}

          {!activeJob && filteredLibrary.length === 0 && (
            <div style={{ textAlign: 'center', padding: '80px 0' }}>
              <div style={{ fontSize: 56, marginBottom: 16, opacity: 0.15 }}>♫</div>
              <p style={{ fontSize: 15, color: '#cccccc' }}>
                {isOnline
                  ? t('songs.emptySongs')
                  : 'No songs saved yet. Go online to save songs for offline playback.'}
              </p>
            </div>
          )}
          {offlineToast && (
            <div style={{
              position:  'fixed',
              bottom:    80,
              left:      '50%',
              transform: 'translateX(-50%)',
              background:   'rgba(18,18,30,0.96)',
              border:       '1px solid rgba(245,158,11,0.4)',
              borderRadius: 10,
              padding:   '12px 20px',
              color:     '#fbbf24',
              fontSize:  13,
              fontWeight: 600,
              zIndex:    9999,
              whiteSpace: 'nowrap',
              boxShadow: '0 8px 32px rgba(0,0,0,0.5)',
              pointerEvents: 'none',
            }}>
              📵 {offlineToast}
            </div>
          )}
        </div>
      </div>

      {ytUpgradePrompt && (
        <div onClick={() => setYtUpgradePrompt(false)} style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.75)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 1000, padding: 24 }}>
          <div onClick={(e) => e.stopPropagation()} style={{ background: '#12121e', border: '1px solid rgba(167,139,250,0.3)', borderRadius: 20, padding: '32px 28px 28px', width: '100%', maxWidth: 380, textAlign: 'center' }}>
            <div style={{ fontSize: 48, marginBottom: 12 }}>📺</div>
            <h3 style={{ fontSize: 18, fontWeight: 800, color: '#e2d9f3', marginBottom: 10 }}>YouTube Upload is a Premium Feature</h3>
            <p style={{ fontSize: 14, color: 'rgba(255,255,255,0.65)', lineHeight: 1.6, marginBottom: 6 }}>
              Upload your songs straight to YouTube with one click.
            </p>
            <p style={{ fontSize: 14, color: 'rgba(255,255,255,0.65)', lineHeight: 1.6, marginBottom: 24 }}>
              Upgrade to <strong style={{ color: '#a78bfa' }}>Music Starter (£9/mo)</strong> or higher to unlock YouTube upload.
            </p>
            <div style={{ display: 'flex', gap: 10 }}>
              <button onClick={() => setYtUpgradePrompt(false)} style={{ flex: 1, padding: '12px 0', borderRadius: 10, border: '1px solid rgba(255,255,255,0.1)', background: 'transparent', color: '#888', fontSize: 14, cursor: 'pointer' }}>Not now</button>
              <button
                onClick={() => { setYtUpgradePrompt(false); window.location.href = '/billing'; }}
                style={{ flex: 2, padding: '12px 0', borderRadius: 10, border: 'none', background: 'linear-gradient(135deg, #7c3aed 0%, #a855f7 100%)', color: '#fff', fontSize: 14, fontWeight: 700, cursor: 'pointer' }}
              >
                Upgrade →
              </button>
            </div>
          </div>
        </div>
      )}

      {ytModal && (
        <div onClick={() => setYtModal(null)} style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.7)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 1000, padding: 24 }}>
          <div onClick={(e) => e.stopPropagation()} style={{ background: '#12121e', border: '1px solid rgba(255,255,255,0.1)', borderRadius: 16, padding: '28px 28px 24px', width: '100%', maxWidth: 380 }}>
            <h3 style={{ fontSize: 16, fontWeight: 700, color: '#e2d9f3', marginBottom: 6 }}>{t('songs.ytModal.title')}</h3>
            <p style={{ fontSize: 13, color: '#cccccc', marginBottom: 20 }}>{ytModal.title || `Song #${ytModal.variant_id}`}</p>
            <label style={{ fontSize: 11, fontWeight: 600, color: '#cccccc', letterSpacing: '0.6px', textTransform: 'uppercase', display: 'block', marginBottom: 8 }}>{t('songs.ytModal.privacyLabel')}</label>
            <select
              value={ytPrivacy}
              onChange={(e) => setYtPrivacy(e.target.value)}
              style={{ width: '100%', background: 'rgba(255,255,255,0.04)', border: '1px solid rgba(255,255,255,0.1)', borderRadius: 8, padding: '10px 12px', color: '#c4b5fd', fontSize: 14, outline: 'none', marginBottom: 24 }}
            >
              <option value="unlisted">{t('songs.ytModal.unlisted')}</option>
              <option value="public">{t('songs.ytModal.public')}</option>
              <option value="private">{t('songs.ytModal.private')}</option>
            </select>
            <div style={{ display: 'flex', gap: 10 }}>
              <button onClick={() => setYtModal(null)} style={{ flex: 1, padding: '11px 0', borderRadius: 8, border: '1px solid rgba(255,255,255,0.1)', background: 'transparent', color: '#666', fontSize: 14, cursor: 'pointer' }}>{t('songs.ytModal.cancel')}</button>
              <button onClick={handleYouTubeUpload} style={{ flex: 1, padding: '11px 0', borderRadius: 8, border: 'none', background: 'linear-gradient(135deg, #7c3aed 0%, #a855f7 100%)', color: '#fff', fontSize: 14, fontWeight: 700, cursor: 'pointer' }}>{t('songs.ytModal.upload')}</button>
            </div>
          </div>
        </div>
      )}

      {remakeModal && (
        <div onClick={() => { setRemakeModal(null); setRemakeGenre(''); setRemakeStyle(''); setRemakeError(''); }} style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.8)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 1000, padding: 20 }}>
          <div onClick={(e) => e.stopPropagation()} style={{ background: '#0d0d14', border: '1px solid rgba(0,240,255,0.2)', borderRadius: 16, padding: '28px 24px', width: '100%', maxWidth: 520, maxHeight: '90vh', overflowY: 'auto' }}>
            <h3 style={{ fontSize: 17, fontWeight: 800, color: '#f0eeff', marginBottom: 4 }}>{t('songs.remakeModal.title')}</h3>
            <p style={{ fontSize: 13, color: '#cccccc', marginBottom: 22 }}>{remakeModal.title || `Song #${remakeModal.variantId}`}</p>
            <p style={{ fontSize: 11, fontWeight: 600, color: '#cccccc', letterSpacing: '0.6px', textTransform: 'uppercase', marginBottom: 10 }}>{t('songs.remakeModal.genreLabel')}</p>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 12, marginBottom: 20 }}>
              {GENRE_CATEGORIES.map(cat => {
                const open = remakeOpenCats.has(cat.id);
                const hasSel = cat.genres.includes(remakeGenre);
                return (
                  <div key={cat.id}>
                    <button
                      type="button"
                      onClick={() => toggleRemakeCat(cat.id)}
                      aria-expanded={open}
                      style={{
                        width: '100%', display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 8,
                        padding: '8px 11px', borderRadius: 9,
                        border: `1.5px solid ${cat.color}${open ? 'aa' : '40'}`,
                        background: open ? cat.color + '14' : (hasSel ? cat.color + '0e' : 'transparent'),
                        cursor: 'pointer', transition: 'all 0.2s ease', fontFamily: 'inherit',
                      }}
                    >
                      <span style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                        <span style={{ fontSize: 10, color: cat.color, transition: 'transform 0.2s ease', transform: open ? 'rotate(90deg)' : 'rotate(0deg)', display: 'inline-block' }}>▶</span>
                        <span style={{ fontSize: 11, fontWeight: 700, color: cat.color, letterSpacing: '0.7px', textTransform: 'uppercase' }}>{cat.label}</span>
                      </span>
                      {hasSel && (
                        <span style={{ fontSize: 10, fontWeight: 800, color: '#000', background: cat.color, borderRadius: 10, padding: '1px 7px' }}>✓</span>
                      )}
                    </button>
                    {open && (
                      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 5, padding: '8px 2px 2px' }}>
                        {cat.genres.map(g => {
                          const sel = remakeGenre === g;
                          return (
                            <button
                              key={g}
                              onClick={() => setRemakeGenre(g)}
                              className={sel ? 'genre-pill genre-pill--sel' : 'genre-pill'}
                              style={{
                                '--pill-color': cat.color,
                                '--pill-hover-bg': cat.color + '28',
                                padding: '5px 11px',
                                borderRadius: 20,
                                border: sel ? `2px solid ${cat.color}` : `1.5px solid ${cat.color}55`,
                                background: sel ? cat.color : 'transparent',
                                color: sel ? '#000' : cat.color,
                                fontSize: 12,
                                fontWeight: sel ? 700 : 500,
                                cursor: 'pointer',
                                transition: 'all 0.2s ease',
                                boxShadow: sel ? `0 0 14px ${cat.color}, 0 0 26px ${cat.color}60` : 'none',
                                transform: sel ? 'scale(1.05)' : 'scale(1)',
                              }}
                            >
                              {gLabel(g)}
                            </button>
                          );
                        })}
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
            <p style={{ fontSize: 11, fontWeight: 600, color: '#cccccc', letterSpacing: '0.6px', textTransform: 'uppercase', marginBottom: 8 }}>{t('songs.remakeModal.styleNoteLabel')}</p>
            <input type="text" value={remakeStyle} onChange={(e) => setRemakeStyle(e.target.value)}
              placeholder={t('songs.remakeModal.stylePlaceholder')}
              style={{ width: '100%', boxSizing: 'border-box', background: 'rgba(255,255,255,0.04)', border: '1px solid rgba(255,255,255,0.1)', borderRadius: 8, padding: '10px 12px', color: '#f0eeff', fontSize: 13, fontFamily: 'inherit', outline: 'none', marginBottom: 20 }}
            />
            {!isAdmin && <p style={{ fontSize: 12, color: '#cccccc', marginBottom: 16 }}>{t('songs.remakeModal.creditInfo', { balance: credits.balance })}</p>}
            {remakeError && <div style={{ background: 'rgba(239,68,68,0.1)', border: '1px solid rgba(239,68,68,0.25)', borderRadius: 8, padding: '8px 12px', color: '#fca5a5', fontSize: 12, marginBottom: 14 }}>{remakeError}</div>}
            <div style={{ display: 'flex', gap: 10 }}>
              <button onClick={() => { setRemakeModal(null); setRemakeGenre(''); setRemakeStyle(''); setRemakeError(''); }} style={{ flex: 1, padding: '11px 0', borderRadius: 8, border: '1px solid rgba(255,255,255,0.1)', background: 'transparent', color: '#666', fontSize: 14, cursor: 'pointer' }}>{t('songs.remakeModal.cancel')}</button>
              <button onClick={handleRemake} disabled={!remakeGenre || remakeLoading} style={{ flex: 2, padding: '11px 0', borderRadius: 8, border: 'none', background: remakeLoading || !remakeGenre ? 'rgba(0,240,255,0.3)' : '#00f0ff', color: '#000', fontSize: 14, fontWeight: 700, cursor: remakeLoading || !remakeGenre ? 'not-allowed' : 'pointer' }}>
                {remakeLoading ? t('songs.remakeModal.generating') : t('songs.remakeModal.generate')}
              </button>
            </div>
          </div>
        </div>
      )}

      {avatarModal && (
        <div onClick={closeAvatarModal} style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.75)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 1000, padding: 24 }}>
          <div onClick={(e) => e.stopPropagation()} style={{ background: '#12121e', border: '1px solid rgba(255,255,255,0.1)', borderRadius: 16, padding: '28px 28px 24px', width: '100%', maxWidth: 480, maxHeight: '90vh', overflowY: 'auto' }}>
            <h3 style={{ fontSize: 16, fontWeight: 700, color: '#e2d9f3', marginBottom: 4 }}>{t('songs.avatarModal.title')}</h3>
            <p style={{ fontSize: 13, color: '#cccccc', marginBottom: 16 }}>{t('songs.avatarModal.desc')}</p>
            <p style={{ fontSize: 12, color: '#4a4a6a', background: 'rgba(167,139,250,0.06)', border: '1px solid rgba(167,139,250,0.12)', borderRadius: 8, padding: '8px 12px', marginBottom: 20, lineHeight: 1.5 }}>
              {t('songs.avatarModal.tip')}
            </p>

            {avatars.length > 0 ? (
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 10, marginBottom: 20 }}>
                {avatars.map((av) => {
                  const sel = selectedAvatarUrl === av.image_url;
                  const isFemale = av.id.startsWith('w');
                  return (
                    <button
                      key={av.id}
                      className="avatar-thumb"
                      onClick={() => setSelectedAvatarUrl(av.image_url)}
                      style={{ border: `2px solid ${sel ? '#a78bfa' : 'rgba(255,255,255,0.08)'}`, borderRadius: 10, padding: 0, overflow: 'hidden', background: 'transparent', cursor: 'pointer', opacity: sel ? 1 : 0.65, transition: 'border-color 0.15s, opacity 0.15s', display: 'flex', flexDirection: 'column', alignItems: 'stretch' }}
                    >
                      <img src={av.image_url} alt={av.name} style={{ width: '100%', aspectRatio: '1/1', objectFit: 'cover', display: 'block' }} />
                      <span style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 4, fontSize: 11, fontWeight: 500, color: sel ? '#c4b5fd' : '#666', padding: '5px 4px' }}>
                        {av.name}
                        <span style={{ fontSize: 9, fontWeight: 600, color: isFemale ? '#f9a8d4' : '#93c5fd', background: isFemale ? 'rgba(249,168,212,0.12)' : 'rgba(147,197,253,0.12)', borderRadius: 4, padding: '1px 4px', letterSpacing: '0.3px' }}>
                          {isFemale ? 'F' : 'M'}
                        </span>
                      </span>
                    </button>
                  );
                })}
              </div>
            ) : (
              <div style={{ height: 40, display: 'flex', alignItems: 'center', marginBottom: 20 }}>
                <span style={{ color: '#444', fontSize: 13 }}>{t('songs.avatarModal.loadingAvatars')}</span>
              </div>
            )}

            <div style={{ borderTop: '1px solid rgba(255,255,255,0.06)', paddingTop: 16, marginBottom: 24 }}>
              <p style={{ fontSize: 12, color: '#cccccc', marginBottom: 10 }}>{t('songs.avatarModal.uploadDesc')}</p>
              <div style={{ display: 'flex', gap: 10, alignItems: 'center' }}>
                <button
                  onClick={() => photoInputRef.current?.click()}
                  disabled={uploadingPhoto}
                  style={{ padding: '7px 16px', borderRadius: 8, border: '1px solid rgba(255,255,255,0.12)', background: 'rgba(255,255,255,0.04)', color: '#888', fontSize: 12, cursor: uploadingPhoto ? 'default' : 'pointer', flexShrink: 0 }}
                >
                  {uploadingPhoto ? t('songs.avatarModal.uploadingPhoto') : t('songs.avatarModal.choosePhoto')}
                </button>
                {selectedAvatarUrl && selectedAvatarUrl.startsWith('/files/avatars/') && (
                  <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                    <img src={`${BACKEND_URL}${selectedAvatarUrl}`} alt="Custom" style={{ width: 40, height: 40, borderRadius: 6, objectFit: 'cover', border: '2px solid #a78bfa' }} />
                    <span style={{ fontSize: 11, color: '#a78bfa' }}>{t('songs.avatarModal.customPhotoSelected')}</span>
                  </div>
                )}
              </div>
            </div>

            <div style={{ borderTop: '1px solid rgba(255,255,255,0.06)', paddingTop: 16, marginBottom: 24 }}>
              <p style={{ fontSize: 11, fontWeight: 600, color: '#cccccc', letterSpacing: '0.6px', textTransform: 'uppercase', marginBottom: 10 }}>{t('songs.avatarModal.generateAI')}</p>
              {portraitTimedOut ? (
                <div>
                  <p style={{ fontSize: 13, color: '#f87171', marginBottom: 10 }}>{t('songs.avatarModal.timeout')}</p>
                  <button onClick={handlePortraitRetry} style={{ padding: '7px 18px', borderRadius: 8, border: '1px solid rgba(248,113,113,0.35)', background: 'rgba(248,113,113,0.08)', color: '#f87171', fontSize: 12, fontWeight: 500, cursor: 'pointer' }}>{t('songs.avatarModal.retry')}</button>
                </div>
              ) : portraitImageUrl ? (
                <div style={{ display: 'flex', alignItems: 'center', gap: 14 }}>
                  <button
                    onClick={() => setSelectedAvatarUrl(portraitImageUrl)}
                    style={{ border: `2px solid ${selectedAvatarUrl === portraitImageUrl ? '#a78bfa' : 'rgba(255,255,255,0.15)'}`, borderRadius: 10, padding: 0, overflow: 'hidden', background: 'transparent', cursor: 'pointer', width: 80, height: 80, flexShrink: 0, transition: 'border-color 0.15s' }}
                  >
                    <img src={portraitImageUrl} alt="AI Generated" style={{ width: '100%', height: '100%', objectFit: 'cover', display: 'block' }} />
                  </button>
                  <div>
                    <span style={{ display: 'inline-block', fontSize: 10, fontWeight: 700, color: '#a78bfa', background: 'rgba(167,139,250,0.12)', border: '1px solid rgba(167,139,250,0.25)', borderRadius: 4, padding: '2px 7px', letterSpacing: '0.3px', textTransform: 'uppercase', marginBottom: 6 }}>AI Generated</span>
                    <p style={{ fontSize: 12, color: '#cccccc', margin: '0 0 4px' }}>{selectedAvatarUrl === portraitImageUrl ? t('songs.avatarModal.selected') : t('songs.avatarModal.clickSelect')}</p>
                    <button onClick={() => { if (selectedAvatarUrl === portraitImageUrl) setSelectedAvatarUrl(null); setPortraitImageUrl(null); setPortraitJobId(null); }} style={{ fontSize: 11, color: '#444', background: 'none', border: 'none', cursor: 'pointer', padding: 0, textDecoration: 'underline' }}>{t('songs.avatarModal.regenerate')}</button>
                  </div>
                </div>
              ) : portraitGenerating ? (
                <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                  <span style={{ fontSize: 13, color: '#666' }}>{t('songs.avatarModal.generating')}</span>
                  <span style={{ fontSize: 14, color: '#444', letterSpacing: 2 }}>···</span>
                </div>
              ) : (
                <div style={{ display: 'flex', gap: 8 }}>
                  <button onClick={() => handleGeneratePortrait('m')} style={{ padding: '7px 18px', borderRadius: 8, border: '1px solid rgba(147,197,253,0.3)', background: 'rgba(147,197,253,0.06)', color: '#93c5fd', fontSize: 12, fontWeight: 500, cursor: 'pointer' }}>{t('songs.avatarModal.genderMale')}</button>
                  <button onClick={() => handleGeneratePortrait('f')} style={{ padding: '7px 18px', borderRadius: 8, border: '1px solid rgba(249,168,212,0.3)', background: 'rgba(249,168,212,0.06)', color: '#f9a8d4', fontSize: 12, fontWeight: 500, cursor: 'pointer' }}>{t('songs.avatarModal.genderFemale')}</button>
                </div>
              )}
            </div>

            <div style={{ display: 'flex', gap: 10 }}>
              <button onClick={closeAvatarModal} style={{ flex: 1, padding: '11px 0', borderRadius: 8, border: '1px solid rgba(255,255,255,0.1)', background: 'transparent', color: '#666', fontSize: 14, cursor: 'pointer' }}>{t('songs.avatarModal.cancel')}</button>
              <button
                onClick={handleAvatarSubmit}
                disabled={!selectedAvatarUrl || avatarSubmitting}
                style={{ flex: 1, padding: '11px 0', borderRadius: 8, border: 'none', background: selectedAvatarUrl ? 'linear-gradient(135deg, #7c3aed 0%, #a855f7 100%)' : 'rgba(255,255,255,0.05)', color: selectedAvatarUrl ? '#fff' : '#444', fontSize: 14, fontWeight: 700, cursor: selectedAvatarUrl ? 'pointer' : 'default' }}
              >
                {avatarSubmitting ? t('songs.avatarModal.submitting') : t('songs.avatarModal.create')}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Cover This Song modal */}
      {coverModal && (
        <div
          onClick={() => setCoverModal(null)}
          style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.8)', zIndex: 1000, display: 'flex', alignItems: 'center', justifyContent: 'center', padding: 20 }}
        >
          <div
            onClick={e => e.stopPropagation()}
            style={{ background: '#12121e', border: '1px solid rgba(0,240,255,0.25)', borderRadius: 16, padding: '28px 24px', maxWidth: 480, width: '100%' }}
          >
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 14 }}>
              <h2 style={{ margin: 0, fontSize: 18, fontWeight: 800, background: 'linear-gradient(90deg,#00f0ff,#a855f7)', WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent' }}>
                🎤 Cover This Song
              </h2>
              <button onClick={() => setCoverModal(null)} style={{ background: 'none', border: '1px solid rgba(255,255,255,0.12)', borderRadius: 6, color: '#cccccc', fontSize: 13, cursor: 'pointer', padding: '4px 9px' }}>✕</button>
            </div>

            <div style={{ background: 'rgba(0,240,255,0.05)', border: '1px solid rgba(0,240,255,0.15)', borderRadius: 8, padding: '10px 14px', marginBottom: 16, fontSize: 13, color: '#cccccc', lineHeight: 1.5 }}>
              Zeus will create a <strong style={{ color: '#e2e8f0' }}>new song</strong> in the same style as this one but with your lyrics. It won't be an exact overlay on the original beat — think of it like a <strong style={{ color: '#e2e8f0' }}>cover version</strong> inspired by this track.
            </div>

            <textarea
              value={coverLyrics}
              onChange={e => setCoverLyrics(e.target.value)}
              placeholder={"[Verse 1]\nWrite your lyrics here...\n\n[Chorus]\nYour chorus here..."}
              rows={8}
              maxLength={3000}
              style={{ width: '100%', background: 'rgba(255,255,255,0.04)', border: '1px solid rgba(255,255,255,0.12)', borderRadius: 8, color: '#e2e8f0', fontSize: 13, padding: '10px 12px', outline: 'none', resize: 'vertical', fontFamily: 'inherit', boxSizing: 'border-box', marginBottom: 8 }}
            />
            <div style={{ fontSize: 11, color: '#cccccc', textAlign: 'right', marginBottom: 12 }}>{coverLyrics.length}/3000 · costs 1 song credit</div>

            {coverError && <p style={{ color: '#f87171', fontSize: 13, margin: '0 0 10px' }}>{coverError}</p>}

            <button
              onClick={handleCoverSubmit}
              disabled={coverLoading || !coverLyrics.trim()}
              style={{ width: '100%', padding: '11px 0', background: 'linear-gradient(135deg,#7c3aed,#a855f7)', border: 'none', borderRadius: 8, color: '#fff', fontWeight: 700, fontSize: 14, cursor: coverLoading || !coverLyrics.trim() ? 'not-allowed' : 'pointer', opacity: coverLoading || !coverLyrics.trim() ? 0.55 : 1, transition: 'opacity 0.2s' }}
            >
              {coverLoading ? '🎵 Submitting…' : '🎤 Generate Cover'}
            </button>
          </div>
        </div>
      )}

      {/* Paid-feature upgrade prompt — web shows /billing CTA, iOS shows compliant message */}
      {upgradeFeature && UPGRADE_FEATURES[upgradeFeature] && (
        <div
          onClick={() => setUpgradeFeature(null)}
          style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.8)', zIndex: 1000, display: 'flex', alignItems: 'center', justifyContent: 'center', padding: 20 }}
        >
          <div
            onClick={e => e.stopPropagation()}
            style={{ background: '#12121e', border: '1px solid rgba(0,240,255,0.25)', borderRadius: 16, padding: '24px 24px 28px', maxWidth: 420, width: '100%', textAlign: 'center' }}
          >
            <div style={{ display: 'flex', justifyContent: 'flex-end' }}>
              <button onClick={() => setUpgradeFeature(null)} style={{ background: 'none', border: '1px solid rgba(255,255,255,0.12)', borderRadius: 6, color: '#cccccc', fontSize: 13, cursor: 'pointer', padding: '4px 9px' }}>✕</button>
            </div>
            <div style={{ fontSize: 40, marginBottom: 10 }}>{UPGRADE_FEATURES[upgradeFeature].icon}</div>
            <h2 style={{ margin: '0 0 10px', fontSize: 20, fontWeight: 800, color: '#e2e8f0' }}>
              {UPGRADE_FEATURES[upgradeFeature].title}
            </h2>
            <p style={{ margin: '0 0 20px', color: '#cccccc', fontSize: 14, lineHeight: 1.6 }}>
              {UPGRADE_FEATURES[upgradeFeature].desc}
            </p>
            {isIOSWebView ? (
              <p style={{ margin: 0, color: '#00f0ff', fontSize: 14, fontWeight: 600 }}>
                Visit zeusbeats.com to upgrade your plan.
              </p>
            ) : (
              <Link
                to="/billing"
                onClick={() => setUpgradeFeature(null)}
                style={{ display: 'block', width: '100%', boxSizing: 'border-box', padding: '13px 0', background: 'linear-gradient(135deg,#00c8d4,#00f0ff)', borderRadius: 10, color: '#000', fontWeight: 800, fontSize: 15, textDecoration: 'none', boxShadow: '0 0 18px rgba(0,240,255,0.3)' }}
              >
                Upgrade from £4.50 first month
              </Link>
            )}
          </div>
        </div>
      )}

      {/* Cover success toast */}
      {coverToast && (
        <div style={{ position: 'fixed', bottom: 24, left: '50%', transform: 'translateX(-50%)', background: 'rgba(0,240,255,0.12)', border: '1px solid rgba(0,240,255,0.4)', borderRadius: 10, padding: '12px 24px', color: '#00f0ff', fontWeight: 600, fontSize: 14, zIndex: 2000, whiteSpace: 'nowrap' }}>
          🎤 Your cover is generating! Check your library soon.
        </div>
      )}
      {lockToast && (
        <div style={{ position: 'fixed', bottom: 90, left: '50%', transform: 'translateX(-50%)', background: 'rgba(0,0,0,0.92)', border: '1px solid rgba(0,240,255,0.35)', borderRadius: 10, padding: '12px 22px', color: '#00f0ff', fontSize: 13, fontWeight: 600, zIndex: 9999, whiteSpace: 'nowrap', boxShadow: '0 4px 24px rgba(0,240,255,0.12)' }}>
          {lockToast}
        </div>
      )}

      {/* Floating Discover button */}
      <a
        href="/discover"
        style={{
          position: 'fixed', bottom: 20, right: 20,
          background: 'linear-gradient(135deg, #00f0ff, #ff0099)',
          color: '#000', borderRadius: 50, padding: '12px 20px',
          fontWeight: 700, fontSize: 14, textDecoration: 'none',
          zIndex: 100, boxShadow: '0 0 20px rgba(0,240,255,0.5)',
          fontFamily: "'Orbitron', sans-serif",
        }}
      >
        🎵 Discover
      </a>

      {/* New Playlist modal */}
      {newPlModal && (
        <div
          style={{
            position: 'fixed', inset: 0, zIndex: 9000,
            background: 'rgba(0,0,0,0.75)', backdropFilter: 'blur(6px)',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
          }}
          onClick={() => setNewPlModal(false)}
        >
          <div
            style={{
              background: '#12121e', border: '1px solid rgba(0,240,255,0.25)',
              borderRadius: 12, padding: 28, width: '90%', maxWidth: 360,
              boxShadow: '0 0 40px rgba(0,240,255,0.15)',
            }}
            onClick={e => e.stopPropagation()}
          >
            <h3 style={{ color: '#e2d9f3', fontSize: 16, fontWeight: 700, margin: '0 0 18px' }}>
              New Playlist
            </h3>
            <form onSubmit={handleCreatePlaylist}>
              <input
                autoFocus
                type="text"
                placeholder="Playlist name"
                value={newPlName}
                onChange={e => setNewPlName(e.target.value)}
                maxLength={80}
                style={{
                  width: '100%', boxSizing: 'border-box',
                  background: 'rgba(255,255,255,0.04)', border: '1px solid rgba(0,240,255,0.25)',
                  borderRadius: 7, color: '#e2d9f3', fontSize: 14, padding: '10px 12px',
                  outline: 'none', marginBottom: 16,
                }}
              />
              <div style={{ display: 'flex', gap: 10 }}>
                <button
                  type="button"
                  onClick={() => setNewPlModal(false)}
                  style={{
                    flex: 1, padding: '10px 0', borderRadius: 7,
                    border: '1px solid rgba(255,255,255,0.1)', background: 'none',
                    color: '#888', fontSize: 14, cursor: 'pointer',
                  }}
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={!newPlName.trim() || newPlLoading}
                  style={{
                    flex: 1, padding: '10px 0', borderRadius: 7, border: 'none',
                    background: newPlName.trim() ? 'linear-gradient(135deg, rgba(0,240,255,0.2), rgba(0,191,255,0.2))' : 'rgba(255,255,255,0.05)',
                    border: '1px solid rgba(0,240,255,0.35)',
                    color: newPlName.trim() ? '#00f0ff' : '#444',
                    fontSize: 14, fontWeight: 600, cursor: newPlName.trim() ? 'pointer' : 'default',
                  }}
                >
                  {newPlLoading ? 'Creating…' : 'Create'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {showKidsPinGate && token && user?.account_type !== 'school' && (
        <Suspense fallback={null}>
          <KidsPinGateLoader
            token={token}
            hasPIN={!!user?.has_kids_pin}
            onSuccess={() => {
              sessionStorage.setItem('kidsMode', '1');
              window.location.href = '/kids';
            }}
            onCancel={() => setShowKidsPinGate(false)}
          />
        </Suspense>
      )}
    </>
  );
}
