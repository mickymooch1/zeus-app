import { useCallback, useEffect, useState } from 'react';
import { useAuth } from '../contexts/AuthContext';

const BACKEND_URL = import.meta.env.VITE_BACKEND_URL || '';

export function SessionSidebar({ currentSessionId, onNewSession, onResumeSession, isOpen, onClose }) {
  const [sessions, setSessions] = useState([]);
  const [tunnelUrl, setTunnelUrl] = useState(null);
  const { token } = useAuth();

  const refresh = useCallback(() => {
    if (!token) {
      setSessions([]);
      return;
    }
    fetch(`${BACKEND_URL}/sessions`, {
      headers: { Authorization: `Bearer ${token}` },
    })
      .then(r => r.ok ? r.json() : [])
      .then(setSessions)
      .catch(() => {});
    fetch(`${BACKEND_URL}/tunnel-url`)
      .then(r => r.json())
      .then(d => setTunnelUrl(d.url))
      .catch(() => {});
  }, [token]);

  useEffect(() => {
    refresh();
  }, [currentSessionId, refresh]);

  return (
    <aside className={`sidebar${isOpen ? ' sidebar--open' : ''}`}>
      <div className="sidebar-header">
        <div className="zeus-logo">
          <span className="zeus-icon">⚡</span>
          <span className="zeus-title">ZEUS</span>
        </div>
      </div>

      <button className="new-session-btn" onClick={onNewSession}>
        + New Session
      </button>

      <div className="session-list">
        <div className="session-list-label">RECENT</div>
        {sessions.map(s => (
          <div
            key={s.id}
            className={`session-item ${s.id === currentSessionId ? 'active' : ''}`}
            onClick={() => onResumeSession(s.id)}
            title={s.id}
          >
            <div className="session-preview">{s.preview || 'Session'}</div>
            <div className="session-meta">
              {s.turns} turn{s.turns !== 1 ? 's' : ''}
            </div>
          </div>
        ))}
      </div>

      <div className="tunnel-status">
        <span className={`status-dot ${tunnelUrl ? 'active' : 'inactive'}`}>●</span>
        {tunnelUrl ? 'Tunnel active' : 'No tunnel'}
      </div>
    </aside>
  );
}
