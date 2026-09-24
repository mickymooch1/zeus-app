import { clipVisualMode, kenBurnsStyle } from '../utils/clipVisual';

/**
 * The full-screen layer behind a clip (feed, clip page, Discover).
 *
 * - video: the uploaded (muted) video, full-screen crop.
 * - photo: the uploaded image, full-screen crop, slow Ken Burns zoom while playing.
 * - cover: a blurred / darkened / zoomed copy of the cover filling the screen.
 *   The cover itself is shown whole by <FramedCover>, placed in the layout's
 *   picture box (.clip-picture) so it can never overlap the header or caption.
 * - none: the plain gradient fallback.
 */
export default function ClipVisual({ mediaType, url, playing, duration, alt = '', videoRef }) {
  const mode = clipVisualMode(mediaType, url);
  const fill = { position: 'absolute', inset: 0, width: '100%', height: '100%', objectFit: 'cover' };

  if (mode === 'video') {
    return <video ref={videoRef} src={url} autoPlay muted loop playsInline className="clip-video" style={fill} />;
  }
  if (mode === 'photo') {
    return (
      <div style={{ position: 'absolute', inset: 0, overflow: 'hidden' }}>
        <img src={url} alt={alt} className="clip-ken-burns" style={{ ...fill, ...kenBurnsStyle(duration, playing) }} />
      </div>
    );
  }
  if (mode === 'cover') {
    return (
      <div style={{ position: 'absolute', inset: 0, overflow: 'hidden', background: '#05050c' }}>
        <img
          src={url}
          alt=""
          aria-hidden="true"
          style={{ ...fill, transform: 'scale(1.3)', filter: 'blur(28px) brightness(0.45) saturate(1.2)' }}
        />
      </div>
    );
  }
  return <div style={{ position: 'absolute', inset: 0, background: 'linear-gradient(135deg, #0d0d1a 0%, #1a0a2e 100%)' }} />;
}

/**
 * The whole square cover, as large as fits the picture box (.clip-framed in
 * index.css), with the Ken Burns zoom while playing. Renders nothing for
 * photo/video clips — their visual is the full-screen layer.
 */
export function FramedCover({ mediaType, url, playing, duration, alt = '' }) {
  if (clipVisualMode(mediaType, url) !== 'cover') return null;
  return (
    <div className="clip-framed">
      <img src={url} alt={alt} className="clip-ken-burns" style={kenBurnsStyle(duration, playing)} />
    </div>
  );
}
