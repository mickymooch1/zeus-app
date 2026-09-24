import { clipVisualMode, kenBurnsStyle } from '../utils/clipVisual';
import { aboveBottomChrome } from '../utils/clipsChrome';

// Side insets of the framed-cover box. The right one keeps the cover clear of
// the action column (44px buttons at right: 14, labels slightly wider) at
// every phone width; ClipPage centres its play button on the same box.
export const FRAME_LEFT = 16;
export const FRAME_RIGHT = 72;

/**
 * The visual behind a clip, shared by the feed and the single-clip page.
 *
 * - video: the uploaded (muted) video, full-screen crop — unchanged.
 * - photo: the uploaded image, full-screen crop, with a slow Ken Burns zoom
 *   while playing.
 * - cover: song cover art is square — cropping it to a 9:16 screen threw away
 *   most of it. It's shown whole, centred between the header and the caption
 *   block, over a blurred/darkened/zoomed copy of itself filling the screen;
 *   the framed cover gets the Ken Burns zoom while playing.
 * - none: the plain gradient fallback.
 *
 * `frameTop`/`frameBottom` bound the framed cover (px from the top, and px
 * above the bottom chrome) so it never sits under the header or the caption.
 */
export default function ClipVisual({
  mediaType, url, playing, duration, alt = '', videoRef, frameTop = 142, frameBottom = 330,
}) {
  const mode = clipVisualMode(mediaType, url);
  const fill = { position: 'absolute', inset: 0, width: '100%', height: '100%', objectFit: 'cover' };
  const kb = kenBurnsStyle(duration, playing);

  if (mode === 'video') {
    return <video ref={videoRef} src={url} autoPlay muted loop playsInline className="clip-video" style={fill} />;
  }
  if (mode === 'photo') {
    return (
      <div style={{ position: 'absolute', inset: 0, overflow: 'hidden' }}>
        <img src={url} alt={alt} className="clip-ken-burns" style={{ ...fill, ...kb }} />
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
        <div style={{
          position: 'absolute', top: frameTop, bottom: aboveBottomChrome(frameBottom), left: FRAME_LEFT, right: FRAME_RIGHT,
          display: 'flex', alignItems: 'center', justifyContent: 'center', pointerEvents: 'none',
          containerType: 'size',
        }}>
          <img
            src={url}
            alt={alt}
            className="clip-ken-burns"
            style={{
              // Largest square that fits the frame, whatever the image's natural size.
              width: 'min(100cqw, 100cqh)', height: 'min(100cqw, 100cqh)',
              // Song covers are square, so this shows the whole cover; a stray
              // non-square image is centre-cropped to the square, never letterboxed.
              objectFit: 'cover',
              borderRadius: 18, boxShadow: '0 18px 50px rgba(0,0,0,0.65), 0 0 40px rgba(0,240,255,0.18)',
              ...kb,
            }}
          />
        </div>
      </div>
    );
  }
  return <div style={{ position: 'absolute', inset: 0, background: 'linear-gradient(135deg, #0d0d1a 0%, #1a0a2e 100%)' }} />;
}
