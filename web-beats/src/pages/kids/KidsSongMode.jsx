import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../../contexts/AuthContext';
import { BACKEND_URL } from '../../brand';

const THEMES = [
  { emoji: '🐘', label: 'Animals' },
  { emoji: '🚀', label: 'Space' },
  { emoji: '🌈', label: 'Magic' },
  { emoji: '🐠', label: 'Ocean' },
  { emoji: '🦁', label: 'Safari' },
  { emoji: '❄️',  label: 'Winter' },
];

const MUSIC_STYLES = [
  { value: 'nursery',  emoji: '🎠', label: 'Nursery Rhyme',   genres: ['acoustic'] },
  { value: 'funpop',   emoji: '🎉', label: 'Fun Pop',          genres: ['pop'] },
  { value: 'acoustic', emoji: '🎸', label: 'Gentle Acoustic',  genres: ['acoustic'] },
  { value: 'piano',    emoji: '🎹', label: 'Happy Piano',      genres: ['classical'] },
  { value: 'reggae',   emoji: '🏝️', label: 'Reggae Fun',      genres: ['reggae'] },
];

const AGE_RANGES = [
  { value: 'tiny_tots',   emoji: '🍼', label: 'Tiny Tots',   ages: '2–4' },
  { value: 'little_ones', emoji: '🌟', label: 'Little Ones', ages: '4–6' },
  { value: 'big_kids',    emoji: '📚', label: 'Big Kids',    ages: '7–10' },
];

const ACCENTS = [
  'British', 'Irish', 'Scottish', 'Australian',
  'Caribbean', 'American Soul', 'Jamaican', 'French', 'Spanish',
];

const selBtn = (active, borderColor, bgColor) => ({
  border: `2px solid ${active ? borderColor : 'rgba(0,0,0,0.1)'}`,
  background: active ? bgColor : 'rgba(255,255,255,0.7)',
  cursor: 'pointer', fontFamily: 'Nunito, sans-serif',
  fontWeight: 700, color: '#1a2b4a', borderRadius: 14, transition: 'all 0.15s',
});

export default function KidsSongMode() {
  const { token } = useAuth();
  const navigate = useNavigate();
  const [theme, setTheme]           = useState(null);
  const [musicStyle, setMusicStyle] = useState('funpop');
  const [age, setAge]               = useState('little_ones');
  const [accent, setAccent]         = useState('');
  const [character, setCharacter]   = useState('');
  const [generating, setGenerating] = useState(false);
  const [error, setError]           = useState('');

  const canGenerate = theme !== null;
  const selectedStyle = MUSIC_STYLES.find(s => s.value === musicStyle) ?? MUSIC_STYLES[1];

  const handleGenerate = async () => {
    if (!canGenerate || generating) return;
    setGenerating(true);
    setError('');
    try {
      const brief = [
        character.trim() && `Main character: ${character.trim()}`,
        `Theme: ${THEMES[theme].label}`,
        age === 'tiny_tots'   && 'Age range: tiny tots aged 2-4',
        age === 'little_ones' && 'Age range: little ones aged 4-6',
        age === 'big_kids'    && 'Age range: big kids aged 7-10',
      ].filter(Boolean).join('. ');

      const res = await fetch(`${BACKEND_URL}/api/songs/generate`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
        body: JSON.stringify({
          brief,
          genres: selectedStyle.genres,
          kids_story: true,
          kids_mode: 'song',
          kids_age_range: age,
          accent: accent || undefined,
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
    <div style={{ flex: 1, padding: '16px 20px 40px', maxWidth: 560, margin: '0 auto', width: '100%' }}>
      <button onClick={() => navigate('/kids')} style={{ background: 'none', border: 'none', color: '#45b7d1', fontWeight: 700, fontSize: 14, cursor: 'pointer', marginBottom: 16, padding: 0 }}>
        ← Back
      </button>

      <h2 style={{ margin: '0 0 4px', fontSize: 22 }}>What kind of song? 🎶</h2>
      <p style={{ margin: '0 0 18px', color: 'rgba(255,255,255,0.75)', fontSize: 14 }}>Pick a theme and style — we'll make it!</p>

      {/* Theme */}
      <p style={{ fontWeight: 800, fontSize: 13, color: 'rgba(255,255,255,0.9)', textTransform: 'uppercase', letterSpacing: '0.5px', margin: '0 0 10px' }}>🌈 Theme</p>
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 10, justifyContent: 'center', marginBottom: 22 }}>
        {THEMES.map((t, i) => (
          <button key={i} className={`kids-tile${theme === i ? ' selected' : ''}`} onClick={() => setTheme(i)}>
            {t.emoji}
            <span>{t.label}</span>
          </button>
        ))}
      </div>

      {/* Music Style */}
      <p style={{ fontWeight: 800, fontSize: 13, color: 'rgba(255,255,255,0.9)', textTransform: 'uppercase', letterSpacing: '0.5px', margin: '0 0 10px' }}>🎵 Music Style</p>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(5, 1fr)', gap: 8, marginBottom: 22 }}>
        {MUSIC_STYLES.map(s => (
          <button key={s.value} onClick={() => setMusicStyle(s.value)} style={{
            ...selBtn(musicStyle === s.value, '#fbd155', 'rgba(251,209,85,0.2)'),
            display: 'flex', flexDirection: 'column', alignItems: 'center',
            padding: '10px 4px 8px', gap: 4,
          }}>
            <span style={{ fontSize: 22 }}>{s.emoji}</span>
            <span style={{ fontSize: 10, textAlign: 'center', lineHeight: 1.2 }}>{s.label}</span>
          </button>
        ))}
      </div>

      {/* Age Range */}
      <p style={{ fontWeight: 800, fontSize: 13, color: 'rgba(255,255,255,0.9)', textTransform: 'uppercase', letterSpacing: '0.5px', margin: '0 0 10px' }}>👶 Age Range</p>
      <div style={{ display: 'flex', gap: 8, marginBottom: 22 }}>
        {AGE_RANGES.map(a => (
          <button key={a.value} onClick={() => setAge(a.value)} style={{
            ...selBtn(age === a.value, '#4ecdc4', 'rgba(78,205,196,0.15)'),
            flex: 1, padding: '10px 6px',
            display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 2,
          }}>
            <span style={{ fontSize: 22 }}>{a.emoji}</span>
            <span style={{ fontSize: 12 }}>{a.label}</span>
            <span style={{ fontSize: 10, fontWeight: 400, color: '#64748b' }}>Ages {a.ages}</span>
          </button>
        ))}
      </div>

      {/* Accent */}
      <p style={{ fontWeight: 800, fontSize: 13, color: 'rgba(255,255,255,0.9)', textTransform: 'uppercase', letterSpacing: '0.5px', margin: '0 0 8px' }}>🎤 Singing Accent</p>
      <select
        value={accent}
        onChange={e => setAccent(e.target.value)}
        className="kids-select"
        style={{ marginBottom: 22 }}
      >
        <option value="">🌟 Default</option>
        {ACCENTS.map(a => <option key={a} value={a}>{a}</option>)}
      </select>

      {/* Character */}
      <p style={{ fontWeight: 800, fontSize: 13, color: 'rgba(255,255,255,0.9)', textTransform: 'uppercase', letterSpacing: '0.5px', margin: '0 0 8px' }}>
        🦁 Main Character{' '}
        <span style={{ fontWeight: 400, textTransform: 'none', fontSize: 12, color: '#94a3b8' }}>(optional)</span>
      </p>
      <input
        className="kids-input"
        placeholder="e.g. Bella the bunny, Leo the lion..."
        value={character}
        onChange={e => setCharacter(e.target.value)}
        style={{ marginBottom: 26 }}
      />

      {error && <p style={{ color: '#ef4444', fontWeight: 700, fontSize: 14, marginBottom: 12 }}>{error}</p>}

      <button
        className="kids-btn kids-btn-primary"
        style={{ width: '100%', opacity: canGenerate ? 1 : 0.45 }}
        disabled={!canGenerate || generating}
        onClick={handleGenerate}
      >
        {generating ? '✨ Making your song...' : '✨ Make My Song!'}
      </button>
    </div>
  );
}
