import { useEffect, useRef } from 'react';

/* ── Zeus Kids Beats — kid-friendly space background ─────────────────────────
   Colorful twinkling stars + cartoon planets. Fixed behind all kids content.
   KidsShell header/main/footer use z-index:1 so they render above (z-index:0).
   ─────────────────────────────────────────────────────────────────────────── */

const STAR_COLORS = [
  [255, 255, 255],   // white
  [255, 230, 50],    // yellow
  [255, 180, 220],   // pink
  [150, 220, 255],   // sky blue
  [200, 175, 255],   // lavender
  [140, 255, 190],   // mint
];

export default function KidsSpaceBackground() {
  const canvasRef = useRef(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    let raf;

    // 200 colorful stars, larger and more visible than adult stars
    const stars = Array.from({ length: 200 }, () => {
      const col = STAR_COLORS[Math.floor(Math.random() * STAR_COLORS.length)];
      return {
        x: Math.random(),
        y: Math.random(),
        r: 0.8 + Math.random() * 2.8,
        speed: 0.7 + Math.random() * 1.4,
        phase: Math.random() * Math.PI * 2,
        color: col,
        sparkle: Math.random() < 0.55,
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
      t += 0.014;

      for (const s of stars) {
        const [r, g, b] = s.color;
        const alpha = 0.4 + 0.6 * (0.5 + 0.5 * Math.sin(t * s.speed + s.phase));
        const px = s.x * W;
        const py = s.y * H;

        ctx.beginPath();
        ctx.arc(px, py, s.r, 0, Math.PI * 2);
        ctx.fillStyle = `rgba(${r},${g},${b},${alpha.toFixed(2)})`;
        ctx.fill();

        if (s.sparkle) {
          const sa = (alpha * 0.55).toFixed(2);
          ctx.strokeStyle = `rgba(${r},${g},${b},${sa})`;
          ctx.lineWidth = 0.8;
          const len = s.r * 4.5;
          ctx.beginPath();
          ctx.moveTo(px - len, py); ctx.lineTo(px + len, py);
          ctx.moveTo(px, py - len); ctx.lineTo(px, py + len);
          ctx.stroke();
        }
      }

      raf = requestAnimationFrame(draw);
    }
    draw();

    return () => {
      cancelAnimationFrame(raf);
      window.removeEventListener('resize', resize);
    };
  }, []);

  return (
    <>
      {/* Deep space gradient + nebula clouds */}
      <div className="kids-space-bg" aria-hidden="true" />

      {/* Planet 1 — large yellow/orange, top-right, with Saturn ring */}
      <div className="kids-planet kids-planet-yellow" aria-hidden="true" />

      {/* Planet 2 — pink/rose, bottom-left */}
      <div className="kids-planet kids-planet-pink" aria-hidden="true" />

      {/* Planet 3 — teal/blue, mid-right */}
      <div className="kids-planet kids-planet-blue" aria-hidden="true" />

      {/* Planet 4 — tiny green, top-left area */}
      <div className="kids-planet kids-planet-green" aria-hidden="true" />

      {/* Twinkling star canvas */}
      <canvas ref={canvasRef} className="kids-stars-canvas" aria-hidden="true" />
    </>
  );
}
