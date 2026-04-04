import { useCallback } from 'react';
import { ChatWindow } from './components/ChatWindow';
import { SessionSidebar } from './components/SessionSidebar';
import { useZeusSocket } from './hooks/useZeusSocket';
import './index.css';

const BACKEND_URL = import.meta.env.VITE_BACKEND_URL || '';

export default function App() {
  const { messages, sessionId, streaming, sendMessage, newSession, loadSession } =
    useZeusSocket();

  const handleResumeSession = useCallback((id) => {
    fetch(`${BACKEND_URL}/history/${id}`)
      .then(r => r.json())
      .then(transcript => loadSession(id, transcript))
      .catch(() => {});
  }, [loadSession]);

  return (
    <div className="app">
      <SessionSidebar
        currentSessionId={sessionId}
        onNewSession={newSession}
        onResumeSession={handleResumeSession}
      />
      <ChatWindow
        messages={messages}
        streaming={streaming}
        onSend={sendMessage}
      />
    </div>
  );
}
