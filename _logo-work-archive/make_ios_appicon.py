#!/usr/bin/env python3
"""Install the APPROVED logo (cyan+white line-art dog on emerald) as the iOS
native app icon for the Capacitor wrapper in `mobile/`.

Modern Xcode (14+) asset catalogs use a SINGLE 1024x1024 universal icon
(`AppIcon-512@2x.png`) and derive every smaller size at build time, so that is
the one file that actually ships. We also refresh the legacy `icons-source/`
set (individual sizes) so nothing stale from the old border-collie PHOTO icon
lingers in the repo.

App Store rules enforced here: RGB, NO alpha channel, square, no rounded
corners (Apple applies the mask), exact pixel sizes. Source master is the same
1024 used for the PWA / App Store listing.
"""
import os
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
MASTER = os.path.join(HERE, "decided", "icons_new", "icon-1024x1024.png")

APPICONSET = os.path.join(
    REPO, "mobile", "ios", "App", "App",
    "Assets.xcassets", "AppIcon.appiconset", "AppIcon-512@2x.png",
)
ICONS_SOURCE = os.path.join(REPO, "mobile", "icons-source")

# Legacy individual sizes Xcode used to want (filename number == pixel size).
LEGACY_SIZES = [20, 29, 40, 58, 60, 76, 80, 87, 120, 152, 167, 180, 1024]


def flat_rgb(img):
    """Guarantee RGB, no alpha (App Store hard rule)."""
    if img.mode in ("RGBA", "LA") or "transparency" in img.info:
        bg = Image.new("RGB", img.size, (10, 26, 20))  # deep emerald, matches art
        bg.paste(img.convert("RGBA"), (0, 0), img.convert("RGBA").split()[-1])
        return bg
    return img.convert("RGB")


def main():
    master = flat_rgb(Image.open(MASTER))
    assert master.size == (1024, 1024), f"master must be 1024², got {master.size}"

    # 1) The icon that actually ships (single universal 1024 in the asset catalog)
    master.save(APPICONSET, "PNG")
    print("installed iOS app icon →", os.path.relpath(APPICONSET, REPO))

    # 2) Refresh legacy staging set so the old photo icons are gone
    for s in LEGACY_SIZES:
        out = os.path.join(ICONS_SOURCE, f"AppIcon-{s}.png")
        master.resize((s, s), Image.LANCZOS).save(out, "PNG")
    print(f"refreshed {len(LEGACY_SIZES)} legacy icons-source PNGs")

    # sanity report
    chk = Image.open(APPICONSET)
    print("verify:", chk.size, chk.mode, "| alpha:",
          chk.mode in ("RGBA", "LA") or "transparency" in chk.info)


if __name__ == "__main__":
    main()
