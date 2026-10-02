"""Generate every Zeus Beats app icon from the one master logo (brand/zeus-logo.png).

    py web-beats/scripts/make_app_icons.py            # from the repo root

The master is a gold ring on black. The ring itself almost touches the image
edge (and a glow does), so each output first cuts the ring out as a disc (black
corners -> transparent) and then places it at a set fraction of the canvas, so
the ring never touches an edge. Sizes per target:

  RING_ANY      0.88  web "any" icons, apple-touch, Play store, iOS app icon
  RING_MASKABLE 0.76  web maskable icons: inside the 80% maskable safe circle
  RING_ADAPTIVE 0.70  Android adaptive (TWA ic_maskable): the layer is 91dp of the
                      108dp canvas, so 0.70 * 91 = 63.7dp < the 66dp safe circle
  RING_EXPO_FG  0.58  Expo adaptive foreground (full 108dp canvas): 0.58 < 66/108
  RING_FAVICON  0.94  tiny tab icons: as large as possible, still clear of edges
"""
import io
import pathlib
import sys

from PIL import Image, ImageDraw, ImageFilter

ROOT = pathlib.Path(__file__).resolve().parents[2]
SRC = ROOT / "brand" / "zeus-logo.png"

# Measured on the master: ring's gold outer edge sits at r~573-600 of a 627 half
# width (the top glow reaches the edge). Cut at 602 with a soft edge.
CUT_RADIUS = 602 / 627
FEATHER = 3            # px at master scale

RING_ANY, RING_MASKABLE, RING_ADAPTIVE = 0.88, 0.76, 0.70
RING_EXPO_FG, RING_FAVICON, RING_LEGACY = 0.58, 0.94, 0.92
BLACK = (0, 0, 0, 255)
CLEAR = (0, 0, 0, 0)


def disc() -> Image.Image:
    im = Image.open(SRC).convert("RGBA")
    w, h = im.size
    r = CUT_RADIUS * w / 2
    mask = Image.new("L", (w, h), 0)
    ImageDraw.Draw(mask).ellipse((w / 2 - r, h / 2 - r, w / 2 + r, h / 2 + r), fill=255)
    mask = mask.filter(ImageFilter.GaussianBlur(FEATHER))
    im.putalpha(mask)
    return im.crop((int(w / 2 - r), int(h / 2 - r), int(w / 2 + r), int(h / 2 + r)))


def icon(d: Image.Image, size: int, ring: float, bg=BLACK, mode="RGBA") -> Image.Image:
    canvas = Image.new("RGBA", (size, size), bg)
    side = max(1, round(size * ring))
    piece = d.resize((side, side), Image.LANCZOS)
    off = (size - side) // 2
    canvas.alpha_composite(piece, (off, off))
    return canvas.convert(mode) if mode != "RGBA" else canvas


def monochrome(d: Image.Image, size: int, ring: float) -> Image.Image:
    """White silhouette for Android themed icons: bright gold areas -> opaque."""
    gray = d.convert("L")
    alpha = gray.point(lambda v: 0 if v < 90 else min(255, (v - 90) * 3))
    a = Image.composite(alpha, Image.new("L", d.size, 0), d.split()[-1])
    white = Image.new("RGBA", d.size, (255, 255, 255, 0))
    white.putalpha(a)
    return icon(white, size, ring, CLEAR)


def save(img: Image.Image, rel: str) -> None:
    p = ROOT / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    img.save(p, optimize=True)
    print(f"  {rel}  {img.size[0]}x{img.size[1]} {img.mode}")


def main() -> None:
    if not SRC.exists():
        sys.exit(f"missing {SRC}")
    d = disc()

    print("web (web-beats/public)")
    for s in (192, 512):
        save(icon(d, s, RING_ANY), f"web-beats/public/icons/icon-{s}.png")
        save(icon(d, s, RING_MASKABLE), f"web-beats/public/icons/icon-maskable-{s}.png")
    save(icon(d, 180, RING_ANY, mode="RGB"), "web-beats/public/icons/apple-touch-icon.png")
    save(icon(d, 32, RING_FAVICON, CLEAR), "web-beats/public/favicon-32.png")
    ico = icon(d, 256, RING_FAVICON, CLEAR)
    buf = io.BytesIO()
    ico.save(buf, format="ICO", sizes=[(16, 16), (32, 32), (48, 48)])
    (ROOT / "web-beats/public/favicon.ico").write_bytes(buf.getvalue())
    print("  web-beats/public/favicon.ico  16/32/48")

    print("android TWA (app/)")
    legacy = {"mdpi": 48, "hdpi": 72, "xhdpi": 96, "xxhdpi": 144, "xxxhdpi": 192}
    maskable = {"mdpi": 82, "hdpi": 123, "xhdpi": 164, "xxhdpi": 246, "xxxhdpi": 328}
    for dens, s in legacy.items():
        save(icon(d, s, RING_LEGACY, CLEAR), f"app/src/main/res/mipmap-{dens}/ic_launcher.png")
    for dens, s in maskable.items():
        save(icon(d, s, RING_ADAPTIVE), f"app/src/main/res/mipmap-{dens}/ic_maskable.png")
    for p in sorted((ROOT / "app/src/main/res").glob("drawable-*/splash.png")):
        s = Image.open(p).size[0]
        save(icon(d, s, 0.60), str(p.relative_to(ROOT)).replace("\\", "/"))
    save(icon(d, 512, RING_ANY), "store_icon.png")

    print("iOS / Expo (zeus-beats-ios/assets)")
    save(icon(d, 1024, RING_ANY, mode="RGB"), "zeus-beats-ios/assets/icon.png")       # no alpha (App Store)
    save(icon(d, 1024, 0.62, CLEAR), "zeus-beats-ios/assets/splash-icon.png")
    save(icon(d, 512, RING_EXPO_FG, CLEAR), "zeus-beats-ios/assets/android-icon-foreground.png")
    save(Image.new("RGBA", (512, 512), BLACK), "zeus-beats-ios/assets/android-icon-background.png")
    save(monochrome(d, 432, RING_EXPO_FG), "zeus-beats-ios/assets/android-icon-monochrome.png")
    save(icon(d, 48, RING_FAVICON, CLEAR), "zeus-beats-ios/assets/favicon.png")


if __name__ == "__main__":
    main()
