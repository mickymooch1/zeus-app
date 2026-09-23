import { useEffect, useRef, useState } from 'react';
import { useLocation, useNavigate, useSearchParams, Link } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import { BACKEND_URL } from '../brand';
import { readUtmAttribution } from '../utils/utmAttribution';
import { clipSeekTarget, clipInitialTime } from '../utils/clipPlayback';
import { useClipsEnabled } from '../hooks/useClipsEnabled';

const CYAN = '#00f0ff';
const PURPLE = '#7c3aed';
const DURATIONS = [15, 30];
const FALLBACK_SONG_LENGTH = 240; // used only if duration_seconds is somehow missing

function formatTime(seconds) {
  const s = Math.max(0, Math.round(seconds));
  return `${Math.floor(s / 60)}:${String(s % 60).padStart(2, '0')}`;
}

/**
 * Publish a clip from one of the user's own finished songs (build brief Phase 2).
 * Reached from SongCard's "🎬 Create Clip" button, which passes the full song via
 * router state (no extra fetch needed) and `?song=` as a fallback if state is
 * missing — e.g. a page refresh, which drops state but keeps the URL.
 */
export default function ClipCreatorPage() {
  const { token, user } = useAuth();
  const canCreateClip = useClipsEnabled(user);
  const navigate = useNavigate();
  const location = useLocation();
  const [searchParams] = useSearchParams();
  const songId = Number(searchParams.get('song'));

  const [song, setSong]         = useState(location.state?.song || null);
  const [loadingSong, setLoadingSong] = useState(!location.state?.song);
  const [notFound, setNotFound] = useState(false);

  const [mediaType, setMediaType]   = useState('cover'); // 'cover' | 'image' | 'video'
  const [uploadedUrl, setUploadedUrl] = useState(null);
  const [uploading, setUploading]   = useState(false);
  const [uploadError, setUploadError] = useState('');

  const [startTime, setStartTime]   = useState(0);
  const [duration, setDuration]     = useState(15);
  const [caption, setCaption]       = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [error, setError]           = useState('');

  const [previewPlaying, setPreviewPlaying] = useState(false);
  const audioRef = useRef(null);

  // Fallback: state is missing (e.g. a refresh) — re-find the song from the
  // library rather than inventing a new single-song endpoint for this one case.
  useEffect(() => {
    if (song || !songId) { setLoadingSong(false); return; }
    fetch(`${BACKEND_URL}/api/library`, { headers: { Authorization: `Bearer ${token}` } })
      .then(r => r.json())
      .then(d => {
        const found = (d.variants || []).find(v => v.variant_id === songId);
        if (found) setSong(found);
        else setNotFound(true);
      })
      .catch(() => setNotFound(true))
      .finally(() => setLoadingSong(false));
  }, [song, songId, token]);

  const songLength = song?.duration_seconds || FALLBACK_SONG_LENGTH;
  const maxStart = Math.max(0, songLength - duration);

  // A duration change (15s <-> 30s) can push the current window past the end
  // of the song — pull it back in rather than letting it silently overflow.
  useEffect(() => {
    setStartTime(s => Math.min(s, maxStart));
  }, [maxStart]);

  // Clamp playback to the selected window — the SAME clamp used on every clip
  // playback surface (feed, clip page), so "what you preview here" and "what
  // plays once published" can never drift apart.
  useEffect(() => {
    const a = audioRef.current;
    if (!a) return undefined;
    const onTime = () => {
      const target = clipSeekTarget(a.currentTime, startTime, duration);
      if (target !== null) a.currentTime = target;
    };
    const onEnded = () => { a.currentTime = startTime; a.play().catch(() => {}); };
    a.addEventListener('timeupdate', onTime);
    a.addEventListener('ended', onEnded);
    return () => {
      a.removeEventListener('timeupdate', onTime);
      a.removeEventListener('ended', onEnded);
    };
  }, [startTime, duration]);

  const playPreview = () => {
    const a = audioRef.current;
    if (!a) return;
    a.currentTime = clipInitialTime(startTime, duration);
    a.play().then(() => setPreviewPlaying(true)).catch(() => {});
  };
  const pausePreview = () => {
    audioRef.current?.pause();
    setPreviewPlaying(false);
  };

  const handleFileChange = async (e) => {
    const f = e.target.files?.[0];
    if (!f) return;
    setUploadError('');
    setUploading(true);
    setUploadedUrl(null);
    try {
      const form = new FormData();
      form.append('file', f);
      form.append('media_type', mediaType);
      const r = await fetch(`${BACKEND_URL}/api/clips/upload-media`, {
        method: 'POST',
        headers: { Authorization: `Bearer ${token}` },
        body: form,
      });
      const d = await r.json().catch(() => ({}));
      if (!r.ok) {
        setUploadError((typeof d.detail === 'string' ? d.detail : d.detail?.message) || 'Upload failed.');
        return;
      }
      setUploadedUrl(d.media_url);
    } catch {
      setUploadError('Network error — please try again.');
    } finally {
      setUploading(false);
    }
  };

  const canSubmit = song && !uploading && !submitting
    && (mediaType === 'cover' || !!uploadedUrl)
    && caption.length <= 150;

  const handleSubmit = async () => {
    if (!canSubmit) return;
    setError('');
    setSubmitting(true);
    try {
      const body = {
        song_id: song.variant_id,
        caption,
        media_type: mediaType,
        media_url: mediaType === 'cover' ? null : uploadedUrl,
        clip_start_time: startTime,
        clip_duration: duration,
        make_song_public: !song.is_public,
        ...(readUtmAttribution() || {}),
      };
      const r = await fetch(`${BACKEND_URL}/api/clips`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
        body: JSON.stringify(body),
      });
      const d = await r.json().catch(() => ({}));
      if (!r.ok) {
        setError((typeof d.detail === 'string' ? d.detail : d.detail?.message) || 'Could not publish this clip.');
        return;
      }
      navigate(`/clips/${d.id}`, { replace: true });
    } catch {
      setError('Network error — please try again.');
    } finally {
      setSubmitting(false);
    }
  };

  if (loadingSong) {
    return (
      <div style={{ background: '#0a0a14', minHeight: '100svh', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
        <div style={{ width: 36, height: 36, borderRadius: '50%', border: `3px solid ${CYAN}33`, borderTopColor: CYAN, animation: 'spin 0.8s linear infinite' }} />
        <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
      </div>
    );
  }

  if (notFound || !song) {
    return (
      <div style={{ background: '#0a0a14', minHeight: '100svh', color: '#fff', display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', gap: 20, padding: 24 }}>
        <p style={{ color: 'rgba(255,255,255,0.5)', fontSize: 15 }}>Couldn&apos;t find that song.</p>
        <Link to="/songs" style={{ color: CYAN, fontWeight: 600, textDecoration: 'none' }}>← Back to my songs</Link>
      </div>
    );
  }

  // CLIPS_ENABLED is off and this user isn't an admin: SongCard's "Create
  // Clip" button is already hidden from them, but a direct/bookmarked visit
  // to this URL would otherwise only find out on submit (a 403 from
  // publish_clip). Tell them clearly instead. This is a UI convenience only
  // — the real enforcement is server-side.
  if (!canCreateClip) {
    return (
      <div style={{ background: '#0a0a14', minHeight: '100svh', color: '#fff', display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', gap: 20, padding: 24, textAlign: 'center' }}>
        <p style={{ color: 'rgba(255,255,255,0.7)', fontSize: 15, maxWidth: 320 }}>
          Zeus Clips isn&apos;t open to everyone yet — check back soon.
        </p>
        <Link to="/songs" style={{ color: CYAN, fontWeight: 600, textDecoration: 'none' }}>← Back to my songs</Link>
      </div>
    );
  }

  const pill = (active) => ({
    padding: '9px 18px', borderRadius: 999, fontSize: 13, fontWeight: 700, cursor: 'pointer',
    border: `1px solid ${active ? 'transparent' : 'rgba(255,255,255,0.18)'}`,
    background: active ? `linear-gradient(90deg, ${CYAN}, ${PURPLE})` : 'rgba(255,255,255,0.05)',
    color: active ? '#000' : 'rgba(255,255,255,0.65)',
  });

  const previewVisualUrl = mediaType === 'cover' ? song.image_url : uploadedUrl;
  const windowPct = (maxStart > 0 ? startTime / maxStart : 0) * 100;
  const windowWidthPct = Math.min(100, (duration / songLength) * 100);

  return (
    <div style={{ background: '#0a0a14', minHeight: '100svh', color: '#fff', padding: '32px 20px 60px', display: 'flex', flexDirection: 'column', alignItems: 'center' }}>
      <Link to="/songs" style={{ color: CYAN, textDecoration: 'none', fontSize: 17, fontWeight: 800, marginBottom: 24, textShadow: `0 0 16px ${CYAN}88` }}>
        ⚡ Zeus Beats
      </Link>

      <div style={{
        width: '100%', maxWidth: 460,
        background: 'linear-gradient(135deg, #0d0d1a 0%, #1a0a2e 100%)',
        border: `1px solid ${CYAN}33`, borderRadius: 20, padding: '26px 24px',
        boxShadow: `0 0 40px ${CYAN}14`,
      }}>
        <h1 style={{ fontFamily: 'Orbitron, sans-serif', fontSize: 19, fontWeight: 800, margin: '0 0 4px' }}>
          🎬 Create a clip
        </h1>
        <p style={{ color: 'rgba(255,255,255,0.5)', fontSize: 13, margin: '0 0 20px' }}>
          from &ldquo;{song.title || 'Untitled'}&rdquo;
        </p>

        <audio ref={audioRef} src={song.mp3_url} onEnded={() => setPreviewPlaying(false)} />

        {/* ── Live preview — the chosen visual in a vertical (9:16) frame, with a
             play button that plays the currently selected segment. ── */}
        <div style={{ display: 'flex', justifyContent: 'center', marginBottom: 22 }}>
          <div style={{
            position: 'relative', width: 168, aspectRatio: '9 / 16', borderRadius: 16,
            overflow: 'hidden', background: '#000', border: `1px solid ${CYAN}44`,
            boxShadow: `0 0 20px ${CYAN}22`, flexShrink: 0,
          }}>
            {mediaType === 'video' && previewVisualUrl ? (
              <video
                src={`${BACKEND_URL}${previewVisualUrl}`}
                muted loop playsInline autoPlay
                style={{ position: 'absolute', inset: 0, width: '100%', height: '100%', objectFit: 'cover' }}
              />
            ) : previewVisualUrl ? (
              <img
                src={mediaType === 'cover' ? previewVisualUrl : `${BACKEND_URL}${previewVisualUrl}`}
                alt=""
                style={{ position: 'absolute', inset: 0, width: '100%', height: '100%', objectFit: 'cover' }}
              />
            ) : (
              <div style={{
                position: 'absolute', inset: 0, display: 'flex', alignItems: 'center', justifyContent: 'center',
                textAlign: 'center', padding: 16, background: 'linear-gradient(135deg, #0d0d1a 0%, #1a0a2e 100%)',
              }}>
                <span style={{ color: 'rgba(255,255,255,0.4)', fontSize: 12, lineHeight: 1.5 }}>
                  Upload a {mediaType} to preview it here
                </span>
              </div>
            )}

            {/* Scrims matching the real feed/clip page treatment (ClipsFeedPage.jsx's
                ClipSlide) — top strip and bottom strip only, middle untouched. */}
            <div style={{
              position: 'absolute', top: 0, left: 0, right: 0, height: '20%',
              background: 'linear-gradient(to bottom, rgba(0,0,0,0.6) 0%, transparent 100%)',
              pointerEvents: 'none',
            }} />
            <div style={{
              position: 'absolute', bottom: 0, left: 0, right: 0, height: '45%',
              background: 'linear-gradient(to top, rgba(0,0,0,0.75) 0%, transparent 100%)',
              pointerEvents: 'none',
            }} />

            <button
              onClick={previewPlaying ? pausePreview : playPreview}
              aria-label={previewPlaying ? 'Pause preview' : 'Play preview'}
              style={{
                position: 'absolute', bottom: 10, right: 10, width: 40, height: 40, borderRadius: '50%',
                background: previewPlaying ? `${CYAN}33` : 'rgba(0,0,0,0.6)', border: `1.5px solid ${CYAN}`,
                color: CYAN, fontSize: 16, cursor: 'pointer', display: 'flex', alignItems: 'center', justifyContent: 'center',
                boxShadow: `0 0 14px ${CYAN}55`,
              }}
            >
              {previewPlaying ? '⏸' : '▶'}
            </button>
          </div>
        </div>

        {/* Media type */}
        <p style={{ fontSize: 12, fontWeight: 700, color: 'rgba(255,255,255,0.5)', textTransform: 'uppercase', letterSpacing: '0.04em', margin: '0 0 8px' }}>
          Visual
        </p>
        <div style={{ display: 'flex', gap: 8, marginBottom: 16 }}>
          {[['cover', '🖼️', 'Cover'], ['image', '📷', 'Photo'], ['video', '🎥', 'Video']].map(([v, icon, label]) => (
            <button
              key={v}
              onClick={() => { setMediaType(v); setUploadedUrl(null); setUploadError(''); }}
              style={{
                ...pill(mediaType === v), flex: 1, fontSize: 13, padding: '10px 4px',
                display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 5, whiteSpace: 'nowrap',
              }}
            >
              <span style={{ fontSize: 14 }}>{icon}</span>{label}
            </button>
          ))}
        </div>

        {mediaType !== 'cover' && (
          <div style={{ marginBottom: 18 }}>
            <input
              type="file"
              accept={mediaType === 'image' ? 'image/*' : 'video/*'}
              onChange={handleFileChange}
              style={{ color: 'rgba(255,255,255,0.7)', fontSize: 13, width: '100%' }}
            />
            {uploading && <p style={{ color: CYAN, fontSize: 12, marginTop: 6 }}>Uploading…</p>}
            {uploadedUrl && <p style={{ color: '#34d399', fontSize: 12, marginTop: 6 }}>✓ Uploaded</p>}
            {uploadError && <p style={{ color: '#f87171', fontSize: 12, marginTop: 6 }}>{uploadError}</p>}
          </div>
        )}

        {/* Duration */}
        <p style={{ fontSize: 12, fontWeight: 700, color: 'rgba(255,255,255,0.5)', textTransform: 'uppercase', letterSpacing: '0.04em', margin: '0 0 8px' }}>
          Length
        </p>
        <div style={{ display: 'flex', gap: 8, marginBottom: 16 }}>
          {DURATIONS.map(d => (
            <button key={d} onClick={() => setDuration(d)} style={pill(duration === d)}>{d}s</button>
          ))}
        </div>

        {/* Start time — a scrubber across the whole song, not a raw number.
            Releasing it plays the newly selected segment. */}
        <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 6 }}>
          <p style={{ fontSize: 12, fontWeight: 700, color: 'rgba(255,255,255,0.5)', textTransform: 'uppercase', letterSpacing: '0.04em', margin: 0 }}>
            Starts at
          </p>
          <p style={{ fontSize: 12, color: CYAN, fontWeight: 700, margin: 0, fontFamily: 'monospace' }}>
            {formatTime(startTime)}–{formatTime(startTime + duration)} <span style={{ color: 'rgba(255,255,255,0.35)' }}>of {formatTime(songLength)}</span>
          </p>
        </div>
        <div style={{ position: 'relative', height: 28, marginBottom: 18, display: 'flex', alignItems: 'center' }}>
          {/* Track + selected-window highlight, drawn behind the native range thumb */}
          <div style={{ position: 'absolute', left: 0, right: 0, height: 4, borderRadius: 2, background: 'rgba(255,255,255,0.12)' }} />
          <div style={{
            position: 'absolute', height: 4, borderRadius: 2,
            background: `linear-gradient(90deg, ${CYAN}, ${PURPLE})`,
            left: `${windowPct}%`, width: `${windowWidthPct}%`,
          }} />
          <input
            type="range"
            min={0}
            max={maxStart}
            step={1}
            value={startTime}
            onChange={e => setStartTime(Number(e.target.value))}
            onMouseUp={playPreview}
            onTouchEnd={playPreview}
            onKeyUp={playPreview}
            aria-label="Clip start time"
            style={{
              position: 'relative', width: '100%', margin: 0, accentColor: CYAN, cursor: 'pointer',
              background: 'transparent',
            }}
          />
        </div>

        {/* Caption */}
        <p style={{ fontSize: 12, fontWeight: 700, color: 'rgba(255,255,255,0.5)', textTransform: 'uppercase', letterSpacing: '0.04em', margin: '0 0 8px' }}>
          Caption
        </p>
        <textarea
          value={caption}
          maxLength={150}
          onChange={e => setCaption(e.target.value)}
          placeholder="Say something about this one…"
          rows={2}
          style={{
            width: '100%', boxSizing: 'border-box', padding: '10px 14px', borderRadius: 10,
            border: '1px solid rgba(255,255,255,0.15)', background: 'rgba(255,255,255,0.04)',
            color: '#fff', fontSize: 14, marginBottom: 6, resize: 'vertical', fontFamily: 'inherit',
          }}
        />
        <p style={{ textAlign: 'right', fontSize: 11, color: 'rgba(255,255,255,0.35)', margin: '0 0 18px' }}>
          {caption.length}/150
        </p>

        {/* Publishing-makes-public notice — only when the song isn't already public */}
        {!song.is_public && (
          <div style={{
            background: 'rgba(251,191,36,0.1)', border: '1px solid rgba(251,191,36,0.4)',
            borderRadius: 10, padding: '10px 14px', marginBottom: 18,
          }}>
            <p style={{ margin: 0, color: '#fbbf24', fontSize: 12.5, fontWeight: 700 }}>
              ⚠️ Publishing will make this song public.
            </p>
            <p style={{ margin: '4px 0 0', color: 'rgba(255,255,255,0.55)', fontSize: 12, lineHeight: 1.5 }}>
              Anyone will be able to hear the full song, not just this clip.
            </p>
          </div>
        )}

        {error && <p style={{ color: '#f87171', fontSize: 13, marginBottom: 14 }}>{error}</p>}

        <button
          onClick={handleSubmit}
          disabled={!canSubmit}
          style={{
            width: '100%', padding: '16px 0', borderRadius: 999,
            background: `linear-gradient(90deg, ${CYAN}, ${PURPLE})`,
            color: '#000', fontWeight: 900, fontSize: 15, fontFamily: 'Orbitron, sans-serif',
            border: 'none', cursor: canSubmit ? 'pointer' : 'default', opacity: canSubmit ? 1 : 0.5,
            boxShadow: `0 0 26px ${CYAN}66`,
          }}
        >
          {submitting ? 'Publishing…' : '🎬 Publish Clip'}
        </button>
      </div>
    </div>
  );
}
