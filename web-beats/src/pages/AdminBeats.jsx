import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { BeatsDashboardHeader } from '../components/BeatsDashboardHeader';
import { useAuth } from '../contexts/AuthContext';
import { BACKEND_URL } from '../brand';

const PLAN_COLORS = {
  enterprise:    { bg: 'rgba(234,179,8,0.15)',   text: '#fbbf24' },
  music_agency:  { bg: 'rgba(168,85,247,0.15)',  text: '#c084fc' },
  music_pro:     { bg: 'rgba(0,240,255,0.12)',   text: '#00f0ff' },
  music_starter: { bg: 'rgba(52,211,153,0.12)',  text: '#34d399' },
};

function fmt(dateStr) {
  if (!dateStr) return '—';
  return new Date(dateStr).toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: 'numeric' });
}

export default function AdminBeats() {
  const { user, token } = useAuth();
  const navigate = useNavigate();
  const [users, setUsers] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [sortKey, setSortKey] = useState('created_at');

  useEffect(() => {
    if (user && !user.is_admin) {
      navigate('/songs', { replace: true });
      return;
    }
    if (!token) return;
    fetch(`${BACKEND_URL}/admin/users`, {
      headers: { Authorization: `Bearer ${token}` },
    })
      .then(r => r.ok ? r.json() : r.json().then(e => Promise.reject(e.detail || 'Failed')))
      .then(data => setUsers(data))
      .catch(e => setError(typeof e === 'string' ? e : 'Failed to load users'))
      .finally(() => setLoading(false));
  }, [user, token, navigate]);

  const sorted = [...users].sort((a, b) => {
    if (sortKey === 'messages_this_month') return (b[sortKey] ?? 0) - (a[sortKey] ?? 0);
    if (sortKey === 'created_at') return new Date(b.created_at || 0) - new Date(a.created_at || 0);
    return (a[sortKey] || '').localeCompare(b[sortKey] || '');
  });

  const COL = [
    { key: 'email',               label: 'Email' },
    { key: 'name',                label: 'Name' },
    { key: 'subscription_plan',   label: 'Plan' },
    { key: 'messages_this_month', label: 'Songs (mo)' },
    { key: 'subscription_status', label: 'Status' },
    { key: 'created_at',          label: 'Joined' },
  ];

  return (
    <div style={{ minHeight: '100vh', background: '#000' }}>
      <BeatsDashboardHeader />

      <div style={{ maxWidth: 1160, margin: '0 auto', padding: '32px 24px 80px' }}>
        <h1 style={{ fontSize: 24, fontWeight: 800, color: '#fff', marginBottom: 4 }}>Admin — Users</h1>
        <p style={{ color: '#555', fontSize: 13, marginBottom: 28 }}>
          {users.length} registered user{users.length !== 1 ? 's' : ''}
        </p>

        {error && (
          <div style={{ background: 'rgba(239,68,68,0.12)', border: '1px solid rgba(239,68,68,0.3)', borderRadius: 8, padding: '10px 14px', color: '#fca5a5', fontSize: 13, marginBottom: 20 }}>
            {error}
          </div>
        )}

        {loading ? (
          <p style={{ color: '#555', fontSize: 14 }}>Loading users…</p>
        ) : (
          <div style={{ overflowX: 'auto', border: '1px solid rgba(255,255,255,0.06)', borderRadius: 12 }}>
            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
              <thead>
                <tr style={{ background: '#0a0a0a' }}>
                  {COL.map(c => (
                    <th
                      key={c.key}
                      onClick={() => setSortKey(c.key)}
                      style={{
                        textAlign: 'left', padding: '10px 14px',
                        color: sortKey === c.key ? '#00f0ff' : '#555',
                        fontWeight: 600, fontSize: 11,
                        textTransform: 'uppercase', letterSpacing: '0.07em',
                        cursor: 'pointer', userSelect: 'none',
                        borderBottom: '1px solid rgba(255,255,255,0.06)',
                        whiteSpace: 'nowrap',
                      }}
                    >
                      {c.label}{sortKey === c.key ? ' ↓' : ''}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {sorted.map((u, i) => {
                  const pc = PLAN_COLORS[u.subscription_plan] || { bg: 'rgba(255,255,255,0.06)', text: '#666' };
                  return (
                    <tr
                      key={u.id}
                      style={{ borderBottom: '1px solid rgba(255,255,255,0.04)', background: i % 2 === 0 ? 'transparent' : 'rgba(255,255,255,0.01)' }}
                    >
                      <td style={{ padding: '10px 14px', color: '#e2e8f0', fontFamily: 'monospace', fontSize: 12 }}>{u.email}</td>
                      <td style={{ padding: '10px 14px', color: '#888' }}>{u.name || '—'}</td>
                      <td style={{ padding: '10px 14px' }}>
                        <span style={{ fontSize: 11, fontWeight: 600, padding: '3px 9px', borderRadius: 999, background: pc.bg, color: pc.text }}>
                          {u.subscription_plan || 'free'}
                        </span>
                        {u.is_admin ? <span style={{ marginLeft: 6, fontSize: 10, color: '#fbbf24' }}>admin</span> : null}
                      </td>
                      <td style={{ padding: '10px 14px', color: '#ccc', textAlign: 'right' }}>{u.messages_this_month ?? 0}</td>
                      <td style={{ padding: '10px 14px' }}>
                        <span style={{ fontSize: 11, color: u.subscription_status === 'active' ? '#4ade80' : '#444' }}>
                          {u.subscription_status || 'free'}
                        </span>
                      </td>
                      <td style={{ padding: '10px 14px', color: '#555', whiteSpace: 'nowrap' }}>{fmt(u.created_at)}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
