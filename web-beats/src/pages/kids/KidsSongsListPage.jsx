import { useEffect, useState, useRef, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../../contexts/AuthContext';
import { BACKEND_URL } from '../../brand';

function resolveUrl(url) {
  if (!url) return null;
  return url.startsWith('http') ? url : `${BACKEND_URL}${url}`;
}

export default function KidsSongsListPage() {
  const { token } = useAuth();
  const navigate = useNavigate();
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(true);
  const [playingId, setPlayingId] = useState(null);
  const audioRef = useRef(null);

  const fetchLibrary = useCallback(async () => {
    if (!token) return;
    try {
      const r = await fetch(`${BACKEND_URL}/api/lyrics`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!r.ok) { setLoading(false); return; }
      const { lyrics } = await r.json();

      const groups = await Promise.all(
        (lyrics || []).map(async (lyric) => {
          const vr = await fetch(`${BACKEND_URL}/api/lyrics/${lyric.id}/variants`, {
            headers: { Authorization: `Bearer ${token}` },
          });
          if (!vr.ok) return [];
          const d = await vr.json();
          return (d.variants || []).map(v => ({ ...v, title: lyric.title, lyric_id: lyric.id }));
        })
      );

      const flat = groups
        .flat()
        .filter(v => v.status === 'complete' && (v.mp3_url || v.story_audio_url))
        .sort((a, b) => b.variant_id - a.variant_id);

      setItems(flat);
    } catch (_) {
      setItems([]);
    } finally {
      setLoading(false);
    }
  }, [token]);

  useEffect(() => { fetchLibrary(); }, [fetchLibrary]);

  const handlePlay = (item) => {
    const url = resolveUrl(item.mp3_url || item.story_audio_url);
    if (!url) return;

    if (playingId === item.variant_id) {
      audioRef.current?.pause();
      setPlayingId(null);
      return;
    }
    if (audioRef.current) audioRef.current.pause();
    const a = new Audio(url);
    a.onended = () => setPlayingId(null);
    a.onpause = () => setPlayingId(null);
    a.play().catch(() => {});
    audioRef.current = a;
    setPlayingId(item.variant_id);
  };

  useEffect(() => () => { audioRef.current?.pause(); }, []);

  const isStory = (item) => item.genre_tag === 'kids_story';

  return (
    <div style={{ flex: 1, padding: '16px 20px 80px', maxWidth: 600, margin: '0 auto', width: '100%' }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 20 }}>
        <h2 style={{ margin: 0, fontSize: 20 }}>Your Songs &amp; Stories 🎵</h2>
        <button
          onClick={() => navigate('/kids')}
          style={{ marginLeft: 'auto', background: 'none', border: 'none', color: '#45b7d1', fontWeight: 700, fontSize: 13, cursor: 'pointer' }}
        >
          ← Home
        </button>
      </div>

      {loading && (
        <p style={{ color: '#64748b', textAlign: 'center', fontFamily: 'Nunito, sans-serif' }}>
          Loading your songs... ✨
        </p>
      )}

      {!loading && items.length === 0 && (
        <div style={{ textAlign: 'center', padding: '40px 20px' }}>
          <div style={{ fontSize: 56, marginBottom: 12 }}>🎵</div>
          <p style={{ color: '#64748b', fontWeight: 600, fontFamily: 'Nunito, sans-serif' }}>
            No songs yet! Go make your first one.
          </p>
          <button className="kids-btn kids-btn-primary" onClick={() => navigate('/kids')} style={{ marginTop: 16 }}>
            Make a Song!
          </button>
        </div>
      )}

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(155px, 1fr))', gap: 16 }}>
        {items.map(item => {
          const playing = playingId === item.variant_id;
          const story = isStory(item);
          const hasAudio = !!(item.mp3_url || item.story_audio_url);

          return (
            <div
              key={item.variant_id}
              className="kids-card"
              style={{ padding: 0, overflow: 'hidden', cursor: hasAudio ? 'pointer' : 'default' }}
              onClick={() => handlePlay(item)}
            >
              {/* Cover art */}
              {item.image_url ? (
                <img
                  src={item.image_url}
                  alt={item.title}
                  style={{ width: '100%', aspectRatio: '1/1', objectFit: 'cover', display: 'block' }}
                />
              ) : (
                <div style={{
                  width: '100%', aspectRatio: '1/1', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 44,
                  background: story
                    ? 'linear-gradient(135deg, #a78bfa, #f472b6)'
                    : 'linear-gradient(135deg, #fbd155, #ff6b6b)',
                }}>
                  {story ? '📖' : '🎵'}
                </div>
              )}

              {/* Card body */}
              <div style={{ padding: '10px 12px' }}>
                <div style={{
                  fontWeight: 800, fontSize: 13, color: '#1a2b4a',
                  overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
                  fontFamily: 'Nunito, sans-serif', marginBottom: 4,
                }}>
                  {item.title || (story ? 'My Story' : 'My Song')}
                </div>

                {story && (
                  <div style={{ fontSize: 10, color: '#a78bfa', fontWeight: 700, fontFamily: 'Nunito, sans-serif', marginBottom: 4 }}>
                    📖 Story
                  </div>
                )}

                <div style={{
                  display: 'flex', alignItems: 'center', justifyContent: 'center',
                  marginTop: 4,
                  height: 36, borderRadius: 10,
                  background: playing
                    ? (story ? 'rgba(167,139,250,0.2)' : 'rgba(251,209,85,0.2)')
                    : 'rgba(0,0,0,0.04)',
                  border: `1px solid ${playing ? (story ? '#a78bfa' : '#fbd155') : 'rgba(0,0,0,0.08)'}`,
                  fontSize: 18,
                }}>
                  {!hasAudio ? '⏳' : playing ? '⏸️' : '▶️'}
                </div>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
