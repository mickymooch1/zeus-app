import { useLayoutEffect, useRef } from 'react';
import { Link, useLocation } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import { deriveClipHandle } from '../utils/clipHandle';
import { isClipsNavPath, CLIPS_NAV_H_VAR, COOKIE_BANNER_H_VAR } from '../utils/clipsChrome';

const CYAN = '#00f0ff';
const PURPLE = '#7c3aed';
// How far the "+" button rises above the bar. Counted in the published height
// so the song bar never sits underneath it.
const RAISE = 26;

/**
 * Zeus Clips bottom nav — Feed · (+) Create · My Clips — styled like the
 * mockups' glass bar with a raised glowing "+" in the middle. Mounted once in
 * App and shown only on isClipsNavPath pages.
 *
 * It sits directly ABOVE the cookie banner (bottom: the banner's published
 * height) and publishes its own height as --clips-nav-h, which the pinned
 * clip controls (aboveBottomChrome) and the profile/pick pages' bottom
 * padding add in — so none of the three ever overlap.
 *
 * Create → /clips/pick and My Clips → /clips/me are SchoolSafeRoute pages, so
 * a logged-out tap goes to login and comes straight back afterwards.
 */
export default function ClipsBottomNav() {
  const { pathname } = useLocation();
  const { user } = useAuth();
  const ref = useRef(null);
  const show = isClipsNavPath(pathname);

  useLayoutEffect(() => {
    const root = document.documentElement;
    const el = ref.current;
    if (!show || !el) {
      root.style.setProperty(CLIPS_NAV_H_VAR, '0px');
      return undefined;
    }
    const publish = () => root.style.setProperty(CLIPS_NAV_H_VAR, `${el.offsetHeight + RAISE}px`);
    publish();
    const ro = typeof ResizeObserver !== 'undefined' ? new ResizeObserver(publish) : null;
    ro?.observe(el);
    return () => {
      ro?.disconnect();
      root.style.setProperty(CLIPS_NAV_H_VAR, '0px');
    };
  }, [show]);

  if (!show) return null;

  const myHandle = user ? deriveClipHandle(user.artist_name || user.name) : null;
  const feedActive = pathname === '/clips' || pathname === '/clips/';
  const mineActive = !!myHandle && pathname.toLowerCase() === `/clips/u/${myHandle}`.toLowerCase();

  const item = (active) => ({
    flex: 1, display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 3,
    textDecoration: 'none', fontSize: 11, fontWeight: 700, letterSpacing: '0.02em',
    color: active ? '#fff' : 'rgba(255,255,255,0.55)',
    textShadow: active ? `0 0 10px ${CYAN}aa` : 'none',
  });

  return (
    <nav
      ref={ref}
      aria-label="Zeus Clips"
      style={{
        position: 'fixed', left: 0, right: 0, bottom: `var(${COOKIE_BANNER_H_VAR}, 0px)`, zIndex: 9000,
        display: 'flex', alignItems: 'flex-end', justifyContent: 'space-around',
        padding: '8px 24px calc(8px + env(safe-area-inset-bottom))',
        background: 'rgba(8,8,18,0.88)',
        backdropFilter: 'blur(14px)', WebkitBackdropFilter: 'blur(14px)',
        borderTop: `1px solid ${CYAN}33`, boxShadow: `0 -6px 24px rgba(0,0,0,0.5), 0 -1px 12px ${CYAN}14`,
      }}
    >
      <Link to="/clips" style={item(feedActive)} aria-current={feedActive ? 'page' : undefined}>
        <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
          <path d="M3 10.5 12 3l9 7.5V20a1 1 0 0 1-1 1h-5v-6h-6v6H4a1 1 0 0 1-1-1z" />
        </svg>
        Feed
      </Link>

      <Link
        to="/clips/pick"
        aria-label="Create a clip"
        style={{ flex: 1, display: 'flex', justifyContent: 'center', textDecoration: 'none' }}
      >
        <span style={{
          width: 58, height: 58, marginTop: -RAISE, borderRadius: '50%',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          background: `linear-gradient(135deg, ${CYAN}, ${PURPLE})`,
          border: '3px solid #08080f',
          boxShadow: `0 0 18px ${CYAN}99, 0 0 36px ${PURPLE}88`,
          color: '#000', fontSize: 32, fontWeight: 400, lineHeight: 1,
        }}>
          +
        </span>
      </Link>

      <Link to="/clips/me" style={item(mineActive)} aria-current={mineActive ? 'page' : undefined}>
        <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
          <circle cx="12" cy="8" r="4" />
          <path d="M4 21v-1a6 6 0 0 1 6-6h4a6 6 0 0 1 6 6v1" />
        </svg>
        My Clips
      </Link>
    </nav>
  );
}
