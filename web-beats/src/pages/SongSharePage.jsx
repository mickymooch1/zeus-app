import { useEffect, useRef, useState } from 'react';
import { useParams, Link } from 'react-router-dom';
import WaveSurfer from 'wavesurfer.js';
import { BRAND, BACKEND_URL } from '../brand';

const GENRE_LABEL = {
  hiphop:'Hip-hop', lofi:'Lo-Fi', edm:'EDM', irishjig:'Irish Jig', irishfolk:'Irish Folk',
  rnb:'R&B', bluessoul:'Blues Soul', drumandbass:'D&B', grime:'Grime', ukgarage:'UK Garage',
  jungle:'Jungle', bassline:'Bassline', house:'House', loversrock:'Lovers Rock', ukdrill:'UK Drill',
  kpop:'K-Pop', deepsoulblues:'Deep Soul Blues', ukstreetsoul:'UK Street Soul', technhouse:'Tech House',
  driftphonk:'Drift Phonk', jerseyclub:'Jersey Club', afroswing:'Afroswing', rastadub:'Rasta Dub', dancehall:'Dancehall',
  deeprotbassline:'Deeprot Bassline', jazz:'Jazz', electronicfunk:'Electronic Funk',
  syntheticpop:'Synthetic Pop', ragga:'Ragga', dubstep:'Dubstep',
  bhangra:'Bhangra', rockney:'Rockney', metal:'Metal',
  trap:'Trap', eastcoasthiphop:'East Coast Hip-Hop', poprap:'Pop Rap',
  synthwave:'Synthwave', gospel:'Gospel', trapsoul:'Trap Soul',
  meditation:'Meditation', christmas:'Christmas', corridos:'Corridos',
  healingfrequency:'Healing Frequency', swing:'Swing', vocaljazz:'Vocal Jazz', scat:'Scat Jazz', opera:'Opera',
  traditionalpop:'Traditional Pop', rocknroll:"Rock 'n' Roll",
  southemsoul:'Southern Soul', countryamericana:'Country Americana',
};
const gLabel = (g) => GENRE_LABEL[g] || (g ? g.charAt(0).toUpperCase() + g.slice(1) : '');

const PAGE_CSS = `
@keyframes fadeInUp {
  from { opacity: 0; transform: translateY(10px); }
  to   { opacity: 1; transform: translateY(0); }
}
.share-card { animation: fadeInUp 0.4s ease both; }
`;

export default function SongSharePage() {
  const { variantId } = useParams();
  const waveRef = useRef(null);
  const wsRef   = useRef(null);

  const [song, setSong]       = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError]     = useState('');
  const [playing, setPlaying] = useState(false);
  const [wsReady, setWsReady] = useState(false);
  const [copied, setCopied]   = useState(false);

  useEffect(() => {
    fetch(`${BACKEND_URL}/api/songs/variants/${variantId}/public`)
      .then((r) => {
        if (!r.ok) throw new Error('Song not found');
        return r.json();
      })
      .then((d) => { setSong(d); setLoading(false); })
      .catch((e) => { setError(e.message); setLoading(false); });
  }, [variantId]);

  useEffect(() => {
    if (!song?.mp3_url || !waveRef.current) return;
    const ws = WaveSurfer.create({
      container:     waveRef.current,
      url:           song.mp3_url,
      waveColor:     '#2a2a40',
      progressColor: '#a78bfa',
      height:        48,
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
    return () => { ws.destroy(); wsRef.current = null; };
  }, [song?.mp3_url]);

  const handlePlay = () => {
    if (!wsRef.current || !wsReady) return;
    playing ? wsRef.current.pause() : wsRef.current.play();
  };

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(window.location.href);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch (_) {}
  };

  const dur = song?.duration_seconds;
  const durStr = dur ? `${Math.floor(dur / 60)}:${String(dur % 60).padStart(2, '0')}` : '';

  return (
    <>
      <style>{PAGE_CSS}</style>
      <div style={{
        background: '#0b0b14',
        minHeight: '100vh',
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        padding: '40px 24px',
        color: '#f0eeff',
        fontFamily: 'inherit',
      }}>
        {/* Branding */}
        <Link to="/" style={{ textDecoration: 'none', marginBottom: 40, display: 'flex', alignItems: 'center', gap: 8 }}>
          <span style={{ fontSize: 22 }}>⚡</span>
          <span style={{ fontSize: 16, fontWeight: 700, color: '#a78bfa', letterSpacing: '-0.3px' }}>{BRAND.name}</span>
        </Link>

        {loading && (
          <div style={{ color: '#444', fontSize: 15 }}>Loading…</div>
        )}

        {error && (
          <div style={{ color: '#f87171', fontSize: 15 }}>{error}</div>
        )}

        {song && (
          <div className="share-card" style={{
            background: '#12121e',
            border: '1px solid rgba(255,255,255,0.07)',
            borderRadius: 16,
            overflow: 'hidden',
            width: '100%',
            maxWidth: 400,
          }}>
            {/* Cover art */}
            {song.image_url ? (
              <img
                src={song.image_url}
                alt={song.title}
                style={{ width: '100%', aspectRatio: '1 / 1', objectFit: 'cover', display: 'block' }}
              />
            ) : (
              <div style={{
                width: '100%',
                aspectRatio: '1 / 1',
                background: 'linear-gradient(135deg, #1a1040 0%, #0e0e22 100%)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
              }}>
                <span style={{ fontSize: 72, opacity: 0.15 }}>♫</span>
              </div>
            )}

            {/* Body */}
            <div style={{ padding: '20px 22px 24px' }}>
              <div style={{ fontWeight: 700, fontSize: 18, color: '#e2d9f3', marginBottom: 10, lineHeight: 1.3 }}>
                {song.title}
              </div>

              <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 18 }}>
                <span style={{
                  background: 'rgba(167,139,250,0.15)',
                  color: '#c4b5fd',
                  border: '1px solid rgba(167,139,250,0.3)',
                  borderRadius: 20,
                  padding: '2px 10px',
                  fontSize: 11,
                  fontWeight: 500,
                }}>{gLabel(song.genre_tag)}</span>
                {durStr && <span style={{ color: '#444', fontSize: 12 }}>{durStr}</span>}
              </div>

              {/* Waveform player */}
              <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 18 }}>
                <button
                  onClick={handlePlay}
                  disabled={!wsReady}
                  style={{
                    width: 40,
                    height: 40,
                    borderRadius: '50%',
                    border: 'none',
                    background: wsReady ? '#7c3aed' : 'rgba(167,139,250,0.1)',
                    color: '#fff',
                    fontSize: 13,
                    cursor: wsReady ? 'pointer' : 'default',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    flexShrink: 0,
                    opacity: wsReady ? 1 : 0.4,
                    transition: 'background 0.2s, opacity 0.2s',
                  }}
                >
                  {playing ? '⏸' : '▶'}
                </button>
                <div
                  ref={waveRef}
                  style={{ flex: 1, opacity: wsReady ? 1 : 0.15, transition: 'opacity 0.4s', minWidth: 0 }}
                />
              </div>

              {/* Action buttons */}
              <div style={{ display: 'flex', gap: 8 }}>
                <a
                  href={song.mp3_url}
                  download={`${(song.title || 'song').replace(/[^a-z0-9]/gi, '-').toLowerCase()}.mp3`}
                  style={{
                    flex: 1,
                    padding: '10px 0',
                    borderRadius: 8,
                    border: '1px solid rgba(255,255,255,0.1)',
                    background: 'transparent',
                    color: '#888',
                    fontSize: 13,
                    textAlign: 'center',
                    textDecoration: 'none',
                    display: 'block',
                  }}
                >
                  ↓ Download
                </a>
                <button
                  onClick={handleCopy}
                  style={{
                    flex: 1,
                    padding: '10px 0',
                    borderRadius: 8,
                    border: '1px solid rgba(255,255,255,0.1)',
                    background: 'transparent',
                    color: copied ? '#a78bfa' : '#888',
                    fontSize: 13,
                    cursor: 'pointer',
                    transition: 'color 0.2s',
                  }}
                >
                  {copied ? '✓ Link copied!' : '↗ Copy link'}
                </button>
              </div>
            </div>
          </div>
        )}

        {/* CTA */}
        <p style={{ marginTop: 36, fontSize: 13, color: '#333', textAlign: 'center' }}>
          AI-generated with{' '}
          <Link to="/" style={{ color: '#7c3aed', textDecoration: 'none', fontWeight: 600 }}>
            {BRAND.name}
          </Link>
          {' '}· Make your own →
        </p>
      </div>
    </>
  );
}
