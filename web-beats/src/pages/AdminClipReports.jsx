import { useEffect, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { BeatsDashboardHeader } from '../components/BeatsDashboardHeader';
import { useAuth } from '../contexts/AuthContext';
import { BACKEND_URL } from '../brand';

const REASON_COLORS = {
  spam:           { bg: 'rgba(239,68,68,0.12)',  text: '#fca5a5' },
  inappropriate:  { bg: 'rgba(234,179,8,0.15)',   text: '#fbbf24' },
  copyright:      { bg: 'rgba(168,85,247,0.15)',  text: '#c084fc' },
  other:          { bg: 'rgba(255,255,255,0.06)', text: '#888' },
};

function fmt(dateStr) {
  if (!dateStr) return '—';
  return new Date(dateStr).toLocaleString('en-GB', { day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' });
}

/**
 * Zeus Clips Phase 3 moderation queue: every open clip report, newest first.
 * Hide/restore act on the clip itself (status='hidden' <-> 'published') — see
 * main.py's admin_hide_clip/admin_restore_clip. Reports themselves aren't
 * "resolved" or dismissed in this v1 (clips.list_reported_clips has no such
 * concept yet); an admin hides the clip (or doesn't) and moves on, matching
 * "simplicity matters more than features" from the build brief.
 */
export default function AdminClipReports() {
  const { user, token } = useAuth();
  const navigate = useNavigate();
  const [reports, setReports] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [actioning, setActioning] = useState(null); // report_id currently being hidden/restored

  const load = () => {
    if (!token) return;
    setLoading(true);
    fetch(`${BACKEND_URL}/admin/clips/reported`, { headers: { Authorization: `Bearer ${token}` } })
      .then(r => r.ok ? r.json() : r.json().then(e => Promise.reject(e.detail || 'Failed')))
      .then(data => setReports(data.reports ?? []))
      .catch(e => setError(typeof e === 'string' ? e : 'Failed to load reports'))
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    if (user && !user.is_admin) { navigate('/songs', { replace: true }); return; }
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [user, token, navigate]);

  const handleAction = async (report, action) => {
    setActioning(report.report_id);
    try {
      const r = await fetch(`${BACKEND_URL}/admin/clips/${report.clip_id}/${action}`, {
        method: 'POST',
        headers: { Authorization: `Bearer ${token}` },
      });
      if (r.ok) {
        setReports(prev => prev.map(rep =>
          rep.clip_id === report.clip_id ? { ...rep, clip_status: action === 'hide' ? 'hidden' : 'published' } : rep
        ));
      }
    } finally {
      setActioning(null);
    }
  };

  return (
    <div style={{ minHeight: '100vh', background: '#000' }}>
      <BeatsDashboardHeader />

      <div style={{ maxWidth: 1000, margin: '0 auto', padding: '32px 24px 80px' }}>
        <h1 style={{ fontSize: 24, fontWeight: 800, color: '#fff', marginBottom: 4 }}>Admin — Reported Clips</h1>
        <p style={{ color: '#555', fontSize: 13, marginBottom: 20 }}>
          {reports.length} open report{reports.length !== 1 ? 's' : ''}
        </p>

        {error && (
          <div style={{ background: 'rgba(239,68,68,0.12)', border: '1px solid rgba(239,68,68,0.3)', borderRadius: 8, padding: '10px 14px', color: '#fca5a5', fontSize: 13, marginBottom: 20 }}>
            {error}
          </div>
        )}

        {loading ? (
          <p style={{ color: '#555', fontSize: 14 }}>Loading reports…</p>
        ) : reports.length === 0 ? (
          <p style={{ color: '#555', fontSize: 14 }}>Nothing reported. ✓</p>
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
            {reports.map(rep => {
              const rc = REASON_COLORS[rep.reason] || REASON_COLORS.other;
              const isHidden = rep.clip_status === 'hidden';
              return (
                <div
                  key={rep.report_id}
                  style={{
                    display: 'flex', alignItems: 'center', gap: 14, flexWrap: 'wrap',
                    border: '1px solid rgba(255,255,255,0.06)', borderRadius: 10, padding: '12px 16px',
                    background: isHidden ? 'rgba(255,255,255,0.02)' : 'transparent',
                  }}
                >
                  <span style={{ fontSize: 11, fontWeight: 700, padding: '3px 9px', borderRadius: 999, background: rc.bg, color: rc.text, textTransform: 'uppercase', letterSpacing: '0.04em' }}>
                    {rep.reason}
                  </span>
                  <div style={{ flex: '1 1 240px', minWidth: 0 }}>
                    <Link to={`/clips/${rep.clip_id}`} target="_blank" rel="noreferrer" style={{ color: '#00f0ff', fontWeight: 700, fontSize: 13, textDecoration: 'none' }}>
                      Clip #{rep.clip_id} ↗
                    </Link>
                    <p style={{ margin: '2px 0 0', color: '#888', fontSize: 12, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                      {rep.caption || <em>no caption</em>}
                    </p>
                  </div>
                  <span style={{ color: '#555', fontSize: 11, whiteSpace: 'nowrap' }}>reported {fmt(rep.created_at)}</span>
                  <span style={{
                    fontSize: 11, fontWeight: 600, whiteSpace: 'nowrap',
                    color: isHidden ? '#f87171' : '#4ade80',
                  }}>
                    {isHidden ? 'hidden' : 'published'}
                  </span>
                  <button
                    onClick={() => handleAction(rep, isHidden ? 'restore' : 'hide')}
                    disabled={actioning === rep.report_id}
                    style={{
                      padding: '6px 14px', borderRadius: 999, fontSize: 12, fontWeight: 700, cursor: 'pointer',
                      border: 'none', whiteSpace: 'nowrap',
                      background: isHidden ? 'rgba(74,222,128,0.15)' : 'rgba(239,68,68,0.15)',
                      color: isHidden ? '#4ade80' : '#fca5a5',
                      opacity: actioning === rep.report_id ? 0.6 : 1,
                    }}
                  >
                    {actioning === rep.report_id ? '…' : isHidden ? 'Restore' : 'Hide'}
                  </button>
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}
