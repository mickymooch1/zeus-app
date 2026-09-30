// The public song-share and memorial pages are standalone, minimal-branding
// pages with their own calm visual identity — opened from a link or a QR code,
// often at a funeral. App chrome that is fixed to the viewport (the cookie
// banner) is suppressed on them: it clashes with the design and covers the
// card/photos on small screens. Safe because these pages set no cookies of
// their own and the banner's consent gates no tracking script (see App.jsx).
//
// NOTE the trailing slashes: `/memorial/<token>` is the memorial page, while
// `/memorials` (landing) and `/memorials/create` (wizard) are ordinary app
// pages and must keep the banner.
const STANDALONE_PREFIXES = ['/songs/share/', '/memorial/'];

export function isStandalonePublicPage(pathname) {
  return STANDALONE_PREFIXES.some((p) => (pathname || '').startsWith(p));
}
