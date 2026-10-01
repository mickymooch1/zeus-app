import { useState } from 'react';
import { GENRE_CATEGORIES } from '../utils/genres';
import { plainLabel, initialCategory, tileArt } from '../utils/genreTiles';

/**
 * Genre picker for the neon restyle (2026-10-01, design-ref/DESIGN.md): category
 * chips filter a grid of tiles. Selection logic is the page's own (selGenres /
 * toggleGenre) — this only changes how the choice is presented.
 *
 * `artFor(genre)` may return an image URL for a tile; until genre artwork
 * exists every tile uses a generated gradient in its category's colour.
 */

function TileArt({ color, src }) {
  if (src) return <div className="zb-tile-art"><img src={src} alt="" loading="lazy" /></div>;
  return (
    <div className="zb-tile-art" style={{
      background: `radial-gradient(120% 90% at 85% 10%, ${color}55 0%, transparent 60%),
                   radial-gradient(90% 80% at 0% 100%, rgba(123,92,255,0.22) 0%, transparent 70%),
                   linear-gradient(160deg, #0d1a30 0%, #060b16 100%)`,
    }}>
      <svg width="30" height="30" viewBox="0 0 24 24" fill="none" stroke={color} strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
        <path d="M9 18V5l12-2v13" /><circle cx="6" cy="18" r="3" /><circle cx="18" cy="16" r="3" />
      </svg>
    </div>
  );
}

export default function GenreTileGrid({ selGenres, toggleGenre, gLabel, artFor = tileArt }) {
  const [catId, setCatId] = useState(() => initialCategory(selGenres));
  const cat = GENRE_CATEGORIES.find((c) => c.id === catId) || GENRE_CATEGORIES[0];

  return (
    <>
      <div className="zb-chips" role="group" aria-label="Genre categories">
        {GENRE_CATEGORIES.map((c) => {
          const n = c.genres.reduce((k, g) => k + (selGenres.has(g) ? 1 : 0), 0);
          return (
            <button key={c.id} type="button" className="zb-chip" aria-pressed={c.id === cat.id} onClick={() => setCatId(c.id)}>
              {plainLabel(c.label)}
              {n > 0 && <span className="zb-chip-count" aria-label={`${n} selected`}>{n}</span>}
            </button>
          );
        })}
      </div>
      <div className="zb-genre-grid">
        {cat.genres.map((g) => {
          const sel = selGenres.has(g);
          return (
            <button key={g} type="button" className="zb-tile" aria-pressed={sel} onClick={() => toggleGenre(g)}>
              <TileArt color={cat.color} src={artFor(g)} />
              {sel && (
                <span className="zb-tile-check" aria-hidden="true">
                  <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3.2" strokeLinecap="round" strokeLinejoin="round"><path d="M20 6 9 17l-5-5" /></svg>
                </span>
              )}
              <span className="zb-tile-name">{gLabel(g)}</span>
            </button>
          );
        })}
      </div>
    </>
  );
}
