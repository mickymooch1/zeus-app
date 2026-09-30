"""Generates the "Heavenly" memorial-page background artwork.

Original, procedurally generated art — every pixel comes from the maths below
(fractal-noise clouds lit from a single light source, volumetric rays, a
perspective stairway, blossom branches). No photo, stock image, AI image model
or third-party asset is involved, so there is nothing to license.

Run from web-beats/:   py scripts/generate_heavenly_bg.py
Writes  src/assets/memorial/heavenly-portrait.webp   (phones / portrait)
        src/assets/memorial/heavenly-landscape.webp  (desktop / landscape)
Deterministic (fixed seeds): re-running reproduces the same images.
Optional:  --preview DIR   also writes small PNG previews there.
"""
import math
import pathlib
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFilter
from scipy import ndimage

OUT = pathlib.Path(__file__).resolve().parent.parent / "src" / "assets" / "memorial"

LAYOUTS = {
    # v = fraction of image height from the top; half-widths in units of image height.
    "portrait": dict(size=(1080, 1920), light_v=0.125, stair_top_v=0.165, stair_bot_v=1.06,
                     half_top=0.030, half_bot=0.205, steps=26, seed=11),
    "landscape": dict(size=(1920, 1200), light_v=0.15, stair_top_v=0.20, stair_bot_v=1.08,
                      half_top=0.042, half_bot=0.46, steps=24, seed=23),
}
STAIR_EXP = 1.85  # perspective: steps bunch together as they recede


def smoothstep(a, b, x):
    t = np.clip((x - a) / (b - a + 1e-9), 0.0, 1.0)
    return t * t * (3 - 2 * t)


def lerp(a, b, t):
    return a + (b - a) * t


def fbm(h, w, rows, stretch, octaves, rng):
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
        amp *= 0.5
    out /= total
    lo, hi = np.percentile(out, (1, 99))
    return np.clip((out - lo) / (hi - lo), 0, 1)


def ramp(d, stops):
    """Piecewise-linear colour ramp over distance d. stops: [(d, (r,g,b)), ...]"""
    ds = np.array([s[0] for s in stops], np.float32)
    cols = np.array([s[1] for s in stops], np.float32) / 255.0
    return np.stack([np.interp(d, ds, cols[:, k]) for k in range(3)], axis=-1)


def cloud_layer(img, dens, u, v, lu, lv, d, detail, strength=0.95):
    """Composite a cloud density field, rim-lit from the light at (lu, lv)."""
    hh = dens.shape[0]
    soft = ndimage.gaussian_filter(dens, hh * 0.004)
    gy, gx = np.gradient(soft)
    du, dv = lu - u, lv - v
    n = np.sqrt(du * du + dv * dv) + 1e-6
    rim = -(gx * du / n + gy * dv / n) * hh * 0.045    # edges facing the light catch it
    near = 1 - smoothstep(0.10, 0.95, d)
    lit = np.clip(0.56 + rim + 0.20 * (detail - 0.5) + 0.30 * near, 0, 1)[..., None]
    shadow = ramp(d, [(0.0, (255, 232, 184)), (0.35, (246, 214, 184)), (0.75, (218, 198, 204)), (1.3, (184, 182, 214))])
    highlight = np.array([255, 254, 248], np.float32) / 255.0
    colour = shadow + (highlight - shadow) * lit
    a = (dens * strength)[..., None]
    return img * (1 - a) + colour * a


def petal_polygon(cx, cy, r, angle, rng, slim=1.0):
    """A soft teardrop petal pointing outward at `angle`."""
    pts = []
    width = r * rng.uniform(0.40, 0.52) * slim
    for i in range(22):
        t = i / 21 * 2 * math.pi
        along = (1 - math.cos(t)) / 2 * r * 1.05           # 0 at the base, r at the tip
        across = math.sin(t) * width * (0.35 + 0.65 * math.sin(math.pi * along / (r * 1.05)) ** 0.7)
        pts.append((cx + along * math.cos(angle) - across * math.sin(angle),
                    cy + along * math.sin(angle) + across * math.cos(angle)))
    return pts


def draw_blossom(draw, cx, cy, r, rng):
    base = rng.uniform(0, 2 * math.pi)
    tint = [(255, 253, 248), (255, 240, 236), (255, 247, 234)][rng.integers(0, 3)]
    for k in range(5):
        ang = base + k * 2 * math.pi / 5 + rng.uniform(-0.12, 0.12)
        rr = r * rng.uniform(0.9, 1.08)
        draw.polygon(petal_polygon(cx, cy, rr, ang, rng), fill=tint + (235,))
        inner = tuple(min(255, c + 6) for c in tint)
        draw.polygon(petal_polygon(cx, cy, rr * 0.62, ang, rng), fill=inner + (255,))
    c = r * 0.2
    draw.ellipse((cx - c, cy - c, cx + c, cy + c), fill=(240, 204, 128, 255))
    for _ in range(5):
        a, rad = rng.uniform(0, 2 * math.pi), r * rng.uniform(0.2, 0.34)
        x, y = cx + rad * math.cos(a), cy + rad * math.sin(a)
        draw.ellipse((x - r * 0.04, y - r * 0.04, x + r * 0.04, y + r * 0.04), fill=(222, 170, 92, 255))


def blossom_branch(layer, start, end, bend, scale, rng):
    """A thin branch from `start` curving to `end`, carrying blossoms, buds and leaves."""
    draw = ImageDraw.Draw(layer, "RGBA")
    (x0, y0), (x1, y1) = start, end
    mx, my = (x0 + x1) / 2 + bend[0], (y0 + y1) / 2 + bend[1]
    pts = []
    for i in range(41):
        t = i / 40
        pts.append(((1 - t) ** 2 * x0 + 2 * (1 - t) * t * mx + t * t * x1,
                    (1 - t) ** 2 * y0 + 2 * (1 - t) * t * my + t * t * y1))
    for i in range(len(pts) - 1):
        wdt = max(1, int(scale * 0.11 * (1 - i / len(pts)) + 1))
        draw.line([pts[i], pts[i + 1]], fill=(176, 142, 108, 170), width=wdt)
    for i in range(6, len(pts), 3):
        x, y = pts[i]
        side = rng.choice([-1, 1])
        jx, jy = rng.uniform(-0.5, 0.5) * scale, rng.uniform(-0.55, 0.35) * scale
        roll = rng.random()
        if roll < 0.5:
            draw_blossom(draw, x + jx, y + jy, scale * rng.uniform(0.34, 0.62), rng)
        elif roll < 0.72:                                   # bud
            b = scale * rng.uniform(0.12, 0.2)
            draw.ellipse((x + jx - b, y + jy - b * 1.3, x + jx + b, y + jy + b * 1.3), fill=(250, 214, 214, 235))
        else:                                               # leaf
            ang = rng.uniform(-math.pi, 0) + side * 0.3
            draw.polygon(petal_polygon(x, y, scale * rng.uniform(0.55, 0.85), ang, rng, slim=0.5), fill=(172, 192, 160, 200))


def render(name, cfg, scale=1.0):
    w, h = int(cfg["size"][0] * scale), int(cfg["size"][1] * scale)
    rng = np.random.default_rng(cfg["seed"])
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    u = (xx - w / 2) / h
    v = yy / h
    lu, lv = 0.0, cfg["light_v"]
    d = np.sqrt((u - lu) ** 2 + (v - lv) ** 2)

    # ── sky: warm light radiating from the top of the stairway ──────────────
    img = ramp(d, [(0.0, (255, 254, 246)), (0.10, (255, 247, 218)), (0.28, (255, 230, 168)),
                   (0.52, (250, 210, 170)), (0.85, (228, 194, 190)), (1.25, (190, 184, 212))])

    # ── volumetric rays ─────────────────────────────────────────────────────
    theta = np.arctan2(v - lv, u - lu)                      # 0..pi is below the light
    knots = ndimage.gaussian_filter1d(rng.random(64), 1.2, mode="wrap")
    knots = (knots - knots.min()) / (knots.max() - knots.min())
    strip = ndimage.zoom(knots, 2048 / 64, order=3, mode="wrap")
    ray = np.interp((theta + math.pi) / (2 * math.pi) * (len(strip) - 1), np.arange(len(strip)), strip)
    ray = smoothstep(0.35, 0.95, ray) * np.exp(-d * 1.9) * (0.30 + 0.70 * smoothstep(-0.3, 0.6, np.sin(theta)))
    ray = ndimage.gaussian_filter(ray, h * 0.006)
    img += ray[..., None] * np.array([1.0, 0.96, 0.82]) * 0.40

    # ── stairway geometry ───────────────────────────────────────────────────
    vt, vb = cfg["stair_top_v"], cfg["stair_bot_v"]
    q = np.clip((v - vt) / (vb - vt), 0, 1)                  # 0 at the top, 1 at the bottom
    s = 1 - q ** (1 / STAIR_EXP)                             # 0 at the bottom, 1 at the top
    half = cfg["half_top"] + (cfg["half_bot"] - cfg["half_top"]) * q
    px = 1.0 / h

    # ── clouds behind the stairway ──────────────────────────────────────────
    corridor = smoothstep(half * 0.85, half * 1.25 + 0.025, np.abs(u))
    rs = h / min(w, h)                                      # rows scale: 1 landscape, ~1.8 portrait
    n_back = fbm(h, w, int(5 * rs), 2.0, 6, rng)
    cover = 0.44 + 0.30 * smoothstep(0.10, 0.70, v)
    dens = smoothstep(0.47, 0.66, n_back + (cover - 0.5) * 0.9)
    dens *= (0.10 + 0.90 * corridor) * smoothstep(0.05, 0.22, d)
    img = cloud_layer(img, dens, u, v, lu, lv, d, fbm(h, w, 22, 1.4, 3, rng), strength=0.85)

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
    edge = (half - np.abs(u)) / (2.5 * px)
    step_c *= (0.90 + 0.10 * smoothstep(0, half * 0.35, half - np.abs(u)))[..., None]   # side shading
    inside = np.clip(edge, 0, 1) * (v >= vt)
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

    # ── clouds in front: they swallow the stair edges and its foot ──────────
    n_front = fbm(h, w, int(3 * rs + 0.5), 1.7, 6, rng)
    edge_zone = smoothstep(half * 0.50, half * 1.05 + 0.015, np.abs(u))
    cover_f = 0.42 + 0.44 * smoothstep(0.18, 0.95, v)
    dens_f = smoothstep(0.49, 0.68, n_front + (cover_f - 0.5) * 1.0) * edge_zone
    foot = smoothstep(0.90, 1.0, v + 0.10 * (n_front - 0.5))
    dens_f = np.maximum(dens_f, foot * 0.92) * smoothstep(0.06, 0.24, d)
    img = cloud_layer(img, dens_f, u, v, lu, lv, d, fbm(h, w, 26, 1.3, 3, rng), strength=0.95)

    # ── bloom: everything bright glows ──────────────────────────────────────
    img = np.clip(img, 0, 1.6)
    bright = np.clip(img - 0.90, 0, None)
    img += ndimage.gaussian_filter(bright, (h * 0.012, h * 0.012, 0)) * 0.45
    img += ndimage.gaussian_filter(bright, (h * 0.05, h * 0.05, 0)) * 0.30
    core = np.exp(-(d / 0.075) ** 2)
    img += core[..., None] * 0.30
    img *= (1 - 0.06 * smoothstep(0.55, 1.35, d))[..., None]                # faint vignette
    img += (rng.random((h, w, 1)).astype(np.float32) - 0.5) * 0.012         # dither, avoids banding
    base = Image.fromarray((np.clip(img, 0, 1) * 255).astype(np.uint8), "RGB").convert("RGBA")

    # ── floral touches: blossom branches reaching in from the lower corners ─
    ss = 2
    layer = Image.new("RGBA", (w * ss, h * ss), (0, 0, 0, 0))
    unit = h * ss * (0.019 if name == "portrait" else 0.027)
    W2, H2 = w * ss, h * ss
    frng = np.random.default_rng(cfg["seed"] + 100)
    if name == "portrait":
        branches = [((-0.02, 0.385), (0.31, 0.235), (-0.02, -0.09)), ((1.02, 0.36), (0.71, 0.225), (0.02, -0.08)),
                    ((-0.02, 0.99), (0.36, 0.83), (-0.02, -0.12)), ((1.02, 0.97), (0.66, 0.82), (0.02, -0.11))]
    else:
        branches = [((-0.01, 1.00), (0.25, 0.60), (-0.05, -0.16)), ((1.01, 0.99), (0.76, 0.58), (0.05, -0.15)),
                    ((-0.01, 0.70), (0.13, 0.42), (-0.03, -0.08)), ((1.01, 0.68), (0.88, 0.41), (0.03, -0.08))]
    for (sx, sy), (ex, ey), (bx, by) in branches:
        blossom_branch(layer, (sx * W2, sy * H2), (ex * W2, ey * H2), (bx * W2, by * H2), unit, frng)
    layer = layer.resize((w, h), Image.LANCZOS).filter(ImageFilter.GaussianBlur(h * 0.0011))
    halo = layer.filter(ImageFilter.GaussianBlur(h * 0.006))                  # soft glow behind the petals
    halo.putalpha(halo.getchannel("A").point(lambda p: int(p * 0.35)))
    base.alpha_composite(halo)
    base.alpha_composite(layer)
    return base.convert("RGB")


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
