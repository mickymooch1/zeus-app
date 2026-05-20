import { useState } from 'react';
import { Link } from 'react-router-dom';
import { Navbar } from '../components/Navbar';
import { useAuth } from '../contexts/AuthContext';

const BACKEND_URL = import.meta.env.VITE_BACKEND_URL || '';

const EXAMPLE_PROMPTS = [
  'Check recent song failures',
  'Why did animated covers fail?',
  'Check user credits',
  'Explain webhook status',
];

export default function HermesAgentPage() {
  const { user, token } = useAuth();
  const [messages, setMessages] = useState([
    {
      role: 'assistant',
      text: 'Hermes is online. I can summarise Zeus platform status, recent song generation issues, credits, and animated cover signals from safe read-only context.',
    },
  ]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const sendMessage = async (text) => {
    const message = text.trim();
    if (!message || loading) return;
    setError('');
    setInput('');
    setMessages((prev) => [...prev, { role: 'user', text: message }]);
    setLoading(true);
    try {
      const res = await fetch(`${BACKEND_URL}/api/admin/hermes/chat`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({ message }),
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(data.detail || 'Hermes is unavailable');
      setMessages((prev) => [...prev, { role: 'assistant', text: data.reply || 'No response.' }]);
    } catch (err) {
      setError(err.message || 'Hermes is unavailable');
      setMessages((prev) => [...prev, { role: 'assistant', text: 'I could not complete that check right now.' }]);
    } finally {
      setLoading(false);
    }
  };

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
        <div className="section-label" style={{ textAlign: 'center' }}>Internal</div>
        <h1 className="section-title" style={{ textAlign: 'center', marginBottom: '0.5rem' }}>
          Hermes Agent
        </h1>
        <p style={{ color: 'var(--text-dim)', textAlign: 'center', marginBottom: '1.5rem' }}>
          Read-only admin assistant for Zeus platform diagnostics.
        </p>

        <div style={{ display: 'flex', justifyContent: 'center', marginBottom: '1.25rem' }}>
          <Link className="tasks-tab-btn" to="/admin">Back to Admin</Link>
        </div>

        <div style={{
          maxWidth: 920,
          margin: '0 auto',
          border: '1px solid rgba(139,92,246,0.24)',
          borderRadius: 12,
          background: 'rgba(5,5,10,0.86)',
          boxShadow: '0 24px 80px rgba(0,0,0,0.32)',
          overflow: 'hidden',
        }}>
          <div style={{ minHeight: 420, maxHeight: 560, overflowY: 'auto', padding: 20 }}>
            {messages.map((msg, idx) => (
              <div
                key={`${msg.role}-${idx}`}
                style={{
                  display: 'flex',
                  justifyContent: msg.role === 'user' ? 'flex-end' : 'flex-start',
                  marginBottom: 14,
                }}
              >
                <div style={{
                  maxWidth: '78%',
                  whiteSpace: 'pre-wrap',
                  lineHeight: 1.55,
                  color: msg.role === 'user' ? '#fff' : '#e5e7eb',
                  background: msg.role === 'user' ? 'rgba(139,92,246,0.28)' : 'rgba(255,255,255,0.055)',
                  border: msg.role === 'user' ? '1px solid rgba(167,139,250,0.4)' : '1px solid rgba(255,255,255,0.08)',
                  borderRadius: 10,
                  padding: '12px 14px',
                  fontSize: 14,
                }}>
                  {msg.text}
                </div>
              </div>
            ))}
            {loading && (
              <div style={{ color: 'var(--text-dim)', fontSize: 13 }}>Hermes is reading safe admin context...</div>
            )}
          </div>

          <div style={{ borderTop: '1px solid rgba(255,255,255,0.08)', padding: 16 }}>
            <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', marginBottom: 12 }}>
              {EXAMPLE_PROMPTS.map((prompt) => (
                <button
                  key={prompt}
                  type="button"
                  className="tasks-tab-btn"
                  onClick={() => sendMessage(prompt)}
                  disabled={loading}
                  style={{ fontSize: 12, padding: '8px 10px' }}
                >
                  {prompt}
                </button>
              ))}
            </div>
            {error && <div className="form-error form-error--banner" style={{ marginBottom: 12 }}>{error}</div>}
            <form
              onSubmit={(e) => {
                e.preventDefault();
                sendMessage(input);
              }}
              style={{ display: 'flex', gap: 10 }}
            >
              <input
                value={input}
                onChange={(e) => setInput(e.target.value)}
                placeholder="Ask Hermes about failures, credits, webhooks, or animated covers..."
                disabled={loading}
                style={{
                  flex: 1,
                  minWidth: 0,
                  borderRadius: 10,
                  border: '1px solid rgba(255,255,255,0.14)',
                  background: 'rgba(255,255,255,0.06)',
                  color: '#fff',
                  padding: '12px 14px',
                }}
              />
              <button className="btn btn-primary" type="submit" disabled={loading || !input.trim()}>
                Send
              </button>
            </form>
          </div>
        </div>
      </div>
    </div>
  );
}
