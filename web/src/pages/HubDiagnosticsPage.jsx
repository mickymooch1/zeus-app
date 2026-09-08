import { useEffect, useState } from 'react';
import { DashboardHeader } from '../components/DashboardHeader';
import { useAuth } from '../contexts/AuthContext';
import { hubApi } from '../hub/api';
import './Hub.css';

function formatTime(epochSeconds) {
  return new Date(epochSeconds * 1000).toLocaleString();
}

function formatUsd(n) {
  return `$${Number(n || 0).toFixed(4)}`;
}

function RequestRow({ request }) {
  const [open, setOpen] = useState(false);
  const multi = request.providers.length > 1;
  return (
    <>
      <tr className="hub-diag-row">
        <td>{formatTime(request.created_at)}</td>
        <td>{request.feature}</td>
        <td>
          {multi
            ? <button type="button" className="hub-diag-expand" onClick={() => setOpen(o => !o)} aria-expanded={open}>
                {request.providers.length} providers {open ? '▲' : '▼'}
              </button>
            : (request.providers[0] ? `${request.providers[0].provider} / ${request.providers[0].model}` : '—')}
        </td>
        <td>{multi ? '—' : (request.providers[0]?.input_tokens ?? '—')}</td>
        <td>{multi ? '—' : (request.providers[0]?.output_tokens ?? '—')}</td>
        <td>{multi ? '—' : formatUsd(request.providers[0]?.estimated_cost)}</td>
        <td>{request.zeus_credits_charged}</td>
        <td><span className={`hub-diag-status hub-diag-status-${request.status}`}>{request.status}</span></td>
        <td className="hub-diag-reqid" title={request.request_id}>{request.request_id.slice(0, 8)}…</td>
      </tr>
      {multi && open && request.providers.map((p, i) => (
        <tr className="hub-diag-subrow" key={i}>
          <td colSpan={2} />
          <td>{p.provider} / {p.model}</td>
          <td>{p.input_tokens ?? '—'}</td>
          <td>{p.output_tokens ?? '—'}</td>
          <td>{formatUsd(p.estimated_cost)}</td>
          <td colSpan={2} />
          <td><span className={`hub-diag-status hub-diag-status-${p.status}`}>{p.status}</span></td>
        </tr>
      ))}
    </>
  );
}

export default function HubDiagnosticsPage() {
  const { user, token } = useAuth();
  const [data, setData] = useState(null);
  const [error, setError] = useState('');

  useEffect(() => {
    if (!user?.is_admin) return;
    const controller = new AbortController();
    hubApi(token, '/diagnostics', null, controller.signal).then(setData).catch(e => { if (e.name !== 'AbortError') setError(e); });
    return () => controller.abort();
  }, [token, user]);

  if (!user?.is_admin) {
    return (
      <div className="hub-page">
        <DashboardHeader />
        <main className="hub-main">
          <p role="alert" className="hub-error">Not authorized.</p>
        </main>
      </div>
    );
  }

  return (
    <div className="hub-page">
      <DashboardHeader />
      <main className="hub-main">
        <div className="hub-eyebrow">ADMIN ONLY <span>✦</span></div>
        <section className="hub-hero" style={{ textAlign: 'left', margin: '32px 0' }}>
          <p className="hub-kicker">ZEUS HUB</p>
          <h1 style={{ fontSize: 'clamp(32px,5vw,52px)' }}>Diagnostics</h1>
          <p className="hub-tagline" style={{ textAlign: 'left' }}>Beta usage and cost — read-only.</p>
        </section>

        {error && <p role="alert" className="hub-error">{error.status === 403 ? 'Not authorized.' : 'Could not load diagnostics.'}</p>}

        {data && <>
          <div className="hub-diag-stats">
            <div className="hub-diag-stat"><span className="hub-diag-stat-label">Hub Beta Credit balance</span><span className="hub-diag-stat-value">{data.balance}</span></div>
            <div className="hub-diag-stat"><span className="hub-diag-stat-label">Total Hub credits spent</span><span className="hub-diag-stat-value">{data.credits_spent}</span></div>
            <div className="hub-diag-stat"><span className="hub-diag-stat-label">Total estimated provider cost</span><span className="hub-diag-stat-value">{formatUsd(data.provider_cost)}</span></div>
            <div className="hub-diag-stat"><span className="hub-diag-stat-label">Average Ask Zeus cost</span><span className="hub-diag-stat-value">{formatUsd(data.avg_ask_cost)}</span></div>
          </div>

          <h2 className="hub-diag-heading">Latest {data.requests.length} requests</h2>
          <div className="hub-diag-table-wrap">
            <table className="hub-diag-table">
              <thead>
                <tr>
                  <th>Timestamp</th><th>Feature</th><th>Provider / model</th><th>Input tokens</th>
                  <th>Output tokens</th><th>Est. cost</th><th>Credits</th><th>Status</th><th>Request ID</th>
                </tr>
              </thead>
              <tbody>
                {data.requests.map(r => <RequestRow key={r.request_id} request={r} />)}
              </tbody>
            </table>
          </div>
        </>}
      </main>
    </div>
  );
}
