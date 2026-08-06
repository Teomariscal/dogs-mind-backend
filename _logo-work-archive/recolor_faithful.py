#!/usr/bin/env python3
"""100% faithful recolor of v1_A_footer.png (dog + golden-ratio grid + wordmark).
No redrawing: every stroke is preserved exactly. Black ink (dog + 'The Dogs' Mind')
-> WHITE; gold golden-ratio grid -> CYAN; cream background -> dark emerald. Crisp,
minimal glow (no neon). No tagline."""
import os
import numpy as np
from PIL import Image, ImageFilter

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "decided")
SRC = os.path.join(HERE, "wordmark-out", "v2_A_footer.png")

CYAN = np.array([94, 200, 230], np.float32)    # #5ec8e6
CYAN_LIGHT = np.array([128, 214, 238], np.float32)  # #80d6ee (grid, more visible)
WHITE = np.array([238, 249, 252], np.float32)   # cool white
EMERALD = [(0.00, (10, 26, 20)), (0.45, (16, 38, 32)),
           (0.78, (22, 52, 46)), (1.00, (38, 70, 60))]

src = Image.open(SRC).convert("RGB")
W, H = src.size
arr = np.asarray(src).astype(np.float32)
R, G, B = arr[..., 0], arr[..., 1], arr[..., 2]
lum = 0.299 * R + 0.587 * G + 0.114 * B
chroma = arr.max(2) - arr.min(2)
warmth = R - B

# masks (soft, anti-aliased)
ink = np.clip((140.0 - lum) / 140.0, 0, 1) * (chroma < 55)
# capture the gold grid more fully (incl. fainter lines) and make it clearly visible
gold = np.clip((warmth - 9.0) / 42.0, 0, 1) * np.clip((232.0 - lum) / 135.0, 0, 1)
gold = np.clip(gold * (1.0 - ink * 0.7) * 2.4, 0, 0.85)
ink = np.clip(ink, 0, 1)

# dark emerald background
def grad():
    lut = np.zeros((256, 3), np.float32)
    for i in range(256):
        t = i / 255.0
        for j in range(len(EMERALD) - 1):
            t0, c0 = EMERALD[j]; t1, c1 = EMERALD[j + 1]
            if t0 <= t <= t1:
                f = (t - t0) / (t1 - t0)
                lut[i] = [c0[k] + (c1[k] - c0[k]) * f for k in range(3)]
                break
    yy = np.linspace(0, 1, H)[:, None]
    xx = np.linspace(0, 1, W)[None, :]
    tt = np.clip(yy * 0.85 + xx * 0.15, 0, 1)
    idx = (tt * 255).astype(np.int32)
    bg = lut[idx]
    # gentle cyan halo, low intensity (no neon)
    cx, cy = 0.5 * W, 0.34 * H
    Y, X = np.mgrid[0:H, 0:W]
    d = np.sqrt((X - cx) ** 2 + (Y - cy) ** 2) / (0.62 * max(W, H))
    halo = (np.clip(1 - d, 0, 1) ** 2.4)[..., None]
    bg = bg + halo * CYAN * 0.14
    return np.clip(bg, 0, 255)

out = grad()
# paint cyan grid (brighter cyan so the background construction strokes read)
ga = gold[..., None]
out = out * (1 - ga) + CYAN_LIGHT * ga
# subtle crisp glow behind ink (very low — not neon)
glow = Image.fromarray((ink * 255).astype(np.uint8)).filter(
    ImageFilter.GaussianBlur(max(1, W // 600)))
gl = (np.asarray(glow).astype(np.float32) / 255.0 * 0.22)[..., None]
out = out * (1 - gl) + CYAN * gl
# paint white ink (crisp)
ia = ink[..., None]
out = out * (1 - ia) + WHITE * ia

res = Image.fromarray(np.clip(out, 0, 255).astype(np.uint8))
path = os.path.join(OUT, "faithful_cyanwhite.png")
res.save(path)
print("saved", path, res.size)

# also: master copy + transparent-background version (for app integration)
res.save(os.path.join(OUT, "MASTER_logo_vibrant_v2A_cyanwhite.png"))

# transparent: composite grid (cyan) -> glow -> ink (white) over alpha=0
trans = np.zeros((H, W, 4), np.float32)
def over(dst, color, a):
    a = np.clip(a, 0, 1)[..., None]
    drgb, da = dst[..., :3], dst[..., 3:4]
    out_a = a + da * (1 - a)
    safe = np.where(out_a > 1e-6, out_a, 1.0)
    out_rgb = (color * a + drgb * da * (1 - a)) / safe
    dst[..., :3] = out_rgb
    dst[..., 3:4] = out_a
    return dst
trans = over(trans, CYAN_LIGHT, gold)
glow_a = np.asarray(glow).astype(np.float32) / 255.0 * 0.22
trans = over(trans, CYAN, glow_a)
trans = over(trans, WHITE, ink)
trans8 = np.zeros((H, W, 4), np.uint8)
trans8[..., :3] = np.clip(trans[..., :3], 0, 255).astype(np.uint8)
trans8[..., 3] = np.clip(trans[..., 3] * 255, 0, 255).astype(np.uint8)
Image.fromarray(trans8, "RGBA").save(os.path.join(OUT, "logo_transparent_cyanwhite.png"))
print("saved transparent + master")
