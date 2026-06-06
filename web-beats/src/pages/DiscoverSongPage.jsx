import { useEffect, useRef, useState } from 'react';
import { useParams, useNavigate, Link } from 'react-router-dom';
import { BACKEND_URL } from '../brand';

const CYAN = '#00f0ff';
const PINK = '#f472b6';

const GENRE_LABELS = {
  hiphop:'Hip-Hop', rnb:'R&B', pop:'Pop', rock:'Rock', soul:'Soul',
  blues:'Blues', jazz:'Jazz', reggae:'Reggae', lofi:'Lo-Fi', edm:'EDM',
  drumandbass:'D&B', grime:'Grime', ukgarage:'UK Garage', jungle:'Jungle',
  bassline:'Bassline', house:'House', techno:'Techno', loversrock:'Lovers Rock',
  ukdrill:'UK Drill', kpop:'K-Pop', classical:'Classical', indie:'Indie',
  afrobeats:'Afrobeats', amapiano:'Amapiano', afroswing:'Afroswing',
  country:'Country', acoustic:'Acoustic', hyperpop:'Hyperpop',
  trap:'Trap', eastcoasthiphop:'East Coast Hip-Hop', poprap:'Pop Rap',
  synthwave:'Synthwave', gospel:'Gospel', trapsoul:'Trap Soul',
  meditation:'Meditation', christmas:'Christmas', corridos:'Corridos',
  healingfrequency:'Healing Frequency', irishjig:'Irish Jig', irishfolk:'Irish Folk',
  bluessoul:'Blues Soul', deepsoulblues:'Deep Soul Blues', ukstreetsoul:'UK Street Soul',
  technhouse:'Tech House', driftphonk:'Drift Phonk', jerseyclub:'Jersey Club',
  rastadub:'Rasta Dub', deeprotbassline:'Deeprot Bassline', electronicfunk:'Electronic Funk',
  syntheticpop:'Synthetic Pop', ragga:'Ragga', dubstep:'Dubstep',
  bhangra:'Bhangra', rockney:'Rockney', metal:'Metal',
  swing:'Swing', vocaljazz:'Vocal Jazz', traditionalpop:'Traditional Pop',
  rocknroll:"Rock 'n' Roll", southemsoul:'Southern Soul', countryamericana:'Country Americana',
};
const gLabel = (g) => GENRE_LABELS[g] || (g ? g.charAt(0).toUpperCase() + g.slice(1) : '');

function setMetaTag(property, content, attr = 'property') {
  let el = document.querySelector(`meta[${attr}="${property}"]`);
  if (!el) {
    el = document.createElement('meta');
    el.setAttribute(attr, property);
    document.head.appendChild(el);
  }
  el.setAttribute('content', content);
}

function removeMetaTag(property, attr = 'property') {
  const el = document.querySelector(`meta[${attr}="${property}"]`);
  if (el) el.remove();
}

export default function DiscoverSongPage() {
  const { variantId } = useParams();
  const navigate = useNavigate();
  const audioRef = useRef(null);

  const [song, setSong]       = useState(null);
  const [loading, setLoading] = useState(true);
  const [notFound, setNotFound] = useState(false);
  const [playing, setPlaying] = useState(false);
  const [copied, setCopied]   = useState(false);

  /* ── Fetch song ──────────────────────────────────────────────────────── */
  useEffect(() => {
    fetch(`${BACKEND_URL}/api/discover/${variantId}`)
      .then(r => {
        if (!r.ok) throw new Error('not found');
        return r.json();
      })
      .then(setSong)
      .catch(() => setNotFound(true))
      .finally(() => setLoading(false));
  }, [variantId]);

  /* ── OG meta tags ────────────────────────────────────────────────────── */
  useEffect(() => {
    if (!song) return;
    const title = `${song.title || 'Untitled'} — Zeus Beats`;
    const desc  = `AI generated ${gLabel(song.genre_tag)} song. Make your own free at zeusbeats.com`;
    const pageUrl = `https://zeusbeats.com/discover/${variantId}`;

    document.title = title;
    setMetaTag('og:title',       title);
    setMetaTag('og:description', desc);
    setMetaTag('og:url',         pageUrl);
    setMetaTag('og:type',        'music.song');
    if (song.cover_url) setMetaTag('og:image', song.cover_url);
    if (song.mp3_url)   setMetaTag('og:audio', song.mp3_url);
    setMetaTag('twitter:card',        'summary_large_image', 'name');
    setMetaTag('twitter:title',       title,                 'name');
    setMetaTag('twitter:description', desc,                  'name');
    if (song.cover_url) setMetaTag('twitter:image', song.cover_url, 'name');

    return () => {
      document.title = 'Zeus Beats';
      ['og:title','og:description','og:url','og:type','og:image','og:audio'].forEach(p => removeMetaTag(p));
      ['twitter:card','twitter:title','twitter:description','twitter:image'].forEach(p => removeMetaTag(p, 'name'));
    };
  }, [song, variantId]);

  /* ── Audio play/pause ─────────────────────────────────────────────────── */
  const togglePlay = () => {
    const a = audioRef.current;
    if (!a) return;
    if (playing) { a.pause(); setPlaying(false); }
    else { a.play().then(() => setPlaying(true)).catch(() => {}); }
  };

  /* ── Copy share link ──────────────────────────────────────────────────── */
  const handleCopy = async () => {
    const url = `https://zeusbeats.com/discover/${variantId}`;
    try {
      if (navigator.share) {
        await navigator.share({ title: song?.title || 'Zeus Beats', url });
      } else {
        await navigator.clipboard.writeText(url);
      }
    } catch (_) {}
    setCopied(true);
    setTimeout(() => setCopied(false), 3000);
  };

  const dur = song?.duration_seconds;
  const durStr = dur ? `${Math.floor(dur / 60)}:${String(dur % 60).padStart(2, '0')}` : '';

  /* ── Loading ──────────────────────────────────────────────────────────── */
  if (loading) {
    return (
      <div style={{ background: '#000', height: '100svh', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
        <div style={{
          width: 36, height: 36, borderRadius: '50%',
          border: `3px solid ${CYAN}33`, borderTopColor: CYAN,
          animation: 'spin 0.8s linear infinite',
        }} />
        <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
      </div>
    );
  }

  /* ── Not found ────────────────────────────────────────────────────────── */
  if (notFound) {
    return (
      <div style={{
        background: '#000', height: '100svh', color: '#fff',
        display: 'flex', flexDirection: 'column',
        alignItems: 'center', justifyContent: 'center', gap: 20, padding: 24,
      }}>
        <p style={{ color: '#555', fontSize: 16 }}>Song not found or no longer public.</p>
        <Link to="/discover" style={{ color: CYAN, fontWeight: 600, textDecoration: 'none' }}>
          ← Browse the feed
        </Link>
      </div>
    );
  }

  return (
    <div style={{ background: '#000', height: '100svh', width: '100vw', overflow: 'hidden', position: 'relative' }}>

      {/* Hidden audio */}
      {song?.mp3_url && (
        <audio
          ref={audioRef}
          src={song.mp3_url}
          onEnded={() => setPlaying(false)}
        />
      )}

      {/* Full-screen background: HD video (premium) or Ken Burns on static cover (default) */}
      {song?.music_video_url ? (
        <video
          src={song.music_video_url}
          autoPlay
          loop
          muted
          playsInline
          style={{
            position: 'absolute', inset: 0,
            width: '100%', height: '100%',
            objectFit: 'cover',
            filter: 'brightness(0.5)',
          }}
        />
      ) : song?.cover_url ? (
        <img
          src={song.cover_url}
          alt={song.title}
          className="cover-ken-burns"
          style={{
            position: 'absolute', inset: 0,
            width: '100%', height: '100%',
            objectFit: 'cover',
            filter: 'brightness(0.4)',
          }}
        />
      ) : (
        <div style={{
          position: 'absolute', inset: 0,
          background: 'linear-gradient(135deg, #0d0d1a 0%, #1a0a2e 100%)',
        }} />
      )}

      {/* Gradient overlays */}
      <div style={{
        position: 'absolute', inset: 0,
        background: 'linear-gradient(to top, rgba(0,0,0,0.95) 0%, rgba(0,0,0,0.3) 50%, rgba(0,0,0,0.5) 100%)',
        pointerEvents: 'none',
      }} />

      {/* Cyan left edge glow */}
      <div style={{
        position: 'absolute', top: 0, bottom: 0, left: 0, width: 3,
        background: `linear-gradient(to bottom, transparent, ${CYAN}, transparent)`,
        opacity: 0.7, pointerEvents: 'none',
      }} />

      {/* Header — logo */}
      <div style={{
        position: 'absolute', top: 0, left: 0, right: 0,
        padding: '20px 24px',
        display: 'flex', alignItems: 'center', justifyContent: 'space-between',
        zIndex: 20,
      }}>
        <Link to="/" style={{
          color: CYAN, textDecoration: 'none', fontSize: 17, fontWeight: 800,
          letterSpacing: '-0.02em',
          textShadow: `0 0 16px ${CYAN}88`,
        }}>
          ⚡ Zeus Beats
        </Link>
        <Link to="/discover" style={{
          color: 'rgba(255,255,255,0.5)', textDecoration: 'none',
          fontSize: 13, fontWeight: 600,
        }}>
          ← Discover
        </Link>
      </div>

      {/* Bottom content */}
      <div style={{
        position: 'absolute', bottom: 0, left: 0, right: 0,
        padding: '0 24px 40px',
        zIndex: 20,
      }}>
        {/* Genre badge */}
        <span style={{
          display: 'inline-block',
          padding: '3px 12px',
          borderRadius: 20,
          fontSize: 11,
          fontWeight: 700,
          letterSpacing: '0.06em',
          textTransform: 'uppercase',
          background: `linear-gradient(90deg, ${CYAN}33, ${PINK}33)`,
          border: `1px solid ${CYAN}55`,
          color: CYAN,
          marginBottom: 10,
        }}>
          {gLabel(song?.genre_tag)}
        </span>

        {/* Title */}
        <p style={{
          margin: '0 0 4px',
          fontSize: 28,
          fontWeight: 800,
          color: '#fff',
          lineHeight: 1.2,
          textShadow: '0 2px 12px rgba(0,0,0,0.9)',
        }}>
          {song?.title || `Song #${variantId}`}
        </p>

        {/* Artist + duration */}
        <p style={{ margin: '0 0 6px', fontSize: 15, color: 'rgba(255,255,255,0.65)', fontWeight: 500 }}>
          {song?.artist_name || 'Zeus Beats Artist'}
          {durStr && <span style={{ color: 'rgba(255,255,255,0.35)', marginLeft: 10 }}>{durStr}</span>}
        </p>

        {/* Made with branding */}
        <p style={{ margin: '0 0 24px', fontSize: 12, color: `${CYAN}88`, fontWeight: 600 }}>
          ⚡ Made with Zeus Beats
        </p>

        {/* Play button + controls row */}
        <div style={{ display: 'flex', gap: 12, alignItems: 'center', marginBottom: 20 }}>
          <button
            onClick={togglePlay}
            style={{
              width: 56, height: 56, borderRadius: '50%',
              border: `2px solid ${CYAN}`,
              background: playing ? `${CYAN}22` : 'rgba(0,0,0,0.6)',
              color: CYAN, fontSize: 20, cursor: 'pointer',
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              backdropFilter: 'blur(8px)',
              boxShadow: `0 0 20px ${CYAN}44`,
              transition: 'all 0.2s', flexShrink: 0,
            }}
          >
            {playing ? '⏸' : '▶'}
          </button>

          {/* Share / copy link */}
          <button
            onClick={handleCopy}
            style={{
              flex: 1, padding: '14px 0', borderRadius: 10,
              border: `1px solid ${copied ? CYAN : 'rgba(255,255,255,0.2)'}`,
              background: copied ? `${CYAN}15` : 'rgba(0,0,0,0.5)',
              color: copied ? CYAN : 'rgba(255,255,255,0.75)',
              fontSize: 14, fontWeight: 600, cursor: 'pointer',
              backdropFilter: 'blur(8px)',
              transition: 'all 0.2s',
              boxShadow: copied ? `0 0 12px ${CYAN}33` : 'none',
            }}
          >
            {copied ? '✓ Link copied! Share it anywhere 🎵' : '🔗 Copy Share Link'}
          </button>
        </div>

        {/* Make Your Own CTA */}
        <button
          onClick={() => navigate('/register')}
          style={{
            width: '100%', padding: '18px 0', borderRadius: 14,
            background: `linear-gradient(90deg, ${CYAN}, ${PINK})`,
            color: '#000', fontWeight: 800, fontSize: 17,
            border: 'none', cursor: 'pointer',
            boxShadow: `0 0 32px ${CYAN}55`,
            letterSpacing: '0.01em',
          }}
        >
          ⚡ Make Your Own Free
        </button>
      </div>
    </div>
  );
}
