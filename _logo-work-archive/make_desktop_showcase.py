#!/usr/bin/env python3
"""Show the NEW icon as it actually renders on a desktop: a browser tab favicon,
a macOS-style dock (with the system squircle mask), and the large icon (raw +
masked). Uses the real generated PNGs so the founder judges the true result."""
import os
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter

HERE = os.path.dirname(os.path.abspath(__file__))
ICN = os.path.join(HERE, "decided", "icons_new")
FONT_SANS = os.path.join(HERE, "fonts", "Jost.ttf")
OUT = os.path.join(ICN, "_desktop_showcase.png")

SC = 2  # supersample for crisp text
W, H = 1300 * SC, 880 * SC


def sans(size, w="Medium"):
    f = ImageFont.truetype(FONT_SANS, size * SC)
    try:
        f.set_variation_by_name(w)
    except Exception:
        pass
    return f


def squircle_mask(size, radius_frac=0.225):
    """Apple-style rounded-rect (close enough) mask at the given pixel size."""
    s = size
    m = Image.new("L", (s, s), 0)
    d = ImageDraw.Draw(m)
    r = int(s * radius_frac)
    d.rounded_rectangle([0, 0, s - 1, s - 1], radius=r, fill=255)
    return m


def masked(icon_path, size, radius_frac=0.225):
    ic = Image.open(icon_path).convert("RGB").resize((size, size), Image.LANCZOS)
    out = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    out.paste(ic, (0, 0), squircle_mask(size, radius_frac))
    return out


def drop_shadow(rgba, blur, alpha=150, dy=6 * SC):
    """Soft shadow behind an RGBA icon. Returns a larger RGBA with icon centered."""
    pad = blur * 3
    big = Image.new("RGBA", (rgba.width + 2 * pad, rgba.height + 2 * pad), (0, 0, 0, 0))
    sh = Image.new("RGBA", big.size, (0, 0, 0, 0))
    a = rgba.split()[3].point(lambda v: int(v * alpha / 255))
    blk = Image.new("RGBA", rgba.size, (0, 0, 0, 0))
    blk.putalpha(a)
    sh.paste(blk, (pad, pad + dy), blk)
    sh = sh.filter(ImageFilter.GaussianBlur(blur))
    sh.alpha_composite(rgba, (pad, pad))
    return sh


# ---- neutral dark desktop background (judge the icon honestly) ----
bg = Image.new("RGB", (W, H), (16, 16, 20))
ramp = np.zeros((H, W, 3), np.float32)
yy = np.linspace(0, 1, H)[:, None]
for c, (a, b) in enumerate([(14, 28), (14, 28), (18, 34)]):
    ramp[:, :, c] = a + (b - a) * yy
bg = Image.fromarray(np.clip(ramp, 0, 255).astype(np.uint8), "RGB").convert("RGBA")
d = ImageDraw.Draw(bg)

cyanL = (128, 214, 238)
white = (236, 244, 246)
grey = (150, 160, 168)

# ===================== 1) BROWSER TAB =====================
d.text((70 * SC, 40 * SC), "EN LA PESTAÑA DEL NAVEGADOR (favicon)",
       font=sans(15, "SemiBold"), fill=cyanL)
# chrome tab strip
strip_y = 78 * SC
d.rounded_rectangle([60 * SC, strip_y, 1240 * SC, strip_y + 96 * SC],
                    radius=10 * SC, fill=(38, 40, 46))
# active tab
tabw = 360 * SC
d.rounded_rectangle([76 * SC, strip_y + 14 * SC, 76 * SC + tabw, strip_y + 96 * SC],
                    radius=12 * SC, fill=(58, 62, 70))
fav = Image.open(os.path.join(ICN, "favicon.ico")).convert("RGBA").resize(
    (20 * SC, 20 * SC), Image.LANCZOS)
bg.alpha_composite(fav, (96 * SC, strip_y + 42 * SC))
d.text((128 * SC, strip_y + 44 * SC), "The Dogs’ Mind", font=sans(16, "Medium"),
       fill=(225, 230, 233))
d.text((tabw + 50 * SC, strip_y + 44 * SC), "+ New tab", font=sans(15, "Regular"),
       fill=(120, 126, 134))
# zoomed favicon (so he can judge the tiny size)
zx = 880 * SC
for px, lab in [(16, "16px real"), (32, "32px real")]:
    ic = Image.open(os.path.join(ICN, "favicon.ico")).convert("RGB").resize(
        (px, px), Image.LANCZOS)
    big = ic.resize((px * 4, px * 4), Image.NEAREST)  # pixel-true zoom
    d.rounded_rectangle([zx - 6 * SC, strip_y + 8 * SC,
                         zx + px * 4 + 6 * SC, strip_y + 8 * SC + px * 4 + 6 * SC],
                        radius=8 * SC, outline=(70, 74, 82), width=SC)
    bg.paste(big, (zx, strip_y + 14 * SC))
    d.text((zx, strip_y + 14 * SC + px * 4 + 10 * SC), lab, font=sans(12), fill=grey)
    zx += px * 4 + 70 * SC

# ===================== 2) macOS DOCK =====================
dock_label_y = 250 * SC
d.text((70 * SC, dock_label_y), "EN EL DOCK / ESCRITORIO (app instalada)",
       font=sans(15, "SemiBold"), fill=cyanL)
dock_y = 300 * SC
dock_h = 150 * SC
dock_x0, dock_x1 = 230 * SC, 1070 * SC
# frosted dock bar
dock = Image.new("RGBA", (dock_x1 - dock_x0, dock_h), (255, 255, 255, 26))
dm = Image.new("L", dock.size, 0)
ImageDraw.Draw(dm).rounded_rectangle([0, 0, dock.width - 1, dock.height - 1],
                                     radius=34 * SC, fill=255)
dock.putalpha(dm)
bg.alpha_composite(dock, (dock_x0, dock_y))
# neighbor app icons (neutral) + OURS in the middle
neighbors = [(58, 109, 240), (52, 199, 89), (255, 159, 10), (255, 55, 95)]
isz = 104 * SC
gap = 30 * SC
n_total = len(neighbors) + 1
total_w = n_total * isz + (n_total - 1) * gap
sx = dock_x0 + ((dock_x1 - dock_x0) - total_w) // 2
cy = dock_y + (dock_h - isz) // 2
order = [0, 1, "OURS", 2, 3]
x = sx
for item in order:
    if item == "OURS":
        ic = masked(os.path.join(ICN, "icon-512x512.png"), isz)
        ic = drop_shadow(ic, 10 * SC, alpha=170)
        bg.alpha_composite(ic, (x - 30 * SC, cy - 30 * SC))
    else:
        col = neighbors[item]
        sq = Image.new("RGBA", (isz, isz), col + (255,))
        sq.putalpha(squircle_mask(isz))
        sq = drop_shadow(sq, 8 * SC, alpha=120)
        bg.alpha_composite(sq, (x - 24 * SC, cy - 24 * SC))
    x += isz + gap

# ===================== 3) LARGE ICON (raw + masked) =====================
big_label_y = 500 * SC
d.text((70 * SC, big_label_y), "ICONO GRANDE  ·  1024 App Store (sin máscara) vs. instalado (squircle)",
       font=sans(15, "SemiBold"), fill=cyanL)
gy = 540 * SC
# raw square (App Store representation, no rounded corners)
raw = Image.open(os.path.join(ICN, "icon-1024x1024.png")).convert("RGB").resize(
    (260 * SC, 260 * SC), Image.LANCZOS)
rawc = Image.new("RGBA", raw.size, (0, 0, 0, 0))
rawc.paste(raw, (0, 0))
rawc = drop_shadow(rawc, 12 * SC, alpha=150)
bg.alpha_composite(rawc, (90 * SC, gy))
d.text((150 * SC, gy + 300 * SC), "App Store 1024² (RGB, sin alfa)", font=sans(13),
       fill=grey)
# masked (how iOS/macOS shows it)
mk = masked(os.path.join(ICN, "icon-512x512.png"), 260 * SC)
mk = drop_shadow(mk, 12 * SC, alpha=150)
bg.alpha_composite(mk, (470 * SC, gy))
d.text((545 * SC, gy + 300 * SC), "Instalado (máscara iOS/macOS)", font=sans(13),
       fill=grey)
# size ladder
ladder = [180, 120, 80, 48, 32]
lx = 860 * SC
ly = gy + 20 * SC
d.text((lx, gy - 4 * SC), "ESCALA REAL", font=sans(13, "SemiBold"), fill=grey)
for s in ladder:
    px = s * SC
    ic = masked(os.path.join(ICN, "icon-512x512.png"), px, radius_frac=0.225)
    bg.alpha_composite(ic, (lx, ly))
    d.text((lx + px + 16 * SC, ly + px // 2 - 8 * SC), f"{s}px", font=sans(12),
           fill=grey)
    ly += px + 18 * SC

out = bg.convert("RGB").resize((W // SC, H // SC), Image.LANCZOS)
out.save(OUT)
print("saved", OUT, out.size)
