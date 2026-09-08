import { useCallback, useEffect, useRef, useState } from 'react';
import { Link, useLocation, useSearchParams } from 'react-router-dom';
import ReactMarkdown from 'react-markdown';
import { DashboardHeader } from '../components/DashboardHeader';
import { useAuth } from '../contexts/AuthContext';
import { hubApi } from '../hub/api';
import BetaStatus from '../hub/BetaStatus';
import UsageDiagnostics from '../hub/UsageDiagnostics';
import './Hub.css';

function Answer({ request }) {
  const result = request.result;
  return <article className="hub-turn">
    <div className="hub-user-message"><span>YOU</span><p>{request.prompt}</p></div>
    {result && <div className="hub-answer"><span className="hub-kicker">{request.feature === 'council' ? '🧠 ZEUS VERDICT' : '⚡ ZEUS'}</span>
      {result.simulated && <p className="hub-beta-caption">Private beta · simulated response</p>}
      <ReactMarkdown disallowedElements={['img']}>{result.text}</ReactMarkdown>
      {result.unavailable > 0 && <p className="hub-notice">{result.unavailable} Council member was unavailable. This verdict uses the remaining responses.</p>}
      {result.members && <details><summary>View Council Responses</summary>{result.members.map(member => <section key={member.member}><h3>AI {member.member} · {member.provider} / {member.model}</h3><ReactMarkdown disallowedElements={['img']}>{member.text}</ReactMarkdown></section>)}</details>}
      <p className="hub-selection">Zeus selected the best AI for this task.</p>
    </div>}
    <UsageDiagnostics request={request} />
    {request.status === 'failed' && <p className="hub-error" role="alert">{request.error}</p>}
    {request.status === 'running' && <p className="hub-working" role="status"><span className="hub-pulse" />{request.progress}</p>}
  </article>;
}

export default function HubChatPage({ feature = 'ask' }) {
  const { token, user } = useAuth();
  const location = useLocation();
  const [params, setParams] = useSearchParams();
  const conversationId = params.get('conversation');
  const council = feature === 'council';
  const [prompt, setPrompt] = useState(location.state?.prompt || '');
  const [status, setStatus] = useState(null);
  const [history, setHistory] = useState([]);
  const [requests, setRequests] = useState([]);
  const [quote, setQuote] = useState(null);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const [pending, setPending] = useState(null);
  const [checking, setChecking] = useState(false);
  const lock = useRef(false);
  const bottom = useRef(null);
  const pendingKey = `zeus-hub-pending:${user?.id}:${feature}`;
  const featureEnabled = status?.enabled && (!council || status?.council_enabled);
  const quoteKey = `${conversationId || ''}:${prompt}`;

  const refresh = useCallback(async () => {
    const [s, h] = await Promise.all([hubApi(token, '/status'), hubApi(token, '/conversations')]);
    setStatus(s); setHistory(h.filter(c => c.feature === feature));
  }, [token, feature]);

  useEffect(() => {
    let alive = true;
    refresh().catch(e => { if (alive) setError(e.message); });
    Promise.resolve().then(() => {
      if (!alive) return;
      try { const saved = JSON.parse(sessionStorage.getItem(pendingKey)); if (saved) { setPending(saved); setBusy(true); } } catch { /* invalid local recovery data is ignored */ }
    });
    return () => { alive = false; };
  }, [refresh, pendingKey]);

  useEffect(() => {
    const controller = new AbortController();
    if (conversationId) {
      hubApi(token, `/conversations/${conversationId}`, null, controller.signal).then(data => {
        if (data.conversation.feature !== feature) throw new Error('This conversation belongs to another Hub feature.');
        setRequests(data.requests);
        const running = data.requests.find(r => r.status === 'running');
        if (running) { setPending({ request_id: running.request_id }); setBusy(true); }
      }).catch(e => { if (e.name !== 'AbortError') setError(e.message); });
    }
    return () => controller.abort();
  }, [conversationId, token, feature]);

  useEffect(() => {
    if (!prompt.trim() || busy || !featureEnabled) return;
    const controller = new AbortController();
    const timer = setTimeout(() => {
      hubApi(token, '/quote', { request_id: crypto.randomUUID(), conversation_id: conversationId, feature, prompt }, controller.signal)
        .then(q => setQuote({ ...q, key: quoteKey }))
        .catch(e => { if (e.name !== 'AbortError') setQuote({ error: e.message, key: quoteKey }); });
    }, 450);
    return () => { clearTimeout(timer); controller.abort(); };
  }, [prompt, conversationId, feature, token, busy, featureEnabled, quoteKey]);

  useEffect(() => { bottom.current?.scrollIntoView({ behavior: 'smooth', block: 'nearest' }); }, [requests]);

  const acceptResult = useCallback(data => {
    setParams({ conversation: data.conversation_id }, { replace: true });
    setRequests(old => [...old.filter(r => r.request_id !== data.request_id), data].sort((a, b) => a.created_at - b.created_at));
    if (data.status !== 'running') {
      sessionStorage.removeItem(pendingKey);
      setPending(null); setBusy(false); lock.current = false;
      refresh().catch(e => setError(e.message));
    }
  }, [pendingKey, refresh, setParams]);

  useEffect(() => {
    if (!pending) return;
    let stopped = false;
    let timer;
    let failures = 0;
    const poll = async () => {
      try {
        const data = await hubApi(token, `/requests/${pending.request_id}`);
        if (stopped) return;
        failures = 0; acceptResult(data);
        if (data.status === 'running') timer = setTimeout(poll, 1200);
      } catch (e) {
        if (stopped) return;
        if (++failures < 5 && e.status !== 404) timer = setTimeout(poll, 2500);
        else setError('Connection interrupted. Use “Check / retry request” to recover the same request without duplicate charges.');
      }
    };
    poll();
    return () => { stopped = true; clearTimeout(timer); };
  }, [pending, token, acceptResult]);

  async function send(e) {
    e.preventDefault();
    if (lock.current || busy || !quote || quote.key !== quoteKey || quote.error) return;
    lock.current = true; setBusy(true); setError('');
    const body = { request_id: crypto.randomUUID(), conversation_id: conversationId, feature, prompt, max_credits: quote.credits };
    sessionStorage.setItem(pendingKey, JSON.stringify(body));
    try {
      const accepted = await hubApi(token, '/requests', body);
      setPending(body); setPrompt(''); setQuote(null);
      setParams({ conversation: accepted.conversation_id });
    } catch (e) {
      setError(e.message);
      if (e.status && (e.status < 500 || e.status === 503)) {
        sessionStorage.removeItem(pendingKey); setBusy(false); lock.current = false;
      } else setPending(body);
    }
  }

  async function recover() {
    if (checking || !pending) return;
    setChecking(true); setError('');
    try {
      let data;
      try { data = await hubApi(token, `/requests/${pending.request_id}`); }
      catch (e) {
        if (e.status !== 404 || !pending.prompt) throw e;
        const accepted = await hubApi(token, '/requests', pending);
        setParams({ conversation: accepted.conversation_id });
        data = await hubApi(token, `/requests/${pending.request_id}`);
      }
      acceptResult(data);
    } catch (e) {
      setError(e.message);
      if (e.status && (e.status < 500 || e.status === 503)) {
        if (pending.prompt) setPrompt(pending.prompt);
        sessionStorage.removeItem(pendingKey);
        setPending(null); setBusy(false); lock.current = false;
      }
    }
    finally { setChecking(false); }
  }

  function newChat() {
    if (busy) return;
    setParams({}); setRequests([]); setPrompt(''); setError(''); setQuote(null);
  }
  const currentQuote = quote?.key === quoteKey ? quote : null;
  const affordable = currentQuote && !currentQuote.error && currentQuote.balance >= currentQuote.credits;
  return <div className="hub-page"><DashboardHeader /><main className="hub-chat-layout">
    <aside className="hub-history"><Link className="hub-back" to="/hub">← Zeus Missions</Link><button className="hub-secondary" onClick={newChat} disabled={busy}>＋ New Chat</button><h2>Conversation history</h2>
      <nav aria-label="Hub conversation history">{history.length === 0 && <p>Your conversations will appear here.</p>}{history.map(c => <button disabled={busy} className={conversationId === c.id ? 'hub-history-active' : ''} key={c.id} onClick={() => { setRequests([]); setError(''); setParams({ conversation: c.id }); }}>{c.title}</button>)}</nav>
    </aside>
    <section className="hub-chat-panel"><header className="hub-chat-heading"><p className="hub-kicker">{council ? 'PERSPECTIVE. CONSENSUS. CLARITY.' : 'YOUR NEXT IDEA STARTS HERE.'}</p><h1>{council ? '🧠 Zeus Council' : '⚡ Ask Zeus'}</h1>{council && <p className="hub-council-formula">3 AIs + 1 Zeus Verdict</p>}<p>{council ? 'Up to three independent perspectives, brought together in one clear answer. If a member is unavailable, Zeus can work with two responses.' : 'Ask naturally. Zeus selects the AI for your task.'}</p>
      {status?.mode === 'live' && <p className="hub-balance">{status.balance} Hub credits · separate from music and video</p>}
    </header>
    {['development', 'beta'].includes(status?.mode) && <BetaStatus balance={status.balance} mode={status.mode} />}
    {status?.mode === 'disabled' && <p className="hub-notice">Ask Zeus and Council are awaiting activation. <Link to="/dashboard">Use the existing Zeus assistant →</Link></p>}
    {council && status?.enabled && !status.council_enabled && <p className="hub-notice">Zeus Council live calls are disabled. <Link to="/hub/ask">Use Ask Zeus →</Link></p>}
    <div className="hub-transcript" aria-label="Conversation">{requests.length === 0 && <div className="hub-empty"><span aria-hidden="true">{council ? '✦' : 'ϟ'}</span><h2>{council ? 'A broader view of your question.' : 'What can we work on?'}</h2><p>{council ? 'Compare approaches, explore a decision, or challenge an idea.' : 'Explore an idea, draft something useful, or work through code.'}</p></div>}{requests.map(r => <Answer key={r.request_id} request={r} />)}<div ref={bottom} /></div>
    {error && <p className="hub-error" role="alert">{error}</p>}
    {pending && <button className="hub-secondary" disabled={checking} onClick={recover}>{checking ? 'Checking…' : 'Check / retry request'}</button>}
    <form className="hub-composer" onSubmit={send}><label htmlFor="zeus-message">{council ? 'Your question for the Council' : 'Message Zeus'}</label><textarea id="zeus-message" rows={4} maxLength={12000} value={prompt} onChange={e => setPrompt(e.target.value)} disabled={busy || !featureEnabled} placeholder={council ? 'What decision or question should the Council consider?' : params.get('mission') === 'coding' ? 'Describe your coding question or paste a small snippet…' : 'What do you want to do?'} />
      <div className="hub-composer-bottom"><div className="hub-quote" aria-live="polite">{busy ? 'Zeus is working. Your credit reservation is protected.' : currentQuote?.error || (currentQuote ? `Up to ${currentQuote.credits} ${status?.mode === 'beta' ? 'Hub Beta Credits' : status?.mode === 'development' ? 'test Hub credits' : 'Hub credits'} reserved; unused credits released.${affordable ? '' : ' Insufficient Hub credits.'}` : prompt.trim() && featureEnabled ? 'Calculating credit requirement…' : 'Your credit estimate appears before sending.')}</div><button type="submit" className="hub-primary" disabled={busy || !featureEnabled || !affordable}>{busy ? 'Working…' : council ? 'Consult Council ↗' : 'Send ↗'}</button></div>
      <p className="hub-fine-print">Text only for this MVP. No browsing or automatic actions. Recent conversation context is used within size limits.</p>
    </form></section>
  </main></div>;
}
