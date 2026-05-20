import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { BeatsDashboardHeader } from '../components/BeatsDashboardHeader';
import { useAuth } from '../contexts/AuthContext';
import { BACKEND_URL } from '../brand';

const EXAMPLE_PROMPTS = [
  'Check recent song failures',
  'Why did animated covers fail?',
  'Check user credits',
  'Explain webhook status',
];

export default function HermesAgentPage() {
  const { user, token } = useAuth();
  const navigate = useNavigate();
  const [messages, setMessages] = useState([
    {
      role: 'assistant',
      text: 'Hermes is online. I can summarise Zeus Beats issues from safe read-only admin context.',
    },
  ]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [checking, setChecking] = useState(false);
  const [issues, setIssues] = useState(null);
  const [error, setError] = useState('');

  useEffect(() => {
    if (user && !user.is_admin) {
      navigate('/songs', { replace: true });
    }
  }, [user, navigate]);

  const sendMessage = async (text) => {
    const message = text.trim();
    if (!message || loading) return;
    setInput('');
    setError('');
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

  const runHealthCheck = async () => {
    if (checking) return;
    setChecking(true);
    setError('');
    try {
      const res = await fetch(`${BACKEND_URL}/api/admin/hermes/check`, {
        method: 'POST',
        headers: { Authorization: `Bearer ${token}` },
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(data.detail || 'Health check failed');
      setIssues(data.issues || []);
      setMessages((prev) => [
        ...prev,
        {
          role: 'assistant',
          text: `Health check complete. ${data.issue_count || 0} issue type${data.issue_count === 1 ? '' : 's'} found.`,
        },
      ]);
    } catch (err) {
      setError(err.message || 'Health check failed');
    } finally {
      setChecking(false);
    }
  };

  if (!user?.is_admin) {
    return (
      <div style={{ minHeight: '100vh', background: '#000' }}>
        <BeatsDashboardHeader />
        <main style={{ maxWidth: 960, margin: '0 auto', padding: '32px 24px', color: '#f87171' }}>
          Access denied.
        </main>
      </div>
    );
  }

  return (
    <div style={{ minHeight: '100vh', background: '#000' }}>
      <BeatsDashboardHeader />
      <main style={{ maxWidth: 980, margin: '0 auto', padding: '32px 24px 80px' }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 16, flexWrap: 'wrap', marginBottom: 22 }}>
          <div>
            <h1 style={{ fontSize: 26, fontWeight: 900, color: '#fff', margin: '0 0 6px' }}>Hermes Agent</h1>
            <p style={{ color: '#555', fontSize: 13, margin: 0 }}>Read-only admin diagnostics for Zeus Beats.</p>
          </div>
          <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap' }}>
            <button
              type="button"
              onClick={() => navigate('/admin')}
              style={{
                border: '1px solid rgba(0,240,255,0.28)',
                background: 'rgba(0,240,255,0.08)',
                color: '#00f0ff',
                borderRadius: 8,
                padding: '10px 14px',
                fontWeight: 700,
                cursor: 'pointer',
              }}
            >
              Back to Admin
            </button>
            <button
              type="button"
              onClick={runHealthCheck}
              disabled={checking}
              style={{
                border: '1px solid rgba(168,85,247,0.34)',
                background: checking ? 'rgba(255,255,255,0.05)' : 'rgba(168,85,247,0.12)',
                color: checking ? '#555' : '#c084fc',
                borderRadius: 8,
                padding: '10px 14px',
                fontWeight: 800,
                cursor: checking ? 'not-allowed' : 'pointer',
              }}
            >
              {checking ? 'Checking...' : 'Run Health Check'}
            </button>
          </div>
        </div>

        <section style={{
          border: '1px solid rgba(0,240,255,0.18)',
          background: 'linear-gradient(180deg, rgba(0,240,255,0.05), rgba(168,85,247,0.04))',
          borderRadius: 12,
          overflow: 'hidden',
          boxShadow: '0 22px 70px rgba(0,0,0,0.42)',
        }}>
          <div style={{ minHeight: 430, maxHeight: 580, overflowY: 'auto', padding: 18 }}>
            {issues && (
              <div style={{
                marginBottom: 18,
                border: '1px solid rgba(0,240,255,0.2)',
                borderRadius: 10,
                background: 'rgba(0,240,255,0.06)',
                padding: 14,
              }}>
                <div style={{ color: '#00f0ff', fontWeight: 900, marginBottom: 10 }}>
                  Watcher issues: {issues.length}
                </div>
                {issues.length === 0 ? (
                  <p style={{ color: '#555', margin: 0, fontSize: 13 }}>No current issues detected.</p>
                ) : (
                  <div style={{ display: 'grid', gap: 10 }}>
                    {issues.map((issue) => (
                      <div key={issue.code} style={{ borderTop: '1px solid rgba(255,255,255,0.08)', paddingTop: 10 }}>
                        <div style={{ color: '#fff', fontWeight: 800 }}>{issue.title}</div>
                        <div style={{ color: '#c084fc', fontSize: 12, marginTop: 2 }}>{issue.severity} · {issue.count} item{issue.count === 1 ? '' : 's'}</div>
                        <div style={{ color: '#cbd5e1', fontSize: 13, marginTop: 6 }}>{issue.summary}</div>
                        <div style={{ color: '#64748b', fontSize: 12, marginTop: 6 }}>{issue.recommended_action}</div>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            )}
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
                  maxWidth: '80%',
                  whiteSpace: 'pre-wrap',
                  lineHeight: 1.55,
                  color: msg.role === 'user' ? '#ecfeff' : '#e5e7eb',
                  background: msg.role === 'user' ? 'rgba(0,240,255,0.12)' : 'rgba(255,255,255,0.055)',
                  border: msg.role === 'user' ? '1px solid rgba(0,240,255,0.3)' : '1px solid rgba(255,255,255,0.08)',
                  borderRadius: 10,
                  padding: '12px 14px',
                  fontSize: 14,
                }}>
                  {msg.text}
                </div>
              </div>
            ))}
            {loading && <p style={{ color: '#555', fontSize: 13 }}>Hermes is reading safe admin context...</p>}
          </div>

          <div style={{ borderTop: '1px solid rgba(255,255,255,0.08)', padding: 16, background: 'rgba(0,0,0,0.42)' }}>
            <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', marginBottom: 12 }}>
              {EXAMPLE_PROMPTS.map((prompt) => (
                <button
                  key={prompt}
                  type="button"
                  onClick={() => sendMessage(prompt)}
                  disabled={loading}
                  style={{
                    border: '1px solid rgba(255,255,255,0.1)',
                    background: 'rgba(255,255,255,0.05)',
                    color: '#cbd5e1',
                    borderRadius: 8,
                    padding: '8px 10px',
                    fontSize: 12,
                    cursor: loading ? 'not-allowed' : 'pointer',
                  }}
                >
                  {prompt}
                </button>
              ))}
            </div>
            {error && (
              <div style={{ background: 'rgba(239,68,68,0.12)', border: '1px solid rgba(239,68,68,0.3)', borderRadius: 8, padding: '10px 14px', color: '#fca5a5', fontSize: 13, marginBottom: 12 }}>
                {error}
              </div>
            )}
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
                placeholder="Ask Hermes about failures, credits, webhooks, or Kling..."
                disabled={loading}
                style={{
                  flex: 1,
                  minWidth: 0,
                  borderRadius: 8,
                  border: '1px solid rgba(255,255,255,0.14)',
                  background: 'rgba(255,255,255,0.06)',
                  color: '#fff',
                  padding: '12px 14px',
                  fontSize: 14,
                }}
              />
              <button
                type="submit"
                disabled={loading || !input.trim()}
                style={{
                  border: '1px solid rgba(0,240,255,0.38)',
                  background: loading || !input.trim() ? 'rgba(255,255,255,0.05)' : 'rgba(0,240,255,0.16)',
                  color: loading || !input.trim() ? '#555' : '#00f0ff',
                  borderRadius: 8,
                  padding: '0 18px',
                  fontWeight: 800,
                  cursor: loading || !input.trim() ? 'not-allowed' : 'pointer',
                }}
              >
                Send
              </button>
            </form>
          </div>
        </section>
      </main>
    </div>
  );
}
