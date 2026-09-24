// The full-screen clip viewers — the /clips feed and a single /clips/:id — pin
// the Remix button and song bar to the bottom of the screen. CookieBanner goes
// compact on these paths and publishes its height so they can sit above it.
export function isClipViewerPath(pathname) {
  return /^\/clips\/?$/.test(pathname) || /^\/clips\/\d+\/?$/.test(pathname);
}

// CSS custom property CookieBanner sets to its rendered height (0px when hidden).
export const COOKIE_BANNER_H_VAR = '--cookie-banner-h';

// `bottom` offset for an element pinned to the bottom of a clip viewer: its
// normal offset, plus however tall the cookie banner is right now.
export const aboveCookieBanner = (px) => `calc(${px}px + var(${COOKIE_BANNER_H_VAR}, 0px))`;
