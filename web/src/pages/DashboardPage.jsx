import { useCallback, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { ChatWindow } from '../components/ChatWindow';
import { SessionSidebar } from '../components/SessionSidebar';
import { useAuth } from '../contexts/AuthContext';
import { useZeusSocket } from '../hooks/useZeusSocket';

const BACKEND_URL = import.meta.env.VITE_BACKEND_URL || '';

function PlanBadge({ status, plan }) {
  if (status === 'active' && plan === 'agency') {
    return <span className="badge-agency">Agency</span>;
  }
  if (status === 'active' && plan === 'pro') {
    return <span className="badge-pro">Pro</span>;
  }
  return <span className="badge-free">Free</span>;
}

export default function DashboardPage() {
  const { user, token, logout } = useAuth();
  const navigate = useNavigate();
  const [sidebarOpen, setSidebarOpen] = useState(false);

  const { messages, sessionId, streaming, sendMessage, newSession, loadSession } =
    useZeusSocket(token);

  const handleResumeSession = useCallback(
    (id) => {
      fetch(`${BACKEND_URL}/history/${id}`, {
        headers: token ? { Authorization: `Bearer ${token}` } : {},
      })
        .then((r) => r.json())
        .then((transcript) => loadSession(id, transcript))
        .catch(() => {});
    },
    [loadSession, token]
  );

  const handleLogout = () => {
    logout();
    navigate('/');
  };

  return (
    <div className="dashboard-page">
      <header className="dashboard-header">
        <button
          className="hamburger-btn"
          onClick={() => setSidebarOpen(true)}
          aria-label="Open menu"
        >
          ☰
        </button>
        <Link to="/" className="dashboard-logo">
          <span className="zeus-icon">⚡</span>
          <span className="zeus-title">Zeus</span>
        </Link>

        <div className="dashboard-header-right">
          <PlanBadge
            status={user?.subscription_status}
            plan={user?.subscription_plan}
          />
          <Link to="/billing" className="dashboard-header-link">
            {user?.email}
          </Link>
          <Link to="/billing" className="btn btn-sm btn-ghost">
            Billing
          </Link>
          <button className="btn btn-sm btn-outline" onClick={handleLogout}>
            Sign out
          </button>
        </div>
      </header>

      <div className="dashboard-body">
        {sidebarOpen && (
          <div
            className="sidebar-backdrop"
            onClick={() => setSidebarOpen(false)}
            aria-hidden="true"
          />
        )}
        <SessionSidebar
          currentSessionId={sessionId}
          onNewSession={newSession}
          onResumeSession={handleResumeSession}
          isOpen={sidebarOpen}
          onClose={() => setSidebarOpen(false)}
        />
        <ChatWindow
          messages={messages}
          streaming={streaming}
          onSend={sendMessage}
          isAdmin={!!user?.is_admin}
          token={token}
        />
      </div>
    </div>
  );
}
