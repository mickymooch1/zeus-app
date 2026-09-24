// The full-screen clip viewers — the /clips feed and a single /clips/:id — pin
// the Remix button and song bar to the bottom of the screen. CookieBanner goes
// compact on these paths and publishes its height so they can sit above it.
export function isClipViewerPath(pathname) {
  return /^\/clips\/?$/.test(pathname) || /^\/clips\/\d+\/?$/.test(pathname);
}

// Where the Zeus Clips bottom nav (Feed / + / My Clips) shows: the viewers,
// profiles and the pick-a-song list — not the creator or remix-confirm flows,
// which have their own primary button at the bottom.
export function isClipsNavPath(pathname) {
  return isClipViewerPath(pathname)
    || /^\/clips\/u\/[^/]+\/?$/.test(pathname)
    || /^\/clips\/pick\/?$/.test(pathname);
}

// CSS custom properties CookieBanner and ClipsBottomNav set to their rendered
// heights (0px when not shown).
export const COOKIE_BANNER_H_VAR = '--cookie-banner-h';
export const CLIPS_NAV_H_VAR = '--clips-nav-h';

// `bottom` offset for an element pinned to the bottom of a clips page: its
// normal offset, plus whatever the cookie banner and bottom nav take up now.
export const aboveBottomChrome = (px) =>
  `calc(${px}px + var(${COOKIE_BANNER_H_VAR}, 0px) + var(${CLIPS_NAV_H_VAR}, 0px))`;

// Where RegisterPage should send a new user who was bounced to login from a
// /clips page (Create → /clips/pick, My Clips → /clips/me). Only in-app
// /clips paths — anything else keeps the normal /songs landing.
export function clipsReturnPath(pathname) {
  return typeof pathname === 'string' && /^\/clips\//.test(pathname) ? pathname : null;
}
