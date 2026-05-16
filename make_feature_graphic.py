"""
Generate Zeus Beats feature graphic — 1024x500 px, cyberpunk style.
"""
from PIL import Image, ImageDraw, ImageFont, ImageFilter

W, H = 1024, 500
OUT = r"C:\Users\Student\zeus-app\web-beats\public\feature-graphic.png"
FONT_DIR = r"C:\Windows\Fonts\\"

CYAN   = (0, 240, 255)
BLACK  = (0, 0, 0)
PURPLE = (139, 92, 246)
WHITE  = (255, 255, 255)

# ---------------------------------------------------------------------------
# Helper – load font with fallback
# ---------------------------------------------------------------------------
def load_font(name, size):
    try:
        return ImageFont.truetype(FONT_DIR + name, size)
    except Exception:
        return ImageFont.load_default()

# ---------------------------------------------------------------------------
# Build image
# ---------------------------------------------------------------------------
img = Image.new("RGBA", (W, H), (0, 0, 0, 255))

# ── 1. Background gradient vignette (subtle dark-purple centre glow) ────────
vign = Image.new("RGBA", (W, H), (0, 0, 0, 0))
vd   = ImageDraw.Draw(vign)
for r in range(220, 0, -4):
    alpha = int(60 * (1 - r / 220))
    vd.ellipse([W//2 - r*2, H//2 - r, W//2 + r*2, H//2 + r],
               fill=(20, 0, 40, alpha))
img = Image.alpha_composite(img, vign)

# ── 2. Grid lines ────────────────────────────────────────────────────────────
grid = Image.new("RGBA", (W, H), (0, 0, 0, 0))
gd   = ImageDraw.Draw(grid)

# Vertical lines
for x in range(0, W + 64, 64):
    gd.line([(x, 0), (x, H)], fill=(0, 240, 255, 22), width=1)

# Horizontal lines — denser / brighter near the bottom (perspective feel)
for y in range(0, H, 40):
    alpha = int(14 + 28 * (y / H))
    gd.line([(0, y), (W, y)], fill=(0, 240, 255, alpha), width=1)

img = Image.alpha_composite(img, grid)

# ── 3. Perspective floor rays from vanishing point ───────────────────────────
vp_x, vp_y = W // 2, int(H * 0.50)   # vanishing point
floor_layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
fd = ImageDraw.Draw(floor_layer)
for angle_pct in range(-20, 21, 2):   # -20..+20 steps of 2
    end_x = int(vp_x + angle_pct * W * 0.055)
    end_y = H + 10
    fd.line([(vp_x, vp_y), (end_x, end_y)], fill=(0, 240, 255, 18), width=1)
# Blur so they blend softly
floor_layer = floor_layer.filter(ImageFilter.GaussianBlur(radius=1))
img = Image.alpha_composite(img, floor_layer)

# ── 4. Border & corner brackets ──────────────────────────────────────────────
draw = ImageDraw.Draw(img)

# Outer border
draw.rectangle([0, 0, W - 1, H - 1], outline=(0, 240, 255, 120), width=2)

# Inner border
draw.rectangle([6, 6, W - 7, H - 7], outline=(0, 240, 255, 40), width=1)

# Corner brackets (L-shape)
BS = 28   # bracket size
BW = 3    # line width
BC = (0, 240, 255, 220)
corners = [(5, 5), (W - 5 - BS, 5), (5, H - 5 - BS), (W - 5 - BS, H - 5 - BS)]
for cx, cy in corners:
    # horizontal arm
    draw.line([(cx, cy + BS // 2), (cx + BS, cy + BS // 2)], fill=BC, width=BW)
    # vertical arm
    draw.line([(cx + BS // 2, cy), (cx + BS // 2, cy + BS)], fill=BC, width=BW)

# ── 5. Fonts ──────────────────────────────────────────────────────────────────
f_title  = load_font("AGENCYB.TTF",     96)
f_tag    = load_font("bahnschrift.ttf", 28)
f_pill   = load_font("bahnschrift.ttf", 18)
f_sub    = load_font("bahnschrift.ttf", 22)

# ── 6. Title glow then sharp text ────────────────────────────────────────────
title = "ZEUS BEATS"

# Measure title
bb = draw.textbbox((0, 0), title, font=f_title)
tw, th = bb[2] - bb[0], bb[3] - bb[1]

# Lightning bolt polygon (hand-drawn, relative to top-left anchor)
def bolt_pts(ox, oy, scale=1.0):
    pts = [
        (ox + 28*scale, oy + 0),
        (ox + 8*scale,  oy + 42*scale),
        (ox + 22*scale, oy + 42*scale),
        (ox + 0,        oy + 80*scale),
        (ox + 42*scale, oy + 36*scale),
        (ox + 28*scale, oy + 36*scale),
    ]
    return [(int(x), int(y)) for x, y in pts]

BOLT_W   = 48     # effective width of bolt area
BOLT_GAP = 16     # gap between bolt and "ZEUS BEATS"
total_title_w = BOLT_W + BOLT_GAP + tw

start_x  = (W - total_title_w) // 2
title_y  = 110
bolt_ox  = start_x
bolt_oy  = title_y + (th - 80) // 2   # vertically centre bolt with text
text_x   = start_x + BOLT_W + BOLT_GAP

# Glow for bolt
bpts = bolt_pts(bolt_ox, bolt_oy)
bolt_glow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
Image.alpha_composite   # just to check
ImageDraw.Draw(bolt_glow).polygon(bpts, fill=(0, 240, 255, 160))
bolt_glow = bolt_glow.filter(ImageFilter.GaussianBlur(radius=18))
img = Image.alpha_composite(img, bolt_glow)

# Glow for title text
txt_glow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
ImageDraw.Draw(txt_glow).text((text_x, title_y), title, font=f_title,
                               fill=(0, 240, 255, 160))
txt_glow = txt_glow.filter(ImageFilter.GaussianBlur(radius=14))
img = Image.alpha_composite(img, txt_glow)

# Sharp bolt
draw = ImageDraw.Draw(img)
draw.polygon(bpts, fill=(0, 240, 255, 255))
# Tiny highlight inside bolt
h_pts = bolt_pts(bolt_ox + 4, bolt_oy + 3, scale=0.55)
draw.polygon(h_pts, fill=(180, 255, 255, 120))

# Sharp title
draw.text((text_x, title_y), title, font=f_title, fill=CYAN + (255,))

# ── 7. Tagline ────────────────────────────────────────────────────────────────
tagline = "Create AI Music. Publish Everywhere."
bb_tag  = draw.textbbox((0, 0), tagline, font=f_tag)
tag_w   = bb_tag[2] - bb_tag[0]
tag_x   = (W - tag_w) // 2
tag_y   = title_y + th + 22

# Subtle glow for tagline
tag_glow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
ImageDraw.Draw(tag_glow).text((tag_x, tag_y), tagline, font=f_tag,
                               fill=(0, 240, 255, 120))
tag_glow = tag_glow.filter(ImageFilter.GaussianBlur(radius=6))
img = Image.alpha_composite(img, tag_glow)

draw = ImageDraw.Draw(img)
draw.text((tag_x, tag_y), tagline, font=f_tag, fill=(160, 240, 255, 240))

# Separator line
sep_y = tag_y + 44
draw.line([(W//2 - 160, sep_y), (W//2 + 160, sep_y)], fill=(0, 240, 255, 60), width=1)
# Diamond accent in the middle of separator
draw.polygon([(W//2 - 4, sep_y - 4), (W//2, sep_y - 8),
              (W//2 + 4, sep_y - 4), (W//2, sep_y)],
             fill=(0, 240, 255, 150))

# ── 8. Genre pills ────────────────────────────────────────────────────────────
genres_row1 = ["Soul", "Grime", "Afrobeats", "D&B", "Jazz", "Hip-hop", "House"]
genres_row2 = ["Reggae", "R&B", "Blues", "Lo-Fi", "Techno", "K-Pop", "+ 30 more"]

PILL_H      = 26
PILL_PAD_X  = 12
PILL_GAP    = 8

def measure_pill(text):
    bb = draw.textbbox((0, 0), text, font=f_pill)
    return bb[2] - bb[0] + PILL_PAD_X * 2

def draw_pill_row(genres, row_y):
    widths  = [measure_pill(g) for g in genres]
    total_w = sum(widths) + PILL_GAP * (len(genres) - 1)
    px      = (W - total_w) // 2
    for g, pw in zip(genres, widths):
        is_plus = g.startswith("+")
        if is_plus:
            border = (139, 92, 246, 180)
            fill   = (30, 0, 60, 130)
            tcol   = (200, 170, 255, 255)
        else:
            border = (0, 240, 255, 90)
            fill   = (0, 30, 40, 130)
            tcol   = (0, 240, 255, 210)

        draw.rounded_rectangle([px, row_y, px + pw, row_y + PILL_H],
                                radius=PILL_H // 2,
                                fill=fill, outline=border, width=1)
        bb_g = draw.textbbox((0, 0), g, font=f_pill)
        gw   = bb_g[2] - bb_g[0]
        gh   = bb_g[3] - bb_g[1]
        draw.text((px + (pw - gw) // 2, row_y + (PILL_H - gh) // 2),
                  g, font=f_pill, fill=tcol)
        px += pw + PILL_GAP

PILL_Y1 = H - 96
PILL_Y2 = H - 62
draw_pill_row(genres_row1, PILL_Y1)
draw_pill_row(genres_row2, PILL_Y2)

# ── 9. Subtle scanlines ───────────────────────────────────────────────────────
scan = Image.new("RGBA", (W, H), (0, 0, 0, 0))
sd   = ImageDraw.Draw(scan)
for y in range(0, H, 3):
    sd.line([(0, y), (W, y)], fill=(0, 0, 0, 18), width=1)
img = Image.alpha_composite(img, scan)

# ── 10. Save ──────────────────────────────────────────────────────────────────
img.convert("RGB").save(OUT, "PNG")
print(f"Saved -> {OUT}")

# Quick sanity check
check = Image.open(OUT)
print(f"Size: {check.size}  Mode: {check.mode}")
