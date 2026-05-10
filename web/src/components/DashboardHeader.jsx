import { Link, useLocation } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';

const NAV_LINKS = [
  { to: '/dashboard', label: 'Chat' },
  { to: '/songs',     label: 'Songs' },
  { to: '/websites',  label: 'Websites' },
  { to: '/tasks',     label: 'Tasks' },
];

function isActive(pathname, to) {
  if (to === '/dashboard') return pathname === '/dashboard' || pathname === '/';
  return pathname === to || pathname.startsWith(to + '/');
}

export function DashboardHeader({ onMenuOpen }) {
  const { user } = useAuth();
  const { pathname } = useLocation();

  return (
    <header className="dashboard-header">
      {onMenuOpen && (
        <button className="hamburger-btn" onClick={onMenuOpen} aria-label="Open menu">
          ☰
        </button>
      )}
      <Link to="/dashboard" className="dashboard-logo">
        <span className="zeus-icon">⚡</span>
        <span className="zeus-title">Zeus</span>
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
