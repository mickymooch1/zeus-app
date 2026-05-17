import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { BeatsDashboardHeader } from '../components/BeatsDashboardHeader';
import { useAuth } from '../contexts/AuthContext';
import { BACKEND_URL } from '../brand';

const TABS = [
  { id: 'style',   label: '🎨 Style Inspiration' },
  { id: 'youtube', label: '▶️ Find Music' },
  { id: 'lyrics',  label: '📝 Find Lyrics' },
];

const TAB_PLACEHOLDERS = {
  style:   'e.g. "Kendrick Lamar" or "Hotel California"',
  youtube: 'e.g. "smooth jazz piano" or "UK drill 2024"',
  lyrics:  'e.g. "Billie Jean Michael Jackson" or "Shape of You Ed Sheeran"',
};

const TAB_DESCRIPTIONS = {
  style:   'Search an artist or song to extract their style — genre, tempo, mood, instruments. Then use it to generate your own song.',
  youtube: 'Find YouTube music videos for inspiration. Click "Use as inspiration" to pull the style into song generation.',
  lyrics:  'Search a song to understand its themes and writing style (no lyrics shown — copyright safe). Use it to write something similar.',
};

function parseStyleAnalysis(text) {
  const lines = text.split('\n').map(s => s.trim()).filter(Boolean);
  const result = {};
  for (const line of lines) {
    const m = line.match(/^(GENRE|TEMPO|MOOD|INSTRUMENTS|STYLE):\s*(.+)$/i);
    if (m) result[m[1].toUpperCase()] = m[2].trim();
  }
  return result;
}

function parseLyricsAnalysis(text) {
  const styleMatch = text.match(/^STYLE:\s*(.+)$/im);
  const summary = text.replace(/^STYLE:.*$/im, '').trim();
  return {
    summary,
    style: styleMatch ? styleMatch[1].trim() : '',
  };
}

export default function SearchPage() {
  const navigate = useNavigate();
  const { token } = useAuth();
  const [tab, setTab] = useState('style');
  const [query, setQuery] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [result, setResult] = useState(null);

  const handleSearch = async (e) => {
    e.preventDefault();
    if (!query.trim()) return;
    setLoading(true);
    setError('');
    setResult(null);

    try {
      const res = await fetch(`${BACKEND_URL}/api/search/music`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({ query: query.trim(), search_type: tab }),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: 'Search failed' }));
        throw new Error(err.detail || 'Search failed');
      }
      const data = await res.json();
      setResult(data);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const goToSongs = ({ style = '', genre = '', tempo = '', mood = '' } = {}) => {
    navigate('/songs', { state: { prefillStyle: style, prefillGenre: genre, prefillTempo: tempo, prefillMood: mood } });
  };

  return (
    <div style={{ minHeight: '100vh', background: '#000', display: 'flex', flexDirection: 'column' }}>
      <BeatsDashboardHeader />

      <div style={{ maxWidth: 860, margin: '0 auto', padding: '32px 24px 80px', width: '100%' }}>
        <h1 style={{
          fontFamily: "'Orbitron', sans-serif",
          fontSize: 'clamp(24px, 5vw, 40px)',
          fontWeight: 900,
          background: 'linear-gradient(90deg, #00f0ff 0%, #00bfff 50%, #00f0ff 100%)',
          WebkitBackgroundClip: 'text',
          WebkitTextFillColor: 'transparent',
          backgroundClip: 'text',
          marginBottom: 10,
          letterSpacing: '-0.5px',
          textShadow: 'none',
          lineHeight: 1.1,
        }}>Find Your Sound</h1>
        <p style={{ color: '#888', fontSize: 14, marginBottom: 32, lineHeight: 1.6, maxWidth: 620 }}>
          Search artists, genres or tracks for inspiration, then generate original songs with the same energy — from Grime and Garage to Afrobeats, Jungle and Drill.
        </p>

        {/* Tabs */}
        <div style={{ display: 'flex', gap: 4, marginBottom: 28, borderBottom: '1px solid rgba(0,240,255,0.12)' }}>
          {TABS.map(t => (
            <button
              key={t.id}
              onClick={() => { setTab(t.id); setResult(null); setError(''); setQuery(''); }}
              style={{
                padding: '10px 18px',
                background: tab === t.id ? 'rgba(0,240,255,0.10)' : 'transparent',
                border: 'none',
                borderBottom: tab === t.id ? '2px solid #00f0ff' : '2px solid transparent',
                color: tab === t.id ? '#00f0ff' : '#666',
                fontWeight: tab === t.id ? 700 : 500,
                fontSize: 13,
                cursor: 'pointer',
                borderRadius: '6px 6px 0 0',
                transition: 'all 0.15s',
                whiteSpace: 'nowrap',
              }}
            >
              {t.label}
            </button>
          ))}
        </div>

        {/* Tab description */}
        <p style={{ color: '#555', fontSize: 13, marginBottom: 20 }}>
          {TAB_DESCRIPTIONS[tab]}
        </p>

        {/* Search form */}
        <form onSubmit={handleSearch} style={{ display: 'flex', gap: 10, marginBottom: 28 }}>
          <input
            value={query}
            onChange={e => setQuery(e.target.value)}
            placeholder={TAB_PLACEHOLDERS[tab]}
            style={{
              flex: 1,
              background: 'rgba(255,255,255,0.04)',
              border: '1px solid rgba(0,240,255,0.20)',
              borderRadius: 10,
              padding: '12px 16px',
              color: '#fff',
              fontSize: 14,
              outline: 'none',
            }}
            onFocus={e => { e.target.style.borderColor = 'rgba(0,240,255,0.5)'; }}
            onBlur={e => { e.target.style.borderColor = 'rgba(0,240,255,0.20)'; }}
          />
          <button
            type="submit"
            disabled={loading || !query.trim()}
            style={{
              padding: '12px 24px',
              background: loading ? 'rgba(0,240,255,0.3)' : '#00f0ff',
              color: '#000',
              fontWeight: 700,
              fontSize: 14,
              border: 'none',
              borderRadius: 10,
              cursor: loading ? 'not-allowed' : 'pointer',
              transition: 'all 0.2s',
              whiteSpace: 'nowrap',
            }}
          >
            {loading ? 'Searching…' : 'Search'}
          </button>
        </form>

        {/* Error */}
        {error && (
          <div style={{
            background: 'rgba(239,68,68,0.12)',
            border: '1px solid rgba(239,68,68,0.3)',
            borderRadius: 8,
            padding: '10px 14px',
            color: '#fca5a5',
            fontSize: 13,
            marginBottom: 24,
          }}>
            {error}
          </div>
        )}

        {/* Results */}
        {result && result.search_type === 'style' && (
          <StyleResult data={result} query={query} onUse={goToSongs} />
        )}
        {result && result.search_type === 'youtube' && (
          <YoutubeResults data={result} onUse={goToSongs} />
        )}
        {result && result.search_type === 'lyrics' && (
          <LyricsResult data={result} query={query} onUse={goToSongs} />
        )}
      </div>
    </div>
  );
}

function StyleResult({ data, query, onUse }) {
  const parsed = parseStyleAnalysis(data.analysis || '');
  const styleString = parsed.STYLE || data.analysis;

  return (
    <div style={{
      background: '#0d0d0d',
      border: '1px solid rgba(0,240,255,0.20)',
      borderRadius: 16,
      padding: 28,
    }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 20, gap: 12, flexWrap: 'wrap' }}>
        <div>
          <div style={{ fontSize: 11, fontWeight: 600, color: '#00f0ff', letterSpacing: '0.08em', textTransform: 'uppercase', marginBottom: 4 }}>Style Breakdown</div>
          <h3 style={{ fontSize: 18, fontWeight: 800, color: '#fff', margin: 0 }}>{query}</h3>
        </div>
        <button
          onClick={() => onUse({ style: styleString, genre: parsed.GENRE || '', tempo: parsed.TEMPO || '', mood: parsed.MOOD || '' })}
          style={{
            padding: '10px 20px',
            background: '#00f0ff',
            color: '#000',
            fontWeight: 700,
            fontSize: 13,
            border: 'none',
            borderRadius: 999,
            cursor: 'pointer',
            whiteSpace: 'nowrap',
          }}
        >
          Generate a song like this →
        </button>
      </div>

      {parsed.GENRE || parsed.TEMPO || parsed.MOOD || parsed.INSTRUMENTS ? (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(180px, 1fr))', gap: 12, marginBottom: 20 }}>
          {[
            { label: 'Genre',       value: parsed.GENRE },
            { label: 'Tempo',       value: parsed.TEMPO },
            { label: 'Mood',        value: parsed.MOOD },
            { label: 'Instruments', value: parsed.INSTRUMENTS },
          ].filter(r => r.value).map(row => (
            <div key={row.label} style={{
              background: 'rgba(0,240,255,0.05)',
              border: '1px solid rgba(0,240,255,0.12)',
              borderRadius: 10,
              padding: '12px 14px',
            }}>
              <div style={{ fontSize: 10, fontWeight: 600, color: '#00f0ff', letterSpacing: '0.08em', textTransform: 'uppercase', marginBottom: 4 }}>{row.label}</div>
              <div style={{ fontSize: 13, color: '#ddd' }}>{row.value}</div>
            </div>
          ))}
        </div>
      ) : null}

      {parsed.STYLE && (
        <div>
          <div style={{ fontSize: 10, fontWeight: 600, color: '#666', letterSpacing: '0.08em', textTransform: 'uppercase', marginBottom: 8 }}>Style descriptors</div>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
            {parsed.STYLE.split(',').map(s => s.trim()).filter(Boolean).map(tag => (
              <span key={tag} style={{
                background: 'rgba(0,240,255,0.08)',
                border: '1px solid rgba(0,240,255,0.18)',
                borderRadius: 999,
                padding: '4px 10px',
                fontSize: 12,
                color: '#00f0ff',
              }}>{tag}</span>
            ))}
          </div>
        </div>
      )}

      {!parsed.GENRE && !parsed.STYLE && (
        <p style={{ color: '#888', fontSize: 13, lineHeight: 1.6 }}>{data.analysis}</p>
      )}
    </div>
  );
}

function YoutubeResults({ data, onUse }) {
  const results = data.results || [];
  if (!results.length) {
    return <p style={{ color: '#666', fontSize: 14 }}>No YouTube results found. Try a different search.</p>;
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
      {results.map((r, i) => (
        <div key={i} style={{
          background: '#0d0d0d',
          border: '1px solid rgba(0,240,255,0.15)',
          borderRadius: 14,
          padding: 16,
          display: 'flex',
          gap: 16,
          alignItems: 'flex-start',
        }}>
          {r.thumbnail && (
            <a href={r.link} target="_blank" rel="noopener noreferrer" style={{ flexShrink: 0 }}>
              <img
                src={r.thumbnail}
                alt={r.title}
                style={{ width: 120, height: 68, objectFit: 'cover', borderRadius: 8, display: 'block' }}
                onError={e => { e.target.style.display = 'none'; }}
              />
            </a>
          )}
          <div style={{ flex: 1, minWidth: 0 }}>
            <a
              href={r.link}
              target="_blank"
              rel="noopener noreferrer"
              style={{ color: '#fff', fontWeight: 700, fontSize: 14, textDecoration: 'none', display: 'block', marginBottom: 4 }}
            >
              {r.title}
            </a>
            {r.snippet && (
              <p style={{ color: '#666', fontSize: 12, margin: '0 0 10px', lineHeight: 1.5, overflow: 'hidden', display: '-webkit-box', WebkitLineClamp: 2, WebkitBoxOrient: 'vertical' }}>
                {r.snippet}
              </p>
            )}
            <button
              onClick={() => onUse({ style: `${r.title} inspired style` })}
              style={{
                padding: '6px 14px',
                background: 'transparent',
                border: '1px solid rgba(0,240,255,0.30)',
                borderRadius: 999,
                color: '#00f0ff',
                fontSize: 12,
                fontWeight: 600,
                cursor: 'pointer',
                transition: 'all 0.15s',
              }}
              onMouseOver={e => { e.target.style.background = 'rgba(0,240,255,0.10)'; }}
              onMouseOut={e => { e.target.style.background = 'transparent'; }}
            >
              Use as inspiration →
            </button>
          </div>
        </div>
      ))}
    </div>
  );
}

function LyricsResult({ data, query, onUse }) {
  const { summary, style } = parseLyricsAnalysis(data.analysis || '');

  return (
    <div style={{
      background: '#0d0d0d',
      border: '1px solid rgba(255,0,153,0.20)',
      borderRadius: 16,
      padding: 28,
    }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 20, gap: 12, flexWrap: 'wrap' }}>
        <div>
          <div style={{ fontSize: 11, fontWeight: 600, color: '#ff0099', letterSpacing: '0.08em', textTransform: 'uppercase', marginBottom: 4 }}>Song Analysis</div>
          <h3 style={{ fontSize: 18, fontWeight: 800, color: '#fff', margin: 0 }}>{query}</h3>
        </div>
        <button
          onClick={() => onUse({ style: style || query + ' inspired style' })}
          style={{
            padding: '10px 20px',
            background: '#ff0099',
            color: '#fff',
            fontWeight: 700,
            fontSize: 13,
            border: 'none',
            borderRadius: 999,
            cursor: 'pointer',
            whiteSpace: 'nowrap',
          }}
        >
          Write me something similar →
        </button>
      </div>

      {summary && (
        <p style={{ color: '#ccc', fontSize: 14, lineHeight: 1.7, marginBottom: style ? 20 : 0 }}>
          {summary}
        </p>
      )}

      {style && (
        <div>
          <div style={{ fontSize: 10, fontWeight: 600, color: '#666', letterSpacing: '0.08em', textTransform: 'uppercase', marginBottom: 8 }}>Musical style</div>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
            {style.split(',').map(s => s.trim()).filter(Boolean).map(tag => (
              <span key={tag} style={{
                background: 'rgba(255,0,153,0.08)',
                border: '1px solid rgba(255,0,153,0.18)',
                borderRadius: 999,
                padding: '4px 10px',
                fontSize: 12,
                color: '#ff0099',
              }}>{tag}</span>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
