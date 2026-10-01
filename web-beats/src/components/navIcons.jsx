// Line icons for app navigation (neon restyle, design-ref/DESIGN.md: "line icons,
// no emoji"). Shared by the desktop NeonSidebar and the phone hamburger menu in
// BeatsDashboardHeader so both show the same icon for the same destination.

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
  menu: <><path d="M4 7h16M4 12h16M4 17h16" /></>,
};

export function NavIcon({ name, size = 19 }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8"
         strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      {ICONS[name]}
    </svg>
  );
}

// The Zeus Beats bolt used by the sidebar and header logos.
export function ZeusBolt({ width = 24, height = 28 }) {
  return (
    <svg width={width} height={height} viewBox="0 0 22 26" fill="#16c8ff" aria-hidden="true">
      <path d="M13 0 2 15h7l-2 11L20 9h-7l2-9z" />
    </svg>
  );
}
