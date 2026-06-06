import { useEffect, useRef } from 'react';

/* ── Animated space background ──────────────────────────────────────────────
   Canvas-based twinkling starfield with scroll parallax.
   Rendered fixed behind all app content; kids-shell overrides with its
   own solid background so stars never show in the kids UI.
   ─────────────────────────────────────────────────────────────────────────── */
export default function SpaceBackground() {
  const canvasRef = useRef(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    let raf;
    let scrollY = 0;

    const onScroll = () => { scrollY = window.scrollY; };
    window.addEventListener('scroll', onScroll, { passive: true });

    // 300 stars: 85% small dim, 15% larger twinkling with cross-sparkle
    const stars = Array.from({ length: 300 }, () => {
      const bright = Math.random() < 0.15;
      return {
        x: Math.random(),
        y: Math.random(),
        r: bright ? 1.6 + Math.random() * 0.9 : 0.35 + Math.random() * 1.0,
        speed: 0.25 + Math.random() * 0.85,
        phase: Math.random() * Math.PI * 2,
        drift: (Math.random() - 0.5) * 0.000028,
        parallax: 0.02 + Math.random() * 0.07,
        bright,
      };
    });

    let t = 0;

    function resize() {
      canvas.width = window.innerWidth;
      canvas.height = window.innerHeight;
    }
    resize();
    window.addEventListener('resize', resize, { passive: true });

    function draw() {
      const W = canvas.width;
      const H = canvas.height;
      ctx.clearRect(0, 0, W, H);
      t += 0.007;

      for (const s of stars) {
        // Slow lateral drift
        s.x += s.drift;
        if (s.x > 1) s.x -= 1;
        if (s.x < 0) s.x += 1;

        // Parallax scroll offset per layer depth
        const py = ((s.y * H + scrollY * s.parallax) % (H + 20)) - 10;
        const alpha = 0.28 + 0.72 * (0.5 + 0.5 * Math.sin(t * s.speed + s.phase));
        const px = s.x * W;

        ctx.beginPath();
        ctx.arc(px, py, s.r, 0, Math.PI * 2);
        ctx.fillStyle = `rgba(255,255,255,${alpha.toFixed(2)})`;
        ctx.fill();

        // Cross-sparkle on bright stars
        if (s.bright) {
          const sa = (alpha * 0.35).toFixed(2);
          ctx.strokeStyle = `rgba(200,230,255,${sa})`;
          ctx.lineWidth = 0.6;
          ctx.beginPath();
          ctx.moveTo(px - s.r * 3.5, py);
          ctx.lineTo(px + s.r * 3.5, py);
          ctx.moveTo(px, py - s.r * 3.5);
          ctx.lineTo(px, py + s.r * 3.5);
          ctx.stroke();
        }
      }

      raf = requestAnimationFrame(draw);
    }
    draw();

    return () => {
      cancelAnimationFrame(raf);
      window.removeEventListener('resize', resize);
      window.removeEventListener('scroll', onScroll);
    };
  }, []);

  return (
    <>
      {/* Deep space gradient + nebula clouds + planet decorations */}
      <div className="space-bg" aria-hidden="true" />
      {/* Twinkling star canvas */}
      <canvas ref={canvasRef} className="space-stars" aria-hidden="true" />
    </>
  );
}
