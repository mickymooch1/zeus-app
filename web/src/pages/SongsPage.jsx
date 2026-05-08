import { useEffect, useRef, useState } from 'react';
import { Link } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';

const BACKEND_URL = import.meta.env.VITE_BACKEND_URL || '';

const GENRES = ['country', 'reggae', 'pop', 'rock', 'hiphop', 'lofi', 'edm', 'acoustic', 'irishjig', 'irishfolk'];
const GENRE_LABEL = { hiphop: 'Hip-hop', lofi: 'Lo-Fi', edm: 'EDM', irishjig: 'Irish Jig', irishfolk: 'Irish Folk' };
const GENRE_DISPLAY = (g) => GENRE_LABEL[g] || g.charAt(0).toUpperCase() + g.slice(1);

const STATUS_CLASS = {
  pending:    'badge-status badge-status--pending',
  generating: 'badge-status badge-status--running',
  complete:   'badge-status badge-status--done',
  failed:     'badge-status badge-status--failed',
};

function VariantCard({ variant }) {
  const isDone = variant.status === 'complete';
  const isFailed = variant.status === 'failed';
  const cardClass = `task-card ${isDone ? 'task-card--done' : isFailed ? 'task-card--failed' : 'task-card--running'}`;

  return (
    <div className={cardClass} style={{ marginBottom: 8 }}>
      <div className="task-card-header">
        <span style={{ fontWeight: 600, textTransform: 'capitalize' }}>
          {GENRE_DISPLAY(variant.genre_tag)}
          {variant.take_number > 1 && <span style={{ color: '#888', fontSize: 12 }}> · take {variant.take_number}</span>}
        </span>
        <span className={STATUS_CLASS[variant.status] || 'badge-status'}>
          {variant.status}
        </span>
      </div>
      {isDone && variant.mp3_url && (
        <div style={{ padding: '8px 16px 12px' }}>
          <audio
            controls
            src={variant.mp3_url}
            style={{ width: '100%', accentColor: '#a78bfa' }}
          />
          {variant.duration_seconds > 0 && (
            <span className="task-card-meta">{variant.duration_seconds}s</span>
          )}
        </div>
      )}
      {isFailed && (
        <div style={{ padding: '4px 16px 12px' }}>
          <span style={{ color: '#f87171', fontSize: 13 }}>Generation failed — credit not refunded</span>
        </div>
      )}
    </div>
  );
}

function ActiveJob({ job }) {
  const allDone = job.variants.every((v) => v.status === 'complete' || v.status === 'failed');
  const doneCount = job.variants.filter((v) => v.status === 'complete').length;

  return (
    <div style={{ marginBottom: 32 }}>
      <div style={{ display: 'flex', alignItems: 'baseline', gap: 12, marginBottom: 12 }}>
        <h2 style={{ color: '#e2d9f3', margin: 0, fontSize: '1rem', fontWeight: 700 }}>
          {job.title}
        </h2>
        <span style={{ color: '#888', fontSize: 13 }}>
          {allDone ? `${doneCount} of ${job.variants.length} ready` : 'Generating…'}
        </span>
      </div>
      {job.variants.map((v) => (
        <VariantCard key={v.variant_id} variant={v} />
      ))}
    </div>
  );
}

function HistoryItem({ lyric, token }) {
  const [variants, setVariants] = useState(null);
  const [loading, setLoading] = useState(false);
  const [open, setOpen] = useState(false);

  const toggle = async () => {
    if (open) { setOpen(false); return; }
    setOpen(true);
    if (variants !== null) return;
    setLoading(true);
    try {
      const res = await fetch(`${BACKEND_URL}/api/lyrics/${lyric.id}/variants`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (res.ok) {
        const data = await res.json();
        setVariants(data.variants);
      }
    } finally {
      setLoading(false);
    }
  };

  const date = lyric.created_at
    ? new Date(lyric.created_at).toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: 'numeric' })
    : '';

  return (
    <div className="task-card" style={{ marginBottom: 8 }}>
      <div
        className="task-card-header"
        style={{ cursor: 'pointer', userSelect: 'none' }}
        onClick={toggle}
      >
        <span style={{ fontWeight: 600, color: '#e2d9f3' }}>
          {lyric.title || `Lyric #${lyric.id}`}
        </span>
        <span style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          {date && <span className="task-card-meta">{date}</span>}
          <span style={{ color: '#666', fontSize: 12 }}>{open ? '▲' : '▼'}</span>
        </span>
      </div>
      {open && (
        <div style={{ padding: '4px 16px 12px' }}>
          {loading && <p style={{ color: '#888', fontSize: 13 }}>Loading…</p>}
          {!loading && variants && variants.length === 0 && (
            <p style={{ color: '#888', fontSize: 13 }}>No variants yet.</p>
          )}
          {!loading && variants && variants.map((v) => (
            <VariantCard key={v.variant_id} variant={v} />
          ))}
        </div>
      )}
    </div>
  );
}

export default function SongsPage() {
  const { token, user } = useAuth();

  const [credits, setCredits] = useState({ balance: 0, monthly_allowance: 0 });
  const [brief, setBrief] = useState('');
  const [selectedGenres, setSelectedGenres] = useState(new Set());
  const [generating, setGenerating] = useState(false);
  const [activeJob, setActiveJob] = useState(null);
  const [history, setHistory] = useState([]);
  const [error, setError] = useState('');

  const pollTimerRef = useRef(null);

  const cost = selectedGenres.size;
  const canAfford = credits.balance >= cost && cost > 0;
  const canGenerate = brief.trim().length > 0 && cost > 0 && canAfford && !generating;

  const fetchCredits = async () => {
    try {
      const res = await fetch(`${BACKEND_URL}/api/users/me/song_credits`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (res.ok) setCredits(await res.json());
    } catch (_) {}
  };

  const fetchHistory = async () => {
    try {
      const res = await fetch(`${BACKEND_URL}/api/lyrics`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (res.ok) {
        const data = await res.json();
        setHistory(data.lyrics || []);
      }
    } catch (_) {}
  };

  useEffect(() => {
    fetchCredits();
    fetchHistory();
  }, [token]); // eslint-disable-line react-hooks/exhaustive-deps

  // Polling — reschedule while any variant is still in progress
  useEffect(() => {
    if (!activeJob) return;

    const allSettled = activeJob.variants.every(
      (v) => v.status === 'complete' || v.status === 'failed'
    );

    if (allSettled) {
      fetchCredits();
      fetchHistory();
      return;
    }

    pollTimerRef.current = setTimeout(async () => {
      try {
        const res = await fetch(
          `${BACKEND_URL}/api/lyrics/${activeJob.lyric_id}/variants`,
          { headers: { Authorization: `Bearer ${token}` } }
        );
        if (res.ok) {
          const data = await res.json();
          setActiveJob((prev) => prev && ({ ...prev, variants: data.variants }));
        }
      } catch (_) {}
    }, 5000);

    return () => clearTimeout(pollTimerRef.current);
  }, [activeJob, token]); // eslint-disable-line react-hooks/exhaustive-deps

  const toggleGenre = (genre) => {
    setSelectedGenres((prev) => {
      const next = new Set(prev);
      if (next.has(genre)) next.delete(genre);
      else next.add(genre);
      return next;
    });
  };

  const handleGenerate = async () => {
    setError('');
    setGenerating(true);
    try {
      const res = await fetch(`${BACKEND_URL}/api/songs/generate`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({
          brief: brief.trim(),
          genres: Array.from(selectedGenres),
        }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || 'Generation failed');
      setActiveJob({ lyric_id: data.lyric_id, title: data.title, variants: data.variants });
      setCredits((prev) => ({ ...prev, balance: Math.max(0, prev.balance - cost) }));
      setBrief('');
      setSelectedGenres(new Set());
    } catch (err) {
      setError(err.message);
    } finally {
      setGenerating(false);
    }
  };

  const creditLabel = `${credits.balance} song${credits.balance !== 1 ? 's' : ''} remaining this month`;
  const creditExceeded = cost > 0 && cost > credits.balance;

  return (
    <div className="tasks-page">
      {/* Header */}
      <header className="dashboard-header">
        <Link to="/dashboard" className="dashboard-logo">
          <span className="zeus-icon">⚡</span>
          <span className="zeus-title">Zeus</span>
        </Link>
        <nav className="dashboard-header-right">
          <Link to="/dashboard" className="dashboard-header-link">Chat</Link>
          <Link to="/songs" className="dashboard-header-link" style={{ fontWeight: 600 }}>Songs</Link>
          <Link to="/websites" className="dashboard-header-link">Websites</Link>
          <Link to="/tasks" className="dashboard-header-link">Tasks</Link>
          <Link to="/billing" className="dashboard-header-link">{user?.email}</Link>
        </nav>
      </header>

      <div style={{ maxWidth: 760, margin: '0 auto', padding: '32px 24px' }}>

        {/* Credit banner */}
        <div style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          background: credits.balance === 0 ? 'rgba(251,191,36,0.08)' : 'rgba(167,139,250,0.08)',
          border: `1px solid ${credits.balance === 0 ? 'rgba(251,191,36,0.25)' : 'rgba(167,139,250,0.2)'}`,
          borderRadius: 8,
          padding: '12px 16px',
          marginBottom: 28,
        }}>
          <span style={{ color: credits.balance === 0 ? '#fbbf24' : '#a78bfa', fontWeight: 600, fontSize: 14 }}>
            {creditLabel}
          </span>
          {credits.balance === 0 && (
            <Link to="/billing" style={{ color: '#fbbf24', fontSize: 13, textDecoration: 'underline' }}>
              Upgrade for more →
            </Link>
          )}
        </div>

        {/* Generator form */}
        <section style={{ marginBottom: 36 }}>
          <h1 style={{ color: '#e2d9f3', fontSize: '1.4rem', fontWeight: 700, marginBottom: 4 }}>
            Song Generator
          </h1>
          <p style={{ color: '#888', fontSize: 14, marginBottom: 20 }}>
            Describe your song and pick genres — Zeus writes the lyrics and Suno turns them into MP3s.
          </p>

          <label className="form-label" style={{ display: 'block', marginBottom: 16 }}>
            Song brief
            <textarea
              className="form-input"
              rows={3}
              placeholder="e.g. An upbeat jingle for a Manchester coffee shop with Friday-morning energy…"
              value={brief}
              onChange={(e) => setBrief(e.target.value)}
              style={{ marginTop: 6, resize: 'vertical', fontFamily: 'inherit' }}
            />
          </label>

          <div style={{ marginBottom: 8 }}>
            <span className="form-label">Genres</span>
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8, marginTop: 8 }}>
              {GENRES.map((genre) => {
                const selected = selectedGenres.has(genre);
                return (
                  <button
                    key={genre}
                    type="button"
                    onClick={() => toggleGenre(genre)}
                    style={{
                      padding: '6px 14px',
                      borderRadius: 20,
                      border: `1px solid ${selected ? '#a78bfa' : 'rgba(167,139,250,0.25)'}`,
                      background: selected ? 'rgba(167,139,250,0.2)' : 'transparent',
                      color: selected ? '#c4b5fd' : '#888',
                      fontSize: 13,
                      fontWeight: selected ? 600 : 400,
                      cursor: 'pointer',
                      transition: 'all 0.15s',
                    }}
                  >
                    {GENRE_DISPLAY(genre)}
                  </button>
                );
              })}
            </div>
          </div>

          {/* Cost preview */}
          {cost > 0 && (
            <p style={{
              fontSize: 13,
              margin: '10px 0 16px',
              color: creditExceeded ? '#f87171' : '#888',
              fontWeight: creditExceeded ? 600 : 400,
            }}>
              Will use {cost} of your {credits.balance} remaining credit{credits.balance !== 1 ? 's' : ''}.
              {creditExceeded && ' Not enough credits — '}
              {creditExceeded && <Link to="/billing" style={{ color: '#f87171' }}>upgrade to continue</Link>}
            </p>
          )}
          {cost === 0 && <div style={{ height: 16 }} />}

          {/* Generate / Upgrade button */}
          {credits.balance === 0 && cost === 0 ? (
            <Link to="/billing" className="btn btn-primary">
              Upgrade to get more songs
            </Link>
          ) : (
            <button
              className="btn btn-primary"
              onClick={handleGenerate}
              disabled={!canGenerate}
              style={{ opacity: canGenerate ? 1 : 0.45 }}
            >
              {generating ? 'Generating lyrics…' : `Generate${cost > 0 ? ` (${cost} credit${cost !== 1 ? 's' : ''})` : ''}`}
            </button>
          )}

          {error && <p className="form-error" style={{ marginTop: 12 }}>{error}</p>}
        </section>

        {/* Active job results */}
        {activeJob && <ActiveJob job={activeJob} />}

        {/* Song history */}
        {history.length > 0 && (
          <section>
            <h2 style={{ color: '#e2d9f3', fontSize: '1rem', fontWeight: 700, marginBottom: 12 }}>
              Previous songs
            </h2>
            {history.map((lyric) => (
              <HistoryItem key={lyric.id} lyric={lyric} token={token} />
            ))}
          </section>
        )}

      </div>
    </div>
  );
}
