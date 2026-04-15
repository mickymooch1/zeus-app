import { useCallback, useEffect, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';

const BACKEND_URL = import.meta.env.VITE_BACKEND_URL || '';

const PLAN_LIMITS = { pro: 1, agency: 5, enterprise: null, free: 0 };

function planLimit(user) {
  if (user?.is_admin) return null;
  if (user?.subscription_status !== 'active') return 0;
  return PLAN_LIMITS[user?.subscription_plan] ?? 0;
}

function UsageBadge({ count, limit }) {
  if (limit === null) return <span className="badge-agency">Unlimited</span>;
  const pct = limit > 0 ? count / limit : 1;
  const cls = pct >= 1 ? 'badge-status badge-status--failed' : 'badge-status badge-status--done';
  return (
    <span className={cls}>
      {count} / {limit} site{limit !== 1 ? 's' : ''}
    </span>
  );
}

function LinkSiteModal({ onClose, onLinked, token }) {
  const [siteName, setSiteName] = useState('');
  const [clientName, setClientName] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    setLoading(true);
    try {
      const res = await fetch(`${BACKEND_URL}/websites`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({
          netlify_site_name: siteName.trim(),
          client_name: clientName.trim() || null,
        }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || 'Failed to link site');
      onLinked(data);
      onClose();
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div className="modal-box" onClick={(e) => e.stopPropagation()}>
        <h3>Link an existing Netlify site</h3>
        <form onSubmit={handleSubmit}>
          <label className="form-label">
            Netlify site name or URL
            <input
              className="form-input"
              placeholder="e.g. smith-plumbing-abc123"
              value={siteName}
              onChange={(e) => setSiteName(e.target.value)}
              required
            />
          </label>
          <label className="form-label">
            Client name <span className="form-hint">(optional)</span>
            <input
              className="form-input"
              placeholder="e.g. Smith Plumbing"
              value={clientName}
              onChange={(e) => setClientName(e.target.value)}
            />
          </label>
          {error && <p className="form-error">{error}</p>}
          <div className="modal-actions">
            <button type="button" className="btn btn-outline" onClick={onClose}>
              Cancel
            </button>
            <button type="submit" className="btn btn-primary" disabled={loading}>
              {loading ? 'Linking…' : 'Link site'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

function SiteCard({ site, onUnlink, onUpdate }) {
  const updatedAt = new Date(site.updated_at).toLocaleDateString('en-GB', {
    day: 'numeric',
    month: 'short',
    year: 'numeric',
  });

  return (
    <div className="task-card">
      <div className="task-card-header">
        <span className="task-description">
          {site.client_name || site.netlify_site_name}
        </span>
        <button
          className="task-delete-btn"
          onClick={() => onUnlink(site.id)}
          title="Unlink site"
        >
          ✕
        </button>
      </div>
      <div className="task-card-body">
        <a
          href={site.site_url}
          target="_blank"
          rel="noopener noreferrer"
          className="site-url-link"
        >
          {site.site_url}
        </a>
        <span className="task-meta">Updated {updatedAt}</span>
      </div>
      <div className="task-card-footer">
        <button className="btn btn-sm btn-primary" onClick={() => onUpdate(site)}>
          Update Site
        </button>
      </div>
    </div>
  );
}

export default function WebsitesPage() {
  const { user, token } = useAuth();
  const navigate = useNavigate();
  const [sites, setSites] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showLinkModal, setShowLinkModal] = useState(false);

  const limit = planLimit(user);
  const canLink = limit === null || (limit > 0 && sites.length < limit);
  const canSeeFeature = limit === null || limit > 0;

  const fetchSites = useCallback(async () => {
    setLoading(true);
    try {
      const res = await fetch(`${BACKEND_URL}/websites`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (res.ok) setSites(await res.json());
    } finally {
      setLoading(false);
    }
  }, [token]);

  useEffect(() => {
    fetchSites();
  }, [fetchSites]);

  const handleUnlink = async (id) => {
    if (
      !window.confirm(
        'Unlink this site? This removes it from Zeus but does not delete it from Netlify.'
      )
    )
      return;
    await fetch(`${BACKEND_URL}/websites/${id}`, {
      method: 'DELETE',
      headers: { Authorization: `Bearer ${token}` },
    });
    setSites((prev) => prev.filter((s) => s.id !== id));
  };

  const handleUpdate = (site) => {
    const label = site.client_name || site.netlify_site_name;
    navigate(`/dashboard?update=${site.id}&label=${encodeURIComponent(label)}`);
  };

  const handleLinked = (newSite) => {
    setSites((prev) => [newSite, ...prev]);
  };

  return (
    <div className="tasks-page">
      <header className="dashboard-header">
        <Link to="/dashboard" className="dashboard-logo">
          <span className="zeus-icon">⚡</span>
          <span className="zeus-title">Zeus</span>
        </Link>
        <nav className="dashboard-header-right">
          <Link to="/dashboard" className="dashboard-header-link">
            Chat
          </Link>
          <Link
            to="/websites"
            className="dashboard-header-link"
            style={{ fontWeight: 600 }}
          >
            Websites
          </Link>
          <Link to="/tasks" className="dashboard-header-link">
            Tasks
          </Link>
          <Link to="/billing" className="dashboard-header-link">
            {user?.email}
          </Link>
        </nav>
      </header>

      <div className="tasks-container">
        <div className="tasks-header">
          <div>
            <h1 className="tasks-title">My Websites</h1>
            <p className="tasks-subtitle">Sites built and managed by Zeus</p>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
            <UsageBadge count={sites.length} limit={limit} />
            {canLink && (
              <button
                className="btn btn-primary"
                onClick={() => setShowLinkModal(true)}
              >
                + Link existing site
              </button>
            )}
          </div>
        </div>

        {!canSeeFeature && (
          <div className="tasks-empty">
            <p>
              Website management is available on Pro, Agency, and Enterprise
              plans.
            </p>
            <Link
              to="/pricing"
              className="btn btn-primary"
              style={{ marginTop: '12px' }}
            >
              View pricing
            </Link>
          </div>
        )}

        {canSeeFeature && loading && <p className="tasks-empty">Loading…</p>}

        {canSeeFeature && !loading && sites.length === 0 && (
          <div className="tasks-empty">
            <p>
              No websites yet. Ask Zeus to build one and it will appear here
              automatically.
            </p>
            <Link
              to="/dashboard"
              className="btn btn-primary"
              style={{ marginTop: '12px' }}
            >
              Open Zeus chat
            </Link>
          </div>
        )}

        {canSeeFeature && !loading && sites.length > 0 && (
          <div className="tasks-list">
            {sites.map((site) => (
              <SiteCard
                key={site.id}
                site={site}
                onUnlink={handleUnlink}
                onUpdate={handleUpdate}
              />
            ))}
          </div>
        )}
      </div>

      {showLinkModal && (
        <LinkSiteModal
          token={token}
          onClose={() => setShowLinkModal(false)}
          onLinked={handleLinked}
        />
      )}
    </div>
  );
}
