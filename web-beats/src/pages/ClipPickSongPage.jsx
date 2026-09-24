import { useEffect, useState } from 'react';
import { Link, Navigate, useNavigate } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import { BACKEND_URL } from '../brand';
import { useClipsEnabled } from '../hooks/useClipsEnabled';
import { pickableSongs } from '../utils/clipVisual';
import { gLabel } from '../utils/genres';
import { deriveClipHandle } from '../utils/clipHandle';
import { ZeusClipsWordmark, ClipsAiBadge } from '../components/ClipsBranding';
import { CLIPS_NAV_H_VAR, COOKIE_BANNER_H_VAR } from '../utils/clipsChrome';

const CYAN = '#00f0ff';

/**
 * "Pick a song" — where the bottom nav's "+" goes. A plain list of the user's
 * finished songs; tapping one opens the clip creator with it (passing the
 * song via router state, exactly like SongCard's "Create Clip" button).
 * Same CLIPS_ENABLED gate as the creator itself.
 */
export default function ClipPickSongPage() {
  const { token, user } = useAuth();
  const canCreateClip = useClipsEnabled(user);
  const navigate = useNavigate();
  const [songs, setSongs] = useState(null);
  const [error, setError] = useState(false);

  useEffect(() => {
    fetch(`${BACKEND_URL}/api/library`, { headers: { Authorization: `Bearer ${token}` } })
      .then(r => { if (!r.ok) throw new Error(); return r.json(); })
      .then(d => setSongs(pickableSongs(d.variants)))
      .catch(() => setError(true));
  }, [token]);

  const page = {
    background: '#0a0a14', minHeight: '100svh', color: '#fff',
    padding: `20px 20px calc(40px + var(${CLIPS_NAV_H_VAR}, 0px) + var(${COOKIE_BANNER_H_VAR}, 0px))`,
  };

  const header = (
    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 22 }}>
      <ZeusClipsWordmark />
      <ClipsAiBadge />
    </div>
  );

  if (!canCreateClip) {
    return (
      <div style={page}>
        {header}
        <p style={{ color: 'rgba(255,255,255,0.7)', fontSize: 15, textAlign: 'center', marginTop: 60 }}>
          Zeus Clips isn&apos;t open to everyone yet — check back soon.
        </p>
      </div>
    );
  }

  return (
    <div style={page}>
      {header}
      <h1 style={{ fontFamily: 'Orbitron, sans-serif', fontSize: 20, fontWeight: 800, margin: '0 0 4px' }}>Pick a song</h1>
      <p style={{ color: 'rgba(255,255,255,0.55)', fontSize: 14, margin: '0 0 18px' }}>
        Choose one of your songs to make a clip from.
      </p>

      {error && <p style={{ color: '#f87171', fontSize: 14 }}>Couldn&apos;t load your songs — please try again.</p>}
      {!error && songs === null && <p style={{ color: 'rgba(255,255,255,0.5)', fontSize: 14 }}>Loading your songs…</p>}

      {songs && songs.length === 0 && (
        <div style={{ textAlign: 'center', marginTop: 40 }}>
          <p style={{ color: 'rgba(255,255,255,0.7)', fontSize: 15 }}>You don&apos;t have any finished songs yet.</p>
          <Link to="/songs" style={{ color: CYAN, fontWeight: 700, textDecoration: 'none' }}>Make your first song →</Link>
        </div>
      )}

      <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
        {(songs || []).map(s => (
          <button
            key={s.variant_id}
            type="button"
            onClick={() => navigate(`/clips/new?song=${s.variant_id}`, { state: { song: s } })}
            style={{
              display: 'flex', alignItems: 'center', gap: 12, width: '100%', textAlign: 'left',
              padding: 10, borderRadius: 14, cursor: 'pointer', color: '#fff',
              background: 'rgba(255,255,255,0.04)', border: `1px solid ${CYAN}22`,
            }}
          >
            {s.image_url
              ? <img src={s.image_url} alt="" style={{ width: 52, height: 52, borderRadius: 10, objectFit: 'cover', flexShrink: 0 }} />
              : <span style={{ width: 52, height: 52, borderRadius: 10, flexShrink: 0, background: '#1a0a2e', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>🎵</span>}
            <span style={{ flex: 1, minWidth: 0 }}>
              <span style={{ display: 'block', fontSize: 15, fontWeight: 700, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                {s.title || 'Untitled'}
              </span>
              {s.genre_tag && (
                <span style={{ display: 'block', fontSize: 12, color: 'rgba(255,255,255,0.5)', marginTop: 2 }}>{gLabel(s.genre_tag)}</span>
              )}
            </span>
            <span style={{ color: CYAN, fontSize: 20, flexShrink: 0 }}>›</span>
          </button>
        ))}
      </div>
    </div>
  );
}

/** /clips/me → the signed-in user's own Clips profile (the bottom nav's "My Clips"). */
export function MyClipsRedirect() {
  const { user } = useAuth();
  const handle = deriveClipHandle(user?.artist_name || user?.name);
  return <Navigate to={`/clips/u/${handle}`} replace />;
}
