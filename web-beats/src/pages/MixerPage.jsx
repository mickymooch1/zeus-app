import { useEffect, useRef, useState } from 'react';
import { BeatsDashboardHeader } from '../components/BeatsDashboardHeader';
import { useAuth } from '../contexts/AuthContext';
import { BACKEND_URL } from '../brand';

const CYAN = '#00f0ff';
const PINK = '#ff0099';
const RED  = '#ff2244';

const GENRE_BPM = {
  dnb: 174, jungle: 160, grime: 140, niche: 138, techno: 138,
  house: 128, techhouse: 125, ukgarage: 130, bassline: 138,
  afrobeats: 100, amapiano: 112, hiphop: 90, soul: 85,
  reggae: 75, rastadub: 70, blues: 80, jazz: 120,
  pop: 120, rock: 130, default: 120,
};

function estimateBpm(genreTag) {
  if (!genreTag) return GENRE_BPM.default;
  const key = genreTag.toLowerCase().replace(/[^a-z]/g, '');
  return GENRE_BPM[key] ?? GENRE_BPM.default;
}

function formatDuration(secs) {
  return `${String(Math.floor(secs / 60)).padStart(2, '0')}:${String(secs % 60).padStart(2, '0')}`;
}

const initialDeck = () => ({
  songId: '', volume: 0.8, bass: 0, mid: 0, treble: 0,
  bpm: null, tapTimes: [], playing: false,
});

export default function MixerPage() {
  const { token } = useAuth();
  const [songs, setSongs] = useState([]);
  const [loadingLib, setLoadingLib] = useState(true);
  const [deckA, setDeckA] = useState(initialDeck);
  const [deckB, setDeckB] = useState(initialDeck);
  const [crossfader, setCrossfader] = useState(0.5);

  // Recording state
  const [recording, setRecording]     = useState(false);
  const [recDuration, setRecDuration] = useState(0);
  const [lastBlob, setLastBlob]       = useState(null);
  const [saving, setSaving]           = useState(false);
  const [saveStatus, setSaveStatus]   = useState(null); // 'ok' | 'err' | null

  // Audio node refs
  const nodesA      = useRef({});
  const nodesB      = useRef({});
  const audioCtx    = useRef(null);
  const masterGain  = useRef(null); // all deck outputs feed here → ctx.destination + recordDest

  // Recording refs
  const recorderRef    = useRef(null);
  const recChunksRef   = useRef([]);
  const recTimerRef    = useRef(null);
  const recStartRef    = useRef(null);
  const recordDestRef  = useRef(null);
  const lastBlobUrlRef = useRef(null);

  // ── Audio context ─────────────────────────────────────────────────────────

  function getCtx() {
    if (!audioCtx.current) {
      const ctx = new (window.AudioContext || window.webkitAudioContext)();
      const mg  = ctx.createGain();
      mg.gain.value = 1;
      mg.connect(ctx.destination);
      audioCtx.current   = ctx;
      masterGain.current = mg;
    }
    if (audioCtx.current.state === 'suspended') audioCtx.current.resume();
    return audioCtx.current;
  }

  useEffect(() => {
    return () => {
      if (recorderRef.current && recorderRef.current.state !== 'inactive') {
        recorderRef.current.stop();
      }
      clearInterval(recTimerRef.current);
      ['A', 'B'].forEach(id => {
        const n = id === 'A' ? nodesA.current : nodesB.current;
        if (n.source) { try { n.source.disconnect(); n.source.stop(); } catch {} }
      });
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
                  title: variants.length > 1 ? `${lyric.title} (v${v.variant_id})` : lyric.title,
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

  // Build filter chain for a deck. Deck crossGain feeds masterGain (not ctx.destination directly).
  // Chain: [source] → bassFilter → midFilter → trebleFilter → volGain → crossGain → masterGain
  function buildChain(id, deck, cf) {
    const ctx = getCtx();
    const n   = id === 'A' ? nodesA.current : nodesB.current;

    if (n.crossGain) { try { n.crossGain.disconnect(); } catch {} }

    const bass = ctx.createBiquadFilter();
    bass.type = 'lowshelf'; bass.frequency.value = 100; bass.gain.value = deck.bass;

    const mid = ctx.createBiquadFilter();
    mid.type = 'peaking'; mid.frequency.value = 1000; mid.Q.value = 1; mid.gain.value = deck.mid;

    const treble = ctx.createBiquadFilter();
    treble.type = 'highshelf'; treble.frequency.value = 8000; treble.gain.value = deck.treble;

    const vol = ctx.createGain();
    vol.gain.value = deck.volume;

    const cross = ctx.createGain();
    cross.gain.value = id === 'A'
      ? Math.cos(cf * Math.PI / 2)
      : Math.cos((1 - cf) * Math.PI / 2);

    bass.connect(mid);
    mid.connect(treble);
    treble.connect(vol);
    vol.connect(cross);
    cross.connect(masterGain.current); // tap point for recorder

    n.bassFilter = bass; n.midFilter = mid; n.trebleFilter = treble;
    n.volGain = vol; n.crossGain = cross;
  }

  function startSource(id, offset = 0) {
    const ctx = getCtx();
    const n   = id === 'A' ? nodesA.current : nodesB.current;

    if (n.source) { try { n.source.disconnect(); n.source.stop(); } catch {} }

    const src = ctx.createBufferSource();
    src.buffer = n.buffer;
    src.loop   = true;
    src.connect(n.bassFilter);
    src.start(0, offset % src.buffer.duration);

    n.source    = src;
    n.startTime = ctx.currentTime - offset;
  }

  // ── Playback handlers ─────────────────────────────────────────────────────

  async function handleToggle(id) {
    const deck    = id === 'A' ? deckA    : deckB;
    const setDeck = id === 'A' ? setDeckA : setDeckB;
    const n       = id === 'A' ? nodesA.current : nodesB.current;

    if (deck.playing) {
      const ctx = getCtx();
      n.pauseAt = n.buffer ? (ctx.currentTime - n.startTime) % n.buffer.duration : 0;
      if (n.source) { try { n.source.disconnect(); n.source.stop(); } catch {} n.source = null; }
      setDeck(d => ({ ...d, playing: false }));
    } else if (n.buffer && n.bassFilter && n.pauseAt != null) {
      try {
        startSource(id, n.pauseAt);
        n.pauseAt = null;
        setDeck(d => ({ ...d, playing: true }));
      } catch (err) { console.error('Mixer resume error', err); }
    } else {
      if (!deck.songId) return;
      const song = songs.find(s => s.id === deck.songId);
      if (!song) return;
      try {
        const ctx = getCtx();
        if (n.loadedUrl !== song.url) {
          const res = await fetch(song.url);
          const ab  = await res.arrayBuffer();
          n.buffer    = await ctx.decodeAudioData(ab);
          n.loadedUrl = song.url;
        }
        n.pauseAt = null;
        buildChain(id, deck, crossfader);
        startSource(id, 0);
        setDeck(d => ({ ...d, playing: true }));
      } catch (err) { console.error('Mixer play error', err); }
    }
  }

  function handleSongSelect(id, songId) {
    const n       = id === 'A' ? nodesA.current : nodesB.current;
    const setDeck = id === 'A' ? setDeckA : setDeckB;

    if (n.source) { try { n.source.disconnect(); n.source.stop(); } catch {} n.source = null; }
    n.loadedUrl = null; n.pauseAt = null;

    const song = songs.find(s => s.id === songId);
    setDeck(d => ({ ...d, songId, playing: false, bpm: song ? estimateBpm(song.genre) : null }));
  }

  function handleVolume(id, value) {
    const n = id === 'A' ? nodesA.current : nodesB.current;
    if (n.volGain) n.volGain.gain.value = value;
    (id === 'A' ? setDeckA : setDeckB)(d => ({ ...d, volume: value }));
  }

  function handleEQ(id, param, value) {
    const n = id === 'A' ? nodesA.current : nodesB.current;
    const filterMap = { bass: 'bassFilter', mid: 'midFilter', treble: 'trebleFilter' };
    if (n[filterMap[param]]) n[filterMap[param]].gain.value = value;
    (id === 'A' ? setDeckA : setDeckB)(d => ({ ...d, [param]: value }));
  }

  function handleCrossfader(value) {
    setCrossfader(value);
    if (nodesA.current.crossGain) nodesA.current.crossGain.gain.value = Math.cos(value * Math.PI / 2);
    if (nodesB.current.crossGain) nodesB.current.crossGain.gain.value = Math.cos((1 - value) * Math.PI / 2);
  }

  function handleTap(id) {
    const now = Date.now();
    (id === 'A' ? setDeckA : setDeckB)(d => {
      const taps = [...d.tapTimes, now].filter(t => now - t < 4000);
      if (taps.length < 2) return { ...d, tapTimes: taps };
      const intervals = taps.slice(1).map((t, i) => t - taps[i]);
      const avg = intervals.reduce((a, b) => a + b, 0) / intervals.length;
      return { ...d, tapTimes: taps, bpm: Math.round(60000 / avg) };
    });
  }

  // ── Recording handlers ────────────────────────────────────────────────────

  function handleRecord() {
    if (recording) {
      recorderRef.current?.stop();
      clearInterval(recTimerRef.current);
      setRecording(false);
    } else {
      const ctx = getCtx();

      // Tap the master output into a MediaStream
      const dest = ctx.createMediaStreamDestination();
      masterGain.current.connect(dest);
      recordDestRef.current = dest;

      const recorder = new MediaRecorder(dest.stream);
      recChunksRef.current = [];
      setSaveStatus(null);
      setLastBlob(null);

      recorder.ondataavailable = e => { if (e.data.size > 0) recChunksRef.current.push(e.data); };
      recorder.onstop = () => {
        // Disconnect recording tap
        try { masterGain.current.disconnect(recordDestRef.current); } catch {}

        const blob = new Blob(recChunksRef.current, { type: 'audio/webm' });
        setLastBlob(blob);

        // Auto-download
        if (lastBlobUrlRef.current) URL.revokeObjectURL(lastBlobUrlRef.current);
        const url = URL.createObjectURL(blob);
        lastBlobUrlRef.current = url;
        const a = document.createElement('a');
        a.href = url;
        a.download = `zeus-mix-${Date.now()}.webm`;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
      };

      recorder.start();
      recorderRef.current = recorder;
      recStartRef.current = Date.now();
      setRecording(true);
      setRecDuration(0);

      recTimerRef.current = setInterval(() => {
        setRecDuration(Math.floor((Date.now() - recStartRef.current) / 1000));
      }, 1000);
    }
  }

  function handleDownload() {
    if (!lastBlob) return;
    if (lastBlobUrlRef.current) URL.revokeObjectURL(lastBlobUrlRef.current);
    const url = URL.createObjectURL(lastBlob);
    lastBlobUrlRef.current = url;
    const a = document.createElement('a');
    a.href = url;
    a.download = `zeus-mix-${Date.now()}.webm`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
  }

  async function handleSave() {
    if (!lastBlob || saving) return;
    setSaving(true);
    setSaveStatus(null);
    try {
      const fd = new FormData();
      fd.append('file', lastBlob, `zeus-mix-${Date.now()}.webm`);
      fd.append('title', `DJ Mix ${new Date().toLocaleString()}`);
      const r = await fetch(`${BACKEND_URL}/api/mixes/upload`, {
        method: 'POST',
        headers: { Authorization: `Bearer ${token}` },
        body: fd,
      });
      if (!r.ok) throw new Error(r.status);
      setSaveStatus('ok');
    } catch {
      setSaveStatus('err');
    } finally {
      setSaving(false);
    }
  }

  // ── Sub-components ────────────────────────────────────────────────────────

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

  function Deck({ id, deck, accent }) {
    return (
      <div style={{
        background: 'rgba(255,255,255,0.03)', border: `1px solid ${accent}33`,
        borderRadius: 12, padding: 20,
      }}>
        <div style={{
          fontSize: '0.82rem', fontWeight: 700, letterSpacing: '0.15em',
          color: accent, marginBottom: 14, textTransform: 'uppercase',
        }}>
          Deck {id}
        </div>

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

        <button
          onClick={() => handleToggle(id)}
          disabled={!deck.songId}
          style={{
            width: '100%', padding: 10, borderRadius: 8,
            border: `1px solid ${accent}`,
            background: deck.playing ? accent : 'transparent',
            color: deck.playing ? '#000' : accent,
            fontWeight: 700, fontSize: '1rem',
            cursor: deck.songId ? 'pointer' : 'not-allowed',
            letterSpacing: '0.05em', marginBottom: 16, transition: 'all 0.15s',
            opacity: deck.songId ? 1 : 0.4,
          }}
        >
          {deck.playing ? '⏸  PAUSE' : '▶  PLAY'}
        </button>

        <SliderRow label="VOL" min={0} max={1} step={0.01}
          value={deck.volume} accent={accent}
          display={`${Math.round(deck.volume * 100)}`}
          onChange={v => handleVolume(id, v)} />
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

  // ── Render ────────────────────────────────────────────────────────────────

  return (
    <div style={{ minHeight: '100vh', background: '#000', color: '#fff', fontFamily: "'Inter', sans-serif" }}>
      {/* Pulse keyframe for record button */}
      <style>{`
        @keyframes recPulse {
          0%, 100% { box-shadow: 0 0 0 0 rgba(255,34,68,0.7); }
          50%       { box-shadow: 0 0 0 10px rgba(255,34,68,0); }
        }
      `}</style>

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
          <p style={{ textAlign: 'center', color: '#555', marginBottom: 24 }}>Loading your library…</p>
        )}
        {!loadingLib && songs.length === 0 && (
          <p style={{ textAlign: 'center', color: '#555', marginBottom: 24 }}>
            No songs in your library yet. Generate some beats first!
          </p>
        )}

        {/* Decks + centre record column */}
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 120px 1fr', gap: 12, marginBottom: 20 }}>
          <Deck id="A" deck={deckA} accent={CYAN} />

          {/* Centre channel — record controls */}
          <div style={{
            display: 'flex', flexDirection: 'column', alignItems: 'center',
            justifyContent: 'center', gap: 14, padding: '8px 0',
          }}>
            {/* Record button */}
            <button
              onClick={handleRecord}
              title={recording ? 'Stop recording' : 'Start recording'}
              style={{
                width: 56, height: 56, borderRadius: '50%',
                border: `2px solid ${RED}`,
                background: recording ? RED : 'transparent',
                color: recording ? '#fff' : RED,
                fontSize: '1.4rem', cursor: 'pointer',
                display: 'flex', alignItems: 'center', justifyContent: 'center',
                animation: recording ? 'recPulse 1.2s ease-in-out infinite' : 'none',
                transition: 'background 0.15s',
              }}
            >
              {recording ? '⏹' : '⏺'}
            </button>

            {/* Timer */}
            <div style={{
              fontSize: '1rem', fontWeight: 700, letterSpacing: '0.1em',
              color: recording ? RED : '#333',
              fontVariantNumeric: 'tabular-nums',
            }}>
              {formatDuration(recDuration)}
            </div>

            <div style={{
              fontSize: '0.62rem', color: '#444', textTransform: 'uppercase',
              letterSpacing: '0.1em', textAlign: 'center',
            }}>
              {recording ? 'REC' : 'RECORD'}
            </div>

            {/* Post-recording actions */}
            {lastBlob && !recording && (
              <>
                <button
                  onClick={handleDownload}
                  title="Download mix"
                  style={{
                    width: '100%', padding: '5px 0', borderRadius: 5,
                    border: '1px solid #333', background: 'transparent',
                    color: '#888', fontSize: '0.7rem', cursor: 'pointer',
                    letterSpacing: '0.05em',
                  }}
                >
                  ⬇ DL
                </button>
                <button
                  onClick={handleSave}
                  disabled={saving || saveStatus === 'ok'}
                  title="Save to My Songs"
                  style={{
                    width: '100%', padding: '5px 0', borderRadius: 5,
                    border: `1px solid ${saveStatus === 'ok' ? '#00c853' : saveStatus === 'err' ? RED : CYAN + '66'}`,
                    background: 'transparent',
                    color: saveStatus === 'ok' ? '#00c853' : saveStatus === 'err' ? RED : CYAN,
                    fontSize: '0.65rem', cursor: saving || saveStatus === 'ok' ? 'default' : 'pointer',
                    letterSpacing: '0.04em', opacity: saving ? 0.6 : 1,
                  }}
                >
                  {saving ? '…' : saveStatus === 'ok' ? '✓ Saved' : saveStatus === 'err' ? '✕ Error' : '💾 Save'}
                </button>
              </>
            )}
          </div>

          <Deck id="B" deck={deckB} accent={PINK} />
        </div>

        {/* Crossfader */}
        <div style={{
          background: 'rgba(255,255,255,0.03)', border: '1px solid rgba(255,255,255,0.07)',
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
            {crossfader === 0.5 ? 'Center'
              : crossfader < 0.5 ? `${Math.round((0.5 - crossfader) * 200)}% → A`
              : `${Math.round((crossfader - 0.5) * 200)}% → B`}
          </div>
        </div>

      </main>
    </div>
  );
}
