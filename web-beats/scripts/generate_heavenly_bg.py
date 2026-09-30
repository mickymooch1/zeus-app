"""Generates the "Heavenly" memorial-page background artwork.

Original, procedurally generated art — every pixel comes from the maths below
(fractal-noise clouds lit from a single light source, soft rays, a perspective
stairway rising into a glowing doorway). No photo, stock image, AI image model
or third-party asset is involved, so there is nothing to license.

Run from web-beats/:   py scripts/generate_heavenly_bg.py
Writes  src/assets/memorial/heavenly-portrait.webp   (phones / portrait)
        src/assets/memorial/heavenly-landscape.webp  (desktop / landscape)
Deterministic (fixed seeds): re-running reproduces the same images.
Options:  --preview DIR  also writes PNG previews there
          --draft        half resolution, previews only (fast iteration)

Clouds, and why they are built this way (2026-09-30 rework — the first pass
read as solid rounded blobs):
  * shape   — fractal noise sampled through a second, domain-WARPING noise, so
              masses streak and curl instead of forming round cells;
  * edges   — a wide soft threshold, then eroded by fine detail noise, so the
              rim breaks up into wisps and fades out rather than ending at a line;
  * shading — for each pixel, the cloud between it and the light is summed
              along the way to the light (a cheap light march): faces toward
              the light glow, the far side falls into soft shade. No edge
              "emboss", which is what made the blobs look like cut-outs;
  * opacity — thin cloud is translucent and takes on the sky's glow.
"""
import math
import pathlib
import sys

import numpy as np
from PIL import Image
from scipy import ndimage

OUT = pathlib.Path(__file__).resolve().parent.parent / "src" / "assets" / "memorial"

LAYOUTS = {
    # v = fraction of image height from the top; half-widths in units of image height.
    "portrait": dict(size=(1080, 1920), light_v=0.125, stair_top_v=0.165, stair_bot_v=1.06,
                     half_top=0.030, half_bot=0.205, steps=26, seed=11),
    "landscape": dict(size=(1920, 1200), light_v=0.15, stair_top_v=0.20, stair_bot_v=1.08,
                      half_top=0.042, half_bot=0.46, steps=24, seed=41),
}
STAIR_EXP = 1.85  # perspective: steps bunch together as they recede


def smoothstep(a, b, x):
    t = np.clip((x - a) / (b - a + 1e-9), 0.0, 1.0)
    return t * t * (3 - 2 * t)


def lerp(a, b, t):
    return a + (b - a) * t


def fbm(h, w, rows, stretch, octaves, rng, gain=0.5):
    """Fractal value noise in [0,1]; `stretch` > 1 makes features wider than tall."""
    out = np.zeros((h, w), np.float32)
    amp, total = 1.0, 0.0
    for o in range(octaves):
        r = max(2, int(rows * 2 ** o))
        c = max(2, int(round(r * (w / h) / stretch)))
        grid = rng.random((r + 1, c + 1)).astype(np.float32)
        layer = ndimage.zoom(grid, (h / (r + 1), w / (c + 1)), order=3, mode="reflect", grid_mode=True)
        out += amp * layer[:h, :w]
        total += amp
        amp *= gain
    out /= total
    lo, hi = np.percentile(out, (1, 99))
    return np.clip((out - lo) / (hi - lo), 0, 1)


def ramp(d, stops):
    """Piecewise-linear colour ramp over distance d. stops: [(d, (r,g,b)), ...]"""
    ds = np.array([s[0] for s in stops], np.float32)
    cols = np.array([s[1] for s in stops], np.float32) / 255.0
    return np.stack([np.interp(d, ds, cols[:, k]) for k in range(3)], axis=-1)


def warped_noise(h, w, rows, stretch, rng, warp=0.06):
    """fbm sampled through a second noise field, so shapes streak and curl."""
    base = fbm(h, w, rows, stretch, 6, rng, gain=0.55)
    wx = fbm(h, w, rows * 1.3, stretch, 3, rng) - 0.5
    wy = fbm(h, w, rows * 1.3, stretch, 3, rng) - 0.5
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    amp = h * warp
    return ndimage.map_coordinates(base, [yy + wy * amp, xx + wx * amp * stretch], order=1, mode="reflect")


def cloud_density(h, w, rows, stretch, rng, cover, soft=(0.45, 0.72), erode=0.60):
    """Soft, wispy density in [0,1]: warped masses with detail-eroded edges."""
    shape = warped_noise(h, w, rows, stretch, rng) + (cover - 0.5) * 0.9
    body = smoothstep(soft[0], soft[1], shape)                       # wide ramp: no hard rim
    detail = warped_noise(h, w, rows * 5, stretch * 1.15, rng, warp=0.025)
    cut = erode * detail * (1 - body)                                # erosion bites the thin edges only
    dens = np.clip((body - cut) / (1 - cut + 1e-4), 0, 1)
    billow = warped_noise(h, w, rows * 2.4, stretch * 0.8, rng, warp=0.035)      # puffs inside the mass
    dens = np.clip(dens * (0.70 + 0.30 * smoothstep(0.15, 0.85, billow)) * 1.30, 0, 1)
    return ndimage.gaussian_filter(dens ** 1.1, h * 0.0014)


def light_march(dens, u, v, lu, lv, h, steps=10, reach=0.075, absorb=2.3):
    """Fraction of light reaching each pixel: sum the cloud on the way to the light."""
    yy, xx = np.mgrid[0:dens.shape[0], 0:dens.shape[1]].astype(np.float32)
    du, dv = lu - u, lv - v
    n = np.sqrt(du * du + dv * dv) + 1e-6
    sx, sy = du / n * h * reach / steps, dv / n * h * reach / steps
    acc = np.zeros_like(dens)
    for i in range(1, steps + 1):
        acc += ndimage.map_coordinates(dens, [yy + sy * i, xx + sx * i], order=1, mode="nearest")
    return np.exp(-absorb * acc / steps * 2.2)


def composite_clouds(img, dens, u, v, lu, lv, d, h, strength=0.92):
    trans = light_march(dens, u, v, lu, lv, h)
    near = 1 - smoothstep(0.08, 0.95, d)
    lit = np.clip(0.24 + 0.72 * trans + 0.12 * near, 0, 1)[..., None] ** 0.85
    # shade: warm close to the light, cooling to a soft lilac far from it
    shade = ramp(d, [(0.0, (250, 222, 170)), (0.35, (238, 204, 184)), (0.75, (214, 196, 208)), (1.3, (186, 188, 220))])
    glow = ramp(d, [(0.0, (255, 254, 244)), (0.5, (255, 252, 242)), (1.3, (253, 248, 246))])
    colour = shade + (glow - shade) * lit
    a = (np.clip(dens, 0, 1) ** 0.85 * strength)[..., None]          # thin cloud stays translucent
    return img * (1 - a) + colour * a


def render(name, cfg, scale=1.0):
    w, h = int(cfg["size"][0] * scale), int(cfg["size"][1] * scale)
    rng = np.random.default_rng(cfg["seed"])
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    u = (xx - w / 2) / h
    v = yy / h
    lu, lv = 0.0, cfg["light_v"]
    d = np.sqrt((u - lu) ** 2 + (v - lv) ** 2)
    rs = h / min(w, h)                                     # noise rows scale: 1 landscape, ~1.8 portrait

    # ── sky: warm light radiating from the top of the stairway ──────────────
    img = ramp(d, [(0.0, (255, 254, 246)), (0.10, (255, 244, 204)), (0.28, (255, 218, 142)),
                   (0.52, (243, 188, 146)), (0.85, (204, 172, 190)), (1.25, (150, 162, 208))])

    # ── soft rays ───────────────────────────────────────────────────────────
    theta = np.arctan2(v - lv, u - lu)                      # 0..pi is below the light
    knots = ndimage.gaussian_filter1d(rng.random(64), 1.2, mode="wrap")
    knots = (knots - knots.min()) / (knots.max() - knots.min())
    strip = ndimage.zoom(knots, 2048 / 64, order=3, mode="wrap")
    ray = np.interp((theta + math.pi) / (2 * math.pi) * (len(strip) - 1), np.arange(len(strip)), strip)
    ray = smoothstep(0.35, 0.95, ray) * np.exp(-d * 1.9) * (0.30 + 0.70 * smoothstep(-0.3, 0.6, np.sin(theta)))
    ray = ndimage.gaussian_filter(ray, h * 0.006)
    img += ray[..., None] * np.array([1.0, 0.96, 0.82]) * 0.38

    # ── stairway geometry ───────────────────────────────────────────────────
    vt, vb = cfg["stair_top_v"], cfg["stair_bot_v"]
    q = np.clip((v - vt) / (vb - vt), 0, 1)                  # 0 at the top, 1 at the bottom
    s = 1 - q ** (1 / STAIR_EXP)                             # 0 at the bottom, 1 at the top
    half = cfg["half_top"] + (cfg["half_bot"] - cfg["half_top"]) * q
    px = 1.0 / h
    away_from_light = smoothstep(0.05, 0.24, d)

    # ── high, thin streaks of cloud (cirrus) across the upper sky ───────────
    cirrus = warped_noise(h, w, int(4 * rs), 6.0, rng, warp=0.03)
    cirrus = smoothstep(0.50, 0.98, cirrus) * (1 - smoothstep(0.35, 0.80, v)) * away_from_light
    img = composite_clouds(img, cirrus * 0.55, u, v, lu, lv, d, h, strength=0.75)

    # ── clouds behind the stairway ──────────────────────────────────────────
    corridor = smoothstep(half * 0.80, half * 1.30 + 0.03, np.abs(u))
    cover = (0.43 if rs > 1 else 0.37) + 0.24 * smoothstep(0.10, 0.75, v)
    back = cloud_density(h, w, int(4 * rs), 2.4, rng, cover)
    back *= (0.08 + 0.92 * corridor) * away_from_light
    img = composite_clouds(img, back, u, v, lu, lv, d, h, strength=0.80)

    # ── the stairway ────────────────────────────────────────────────────────
    k = s * cfg["steps"]
    f = k - np.floor(k)
    riser = (f < 0.40).astype(np.float32)
    nosing = np.exp(-((f - 0.43) / 0.035) ** 2)
    glow = (s ** 0.75)[..., None]
    tread_c = lerp(np.array([255, 246, 224], np.float32), np.array([255, 255, 252], np.float32), glow) / 255
    riser_c = lerp(np.array([232, 200, 150], np.float32), np.array([255, 245, 220], np.float32), glow) / 255
    riser_shade = (1.0 - 0.13 * smoothstep(0.0, 0.40, f))[..., None]      # darker just under the nosing
    tread_shade = (0.965 + 0.035 * smoothstep(0.40, 1.0, f))[..., None]
    step_c = tread_c * tread_shade * (1 - riser[..., None]) + riser_c * riser_shade * riser[..., None]
    step_c = np.clip(step_c + nosing[..., None] * 0.06, 0, 1)
    step_c *= (0.90 + 0.10 * smoothstep(0, half * 0.35, half - np.abs(u)))[..., None]   # side shading
    feather = 0.0035 + 0.006 * q                           # edges soften as the stairs come nearer
    inside = smoothstep(0.0, 1.0, (half - np.abs(u)) / feather) * (v >= vt)
    a = inside[..., None]
    img = img * (1 - a) + step_c * a

    # glowing doorway of light at the top of the stairs
    gw, gh = cfg["half_top"] * 1.35, cfg["half_top"] * 3.3
    gy = (v - (vt - gh * 0.45)) / gh
    gx = np.abs(u) / gw
    arch = np.where(gy < 0, np.sqrt(gx ** 2 + (gy * gh / gw) ** 2), np.maximum(gx, gy))
    door = 1 - smoothstep(0.85, 1.15, arch)
    img = img * (1 - door[..., None]) + door[..., None]

    # light spilling down the stairs and out around them
    spill = ndimage.gaussian_filter(inside * s, h * 0.02)
    img += spill[..., None] * np.array([1.0, 0.95, 0.80]) * 0.16

    # ── clouds in front: they drift across the stair edges and its foot ─────
    edge_zone = smoothstep(half * 0.30, half * 1.00 + 0.015, np.abs(u))
    cover_f = (0.40 if rs > 1 else 0.33) + 0.24 * smoothstep(0.18, 0.95, v)
    front = cloud_density(h, w, int(2.6 * rs + 0.5), 2.0, rng, cover_f) * edge_zone
    mist = warped_noise(h, w, int(3 * rs), 3.0, rng, warp=0.04)
    wisp = warped_noise(h, w, int(7 * rs), 3.5, rng, warp=0.05)
    band = np.exp(-(((np.abs(u) - half) / (0.022 + 0.075 * q)) ** 2))            # hugs both stair edges
    edge_wisps = band * smoothstep(0.40, 0.78, wisp) * smoothstep(0.02, 0.30, q) * 0.85
    foot = smoothstep(0.93, 1.04, v + 0.14 * (mist - 0.5))
    front = np.maximum(np.maximum(front, edge_wisps), foot * 0.85) * away_from_light
    img = composite_clouds(img, front, u, v, lu, lv, d, h, strength=0.92)

    # a breath of haze low down, so the far clouds melt into the distance
    haze = smoothstep(0.45, 1.0, v) * (0.25 + 0.75 * mist) * 0.07
    img = img * (1 - haze[..., None]) + np.array([252, 240, 232], np.float32) / 255 * haze[..., None]

    # ── bloom: everything bright glows ──────────────────────────────────────
    img = np.clip(img, 0, 1.6)
    bright = np.clip(img - 0.90, 0, None)
    img += ndimage.gaussian_filter(bright, (h * 0.012, h * 0.012, 0)) * 0.45
    img += ndimage.gaussian_filter(bright, (h * 0.05, h * 0.05, 0)) * 0.30
    img += np.exp(-(d / 0.075) ** 2)[..., None] * 0.30
    img *= (1 - 0.06 * smoothstep(0.55, 1.35, d))[..., None]                # faint vignette
    img += (rng.random((h, w, 1)).astype(np.float32) - 0.5) * 0.012         # dither, avoids banding
    return Image.fromarray((np.clip(img, 0, 1) * 255).astype(np.uint8), "RGB")


def main():
    preview = None
    if "--preview" in sys.argv:
        preview = pathlib.Path(sys.argv[sys.argv.index("--preview") + 1])
        preview.mkdir(parents=True, exist_ok=True)
    draft = "--draft" in sys.argv
    OUT.mkdir(parents=True, exist_ok=True)
    for name, cfg in LAYOUTS.items():
        img = render(name, cfg, scale=0.5 if draft else 1.0)
        if not draft:
            path = OUT / f"heavenly-{name}.webp"
            img.save(path, "WEBP", quality=92, method=6)
            print(f"{path.name}: {img.size[0]}x{img.size[1]}, {path.stat().st_size // 1024} KB")
        if preview:
            img.save(preview / f"heavenly-{name}.png")
            print("preview:", preview / f"heavenly-{name}.png")


if __name__ == "__main__":
    main()
