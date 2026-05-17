import { useState, useEffect, useRef } from 'react';

const gLabel = (g) => {
  const MAP = { hiphop:'Hip-hop', lofi:'Lo-Fi', edm:'EDM', rnb:'R&B', drumandbass:'D&B', ukgarage:'UK Garage', ukdrill:'UK Drill', kpop:'K-Pop', afrobeats:'Afrobeats', technhouse:'Tech House', driftphonk:'Drift Phonk', jerseyclub:'Jersey Club', afroswing:'Afroswing', rastadub:'Rasta Dub' };
  return MAP[g] || (g ? g.charAt(0).toUpperCase() + g.slice(1) : '');
};

export default function MixerSongDropdown({ songs, selected, onSelect, accentColor, placeholder }) {
  const [open, setOpen] = useState(false);
  const [search, setSearch] = useState('');
  const containerRef = useRef(null);

  const selectedSong = songs.find(s => s.id === selected);

  const filtered = songs.filter(s => {
    if (!search.trim()) return true;
    const q = search.toLowerCase();
    return s.title.toLowerCase().includes(q) || (s.genre || '').toLowerCase().includes(q);
  });

  // Close on outside click
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

  const glowColor = accentColor === '#00f0ff'
    ? 'rgba(0,240,255,0.3)'
    : 'rgba(255,0,153,0.3)';

  return (
    <div ref={containerRef} style={{ position: 'relative', width: '100%' }}>
      {/* Trigger button */}
      <button
        onClick={() => { setOpen(o => !o); setSearch(''); }}
        style={{
          width: '100%',
          padding: '10px 14px',
          background: '#0a0a0a',
          border: `1px solid ${open ? accentColor : 'rgba(255,255,255,0.12)'}`,
          borderRadius: 8,
          color: selectedSong ? '#f0eeff' : '#555',
          fontSize: 13,
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
        <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', flex: 1 }}>
          {selectedSong ? selectedSong.title : placeholder || 'Select a song…'}
        </span>
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
          <div style={{ padding: '8px 10px', borderBottom: '1px solid rgba(255,255,255,0.06)' }}>
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
                padding: '6px 10px',
                color: '#f0eeff',
                fontSize: 12,
                outline: 'none',
                fontFamily: 'inherit',
              }}
            />
          </div>

          {/* Song list */}
          <div style={{
            maxHeight: 300,
            overflowY: 'auto',
            scrollbarWidth: 'thin',
            scrollbarColor: `${accentColor}40 transparent`,
          }}>
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
                    onClick={() => {
                      onSelect(song.id);
                      setOpen(false);
                      setSearch('');
                    }}
                    style={{
                      width: '100%',
                      padding: '10px 14px',
                      background: isSel ? `${accentColor}18` : 'transparent',
                      border: 'none',
                      borderLeft: isSel ? `3px solid ${accentColor}` : '3px solid transparent',
                      cursor: 'pointer',
                      textAlign: 'left',
                      display: 'block',
                      transition: 'background 0.15s',
                    }}
                    onMouseEnter={e => { if (!isSel) e.currentTarget.style.background = `${accentColor}0d`; }}
                    onMouseLeave={e => { if (!isSel) e.currentTarget.style.background = 'transparent'; }}
                  >
                    <div style={{ color: isSel ? accentColor : '#e2d9f3', fontSize: 13, fontWeight: isSel ? 600 : 400, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                      {song.title}
                    </div>
                    {song.genre && (
                      <div style={{ color: '#555', fontSize: 11, marginTop: 2 }}>
                        {gLabel(song.genre)}
                      </div>
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
