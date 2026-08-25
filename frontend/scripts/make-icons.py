"""Generate the PWA raster icons from the ForgeFit mark.

iOS Safari does not accept SVG for Add to Home Screen, and Android wants a
maskable icon or it letterboxes yours inside a white rounded square. The
manifest previously offered only favicon.svg, so installs looked broken on
both.

Run after any change to the mark or palette:

    python frontend/scripts/make-icons.py

PALETTE NOTE: these are the *current shipped* colours (near-black + lime).
When the ink redesign is wired into frontend/src, change GROUND and ACCENT to
#171615 and #ff563c, re-run this, and update theme_color/background_color in
frontend/public/manifest.json to match.
"""

from pathlib import Path

from PIL import Image, ImageDraw

GROUND = "#0a0a0b"
ACCENT = "#c8f542"

OUT = Path(__file__).resolve().parent.parent / "public" / "icons"

# The mark, in the 64-unit coordinate space of favicon.svg.
VIEWBOX = 64.0
TRIANGLE = [(16, 40), (32, 12), (48, 40)]
BAR = (22, 36, 42, 42)
STROKE = 3.0


def draw_mark(size: int, inset: float = 1.0) -> Image.Image:
    """inset < 1 shrinks the mark toward the centre, for maskable safe zones."""
    # Supersample, then downscale — Pillow has no antialiased primitives.
    ss = 4
    px = size * ss
    img = Image.new("RGBA", (px, px), GROUND)
    d = ImageDraw.Draw(img)

    def pt(x, y):
        scale = px / VIEWBOX * inset
        offset = px * (1 - inset) / 2
        return (x * scale + offset, y * scale + offset)

    width = max(1, round(STROKE * px / VIEWBOX * inset))

    d.line([pt(*p) for p in TRIANGLE] + [pt(*TRIANGLE[0])],
           fill=ACCENT, width=width, joint="curve")
    d.rectangle([pt(BAR[0], BAR[1]), pt(BAR[2], BAR[3])], fill=ACCENT)

    return img.resize((size, size), Image.LANCZOS)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)

    for size in (192, 512):
        draw_mark(size).save(OUT / f"icon-{size}.png")

    # Maskable: Android crops to a circle on many launchers, so the glyph has
    # to sit inside the middle ~80% or it loses its corners.
    draw_mark(512, inset=0.62).save(OUT / "icon-maskable-512.png")

    # iOS composites onto white if there is any alpha, and applies its own
    # corner mask, so this one is flattened and full-bleed.
    draw_mark(180).convert("RGB").save(OUT / "apple-touch-icon.png")

    for f in sorted(OUT.iterdir()):
        print(f"{f.name}: {f.stat().st_size:,} bytes")


if __name__ == "__main__":
    main()
