import { useEffect, useRef, useState } from 'react';
import { useParams } from 'react-router-dom';
import WaveSurfer from 'wavesurfer.js';
import { BACKEND_URL } from '../brand';

const gLabel = (g) => (g ? g.charAt(0).toUpperCase() + g.slice(1) : '');

// Deliberately its own visual identity — warm, quiet, paper-like — not the
// main app's dark neon UI. Suits a memorial page as comfortably as a gift or
// celebration. Respects prefers-color-scheme so it still looks considered in
// dark mode, but the *designed* default is the warm light theme, distinct
// from the main product, which is dark-only.
const PAGE_CSS = `
@keyframes shareFadeInUp {
  from { opacity: 0; transform: translateY(10px); }
  to   { opacity: 1; transform: translateY(0); }
}
.zb-share-page {
  --sp-bg: #f7f2ea;
  --sp-text: #2b2622;
  --sp-muted: #8a7f74;
  --sp-accent: #a8593f;
  --sp-mat: #fffdf9;
  --sp-border: rgba(43,38,34,0.12);
  --sp-shadow: rgba(43,38,34,0.16);
}
@media (prefers-color-scheme: dark) {
  .zb-share-page {
    --sp-bg: #211f1c;
    --sp-text: #ede7de;
    --sp-muted: #a89a8c;
    --sp-accent: #d98a6f;
    --sp-mat: #2b2724;
    --sp-border: rgba(237,231,222,0.14);
    --sp-shadow: rgba(0,0,0,0.45);
  }
}
.zb-share-content { animation: shareFadeInUp 0.4s ease both; }
.zb-share-btn {
  background: transparent;
  border: 1px solid var(--sp-border);
  color: var(--sp-text);
  cursor: pointer;
  transition: border-color 0.2s, color 0.2s;
}
.zb-share-btn:hover { border-color: var(--sp-accent); color: var(--sp-accent); }
`;

const SERIF = "Georgia, 'Iowan Old Style', 'Palatino Linotype', 'Book Antiqua', serif";
const SANS = "-apple-system, BlinkMacSystemFont, 'Segoe UI', Helvetica, Arial, sans-serif";

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

  // This page must never be indexed — it can carry personal photos (memorial
  // pages especially) and is only ever meant to be reached via a direct
  // link/QR, not discovered through search. A client-rendered SPA route has
  // no server-side <head>, so the tag is set here; Google's crawler does
  // execute JS and respects a noindex tag present in the rendered DOM.
  useEffect(() => {
    let tag = document.querySelector('meta[name="robots"]');
    const existed = !!tag;
    const previousContent = tag?.getAttribute('content') ?? null;
    if (!tag) {
      tag = document.createElement('meta');
      tag.setAttribute('name', 'robots');
      document.head.appendChild(tag);
    }
    tag.setAttribute('content', 'noindex, nofollow');
    return () => {
      if (!existed) {
        tag.remove();
      } else if (previousContent !== null) {
        tag.setAttribute('content', previousContent);
      }
    };
  }, []);

  useEffect(() => {
    if (!song?.mp3_url || !waveRef.current) return;
    // wavesurfer needs literal colors, not CSS variables — read the system
    // theme once at mount so the waveform matches whichever palette (light
    // or dark) the rest of the page renders in.
    const isDark = window.matchMedia?.('(prefers-color-scheme: dark)').matches;
    const ws = WaveSurfer.create({
      container:     waveRef.current,
      url:           song.mp3_url,
      waveColor:     isDark ? 'rgba(237,231,222,0.25)' : 'rgba(43,38,34,0.18)',
      progressColor: isDark ? '#d98a6f' : '#a8593f',
      height:        44,
      barWidth:      2,
      barGap:        2,
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
    } catch {
      // clipboard access denied/unavailable — button just won't confirm, non-fatal
    }
  };

  const dur = song?.duration_seconds;
  const durStr = dur ? `${Math.floor(dur / 60)}:${String(dur % 60).padStart(2, '0')}` : '';

  return (
    <>
      <style>{PAGE_CSS}</style>
      <div className="zb-share-page" style={{
        background: 'var(--sp-bg)',
        minHeight: '100vh',
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        padding: '48px 20px 28px',
        color: 'var(--sp-text)',
        fontFamily: SANS,
      }}>
        {loading && (
          <div style={{ color: 'var(--sp-muted)', fontSize: 15 }}>Loading…</div>
        )}

        {error && (
          <div style={{ color: 'var(--sp-muted)', fontSize: 15 }}>{error}</div>
        )}

        {song && (
          <div className="zb-share-content" style={{ width: '100%', maxWidth: 380, textAlign: 'center' }}>
            {/* Cover art, presented like a printed photo — a paper "mat" around
                it rather than an edge-to-edge UI thumbnail */}
            <div style={{
              background: 'var(--sp-mat)',
              padding: 12,
              borderRadius: 14,
              boxShadow: '0 8px 28px var(--sp-shadow)',
              marginBottom: 22,
            }}>
              {song.image_url ? (
                <img
                  src={song.image_url}
                  alt={song.title}
                  style={{ width: '100%', aspectRatio: '1 / 1', objectFit: 'cover', display: 'block', borderRadius: 6 }}
                />
              ) : (
                <div style={{
                  width: '100%',
                  aspectRatio: '1 / 1',
                  borderRadius: 6,
                  background: 'var(--sp-bg)',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                }}>
                  <span style={{ fontSize: 56, opacity: 0.2 }}>♫</span>
                </div>
              )}
            </div>

            <div style={{ fontFamily: SERIF, fontWeight: 500, fontSize: 24, lineHeight: 1.3, marginBottom: 6 }}>
              {song.title}
            </div>

            {(gLabel(song.genre_tag) || durStr) && (
              <div style={{ fontSize: 13, color: 'var(--sp-muted)', marginBottom: 26 }}>
                {[gLabel(song.genre_tag), durStr].filter(Boolean).join(' · ')}
              </div>
            )}

            {/* Waveform player */}
            <div style={{ display: 'flex', alignItems: 'center', gap: 14, marginBottom: 22 }}>
              <button
                onClick={handlePlay}
                disabled={!wsReady}
                aria-label={playing ? 'Pause' : 'Play'}
                style={{
                  width: 42,
                  height: 42,
                  borderRadius: '50%',
                  border: '1px solid var(--sp-accent)',
                  background: 'transparent',
                  color: 'var(--sp-accent)',
                  fontSize: 14,
                  cursor: wsReady ? 'pointer' : 'default',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  flexShrink: 0,
                  opacity: wsReady ? 1 : 0.35,
                  transition: 'opacity 0.3s',
                }}
              >
                {playing ? '⏸' : '▶'}
              </button>
              <div
                ref={waveRef}
                style={{ flex: 1, opacity: wsReady ? 1 : 0.2, transition: 'opacity 0.4s', minWidth: 0 }}
              />
            </div>

            {/* Actions */}
            <div style={{ display: 'flex', gap: 10, marginBottom: song.photos?.length ? 26 : 4 }}>
              <a
                href={song.mp3_url}
                download={`${(song.title || 'song').replace(/[^a-z0-9]/gi, '-').toLowerCase()}.mp3`}
                className="zb-share-btn"
                style={{
                  flex: 1,
                  padding: '11px 0',
                  borderRadius: 9,
                  fontSize: 13,
                  textAlign: 'center',
                  textDecoration: 'none',
                  display: 'block',
                }}
              >
                Download
              </a>
              <button onClick={handleCopy} className="zb-share-btn" style={{ flex: 1, padding: '11px 0', borderRadius: 9, fontSize: 13 }}>
                {copied ? 'Link copied' : 'Copy link'}
              </button>
            </div>

            {/* Photos — 1 as a single framed image, 2-5 as a responsive grid,
                same "paper" treatment as the cover art above */}
            {song.photos && song.photos.length > 0 && (
              <div
                style={{
                  display: 'grid',
                  gridTemplateColumns: song.photos.length === 1 ? '1fr' : 'repeat(2, 1fr)',
                  gap: 10,
                }}
              >
                {song.photos.map((photo) => (
                  <div key={photo.photo_id} style={{ background: 'var(--sp-mat)', padding: 8, borderRadius: 10, boxShadow: '0 4px 16px var(--sp-shadow)' }}>
                    <img
                      src={photo.url}
                      alt=""
                      style={{ width: '100%', aspectRatio: '1 / 1', objectFit: 'cover', borderRadius: 4, display: 'block' }}
                    />
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {/* Minimal, quiet credit — no logo, no pitch, no app navigation */}
        <p style={{ marginTop: 44, fontSize: 12, color: 'var(--sp-muted)', textAlign: 'center' }}>
          Made with{' '}
          <a href="/" style={{ color: 'var(--sp-muted)', textDecoration: 'underline' }}>
            Zeus Beats
          </a>
        </p>
      </div>
    </>
  );
}
