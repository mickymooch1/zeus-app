import { useState, useRef, useEffect } from 'react';
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
  const [overflowOpen, setOverflowOpen] = useState(false);
  const menuRef = useRef(null);

  useEffect(() => {
    if (!overflowOpen) return;
    function handleOutside(e) {
      if (menuRef.current && !menuRef.current.contains(e.target)) {
        setOverflowOpen(false);
      }
    }
    document.addEventListener('mousedown', handleOutside);
    document.addEventListener('touchstart', handleOutside);
    return () => {
      document.removeEventListener('mousedown', handleOutside);
      document.removeEventListener('touchstart', handleOutside);
    };
  }, [overflowOpen]);

  const PRIMARY_LINKS = [
    { to: '/songs',     label: t('nav.songs') },
    { to: '/discover',  label: 'Discover' },
    { to: '/playlists', label: '🎵 Playlists' },
    { to: '/search',    label: t('nav.search') },
    { to: '/mixer',     label: t('nav.mixer') },
  ];

  const OVERFLOW_LINKS = [
    { to: '/contact', label: t('nav.contact') },
    { to: '/billing', label: t('nav.billing') },
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
        {/* Primary links — always visible on all screen sizes */}
        {PRIMARY_LINKS.map(({ to, label }) => (
          <Link
            key={to}
            to={to}
            className={`dashboard-header-link nav-primary-link${isActive(pathname, to) ? ' dashboard-header-link--active' : ''}`}
          >
            {label}
          </Link>
        ))}

        {/* Overflow links — desktop: visible in nav, mobile: hidden here (shown in hamburger) */}
        {OVERFLOW_LINKS.map(({ to, label }) => (
          <Link
            key={to}
            to={to}
            className={`dashboard-header-link nav-overflow-desktop${isActive(pathname, to) ? ' dashboard-header-link--active' : ''}`}
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

        {/* Mobile-only overflow hamburger (☰) */}
        <div className="nav-hamburger-wrap" ref={menuRef}>
          <button
            className="nav-hamburger-btn"
            onClick={() => setOverflowOpen(o => !o)}
            aria-label="More navigation options"
            aria-expanded={overflowOpen}
          >
            ☰
          </button>
          {overflowOpen && (
            <div className="nav-overflow-menu">
              {OVERFLOW_LINKS.map(({ to, label }) => (
                <Link
                  key={to}
                  to={to}
                  className={`nav-overflow-link${isActive(pathname, to) ? ' nav-overflow-link--active' : ''}`}
                  onClick={() => setOverflowOpen(false)}
                >
                  {label}
                </Link>
              ))}
            </div>
          )}
        </div>
      </nav>
    </header>
  );
}
