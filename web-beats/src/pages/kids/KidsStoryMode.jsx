import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../../contexts/AuthContext';
import { BACKEND_URL } from '../../brand';

const STORY_THEMES = [
  { emoji: '🐉', label: 'Dragons' },
  { emoji: '🧚', label: 'Fairies' },
  { emoji: '🌙', label: 'Bedtime' },
  { emoji: '🏴‍☠️', label: 'Pirates' },
  { emoji: '🦄', label: 'Unicorns' },
  { emoji: '🌳', label: 'Forest' },
];

const AGE_RANGES = [
  { value: 'tiny_tots',   emoji: '🍼', label: 'Tiny Tots',   ages: '2–4' },
  { value: 'little_ones', emoji: '🌟', label: 'Little Ones', ages: '4–6' },
  { value: 'big_kids',    emoji: '📚', label: 'Big Kids',    ages: '7–10' },
];

const NARRATOR_VOICES = [
  ['british',    '🇬🇧', 'British',     'Default'],
  ['australian', '🦘',  'Australian',  'Warm'],
  ['newzealand', '🇳🇿', 'New Zealand', 'Clear'],
  ['indian',     '🇮🇳', 'Indian',      'Rich'],
  ['scouse',     '🎸',  'Scouse',      'Liverpool'],
  ['irish',      '🍀',  'Irish',       'Musical'],
  ['scottish',   '🏴󠁧󠁢󠁳󠁣󠁴󠁿', 'Scottish',   'Lively'],
  ['jamaican',   '🇯🇲', 'Jamaican',    'Caribbean'],
];

const HERO_VOICES = [
  ['younggirl',  '👧',  'Young Girl',  'Youthful'],
  ['youngboy',   '👦',  'Young Boy',   'Boyish'],
  ['australian', '🦘',  'Australian',  'Warm'],
  ['newzealand', '🇳🇿', 'New Zealand', 'Bright'],
  ['irish',      '🍀',  'Irish',       'Musical'],
  ['british',    '🇬🇧', 'British',     'Clear'],
  ['indian',     '🇮🇳', 'Indian',      'Rich'],
  ['scouse',     '🎸',  'Scouse',      'Cheeky'],
  ['scottish',   '🏴󠁧󠁢󠁳󠁣󠁴󠁿', 'Scottish',   'Lively'],
];

const CHARACTER_VOICES = [
  ['dragon',   '🐉',   'Dragon',   'Fierce'],
  ['villain',  '😈',   'Villain',  'Menacing'],
  ['fairy',    '🧚',   'Fairy',    'Magical'],
  ['cranky',   '👴',   'Cranky',   'Old man'],
  ['pirate',   '🏴‍☠️',  'Pirate',   'Swashbuckling'],
  ['wizard',   '🧙',   'Wizard',   'Wise'],
  ['raspy',    '👹',   'Raspy',    'Scary'],
  ['gnarly',   '🤙',   'Gnarly',   'Wild'],
  ['cockney',  '🎩',   'Cockney',  'London'],
  ['jamaican', '🇯🇲',  'Jamaican', 'Caribbean'],
];

const MUSIC_STYLES = [
  { value: 'piano',    emoji: '🎹', label: 'Gentle Piano',  genres: ['classical'] },
  { value: 'acoustic', emoji: '🎸', label: 'Soft Acoustic', genres: ['acoustic'] },
  { value: 'nursery',  emoji: '🎠', label: 'Nursery Tune',  genres: ['acoustic'] },
  { value: 'funpop',   emoji: '🎵', label: 'Light Pop',     genres: ['pop'] },
  { value: 'reggae',   emoji: '🏝️', label: 'Soft Reggae',  genres: ['reggae'] },
];

const LANGUAGES = [
  ['english', '🇬🇧', 'English'],
  ['french',  '🇫🇷', 'French'],
  ['spanish', '🇪🇸', 'Spanish'],
  ['german',  '🇩🇪', 'German'],
  ['italian', '🇮🇹', 'Italian'],
];

const voiceBtn = (active, borderColor, bgColor) => ({
  display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 3,
  padding: '10px 4px 8px', borderRadius: 12, cursor: 'pointer', transition: 'all 0.15s',
  border: `1px solid ${active ? borderColor : 'rgba(0,0,0,0.1)'}`,
  background: active ? bgColor : 'rgba(255,255,255,0.65)',
  width: '100%', fontFamily: 'Nunito, sans-serif',
});

export default function KidsStoryMode() {
  const { token } = useAuth();
  const navigate = useNavigate();
  const [theme, setTheme]             = useState(null);
  const [age, setAge]                 = useState('little_ones');
  const [narrator, setNarrator]       = useState('british');
  const [heroVoice, setHeroVoice]     = useState('younggirl');
  const [charVoice, setCharVoice]     = useState('');
  const [language, setLanguage]       = useState('english');
  const [musicStyle, setMusicStyle]   = useState('piano');
  const [mainCharacter, setMainChar]  = useState('');
  const [storyEvent, setStoryEvent]   = useState('');
  const [generating, setGenerating]   = useState(false);
  const [error, setError]             = useState('');

  const canGenerate = theme !== null;
  const selectedStyle = MUSIC_STYLES.find(s => s.value === musicStyle) ?? MUSIC_STYLES[0];

  const handleGenerate = async () => {
    if (!canGenerate || generating) return;
    setGenerating(true);
    setError('');
    try {
      const brief = [
        `A ${STORY_THEMES[theme].label.toLowerCase()} story for children`,
        mainCharacter.trim() && `Main character: ${mainCharacter.trim()}`,
        storyEvent.trim()    && `What happens: ${storyEvent.trim()}`,
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
          kids_mode: 'story',
          kids_age_range: age,
          accent: narrator,
          child_voice: heroVoice,
          character_voice: charVoice || undefined,
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

  const label = (text, sub) => (
    <p style={{ fontWeight: 800, fontSize: 13, color: '#1a2b4a', textTransform: 'uppercase', letterSpacing: '0.5px', margin: '0 0 10px' }}>
      {text}{sub && <span style={{ fontWeight: 400, textTransform: 'none', fontSize: 12, color: '#94a3b8', marginLeft: 6 }}>{sub}</span>}
    </p>
  );

  return (
    <div style={{ flex: 1, padding: '16px 20px 40px', maxWidth: 560, margin: '0 auto', width: '100%' }}>
      <button onClick={() => navigate('/kids')} style={{ background: 'none', border: 'none', color: '#45b7d1', fontWeight: 700, fontSize: 14, cursor: 'pointer', marginBottom: 16, padding: 0 }}>
        ← Back
      </button>

      <h2 style={{ margin: '0 0 4px', fontSize: 22 }}>What's the story about? 📖</h2>
      <p style={{ margin: '0 0 18px', color: '#64748b', fontSize: 14 }}>Pick a theme and we'll tell a magical story!</p>

      {/* Story Theme */}
      {label('🌈 Story Theme')}
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 10, justifyContent: 'center', marginBottom: 22 }}>
        {STORY_THEMES.map((t, i) => (
          <button key={i} className={`kids-tile${theme === i ? ' selected' : ''}`} onClick={() => setTheme(i)}>
            {t.emoji}<span>{t.label}</span>
          </button>
        ))}
      </div>

      {/* Optional character / event */}
      {label('🦁 Main Character', '(optional)')}
      <input className="kids-input" placeholder="e.g. Rosie the rabbit, Max the dragon..." value={mainCharacter} onChange={e => setMainChar(e.target.value)} style={{ marginBottom: 14 }} />
      {label('✨ What Happens?', '(optional)')}
      <textarea className="kids-input" placeholder="e.g. goes on a big adventure to find the magic rainbow cake" rows={2} value={storyEvent} onChange={e => setStoryEvent(e.target.value)} style={{ marginBottom: 22, resize: 'vertical' }} />

      {/* Age Range */}
      {label('👶 Age Range')}
      <div style={{ display: 'flex', gap: 8, marginBottom: 22 }}>
        {AGE_RANGES.map(a => (
          <button key={a.value} onClick={() => setAge(a.value)} style={{
            flex: 1, padding: '10px 6px', borderRadius: 14, cursor: 'pointer', transition: 'all 0.15s',
            border: `2px solid ${age === a.value ? '#fbd155' : 'rgba(0,0,0,0.1)'}`,
            background: age === a.value ? 'rgba(251,209,85,0.2)' : 'rgba(255,255,255,0.7)',
            fontFamily: 'Nunito, sans-serif', fontWeight: 700, color: '#1a2b4a',
            display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 2,
          }}>
            <span style={{ fontSize: 22 }}>{a.emoji}</span>
            <span style={{ fontSize: 12 }}>{a.label}</span>
            <span style={{ fontSize: 10, fontWeight: 400, color: '#64748b' }}>Ages {a.ages}</span>
          </button>
        ))}
      </div>

      {/* Narrator Voice */}
      {label('📖 Narrator Voice')}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 8, marginBottom: 22 }}>
        {NARRATOR_VOICES.map(([val, emoji, name, desc]) => (
          <button key={val} onClick={() => setNarrator(val)} style={voiceBtn(narrator === val, '#fbd155', 'rgba(251,209,85,0.2)')}>
            <span style={{ fontSize: 20 }}>{emoji}</span>
            <span style={{ fontSize: 11, fontWeight: narrator === val ? 800 : 600, color: narrator === val ? '#b45309' : '#475569' }}>{name}</span>
            <span style={{ fontSize: 9, color: '#94a3b8' }}>{desc}</span>
          </button>
        ))}
      </div>

      {/* Hero Voice */}
      {label('🧒 Main Character Voice')}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 8, marginBottom: 22 }}>
        {HERO_VOICES.map(([val, emoji, name, desc]) => (
          <button key={val} onClick={() => setHeroVoice(val)} style={voiceBtn(heroVoice === val, '#4ecdc4', 'rgba(78,205,196,0.18)')}>
            <span style={{ fontSize: 20 }}>{emoji}</span>
            <span style={{ fontSize: 11, fontWeight: heroVoice === val ? 800 : 600, color: heroVoice === val ? '#0d9488' : '#475569' }}>{name}</span>
            <span style={{ fontSize: 9, color: '#94a3b8' }}>{desc}</span>
          </button>
        ))}
      </div>

      {/* Character Voice (optional) */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 10 }}>
        <p style={{ fontWeight: 800, fontSize: 13, color: '#1a2b4a', textTransform: 'uppercase', letterSpacing: '0.5px', margin: 0 }}>🎭 Character Voice</p>
        <span style={{ fontSize: 11, color: '#94a3b8', fontStyle: 'italic' }}>optional — 3-voice mode</span>
        {charVoice && (
          <button onClick={() => setCharVoice('')} style={{ marginLeft: 'auto', background: 'none', border: '1px solid rgba(244,114,182,0.4)', borderRadius: 6, color: '#f472b6', fontSize: 10, cursor: 'pointer', padding: '2px 8px' }}>
            ✕ None
          </button>
        )}
      </div>
      {charVoice && (
        <div style={{ marginBottom: 8, padding: '6px 10px', borderRadius: 8, background: 'rgba(244,114,182,0.08)', border: '1px solid rgba(244,114,182,0.2)', fontSize: 11, color: '#f472b6', fontFamily: 'Nunito, sans-serif' }}>
          ✨ 3-voice mode — narrator, child hero &amp; {charVoice} each get their own voice
        </div>
      )}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 8, marginBottom: 22 }}>
        {CHARACTER_VOICES.map(([val, emoji, name, desc]) => (
          <button key={val} onClick={() => setCharVoice(v => v === val ? '' : val)} style={voiceBtn(charVoice === val, '#f472b6', 'rgba(244,114,182,0.18)')}>
            <span style={{ fontSize: 20 }}>{emoji}</span>
            <span style={{ fontSize: 11, fontWeight: charVoice === val ? 800 : 600, color: charVoice === val ? '#be185d' : '#475569' }}>{name}</span>
            <span style={{ fontSize: 9, color: '#94a3b8' }}>{desc}</span>
          </button>
        ))}
      </div>

      {/* Story Language */}
      {label('🌍 Story Language')}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(5, 1fr)', gap: 6, marginBottom: 22 }}>
        {LANGUAGES.map(([val, flag, lbl]) => (
          <button key={val} onClick={() => setLanguage(val)} style={{
            display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 3,
            padding: '8px 4px 6px', borderRadius: 10, cursor: 'pointer', transition: 'all 0.15s',
            border: `2px solid ${language === val ? '#45b7d1' : 'rgba(0,0,0,0.1)'}`,
            background: language === val ? 'rgba(69,183,209,0.15)' : 'rgba(255,255,255,0.7)',
            fontFamily: 'Nunito, sans-serif',
          }}>
            <span style={{ fontSize: 20 }}>{flag}</span>
            <span style={{ fontSize: 10, fontWeight: language === val ? 800 : 600, color: language === val ? '#0369a1' : '#475569' }}>{lbl}</span>
          </button>
        ))}
      </div>

      {/* Background Music */}
      {label('🎵 Background Music')}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(5, 1fr)', gap: 8, marginBottom: 26 }}>
        {MUSIC_STYLES.map(s => (
          <button key={s.value} onClick={() => setMusicStyle(s.value)} style={{
            display: 'flex', flexDirection: 'column', alignItems: 'center',
            padding: '10px 4px 8px', gap: 4, borderRadius: 12, cursor: 'pointer', transition: 'all 0.15s',
            border: `2px solid ${musicStyle === s.value ? '#c084fc' : 'rgba(0,0,0,0.1)'}`,
            background: musicStyle === s.value ? 'rgba(192,132,252,0.15)' : 'rgba(255,255,255,0.7)',
            fontFamily: 'Nunito, sans-serif',
          }}>
            <span style={{ fontSize: 22 }}>{s.emoji}</span>
            <span style={{ fontSize: 10, fontWeight: musicStyle === s.value ? 800 : 600, color: musicStyle === s.value ? '#7c3aed' : '#475569', textAlign: 'center', lineHeight: 1.2 }}>{s.label}</span>
          </button>
        ))}
      </div>

      {error && <p style={{ color: '#ef4444', fontWeight: 700, fontSize: 14, marginBottom: 12 }}>{error}</p>}

      <button
        className="kids-btn kids-btn-coral"
        style={{ width: '100%', opacity: canGenerate ? 1 : 0.45 }}
        disabled={!canGenerate || generating}
        onClick={handleGenerate}
      >
        {generating ? '📖 Creating your story...' : '📖 Tell My Story!'}
      </button>
    </div>
  );
}
