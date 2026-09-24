import { useState } from 'react';
import { GENRE_CATEGORIES, GENRES, gLabel } from '../utils/genres';
import { remixableGenres } from '../utils/remixGenre';

const CYAN = '#00f0ff';
const PURPLE = '#7c3aed';

/**
 * Full genre picker as a bottom sheet — the remix confirm page's "More genres".
 * Same data and interaction as the song creator's picker in SongsPage
 * (GENRE_CATEGORIES accordion of colour-coded pills, optional "Blend with" a
 * second genre), as a self-contained component so SongsPage itself is untouched.
 * One main genre (a remix is one generation); `exclude` hides the original and
 * `nonVocal` (the server's list) hides genres with no singing — a remix always
 * writes new lyrics.
 * onPick({ genre, genreB }) / onClose().
 */
export default function GenrePickerSheet({ exclude = [], nonVocal, initial, onPick, onClose }) {
  const [genre, setGenre] = useState(initial?.genre || '');
  const [blend, setBlend] = useState(!!initial?.genreB);
  const [genreB, setGenreB] = useState(initial?.genreB || '');
  const [openCats, setOpenCats] = useState(() => new Set(
    GENRE_CATEGORIES.filter(c => c.genres.includes(initial?.genre)).map(c => c.id),
  ));
  const toggleCat = (id) => setOpenCats(s => { const n = new Set(s); n.has(id) ? n.delete(id) : n.add(id); return n; });

  const pick = () => { if (genre) onPick({ genre, genreB: blend && genreB ? genreB : undefined }); };

  return (
    <div
      onClick={onClose}
      style={{ position: 'fixed', inset: 0, zIndex: 9500, background: 'rgba(0,0,0,0.7)', display: 'flex', alignItems: 'flex-end', justifyContent: 'center' }}
    >
      <div
        role="dialog"
        aria-label="Pick a genre"
        onClick={e => e.stopPropagation()}
        style={{
          width: '100%', maxWidth: 520, maxHeight: '85svh', display: 'flex', flexDirection: 'column',
          background: '#0d0d1a', borderTop: `1px solid ${CYAN}44`, borderRadius: '20px 20px 0 0',
          boxShadow: `0 -10px 40px rgba(0,0,0,0.7)`,
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '16px 18px 8px' }}>
          <p style={{ margin: 0, fontFamily: 'Orbitron, sans-serif', fontSize: 16, fontWeight: 800, color: '#fff' }}>Pick a genre</p>
          <button type="button" onClick={onClose} aria-label="Close"
            style={{ background: 'none', border: 'none', color: 'rgba(255,255,255,0.6)', fontSize: 22, cursor: 'pointer' }}>×</button>
        </div>

        <div style={{ overflowY: 'auto', padding: '4px 16px 12px', display: 'flex', flexDirection: 'column', gap: 8 }}>
          {GENRE_CATEGORIES.map(cat => {
            const genres = remixableGenres(cat.genres, nonVocal, exclude);
            if (!genres.length) return null;
            const open = openCats.has(cat.id);
            return (
              <div key={cat.id}>
                <button
                  type="button"
                  onClick={() => toggleCat(cat.id)}
                  aria-expanded={open}
                  style={{
                    width: '100%', display: 'flex', alignItems: 'center', gap: 9, padding: '9px 12px', borderRadius: 10,
                    border: `1.5px solid ${cat.color}${open ? 'aa' : '40'}`, background: open ? cat.color + '14' : 'transparent',
                    cursor: 'pointer', fontFamily: 'inherit',
                  }}
                >
                  <span style={{ fontSize: 11, color: cat.color, display: 'inline-block', transform: open ? 'rotate(90deg)' : 'none' }}>▶</span>
                  <span style={{ fontSize: 12, fontWeight: 700, color: cat.color, letterSpacing: '0.8px', textTransform: 'uppercase' }}>{cat.label}</span>
                </button>
                {open && (
                  <div style={{ display: 'flex', flexWrap: 'wrap', gap: 7, padding: '10px 2px 4px' }}>
                    {genres.map(g => {
                      const sel = genre === g;
                      return (
                        <button
                          key={g}
                          type="button"
                          onClick={() => { setGenre(g); if (genreB === g) setGenreB(''); }}
                          aria-pressed={sel}
                          style={{
                            padding: '7px 15px', borderRadius: 20, fontSize: 13, cursor: 'pointer',
                            border: sel ? `2px solid ${cat.color}` : `1.5px solid ${cat.color}55`,
                            background: sel ? cat.color : 'transparent', color: sel ? '#000' : cat.color,
                            fontWeight: sel ? 700 : 500, boxShadow: sel ? `0 0 16px ${cat.color}` : 'none',
                          }}
                        >
                          {gLabel(g)}
                        </button>
                      );
                    })}
                  </div>
                )}
              </div>
            );
          })}
        </div>

        <div style={{ padding: '10px 16px 18px', borderTop: '1px solid rgba(255,255,255,0.08)' }}>
          <label style={{ display: 'flex', alignItems: 'center', gap: 10, cursor: 'pointer', marginBottom: blend ? 10 : 12 }}>
            <input type="checkbox" checked={blend} onChange={e => { setBlend(e.target.checked); if (!e.target.checked) setGenreB(''); }} />
            <span style={{ fontSize: 13, color: '#c4b5fd', fontWeight: 600 }}>Blend with a second genre</span>
          </label>
          {blend && (
            <select
              value={genreB}
              onChange={e => setGenreB(e.target.value)}
              aria-label="Second genre"
              style={{ width: '100%', background: 'rgba(255,255,255,0.04)', border: '1px solid rgba(255,255,255,0.15)', borderRadius: 8, padding: '8px 10px', color: genreB ? CYAN : '#ccc', fontSize: 13, marginBottom: 12 }}
            >
              <option value="">Pick a second genre…</option>
              {remixableGenres(GENRES, nonVocal, [genre]).map(g => <option key={g} value={g}>{gLabel(g)}</option>)}
            </select>
          )}
          <button
            type="button"
            onClick={pick}
            disabled={!genre}
            style={{
              width: '100%', padding: '13px 0', borderRadius: 999, border: 'none', fontSize: 15, fontWeight: 800,
              cursor: genre ? 'pointer' : 'default', color: '#000', opacity: genre ? 1 : 0.4,
              background: `linear-gradient(90deg, ${CYAN}, ${PURPLE})`,
            }}
          >
            {genre ? `Use ${gLabel(blend && genreB ? `${genre}__${genreB}` : genre)}` : 'Pick a genre'}
          </button>
        </div>
      </div>
    </div>
  );
}
