import { Link, useLocation } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { useAuth } from '../contexts/AuthContext';
import { LanguageSelector } from './LanguageSelector';
import { useDiscoverBadge } from '../hooks/useDiscoverBadge';
import { useClipsEnabled } from '../hooks/useClipsEnabled';
import { isIOSWebView } from '../hooks/useIsIOSWebView';

/**
 * Desktop navigation for the neon restyle (2026-10-01, design-ref/DESIGN.md):
 * a left sidebar with line icons instead of the emoji top bar. Shown only at
 * ≥1024px (songsNeon.css); below that the existing BeatsDashboardHeader and its
 * hamburger stay. Same destinations, labels, badge and gating as that header —
 * only the presentation differs.
 */

const ICONS = {
  songs: <><path d="M9 18V5l12-2v13" /><circle cx="6" cy="18" r="3" /><circle cx="18" cy="16" r="3" /></>,
  search: <><circle cx="11" cy="11" r="7" /><path d="m21 21-4.3-4.3" /></>,
  discover: <><circle cx="12" cy="12" r="9" /><path d="m15.5 8.5-2 5-5 2 2-5z" /></>,
  clips: <><rect x="3" y="5" width="18" height="14" rx="2" /><path d="m10 9 5 3-5 3z" /></>,
  playlists: <><path d="M3 6h12M3 12h12M3 18h8" /><path d="M17 18V8l4-1" /><circle cx="15" cy="18" r="2" /></>,
  mixer: <><path d="M4 21v-7M4 10V3M12 21v-9M12 8V3M20 21v-5M20 12V3" /><path d="M2 14h4M10 8h4M18 16h4" /></>,
  billing: <><rect x="2" y="5" width="20" height="14" rx="2" /><path d="M2 10h20" /></>,
  voice: <><rect x="9" y="2" width="6" height="12" rx="3" /><path d="M5 10a7 7 0 0 0 14 0M12 17v4" /></>,
  tutorial: <><path d="M2 4h7a3 3 0 0 1 3 3v13a2 2 0 0 0-2-2H2zM22 4h-7a3 3 0 0 0-3 3v13a2 2 0 0 1 2-2h8z" /></>,
  contact: <><rect x="2" y="4" width="20" height="16" rx="2" /><path d="m22 6-10 7L2 6" /></>,
  memorials: <><path d="M12 21s-7-4.4-7-10a4 4 0 0 1 7-2.6A4 4 0 0 1 19 11c0 5.6-7 10-7 10z" /></>,
  admin: <><path d="M12 2 4 5v6c0 5 3.4 9.3 8 11 4.6-1.7 8-6 8-11V5z" /></>,
};

function Icon({ name }) {
  return (
    <svg width="19" height="19" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8"
         strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      {ICONS[name]}
    </svg>
  );
}

function isActive(pathname, to) {
  return pathname === to || pathname.startsWith(to + '/');
}

export function NeonSidebar() {
  const { user } = useAuth();
  const { pathname } = useLocation();
  const { t } = useTranslation();
  const newOnDiscover = useDiscoverBadge(user);
  const clipsVisible = useClipsEnabled(user);

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
        <svg width="24" height="28" viewBox="0 0 22 26" fill="#16c8ff" aria-hidden="true"><path d="M13 0 2 15h7l-2 11L20 9h-7l2-9z" /></svg>
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
