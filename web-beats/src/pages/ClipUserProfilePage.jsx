import { useEffect, useState } from 'react';
import { useParams, Link } from 'react-router-dom';
import { BACKEND_URL } from '../brand';
import { formatCount } from '../utils/formatCount';
import { ZeusClipsWordmark, ClipsAiBadge } from '../components/ClipsBranding';
import { CLIPS_NAV_H_VAR, COOKIE_BANNER_H_VAR } from '../utils/clipsChrome';

// Zeus Beats' own electric-blue → purple pair (see RemixButton.jsx).
const CYAN = '#00f0ff';
const PURPLE = '#7c3aed';

/**
 * A Clips profile — deliberately simple (build brief, 2026-09-24): avatar,
 * @handle, clip count, total likes, and a 3-column grid of their published
 * clips with play counts. NO followers/following/message/bio/links, no
 * Sounds/Remixes/Likes tabs — this is a read-only aggregate view of one
 * person's clips, not a social profile. See clips.get_user_public_profile
 * for what "handle" means here (not a real per-account username).
 */
export default function ClipUserProfilePage() {
  const { username } = useParams();
  const [profile, setProfile] = useState(null);
  const [loading, setLoading] = useState(true);
  const [notFound, setNotFound] = useState(false);

  useEffect(() => {
    setLoading(true);
    setNotFound(false);
    fetch(`${BACKEND_URL}/api/clips/u/${encodeURIComponent(username)}`)
      .then(r => { if (!r.ok) throw new Error('not found'); return r.json(); })
      .then(setProfile)
      .catch(() => setNotFound(true))
      .finally(() => setLoading(false));
  }, [username]);

  if (loading) {
    return (
      <div style={{ background: '#0a0a14', minHeight: '100svh', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
        <div style={{ width: 36, height: 36, borderRadius: '50%', border: `3px solid ${CYAN}33`, borderTopColor: CYAN, animation: 'spin 0.8s linear infinite' }} />
        <style>{'@keyframes spin { to { transform: rotate(360deg); } }'}</style>
      </div>
    );
  }

  if (notFound || !profile) {
    return (
      <div style={{ background: '#0a0a14', minHeight: '100svh', color: '#fff', display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', gap: 20, padding: 24 }}>
        <p style={{ color: 'rgba(255,255,255,0.5)', fontSize: 15 }}>No Clips profile for @{username}.</p>
        <Link to="/clips" style={{ color: CYAN, fontWeight: 600, textDecoration: 'none' }}>← Browse clips</Link>
      </div>
    );
  }

  const avatarUrl = profile.avatar_url
    ? (profile.avatar_url.startsWith('http') ? profile.avatar_url : `${BACKEND_URL}${profile.avatar_url}`)
    : null;

  return (
    <div style={{
      background: '#0a0a14', minHeight: '100svh', color: '#fff',
      // Room for the bottom nav (+ cookie banner) so the grid's last row isn't hidden.
      padding: `20px 20px calc(48px + var(${CLIPS_NAV_H_VAR}, 0px) + var(${COOKIE_BANNER_H_VAR}, 0px))`,
    }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 14 }}>
        <ZeusClipsWordmark />
        <ClipsAiBadge />
      </div>
      <Link to="/clips" style={{ color: CYAN, textDecoration: 'none', fontSize: 14, fontWeight: 700 }}>← Clips</Link>

      <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', marginTop: 24, marginBottom: 28 }}>
        <div style={{
          width: 84, height: 84, borderRadius: '50%', overflow: 'hidden', flexShrink: 0,
          border: `2px solid ${CYAN}`, boxShadow: `0 0 22px ${CYAN}55`,
          background: `linear-gradient(135deg, ${CYAN}33, ${PURPLE}33)`,
          display: 'flex', alignItems: 'center', justifyContent: 'center',
        }}>
          {avatarUrl ? (
            <img src={avatarUrl} alt="" style={{ width: '100%', height: '100%', objectFit: 'cover' }} />
          ) : (
            <span style={{ fontSize: 32, fontWeight: 800 }}>{(profile.display_name || '?')[0].toUpperCase()}</span>
          )}
        </div>

        <p style={{ margin: '14px 0 0', fontSize: 18, fontWeight: 800 }}>@{profile.handle}</p>
        {profile.display_name && profile.display_name.toLowerCase() !== profile.handle && (
          <p style={{ margin: '2px 0 0', fontSize: 13, color: 'rgba(255,255,255,0.5)' }}>{profile.display_name}</p>
        )}

        <div style={{ display: 'flex', gap: 32, marginTop: 18 }}>
          <div style={{ textAlign: 'center' }}>
            <p style={{ margin: 0, fontSize: 18, fontWeight: 800 }}>{formatCount(profile.clip_count)}</p>
            <p style={{ margin: 0, fontSize: 12, color: 'rgba(255,255,255,0.5)' }}>Clips</p>
          </div>
          <div style={{ textAlign: 'center' }}>
            <p style={{ margin: 0, fontSize: 18, fontWeight: 800 }}>{formatCount(profile.total_likes)}</p>
            <p style={{ margin: 0, fontSize: 12, color: 'rgba(255,255,255,0.5)' }}>Likes</p>
          </div>
        </div>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 3 }}>
        {profile.clips.map(clip => {
          const thumbUrl = clip.media_type === 'cover'
            ? clip.song_cover_url
            : (clip.media_url ? `${BACKEND_URL}${clip.media_url}` : null);
          return (
            <Link
              key={clip.id}
              to={`/clips/${clip.id}`}
              style={{
                position: 'relative', aspectRatio: '9 / 16', borderRadius: 8, overflow: 'hidden',
                background: 'linear-gradient(135deg, #0d0d1a 0%, #1a0a2e 100%)', textDecoration: 'none',
              }}
            >
              {thumbUrl && (
                <img src={thumbUrl} alt="" style={{ position: 'absolute', inset: 0, width: '100%', height: '100%', objectFit: 'cover' }} />
              )}
              <div style={{
                position: 'absolute', bottom: 0, left: 0, right: 0, padding: '16px 6px 6px',
                background: 'linear-gradient(to top, rgba(0,0,0,0.75), transparent)',
                display: 'flex', alignItems: 'center', gap: 3,
              }}>
                <span style={{ fontSize: 11, color: '#fff' }}>▶</span>
                <span style={{ fontSize: 11, fontWeight: 700, color: '#fff', textShadow: '0 1px 3px rgba(0,0,0,0.9)' }}>
                  {formatCount(clip.view_count)}
                </span>
              </div>
            </Link>
          );
        })}
      </div>

    </div>
  );
}
