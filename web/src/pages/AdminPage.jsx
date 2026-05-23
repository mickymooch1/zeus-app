import { useEffect, useState, useCallback, useRef } from 'react';
import { Navbar } from '../components/Navbar';
import { useAuth } from '../contexts/AuthContext';

const BACKEND_URL = import.meta.env.VITE_BACKEND_URL || '';

const PLAN_OPTIONS = ['free', 'pro', 'agency', 'enterprise'];
const STATUS_OPTIONS = ['free', 'active', 'cancelled'];

function AdminCell({ userId, field, value, token, onSaved }) {
  const [current, setCurrent] = useState(value);
  const [saving, setSaving] = useState(false);
  const [flash, setFlash] = useState(null); // 'ok' | 'err'

  const options = field === 'subscription_plan' ? PLAN_OPTIONS : STATUS_OPTIONS;

  const handleChange = useCallback(async (e) => {
    const newVal = e.target.value;
    const prev = current;
    setCurrent(newVal);
    setSaving(true);
    setFlash(null);
    try {
      const res = await fetch(`${BACKEND_URL}/admin/users/${userId}`, {
        method: 'PATCH',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({ field, value: newVal }),
      });
      if (!res.ok) {
        setCurrent(prev);
        setFlash('err');
      } else {
        setFlash('ok');
        onSaved(userId, field, newVal);
      }
    } catch {
      setCurrent(prev);
      setFlash('err');
    } finally {
      setSaving(false);
      setTimeout(() => setFlash(null), 2000);
    }
  }, [current, field, token, userId, onSaved]);

  return (
    <td className={`admin-cell${saving ? ' admin-cell--saving' : ''}${flash === 'ok' ? ' admin-cell--saved' : ''}${flash === 'err' ? ' admin-cell--error' : ''}`}>
      <select
        className="admin-select"
        value={current}
        onChange={handleChange}
        disabled={saving}
      >
        {options.map((o) => (
          <option key={o} value={o}>{o}</option>
        ))}
      </select>
      {flash === 'ok' && <span className="admin-flash admin-flash--ok">✓</span>}
      {flash === 'err' && <span className="admin-flash admin-flash--err">✗</span>}
    </td>
  );
}

const TASK_STATUS_BADGE = {
  pending: { label: 'Pending', className: 'badge-status badge-status--pending' },
  running: { label: 'Running', className: 'badge-status badge-status--running' },
  done:    { label: 'Done',    className: 'badge-status badge-status--done'    },
  failed:  { label: 'Failed',  className: 'badge-status badge-status--failed'  },
};

function AdminTasksTab({ token }) {
  const [tasks, setTasks] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const pollRef = useRef(null);

  const fetchTasks = useCallback(async () => {
    try {
      const res = await fetch(`${BACKEND_URL}/admin/tasks`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!res.ok) throw new Error('Failed to load tasks');
      setTasks(await res.json());
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }, [token]);

  useEffect(() => {
    fetchTasks();
  }, [fetchTasks]);

  // Poll every 10s while any task is active
  useEffect(() => {
    const hasActive = tasks.some((t) => t.status === 'pending' || t.status === 'running');
    clearInterval(pollRef.current);
    if (hasActive) pollRef.current = setInterval(fetchTasks, 10_000);
    return () => clearInterval(pollRef.current);
  }, [tasks, fetchTasks]);

  if (error) return <div className="form-error form-error--banner">{error}</div>;

  if (loading) {
    return (
      <div style={{ textAlign: 'center', padding: '3rem' }}>
        <span className="spinner" />
      </div>
    );
  }

  if (tasks.length === 0) {
    return (
      <p style={{ textAlign: 'center', color: 'var(--text-dim)', padding: '3rem 0' }}>
        No background tasks yet.
      </p>
    );
  }

  return (
    <div className="admin-table-wrap">
      <table className="admin-table">
        <thead>
          <tr>
            <th>User</th>
            <th>Task</th>
            <th>Status</th>
            <th>Started</th>
          </tr>
        </thead>
        <tbody>
          {tasks.map((t) => {
            const badge = TASK_STATUS_BADGE[t.status] || TASK_STATUS_BADGE.pending;
            return (
              <tr key={t.id}>
                <td className="admin-email">{t.user_email || t.user_id}</td>
                <td style={{ maxWidth: '340px' }}>{t.description}</td>
                <td><span className={badge.className}>{badge.label}</span></td>
                <td className="admin-date">{new Date(t.created_at).toLocaleString()}</td>
              </tr>
            );
          })}
        </tbody>
      </table>
      <p className="admin-count">{tasks.length} task{tasks.length !== 1 ? 's' : ''}</p>
    </div>
  );
}

function SongStatsBar({ overview }) {
  if (!overview) return null;
  const stats = [
    { label: 'Total songs generated', value: overview.total_songs ?? 0 },
    { label: 'Songs this month',      value: overview.songs_this_month ?? 0 },
    { label: 'Most active (month)',   value: overview.most_active_user ?? '—' },
  ];
  return (
    <div style={{ display: 'flex', gap: 16, flexWrap: 'wrap', marginBottom: '1.5rem' }}>
      {stats.map(({ label, value }) => (
        <div key={label} style={{ flex: '1 1 180px', background: 'rgba(139,92,246,0.08)', border: '1px solid rgba(139,92,246,0.2)', borderRadius: 10, padding: '14px 18px' }}>
          <div style={{ fontSize: 22, fontWeight: 800, color: '#a78bfa' }}>{value}</div>
          <div style={{ fontSize: 11, color: '#555', marginTop: 4, textTransform: 'uppercase', letterSpacing: '0.06em' }}>{label}</div>
        </div>
      ))}
    </div>
  );
}

export default function AdminPage() {
  const { user, token } = useAuth();
  const [activeTab, setActiveTab] = useState('users');
  const [users, setUsers] = useState([]);
  const [overview, setOverview] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    if (!token) return;
    fetch(`${BACKEND_URL}/admin/users`, {
      headers: { Authorization: `Bearer ${token}` },
    })
      .then(async (res) => {
        if (res.status === 403) { setError('forbidden'); return; }
        if (!res.ok) throw new Error('Failed to load users');
        const data = await res.json();
        setUsers(data.users ?? data);
        setOverview(data.overview ?? null);
      })
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false));
  }, [token]);

  const handleSaved = useCallback((userId, field, newVal) => {
    setUsers((prev) =>
      prev.map((u) => (u.id === userId ? { ...u, [field]: newVal } : u))
    );
  }, []);

  if (!user?.is_admin) {
    return (
      <div className="admin-page">
        <Navbar />
        <div className="page admin-page-inner">
          <p className="admin-denied">Access denied.</p>
        </div>
      </div>
    );
  }

  return (
    <div className="admin-page">
      <Navbar />
      <div className="page admin-page-inner">
        <div className="hero-orbs" aria-hidden>
          <div className="orb orb-1" />
          <div className="orb orb-2" />
        </div>

        <div className="section-label" style={{ textAlign: 'center' }}>Internal</div>
        <h1 className="section-title" style={{ textAlign: 'center', marginBottom: '1.5rem' }}>
          Admin Dashboard
        </h1>

        <div className="tasks-tab-bar" role="tablist" aria-label="Admin views" style={{ marginBottom: '1.5rem' }}>
          <button
            role="tab"
            aria-selected={activeTab === 'users'}
            className={`tasks-tab-btn${activeTab === 'users' ? ' tasks-tab-btn--active' : ''}`}
            onClick={() => setActiveTab('users')}
          >
            Users
          </button>
          <button
            role="tab"
            aria-selected={activeTab === 'tasks'}
            className={`tasks-tab-btn${activeTab === 'tasks' ? ' tasks-tab-btn--active' : ''}`}
            onClick={() => setActiveTab('tasks')}
          >
            All Tasks
          </button>
        </div>

        {activeTab === 'users' && (
          <>
            {error === 'forbidden' && (
              <p className="admin-denied">403 — Admin access required.</p>
            )}
            {error && error !== 'forbidden' && (
              <div className="form-error form-error--banner">{error}</div>
            )}
            {!loading && <SongStatsBar overview={overview} />}
            {loading ? (
              <div style={{ textAlign: 'center', padding: '3rem' }}>
                <span className="spinner" />
              </div>
            ) : (
              <div className="admin-table-wrap">
                <table className="admin-table">
                  <thead>
                    <tr>
                      <th>Email</th>
                      <th>Name</th>
                      <th>Plan</th>
                      <th>Status</th>
                      <th>Msgs (mo)</th>
                      <th>Songs (all)</th>
                      <th>Songs (mo)</th>
                      <th>Credits</th>
                      <th>Last Song</th>
                      <th>Created</th>
                      <th>Admin</th>
                    </tr>
                  </thead>
                  <tbody>
                    {users.map((u) => (
                      <tr key={u.id}>
                        <td className="admin-email">{u.email}</td>
                        <td>{u.name || '—'}</td>
                        <AdminCell
                          userId={u.id}
                          field="subscription_plan"
                          value={u.subscription_plan || 'free'}
                          token={token}
                          onSaved={handleSaved}
                        />
                        <AdminCell
                          userId={u.id}
                          field="subscription_status"
                          value={u.subscription_status || 'free'}
                          token={token}
                          onSaved={handleSaved}
                        />
                        <td style={{ textAlign: 'center' }}>{u.messages_this_month ?? 0}</td>
                        <td style={{ textAlign: 'center' }}>{u.total_songs_generated ?? 0}</td>
                        <td style={{ textAlign: 'center' }}>{u.songs_this_month ?? 0}</td>
                        <td style={{ textAlign: 'center' }}>{u.credits_remaining ?? 0}</td>
                        <td className="admin-date">{u.last_song_at ? new Date(u.last_song_at).toLocaleDateString() : '—'}</td>
                        <td className="admin-date">{new Date(u.created_at).toLocaleDateString()}</td>
                        <td style={{ textAlign: 'center' }}>{u.is_admin ? '✓' : ''}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
                <p className="admin-count">{users.length} user{users.length !== 1 ? 's' : ''}</p>
              </div>
            )}
          </>
        )}

        {activeTab === 'tasks' && <AdminTasksTab token={token} />}
      </div>
    </div>
  );
}
