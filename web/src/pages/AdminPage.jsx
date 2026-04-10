import { useEffect, useState, useCallback } from 'react';
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

export default function AdminPage() {
  const { user, token } = useAuth();
  const [users, setUsers] = useState([]);
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
        setUsers(await res.json());
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
        <h1 className="section-title" style={{ textAlign: 'center', marginBottom: '2rem' }}>
          Admin Dashboard
        </h1>

        {error === 'forbidden' && (
          <p className="admin-denied">403 — Admin access required.</p>
        )}
        {error && error !== 'forbidden' && (
          <div className="form-error form-error--banner">{error}</div>
        )}

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
                  <th>Msgs (month)</th>
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
                    <td className="admin-date">{new Date(u.created_at).toLocaleDateString()}</td>
                    <td style={{ textAlign: 'center' }}>{u.is_admin ? '✓' : ''}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            <p className="admin-count">{users.length} user{users.length !== 1 ? 's' : ''}</p>
          </div>
        )}
      </div>
    </div>
  );
}
