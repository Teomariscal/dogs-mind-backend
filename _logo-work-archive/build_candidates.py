#!/usr/bin/env python3
"""Build App Store icon candidates: professional open-source marks composited
onto The Dogs' Mind emerald brand field. No freehand drawing — marks are
MIT/ISC-licensed icons (Phosphor, Lucide, Tabler), recolored via alpha mask."""
import os, subprocess, math
from PIL import Image, ImageDraw, ImageFilter
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
MARKS = os.path.join(HERE, "marks")
OUT = os.path.join(HERE, "candidates")
os.makedirs(OUT, exist_ok=True)

SIZE = 1024
# Brand emerald palette
DARK   = (10, 26, 20)    # #0a1a14 top-left
MID1   = (18, 42, 35)    # #122a23
MID2   = (26, 59, 52)    # #1a3b34
OLIVE  = (74, 103, 65)   # #4a6741 bottom-right
CYAN   = (94, 200, 230)  # #5ec8e6
CYAN_L = (128, 214, 238) # #80d6ee
WHITE  = (255, 255, 255)

def lerp(a, b, t):
    return tuple(int(a[i] + (b[i]-a[i])*t) for i in range(3))

def emerald_field(size=SIZE):
    """Diagonal emerald gradient (dark TL -> olive BR) + soft cyan halo."""
    ys, xs = np.mgrid[0:size, 0:size].astype(np.float32)
    # diagonal param 0..1
    d = (xs + ys) / (2*(size-1))
    # piecewise gradient dark->mid1->mid2->olive
    stops = [(0.0, DARK), (0.40, MID1), (0.72, MID2), (1.0, OLIVE)]
    img = np.zeros((size, size, 3), np.float32)
    for i in range(len(stops)-1):
        t0, c0 = stops[i]; t1, c1 = stops[i+1]
        m = (d >= t0) & (d <= t1)
        local = (d - t0) / (t1 - t0 + 1e-6)
        for ch in range(3):
            img[..., ch] = np.where(m, c0[ch] + (c1[ch]-c0[ch])*local, img[..., ch])
    # cyan halo: soft radial centred slightly upper-right, low intensity
    cx, cy = size*0.62, size*0.40
    r = np.sqrt((xs-cx)**2 + (ys-cy)**2)
    halo = np.clip(1 - r/(size*0.62), 0, 1) ** 2
    halo *= 0.16  # max opacity
    for ch in range(3):
        img[..., ch] = img[..., ch]*(1-halo) + CYAN[ch]*halo
    # subtle vignette darkening at corners for depth
    rr = np.sqrt((xs-size/2)**2 + (ys-size/2)**2) / (size*0.72)
    vig = np.clip(rr-0.55, 0, 1) * 0.22
    for ch in range(3):
        img[..., ch] *= (1 - vig)
    return Image.fromarray(np.clip(img, 0, 255).astype(np.uint8), "RGB")

def raster_mark(svg_path, px=2048):
    """rsvg-convert -> RGBA, trim transparent bbox, return mask alpha image."""
    tmp = svg_path + ".raster.png"
    subprocess.run(["rsvg-convert", "-w", str(px), "-h", str(px),
                    svg_path, "-o", tmp], check=True)
    im = Image.open(tmp).convert("RGBA")
    bbox = im.getbbox()
    if bbox:
        im = im.crop(bbox)
    return im  # RGBA, black/colored shape on transparent; alpha is the mask

def colorize(mark_rgba, color):
    """Replace RGB with `color`, keep alpha (anti-aliased mask)."""
    a = mark_rgba.split()[3]
    solid = Image.new("RGBA", mark_rgba.size, color + (0,))
    solid.putalpha(a)
    return solid

def place(field, mark_rgba, color, frac=0.58, dy=0.0, glow=True):
    """Composite recolored mark centered, scaled so its longest side = frac*SIZE."""
    base = field.copy().convert("RGBA")
    col = colorize(mark_rgba, color)
    w, h = col.size
    target = int(SIZE * frac)
    scale = target / max(w, h)
    nw, nh = max(1, int(w*scale)), max(1, int(h*scale))
    col = col.resize((nw, nh), Image.LANCZOS)
    x = (SIZE - nw)//2
    y = (SIZE - nh)//2 + int(dy*SIZE)
    if glow:
        # soft drop/contact glow for premium depth
        glow_layer = Image.new("RGBA", (SIZE, SIZE), (0,0,0,0))
        gcol = colorize(mark_rgba.resize((nw, nh), Image.LANCZOS),
                        (0,0,0)) if False else None
        shadow = Image.new("RGBA", (SIZE, SIZE), (0,0,0,0))
        sh = col.split()[3].point(lambda p: int(p*0.40))
        blk = Image.new("RGBA", (nw, nh), (0,0,0,0)); blk.putalpha(sh)
        shadow.paste(blk, (x, y+int(SIZE*0.012)), blk)
        shadow = shadow.filter(ImageFilter.GaussianBlur(SIZE*0.012))
        base = Image.alpha_composite(base, shadow)
    base.paste(col, (x, y), col)
    return base.convert("RGB")

def rounded(img, radius_frac=0.2237):
    """Apply iOS-style rounded-rect mask for PREVIEW display only."""
    r = int(SIZE*radius_frac)
    mask = Image.new("L", (SIZE, SIZE), 0)
    d = ImageDraw.Draw(mask)
    d.rounded_rectangle([0,0,SIZE-1,SIZE-1], radius=r, fill=255)
    out = img.convert("RGBA"); out.putalpha(mask)
    return out

# ---- load marks ----
dog_fill = raster_mark(os.path.join(MARKS, "phosphor-dog-fill.svg"))
dog_line = raster_mark(os.path.join(MARKS, "phosphor-dog.svg"))
paw_fill = raster_mark(os.path.join(MARKS, "phosphor-paw-fill.svg"))
lucide_dog = raster_mark(os.path.join(MARKS, "lucide-dog.svg"))

field = emerald_field()

candidates = [
    ("c1_dogfill_white", dog_fill, WHITE, 0.56),
    ("c2_dogfill_cyan",  dog_fill, CYAN_L, 0.56),
    ("c3_dogline_white", dog_line, WHITE, 0.60),
    ("c4_pawfill_white", paw_fill, WHITE, 0.52),
    ("c5_pawfill_cyan",  paw_fill, CYAN_L, 0.52),
    ("c6_lucidedog_white", lucide_dog, WHITE, 0.62),
]

made = []
for name, mark, color, frac in candidates:
    icon = place(field, mark, color, frac=frac)
    p = os.path.join(OUT, name + ".png")
    icon.save(p)
    made.append((name, p, icon))
    print("saved", name)

# ---- contact sheet ----
cols = 3
tile = 300
pad = 40
label_h = 46
rows = (len(made)+cols-1)//cols
sheet_w = cols*tile + (cols+1)*pad
sheet_h = rows*(tile+label_h) + (rows+1)*pad + 120
sheet = Image.new("RGB", (sheet_w, sheet_h), (8, 12, 14))
draw = ImageDraw.Draw(sheet)
try:
    from PIL import ImageFont
    f = ImageFont.truetype("/System/Library/Fonts/Supplemental/Arial.ttf", 22)
    fb = ImageFont.truetype("/System/Library/Fonts/Supplemental/Arial Bold.ttf", 30)
except Exception:
    f = fb = None
draw.text((pad, 34), "The Dogs' Mind · App Store icon candidates (marcas pro, sin mano alzada)",
          fill=(180,225,240), font=fb)
labels = {
 "c1_dogfill_white":"A · Dog sólido blanco",
 "c2_dogfill_cyan":"B · Dog sólido cyan",
 "c3_dogline_white":"C · Dog línea blanco",
 "c4_pawfill_white":"D · Huella sólida blanco",
 "c5_pawfill_cyan":"E · Huella sólida cyan",
 "c6_lucidedog_white":"F · Dog alt (Lucide) blanco",
}
for i,(name,p,icon) in enumerate(made):
    r = i//cols; c = i%cols
    x = pad + c*(tile+pad)
    y = 120 + pad + r*(tile+label_h+pad)
    disp = rounded(icon).resize((tile,tile), Image.LANCZOS)
    sheet.paste(disp, (x,y), disp)
    draw.text((x, y+tile+10), labels.get(name,name), fill=(210,230,240), font=f)
sheet.save(os.path.join(OUT, "_contact_sheet.png"))
print("saved contact sheet")

# ---- small-size legibility strip (top 2 picks) ----
strip = Image.new("RGB", (1000, 360), (8,12,14))
sd = ImageDraw.Draw(strip)
sd.text((30,18), "Legibilidad a tamano real (Spotlight/Ajustes): 120 / 80 / 60 / 40 px",
        fill=(180,225,240), font=f)
picks = [("c1_dogfill_white", dict(made)[ "c1_dogfill_white"] if False else None)]
def get(name):
    for n,p,ic in made:
        if n==name: return ic
    return None
xoff = 30
for name,lab in [("c1_dogfill_white","Dog solido"),("c4_pawfill_white","Huella")]:
    ic = get(name)
    yb = 80
    sd.text((xoff, yb-4), lab, fill=(210,230,240), font=f)
    xx = xoff
    for s in (120,80,60,40):
        small = rounded(ic).resize((s,s), Image.LANCZOS)
        strip.paste(small, (xx, yb+30 + (120-s)), small)
        xx += s + 16
    xoff += 360
strip.save(os.path.join(OUT, "_size_strip.png"))
print("saved size strip")
print("DONE ->", OUT)
