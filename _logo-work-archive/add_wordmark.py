#!/usr/bin/env python3
"""Compose the 'The Dogs' Mind' wordmark (Cormorant Garamond) onto the two
Recraft line-art logos, in two placements each: (A) footer/baseline, (B)
crossing the dog's body. Output full-res PNGs + a contact sheet."""
import os
from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
DL = os.path.expanduser("~/Downloads")
OUT = os.path.join(HERE, "wordmark-out")
os.makedirs(OUT, exist_ok=True)
FONT = os.path.join(HERE, "fonts", "CormorantGaramond.ttf")

WORD = "The Dogs’ Mind"   # U+2019 apostrophe
INK = (26, 26, 26)             # near-black to match the line

SRC = {
    "v1": "bocalan_online_A_minimalist_logo_of_a_Border_Collie_SITTING_in_a_triangular_A-s_edd4d89b-0826-42be-9b21-690d7ef39b2a (1).png",
    "v2": "bocalan_online_A_minimalist_logo_of_a_Border_Collie_SITTING_in_a_triangular_A-s_1d690ea5-13d0-4563-a436-338132d96421 (1).png",
}


def line_bbox(im, thr=90):
    """Bounding box of the dark (black) line art, ignoring the faint gold grid."""
    g = im.convert("RGB")
    px = g.load()
    W, H = g.size
    step = 2
    x0, y0, x1, y1 = W, H, 0, 0
    for y in range(0, H, step):
        for x in range(0, W, step):
            r, gr, b = px[x, y]
            if r < thr and gr < thr and b < thr:
                if x < x0: x0 = x
                if x > x1: x1 = x
                if y < y0: y0 = y
                if y > y1: y1 = y
    return x0, y0, x1, y1


def make_font(size, weight="SemiBold"):
    f = ImageFont.truetype(FONT, size)
    try:
        f.set_variation_by_name(weight)
    except Exception:
        pass
    return f


def measure(text, font, tracking):
    w = 0.0
    for i, ch in enumerate(text):
        w += font.getlength(ch)
        if i < len(text) - 1:
            w += tracking
    return w


def fit_font(text, target_w, weight, track_ratio):
    """Pick font size so the tracked wordmark spans ~target_w px."""
    base = 200
    f = make_font(base, weight)
    w0 = measure(text, f, track_ratio * base)
    size = max(20, int(base * target_w / w0))
    f = make_font(size, weight)
    tracking = track_ratio * size
    return f, tracking, size


def render_wordmark(text, font, tracking, color, halo=None, halo_w=0):
    asc, desc = font.getmetrics()
    pad = halo_w + 12
    width = int(measure(text, font, tracking)) + pad * 2
    height = asc + desc + pad * 2
    layer = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    # pass 1: halo
    if halo and halo_w > 0:
        x = pad
        for ch in text:
            d.text((x, pad), ch, font=font, fill=halo,
                    stroke_width=halo_w, stroke_fill=halo)
            x += font.getlength(ch) + tracking
    # pass 2: ink
    x = pad
    for ch in text:
        d.text((x, pad), ch, font=font, fill=color)
        x += font.getlength(ch) + tracking
    return layer.crop(layer.getbbox())


def bg_color(im):
    return im.convert("RGB").getpixel((8, 8))


def footer_version(im, bbox):
    W, H = im.size
    x0, y0, x1, y1 = bbox
    cx = (x0 + x1) // 2
    target = int(0.50 * W)
    f, tr, size = fit_font(WORD, target, "SemiBold", 0.10)
    wm = render_wordmark(WORD, f, tr, INK)
    gap = int(0.42 * size)
    top = y1 + gap
    needed = top + wm.height + int(0.9 * size)
    canvas = im.convert("RGB")
    if needed > H:
        new = Image.new("RGB", (W, needed), bg_color(im))
        new.paste(canvas, (0, 0))
        canvas = new
    px = cx - wm.width // 2
    canvas.paste(wm, (px, top), wm)
    return canvas


def cross_version(im, bbox):
    W, H = im.size
    x0, y0, x1, y1 = bbox
    cx = (x0 + x1) // 2
    target = int(0.60 * W)
    f, tr, size = fit_font(WORD, target, "Medium", 0.12)
    halo_w = max(6, int(0.05 * size))
    wm = render_wordmark(WORD, f, tr, INK, halo=bg_color(im), halo_w=halo_w)
    cy = y0 + int(0.60 * (y1 - y0))
    px = cx - wm.width // 2
    py = cy - wm.height // 2
    canvas = im.convert("RGB").copy()
    canvas.paste(wm, (px, py), wm)
    return canvas


results = {}
for key, fn in SRC.items():
    im = Image.open(os.path.join(DL, fn)).convert("RGB")
    bbox = line_bbox(im)
    print(key, "bbox", bbox, "of", im.size)
    a = footer_version(im, bbox)
    b = cross_version(im, bbox)
    pa = os.path.join(OUT, f"{key}_A_footer.png")
    pb = os.path.join(OUT, f"{key}_B_cross.png")
    a.save(pa); b.save(pb)
    results[f"{key}_A"] = a
    results[f"{key}_B"] = b
    print("  saved", pa, a.size)
    print("  saved", pb, b.size)

# contact sheet: 2 cols (A,B) x 2 rows (v1,v2)
thumb_w = 900
cells = [("v1_A", "v1 — A pie"), ("v1_B", "v1 — B cruzando"),
         ("v2_A", "v2 — A pie"), ("v2_B", "v2 — B cruzando")]
thumbs = []
for k, _ in cells:
    im = results[k]
    r = thumb_w / im.width
    thumbs.append(im.resize((thumb_w, int(im.height * r))))
ch_h = max(t.height for t in thumbs)
pad = 30
sheet = Image.new("RGB", (thumb_w * 2 + pad * 3, (ch_h + 70) * 2 + pad),
                  (245, 244, 240))
d = ImageDraw.Draw(sheet)
lab = make_font(34, "Medium")
for i, (k, label) in enumerate(cells):
    col = i % 2
    row = i // 2
    x = pad + col * (thumb_w + pad)
    y = pad + row * (ch_h + 70)
    sheet.paste(thumbs[i], (x, y))
    d.text((x + 6, y + thumbs[i].height + 12), label, font=lab, fill=(30, 30, 30))
sheet_path = os.path.join(OUT, "_contact_sheet.png")
sheet.save(sheet_path)
print("contact sheet", sheet_path, sheet.size)
