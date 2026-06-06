import { useState, useRef, useEffect, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../../contexts/AuthContext';
import { BACKEND_URL } from '../../brand';

const LANGUAGES = [
  { value: 'french',  flag: '🇫🇷', label: 'French'  },
  { value: 'spanish', flag: '🇪🇸', label: 'Spanish' },
  { value: 'german',  flag: '🇩🇪', label: 'German'  },
  { value: 'italian', flag: '🇮🇹', label: 'Italian' },
];

const TOPICS = [
  { value: 'days',      emoji: '📅', label: 'Days of the Week' },
  { value: 'numbers',   emoji: '🔢', label: 'Numbers 1–20'     },
  { value: 'colours',   emoji: '🎨', label: 'Colours'          },
  { value: 'animals',   emoji: '🐶', label: 'Animals'          },
  { value: 'food',      emoji: '🍎', label: 'Food'             },
  { value: 'greetings', emoji: '👋', label: 'Greetings'        },
  { value: 'family',    emoji: '👨‍👩‍👧', label: 'Family'          },
  { value: 'weather',   emoji: '🌦️', label: 'Weather'          },
];

function fmtTime(s) {
  if (!isFinite(s) || s < 0) return '0:00';
  const m = Math.floor(s / 60);
  const ss = String(Math.floor(s % 60)).padStart(2, '0');
  return `${m}:${ss}`;
}

// ── Lesson Player ─────────────────────────────────────────────────────────
function LessonPlayer({ audioUrl, words, language, topic, onBack }) {
  const [isPlaying, setIsPlaying] = useState(false);
  const [currentTime, setCurrentTime] = useState(0);
  const [duration, setDuration] = useState(0);
  const audioRef = useRef(null);
  const wordListRef = useRef(null);

  // Find active word pair
  const activePair = words.find((w, i) => {
    const nextStart = words[i + 1]?.foreign_start ?? Infinity;
    return currentTime >= w.foreign_start && currentTime < nextStart;
  }) ?? null;
  const showEnglish = activePair ? currentTime >= activePair.english_start : false;
  const activeIdx = activePair ? words.indexOf(activePair) : -1;

  useEffect(() => {
    const url = audioUrl.startsWith('http') ? audioUrl : `${BACKEND_URL}${audioUrl}`;
    const a = new Audio(url);
    audioRef.current = a;
    a.onloadedmetadata = () => setDuration(a.duration);
    a.ontimeupdate = () => setCurrentTime(a.currentTime);
    a.onended = () => { setIsPlaying(false); setCurrentTime(0); };
    return () => {
      a.pause();
      a.ontimeupdate = null;
      a.onended = null;
      audioRef.current = null;
    };
  }, [audioUrl]);

  // Scroll active word into view
  useEffect(() => {
    if (activeIdx < 0 || !wordListRef.current) return;
    const child = wordListRef.current.children[activeIdx];
    if (child) child.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
  }, [activeIdx]);

  const togglePlay = () => {
    const a = audioRef.current;
    if (!a) return;
    if (a.paused) { a.play(); setIsPlaying(true); }
    else          { a.pause(); setIsPlaying(false); }
  };

  const replay = () => {
    const a = audioRef.current;
    if (!a) return;
    a.currentTime = 0;
    a.play();
    setIsPlaying(true);
    setCurrentTime(0);
  };

  const langInfo = LANGUAGES.find(l => l.value === language);
  const topicInfo = TOPICS.find(t => t.value === topic);
  const pct = duration > 0 ? (currentTime / duration) * 100 : 0;

  return (
    <div style={{ flex: 1, display: 'flex', flexDirection: 'column', padding: '12px 20px 24px', maxWidth: 480, margin: '0 auto', width: '100%' }}>
      {/* Top bar */}
      <div style={{ display: 'flex', alignItems: 'center', marginBottom: 16 }}>
        <button onClick={onBack} style={{ background: 'none', border: 'none', color: '#45b7d1', fontWeight: 700, fontSize: 14, cursor: 'pointer', padding: 0 }}>
          ← Change lesson
        </button>
        <div style={{ marginLeft: 'auto', fontSize: 13, fontWeight: 700, color: 'rgba(255,255,255,0.7)', display: 'flex', alignItems: 'center', gap: 6 }}>
          {langInfo?.flag} {topicInfo?.emoji} {topicInfo?.label}
        </div>
      </div>

      {/* Big word display */}
      <div style={{
        borderRadius: 24, padding: '28px 24px',
        background: 'rgba(255,255,255,0.08)',
        border: '2px solid rgba(255,255,255,0.12)',
        marginBottom: 16, minHeight: 160,
        display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center',
        textAlign: 'center',
      }}>
        {activePair ? (
          <>
            <div style={{ fontSize: 13, fontWeight: 700, color: langInfo?.flag ? 'rgba(255,255,255,0.5)' : 'transparent', marginBottom: 8, letterSpacing: 1 }}>
              {langInfo?.flag} {langInfo?.label?.toUpperCase()}
            </div>
            <div style={{
              fontSize: 'clamp(28px, 8vw, 40px)', fontWeight: 900, color: '#fbd155',
              lineHeight: 1.2, marginBottom: 14,
              textShadow: '0 2px 12px rgba(251,209,85,0.4)',
            }}>
              {activePair.foreign}
            </div>
            <div style={{
              fontSize: 'clamp(18px, 5vw, 26px)', fontWeight: 700,
              color: 'rgba(255,255,255,0.9)', lineHeight: 1.3,
              opacity: showEnglish ? 1 : 0,
              transition: 'opacity 0.35s ease',
            }}>
              {activePair.english}
            </div>
          </>
        ) : (
          <>
            <div style={{ fontSize: 48, marginBottom: 8 }}>🌍</div>
            <div style={{ fontSize: 16, fontWeight: 700, color: 'rgba(255,255,255,0.6)' }}>
              {isPlaying ? 'Listening...' : 'Press play to start!'}
            </div>
          </>
        )}
      </div>

      {/* Progress indicator */}
      {words.length > 0 && (
        <div style={{ textAlign: 'center', fontSize: 12, fontWeight: 700, color: 'rgba(255,255,255,0.5)', marginBottom: 10 }}>
          {activeIdx >= 0 ? `${activeIdx + 1} / ${words.length}` : `${words.length} words`}
        </div>
      )}

      {/* Audio controls */}
      <div style={{ marginBottom: 16 }}>
        <div style={{ position: 'relative', height: 6, borderRadius: 6, background: 'rgba(255,255,255,0.15)', marginBottom: 6 }}>
          <div style={{
            position: 'absolute', left: 0, top: 0, bottom: 0, borderRadius: 6,
            width: `${pct}%`, background: 'linear-gradient(90deg, #fbd155, #ff6b6b)',
            transition: 'width 0.2s linear',
          }} />
        </div>
        <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 11, color: 'rgba(255,255,255,0.5)', fontWeight: 700 }}>
          <span>{fmtTime(currentTime)}</span>
          <span>{fmtTime(duration)}</span>
        </div>
      </div>

      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 16, marginBottom: 20 }}>
        <button
          onClick={replay}
          style={{
            width: 52, height: 52, borderRadius: '50%', border: 'none',
            background: 'rgba(255,255,255,0.15)', cursor: 'pointer',
            fontSize: 20, display: 'flex', alignItems: 'center', justifyContent: 'center',
          }}
          title="Restart"
        >
          ↩
        </button>
        <button
          onClick={togglePlay}
          style={{
            width: 68, height: 68, borderRadius: '50%', border: 'none',
            background: 'linear-gradient(135deg, #fbd155 0%, #ff6b6b 100%)',
            cursor: 'pointer', fontSize: 26,
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            boxShadow: '0 6px 24px rgba(251,209,85,0.45)',
          }}
        >
          {isPlaying ? '⏸' : '▶'}
        </button>
        <div style={{ width: 52, height: 52 }} />
      </div>

      {/* Word list */}
      <div
        ref={wordListRef}
        style={{
          flex: 1, overflowY: 'auto', display: 'flex', flexDirection: 'column', gap: 8,
          maxHeight: 240,
        }}
      >
        {words.map((w, i) => {
          const isActive = i === activeIdx;
          const isDone = currentTime > w.english_end && !isActive;
          return (
            <div
              key={i}
              style={{
                display: 'flex', alignItems: 'center', gap: 12, padding: '10px 14px',
                borderRadius: 12,
                background: isActive ? 'rgba(251,209,85,0.18)' : 'rgba(255,255,255,0.05)',
                border: `1px solid ${isActive ? 'rgba(251,209,85,0.5)' : 'rgba(255,255,255,0.08)'}`,
                transition: 'all 0.2s',
              }}
            >
              <span style={{ fontSize: 16, flexShrink: 0 }}>
                {isDone ? '✅' : isActive ? '🔊' : '○'}
              </span>
              <div style={{ flex: 1 }}>
                <div style={{
                  fontSize: 15, fontWeight: 800,
                  color: isActive ? '#fbd155' : isDone ? 'rgba(255,255,255,0.5)' : 'rgba(255,255,255,0.85)',
                }}>
                  {w.foreign}
                </div>
                <div style={{ fontSize: 12, fontWeight: 600, color: 'rgba(255,255,255,0.45)', marginTop: 1 }}>
                  {w.english}
                </div>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

// ── Main page ─────────────────────────────────────────────────────────────
export default function KidsLanguagePage() {
  const { token } = useAuth();
  const navigate = useNavigate();
  const [language, setLanguage] = useState('french');
  const [topic, setTopic] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [lesson, setLesson] = useState(null);  // { audioUrl, words }

  const canStart = language && topic !== null;

  const handleStart = useCallback(async () => {
    if (!canStart || loading) return;
    setLoading(true);
    setError('');
    try {
      const res = await fetch(`${BACKEND_URL}/api/kids/language`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
        body: JSON.stringify({ language, topic }),
      });
      if (!res.ok) {
        const d = await res.json().catch(() => ({}));
        throw new Error(d.detail || 'Could not load lesson');
      }
      const data = await res.json();
      setLesson({ audioUrl: data.audio_url, words: data.words });
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }, [canStart, language, topic, token, loading]);

  if (lesson) {
    return (
      <LessonPlayer
        audioUrl={lesson.audioUrl}
        words={lesson.words}
        language={language}
        topic={topic}
        onBack={() => setLesson(null)}
      />
    );
  }

  const langInfo = LANGUAGES.find(l => l.value === language);

  return (
    <div style={{ flex: 1, padding: '16px 20px 40px', maxWidth: 520, margin: '0 auto', width: '100%' }}>
      <button onClick={() => navigate('/kids')} style={{ background: 'none', border: 'none', color: '#45b7d1', fontWeight: 700, fontSize: 14, cursor: 'pointer', marginBottom: 16, padding: 0 }}>
        ← Back
      </button>

      <h2 style={{ margin: '0 0 4px', fontSize: 22 }}>Learn a Language 🌍</h2>
      <p style={{ margin: '0 0 22px', color: 'rgba(255,255,255,0.7)', fontSize: 14 }}>
        Listen and learn — each word in {langInfo?.label ?? 'the language'} then English!
      </p>

      {/* Language picker */}
      <p style={{ fontWeight: 800, fontSize: 13, color: 'rgba(255,255,255,0.9)', textTransform: 'uppercase', letterSpacing: '0.5px', margin: '0 0 10px' }}>
        🗣️ Pick a Language
      </p>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 8, marginBottom: 24 }}>
        {LANGUAGES.map(l => (
          <button
            key={l.value}
            onClick={() => setLanguage(l.value)}
            style={{
              display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 4,
              padding: '10px 4px 8px', borderRadius: 14, cursor: 'pointer',
              border: `2px solid ${language === l.value ? '#45b7d1' : 'rgba(0,0,0,0.1)'}`,
              background: language === l.value ? 'rgba(69,183,209,0.18)' : 'rgba(255,255,255,0.7)',
              fontFamily: 'Nunito, sans-serif',
            }}
          >
            <span style={{ fontSize: 24 }}>{l.flag}</span>
            <span style={{ fontSize: 11, fontWeight: language === l.value ? 800 : 600, color: language === l.value ? '#0369a1' : '#475569' }}>
              {l.label}
            </span>
          </button>
        ))}
      </div>

      {/* Topic picker */}
      <p style={{ fontWeight: 800, fontSize: 13, color: 'rgba(255,255,255,0.9)', textTransform: 'uppercase', letterSpacing: '0.5px', margin: '0 0 10px' }}>
        📚 What do you want to learn?
      </p>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: 10, marginBottom: 24 }}>
        {TOPICS.map(t => (
          <button
            key={t.value}
            onClick={() => setTopic(t.value)}
            style={{
              display: 'flex', alignItems: 'center', gap: 10,
              padding: '12px 14px', borderRadius: 14, cursor: 'pointer', textAlign: 'left',
              border: `2px solid ${topic === t.value ? '#fbd155' : 'rgba(0,0,0,0.1)'}`,
              background: topic === t.value ? 'rgba(251,209,85,0.18)' : 'rgba(255,255,255,0.7)',
              fontFamily: 'Nunito, sans-serif',
            }}
          >
            <span style={{ fontSize: 22 }}>{t.emoji}</span>
            <span style={{ fontSize: 13, fontWeight: topic === t.value ? 800 : 600, color: topic === t.value ? '#92400e' : '#475569' }}>
              {t.label}
            </span>
          </button>
        ))}
      </div>

      {error && <p style={{ color: '#ef4444', fontWeight: 700, fontSize: 14, marginBottom: 12 }}>{error}</p>}

      <button
        className="kids-btn kids-btn-primary"
        style={{ width: '100%', opacity: canStart ? 1 : 0.45 }}
        disabled={!canStart || loading}
        onClick={handleStart}
      >
        {loading
          ? '🎧 Loading lesson...'
          : canStart
            ? `🎧 Start ${TOPICS.find(t => t.value === topic)?.label} in ${langInfo?.label}!`
            : '🌍 Pick a language and topic'}
      </button>
    </div>
  );
}
