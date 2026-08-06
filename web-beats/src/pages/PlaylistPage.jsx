import { useState, useEffect, useCallback } from 'react';
import { useAuth } from '../contexts/AuthContext';
import { useNowPlaying } from '../contexts/NowPlayingContext';
import { audioManager } from '../utils/audioManager';
import { BeatsDashboardHeader } from '../components/BeatsDashboardHeader';
import {
  DndContext, closestCenter, PointerSensor, KeyboardSensor, useSensor, useSensors,
} from '@dnd-kit/core';
import {
  SortableContext, useSortable, verticalListSortingStrategy, arrayMove,
  sortableKeyboardCoordinates,
} from '@dnd-kit/sortable';
import { CSS } from '@dnd-kit/utilities';

const BACKEND_URL = import.meta.env.VITE_BACKEND_URL || '';

const GENRE_LABEL = {
  hiphop:'Hip-hop', lofi:'Lo-Fi', edm:'EDM', irishjig:'Irish Jig', irishfolk:'Irish Folk',
  rnb:'R&B', bluessoul:'Blues Soul', drumandbass:'D&B', grime:'Grime', ukgarage:'UK Garage',
  jungle:'Jungle', bassline:'Bassline', house:'House', loversrock:'Lovers Rock', ukdrill:'UK Drill',
  kpop:'K-Pop', deepsoulblues:'Deep Soul Blues', ukstreetsoul:'UK Street Soul', technhouse:'Tech House',
  driftphonk:'Drift Phonk', jerseyclub:'Jersey Club', afroswing:'Afroswing', rastadub:'Rasta Dub', dancehall:'Dancehall',
  deeprotbassline:'Deeprot Bassline', jazz:'Jazz', electronicfunk:'Electronic Funk',
  syntheticpop:'Synthetic Pop', ragga:'Ragga', dubstep:'Dubstep',
  bhangra:'Bhangra', rockney:'Rockney', metal:'Metal', rootsreggae:'Roots Reggae',
  trap:'Trap', eastcoasthiphop:'East Coast Hip-Hop', poprap:'Pop Rap',
  synthwave:'Synthwave', gospel:'Gospel', trapsoul:'Trap Soul',
  meditation:'Meditation', christmas:'Christmas', corridos:'Corridos',
  healingfrequency:'Healing Frequency', swing:'Swing', vocaljazz:'Vocal Jazz', scat:'Scat Jazz', opera:'Opera',
  traditionalpop:'Traditional Pop', rocknroll:"Rock 'n' Roll",
  southemsoul:'Southern Soul', countryamericana:'Country Americana',
};
function gLabel(g) {
  if (!g) return '';
  if (g.includes('__')) { const [a,b]=g.split('__'); return `${GENRE_LABEL[a]||a} × ${GENRE_LABEL[b]||b}`; }
  return GENRE_LABEL[g] || g.charAt(0).toUpperCase()+g.slice(1);
}

const AI_CHIPS = [
  'Sunday morning chill', 'Hype workout', 'Late night drive',
  'Friday night out', 'Focus mode', 'Heartbreak vibes',
];

// ── styles ────────────────────────────────────────────────────────────────────
const S = {
  page:    { minHeight: '100vh', background: '#0b0b14', color: '#e2e8f0', paddingBottom: 100 },
  wrap:    { maxWidth: 860, margin: '0 auto', padding: '32px 20px' },
  heading: { fontSize: 26, fontWeight: 800, background: 'linear-gradient(90deg,#00f0ff,#a855f7)', WebkitBackgroundClip:'text', WebkitTextFillColor:'transparent', marginBottom: 24 },
  card:    { background: '#12121e', border: '1px solid rgba(255,255,255,0.07)', borderRadius: 12, marginBottom: 16, overflow: 'hidden' },
  cardHdr: { display: 'flex', alignItems: 'center', gap: 12, padding: '14px 18px', cursor: 'pointer', userSelect: 'none' },
  pill:    { fontSize: 11, fontWeight: 600, padding: '2px 8px', borderRadius: 4, background: 'rgba(168,85,247,0.18)', color: '#c084fc', border: '1px solid rgba(168,85,247,0.3)' },
  songRow: { display: 'flex', alignItems: 'center', gap: 12, padding: '10px 18px', borderTop: '1px solid rgba(255,255,255,0.05)' },
  btn:     { background: 'none', border: '1px solid rgba(255,255,255,0.12)', borderRadius: 6, color: '#94a3b8', fontSize: 13, cursor: 'pointer', padding: '5px 10px', transition: 'all 0.15s' },
  input:   { background: 'rgba(255,255,255,0.05)', border: '1px solid rgba(0,240,255,0.25)', borderRadius: 8, color: '#e2e8f0', fontSize: 14, padding: '8px 14px', outline: 'none', width: 220 },
};

function ConfirmDialog({ message, onConfirm, onCancel }) {
  return (
    <div style={{ position:'fixed', inset:0, background:'rgba(0,0,0,0.7)', zIndex:1000, display:'flex', alignItems:'center', justifyContent:'center' }}>
      <div style={{ background:'#18182a', border:'1px solid rgba(248,113,113,0.3)', borderRadius:12, padding:'28px 32px', maxWidth:340, textAlign:'center' }}>
        <p style={{ color:'#e2e8f0', marginBottom:20, fontSize:15 }}>{message}</p>
        <div style={{ display:'flex', gap:12, justifyContent:'center' }}>
          <button onClick={onConfirm} style={{ ...S.btn, color:'#f87171', borderColor:'rgba(248,113,113,0.4)' }}>Delete</button>
          <button onClick={onCancel}  style={S.btn}>Cancel</button>
        </div>
      </div>
    </div>
  );
}

function SortableSongRow({ song, index, onPlay, onRemove }) {
  const { attributes, listeners, setNodeRef, transform, transition, isDragging } = useSortable({
    id: song.variant_id,
  });

  return (
    <div
      ref={setNodeRef}
      style={{
        ...S.songRow,
        transform: CSS.Transform.toString(transform),
        transition,
        background: isDragging ? 'rgba(0,240,255,0.06)' : 'transparent',
        opacity: isDragging ? 0.55 : 1,
        zIndex: isDragging ? 10 : 'auto',
        position: 'relative',
        boxShadow: isDragging ? '0 4px 20px rgba(0,0,0,0.5)' : 'none',
      }}
    >
      <span style={{ color:'#475569', fontSize:12, width:20, textAlign:'right', flexShrink:0 }}>{index+1}</span>
      {/* drag handle — only this element is draggable */}
      <span
        {...attributes}
        {...listeners}
        style={{
          color: '#475569', fontSize: 16, flexShrink: 0,
          cursor: isDragging ? 'grabbing' : 'grab',
          touchAction: 'none', padding: '0 2px', lineHeight: 1,
        }}
        title="Drag to reorder"
      >⣿</span>
      {song.image_url
        ? <img src={song.image_url} alt="" style={{ width:36, height:36, borderRadius:5, objectFit:'cover', flexShrink:0, border:'1px solid rgba(255,255,255,0.08)' }} />
        : <div style={{ width:36, height:36, borderRadius:5, background:'rgba(124,58,237,0.3)', display:'flex', alignItems:'center', justifyContent:'center', flexShrink:0, fontSize:16 }}>♫</div>
      }
      <div style={{ flex:1, minWidth:0 }}>
        <div style={{ fontSize:13, fontWeight:600, overflow:'hidden', textOverflow:'ellipsis', whiteSpace:'nowrap' }}>{song.title || 'Untitled'}</div>
        <span style={S.pill}>{gLabel(song.genre_tag)}</span>
      </div>
      <button onClick={() => onPlay(index)} style={{ ...S.btn, color:'#00f0ff', borderColor:'rgba(0,240,255,0.3)' }}>▶ Play</button>
      <button onClick={() => onRemove(song.variant_id)} style={{ ...S.btn, color:'#f87171', borderColor:'rgba(248,113,113,0.3)', fontSize:11 }}>✕</button>
    </div>
  );
}

function PlaylistCard({ playlist, token, onDeleted }) {
  const { play } = useNowPlaying();
  const [open, setOpen]       = useState(false);
  const [songs, setSongs]     = useState([]);
  const [loading, setLoading] = useState(false);
  const [confirm, setConfirm] = useState(false);

  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 5 } }),
    useSensor(KeyboardSensor, { coordinateGetter: sortableKeyboardCoordinates }),
  );

  const fetchSongs = useCallback(async () => {
    setLoading(true);
    try {
      const r = await fetch(`${BACKEND_URL}/api/playlists/${playlist.id}/songs`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (r.ok) {
        const d = await r.json();
        setSongs(d.songs || []);
      }
    } finally {
      setLoading(false);
    }
  }, [playlist.id, token]);

  const toggle = () => {
    if (!open) fetchSongs();
    setOpen(o => !o);
  };

  const handlePlay = (startIndex) => play(songs, startIndex);

  const handleRemove = async (variantId) => {
    await fetch(`${BACKEND_URL}/api/playlists/${playlist.id}/songs/${variantId}`, {
      method: 'DELETE',
      headers: { Authorization: `Bearer ${token}` },
    });
    setSongs(s => s.filter(x => x.variant_id !== variantId));
  };

  const handleDelete = async () => {
    await fetch(`${BACKEND_URL}/api/playlists/${playlist.id}`, {
      method: 'DELETE',
      headers: { Authorization: `Bearer ${token}` },
    });
    onDeleted(playlist.id);
    setConfirm(false);
  };

  const handleDragEnd = async ({ active, over }) => {
    if (!over || active.id === over.id) return;
    const oldIndex = songs.findIndex(s => s.variant_id === active.id);
    const newIndex = songs.findIndex(s => s.variant_id === over.id);
    const newSongs = arrayMove(songs, oldIndex, newIndex);
    setSongs(newSongs); // optimistic update
    await fetch(`${BACKEND_URL}/api/playlists/${playlist.id}/reorder`, {
      method: 'PATCH',
      headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
      body: JSON.stringify({ variant_ids: newSongs.map(s => s.variant_id) }),
    });
  };

  return (
    <div style={S.card}>
      {confirm && (
        <ConfirmDialog
          message={`Delete playlist "${playlist.name}"?`}
          onConfirm={handleDelete}
          onCancel={() => setConfirm(false)}
        />
      )}
      <div style={S.cardHdr} onClick={toggle}>
        <span style={{ fontSize: 18 }}>{open ? '▾' : '▸'}</span>
        <span style={{ fontSize: 15, fontWeight: 700, flex: 1 }}>{playlist.name}</span>
        <span style={{ fontSize: 12, color: '#64748b' }}>{playlist.song_count ?? 0} songs</span>
        {open && songs.length > 0 && (
          <button
            onClick={(e) => { e.stopPropagation(); handlePlay(0); }}
            style={{ ...S.btn, color:'#00f0ff', borderColor:'rgba(0,240,255,0.3)', marginLeft:8, fontSize:12 }}
          >
            ▶ Play All
          </button>
        )}
        <button
          onClick={(e) => { e.stopPropagation(); setConfirm(true); }}
          style={{ ...S.btn, color:'#f87171', borderColor:'rgba(248,113,113,0.3)', marginLeft:8, fontSize:12 }}
        >
          🗑
        </button>
      </div>

      {open && (
        loading ? (
          <div style={{ padding:'16px 18px', color:'#64748b', fontSize:13 }}>Loading…</div>
        ) : songs.length === 0 ? (
          <div style={{ padding:'16px 18px', color:'#475569', fontSize:13 }}>No songs yet. Add songs from your library.</div>
        ) : (
          <DndContext sensors={sensors} collisionDetection={closestCenter} onDragEnd={handleDragEnd}>
            <SortableContext items={songs.map(s => s.variant_id)} strategy={verticalListSortingStrategy}>
              {songs.map((song, i) => (
                <SortableSongRow
                  key={song.variant_id}
                  song={song}
                  index={i}
                  onPlay={handlePlay}
                  onRemove={handleRemove}
                />
              ))}
            </SortableContext>
          </DndContext>
        )
      )}
    </div>
  );
}

const settingToggleStyle = (active) => ({
  background: active ? 'rgba(0,240,255,0.14)' : 'rgba(255,255,255,0.05)',
  border: `1px solid ${active ? 'rgba(0,240,255,0.55)' : 'rgba(255,255,255,0.14)'}`,
  borderRadius: 20, padding: '5px 16px', cursor: 'pointer', flexShrink: 0, marginLeft: 16,
  color: active ? '#00f0ff' : '#64748b', fontWeight: 700, fontSize: 13, transition: 'all 0.2s',
});

function PlaybackSettings() {
  const {
    crossfade, crossfadeDuration, setCrossfade, setCrossfadeDuration,
    shuffle, toggleShuffle,
  } = useNowPlaying();

  return (
    <div style={{ ...S.card, marginBottom: 32 }}>
      <div style={{ padding: '16px 20px' }}>
        <p style={{ fontSize: 11, fontWeight: 700, color: '#64748b', letterSpacing: '0.6px', textTransform: 'uppercase', marginBottom: 14 }}>
          Playback Settings
        </p>

        {/* Shuffle toggle — Bug 3: expose shuffle here so it's visible even when the Now Playing bar is paused/hidden */}
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 16 }}>
          <div>
            <span style={{ fontSize: 14, color: '#e2e8f0', fontWeight: 600 }}>🔀 Shuffle</span>
            <p style={{ fontSize: 12, color: shuffle ? '#fbbf24' : '#64748b', margin: '2px 0 0', lineHeight: 1.4 }}>
              {shuffle ? '⚠️ Shuffle is ON — songs play in random order' : 'Songs play in playlist order'}
            </p>
          </div>
          <button onClick={toggleShuffle} style={settingToggleStyle(shuffle)}>
            {shuffle ? 'ON' : 'OFF'}
          </button>
        </div>

        {/* Crossfade toggle */}
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: crossfade ? 16 : 0 }}>
          <div>
            <span style={{ fontSize: 14, color: '#e2e8f0', fontWeight: 600 }}>🎚️ Crossfade</span>
            <p style={{ fontSize: 12, color: '#64748b', margin: '2px 0 0', lineHeight: 1.4 }}>
              Fade smoothly between tracks — starts {crossfadeDuration}s before each track ends
            </p>
          </div>
          <button onClick={() => setCrossfade(!crossfade)} style={settingToggleStyle(crossfade)}>
            {crossfade ? 'ON' : 'OFF'}
          </button>
        </div>

        {/* Duration selector — only shown when crossfade is on */}
        {crossfade && (
          <div>
            <p style={{ fontSize: 12, color: '#64748b', marginBottom: 8 }}>Fade duration</p>
            <div style={{ display: 'flex', gap: 8 }}>
              {[
                { d: 5,  label: '⚡ 5s'  },
                { d: 10, label: '🎚️ 10s' },
                { d: 15, label: '🎵 15s' },
                { d: 20, label: '🌊 20s' },
              ].map(({ d, label }) => (
                <button
                  key={d}
                  onClick={() => setCrossfadeDuration(d)}
                  style={{
                    flex: 1, padding: '7px 0',
                    background: crossfadeDuration === d ? 'rgba(0,240,255,0.14)' : 'rgba(255,255,255,0.04)',
                    border: `1px solid ${crossfadeDuration === d ? 'rgba(0,240,255,0.55)' : 'rgba(255,255,255,0.1)'}`,
                    borderRadius: 8, cursor: 'pointer',
                    color: crossfadeDuration === d ? '#00f0ff' : '#64748b',
                    fontWeight: crossfadeDuration === d ? 700 : 400, fontSize: 12,
                    transition: 'all 0.2s',
                  }}
                >
                  {label}
                </button>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

export default function PlaylistPage() {
  const { token } = useAuth();
  const { dismiss } = useNowPlaying();
  const [playlists, setPlaylists]   = useState([]);
  const [loading, setLoading]       = useState(true);
  const [newName, setNewName]       = useState('');
  const [creating, setCreating]     = useState(false);
  const [aiOpen, setAiOpen]         = useState(false);
  const [aiPrompt, setAiPrompt]     = useState('');
  const [aiLoading, setAiLoading]   = useState(false);
  const [aiError, setAiError]       = useState('');

  // Clear now-playing when leaving playlist if nothing is actively playing
  useEffect(() => {
    return () => {
      if (!audioManager.isPlaying()) {
        dismiss();
      }
    };
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const fetchPlaylists = useCallback(async () => {
    try {
      const r = await fetch(`${BACKEND_URL}/api/playlists`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (r.ok) setPlaylists(await r.json());
    } finally {
      setLoading(false);
    }
  }, [token]);

  useEffect(() => { fetchPlaylists(); }, [fetchPlaylists]);

  const handleCreate = async (e) => {
    e.preventDefault();
    if (!newName.trim()) return;
    setCreating(true);
    try {
      const r = await fetch(`${BACKEND_URL}/api/playlists`, {
        method: 'POST',
        headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
        body: JSON.stringify({ name: newName.trim() }),
      });
      if (r.ok) {
        const pl = await r.json();
        setPlaylists(prev => [{ ...pl, song_count: 0 }, ...prev]);
        setNewName('');
      }
    } finally {
      setCreating(false);
    }
  };

  const handleDeleted = (id) => setPlaylists(prev => prev.filter(p => p.id !== id));

  const handleAiGenerate = async () => {
    if (!aiPrompt.trim()) return;
    setAiLoading(true);
    setAiError('');
    try {
      const r = await fetch(`${BACKEND_URL}/api/playlists/ai-generate`, {
        method: 'POST',
        headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
        body: JSON.stringify({ prompt: aiPrompt.trim() }),
      });
      const data = await r.json();
      if (!r.ok) { setAiError(data.detail || 'Something went wrong'); return; }
      // Merge song_count from response into playlist object for immediate display
      setPlaylists(prev => [{ ...data.playlist, song_count: data.song_count }, ...prev]);
      setAiOpen(false);
      setAiPrompt('');
    } catch (_) {
      setAiError('Something went wrong. Try again.');
    } finally {
      setAiLoading(false);
    }
  };

  return (
    <div style={S.page}>
      <BeatsDashboardHeader />
      <div style={S.wrap}>
        <h1 style={S.heading}>🎵 Playlists</h1>

        {/* Create new playlist */}
        <form onSubmit={handleCreate} style={{ display:'flex', gap:10, marginBottom:32 }}>
          <input
            value={newName}
            onChange={e => setNewName(e.target.value)}
            placeholder="New playlist name…"
            style={S.input}
            maxLength={80}
          />
          <button
            type="submit"
            disabled={creating || !newName.trim()}
            style={{
              background: 'linear-gradient(135deg,#7c3aed,#a855f7)', border:'none', borderRadius:8,
              color:'#fff', fontWeight:700, fontSize:13, padding:'8px 18px', cursor:'pointer',
              opacity: creating || !newName.trim() ? 0.55 : 1,
            }}
          >
            {creating ? '…' : '+ Create'}
          </button>
        </form>

        <button
          type="button"
          onClick={() => { setAiOpen(true); setAiError(''); }}
          style={{
            background: 'linear-gradient(135deg,rgba(0,240,255,0.08),rgba(168,85,247,0.08))',
            border: '1px solid rgba(0,240,255,0.3)', borderRadius: 8,
            color: '#00f0ff', fontWeight: 700, fontSize: 13,
            padding: '8px 18px', cursor: 'pointer', marginBottom: 32, transition: 'all 0.15s',
          }}
        >
          ✨ AI Playlist
        </button>

        <PlaybackSettings />

        {loading ? (
          <div style={{ color:'#64748b', textAlign:'center', padding:40 }}>Loading playlists…</div>
        ) : playlists.length === 0 ? (
          <div style={{ color:'#475569', textAlign:'center', padding:40, fontSize:15 }}>
            No playlists yet. Create one above, then add songs from your library.
          </div>
        ) : (
          playlists.map(pl => (
            <PlaylistCard key={pl.id} playlist={pl} token={token} onDeleted={handleDeleted} />
          ))
        )}
      </div>

      {/* AI Playlist modal */}
      {aiOpen && (
        <div
          onClick={() => setAiOpen(false)}
          style={{
            position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.78)', zIndex: 1000,
            display: 'flex', alignItems: 'center', justifyContent: 'center', padding: 20,
          }}
        >
          <div
            onClick={e => e.stopPropagation()}
            style={{
              background: '#12121e', border: '1px solid rgba(0,240,255,0.25)',
              borderRadius: 16, padding: '28px 24px', maxWidth: 440, width: '100%',
            }}
          >
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 18 }}>
              <h2 style={{ margin: 0, fontSize: 18, fontWeight: 800, background: 'linear-gradient(90deg,#00f0ff,#a855f7)', WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent' }}>
                ✨ AI Playlist Builder
              </h2>
              <button onClick={() => setAiOpen(false)} style={{ ...S.btn, padding: '4px 9px', fontSize: 15 }}>✕</button>
            </div>

            <div style={{ display: 'flex', flexWrap: 'wrap', gap: 7, marginBottom: 14 }}>
              {AI_CHIPS.map(chip => (
                <button
                  key={chip}
                  onClick={() => setAiPrompt(chip)}
                  style={{
                    background: aiPrompt === chip ? 'rgba(0,240,255,0.12)' : 'rgba(255,255,255,0.04)',
                    border: `1px solid ${aiPrompt === chip ? 'rgba(0,240,255,0.5)' : 'rgba(255,255,255,0.1)'}`,
                    borderRadius: 20, color: aiPrompt === chip ? '#00f0ff' : '#94a3b8',
                    fontSize: 12, padding: '5px 12px', cursor: 'pointer', transition: 'all 0.15s',
                  }}
                >
                  {chip}
                </button>
              ))}
            </div>

            <input
              value={aiPrompt}
              onChange={e => setAiPrompt(e.target.value)}
              onKeyDown={e => e.key === 'Enter' && !aiLoading && handleAiGenerate()}
              placeholder="Describe your mood or vibe..."
              style={{ ...S.input, width: '100%', marginBottom: 12, boxSizing: 'border-box' }}
              autoFocus
              maxLength={120}
            />

            {aiError && (
              <p style={{ color: '#f87171', fontSize: 13, margin: '0 0 10px' }}>{aiError}</p>
            )}

            <button
              onClick={handleAiGenerate}
              disabled={aiLoading || !aiPrompt.trim()}
              style={{
                width: '100%', padding: '11px 0', marginTop: 4,
                background: 'linear-gradient(135deg,#7c3aed,#a855f7)', border: 'none',
                borderRadius: 8, color: '#fff', fontWeight: 700, fontSize: 14, cursor: 'pointer',
                opacity: aiLoading || !aiPrompt.trim() ? 0.55 : 1, transition: 'opacity 0.2s',
              }}
            >
              {aiLoading ? '✨ Claude is curating your playlist…' : '✨ Generate Playlist'}
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
