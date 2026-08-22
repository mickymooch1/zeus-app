import { useState, useRef, useEffect } from 'react';
import { Link, useLocation } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { useAuth } from '../contexts/AuthContext';
import { BRAND } from '../brand';
import { LanguageSelector } from './LanguageSelector';
import { useDiscoverBadge } from '../hooks/useDiscoverBadge';

function isActive(pathname, to) {
  return pathname === to || pathname.startsWith(to + '/');
}

// Count pill for the Discover link. Capped at 9+ so a long-quiet feed suddenly
// dropping 40 songs cannot stretch the nav item.
function NavBadge({ count }) {
  if (!count) return null;
  return (
    <span className="nav-badge" aria-label={`${count} new`}>
      {count > 9 ? '9+' : count}
    </span>
  );
}

export function BeatsDashboardHeader({ onMenuOpen }) {
  const { user } = useAuth();
  const { pathname } = useLocation();
  const { t } = useTranslation();
  const [overflowOpen, setOverflowOpen] = useState(false);
  const menuRef = useRef(null);
  const newOnDiscover = useDiscoverBadge(user);

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

  // Mobile visible: Songs, Search
  // Mobile hamburger: Discover, Playlists, Mixer, Billing, Tutorial, Contact
  const PRIMARY_LINKS = [
    { to: '/songs',  label: t('nav.songs') },
    { to: '/search', label: t('nav.search') },
  ];

  const OVERFLOW_LINKS = [
    { to: '/discover',  label: '🔍 Discover' },
    { to: '/playlists', label: '🎵 Playlists' },
    { to: '/mixer',     label: `🎛️ ${t('nav.mixer')}` },
    { to: '/billing',   label: `💳 ${t('nav.billing')}` },
    { to: '/settings',  label: '🎙️ Voice' },
    { to: '/tutorial',  label: '📖 Tutorial' },
    { to: '/contact',   label: `✉️ ${t('nav.contact')}` },
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
            {to === '/discover' && <NavBadge count={newOnDiscover} />}
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
            aria-label={newOnDiscover
              ? `More navigation options — ${newOnDiscover} new on Discover`
              : 'More navigation options'}
            aria-expanded={overflowOpen}
          >
            ☰
            {/* Discover lives inside this menu on mobile, so a badge on the link
                alone would be invisible at 375px until the menu is opened. The dot
                is what makes the feature work on a phone. */}
            {newOnDiscover > 0 && <span className="nav-hamburger-dot" aria-hidden="true" />}
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
                  {to === '/discover' && <NavBadge count={newOnDiscover} />}
                </Link>
              ))}
            </div>
          )}
        </div>
      </nav>
    </header>
  );
}
