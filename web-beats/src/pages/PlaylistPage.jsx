import { useState, useEffect, useCallback, useRef } from 'react';
import { useAuth } from '../contexts/AuthContext';
import { useNowPlaying } from '../contexts/NowPlayingContext';
import { BeatsDashboardHeader } from '../components/BeatsDashboardHeader';

const BACKEND_URL = import.meta.env.VITE_BACKEND_URL || '';

const GENRE_LABEL = {
  hiphop:'Hip-hop', lofi:'Lo-Fi', edm:'EDM', irishjig:'Irish Jig', irishfolk:'Irish Folk',
  rnb:'R&B', bluessoul:'Blues Soul', drumandbass:'D&B', grime:'Grime', ukgarage:'UK Garage',
  jungle:'Jungle', bassline:'Bassline', house:'House', loversrock:'Lovers Rock', ukdrill:'UK Drill',
  kpop:'K-Pop', deepsoulblues:'Deep Soul Blues', ukstreetsoul:'UK Street Soul', technhouse:'Tech House',
  driftphonk:'Drift Phonk', jerseyclub:'Jersey Club', afroswing:'Afroswing', rastadub:'Rasta Dub',
  deeprotbassline:'Deeprot Bassline', jazz:'Jazz', electronicfunk:'Electronic Funk',
  syntheticpop:'Synthetic Pop', ragga:'Ragga', dubstep:'Dubstep',
  bhangra:'Bhangra', rockney:'Rockney', metal:'Metal',
};
function gLabel(g) {
  if (!g) return '';
  if (g.includes('__')) { const [a,b]=g.split('__'); return `${GENRE_LABEL[a]||a} × ${GENRE_LABEL[b]||b}`; }
  return GENRE_LABEL[g] || g.charAt(0).toUpperCase()+g.slice(1);
}

// ── styles ────────────────────────────────────────────────────────────────────
const S = {
  page:    { minHeight: '100vh', background: '#0b0b14', color: '#e2e8f0', paddingBottom: 100 },
  wrap:    { maxWidth: 860, margin: '0 auto', padding: '32px 20px' },
  heading: { fontSize: 26, fontWeight: 800, background: 'linear-gradient(90deg,#00f0ff,#a855f7)', WebkitBackgroundClip:'text', WebkitTextFillColor:'transparent', marginBottom: 24 },
  card:    { background: '#12121e', border: '1px solid rgba(255,255,255,0.07)', borderRadius: 12, marginBottom: 16, overflow: 'hidden' },
  cardHdr: { display: 'flex', alignItems: 'center', gap: 12, padding: '14px 18px', cursor: 'pointer', userSelect: 'none' },
  pill:    { fontSize: 11, fontWeight: 600, padding: '2px 8px', borderRadius: 4, background: 'rgba(168,85,247,0.18)', color: '#c084fc', border: '1px solid rgba(168,85,247,0.3)' },
  songRow: { display: 'flex', alignItems: 'center', gap: 12, padding: '10px 18px', borderTop: '1px solid rgba(255,255,255,0.05)', transition: 'background 0.15s' },
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

function SongRow({ song, index, onPlay, onRemove, onDragStart, onDragOver, onDrop, dragging }) {
  return (
    <div
      draggable
      onDragStart={(e) => onDragStart(e, index)}
      onDragOver={(e) => { e.preventDefault(); onDragOver(index); }}
      onDrop={(e) => onDrop(e, index)}
      style={{
        ...S.songRow,
        background: dragging ? 'rgba(0,240,255,0.04)' : 'transparent',
        opacity: dragging ? 0.6 : 1,
        cursor: 'grab',
      }}
    >
      <span style={{ color:'#475569', fontSize:12, width:20, textAlign:'right', flexShrink:0 }}>{index+1}</span>
      <span style={{ color:'#475569', fontSize:14, cursor:'grab', flexShrink:0 }}>⠿</span>
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
  const [open, setOpen]     = useState(false);
  const [songs, setSongs]   = useState([]);
  const [loading, setLoading] = useState(false);
  const [confirm, setConfirm] = useState(false);
  const [dragIdx, setDragIdx] = useState(null);
  const [overIdx, setOverIdx] = useState(null);
  const dragSrcRef = useRef(null);

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

  const handlePlay = (startIndex) => {
    play(songs, startIndex);
  };

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

  // Drag-and-drop reorder
  const onDragStart = (e, idx) => {
    dragSrcRef.current = idx;
    setDragIdx(idx);
    e.dataTransfer.effectAllowed = 'move';
  };
  const onDragOver = (idx) => setOverIdx(idx);
  const onDrop = async (e, targetIdx) => {
    e.preventDefault();
    const srcIdx = dragSrcRef.current;
    if (srcIdx === null || srcIdx === targetIdx) { setDragIdx(null); setOverIdx(null); return; }
    const newSongs = [...songs];
    const [moved] = newSongs.splice(srcIdx, 1);
    newSongs.splice(targetIdx, 0, moved);
    setSongs(newSongs);
    setDragIdx(null);
    setOverIdx(null);
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
          songs.map((song, i) => (
            <SongRow
              key={song.variant_id}
              song={song}
              index={i}
              onPlay={handlePlay}
              onRemove={handleRemove}
              onDragStart={onDragStart}
              onDragOver={onDragOver}
              onDrop={onDrop}
              dragging={dragIdx === i || overIdx === i}
            />
          ))
        )
      )}
    </div>
  );
}

export default function PlaylistPage() {
  const { token } = useAuth();
  const [playlists, setPlaylists]   = useState([]);
  const [loading, setLoading]       = useState(true);
  const [newName, setNewName]       = useState('');
  const [creating, setCreating]     = useState(false);

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
        setPlaylists(prev => [pl, ...prev]);
        setNewName('');
      }
    } finally {
      setCreating(false);
    }
  };

  const handleDeleted = (id) => setPlaylists(prev => prev.filter(p => p.id !== id));

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
    </div>
  );
}
