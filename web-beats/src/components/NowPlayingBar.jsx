import { useState, useEffect } from 'react';
import { useNowPlaying } from '../contexts/NowPlayingContext';
import LyricsModal from './LyricsModal';

const GENRE_LABEL = {
  hiphop:'Hip-hop', lofi:'Lo-Fi', edm:'EDM', irishjig:'Irish Jig', irishfolk:'Irish Folk',
  rnb:'R&B', bluessoul:'Blues Soul', drumandbass:'D&B', grime:'Grime', ukgarage:'UK Garage',
  jungle:'Jungle', bassline:'Bassline', house:'House', loversrock:'Lovers Rock', ukdrill:'UK Drill',
  kpop:'K-Pop', deepsoulblues:'Deep Soul Blues', ukstreetsoul:'UK Street Soul', technhouse:'Tech House',
  driftphonk:'Drift Phonk', jerseyclub:'Jersey Club', afroswing:'Afroswing', rastadub:'Rasta Dub', dancehall:'Dancehall',
  deeprotbassline:'Deeprot Bassline', jazz:'Jazz', electronicfunk:'Electronic Funk',
  syntheticpop:'Synthetic Pop', ragga:'Ragga', dubstep:'Dubstep',
  bhangra:'Bhangra', rockney:'Rockney', metal:'Metal',
  trap:'Trap', eastcoasthiphop:'East Coast Hip-Hop', poprap:'Pop Rap',
  synthwave:'Synthwave', gospel:'Gospel', trapsoul:'Trap Soul',
  meditation:'Meditation', christmas:'Christmas', corridos:'Corridos',
  healingfrequency:'Healing Frequency',
  swing:'Swing', vocaljazz:'Vocal Jazz', scat:'Scat Jazz', opera:'Opera', traditionalpop:'Traditional Pop',
  rocknroll:'Rock \'n\' Roll', southemsoul:'Southern Soul', countryamericana:'Country Americana',
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
  if (!s || !isFinite(s) || s < 0) return '0:00';
  return `${Math.floor(s / 60)}:${String(Math.floor(s % 60)).padStart(2, '0')}`;
}

// Shared seek-bar used in both layouts
function SeekBar({ currentTime, duration, seek }) {
  const progress = duration > 0 ? Math.min(1, currentTime / duration) : 0;
  return (
    <div
      role="slider"
      aria-label="Song progress"
      aria-valuemin={0}
      aria-valuemax={Math.round(duration)}
      aria-valuenow={Math.round(currentTime)}
      style={{
        flex: 1, position: 'relative', height: 8, borderRadius: 4,
        background: 'rgba(255,255,255,0.1)', cursor: 'pointer', minWidth: 60,
      }}
      onClick={(e) => {
        const rect = e.currentTarget.getBoundingClientRect();
        const ratio = Math.max(0, Math.min(1, (e.clientX - rect.left) / rect.width));
        seek(ratio * duration);
      }}
    >
      <div style={{
        position: 'absolute', left: 0, top: 0, height: '100%', borderRadius: 4,
        background: 'linear-gradient(90deg, #7c3aed, #00f0ff)',
        width: `${progress * 100}%`,
        transition: 'width 0.1s linear',
        pointerEvents: 'none',
      }} />
      <div style={{
        position: 'absolute', top: '50%', left: `${progress * 100}%`,
        transform: 'translate(-50%, -50%)',
        width: 14, height: 14, borderRadius: '50%',
        background: '#00f0ff', boxShadow: '0 0 6px rgba(0,240,255,0.8)',
        pointerEvents: 'none',
      }} />
    </div>
  );
}

export default function NowPlayingBar() {
  const {
    currentSong, isPlaying, togglePlay, next, prev,
    currentTime, duration, seek, rewind, forward,
    shuffle, toggleShuffle, repeat, cycleRepeat,
    dismiss,
  } = useNowPlaying();

  const [isMobile, setIsMobile] = useState(
    typeof window !== 'undefined' && window.innerWidth < 640,
  );
  const [showLyrics, setShowLyrics] = useState(false);
  const hasLyrics = currentSong?.lyric_id != null;

  useEffect(() => {
    const check = () => setIsMobile(window.innerWidth < 640);
    window.addEventListener('resize', check, { passive: true });
    return () => window.removeEventListener('resize', check);
  }, []);

  // Bar stays visible whenever a song is loaded — hide only when nothing is in the queue.
  // This prevents pause from unmounting the bar (which would make users re-click play
  // from the playlist and restart the song from the beginning).
  const visible = !!currentSong;

  useEffect(() => {
    document.body.style.paddingBottom = visible ? (isMobile ? '108px' : '80px') : '';
    return () => { document.body.style.paddingBottom = ''; };
  }, [visible, isMobile]);

  if (!visible) return null;

  const remaining = duration > 0 ? duration - currentTime : 0;

  const barBase = {
    position: 'fixed', bottom: 0, left: 0, right: 0, zIndex: 9999,
    background: 'linear-gradient(180deg, rgba(10,10,20,0.97) 0%, #0a0a14 100%)',
    borderTop: '1px solid rgba(0,240,255,0.18)',
    backdropFilter: 'blur(20px)',
    boxShadow: '0 -4px 40px rgba(0,240,255,0.08)',
  };

  // ── Mobile layout: 2 rows ─────────────────────────────────────────────────
  if (isMobile) {
    return (
      <>
      <div style={{ ...barBase, padding: '8px 14px 10px' }}>
        <button
          onClick={dismiss}
          aria-label="Close player"
          style={{ position: 'absolute', right: 8, top: 8, background: 'none', border: 'none', color: '#475569', fontSize: 16, cursor: 'pointer', lineHeight: 1, padding: 4 }}
        >✕</button>
        {/* Row 1: art + title + transport controls */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 8 }}>
          {currentSong.image_url
            ? <img src={currentSong.image_url} alt="" className="cover-ken-burns cover-glow-pulse" style={{ width: 36, height: 36, borderRadius: 5, objectFit: 'cover', flexShrink: 0, border: '1px solid rgba(0,240,255,0.2)' }} />
            : <div style={{ width: 36, height: 36, borderRadius: 5, background: 'rgba(124,58,237,0.3)', display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0, fontSize: 16 }}>♫</div>
          }
          <div style={{ minWidth: 0, flex: 1 }}>
            <div style={{ fontSize: 12, fontWeight: 700, color: '#e2e8f0', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
              {currentSong.title || 'Untitled'}
            </div>
          </div>
          {/* ⏮ ⏪ ⏸/▶ ⏩ ⏭ — 44px tap targets */}
          <div style={{ display: 'flex', alignItems: 'center', gap: 2, flexShrink: 0 }}>
            <button onClick={prev}       style={mBtn}     title="Previous">⏮</button>
            <button onClick={rewind}     style={mBtn}     title="−10s">⏪</button>
            <button onClick={togglePlay} style={mBtnPlay} title={isPlaying ? 'Pause' : 'Play'}>
              {isPlaying ? '⏸' : '▶'}
            </button>
            <button onClick={forward}    style={mBtn}     title="+10s">⏩</button>
            <button onClick={next}       style={mBtn}     title="Next">⏭</button>
          </div>
        </div>

        {/* Row 2: current time + seek bar + time remaining + lyrics */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <span style={{ fontSize: 11, color: '#64748b', flexShrink: 0, fontVariantNumeric: 'tabular-nums', minWidth: 30 }}>
            {fmt(currentTime)}
          </span>
          <SeekBar currentTime={currentTime} duration={duration} seek={seek} />
          <span style={{ fontSize: 11, color: '#64748b', flexShrink: 0, fontVariantNumeric: 'tabular-nums', minWidth: 38, textAlign: 'right' }}>
            -{fmt(remaining)}
          </span>
          {hasLyrics && (
            <button
              onClick={() => setShowLyrics(true)}
              aria-label="Show lyrics"
              title="Lyrics"
              style={{ ...mBtn, width: 40, height: 40, fontSize: 18, flexShrink: 0 }}
            >📜</button>
          )}
        </div>
      </div>
      {showLyrics && hasLyrics && (
        <LyricsModal lyricId={currentSong.lyric_id} title={currentSong.title} onClose={() => setShowLyrics(false)} />
      )}
      </>
    );
  }

  // ── Desktop layout: single row ────────────────────────────────────────────
  return (
    <>
    <div style={{ ...barBase, padding: '10px 20px 14px', display: 'flex', alignItems: 'center', gap: 16, paddingRight: 40 }}>
      {/* Thumb + info */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 10, minWidth: 0, flex: '0 0 200px', maxWidth: 200 }}>
        {currentSong.image_url
          ? <img src={currentSong.image_url} alt="" className="cover-ken-burns cover-glow-pulse" style={{ width: 40, height: 40, borderRadius: 6, objectFit: 'cover', flexShrink: 0, border: '1px solid rgba(0,240,255,0.2)' }} />
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

      {/* ⏮ ⏪ ⏸/▶ ⏩ ⏭ */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 6, flexShrink: 0 }}>
        <button onClick={prev}       style={dBtn}     title="Previous">⏮</button>
        <button onClick={rewind}     style={dBtn}     title="−10 seconds">⏪</button>
        <button
          onClick={togglePlay}
          style={{
            width: 44, height: 44, borderRadius: '50%', border: 'none', cursor: 'pointer',
            background: 'linear-gradient(135deg, #7c3aed, #00f0ff)',
            color: '#fff', fontSize: 18, display: 'flex', alignItems: 'center', justifyContent: 'center',
            boxShadow: '0 0 12px rgba(0,240,255,0.35)',
          }}
          title={isPlaying ? 'Pause' : 'Play'}
        >
          {isPlaying ? '⏸' : '▶'}
        </button>
        <button onClick={forward}    style={dBtn}     title="+10 seconds">⏩</button>
        <button onClick={next}       style={dBtn}     title="Next">⏭</button>
      </div>

      {/* Progress: current | seekbar | total */}
      <div style={{ flex: 1, display: 'flex', alignItems: 'center', gap: 8, minWidth: 0 }}>
        <span style={{ fontSize: 11, color: '#64748b', flexShrink: 0, fontVariantNumeric: 'tabular-nums' }}>
          {fmt(currentTime)}
        </span>
        <SeekBar currentTime={currentTime} duration={duration} seek={seek} />
        <span style={{ fontSize: 11, color: '#64748b', flexShrink: 0, fontVariantNumeric: 'tabular-nums' }}>
          {fmt(duration)}
        </span>
      </div>

      {/* Lyrics / Shuffle / Repeat */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 6, flexShrink: 0 }}>
        {hasLyrics && (
          <button
            onClick={() => setShowLyrics(true)}
            style={{ ...dBtn, fontSize: 16 }}
            aria-label="Show lyrics"
            title="Lyrics"
          >📜</button>
        )}
        <button
          onClick={toggleShuffle}
          style={{ ...dBtn, color: shuffle ? '#00f0ff' : '#475569', fontSize: 16 }}
          title="Shuffle"
        >🔀</button>
        <button
          onClick={cycleRepeat}
          style={{ ...dBtn, color: repeat !== 'none' ? '#a855f7' : '#475569', fontSize: 16 }}
          title={repeat === 'none' ? 'Repeat off' : repeat === 'all' ? 'Repeat all' : 'Repeat one'}
        >
          {repeat === 'one' ? '🔂' : '🔁'}
        </button>
      </div>

      {/* Dismiss */}
      <button
        onClick={dismiss}
        aria-label="Close player"
        style={{ position: 'absolute', right: 8, top: 8, background: 'none', border: 'none', color: '#475569', fontSize: 16, cursor: 'pointer', lineHeight: 1, padding: 4 }}
      >✕</button>
    </div>
    {showLyrics && hasLyrics && (
      <LyricsModal lyricId={currentSong.lyric_id} title={currentSong.title} onClose={() => setShowLyrics(false)} />
    )}
    </>
  );
}

// Desktop button style
const dBtn = {
  background: 'none', border: '1px solid rgba(255,255,255,0.1)', borderRadius: 6,
  color: '#94a3b8', fontSize: 18, cursor: 'pointer', width: 36, height: 36,
  display: 'flex', alignItems: 'center', justifyContent: 'center',
  transition: 'color 0.15s, border-color 0.15s',
};

// Mobile button style — 44px tap target
const mBtn = {
  background: 'none', border: '1px solid rgba(255,255,255,0.1)', borderRadius: 6,
  color: '#94a3b8', fontSize: 16, cursor: 'pointer', width: 44, height: 44,
  display: 'flex', alignItems: 'center', justifyContent: 'center',
  transition: 'color 0.15s',
};

const mBtnPlay = {
  width: 44, height: 44, borderRadius: '50%', border: 'none', cursor: 'pointer',
  background: 'linear-gradient(135deg, #7c3aed, #00f0ff)',
  color: '#fff', fontSize: 18,
  display: 'flex', alignItems: 'center', justifyContent: 'center',
  boxShadow: '0 0 10px rgba(0,240,255,0.35)',
};
