#!/usr/bin/env python3
"""Turn the approved v2 line-art dog into the brand 'vibrant emerald + cyan-AI'
treatment: extract the dog line (drop the golden-ratio grid), render it as a
luminous cyan energy-line on the deep emerald gradient with a faint tech dot-grid
and cyan halo. Output App Store icon (no text, square, no alpha), a size-strip
legibility proof, a transparent glowing dog, and the full vibrant lockup."""
import os, math
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter

HERE = os.path.dirname(os.path.abspath(__file__))
DL = os.path.expanduser("~/Downloads")
OUT = os.path.join(HERE, "decided")
os.makedirs(OUT, exist_ok=True)
FONT_SERIF = os.path.join(HERE, "fonts", "CormorantGaramond.ttf")
FONT_SANS = os.path.join(HERE, "fonts", "Jost.ttf")
SRC_V2 = os.path.join(DL, "bocalan_online_A_minimalist_logo_of_a_Border_Collie_SITTING_in_a_triangular_A-s_1d690ea5-13d0-4563-a436-338132d96421 (1).png")

# Brand palette
EMERALD_STOPS = [(0.00, (10, 26, 20)), (0.42, (18, 42, 35)),
                 (0.74, (26, 59, 52)), (1.00, (74, 103, 65))]
CYAN = (94, 200, 230)        # #5ec8e6
CYAN_LIGHT = (128, 214, 238) # #80d6ee
LINE_CORE = (224, 248, 255)  # luminous near-white cyan
INK = (245, 250, 248)

WORD = "The Dogs’ Mind"      # U+2019
TAG = "AI FOR CANINE BEHAVIOR"


# ---------- dog line extraction (drop the gold grid) ----------
def extract_dog(path):
    im = Image.open(path).convert("RGB")
    arr = np.asarray(im).astype(np.float32)
    lum = arr.mean(axis=2)
    chroma = arr.max(axis=2) - arr.min(axis=2)
    # dark + neutral => the black dog line; warm tan grid has high chroma -> excluded
    alpha = np.clip((165.0 - lum) / 165.0, 0, 1)
    alpha = alpha * (chroma < 48)
    a8 = (alpha * 255).astype(np.uint8)
    mask = Image.fromarray(a8, "L")
    bbox = mask.getbbox()
    return mask.crop(bbox)


DOG = extract_dog(SRC_V2)
print("dog mask", DOG.size)


def lerp(a, b, t):
    return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))


def grad_color(t):
    for i in range(len(EMERALD_STOPS) - 1):
        t0, c0 = EMERALD_STOPS[i]
        t1, c1 = EMERALD_STOPS[i + 1]
        if t0 <= t <= t1:
            return lerp(c0, c1, (t - t0) / (t1 - t0))
    return EMERALD_STOPS[-1][1]


def background(W, H, halo_xy=(0.5, 0.32), dotgrid=True):
    # diagonal-ish vertical emerald gradient
    ramp = np.zeros((H, W, 3), np.float32)
    yy = np.linspace(0, 1, H)[:, None]
    xx = np.linspace(0, 1, W)[None, :]
    t = np.clip(yy * 0.82 + xx * 0.18, 0, 1)
    lut = np.array([grad_color(v / 255.0) for v in range(256)], np.float32)
    idx = (t * 255).astype(np.int32)
    for c in range(3):
        ramp[:, :, c] = lut[idx, c]
    # cyan halo (radial, additive)
    hx, hy = halo_xy
    cx, cy = hx * W, hy * H
    Y, X = np.mgrid[0:H, 0:W]
    d = np.sqrt((X - cx) ** 2 + (Y - cy) ** 2) / (0.62 * max(W, H))
    halo = np.clip(1 - d, 0, 1) ** 2.2
    for c in range(3):
        ramp[:, :, c] += halo * CYAN[c] * 0.22
    img = Image.fromarray(np.clip(ramp, 0, 255).astype(np.uint8), "RGB")
    # faint tech dot-grid
    if dotgrid:
        layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        d2 = ImageDraw.Draw(layer)
        step = max(34, W // 36)
        r = max(1, W // 1100)
        for gy in range(step, H, step):
            for gx in range(step, W, step):
                d2.ellipse([gx - r, gy - r, gx + r, gy + r],
                           fill=(CYAN_LIGHT[0], CYAN_LIGHT[1], CYAN_LIGHT[2], 16))
        img = Image.alpha_composite(img.convert("RGBA"), layer).convert("RGB")
    return img


def glowing_dog(target_w):
    """Return RGBA of the dog as a luminous cyan energy-line, sized to width."""
    r = target_w / DOG.width
    m = DOG.resize((target_w, int(DOG.height * r)), Image.LANCZOS)
    W, H = m.size
    pad = int(0.16 * W)
    canvas = Image.new("RGBA", (W + 2 * pad, H + 2 * pad), (0, 0, 0, 0))
    mfull = Image.new("L", canvas.size, 0)
    mfull.paste(m, (pad, pad))
    # glow layers (cyan), increasing blur
    for blur, op, col in [(int(W*0.05), 130, CYAN), (int(W*0.022), 150, CYAN),
                          (int(W*0.009), 170, CYAN_LIGHT)]:
        g = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
        solid = Image.new("RGBA", canvas.size, col + (0,))
        a = mfull.filter(ImageFilter.GaussianBlur(max(1, blur)))
        a = a.point(lambda v: int(v * op / 255))
        solid.putalpha(a)
        canvas = Image.alpha_composite(canvas, solid)
    # crisp core
    core = Image.new("RGBA", canvas.size, LINE_CORE + (0,))
    core.putalpha(mfull)
    canvas = Image.alpha_composite(canvas, core)
    return canvas.crop(canvas.getbbox())


def font_serif(size, w="SemiBold"):
    f = ImageFont.truetype(FONT_SERIF, size)
    try: f.set_variation_by_name(w)
    except Exception: pass
    return f


def font_sans(size, w="Medium"):
    f = ImageFont.truetype(FONT_SANS, size)
    try: f.set_variation_by_name(w)
    except Exception: pass
    return f


def tracked(draw, text, font, x, y, color, tracking):
    for ch in text:
        draw.text((x, y), ch, font=font, fill=color)
        x += font.getlength(ch) + tracking


def tracked_w(text, font, tracking):
    return sum(font.getlength(c) + tracking for c in text) - tracking


# ---------- ICON 1024 (no text, square, NO alpha) ----------
def build_icon(size=1024):
    bg = background(size, size, halo_xy=(0.5, 0.30))
    dog = glowing_dog(int(size * 0.74))
    x = (size - dog.width) // 2
    y = int(size * 0.50) - dog.height // 2
    bg = bg.convert("RGBA")
    bg.alpha_composite(dog, (x, y))
    return bg.convert("RGB")  # no alpha


icon = build_icon(1024)
icon.save(os.path.join(OUT, "icon_1024_vibrant.png"))
print("icon", icon.size)

# ---------- size-strip legibility proof ----------
sizes = [1024, 180, 120, 80, 60, 40]
pad = 40
strip_h = 1024 + 130
strip_w = sum(sizes) + pad * (len(sizes) + 1)
strip = Image.new("RGB", (strip_w, strip_h), (245, 244, 240))
ds = ImageDraw.Draw(strip)
lab = font_sans(30, "Medium")
x = pad
for s in sizes:
    ic = icon.resize((s, s), Image.LANCZOS)
    y = 40 + (1024 - s) // 2
    strip.paste(ic, (x, y))
    t = f"{s}px"
    tw = lab.getlength(t)
    ds.text((x + s/2 - tw/2, 40 + 1024 + 24), t, font=lab, fill=(40, 40, 40))
    x += s + pad
strip.save(os.path.join(OUT, "icon_sizes_strip.png"))
print("size strip", strip.size)

# ---------- transparent glowing dog (reusable) ----------
glowing_dog(1100).save(os.path.join(OUT, "dog_glow_transparent.png"))

# ---------- vibrant lockup (dog + wordmark + tagline) ----------
def render_word_layer(text, font, tracking, core_rgb,
                      glow_rgb=None, glow_blur=0, glow_alpha=90):
    asc, desc = font.getmetrics()
    pad = glow_blur * 2 + 20
    w = int(tracked_w(text, font, tracking)) + pad * 2
    h = asc + desc + pad * 2
    layer = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    if glow_rgb and glow_blur > 0:
        g = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        dg = ImageDraw.Draw(g)
        x = pad
        for ch in text:
            dg.text((x, pad), ch, font=font, fill=glow_rgb + (glow_alpha,))
            x += font.getlength(ch) + tracking
        g = g.filter(ImageFilter.GaussianBlur(glow_blur))
        layer = Image.alpha_composite(layer, g)
    d = ImageDraw.Draw(layer)
    x = pad
    for ch in text:
        d.text((x, pad), ch, font=font, fill=core_rgb + (255,))
        x += font.getlength(ch) + tracking
    return layer.crop(layer.getbbox())


def build_lockup(W=1400):
    topM = int(W * 0.12)
    dog = glowing_dog(int(W * 0.60))
    fw = font_serif(int(W * 0.105), "SemiBold")
    word = render_word_layer(WORD, fw, W * 0.006, INK, CYAN, int(W * 0.012), 90)
    ft = font_sans(int(W * 0.030), "Medium")
    tag = render_word_layer(TAG, ft, W * 0.018, CYAN_LIGHT)
    gap1 = int(W * 0.075)     # dog -> wordmark (tightened: text sits higher)
    gap_div = int(W * 0.050)  # wordmark -> divider dot
    gap_tag = int(W * 0.042)  # divider -> tagline
    div_r = 5
    H = (topM + dog.height + gap1 + word.height + gap_div
         + div_r * 2 + gap_tag + tag.height + topM)
    bg = background(W, H, halo_xy=(0.5, 0.26)).convert("RGBA")
    y = topM
    bg.alpha_composite(dog, ((W - dog.width) // 2, y)); y += dog.height + gap1
    bg.alpha_composite(word, ((W - word.width) // 2, y)); y += word.height + gap_div
    d = ImageDraw.Draw(bg)
    d.ellipse([W/2 - div_r, y - div_r, W/2 + div_r, y + div_r],
              fill=CYAN_LIGHT + (220,)); y += div_r * 2 + gap_tag
    bg.alpha_composite(tag, ((W - tag.width) // 2, y))
    return bg.convert("RGB")


lock = build_lockup()
lock.save(os.path.join(OUT, "lockup_vibrant.png"))
print("lockup", lock.size)
print("DONE ->", OUT)
