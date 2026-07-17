import { useState, useEffect, useRef } from 'react';
import { createPortal } from 'react-dom';
import { BACKEND_URL } from '../brand';
import { useAuth } from '../contexts/AuthContext';

// Session cache so reopening the same song's lyrics is instant and re-fetch-free.
const lyricsCache = new Map();

const INSTRUMENTAL_SENTINEL = '[Instrumental]';

/**
 * Parse Suno lyrics_text into ordered display blocks.
 *   - a line that is ONLY a [tag]  -> { type: 'header', text }  (e.g. "Verse 1")
 *   - any other non-empty line     -> { type: 'line',   text }
 * Blank lines become spacing between blocks, not blocks of their own.
 * Parenthetical ad-libs like "(oohs and ahs)" are ordinary lines, left intact.
 * Exported for unit testing without React.
 */
export function parseLyrics(text) {
  if (!text) return [];
  const blocks = [];
  for (const raw of text.split('\n')) {
    const line = raw.trim();
    if (!line) continue;
    const header = line.match(/^\[([^\]]+)\]$/);
    if (header) {
      blocks.push({ type: 'header', text: header[1].trim() });
    } else {
      blocks.push({ type: 'line', text: line });
    }
  }
  return blocks;
}

/** True when the stored lyrics mean "no lyrics — instrumental track". */
export function isInstrumental(text) {
  const t = (text || '').trim();
  return t === '' || t === INSTRUMENTAL_SENTINEL;
}

export default function LyricsModal({ lyricId, title, onClose }) {
  const { token } = useAuth();
  const [state, setState] = useState(
    lyricId != null && lyricsCache.has(lyricId)
      ? { status: 'loaded', text: lyricsCache.get(lyricId) }
      : { status: 'loading', text: '' },
  );
  const closeRef = useRef(null);

  // Fetch lyrics for this lyricId (unless already cached).
  useEffect(() => {
    if (lyricId == null) { setState({ status: 'error', text: '' }); return; }
    if (lyricsCache.has(lyricId)) {
      setState({ status: 'loaded', text: lyricsCache.get(lyricId) });
      return;
    }
    let cancelled = false;
    setState({ status: 'loading', text: '' });
    (async () => {
      try {
        const r = await fetch(`${BACKEND_URL}/api/lyrics/${lyricId}`, {
          headers: { Authorization: `Bearer ${token}` },
        });
        if (!r.ok) throw new Error(`status ${r.status}`);
        const data = await r.json();
        const text = data.lyrics_text ?? '';
        lyricsCache.set(lyricId, text);
        if (!cancelled) setState({ status: 'loaded', text });
      } catch (_) {
        if (!cancelled) setState({ status: 'error', text: '' });
      }
    })();
    return () => { cancelled = true; };
  }, [lyricId, token]);

  // Escape to close; focus the close button on open.
  useEffect(() => {
    const onKey = (e) => { if (e.key === 'Escape') onClose(); };
    window.addEventListener('keydown', onKey);
    closeRef.current?.focus();
    return () => window.removeEventListener('keydown', onKey);
  }, [onClose]);

  const blocks = state.status === 'loaded' ? parseLyrics(state.text) : [];
  const instrumental = state.status === 'loaded' && isInstrumental(state.text);

  // Portal to <body>: rendered from inside a song card, a transformed ancestor
  // (.song-card-anim) would otherwise trap position:fixed to the card's box.
  return createPortal(
    <div
      onClick={onClose}
      style={{
        position: 'fixed', inset: 0, zIndex: 10000,
        background: 'rgba(6,6,12,0.92)', backdropFilter: 'blur(6px)',
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        padding: '0',
      }}
    >
      <div
        onClick={(e) => e.stopPropagation()}
        role="dialog"
        aria-label="Lyrics"
        style={{
          position: 'relative',
          width: '100%', maxWidth: 560,
          height: '100%', maxHeight: '80vh',
          display: 'flex', flexDirection: 'column',
          background: '#0a0a14',
          borderTop: '1px solid rgba(0,240,255,0.18)',
          border: '1px solid rgba(0,240,255,0.14)',
          borderRadius: 'clamp(0px, 3vw, 16px)',
          boxShadow: '0 -4px 60px rgba(0,240,255,0.10)',
          overflow: 'hidden',
        }}
      >
        {/* Header row: title + close */}
        <div style={{
          display: 'flex', alignItems: 'center', justifyContent: 'space-between',
          padding: '14px 16px', borderBottom: '1px solid rgba(255,255,255,0.06)',
          flexShrink: 0,
        }}>
          <div style={{
            fontSize: 14, fontWeight: 700, color: '#e2e8f0',
            overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
            paddingRight: 12,
          }}>
            📜 {title || 'Lyrics'}
          </div>
          <button
            ref={closeRef}
            onClick={onClose}
            aria-label="Close lyrics"
            style={{
              flexShrink: 0, width: 44, height: 44, borderRadius: 8,
              background: 'rgba(255,255,255,0.05)', border: '1px solid rgba(255,255,255,0.12)',
              color: '#94a3b8', fontSize: 20, cursor: 'pointer',
              display: 'flex', alignItems: 'center', justifyContent: 'center',
            }}
          >✕</button>
        </div>

        {/* Body */}
        <div style={{
          flex: 1, overflowY: 'auto', padding: '20px 22px 32px',
          WebkitOverflowScrolling: 'touch',
        }}>
          {state.status === 'loading' && (
            <div style={{ color: '#64748b', textAlign: 'center', marginTop: 40 }}>
              Loading lyrics…
            </div>
          )}

          {state.status === 'error' && (
            <div style={{ color: '#64748b', textAlign: 'center', marginTop: 40 }}>
              Couldn't load lyrics.
            </div>
          )}

          {instrumental && (
            <div style={{
              color: '#c084fc', textAlign: 'center', marginTop: 60,
              fontSize: 20, fontWeight: 600, letterSpacing: '0.02em',
            }}>
              🎵 Instrumental
            </div>
          )}

          {state.status === 'loaded' && !instrumental && blocks.map((b, i) =>
            b.type === 'header' ? (
              <div key={i} style={{
                fontSize: 12, fontWeight: 700, letterSpacing: '0.12em',
                textTransform: 'uppercase', color: '#c084fc',
                marginTop: i === 0 ? 0 : 26, marginBottom: 8,
              }}>
                {b.text}
              </div>
            ) : (
              <div key={i} style={{
                fontSize: 16, lineHeight: 1.7, color: '#e2e8f0',
              }}>
                {b.text}
              </div>
            ),
          )}
        </div>
      </div>
    </div>,
    document.body,
  );
}
