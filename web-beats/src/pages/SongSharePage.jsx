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

// Per-occasion tone. Unset (no occasion) renders exactly as before this
// feature existed — plain song title, no subheading, icon-only play button —
// so every song that predates this feature is visually untouched.
const OCCASION_COPY = {
  memorial: {
    heading: (name, title) => name || title,
    subheading: 'Forever loved, never forgotten',
    playLabel: 'Play Their Song',
  },
  birthday: {
    heading: (name, title) => (name ? `Happy Birthday ${name}!` : title),
    subheading: 'A song made just for you',
    playLabel: 'Play Your Song',
  },
  anniversary: {
    heading: (name, title) => (name ? `Happy Anniversary ${name}!` : title),
    subheading: "Here's to many more",
    playLabel: 'Play Your Song',
  },
  celebration: {
    heading: (name, title) => name || title,
    subheading: 'A moment worth celebrating',
    playLabel: 'Play the Song',
  },
};

const CAROUSEL_INTERVAL_MS = 4000;
const SWIPE_THRESHOLD_PX = 40;

// Auto-advancing, swipeable slideshow for 2-5 photos — a slow crossfade
// (not a hard cut) to match the page's calm tone. All photos are mounted at
// once, stacked and cross-faded via opacity, so there's no load-in flash
// when advancing. A single photo is rendered separately by the caller, in
// the same static framed style as before — this component is only for 2+.
function PhotoCarousel({ photos }) {
  const [index, setIndex] = useState(0);
  const touchStartRef = useRef(null);
  const wasSwipeRef = useRef(false);

  useEffect(() => {
    const id = setInterval(() => {
      setIndex((i) => (i + 1) % photos.length);
    }, CAROUSEL_INTERVAL_MS);
    return () => clearInterval(id);
  }, [index, photos.length]);

  const goTo = (i) => setIndex(((i % photos.length) + photos.length) % photos.length);
  const goNext = () => goTo(index + 1);
  const goPrev = () => goTo(index - 1);

  const handleTouchStart = (e) => {
    touchStartRef.current = e.touches[0].clientX;
    wasSwipeRef.current = false;
  };
  const handleTouchEnd = (e) => {
    if (touchStartRef.current == null) return;
    const delta = e.changedTouches[0].clientX - touchStartRef.current;
    touchStartRef.current = null;
    if (Math.abs(delta) >= SWIPE_THRESHOLD_PX) {
      wasSwipeRef.current = true;
      delta < 0 ? goNext() : goPrev();
    }
  };
  const handleClick = (e) => {
    // A swipe's trailing click shouldn't also count as a tap — consume it once.
    if (wasSwipeRef.current) { wasSwipeRef.current = false; return; }
    const frac = (e.clientX - e.currentTarget.getBoundingClientRect().left) / e.currentTarget.clientWidth;
    frac < 0.3 ? goPrev() : goNext();
  };

  return (
    <div>
      <div
        onTouchStart={handleTouchStart}
        onTouchEnd={handleTouchEnd}
        onClick={handleClick}
        style={{
          background: 'var(--sp-mat)',
          padding: 8,
          borderRadius: 10,
          boxShadow: '0 4px 16px var(--sp-shadow)',
          position: 'relative',
          aspectRatio: '1 / 1',
          cursor: 'pointer',
          touchAction: 'pan-y',
        }}
      >
        {photos.map((photo, i) => (
          <img
            key={photo.photo_id}
            src={photo.url}
            alt=""
            draggable={false}
            style={{
              position: 'absolute',
              inset: 8,
              width: 'calc(100% - 16px)',
              height: 'calc(100% - 16px)',
              objectFit: 'cover',
              borderRadius: 4,
              opacity: i === index ? 1 : 0,
              transition: 'opacity 1.4s ease',
              pointerEvents: 'none',
            }}
          />
        ))}
      </div>
      <div style={{ display: 'flex', justifyContent: 'center', gap: 8, marginTop: 12 }}>
        {photos.map((photo, i) => (
          <button
            key={photo.photo_id}
            onClick={() => goTo(i)}
            aria-label={`Show photo ${i + 1}`}
            style={{
              width: 7,
              height: 7,
              borderRadius: '50%',
              padding: 0,
              border: 'none',
              cursor: 'pointer',
              background: i === index ? 'var(--sp-accent)' : 'var(--sp-border)',
              transition: 'background 0.3s ease',
            }}
          />
        ))}
      </div>
    </div>
  );
}

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

  const occasionCopy = song?.occasion ? OCCASION_COPY[song.occasion] : null;
  const heading = occasionCopy ? occasionCopy.heading(song.occasion_name, song.title) : song?.title;
  const subheading = occasionCopy?.subheading;
  const playLabel = occasionCopy?.playLabel;

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

            <div style={{ fontFamily: SERIF, fontWeight: 500, fontSize: 24, lineHeight: 1.3, marginBottom: subheading ? 4 : 6 }}>
              {heading}
            </div>

            {subheading && (
              <div style={{ fontFamily: SERIF, fontStyle: 'italic', fontSize: 15, color: 'var(--sp-accent)', marginBottom: 6 }}>
                {subheading}
              </div>
            )}

            {(gLabel(song.genre_tag) || durStr) && (
              <div style={{ fontSize: 13, color: 'var(--sp-muted)', marginBottom: 26 }}>
                {[gLabel(song.genre_tag), durStr].filter(Boolean).join(' · ')}
              </div>
            )}

            {/* Waveform player */}
            {playLabel && (
              <div style={{ fontSize: 12, color: 'var(--sp-muted)', marginBottom: 10, letterSpacing: '0.02em' }}>
                {playLabel}
              </div>
            )}
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

            {/* Photos — 1 as a single framed image (unchanged), 2-5 as a
                slow-crossfading carousel, same "paper" treatment throughout */}
            {song.photos && song.photos.length === 1 && (
              <div style={{ background: 'var(--sp-mat)', padding: 8, borderRadius: 10, boxShadow: '0 4px 16px var(--sp-shadow)' }}>
                <img
                  src={song.photos[0].url}
                  alt=""
                  style={{ width: '100%', aspectRatio: '1 / 1', objectFit: 'cover', borderRadius: 4, display: 'block' }}
                />
              </div>
            )}
            {song.photos && song.photos.length > 1 && (
              <PhotoCarousel photos={song.photos} />
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
