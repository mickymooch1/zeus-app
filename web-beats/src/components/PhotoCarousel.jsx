import { useEffect, useRef, useState } from 'react';

const CAROUSEL_INTERVAL_MS = 4000;
const SWIPE_THRESHOLD_PX = 40;

// Auto-advancing, swipeable slideshow for 2-5 photos — a slow crossfade
// (not a hard cut) to match the page's calm tone. All photos are mounted at
// once, stacked and cross-faded via opacity, so there's no load-in flash
// when advancing. A single photo is rendered separately by the caller, in
// the same static framed style as before — this component is only for 2+.
export default function PhotoCarousel({ photos }) {
  const [index, setIndex] = useState(0);
  const touchStartRef = useRef(null);
  const wasSwipeRef = useRef(false);

  useEffect(() => {
    const id = setInterval(() => {
      setIndex((i) => (i + 1) % photos.length);
    }, CAROUSEL_INTERVAL_MS);
    return () => clearInterval(id);
  }, [index, photos.length]);

  const goTo = (i) => setIndex(((i % photos.length) + photos.length) % photos.length);
  const goNext = () => goTo(index + 1);
  const goPrev = () => goTo(index - 1);

  const handleTouchStart = (e) => {
    touchStartRef.current = e.touches[0].clientX;
    wasSwipeRef.current = false;
  };
  const handleTouchEnd = (e) => {
    if (touchStartRef.current == null) return;
    const delta = e.changedTouches[0].clientX - touchStartRef.current;
    touchStartRef.current = null;
    if (Math.abs(delta) >= SWIPE_THRESHOLD_PX) {
      wasSwipeRef.current = true;
      delta < 0 ? goNext() : goPrev();
    }
  };
  const handleClick = (e) => {
    // A swipe's trailing click shouldn't also count as a tap — consume it once.
    if (wasSwipeRef.current) { wasSwipeRef.current = false; return; }
    const frac = (e.clientX - e.currentTarget.getBoundingClientRect().left) / e.currentTarget.clientWidth;
    frac < 0.3 ? goPrev() : goNext();
  };

  return (
    <div>
      <div
        onTouchStart={handleTouchStart}
        onTouchEnd={handleTouchEnd}
        onClick={handleClick}
        style={{
          background: 'var(--sp-mat)',
          padding: 8,
          borderRadius: 10,
          boxShadow: '0 4px 16px var(--sp-shadow)',
          position: 'relative',
          aspectRatio: '1 / 1',
          cursor: 'pointer',
          touchAction: 'pan-y',
        }}
      >
        {photos.map((photo, i) => (
          <img
            key={photo.photo_id}
            src={photo.url}
            alt=""
            draggable={false}
            style={{
              position: 'absolute',
              inset: 8,
              width: 'calc(100% - 16px)',
              height: 'calc(100% - 16px)',
              objectFit: 'cover',
              borderRadius: 4,
              opacity: i === index ? 1 : 0,
              transition: 'opacity 1.4s ease',
              pointerEvents: 'none',
            }}
          />
        ))}
      </div>
      <div style={{ display: 'flex', justifyContent: 'center', gap: 8, marginTop: 12 }}>
        {photos.map((photo, i) => (
          <button
            key={photo.photo_id}
            onClick={() => goTo(i)}
            aria-label={`Show photo ${i + 1}`}
            style={{
              width: 7,
              height: 7,
              borderRadius: '50%',
              padding: 0,
              border: 'none',
              cursor: 'pointer',
              background: i === index ? 'var(--sp-accent)' : 'var(--sp-border)',
              transition: 'background 0.3s ease',
            }}
          />
        ))}
      </div>
    </div>
  );
}
