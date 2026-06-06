import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../../contexts/AuthContext';
import { BACKEND_URL } from '../../brand';

const THEMES = [
  { emoji: '🐘', label: 'Animals',   genres: ['kids pop', 'childrens'] },
  { emoji: '🚀', label: 'Space',     genres: ['kids pop', 'fun electronic'] },
  { emoji: '🌈', label: 'Magic',     genres: ['childrens', 'fantasy pop'] },
  { emoji: '🐠', label: 'Ocean',     genres: ['kids pop', 'relaxed'] },
  { emoji: '🦁', label: 'Safari',    genres: ['kids pop', 'world'] },
  { emoji: '❄️',  label: 'Winter',   genres: ['childrens', 'festive'] },
];

const AGE_RANGES = [
  { value: 'tiny_tots',   label: '👶 Tiny Tots',   sub: 'Ages 2–4' },
  { value: 'little_ones', label: '🧒 Little Ones',  sub: 'Ages 4–6' },
  { value: 'big_kids',    label: '🧑 Big Kids',     sub: 'Ages 7–10' },
];

export default function KidsSongMode() {
  const { token } = useAuth();
  const navigate = useNavigate();
  const [theme, setTheme] = useState(null);
  const [age, setAge] = useState('little_ones');
  const [character, setCharacter] = useState('');
  const [generating, setGenerating] = useState(false);
  const [error, setError] = useState('');

  const canGenerate = theme !== null;

  const handleGenerate = async () => {
    if (!canGenerate || generating) return;
    setGenerating(true);
    setError('');
    try {
      const res = await fetch(`${BACKEND_URL}/api/songs/generate`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
        body: JSON.stringify({
          brief: character.trim()
            ? `A fun kids song about ${character.trim()} with a ${THEMES[theme].label.toLowerCase()} theme`
            : `A fun kids song with a ${THEMES[theme].label.toLowerCase()} theme`,
          genres: THEMES[theme].genres,
          kids_mode: 'song',
          age_range: age,
          explicit: false,
        }),
      });
      if (!res.ok) {
        const d = await res.json().catch(() => ({}));
        throw new Error(d.detail || 'Could not make the song');
      }
      navigate('/kids/songs');
    } catch (e) {
      setError(e.message);
    } finally {
      setGenerating(false);
    }
  };

  return (
    <div style={{ flex: 1, padding: '16px 20px 32px', maxWidth: 520, margin: '0 auto', width: '100%' }}>
      <button onClick={() => navigate('/kids')} style={{ background: 'none', border: 'none', color: '#45b7d1', fontWeight: 700, fontSize: 14, cursor: 'pointer', marginBottom: 16, padding: 0 }}>
        ← Back
      </button>

      <h2 style={{ margin: '0 0 6px', fontSize: 22 }}>What kind of song? 🎶</h2>
      <p style={{ margin: '0 0 20px', color: '#64748b', fontSize: 14 }}>Pick a theme to get started!</p>

      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 10, justifyContent: 'center', marginBottom: 24 }}>
        {THEMES.map((t, i) => (
          <button key={i} className={`kids-tile${theme === i ? ' selected' : ''}`} onClick={() => setTheme(i)}>
            {t.emoji}
            <span>{t.label}</span>
          </button>
        ))}
      </div>

      <p style={{ fontWeight: 700, fontSize: 14, margin: '0 0 10px' }}>Who is it for?</p>
      <div style={{ display: 'flex', gap: 8, marginBottom: 20, flexWrap: 'wrap' }}>
        {AGE_RANGES.map(a => (
          <button
            key={a.value}
            onClick={() => setAge(a.value)}
            style={{
              flex: '1 1 90px', padding: '10px 8px', borderRadius: 16, border: `2px solid ${age === a.value ? '#fbd155' : 'rgba(69,183,209,0.3)'}`,
              background: age === a.value ? 'rgba(251,209,85,0.15)' : 'rgba(255,255,255,0.7)',
              cursor: 'pointer', fontFamily: 'Nunito, sans-serif', fontWeight: 700, fontSize: 13, color: '#1a2b4a',
            }}
          >
            {a.label}<br/><span style={{ fontSize: 11, fontWeight: 400, color: '#64748b' }}>{a.sub}</span>
          </button>
        ))}
      </div>

      <p style={{ fontWeight: 700, fontSize: 14, margin: '0 0 8px' }}>Who is the song about? (optional)</p>
      <input
        className="kids-input"
        placeholder="e.g. Bella the bunny, Leo the lion..."
        value={character}
        onChange={e => setCharacter(e.target.value)}
        style={{ marginBottom: 24 }}
      />

      {error && <p style={{ color: '#ef4444', fontWeight: 700, fontSize: 14, marginBottom: 12 }}>{error}</p>}

      <button
        className="kids-btn kids-btn-primary"
        style={{ width: '100%', opacity: canGenerate ? 1 : 0.5 }}
        disabled={!canGenerate || generating}
        onClick={handleGenerate}
      >
        {generating ? '✨ Making your song...' : '✨ Make My Song!'}
      </button>
    </div>
  );
}
