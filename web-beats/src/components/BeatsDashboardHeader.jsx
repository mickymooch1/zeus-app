import { Link, useLocation } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { useAuth } from '../contexts/AuthContext';
import { BRAND } from '../brand';
import { LanguageSelector } from './LanguageSelector';

function isActive(pathname, to) {
  return pathname === to || pathname.startsWith(to + '/');
}

export function BeatsDashboardHeader({ onMenuOpen }) {
  const { user } = useAuth();
  const { pathname } = useLocation();
  const { t } = useTranslation();

  const NAV_LINKS = [
    { to: '/songs',   label: t('nav.songs') },
    { to: '/search',  label: t('nav.search') },
    { to: '/billing', label: t('nav.billing') },
    { to: '/contact', label: t('nav.contact') },
  ];

  return (
    <header className="dashboard-header">
      {onMenuOpen && (
        <button className="hamburger-btn" onClick={onMenuOpen} aria-label={t('nav.openMenu')}>
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
        {user?.is_admin && (
          <Link
            to="/admin"
            className={`dashboard-header-link${isActive(pathname, '/admin') ? ' dashboard-header-link--active' : ''}`}
            style={{ color: '#00f0ff' }}
          >
            {t('nav.admin')}
          </Link>
        )}
        <Link to="/billing" className="dashboard-header-link dashboard-email-link" title={user?.email}>
          {user?.email}
        </Link>
        <Link to="/billing" className="dashboard-header-link dashboard-email-icon" aria-label={t('nav.account')} title={user?.email}>
          <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/>
            <circle cx="12" cy="7" r="4"/>
          </svg>
        </Link>
        <LanguageSelector />
      </nav>
    </header>
  );
}
