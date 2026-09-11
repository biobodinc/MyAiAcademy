"""Generate the website's icons from one vector definition.

No image library is available in every environment this repo builds in, and pulling a
rasteriser in for four small files is not worth it, so this writes PNGs directly: shapes
are filled with a scanline polygon rasteriser at 4x and box-filtered down, then encoded
with zlib. Re-run it whenever the mark changes:

    uv run python scripts/generate_web_icons.py

Outputs (committed, so the site builds without Python):
    apps/website/app/apple-icon.png              180x180 opaque, iOS home screen
    apps/website/public/icons/icon-192.png       192x192 rounded badge
    apps/website/public/icons/icon-512.png       512x512 rounded badge
    apps/website/public/icons/icon-maskable.png  512x512 full bleed, Android maskable
"""

from __future__ import annotations

import math
import struct
import zlib
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WEBSITE = ROOT / "apps" / "website"

ACCENT = (109, 74, 255, 255)  # --accent in globals.css
WHITE = (255, 255, 255, 255)
TRANSPARENT = (0, 0, 0, 0)
SUPERSAMPLE = 4

Point = tuple[float, float]
Colour = tuple[int, int, int, int]


@dataclass(frozen=True, slots=True)
class Shape:
    """A filled polygon in unit coordinates (0..1 across the canvas)."""

    points: tuple[Point, ...]
    colour: Colour


def rounded_square(radius: float, colour: Colour, inset: float = 0.0) -> Shape:
    """A square with rounded corners, as a polygon."""
    lo, hi = inset, 1.0 - inset
    r = radius
    corners = [
        ((hi - r, hi - r), 0.0),  # bottom-right quadrant start angle
        ((lo + r, hi - r), 90.0),
        ((lo + r, lo + r), 180.0),
        ((hi - r, lo + r), 270.0),
    ]
    points: list[Point] = []
    for (cx, cy), start in corners:
        for step in range(13):
            angle = math.radians(start + step * 7.5)
            points.append((cx + r * math.cos(angle), cy + r * math.sin(angle)))
    return Shape(tuple(points), colour)


def circle(cx: float, cy: float, r: float, colour: Colour) -> Shape:
    points = tuple(
        (cx + r * math.cos(math.tau * i / 48), cy + r * math.sin(math.tau * i / 48))
        for i in range(48)
    )
    return Shape(points, colour)


def mortarboard(scale: float, cy: float) -> list[Shape]:
    """The graduation cap, centred horizontally, scaled about ``(0.5, cy)``."""

    def p(x: float, y: float) -> Point:
        return (0.5 + (x - 0.5) * scale, cy + (y - 0.5) * scale)

    board = Shape((p(0.5, 0.14), p(0.95, 0.35), p(0.5, 0.56), p(0.05, 0.35)), WHITE)
    # The cap under the board: straight sides with an elliptical bottom.
    cap: list[Point] = [p(0.25, 0.42), p(0.75, 0.42), p(0.75, 0.60)]
    for step in range(17):
        angle = math.radians(step * 180 / 16)
        cap.append(p(0.5 + 0.25 * math.cos(angle), 0.60 + 0.16 * math.sin(angle)))
    cap.append(p(0.25, 0.60))
    tassel_x, tassel_top, tassel_bottom, half = 0.95, 0.35, 0.74, 0.018
    cord = Shape(
        (
            p(tassel_x - half, tassel_top),
            p(tassel_x + half, tassel_top),
            p(tassel_x + half, tassel_bottom),
            p(tassel_x - half, tassel_bottom),
        ),
        WHITE,
    )
    knot_centre = p(tassel_x, tassel_bottom + 0.04)
    knot = circle(knot_centre[0], knot_centre[1], 0.045 * scale, WHITE)
    return [board, Shape(tuple(cap), WHITE), cord, knot]


def icon_shapes(*, full_bleed: bool, background: Colour = ACCENT) -> list[Shape]:
    """``full_bleed`` fills the whole square (maskable/iOS); otherwise a rounded badge."""
    if full_bleed:
        return [
            Shape(((0.0, 0.0), (1.0, 0.0), (1.0, 1.0), (0.0, 1.0)), background),
            *mortarboard(scale=0.60, cy=0.52),
        ]
    return [rounded_square(0.22, background), *mortarboard(scale=0.74, cy=0.52)]


def fill_polygon(
    buffer: bytearray, width: int, height: int, points: tuple[Point, ...], colour: Colour
) -> None:
    """Even-odd scanline fill. Pixel centres decide coverage; the caller supersamples."""
    scaled = [(x * width, y * height) for x, y in points]
    ys = [y for _, y in scaled]
    top = max(0, math.floor(min(ys)))
    bottom = min(height - 1, math.ceil(max(ys)))
    red, green, blue, alpha = colour
    for row in range(top, bottom + 1):
        centre = row + 0.5
        crossings: list[float] = []
        for index in range(len(scaled)):
            x0, y0 = scaled[index]
            x1, y1 = scaled[(index + 1) % len(scaled)]
            if (y0 <= centre < y1) or (y1 <= centre < y0):
                crossings.append(x0 + (centre - y0) / (y1 - y0) * (x1 - x0))
        crossings.sort()
        for pair in range(0, len(crossings) - 1, 2):
            start = max(0, math.ceil(crossings[pair] - 0.5))
            end = min(width - 1, math.floor(crossings[pair + 1] - 0.5))
            for column in range(start, end + 1):
                offset = (row * width + column) * 4
                buffer[offset : offset + 4] = bytes((red, green, blue, alpha))


def render(size: int, shapes: list[Shape]) -> bytes:
    """Render at ``size`` after supersampling, and return raw RGBA bytes."""
    big = size * SUPERSAMPLE
    buffer = bytearray(big * big * 4)
    for shape in shapes:
        fill_polygon(buffer, big, big, shape.points, shape.colour)

    out = bytearray(size * size * 4)
    samples = SUPERSAMPLE * SUPERSAMPLE
    for row in range(size):
        for column in range(size):
            totals = [0, 0, 0, 0]
            for sub_row in range(SUPERSAMPLE):
                base = ((row * SUPERSAMPLE + sub_row) * big + column * SUPERSAMPLE) * 4
                for sub_column in range(SUPERSAMPLE):
                    offset = base + sub_column * 4
                    for channel in range(4):
                        totals[channel] += buffer[offset + channel]
            target = (row * size + column) * 4
            out[target : target + 4] = bytes(total // samples for total in totals)
    return bytes(out)


def write_png(path: Path, size: int, rgba: bytes) -> None:
    raw = bytearray()
    stride = size * 4
    for row in range(size):
        raw.append(0)  # filter type 0 (None)
        raw.extend(rgba[row * stride : (row + 1) * stride])

    def chunk(kind: bytes, payload: bytes) -> bytes:
        return (
            struct.pack(">I", len(payload))
            + kind
            + payload
            + struct.pack(">I", zlib.crc32(kind + payload) & 0xFFFFFFFF)
        )

    header = struct.pack(">IIBBBBB", size, size, 8, 6, 0, 0, 0)
    png = (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", header)
        + chunk(b"IDAT", zlib.compress(bytes(raw), 9))
        + chunk(b"IEND", b"")
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(png)
    print(f"wrote {path.relative_to(ROOT)} ({size}x{size}, {len(png) / 1024:.1f} KB)")


def main() -> None:
    badge = icon_shapes(full_bleed=False)
    bleed = icon_shapes(full_bleed=True)
    targets = [
        (WEBSITE / "app" / "apple-icon.png", 180, bleed),
        (WEBSITE / "public" / "icons" / "icon-192.png", 192, badge),
        (WEBSITE / "public" / "icons" / "icon-512.png", 512, badge),
        (WEBSITE / "public" / "icons" / "icon-maskable.png", 512, bleed),
    ]
    for path, size, shapes in targets:
        write_png(path, size, render(size, shapes))


if __name__ == "__main__":
    main()
