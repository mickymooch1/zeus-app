import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../../contexts/AuthContext';
import { BACKEND_URL } from '../../brand';

const THEMES = [
  { emoji: '🐉', label: 'Dragons' },
  { emoji: '🧚', label: 'Fairies' },
  { emoji: '🌙', label: 'Bedtime' },
  { emoji: '🏴‍☠️', label: 'Pirates' },
  { emoji: '🦄', label: 'Unicorns' },
  { emoji: '🌳', label: 'Forest' },
];

const AGE_RANGES = [
  { value: 'tiny_tots',   label: '👶 Tiny Tots',   sub: 'Ages 2–4' },
  { value: 'little_ones', label: '🧒 Little Ones',  sub: 'Ages 4–6' },
  { value: 'big_kids',    label: '🧑 Big Kids',     sub: 'Ages 7–10' },
];

const LANGUAGES = [
  { value: 'english',    flag: '🇬🇧', label: 'English' },
  { value: 'spanish',    flag: '🇪🇸', label: 'Spanish' },
  { value: 'french',     flag: '🇫🇷', label: 'French' },
  { value: 'german',     flag: '🇩🇪', label: 'German' },
  { value: 'italian',    flag: '🇮🇹', label: 'Italian' },
  { value: 'portuguese', flag: '🇵🇹', label: 'Portuguese' },
];

export default function KidsStoryMode() {
  const { token } = useAuth();
  const navigate = useNavigate();
  const [theme, setTheme] = useState(null);
  const [age, setAge] = useState('little_ones');
  const [language, setLanguage] = useState('english');
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
          brief: `A magical ${THEMES[theme].label.toLowerCase()} story for children`,
          genres: ['childrens', 'storytelling'],
          kids_story: true,
          kids_mode: 'story',
          kids_age_range: age,
          story_language: language,
          explicit: false,
        }),
      });
      if (!res.ok) {
        const d = await res.json().catch(() => ({}));
        throw new Error(d.detail || 'Could not make the story');
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

      <h2 style={{ margin: '0 0 6px', fontSize: 22 }}>What's the story about? 📖</h2>
      <p style={{ margin: '0 0 20px', color: '#64748b', fontSize: 14 }}>Pick a theme and we'll tell you a magical story!</p>

      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 10, justifyContent: 'center', marginBottom: 24 }}>
        {THEMES.map((t, i) => (
          <button key={i} className={`kids-tile${theme === i ? ' selected' : ''}`} onClick={() => setTheme(i)}>
            {t.emoji}
            <span>{t.label}</span>
          </button>
        ))}
      </div>

      <p style={{ fontWeight: 700, fontSize: 14, margin: '0 0 10px' }}>Who is the story for?</p>
      <div style={{ display: 'flex', gap: 8, marginBottom: 20, flexWrap: 'wrap' }}>
        {AGE_RANGES.map(a => (
          <button
            key={a.value}
            onClick={() => setAge(a.value)}
            style={{
              flex: '1 1 90px', padding: '10px 8px', borderRadius: 16,
              border: `2px solid ${age === a.value ? '#fbd155' : 'rgba(69,183,209,0.3)'}`,
              background: age === a.value ? 'rgba(251,209,85,0.15)' : 'rgba(255,255,255,0.7)',
              cursor: 'pointer', fontFamily: 'Nunito, sans-serif', fontWeight: 700, fontSize: 13, color: '#1a2b4a',
            }}
          >
            {a.label}<br/><span style={{ fontSize: 11, fontWeight: 400, color: '#64748b' }}>{a.sub}</span>
          </button>
        ))}
      </div>

      <p style={{ fontWeight: 700, fontSize: 14, margin: '0 0 10px' }}>Story language</p>
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8, marginBottom: 24 }}>
        {LANGUAGES.map(l => (
          <button
            key={l.value}
            onClick={() => setLanguage(l.value)}
            style={{
              padding: '8px 14px', borderRadius: 12,
              border: `2px solid ${language === l.value ? '#4ecdc4' : 'rgba(69,183,209,0.25)'}`,
              background: language === l.value ? 'rgba(78,205,196,0.15)' : 'rgba(255,255,255,0.7)',
              cursor: 'pointer', fontFamily: 'Nunito, sans-serif', fontWeight: 700, fontSize: 13, color: '#1a2b4a',
            }}
          >
            {l.flag} {l.label}
          </button>
        ))}
      </div>

      {error && <p style={{ color: '#ef4444', fontWeight: 700, fontSize: 14, marginBottom: 12 }}>{error}</p>}

      <button
        className="kids-btn kids-btn-coral"
        style={{ width: '100%', opacity: canGenerate ? 1 : 0.5 }}
        disabled={!canGenerate || generating}
        onClick={handleGenerate}
      >
        {generating ? '📖 Creating your story...' : '📖 Tell My Story!'}
      </button>
    </div>
  );
}
