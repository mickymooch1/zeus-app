import { useEffect, useState, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../../contexts/AuthContext';
import { BACKEND_URL } from '../../brand';

export default function KidsSongsListPage() {
  const { token } = useAuth();
  const navigate = useNavigate();
  const [songs, setSongs] = useState([]);
  const [loading, setLoading] = useState(true);
  const [playingId, setPlayingId] = useState(null);
  const audioRef = useRef(null);

  useEffect(() => {
    if (!token) return;
    fetch(`${BACKEND_URL}/api/songs`, { headers: { Authorization: `Bearer ${token}` } })
      .then(r => r.ok ? r.json() : [])
      .then(data => {
        const variants = Array.isArray(data) ? data : (data.variants || []);
        setSongs(variants.filter(v => v.status === 'complete').slice(0, 20));
      })
      .catch(() => setSongs([]))
      .finally(() => setLoading(false));
  }, [token]);

  const handlePlay = (song) => {
    if (!song.mp3_url) return;
    if (playingId === song.variant_id) {
      audioRef.current?.pause();
      setPlayingId(null);
      return;
    }
    if (audioRef.current) {
      audioRef.current.pause();
      audioRef.current.src = song.mp3_url;
      audioRef.current.play().catch(() => {});
      setPlayingId(song.variant_id);
    }
  };

  return (
    <div style={{ flex: 1, padding: '16px 20px 80px', maxWidth: 600, margin: '0 auto', width: '100%' }}>
      <audio ref={audioRef} onEnded={() => setPlayingId(null)} style={{ display: 'none' }} />

      <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 20 }}>
        <h2 style={{ margin: 0, fontSize: 20 }}>Your Songs &amp; Stories 🎵</h2>
        <button onClick={() => navigate('/kids')} style={{ marginLeft: 'auto', background: 'none', border: 'none', color: '#45b7d1', fontWeight: 700, fontSize: 13, cursor: 'pointer' }}>
          ← Home
        </button>
      </div>

      {loading && <p style={{ color: '#64748b', textAlign: 'center' }}>Loading your songs... ✨</p>}

      {!loading && songs.length === 0 && (
        <div style={{ textAlign: 'center', padding: '40px 20px' }}>
          <div style={{ fontSize: 56, marginBottom: 12 }}>🎵</div>
          <p style={{ color: '#64748b', fontWeight: 600 }}>No songs yet! Go make your first one.</p>
          <button className="kids-btn kids-btn-primary" onClick={() => navigate('/kids')} style={{ marginTop: 16 }}>
            Make a Song!
          </button>
        </div>
      )}

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(160px, 1fr))', gap: 16 }}>
        {songs.map(song => (
          <div key={song.variant_id} className="kids-card" style={{ padding: 0, overflow: 'hidden', cursor: 'pointer' }} onClick={() => handlePlay(song)}>
            {song.image_url
              ? <img src={song.image_url} alt={song.title} className="cover-ken-burns" style={{ width: '100%', aspectRatio: '1/1', objectFit: 'cover', display: 'block' }} />
              : <div style={{ width: '100%', aspectRatio: '1/1', background: 'linear-gradient(135deg, #fbd155, #ff6b9d)', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 40 }}>🎵</div>
            }
            <div style={{ padding: '10px 12px' }}>
              <div style={{ fontWeight: 800, fontSize: 13, color: '#1a2b4a', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                {song.title || 'My Song'}
              </div>
              <div style={{ fontSize: 22, textAlign: 'center', marginTop: 6 }}>
                {playingId === song.variant_id ? '⏸' : '▶️'}
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
