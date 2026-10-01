import { isStandalonePublicPage } from './standalonePages.js';

// Where the neon desktop sidebar (NeonSidebar) is shown for a signed-in user
// (2026-10-01): the logged-in app pages, so navigation is the same everywhere.
// Not on: public/marketing pages, the standalone share & memorial pages, kids
// mode (its own shell), and Zeus Clips (a full-screen sub-app with its own
// navigation — the sidebar links to it instead).
const APP_PATHS = [
  '/songs', '/search', '/discover', '/playlists', '/mixer', '/billing',
  '/settings', '/tutorial', '/contact', '/admin', '/memorials/create',
];

export function showsAppSidebar(pathname) {
  if (!pathname || isStandalonePublicPage(pathname)) return false;
  if (/^\/discover\/[^/]+\/remix\/?$/.test(pathname)) return false;   // remix confirm: its own full-width flow
  return APP_PATHS.some((p) => pathname === p || pathname.startsWith(`${p}/`));
}
