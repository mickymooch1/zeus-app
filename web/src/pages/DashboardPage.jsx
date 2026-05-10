import { useCallback, useEffect, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import { DashboardHeader } from '../components/DashboardHeader';
import { ChatWindow } from '../components/ChatWindow';
import { SessionSidebar } from '../components/SessionSidebar';
import { useAuth } from '../contexts/AuthContext';
import { useZeusSocket } from '../hooks/useZeusSocket';

const BACKEND_URL = import.meta.env.VITE_BACKEND_URL || '';

export default function DashboardPage() {
  const { user, token } = useAuth();
  const [sidebarOpen, setSidebarOpen] = useState(false);

  const { messages, sessionId, streaming, sendMessage, newSession, loadSession } =
    useZeusSocket(token);

  const [searchParams, setSearchParams] = useSearchParams();

  useEffect(() => {
    const updateId = searchParams.get('update');
    const label = searchParams.get('label') || 'your site';
    if (updateId) {
      setSearchParams({}, { replace: true });
      const timer = setTimeout(() => {
        sendMessage(
          `I want to update ${label} (website ID: ${updateId}). What changes would you like to make?`
        );
      }, 500);
      return () => clearTimeout(timer);
    }
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

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

  return (
    <div className="dashboard-page">
      <DashboardHeader onMenuOpen={() => setSidebarOpen(true)} />

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
