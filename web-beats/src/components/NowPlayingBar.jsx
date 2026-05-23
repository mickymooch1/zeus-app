import { useNowPlaying } from '../contexts/NowPlayingContext';

const GENRE_LABEL = {
  hiphop:'Hip-hop', lofi:'Lo-Fi', edm:'EDM', irishjig:'Irish Jig', irishfolk:'Irish Folk',
  rnb:'R&B', bluessoul:'Blues Soul', drumandbass:'D&B', grime:'Grime', ukgarage:'UK Garage',
  jungle:'Jungle', bassline:'Bassline', house:'House', loversrock:'Lovers Rock', ukdrill:'UK Drill',
  kpop:'K-Pop', deepsoulblues:'Deep Soul Blues', ukstreetsoul:'UK Street Soul', technhouse:'Tech House',
  driftphonk:'Drift Phonk', jerseyclub:'Jersey Club', afroswing:'Afroswing', rastadub:'Rasta Dub',
  deeprotbassline:'Deeprot Bassline', jazz:'Jazz', electronicfunk:'Electronic Funk',
  syntheticpop:'Synthetic Pop', ragga:'Ragga', dubstep:'Dubstep',
  bhangra:'Bhangra', rockney:'Rockney', metal:'Metal',
};

function gLabel(g) {
  if (!g) return '';
  if (g.includes('__')) {
    const [a, b] = g.split('__');
    return `${GENRE_LABEL[a] || a} × ${GENRE_LABEL[b] || b}`;
  }
  return GENRE_LABEL[g] || g.charAt(0).toUpperCase() + g.slice(1);
}

function fmt(s) {
  if (!s || !isFinite(s)) return '0:00';
  return `${Math.floor(s / 60)}:${String(Math.floor(s % 60)).padStart(2, '0')}`;
}

export default function NowPlayingBar() {
  const {
    currentSong, isPlaying, togglePlay, next, prev,
    currentTime, duration, seek,
    shuffle, toggleShuffle, repeat, cycleRepeat,
  } = useNowPlaying();

  if (!currentSong) return null;

  const progress = duration > 0 ? currentTime / duration : 0;

  return (
    <div style={{
      position: 'fixed', bottom: 0, left: 0, right: 0, zIndex: 9999,
      background: 'linear-gradient(180deg, rgba(10,10,20,0.97) 0%, #0a0a14 100%)',
      borderTop: '1px solid rgba(0,240,255,0.18)',
      backdropFilter: 'blur(20px)',
      padding: '10px 20px 12px',
      display: 'flex', alignItems: 'center', gap: 16,
      boxShadow: '0 -4px 40px rgba(0,240,255,0.08)',
    }}>
      {/* Thumb + info */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 10, minWidth: 0, flex: '0 0 200px', maxWidth: 200 }}>
        {currentSong.image_url
          ? <img src={currentSong.image_url} alt="" style={{ width: 40, height: 40, borderRadius: 6, objectFit: 'cover', flexShrink: 0, border: '1px solid rgba(0,240,255,0.2)' }} />
          : <div style={{ width: 40, height: 40, borderRadius: 6, background: 'rgba(124,58,237,0.3)', display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0, fontSize: 18 }}>♫</div>
        }
        <div style={{ minWidth: 0 }}>
          <div style={{ fontSize: 12, fontWeight: 700, color: '#e2e8f0', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
            {currentSong.title || 'Untitled'}
          </div>
          <span style={{
            display: 'inline-block', fontSize: 10, fontWeight: 600, padding: '1px 6px',
            borderRadius: 4, background: 'rgba(168,85,247,0.2)', color: '#c084fc',
            border: '1px solid rgba(168,85,247,0.3)', marginTop: 2,
          }}>
            {gLabel(currentSong.genre_tag)}
          </span>
        </div>
      </div>

      {/* Controls */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 10, flexShrink: 0 }}>
        <button onClick={prev} style={btnStyle} title="Previous">⏮</button>
        <button
          onClick={togglePlay}
          style={{
            width: 40, height: 40, borderRadius: '50%', border: 'none', cursor: 'pointer',
            background: 'linear-gradient(135deg, #7c3aed, #00f0ff)',
            color: '#fff', fontSize: 16, display: 'flex', alignItems: 'center', justifyContent: 'center',
            boxShadow: '0 0 12px rgba(0,240,255,0.35)',
          }}
          title={isPlaying ? 'Pause' : 'Play'}
        >
          {isPlaying ? '⏸' : '▶'}
        </button>
        <button onClick={next} style={btnStyle} title="Next">⏭</button>
      </div>

      {/* Progress */}
      <div style={{ flex: 1, display: 'flex', alignItems: 'center', gap: 8, minWidth: 0 }}>
        <span style={{ fontSize: 11, color: '#64748b', flexShrink: 0, fontVariantNumeric: 'tabular-nums' }}>{fmt(currentTime)}</span>
        <div style={{ flex: 1, position: 'relative', height: 4, borderRadius: 2, background: 'rgba(255,255,255,0.1)', cursor: 'pointer' }}
          onClick={(e) => {
            const rect = e.currentTarget.getBoundingClientRect();
            seek(((e.clientX - rect.left) / rect.width) * duration);
          }}
        >
          <div style={{
            position: 'absolute', left: 0, top: 0, height: '100%', borderRadius: 2,
            background: 'linear-gradient(90deg, #7c3aed, #00f0ff)',
            width: `${progress * 100}%`,
            transition: 'width 0.1s linear',
          }} />
        </div>
        <span style={{ fontSize: 11, color: '#64748b', flexShrink: 0, fontVariantNumeric: 'tabular-nums' }}>{fmt(duration)}</span>
      </div>

      {/* Shuffle / Repeat */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 6, flexShrink: 0 }}>
        <button
          onClick={toggleShuffle}
          style={{ ...btnStyle, color: shuffle ? '#00f0ff' : '#475569', fontSize: 16 }}
          title="Shuffle"
        >🔀</button>
        <button
          onClick={cycleRepeat}
          style={{ ...btnStyle, color: repeat !== 'none' ? '#a855f7' : '#475569', fontSize: 16 }}
          title={repeat === 'none' ? 'Repeat off' : repeat === 'all' ? 'Repeat all' : 'Repeat one'}
        >
          {repeat === 'one' ? '🔂' : '🔁'}
        </button>
      </div>
    </div>
  );
}

const btnStyle = {
  background: 'none', border: '1px solid rgba(255,255,255,0.1)', borderRadius: 6,
  color: '#94a3b8', fontSize: 18, cursor: 'pointer', width: 34, height: 34,
  display: 'flex', alignItems: 'center', justifyContent: 'center',
  transition: 'color 0.15s, border-color 0.15s',
};
