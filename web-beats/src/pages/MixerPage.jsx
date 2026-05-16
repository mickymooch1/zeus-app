import { useEffect, useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { BeatsDashboardHeader } from '../components/BeatsDashboardHeader';
import { useAuth } from '../contexts/AuthContext';
import { BACKEND_URL } from '../brand';

const CYAN = '#00f0ff';
const PINK = '#ff0099';

const initialDeck = () => ({
  songId: '',
  volume: 0.8,
  bass: 0,
  mid: 0,
  treble: 0,
  bpm: null,
  tapTimes: [],
  playing: false,
});

export default function MixerPage() {
  const { t } = useTranslation();
  const { token } = useAuth();
  const [songs, setSongs] = useState([]);
  const [loadingLib, setLoadingLib] = useState(true);
  const [deckA, setDeckA] = useState(initialDeck);
  const [deckB, setDeckB] = useState(initialDeck);
  const [crossfader, setCrossfader] = useState(0.5);

  // Per-deck audio nodes (mutable, no re-render needed)
  const nodesA = useRef({});
  const nodesB = useRef({});
  const audioCtx = useRef(null);

  // ── Audio context ─────────────────────────────────────────────────────────

  function getCtx() {
    if (!audioCtx.current) {
      audioCtx.current = new (window.AudioContext || window.webkitAudioContext)();
    }
    if (audioCtx.current.state === 'suspended') audioCtx.current.resume();
    return audioCtx.current;
  }

  useEffect(() => {
    return () => {
      stopDeck('A');
      stopDeck('B');
      if (audioCtx.current) audioCtx.current.close().catch(() => {});
    };
  }, []); // eslint-disable-line

  // ── Library loading ───────────────────────────────────────────────────────

  useEffect(() => {
    if (!token) return;
    const headers = { Authorization: `Bearer ${token}` };

    fetch(`${BACKEND_URL}/api/lyrics`, { headers })
      .then(r => { if (!r.ok) throw new Error(r.status); return r.json(); })
      .then(async ({ lyrics = [] }) => {
        const groups = await Promise.all(
          lyrics.map(async (lyric) => {
            try {
              const vr = await fetch(`${BACKEND_URL}/api/lyrics/${lyric.id}/variants`, { headers });
              if (!vr.ok) return [];
              const { variants = [] } = await vr.json();
              return variants
                .filter(v => v.status === 'complete' && v.mp3_url)
                .map(v => ({
                  id: `${lyric.id}-${v.variant_id}`,
                  title: variants.length > 1
                    ? `${lyric.title} (v${v.variant_id})`
                    : lyric.title,
                  genre: v.genre_tag || '',
                  url: v.mp3_url,
                }));
            } catch { return []; }
          })
        );
        setSongs(groups.flat().sort((a, b) => b.id.localeCompare(a.id)));
      })
      .catch(() => {})
      .finally(() => setLoadingLib(false));
  }, [token]);

  // ── Audio helpers ─────────────────────────────────────────────────────────

  function stopDeck(id) {
    const n = id === 'A' ? nodesA.current : nodesB.current;
    if (n.source) { try { n.source.stop(); } catch {} n.source = null; }
  }

  function applyGains(id, cf) {
    const n = id === 'A' ? nodesA.current : nodesB.current;
    if (!n.crossGain) return;
    n.crossGain.gain.value = id === 'A'
      ? Math.cos(cf * Math.PI / 2)
      : Math.sin(cf * Math.PI / 2);
  }

  async function playDeck(id, deck) {
    const song = songs.find(s => s.id === deck.songId);
    if (!song) return;

    const ctx = getCtx();
    const n = id === 'A' ? nodesA.current : nodesB.current;
    stopDeck(id);

    // Fetch & decode only if song changed
    if (n.loadedUrl !== song.url) {
      const res = await fetch(song.url);
      const ab = await res.arrayBuffer();
      n.buffer = await ctx.decodeAudioData(ab);
      n.loadedUrl = song.url;
    }

    const bass = ctx.createBiquadFilter();
    bass.type = 'lowshelf';
    bass.frequency.value = 100;
    bass.gain.value = deck.bass;

    const mid = ctx.createBiquadFilter();
    mid.type = 'peaking';
    mid.frequency.value = 1000;
    mid.Q.value = 1;
    mid.gain.value = deck.mid;

    const treble = ctx.createBiquadFilter();
    treble.type = 'highshelf';
    treble.frequency.value = 8000;
    treble.gain.value = deck.treble;

    const vol = ctx.createGain();
    vol.gain.value = deck.volume;

    const cross = ctx.createGain();
    cross.gain.value = id === 'A'
      ? Math.cos(crossfader * Math.PI / 2)
      : Math.sin(crossfader * Math.PI / 2);

    const src = ctx.createBufferSource();
    src.buffer = n.buffer;
    src.loop = true;
    src.connect(bass);
    bass.connect(mid);
    mid.connect(treble);
    treble.connect(vol);
    vol.connect(cross);
    cross.connect(ctx.destination);
    src.start(0);

    n.source = src;
    n.bassFilter = bass;
    n.midFilter = mid;
    n.trebleFilter = treble;
    n.volGain = vol;
    n.crossGain = cross;
  }

  // ── Event handlers ────────────────────────────────────────────────────────

  async function handleToggle(id) {
    const deck = id === 'A' ? deckA : deckB;
    const setDeck = id === 'A' ? setDeckA : setDeckB;

    if (deck.playing) {
      stopDeck(id);
      setDeck(d => ({ ...d, playing: false }));
    } else {
      if (!deck.songId) return;
      try {
        await playDeck(id, deck);
        setDeck(d => ({ ...d, playing: true }));
      } catch (err) {
        console.error('Mixer play error', err);
      }
    }
  }

  function handleSongSelect(id, songId) {
    const deck = id === 'A' ? deckA : deckB;
    const setDeck = id === 'A' ? setDeckA : setDeckB;
    if (deck.playing) {
      stopDeck(id);
      const n = id === 'A' ? nodesA.current : nodesB.current;
      n.loadedUrl = null;
    }
    setDeck(d => ({ ...d, songId, playing: false }));
  }

  function handleVolume(id, value) {
    const setDeck = id === 'A' ? setDeckA : setDeckB;
    const n = id === 'A' ? nodesA.current : nodesB.current;
    setDeck(d => ({ ...d, volume: value }));
    if (n.volGain) n.volGain.gain.value = value;
  }

  function handleEQ(id, param, value) {
    const setDeck = id === 'A' ? setDeckA : setDeckB;
    const n = id === 'A' ? nodesA.current : nodesB.current;
    setDeck(d => ({ ...d, [param]: value }));
    const filterMap = { bass: 'bassFilter', mid: 'midFilter', treble: 'trebleFilter' };
    if (n[filterMap[param]]) n[filterMap[param]].gain.value = value;
  }

  function handleCrossfader(value) {
    setCrossfader(value);
    applyGains('A', value);
    applyGains('B', value);
  }

  function handleTap(id) {
    const setDeck = id === 'A' ? setDeckA : setDeckB;
    const now = Date.now();
    setDeck(d => {
      const taps = [...d.tapTimes, now].filter(t => now - t < 4000);
      if (taps.length < 2) return { ...d, tapTimes: taps };
      const intervals = taps.slice(1).map((t, i) => t - taps[i]);
      const avg = intervals.reduce((a, b) => a + b, 0) / intervals.length;
      return { ...d, tapTimes: taps, bpm: Math.round(60000 / avg) };
    });
  }

  // ── Render ────────────────────────────────────────────────────────────────

  function Deck({ id, deck, accent }) {
    return (
      <div style={{
        background: 'rgba(255,255,255,0.03)',
        border: `1px solid ${accent}33`,
        borderRadius: 12,
        padding: 20,
      }}>
        <div style={{
          fontSize: '0.82rem', fontWeight: 700, letterSpacing: '0.15em',
          color: accent, marginBottom: 14, textTransform: 'uppercase',
        }}>
          Deck {id}
        </div>

        {/* Song selector */}
        <select
          value={deck.songId}
          onChange={e => handleSongSelect(id, e.target.value)}
          style={{
            width: '100%', background: '#111', border: `1px solid ${accent}44`,
            borderRadius: 6, color: '#fff', padding: '8px 10px',
            fontSize: '0.83rem', marginBottom: 12, outline: 'none', cursor: 'pointer',
          }}
        >
          <option value="">— Select a song —</option>
          {songs.map(s => (
            <option key={s.id} value={s.id}>
              {s.genre ? `${s.title} · ${s.genre}` : s.title}
            </option>
          ))}
        </select>

        {/* Play/Pause */}
        <button
          onClick={() => handleToggle(id)}
          disabled={!deck.songId}
          style={{
            width: '100%', padding: 10, borderRadius: 8,
            border: `1px solid ${accent}`,
            background: deck.playing ? accent : 'transparent',
            color: deck.playing ? '#000' : accent,
            fontWeight: 700, fontSize: '1rem', cursor: deck.songId ? 'pointer' : 'not-allowed',
            letterSpacing: '0.05em', marginBottom: 16, transition: 'all 0.15s',
            opacity: deck.songId ? 1 : 0.4,
          }}
        >
          {deck.playing ? '⏸  PAUSE' : '▶  PLAY'}
        </button>

        {/* Volume */}
        <SliderRow label="VOL" min={0} max={1} step={0.01}
          value={deck.volume} accent={accent}
          display={`${Math.round(deck.volume * 100)}`}
          onChange={v => handleVolume(id, v)} />

        {/* EQ */}
        <SliderRow label="BASS" min={-15} max={15} step={1}
          value={deck.bass} accent={accent}
          display={`${deck.bass > 0 ? '+' : ''}${deck.bass}`}
          onChange={v => handleEQ(id, 'bass', v)} />
        <SliderRow label="MID" min={-15} max={15} step={1}
          value={deck.mid} accent={accent}
          display={`${deck.mid > 0 ? '+' : ''}${deck.mid}`}
          onChange={v => handleEQ(id, 'mid', v)} />
        <SliderRow label="TREBLE" min={-15} max={15} step={1}
          value={deck.treble} accent={accent}
          display={`${deck.treble > 0 ? '+' : ''}${deck.treble}`}
          onChange={v => handleEQ(id, 'treble', v)} />

        {/* BPM + Tap */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginTop: 14 }}>
          <div>
            <div style={{ fontSize: '1.5rem', fontWeight: 700, color: accent, minWidth: 56 }}>
              {deck.bpm ?? '--'}
            </div>
            <div style={{ fontSize: '0.68rem', color: '#555', letterSpacing: '0.1em' }}>BPM</div>
          </div>
          <button
            onClick={() => handleTap(id)}
            style={{
              padding: '6px 14px', borderRadius: 5,
              border: `1px solid ${accent}55`, background: 'transparent',
              color: accent, fontSize: '0.75rem', cursor: 'pointer', letterSpacing: '0.06em',
            }}
          >
            TAP
          </button>
        </div>
      </div>
    );
  }

  function SliderRow({ label, min, max, step, value, accent, display, onChange }) {
    return (
      <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 9 }}>
        <span style={{ width: 48, fontSize: '0.72rem', color: '#666', flexShrink: 0 }}>{label}</span>
        <input
          type="range" min={min} max={max} step={step} value={value}
          style={{ flex: 1, accentColor: accent, cursor: 'pointer' }}
          onChange={e => onChange(step < 1 ? parseFloat(e.target.value) : parseInt(e.target.value))}
        />
        <span style={{ width: 32, textAlign: 'right', fontSize: '0.72rem', color: '#555' }}>{display}</span>
      </div>
    );
  }

  return (
    <div style={{ minHeight: '100vh', background: '#000', color: '#fff', fontFamily: "'Inter', sans-serif" }}>
      <BeatsDashboardHeader />
      <main style={{ padding: '28px 16px 60px', maxWidth: 1080, margin: '0 auto' }}>

        <h1 style={{
          textAlign: 'center', fontSize: '1.6rem', fontWeight: 700,
          letterSpacing: '0.12em', marginBottom: 28,
          background: `linear-gradient(90deg, ${CYAN}, ${PINK})`,
          WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent',
        }}>
          ⚡ DJ MIXER
        </h1>

        {loadingLib && (
          <p style={{ textAlign: 'center', color: '#555', marginBottom: 24 }}>
            Loading your library…
          </p>
        )}
        {!loadingLib && songs.length === 0 && (
          <p style={{ textAlign: 'center', color: '#555', marginBottom: 24 }}>
            No songs in your library yet. Generate some beats first!
          </p>
        )}

        {/* Decks */}
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16, marginBottom: 20 }}>
          <Deck id="A" deck={deckA} accent={CYAN} />
          <Deck id="B" deck={deckB} accent={PINK} />
        </div>

        {/* Crossfader */}
        <div style={{
          background: 'rgba(255,255,255,0.03)',
          border: '1px solid rgba(255,255,255,0.07)',
          borderRadius: 12, padding: '18px 24px',
        }}>
          <div style={{
            textAlign: 'center', fontSize: '0.72rem', color: '#555',
            letterSpacing: '0.14em', textTransform: 'uppercase', marginBottom: 12,
          }}>
            Crossfader
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 14 }}>
            <span style={{ fontWeight: 700, color: CYAN, width: 18, fontSize: '0.85rem' }}>A</span>
            <input
              type="range" min="0" max="1" step="0.01" value={crossfader}
              style={{
                flex: 1, cursor: 'pointer',
                accentColor: crossfader < 0.5 ? CYAN : crossfader > 0.5 ? PINK : '#888',
              }}
              onChange={e => handleCrossfader(parseFloat(e.target.value))}
            />
            <span style={{ fontWeight: 700, color: PINK, width: 18, fontSize: '0.85rem', textAlign: 'right' }}>B</span>
          </div>
          <div style={{ textAlign: 'center', fontSize: '0.7rem', color: '#444', marginTop: 8 }}>
            {crossfader === 0.5 ? 'Center' : crossfader < 0.5
              ? `${Math.round((0.5 - crossfader) * 200)}% → A`
              : `${Math.round((crossfader - 0.5) * 200)}% → B`}
          </div>
        </div>

      </main>
    </div>
  );
}
