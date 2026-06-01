import { useState, useEffect, useRef } from 'react';

const gLabel = (g) => {
  const MAP = {
    hiphop:'Hip-hop', lofi:'Lo-Fi', edm:'EDM', rnb:'R&B', drumandbass:'D&B',
    ukgarage:'UK Garage', ukdrill:'UK Drill', kpop:'K-Pop', afrobeats:'Afrobeats',
    technhouse:'Tech House', driftphonk:'Drift Phonk', jerseyclub:'Jersey Club',
    afroswing:'Afroswing', rastadub:'Rasta Dub', irishjig:'Irish Jig', irishfolk:'Irish Folk',
    bluessoul:'Blues Soul', deepsoulblues:'Deep Soul Blues', ukstreetsoul:'UK Street Soul',
    deeprotbassline:'Deeprot Bassline', electronicfunk:'Electronic Funk',
    syntheticpop:'Synthetic Pop', eastcoasthiphop:'East Coast Hip-Hop', poprap:'Pop Rap',
    trapsoul:'Trap Soul', healingfrequency:'Healing Frequency', vocaljazz:'Vocal Jazz',
    traditionalpop:'Traditional Pop', rocknroll:"Rock 'n' Roll",
    southemsoul:'Southern Soul', countryamericana:'Country Americana',
  };
  return MAP[g] || (g ? g.charAt(0).toUpperCase() + g.slice(1) : '');
};

const DROPDOWN_CSS = `
.mixer-item { transition: background 0.15s ease, box-shadow 0.15s ease; }
.mixer-item-cyan:not(.mixer-item-sel):hover {
  background: rgba(0,240,255,0.08) !important;
  box-shadow: inset 2px 0 0 #00f0ff;
}
.mixer-item-pink:not(.mixer-item-sel):hover {
  background: rgba(255,0,153,0.08) !important;
  box-shadow: inset 2px 0 0 #ff0099;
}
.mixer-item:hover .mixer-item-title { color: #ffffff !important; }
.mixer-song-list::-webkit-scrollbar { width: 4px; }
.mixer-song-list::-webkit-scrollbar-track { background: transparent; }
.mixer-song-list-cyan::-webkit-scrollbar-thumb { background: #00f0ff; border-radius: 4px; }
.mixer-song-list-pink::-webkit-scrollbar-thumb { background: #ff0099; border-radius: 4px; }
`;

export default function MixerSongDropdown({ songs, selected, onSelect, accentColor, placeholder }) {
  const [open, setOpen] = useState(false);
  const [search, setSearch] = useState('');
  const containerRef = useRef(null);

  const isCyan = accentColor === '#00f0ff';
  const glowColor = isCyan ? 'rgba(0,240,255,0.3)' : 'rgba(255,0,153,0.3)';
  const accentRgb = isCyan ? '0,240,255' : '255,0,153';
  const colorKey = isCyan ? 'cyan' : 'pink';

  const selectedSong = songs.find(s => s.id === selected);

  const filtered = songs.filter(s => {
    if (!search.trim()) return true;
    const q = search.toLowerCase();
    return s.title.toLowerCase().includes(q) || (s.genre || '').toLowerCase().includes(q);
  });

  useEffect(() => {
    if (!open) return;
    const handler = (e) => {
      if (containerRef.current && !containerRef.current.contains(e.target)) {
        setOpen(false);
        setSearch('');
      }
    };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, [open]);

  return (
    <div ref={containerRef} style={{ position: 'relative', width: '100%' }}>
      <style>{DROPDOWN_CSS}</style>

      {/* Trigger button */}
      <button
        onClick={() => { setOpen(o => !o); setSearch(''); }}
        style={{
          width: '100%',
          padding: '10px 14px',
          background: '#0a0a0a',
          border: `1px solid ${open ? accentColor : 'rgba(255,255,255,0.12)'}`,
          borderRadius: 8,
          cursor: 'pointer',
          textAlign: 'left',
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          gap: 8,
          boxShadow: open ? `0 0 15px ${glowColor}` : 'none',
          transition: 'border-color 0.2s, box-shadow 0.2s',
        }}
      >
        {selectedSong ? (
          <span style={{ display: 'flex', flexDirection: 'column', flex: 1, overflow: 'hidden', minWidth: 0, gap: 1 }}>
            <span style={{ color: '#fff', fontSize: 13, fontWeight: 400, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
              {selectedSong.title}
            </span>
            <span style={{ color: accentColor, fontSize: 11, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
              {gLabel(selectedSong.genre || '')}
            </span>
          </span>
        ) : (
          <span style={{ color: '#555', fontSize: 13, flex: 1 }}>
            {placeholder || 'Select a song…'}
          </span>
        )}
        <span style={{ color: accentColor, fontSize: 10, flexShrink: 0 }}>{open ? '▲' : '▼'}</span>
      </button>

      {/* Dropdown panel */}
      {open && (
        <div style={{
          position: 'absolute',
          top: 'calc(100% + 4px)',
          left: 0,
          right: 0,
          zIndex: 200,
          background: '#0a0a0a',
          border: `1px solid ${accentColor}`,
          borderRadius: 8,
          boxShadow: `0 0 15px ${glowColor}, 0 8px 32px rgba(0,0,0,0.8)`,
          overflow: 'hidden',
        }}>
          {/* Search input */}
          <div style={{ padding: '8px 10px', borderBottom: '1px solid rgba(255,255,255,0.06)', position: 'relative' }}>
            <span style={{
              position: 'absolute', left: 18, top: '50%', transform: 'translateY(-50%)',
              fontSize: 12, color: '#555', pointerEvents: 'none', lineHeight: 1,
            }}>🔍</span>
            <input
              autoFocus
              value={search}
              onChange={e => setSearch(e.target.value)}
              placeholder="Search songs…"
              style={{
                width: '100%',
                boxSizing: 'border-box',
                background: 'rgba(255,255,255,0.05)',
                border: `1px solid ${accentColor}40`,
                borderRadius: 6,
                padding: '6px 10px 6px 28px',
                color: '#f0eeff',
                fontSize: 12,
                outline: 'none',
                fontFamily: 'inherit',
              }}
            />
          </div>

          {/* Song list */}
          <div
            className={`mixer-song-list mixer-song-list-${colorKey}`}
            style={{
              maxHeight: 300,
              overflowY: 'auto',
              scrollbarWidth: 'thin',
              scrollbarColor: `${accentColor}60 transparent`,
            }}
          >
            {filtered.length === 0 ? (
              <div style={{ padding: '16px', textAlign: 'center', color: '#555', fontSize: 12 }}>
                No songs found
              </div>
            ) : (
              filtered.map(song => {
                const isSel = song.id === selected;
                return (
                  <button
                    key={song.id}
                    onClick={() => { onSelect(song.id); setOpen(false); setSearch(''); }}
                    className={`mixer-item mixer-item-${colorKey}${isSel ? ' mixer-item-sel' : ''}`}
                    style={{
                      width: '100%',
                      padding: '8px 12px',
                      background: isSel ? `rgba(${accentRgb},0.1)` : 'transparent',
                      border: 'none',
                      borderLeft: isSel ? `2px solid ${accentColor}` : '2px solid transparent',
                      cursor: 'pointer',
                      textAlign: 'left',
                      display: 'flex',
                      alignItems: 'center',
                      gap: 8,
                    }}
                  >
                    <span style={{ flex: 1, minWidth: 0 }}>
                      <span
                        className="mixer-item-title"
                        style={{
                          display: 'block',
                          color: isSel ? accentColor : '#e2d9f3',
                          fontSize: 13,
                          fontWeight: isSel ? 600 : 400,
                          overflow: 'hidden',
                          textOverflow: 'ellipsis',
                          whiteSpace: 'nowrap',
                        }}
                      >
                        {song.title}
                      </span>
                      {song.genre && (
                        <span style={{ display: 'block', color: '#555', fontSize: 11, marginTop: 1 }}>
                          {gLabel(song.genre)}
                        </span>
                      )}
                    </span>
                    {isSel && (
                      <span style={{ color: accentColor, fontSize: 12, flexShrink: 0 }}>✓</span>
                    )}
                  </button>
                );
              })
            )}
          </div>
        </div>
      )}
    </div>
  );
}
