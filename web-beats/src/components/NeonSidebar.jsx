import { useEffect } from 'react';
import { Link, useLocation } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { useAuth } from '../contexts/AuthContext';
import { LanguageSelector } from './LanguageSelector';
import { useDiscoverBadge } from '../hooks/useDiscoverBadge';
import { useClipsEnabled } from '../hooks/useClipsEnabled';
import { isIOSWebView } from '../hooks/useIsIOSWebView';
import { NavIcon as Icon, ZeusBolt } from './navIcons';
import './NeonSidebar.css';

/**
 * Desktop navigation for the neon restyle (2026-10-01, design-ref/DESIGN.md):
 * a left sidebar with line icons instead of the emoji top bars. Rendered once
 * by App for every logged-in app page (utils/appNav.js) and shown only at
 * ≥1024px (NeonSidebar.css); below that each page's own header and hamburger
 * stay. Same destinations, labels, badge and gating as BeatsDashboardHeader —
 * only the presentation differs.
 */

function isActive(pathname, to) {
  return pathname === to || pathname.startsWith(to + '/');
}

export function NeonSidebar() {
  const { user } = useAuth();
  const { pathname } = useLocation();
  const { t } = useTranslation();
  const newOnDiscover = useDiscoverBadge(user);
  const clipsVisible = useClipsEnabled(user);

  // While mounted, the page shifts right to make room (NeonSidebar.css).
  useEffect(() => {
    document.body.classList.add('zb-has-sidebar');
    return () => document.body.classList.remove('zb-has-sidebar');
  }, []);

  const links = [
    { to: '/songs', icon: 'songs', label: t('nav.songs') },
    { to: '/search', icon: 'search', label: t('nav.search') },
    { to: '/discover', icon: 'discover', label: 'Discover', badge: newOnDiscover },
    ...(clipsVisible ? [{ to: '/clips', icon: 'clips', label: 'Clips' }] : []),
    { to: '/playlists', icon: 'playlists', label: 'Playlists' },
    { to: '/mixer', icon: 'mixer', label: t('nav.mixer') },
    { to: '/billing', icon: 'billing', label: t('nav.billing') },
    { to: '/settings', icon: 'voice', label: 'Voice' },
    { to: '/tutorial', icon: 'tutorial', label: 'Tutorial' },
    { to: '/contact', icon: 'contact', label: t('nav.contact') },
    ...(isIOSWebView ? [] : [{ to: '/memorials', icon: 'memorials', label: 'Memorials' }]),
    // !! — /auth/me sends is_admin as 0/1; a bare 0 must not render.
    ...(user?.is_admin ? [{ to: '/admin', icon: 'admin', label: t('nav.admin') }] : []),
  ];

  return (
    <aside className="zb-side" aria-label="Main navigation">
      <Link to="/songs" className="zb-side-logo">
        <ZeusBolt />
        <span>ZEUS <b>BEATS</b></span>
      </Link>
      <nav>
        {links.map(({ to, icon, label, badge }) => (
          <Link key={to} to={to} className={`zb-side-link${isActive(pathname, to) ? ' zb-side-link--active' : ''}`}
                aria-current={isActive(pathname, to) ? 'page' : undefined}>
            <Icon name={icon} />
            {label}
            {badge > 0 && <span className="zb-side-badge" aria-label={`${badge} new`}>{badge > 9 ? '9+' : badge}</span>}
          </Link>
        ))}
      </nav>
      <div className="zb-side-foot">
        <Link to="/billing" className="zb-side-account" title={user?.email}>{user?.email}</Link>
        <div style={{ padding: '0 6px' }}><LanguageSelector /></div>
      </div>
    </aside>
  );
}
