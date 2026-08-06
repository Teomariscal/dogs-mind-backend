#!/usr/bin/env python3
"""Generate the iOS/PWA/favicon icon set from the approved v2 dog, in the
approved style: white dog line (thickened so it reads small) + tiny cyan glow
on the emerald gradient. Dog only (no text, no grid) per App Store rules.
Outputs to decided/icons_new/ (staging — copied into frontend after backup)."""
import os
import numpy as np
from PIL import Image, ImageFilter

HERE = os.path.dirname(os.path.abspath(__file__))
DL = os.path.expanduser("~/Downloads")
OUT = os.path.join(HERE, "decided", "icons_new")
os.makedirs(OUT, exist_ok=True)
SRC_V2 = os.path.join(DL, "bocalan_online_A_minimalist_logo_of_a_Border_Collie_SITTING_in_a_triangular_A-s_1d690ea5-13d0-4563-a436-338132d96421 (1).png")

CYAN = np.array([94, 200, 230], np.float32)
WHITE = np.array([238, 249, 252], np.float32)
EMERALD = [(0.00, (10, 26, 20)), (0.45, (16, 38, 32)),
           (0.78, (22, 52, 46)), (1.00, (40, 72, 62))]


def extract_dog(path):
    im = Image.open(path).convert("RGB")
    arr = np.asarray(im).astype(np.float32)
    lum = arr.mean(axis=2)
    chroma = arr.max(axis=2) - arr.min(axis=2)
    a = np.clip((165.0 - lum) / 165.0, 0, 1) * (chroma < 48)
    m = Image.fromarray((a * 255).astype(np.uint8))
    return m.crop(m.getbbox())


DOG = extract_dog(SRC_V2)
LINE_FRAC = 7.0 / 1290.0   # approx source line width / dog width


def emerald_bg(S):
    lut = np.zeros((256, 3), np.float32)
    for i in range(256):
        t = i / 255.0
        for j in range(len(EMERALD) - 1):
            t0, c0 = EMERALD[j]; t1, c1 = EMERALD[j + 1]
            if t0 <= t <= t1:
                f = (t - t0) / (t1 - t0)
                lut[i] = [c0[k] + (c1[k] - c0[k]) * f for k in range(3)]
                break
    yy = np.linspace(0, 1, S)[:, None]
    xx = np.linspace(0, 1, S)[None, :]
    tt = np.clip(yy * 0.82 + xx * 0.18, 0, 1)
    bg = lut[(tt * 255).astype(np.int32)]
    cx, cy = 0.5 * S, 0.34 * S
    Y, X = np.mgrid[0:S, 0:S]
    d = np.sqrt((X - cx) ** 2 + (Y - cy) ** 2) / (0.62 * S)
    halo = (np.clip(1 - d, 0, 1) ** 2.4)[..., None]
    bg = bg + halo * CYAN * 0.13
    return np.clip(bg, 0, 255)


def build_icon(S, pad=0.72, ycenter=0.50):
    bg = emerald_bg(S)
    tw = max(8, int(pad * S))
    r = tw / DOG.width
    dog = DOG.resize((tw, max(1, int(DOG.height * r))), Image.LANCZOS)
    m = Image.new("L", (S, S), 0)
    x = (S - dog.width) // 2
    y = int(S * ycenter) - dog.height // 2
    m.paste(dog, (x, y))
    # thicken so the line survives at small sizes
    cur = LINE_FRAC * tw
    target = min(max(S * 0.045, 1.4), 9.0)
    rad = int(round((target - cur) / 2))
    if rad >= 1:
        k = min(2 * rad + 1, 31)
        m = m.filter(ImageFilter.MaxFilter(k))
    glow = m.filter(ImageFilter.GaussianBlur(max(1, S // 130)))
    out = bg.copy()
    ga = (np.asarray(glow).astype(np.float32) / 255.0 * 0.18)[..., None]
    out = out * (1 - ga) + CYAN * ga
    ia = (np.asarray(m).astype(np.float32) / 255.0)[..., None]
    out = out * (1 - ia) + WHITE * ia
    return Image.fromarray(np.clip(out, 0, 255).astype(np.uint8), "RGB")


SIZES = [16, 32, 48, 60, 72, 80, 96, 120, 128, 144, 152, 180, 192, 256, 512, 1024]
icons = {}
for s in SIZES:
    icons[s] = build_icon(s)

# named PWA/iOS files (match existing frontend filenames)
for s in [72, 96, 128, 144, 152, 180, 192, 512]:
    icons[s].save(os.path.join(OUT, f"icon-{s}x{s}.png"))
icons[180].save(os.path.join(OUT, "apple-touch-icon.png"))
icons[1024].save(os.path.join(OUT, "icon-1024x1024.png"))  # App Store (RGB, no alpha)

# favicon.ico (multi-size)
icons[256].save(os.path.join(OUT, "favicon.ico"),
                sizes=[(16, 16), (32, 32), (48, 48), (64, 64)])

# contact strip for review
strip_sizes = [512, 180, 120, 80, 48, 32, 16]
pad = 28
sw = sum(strip_sizes) + pad * (len(strip_sizes) + 1)
strip = Image.new("RGB", (sw, 512 + 90), (245, 244, 240))
xx = pad
for s in strip_sizes:
    strip.paste(icons[s], (xx, 30 + (512 - s) // 2))
    xx += s + pad
strip.save(os.path.join(OUT, "_icon_review_strip.png"))
print("generated", len(SIZES), "sizes ->", OUT)
