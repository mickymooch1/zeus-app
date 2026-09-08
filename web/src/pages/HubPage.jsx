import { useEffect, useRef, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { DashboardHeader } from '../components/DashboardHeader';
import { useAuth } from '../contexts/AuthContext';
import { hubApi } from '../hub/api';
import BetaStatus from '../hub/BetaStatus';
import './Hub.css';

const missions = [
  { icon: '⚡', title: 'Ask Zeus', detail: 'Ask a question, shape an idea or get help with a task. Zeus chooses the AI.', action: 'Start a conversation', label: 'YOUR EVERYDAY AI', to: '/hub/ask', featured: true },
  { icon: '🧠', title: 'Zeus Council', detail: 'Compare independent perspectives and get one clear conclusion.', action: 'Consult the Council', label: 'A BROADER PERSPECTIVE', formula: '3 AIs + 1 Zeus Verdict', to: '/hub/council', featured: true },
  { icon: '🌐', title: 'Build a Website', detail: 'Create and refine your site with Zeus.', action: 'Open website builder', to: '/dashboard' },
  { icon: '🎵', title: 'Create Music', detail: 'Make your next track in the Zeus music studio.', action: 'Open music studio', to: '/songs' },
  { icon: '📱', title: 'Create Social Content', detail: 'A guided content workflow.', soon: true },
  { icon: '💼', title: 'Start a Business', detail: 'Turn an idea into a practical launch plan.', soon: true },
  { icon: '🔎', title: 'Research Something', detail: 'A dedicated research workflow.', soon: true },
  { icon: '🎨', title: 'Create Images', detail: 'Bring an idea to life with Zeus’s image tools.', action: 'Open image tools', to: '/dashboard' },
  { icon: '💻', title: 'Coding Assistant', detail: 'Explain, debug or improve code with Ask Zeus.', action: 'Get coding help', to: '/hub/ask?mission=coding' },
];

const suggestions = [
  { label: 'Draft a project brief', prompt: 'Help me draft a clear project brief. Ask me about the goal, audience and deadline first.' },
  { label: 'Compare two ideas', prompt: 'Help me compare two ideas. Ask what they are, then weigh the benefits, trade-offs and uncertainties.' },
  { label: 'Plan my week', prompt: 'Help me plan a realistic week. Ask about my priorities, commitments and available time.' },
  { label: 'Explain some code', prompt: 'Help me understand a piece of code. Ask me to paste it, then explain what it does in plain language.' },
];

export default function HubPage() {
  const { token } = useAuth();
  const navigate = useNavigate();
  const [prompt, setPrompt] = useState('');
  const [status, setStatus] = useState(null);
  const [error, setError] = useState('');
  const promptInput = useRef(null);
  useEffect(() => {
    const controller = new AbortController();
    hubApi(token, '/status', null, controller.signal).then(setStatus).catch(e => { if (e.name !== 'AbortError') setError(e.message); });
    return () => controller.abort();
  }, [token]);
  return (
    <div className="hub-page">
      <DashboardHeader />
      <main className="hub-main">
        <div className="hub-eyebrow">YOUR ZEUS UNIVERSE <span>✦</span></div>
        <section className="hub-hero">
          <p className="hub-kicker">CREATE. THINK. BUILD.</p>
          <h1>ZEUS <span>AI</span></h1>
          <p className="hub-tagline">One request. The right AI. A finished result.</p>
          <form className="hub-launch" onSubmit={e => { e.preventDefault(); navigate('/hub/ask', { state: { prompt } }); }}>
            <label htmlFor="hub-prompt">What do you want to do?</label>
            <textarea ref={promptInput} id="hub-prompt" rows={2} maxLength={12000} value={prompt} onChange={e => setPrompt(e.target.value)} placeholder="Bring your next idea to Zeus…" />
            <div className="hub-suggestions" role="group" aria-label="Prompt suggestions"><span>Try a starting point</span>{suggestions.map(s => <button key={s.label} type="button" onClick={() => { setPrompt(s.prompt); promptInput.current?.focus(); }}>{s.label}</button>)}</div>
            <div className="hub-launch-footer"><span>One question, or a fresh perspective.</span><div className="hub-launch-actions"><button className="hub-primary" type="submit">Ask Zeus <span aria-hidden="true">↗</span></button><button className="hub-council-button" type="button" onClick={() => navigate('/hub/council', { state: { prompt } })}>Ask the Council <span aria-hidden="true">↗</span></button></div></div>
          </form>
        </section>
        {status?.mode === 'live' && <div className="hub-status-strip"><span>⚡ <strong>{status.balance}</strong> Zeus Hub credits</span><span>Separate from music, video and premium credits</span></div>}
        {status?.mode === 'disabled' && <p className="hub-availability">Ask Zeus & Council are awaiting activation. <Link to="/dashboard">Your existing Zeus tools are ready →</Link></p>}
        {error && <p role="alert" className="hub-error">{error}</p>}
        <section aria-labelledby="missions-heading">
          <div className="hub-section-title"><div><p className="hub-kicker">PICK YOUR NEXT MOVE</p><h2 id="missions-heading">Zeus Missions</h2></div><Link to="/websites">Your websites →</Link></div>
          <div className="hub-missions">
            {missions.map(m => {
              const content = <><div className="hub-mission-top"><span className="hub-mission-icon" aria-hidden="true">{m.icon}</span>{m.soon ? <span className="hub-soon-label">Coming soon</span> : m.label && <span className="hub-mission-label">{m.label}</span>}</div><h3>{m.title}</h3>{m.formula && <span className="hub-council-formula">{m.formula}</span>}<p>{m.detail}</p>{!m.soon && <span className="hub-mission-action">{m.action} <span aria-hidden="true">↗</span></span>}</>;
              return m.soon ? <article className="hub-mission hub-mission-soon" key={m.title}>{content}</article> : <Link key={m.title} className={`hub-mission ${m.featured ? 'hub-mission-featured' : ''}`} to={m.to}>{content}</Link>;
            })}
          </div>
        </section>
        {['development', 'beta'].includes(status?.mode) && <BetaStatus balance={status.balance} mode={status.mode} />}
        <footer className="hub-footer">Your existing Zeus tools, together. <Link to="/dashboard">Open the original Zeus assistant →</Link></footer>
      </main>
    </div>
  );
}
