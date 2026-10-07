"""Draws the Silai Rahm mark (apps/core/mark.py) — a tree with a twisted trunk
whose branches end in the people of a family, gold on indigo — and writes
every icon the site and the Mac app need.

    python tools/make_icons.py
"""
import subprocess
import sys
from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parent.parent
GOLD = (240, 195, 78, 255)
INDIGO_A, INDIGO_B = (24, 33, 82), (59, 59, 146)
SS = 4  # supersampling
sys.path.insert(0, str(ROOT))
from apps.core import mark  # noqa: E402 - the one description of the mark

MARK_SVG = mark.svg()


def gradient(size):
    img = Image.new("RGB", (size, size))
    px = img.load()
    for y in range(size):
        for x in range(size):
            t = (x + y) / (2 * size - 2)
            px[x, y] = tuple(round(a + (b - a) * t) for a, b in zip(INDIGO_A, INDIGO_B))
    return img


def draw_mark(draw, box, colour, weight=2.0):
    """The mark inside `box` = (x, y, size); coordinates follow templates/partials/logo.svg (32 units)."""
    x0, y0, size = box
    k = size / 32

    def p(x, y):
        return (x0 + x * k, y0 + y * k)

    w = max(1, round(weight * k))

    def line(points):
        draw.line([p(*pt) for pt in points], fill=colour, width=w, joint="curve")
        r = w / 2
        for pt in points:  # round caps and joins
            cx, cy = p(*pt)
            draw.ellipse((cx - r, cy - r, cx + r, cy + r), fill=colour)

    for points in mark.polylines():
        line(points)
    for cx, cy, r in mark.NODES:
        a, b = p(cx - r, cy - r), p(cx + r, cy + r)
        draw.ellipse((a[0], a[1], b[0], b[1]), fill=colour)


def app_icon(size, radius=0.225, margin=0.0, mark=0.56):
    """Rounded indigo tile with the gold mark. `margin`: transparent border (macOS icons)."""
    big = size * SS
    tile = big * (1 - 2 * margin)
    img = Image.new("RGBA", (big, big), (0, 0, 0, 0))
    mask = Image.new("L", (big, big), 0)
    off = big * margin
    ImageDraw.Draw(mask).rounded_rectangle((off, off, off + tile, off + tile), radius=tile * radius, fill=255)
    img.paste(gradient(big), (0, 0), mask)
    draw = ImageDraw.Draw(img)
    m = tile * mark
    draw_mark(draw, (off + (tile - m) / 2, off + (tile - m) / 2 - tile * 0.01, m), GOLD, weight=2.1)
    return img.resize((size, size), Image.LANCZOS)


def badge(size=96):
    """Monochrome mark for the Android status bar."""
    big = size * SS
    img = Image.new("RGBA", (big, big), (0, 0, 0, 0))
    draw_mark(ImageDraw.Draw(img), (big * 0.08, big * 0.08, big * 0.84), (255, 255, 255, 255), weight=2.6)
    return img.resize((size, size), Image.LANCZOS)


def main():
    static = ROOT / "static" / "img"
    (ROOT / "templates" / "partials" / "logo.svg").write_text(
        '<svg viewBox="0 0 32 32" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" '
        'stroke-linejoin="round" aria-hidden="true">' + MARK_SVG + "</svg>\n", encoding="utf-8")
    app_icon(192).save(static / "icon-192.png")
    app_icon(512).save(static / "icon-512.png")
    app_icon(512, radius=0, mark=0.46).save(static / "icon-maskable-512.png")
    badge().save(static / "badge.png")
    (static / "icon.svg").write_text(
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64">'
        '<defs><linearGradient id="g" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#182152"/>'
        '<stop offset="1" stop-color="#3b3b92"/></linearGradient></defs>'
        '<rect width="64" height="64" rx="14.5" fill="url(#g)"/>'
        '<g transform="translate(14 13.5) scale(1.125)" fill="none" stroke="#f0c34e" stroke-width="2.1" '
        'stroke-linecap="round" stroke-linejoin="round">' + MARK_SVG.replace("currentColor", "#f0c34e") + "</g></svg>\n",
        encoding="utf-8")

    # macOS app icon (with the standard transparent margin) → .icns
    mac = ROOT / "macos"
    master = app_icon(1024, radius=0.2237, margin=0.0977, mark=0.54)
    master.save(mac / "Resources" / "icon-1024.png")
    iconset = mac / "build" / "AppIcon.iconset"
    iconset.mkdir(parents=True, exist_ok=True)
    for base in (16, 32, 128, 256, 512):
        for scale in (1, 2):
            px = base * scale
            name = f"icon_{base}x{base}{'@2x' if scale == 2 else ''}.png"
            master.resize((px, px), Image.LANCZOS).save(iconset / name)
    try:
        subprocess.run(["iconutil", "-c", "icns", str(iconset), "-o", str(mac / "Resources" / "AppIcon.icns")], check=True)
    except (FileNotFoundError, subprocess.CalledProcessError):
        print("iconutil not available: the .icns was not rebuilt")
    print("icons written")


if __name__ == "__main__":
    main()
