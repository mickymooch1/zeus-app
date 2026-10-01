# Zeus Beats neon restyle: reference for Claude Code

Look at every image in this folder before changing anything.

- `poster-roast-mode.png`, `poster-dj-mixer.png`: the target look (our ads). The web app should feel like the app screen shown inside these posters.
- `current-songs-page-BEFORE.png`: how /songs looks now. Too flat and grey.
- `roast-mockup-mobile.html`, `roast-mockup-desktop.html`: an approved mockup of the /roast landing page. Use these as a style reference for spacing, glow, fonts and sizes. They use a custom template format (`<x-dc>`, `{{holes}}`, `<sc-for>`), so do NOT copy them into the app; translate the styling into our React components.
- `zeus-hero.jpg`: Zeus character art. Copy into `web-beats/public/images/` and use it in the /roast hero and the Create page header.

## Design tokens

| Token | Value | Use |
|---|---|---|
| bg | `#04060c` | page background |
| surface | `#0b1222` | cards, panels |
| input | `#060b16` | text fields |
| border | `#2a3b57` | default borders |
| border-glow | `#1f5f8a` | highlighted cards |
| cyan | `#16c8ff` | PRIMARY accent: main buttons, active tab/nav, icons |
| purple | `#7b5cff` | secondary accent only (small highlights) |
| text | `#eef6ff` | body text |
| muted | `#9fb0c8` | secondary text |
| on-cyan | `#031018` | text on cyan buttons |

Glow: `box-shadow: 0 0 28px rgba(22,200,255,0.6)` on the main button, `0 0 32px rgba(22,200,255,0.22)` on the main card.

Fonts (Google Fonts): **Bebas Neue** for headings and button labels, **Permanent Marker** only for small hand-written taglines and the big "Roast Mode" style titles, **Barlow** (400/600/700) for body text.

## Rules

- Cyan is the main colour everywhere. Purple is no longer the primary.
- One glowing cyan pill button per screen: the main action (Generate).
- Genre picker becomes a grid of image tiles using each genre's existing cover art, with category chips above it for filtering.
- Desktop nav moves to a left sidebar with line icons (no emoji); mobile keeps the hamburger.
- Keep it simple. Non-technical users are the target, so do not add controls or steps.
- Never mention Suno anywhere a user can see it.
- Don't change functionality. Styling and layout only, unless told otherwise.
