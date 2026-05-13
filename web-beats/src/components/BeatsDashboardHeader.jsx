import { Link, useLocation } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import { BRAND } from '../brand';

const NAV_LINKS = [
  { to: '/songs',   label: 'Songs' },
  { to: '/billing', label: 'Billing' },
];

function isActive(pathname, to) {
  return pathname === to || pathname.startsWith(to + '/');
}

export function BeatsDashboardHeader({ onMenuOpen }) {
  const { user } = useAuth();
  const { pathname } = useLocation();

  return (
    <header className="dashboard-header">
      {onMenuOpen && (
        <button className="hamburger-btn" onClick={onMenuOpen} aria-label="Open menu">
          ☰
        </button>
      )}
      <Link to="/songs" className="dashboard-logo">
        <span className="zeus-icon">⚡</span>
        <span className="zeus-title">{BRAND.name}</span>
      </Link>
      <nav className="dashboard-header-right">
        {NAV_LINKS.map(({ to, label }) => (
          <Link
            key={to}
            to={to}
            className={`dashboard-header-link${isActive(pathname, to) ? ' dashboard-header-link--active' : ''}`}
          >
            {label}
          </Link>
        ))}
        <Link
          to="/billing"
          className={`dashboard-header-link${isActive(pathname, '/billing') ? ' dashboard-header-link--active' : ''}`}
          style={{ maxWidth: 140 }}
        >
          {user?.email}
        </Link>
      </nav>
    </header>
  );
}
